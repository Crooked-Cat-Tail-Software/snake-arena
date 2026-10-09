#!/usr/bin/env bash
set -euo pipefail

# Deploys the shared observability stack (01-observability.yaml): the
# metrics log group, alarm topic, CloudWatch dashboard and X-Ray groups
# that dev and prod both use. Deploy it once, before the app stacks
# (deploy.sh checks); rerunning it is safe and updates it in place.
#
# Usage: ./deploy-observability.sh [aws-region]      Default: us-east-2
# Alarm emails: ALARM_EMAIL=you@example.com ./deploy-observability.sh
# (AWS emails a confirmation link first). Unset keeps the current
# setting; ALARM_EMAIL= (empty) turns emails off.

AWS_REGION="${1:-us-east-2}"
STACK_NAME="snake-arena-observability"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found -- install it and sign in first."; exit 1; }

echo "== Snake Arena observability stack ($STACK_NAME, $AWS_REGION) =="
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file "$SCRIPT_DIR/01-observability.yaml" \
  ${ALARM_EMAIL+--parameter-overrides AlarmEmail="$ALARM_EMAIL"} \
  --no-fail-on-empty-changeset \
  --region "$AWS_REGION"

echo
echo "Dashboard:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" \
  --output text
