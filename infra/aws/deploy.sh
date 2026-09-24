#!/usr/bin/env bash
set -euo pipefail

# Deploys Snake Arena to AWS: ECR repository -> build & push the image ->
# app stack (VPC, RDS Postgres, ECS Fargate, ALB). Run this yourself, from
# your own machine, with the AWS CLI configured (aws configure) and
# Docker running -- this script is not run by Claude. See README.md in
# this directory for the full picture, a cost estimate, and how to tear
# it back down when you're done (./teardown.sh).
#
# Usage: ./deploy.sh [project-name] [aws-region]
# Defaults: snake-arena, us-east-2 (us-east-2 because that's this
# project's assigned Region under the new AWS experience account type --
# see ~/.claude/CLAUDE.md's AWS Agent Toolkit rules if that applies to
# you. Pass a different Region explicitly if yours differs.)

PROJECT_NAME="${1:-snake-arena}"
AWS_REGION="${2:-us-east-2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_TAG="$(date +%Y%m%d%H%M%S)"

echo "== Snake Arena AWS deploy =="
echo "Project: $PROJECT_NAME   Region: $AWS_REGION   Image tag: $IMAGE_TAG"
echo

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found -- install it and run 'aws configure' first."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker not found -- install/start Docker first."; exit 1; }

echo "--> [1/5] Deploying ECR repository stack..."
aws cloudformation deploy \
  --stack-name "${PROJECT_NAME}-ecr" \
  --template-file "$SCRIPT_DIR/01-ecr.yaml" \
  --parameter-overrides ProjectName="$PROJECT_NAME" \
  --region "$AWS_REGION"

REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name "${PROJECT_NAME}-ecr" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue" \
  --output text)
echo "ECR repository: $REPO_URI"
echo

echo "--> [2/5] Building the image (this is the same Dockerfile 'docker compose build' uses)..."
docker build -t "${PROJECT_NAME}:${IMAGE_TAG}" "$REPO_ROOT"
docker tag "${PROJECT_NAME}:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"
echo

echo "--> [3/5] Pushing to ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${REPO_URI%%/*}"
docker push "${REPO_URI}:${IMAGE_TAG}"
echo

echo "--> [4/5] Deploying the app stack (VPC, RDS, ECS, ALB)..."
echo "    This step takes the longest -- RDS alone is typically 5-10 minutes."
echo "    (First deploy only; updates after this are much faster.)"
aws cloudformation deploy \
  --stack-name "${PROJECT_NAME}-app" \
  --template-file "$SCRIPT_DIR/02-app.yaml" \
  --parameter-overrides ProjectName="$PROJECT_NAME" ImageUri="${REPO_URI}:${IMAGE_TAG}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$AWS_REGION"
echo

echo "--> [5/5] Done. App URL:"
APP_URL=$(aws cloudformation describe-stacks \
  --stack-name "${PROJECT_NAME}-app" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='AppUrl'].OutputValue" \
  --output text)
echo "$APP_URL"
echo
echo "(The ALB can take a minute or two after this to start passing health"
echo " checks -- if the URL doesn't load right away, wait a bit and retry.)"
echo
echo "When you're done, tear everything down with: ./teardown.sh $PROJECT_NAME $AWS_REGION"
