#!/usr/bin/env bash
set -euo pipefail

# Deploy stage: serves an image that build.sh (the build stage) already
# pushed to ECR. Deploys/updates the app stack (VPC, RDS Postgres, ECS
# Fargate, ALB) pointing at that image; ECS pulls it from ECR. Nothing is
# built here and Docker isn't needed. See README.md in this directory for
# the full picture, a cost estimate, and ./teardown.sh.
#
# Usage: ./deploy.sh [project-name] [aws-region] [db-deletion-protection] [image-tag]
# Defaults: snake-arena, us-east-2, false, the most recently pushed image
#
# Typical dev flow:
#   ./build.sh                 # build + push, prints e.g. 20260818-163457-83242da
#   ./deploy.sh                # deploy the newest image (or pass its tag as arg 4)
#
# Dev and production are two independent copies of the same stacks,
# told apart only by project name. Prod is created once with
#   ./build.sh snake-arena-prod && ./deploy.sh snake-arena-prod us-east-2 true
# and after that only updated with ./promote.sh, which ships the image dev
# is running. The third argument turns on RDS deletion protection --
# always pass "true" for prod. (Region defaults to us-east-2 because
# that's this project's assigned Region under the new AWS experience
# account type. Pass a different Region explicitly if yours differs.)

PROJECT_NAME="${1:-snake-arena}"
AWS_REGION="${2:-us-east-2}"
DB_DELETION_PROTECTION="${3:-false}"
IMAGE_TAG="${4:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Reported on every trace as deployment.environment.name.
case "$PROJECT_NAME" in
  *-prod) DEPLOY_ENV=prod ;;
  *) DEPLOY_ENV=dev ;;
esac

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found -- install it and sign in first."; exit 1; }

echo "== Snake Arena deploy =="
echo "Project: $PROJECT_NAME ($DEPLOY_ENV)   Region: $AWS_REGION   DB deletion protection: $DB_DELETION_PROTECTION"
echo

# The app stack imports the shared metrics log group and alarm topic.
if ! aws cloudformation describe-stacks --stack-name snake-arena-observability \
    --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "No snake-arena-observability stack -- run ./deploy-observability.sh $AWS_REGION first"
  echo "(once; dev and prod share it)."
  exit 1
fi

echo "--> [1/3] Finding the image in ECR..."
if ! REPO_URI=$(aws cloudformation describe-stacks \
    --stack-name "${PROJECT_NAME}-ecr" \
    --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue" \
    --output text 2>/dev/null); then
  echo "No ${PROJECT_NAME}-ecr stack -- run ./build.sh $PROJECT_NAME $AWS_REGION first."
  exit 1
fi
REPO_NAME="${REPO_URI#*/}"

if [ -z "$IMAGE_TAG" ]; then
  IMAGE_TAG=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --region "$AWS_REGION" \
    --query "sort_by(imageDetails[?imageTags != null], &imagePushedAt)[-1].imageTags[0]" \
    --output text)
  if [ -z "$IMAGE_TAG" ] || [ "$IMAGE_TAG" = "None" ]; then
    echo "No images in $REPO_NAME -- run ./build.sh $PROJECT_NAME $AWS_REGION first."
    exit 1
  fi
  echo "No tag given -- using the most recently pushed image."
elif ! aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --region "$AWS_REGION" \
    --image-ids imageTag="$IMAGE_TAG" >/dev/null 2>&1; then
  echo "Image tag $IMAGE_TAG isn't in $REPO_NAME -- build/push it first with ./build.sh."
  exit 1
fi
IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"
echo "Image: $IMAGE_URI"
echo

echo "--> [2/3] Deploying the app stack (VPC, RDS, ECS, ALB)..."
echo "    First deploy takes the longest -- RDS alone is typically 5-10 minutes."
aws cloudformation deploy \
  --stack-name "${PROJECT_NAME}-app" \
  --template-file "$SCRIPT_DIR/02-app.yaml" \
  --parameter-overrides ProjectName="$PROJECT_NAME" ImageUri="$IMAGE_URI" \
    DBDeletionProtection="$DB_DELETION_PROTECTION" DeploymentEnvironment="$DEPLOY_ENV" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --region "$AWS_REGION"
echo

echo "--> [3/3] Done. App URL:"
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
