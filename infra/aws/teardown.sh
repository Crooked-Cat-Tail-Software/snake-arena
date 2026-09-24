#!/usr/bin/env bash
set -euo pipefail

# Tears down everything deploy.sh created: deletes the app stack (ALB,
# ECS, RDS -- this destroys the Postgres database and all its data, i.e.
# the leaderboard) and then the ECR repository stack (and every image in
# it). Irreversible. Run this yourself; it is not run by Claude.
#
# Usage: ./teardown.sh [project-name] [aws-region]
# Defaults: snake-arena, us-east-2 (matches deploy.sh's default -- see
# its comment for why)

PROJECT_NAME="${1:-snake-arena}"
AWS_REGION="${2:-us-east-2}"

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found -- install it and run 'aws configure' first."; exit 1; }

echo "This will DELETE the ${PROJECT_NAME}-app stack, including its RDS"
echo "database and all data in it (the leaderboard), and then the"
echo "${PROJECT_NAME}-ecr repository and every image in it."
echo
read -r -p "Type the project name (${PROJECT_NAME}) to confirm: " CONFIRM
if [ "$CONFIRM" != "$PROJECT_NAME" ]; then
  echo "Confirmation didn't match, aborting. Nothing was deleted."
  exit 1
fi

echo
echo "--> Deleting app stack (this can take several minutes, mostly RDS)..."
aws cloudformation delete-stack --stack-name "${PROJECT_NAME}-app" --region "$AWS_REGION"
aws cloudformation wait stack-delete-complete --stack-name "${PROJECT_NAME}-app" --region "$AWS_REGION"
echo "App stack deleted."
echo

echo "--> Emptying the ECR repository (CloudFormation won't delete a repo that still has images in it)..."
REPO_NAME=$(aws cloudformation describe-stacks \
  --stack-name "${PROJECT_NAME}-ecr" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryName'].OutputValue" \
  --output text)
IMAGE_IDS=$(aws ecr list-images --repository-name "$REPO_NAME" --region "$AWS_REGION" --query 'imageIds[*]' --output json)
if [ "$IMAGE_IDS" != "[]" ]; then
  aws ecr batch-delete-image --repository-name "$REPO_NAME" --region "$AWS_REGION" --image-ids "$IMAGE_IDS" >/dev/null
  echo "Deleted all images in $REPO_NAME."
else
  echo "Repository already empty."
fi
echo

echo "--> Deleting ECR stack..."
aws cloudformation delete-stack --stack-name "${PROJECT_NAME}-ecr" --region "$AWS_REGION"
aws cloudformation wait stack-delete-complete --stack-name "${PROJECT_NAME}-ecr" --region "$AWS_REGION"
echo

echo "Done -- all AWS resources for ${PROJECT_NAME} have been deleted."
