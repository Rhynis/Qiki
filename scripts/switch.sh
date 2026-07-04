#!/usr/bin/env bash
# Trigger the "Switch Backend" workflow, wait for it, and report a clear result.
# Unlike `gh workflow run` (which returns immediately), this blocks until the switch
# finishes and prints whether prod actually changed.
#
#   scripts/switch.sh render|railway|oracle
set -euo pipefail

REPO="Rhynis/Gas-Rag-bot"
PROD_URL="https://gas-rag-bot-rhynis-projects.vercel.app"

target="${1:-}"
case "$target" in
  render | railway | oracle) ;;
  *)
    echo "usage: $0 render|railway|oracle" >&2
    exit 1
    ;;
esac

echo "→ Switching prod backend to: $target"
gh workflow run "Switch Backend" --repo "$REPO" -f target="$target" >/dev/null
echo "  triggered; waiting for the run to start…"
sleep 6

run_id="$(gh run list --workflow 'Switch Backend' --repo "$REPO" --limit 1 \
  --json databaseId --jq '.[0].databaseId')"
echo "  run #$run_id started — deploying (~2 min), please wait…"

if gh run watch "$run_id" --repo "$REPO" --interval 15 --exit-status >/dev/null 2>&1; then
  echo "✅ SWITCHED: prod BACKEND_URL is now → $target"
else
  echo "❌ FAILED: prod was NOT changed. Inspect the log with:"
  echo "     gh run view $run_id --repo $REPO --log-failed"
  exit 1
fi

echo "→ Verifying the live site responds…"
code="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 60 "$PROD_URL/health" || true)"
if [[ "$code" == "200" ]]; then
  echo "   prod /health → HTTP 200 (OK) ✅"
else
  echo "   prod /health → HTTP ${code:-000} ⚠️  (check the site / backend)"
fi
