#!/usr/bin/env bash
set -euo pipefail

# Promotes the version currently running in dev to production: the exact
# image dev's ECS service runs is copied into prod's ECR repository (same
# tag, no rebuild) and prod's app stack is updated to run it. Prod only
# ever receives an image that has already run in dev -- "build once,
# promote" -- so what you tested is byte-for-byte what ships.
#
# Dev must be deployed and healthy (./deploy.sh): teardown.sh deletes
# dev's ECR repository, so there's nothing to promote while dev is down.
# Prod must already exist -- create it once with
#   ./deploy.sh snake-arena-prod us-east-2 true
# and use this script for every prod update after that.
#
# Used by .github/workflows/promote.yaml; also runnable by hand.
#
# Usage: ./promote.sh [source-project] [target-project] [aws-region]
# Defaults: snake-arena, snake-arena-prod, us-east-2

SOURCE_PROJECT="${1:-snake-arena}"
TARGET_PROJECT="${2:-snake-arena-prod}"
AWS_REGION="${3:-us-east-2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found -- install it and sign in first."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker not found -- install/start Docker first."; exit 1; }

stack_output() {
  aws cloudformation describe-stacks --stack-name "$1" --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text
}

stack_parameter() {
  aws cloudformation describe-stacks --stack-name "$1" --region "$AWS_REGION" \
    --query "Stacks[0].Parameters[?ParameterKey=='$2'].ParameterValue" --output text
}

echo "== Snake Arena promotion: $SOURCE_PROJECT -> $TARGET_PROJECT ($AWS_REGION) =="
echo

echo "--> [1/5] Finding the image dev is running..."
if ! SOURCE_IMAGE=$(stack_parameter "${SOURCE_PROJECT}-app" ImageUri 2>/dev/null) || [ -z "$SOURCE_IMAGE" ] || [ "$SOURCE_IMAGE" = "None" ]; then
  echo "No ${SOURCE_PROJECT}-app stack found -- deploy dev first (./deploy.sh) and test it."
  exit 1
fi
IMAGE_TAG="${SOURCE_IMAGE##*:}"
echo "Dev image: $SOURCE_IMAGE"
echo

echo "--> [2/5] Checking dev is healthy before promoting it..."
SOURCE_URL=$(stack_output "${SOURCE_PROJECT}-app" AppUrl)
if ! curl -fsS --max-time 10 "$SOURCE_URL/api/health"; then
  echo
  echo "Dev ($SOURCE_URL) isn't healthy -- not promoting an image that isn't working in dev."
  exit 1
fi
echo
echo

echo "--> [3/5] Copying the image to prod's ECR repository (no rebuild)..."
TARGET_REPO=$(stack_output "${TARGET_PROJECT}-ecr" RepositoryUri)
TARGET_IMAGE="${TARGET_REPO}:${IMAGE_TAG}"
# Both repositories live in the same account's registry, so one login
# covers the pull and the push. Pulling linux/amd64 explicitly matches
# the platform Fargate runs (see RuntimePlatform in 02-app.yaml).
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${TARGET_REPO%%/*}"
docker pull --platform linux/amd64 "$SOURCE_IMAGE"
docker tag "$SOURCE_IMAGE" "$TARGET_IMAGE"
docker push "$TARGET_IMAGE"
echo

echo "--> [4/5] Updating the prod app stack to run $IMAGE_TAG..."
# DBDeletionProtection stays "true" -- this script only ever targets prod.
aws cloudformation deploy \
  --stack-name "${TARGET_PROJECT}-app" \
  --template-file "$SCRIPT_DIR/02-app.yaml" \
  --parameter-overrides ProjectName="$TARGET_PROJECT" ImageUri="$TARGET_IMAGE" \
    DBDeletionProtection=true \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --region "$AWS_REGION"
echo

echo "--> [5/5] Checking prod is healthy..."
TARGET_URL=$(stack_output "${TARGET_PROJECT}-app" AppUrl)
for i in $(seq 1 30); do
  if curl -fsS --max-time 5 "$TARGET_URL/api/health"; then
    echo
    echo "Promoted $IMAGE_TAG to $TARGET_PROJECT -- healthy after ${i} attempt(s)."
    echo "$TARGET_URL"
    exit 0
  fi
  echo "Not ready yet (attempt $i/30) -- waiting 10s..."
  sleep 10
done
echo "$TARGET_URL/api/health never returned a healthy response after 5 minutes."
exit 1
