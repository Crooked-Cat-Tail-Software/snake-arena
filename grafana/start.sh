#!/usr/bin/env bash
set -euo pipefail

# Starts local Grafana (http://localhost:3000) with the Snake Arena
# dashboard. Grafana reads CloudWatch through your `aws login` session
# (see the grafana service in docker-compose.yml) and renews its
# short-lived credentials itself, so it keeps working until that session
# ends -- then run `aws login` again; no restart needed.
#
# Usage: grafana/start.sh        (AWS_PROFILE=<name> to use another profile)
# Stop:  docker compose --profile monitoring stop grafana

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v aws >/dev/null 2>&1 || { echo "aws CLI not found."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker not found -- start Docker first."; exit 1; }

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "No valid AWS session -- run 'aws login' first."
  exit 1
fi
if [ ! -d "$HOME/.aws/login" ]; then
  echo "No ~/.aws/login session folder -- this setup expects credentials from"
  echo "'aws login'. Run 'aws login' first."
  exit 1
fi

docker compose -f "$REPO_ROOT/docker-compose.yml" --profile monitoring up -d grafana
echo
echo "Grafana: http://localhost:3000"
