#!/usr/bin/env bash
# Point the Vercel frontend at one of the interchangeable backends and redeploy.
#
# Manual (interactive — unchanged):
#   ./scripts/switch-backend.sh railway|render|oracle
# Direct URL (used by CI / scripts/health_failover.sh):
#   ./scripts/switch-backend.sh --url https://host.example "label"
#
# All backends must share the SAME JWT_SECRET_KEY + Upstash Redis + Supabase DB so the switch
# is seamless (see docs/HOSTING.md). A switch sets the BACKEND_URL prod env then redeploys
# (Vercel needs a redeploy for env changes to take effect) — takes ~2 min.
#
# Non-interactive / CI: set VERCEL_TOKEN (plus VERCEL_ORG_ID and VERCEL_PROJECT_ID) and the
# core runs without `vercel login` / `vercel link`. Interactive use relies on your logged-in
# session and linked project, exactly as before.
set -euo pipefail

# Named-mode host URLs. Overridable via env (repo variables in CI); the Railway default keeps
# the manual command working out of the box.
RAILWAY_URL="${RAILWAY_URL:-https://gas-rag-bot-production.up.railway.app}"
RENDER_URL="${RENDER_URL:-https://gasbot-backend.onrender.com}"
ORACLE_URL="${ORACLE_URL:-https://FILL-ME}"

VERCEL_BIN="${VERCEL_BIN:-vercel}"

# Run the Vercel CLI, adding --token automatically when VERCEL_TOKEN is set (CI). With a token,
# VERCEL_ORG_ID + VERCEL_PROJECT_ID in the environment select the project without `vercel link`.
vercel_cli() {
  if [[ -n "${VERCEL_TOKEN:-}" ]]; then
    "$VERCEL_BIN" "$@" --token "$VERCEL_TOKEN"
  else
    "$VERCEL_BIN" "$@"
  fi
}

# Core: set the production BACKEND_URL and trigger a prod redeploy. Callable directly by CI.
apply_backend_url() {
  local url="$1"
  local label="${2:-custom}"
  local frontend_dir root_dir
  frontend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../frontend" && pwd)"
  root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  # Update the env var (cwd-independent; project selected by the link or VERCEL_*_ID).
  (
    cd "$frontend_dir"
    vercel_cli env rm BACKEND_URL production --yes >/dev/null 2>&1 || true
    printf '%s' "$url" | vercel_cli env add BACKEND_URL production
  )
  # Redeploy from the REPO ROOT: the Vercel project's Root Directory is "frontend", so deploying
  # from frontend/ makes Vercel append it again -> ".../frontend/frontend does not exist".
  (
    cd "$root_dir"
    vercel_cli --prod --yes
  )
  echo "BACKEND_URL -> $url ($label). Redeploy triggered (~2 min)."
}

_require_configured() {
  local url="$1" name="$2"
  if [[ -z "$url" || "$url" == *FILL-ME* ]]; then
    echo "Set the $name URL (env var or scripts/switch-backend.sh default) first." >&2
    exit 1
  fi
}

main() {
  case "${1:-}" in
    --url)
      _require_configured "${2:-}" "target"
      apply_backend_url "$2" "${3:-custom}"
      ;;
    railway)
      _require_configured "$RAILWAY_URL" railway
      apply_backend_url "$RAILWAY_URL" railway
      ;;
    render)
      _require_configured "$RENDER_URL" render
      apply_backend_url "$RENDER_URL" render
      ;;
    oracle)
      _require_configured "$ORACLE_URL" oracle
      apply_backend_url "$ORACLE_URL" oracle
      ;;
    *)
      echo "usage: $0 railway|render|oracle | --url <URL> [label]" >&2
      exit 1
      ;;
  esac
}

# Only run when executed directly, so other scripts may source the core functions.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
