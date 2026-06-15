#!/usr/bin/env bash
# Deploy / update the Gasbot backend on a VPS (Oracle Cloud).
# First run: clone the repo, create deploy/oracle/.env (see .env.example), install Docker +
# the compose plugin, then run this script. Re-run it to deploy the latest main.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo "Missing $SCRIPT_DIR/.env — copy .env.example and fill it (never commit it)." >&2
  exit 1
fi

cd "$REPO_ROOT"
git fetch --prune origin
git checkout main
git pull --ff-only origin main

docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d --build
docker image prune -f >/dev/null 2>&1 || true

echo "Deployed. Health: curl -f http://127.0.0.1:8000/health"
