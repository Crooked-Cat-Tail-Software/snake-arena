#!/usr/bin/env bash
set -euo pipefail

# Build stage: builds the app image from the repo's Dockerfile and pushes
# it to the project's ECR repository. Nothing is deployed -- deploy.sh
# (the deploy stage) then serves an image from ECR by its tag.
#
# Every image is tagged YYYYMMDD-HHMMSS-shortsha (UTC time + the commit
# it was built from), e.g. 20260818-163457-83242da, so any running image
# can be traced back to its exact commit. Because of that, this refuses
# to build with uncommitted changes to tracked files -- the tag would
# claim a commit the image doesn't match. Set ALLOW_DIRTY=1 to build
# anyway (e.g. a quick dev experiment); such a tag is not traceable.
#
# Usage: ./build.sh [project-name] [aws-region]
# Defaults: snake-arena, us-east-2
# Prints the tag on its last line ("IMAGE_TAG=<tag>"), and also writes
# image_tag=<tag> to $GITHUB_OUTPUT when run in GitHub Actions.

PROJECT_NAME="${1:-snake-arena}"
AWS_REGION="${2:-us-east-2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found -- install it and sign in first."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker not found -- install/start Docker first."; exit 1; }
command -v git >/dev/null 2>&1 || { echo "git not found -- needed for the commit SHA in the image tag."; exit 1; }

if [ -n "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=no)" ] && [ "${ALLOW_DIRTY:-0}" != "1" ]; then
  echo "Uncommitted changes to tracked files -- commit them first, so the image"
  echo "tag's commit SHA matches what's actually in the image:"
  git -C "$REPO_ROOT" status --short --untracked-files=no
  echo "(Or rerun with ALLOW_DIRTY=1 to build anyway.)"
  exit 1
fi

SHORT_SHA="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD)"
IMAGE_TAG="$(date -u +%Y%m%d-%H%M%S)-${SHORT_SHA}"

echo "== Snake Arena build =="
echo "Project: $PROJECT_NAME   Region: $AWS_REGION   Image tag: $IMAGE_TAG"
echo

echo "--> [1/3] Making sure the ECR repository exists..."
aws cloudformation deploy \
  --stack-name "${PROJECT_NAME}-ecr" \
  --template-file "$SCRIPT_DIR/01-ecr.yaml" \
  --parameter-overrides ProjectName="$PROJECT_NAME" \
  --no-fail-on-empty-changeset \
  --region "$AWS_REGION"

REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name "${PROJECT_NAME}-ecr" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue" \
  --output text)
echo "ECR repository: $REPO_URI"
echo

echo "--> [2/3] Building the image (this is the same Dockerfile 'docker compose build' uses)..."
# Fargate runs x86_64 (see RuntimePlatform in 02-app.yaml). Without an
# explicit platform, an Apple Silicon Mac builds an arm64 image that
# Fargate can't start ("exec format error"), and the ECS service never
# stabilizes.
# APP_VERSION becomes service.version on every trace (see Dockerfile).
docker build --platform linux/amd64 \
  --build-arg APP_VERSION="$IMAGE_TAG" \
  -t "${REPO_URI}:${IMAGE_TAG}" "$REPO_ROOT"
echo

echo "--> [3/3] Pushing to ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${REPO_URI%%/*}"
docker push "${REPO_URI}:${IMAGE_TAG}"
echo

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "image_tag=${IMAGE_TAG}" >> "$GITHUB_OUTPUT"
fi
echo "Built and pushed. Deploy it with: ./deploy.sh $PROJECT_NAME $AWS_REGION <true|false> $IMAGE_TAG"
echo "IMAGE_TAG=${IMAGE_TAG}"
