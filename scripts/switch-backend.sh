#!/usr/bin/env bash
# Point the Vercel frontend at one of the interchangeable backends and redeploy.
#
#   ./scripts/switch-backend.sh railway|render|oracle
#
# One-time setup: npm i -g vercel && vercel login && (cd frontend && vercel link)
# Fill RENDER_URL / ORACLE_URL below once those hosts are deployed.
# A switch sets the BACKEND_URL prod env then redeploys (Vercel needs a redeploy for env
# changes to take effect) — takes ~2 min. All backends must share the SAME JWT_SECRET_KEY +
# Upstash Redis + Supabase DB so the switch is seamless (see docs/HOSTING.md).
set -euo pipefail

RAILWAY_URL="https://gas-rag-bot-production.up.railway.app"
RENDER_URL="https://FILL-ME.onrender.com"      # set after the Render deploy
ORACLE_URL="https://FILL-ME"                    # set after the Oracle deploy (api.YOUR-DOMAIN)

case "${1:-}" in
  railway) URL="$RAILWAY_URL" ;;
  render)  URL="$RENDER_URL" ;;
  oracle)  URL="$ORACLE_URL" ;;
  *) echo "usage: $0 railway|render|oracle" >&2; exit 1 ;;
esac

if [[ "$URL" == *FILL-ME* ]]; then
  echo "Set the $1 URL in scripts/switch-backend.sh first." >&2
  exit 1
fi

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../frontend" && pwd)"
cd "$FRONTEND_DIR"

vercel env rm BACKEND_URL production -y >/dev/null 2>&1 || true
printf '%s' "$URL" | vercel env add BACKEND_URL production
vercel --prod

echo "✅ BACKEND_URL → $URL ($1). Redeploy triggered (~2 min)."
