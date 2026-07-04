#!/usr/bin/env bash
# Backend health monitor + conservative auto-failover for the live shop.
#
# Probes every configured backend's /health, picks the highest-priority healthy host, and
# reconciles Vercel's production BACKEND_URL to it. This job CHANGES PRODUCTION TRAFFIC ROUTING,
# so it is conservative by default:
#   * never routes to a host that is not returning 200,
#   * requires the desired host to be stable across TWO probe rounds before flipping (anti-flap),
#   * shouts (GitHub issue) on every switch and when everything is down,
#   * is a no-op when Vercel already points at the desired host (idempotent reconciliation).
#
#   scripts/health_failover.sh              # probe + reconcile (used by CI)
#   scripts/health_failover.sh --no-apply   # probe only: print per-host health + desired host
#
# Hosts by priority (highest first): the FAILOVER_PRIORITY repo variable (space-separated host
# names), default "render railway oracle" — Render primary, Railway backup. URLs come from the
# RENDER_URL / RAILWAY_URL / ORACLE_URL env / repo variables; unset or FILL-ME hosts are skipped.
#
# Current prod health is read by probing PROD_URL/health (the Vercel frontend, which proxies to
# the active backend) — the Vercel env API does not return decrypted values, so we do NOT read it.
# This reacts to an outage of the CURRENT backend; it does not auto-fail-back to the primary once
# it recovers (safer, no flapping). Applying a switch needs VERCEL_TOKEN + VERCEL_ORG_ID +
# VERCEL_PROJECT_ID (used only by scripts/switch-backend.sh to set BACKEND_URL and redeploy).
# Notifications use `gh` + GH_TOKEN when GH_NOTIFY_REPO is set; else logged. FAILOVER_DISABLED=true
# forces probe-only (still keeps hosts warm).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROBE_TIMEOUT="${PROBE_TIMEOUT:-8}"     # seconds per /health request
PROBE_ATTEMPTS="${PROBE_ATTEMPTS:-2}"   # attempts per host per round
CONFIRM_DELAY="${CONFIRM_DELAY:-15}"    # seconds between the two confirmation rounds
NOTIFY_MARKER="[ops-failover]"          # stable title marker for issue de-duplication

APPLY=1
case "${1:-}" in
  --no-apply) APPLY=0 ;;
  "") ;;
  -h | --help)
    sed -n '2,20p' "$0"
    exit 0
    ;;
  *)
    echo "usage: $0 [--no-apply]" >&2
    exit 2
    ;;
esac
[[ "${FAILOVER_DISABLED:-}" == "true" ]] && APPLY=0

log() { printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*" >&2; }

# Priority-ordered host names and their URLs (parallel arrays; unset/FILL-ME are skipped).
NAMES=()
URLS=()
add_host() {
  local name="$1" url="${2:-}"
  [[ -z "$url" || "$url" == *FILL-ME* ]] && return 0
  url="${url%/}" # normalise: drop a single trailing slash
  NAMES+=("$name")
  URLS+=("$url")
}
# Priority is configurable so hosts can be reordered/dropped without a code change (e.g. when the
# Railway trial ends). Default puts Render first, Railway as backup, Oracle last.
url_for_name() {
  case "$1" in
    railway) printf '%s' "${RAILWAY_URL:-}" ;;
    render) printf '%s' "${RENDER_URL:-}" ;;
    oracle) printf '%s' "${ORACLE_URL:-}" ;;
    *) printf '' ;;
  esac
}
read -ra _priority <<<"${FAILOVER_PRIORITY:-render railway oracle}"
for _host in "${_priority[@]}"; do
  add_host "$_host" "$(url_for_name "$_host")"
done

# GET {url}/health, healthy iff an attempt returns HTTP 200. Prints nothing sensitive.
probe() {
  local url="$1" attempt code
  for ((attempt = 1; attempt <= PROBE_ATTEMPTS; attempt++)); do
    code="$(curl -fsS -m "$PROBE_TIMEOUT" -o /dev/null -w '%{http_code}' "$url/health" 2>/dev/null || true)"
    [[ "$code" == "200" ]] && {
      printf '200'
      return 0
    }
    sleep 1
  done
  printf '%s' "${code:-000}"
  return 1
}

# One probe round over all hosts in priority order. Echoes the name of the first healthy host
# (empty if none) and logs each host's status.
probe_round() {
  local i name url code desired=""
  for i in "${!NAMES[@]}"; do
    name="${NAMES[$i]}"
    url="${URLS[$i]}"
    if code="$(probe "$url")"; then
      log "  $name: healthy (200)"
      [[ -z "$desired" ]] && desired="$name"
    else
      log "  $name: DOWN ($code)"
    fi
  done
  printf '%s' "$desired"
}

url_of() {
  local want="$1" i
  for i in "${!NAMES[@]}"; do
    [[ "${NAMES[$i]}" == "$want" ]] && {
      printf '%s' "${URLS[$i]}"
      return 0
    }
  done
  return 1
}

# Is the LIVE prod site currently served by a healthy backend? The Vercel frontend proxies
# /health to the active BACKEND_URL, so probing PROD_URL/health reflects whichever host prod
# points at — WITHOUT reading (and decrypting) the Vercel env, which the API does not return.
# Follow redirects (-L): Next rewrites /health via a 307 first.
# Returns 0 = healthy, 1 = down, 2 = unknown (PROD_URL not configured).
prod_backend_healthy() {
  local url="${PROD_URL:-}" code
  [[ -n "$url" ]] || return 2
  url="${url%/}"
  code="$(curl -sL -m "$PROBE_TIMEOUT" -o /dev/null -w '%{http_code}' "$url/health" 2>/dev/null || true)"
  [[ "$code" == "200" ]] && return 0
  log "prod: $url/health -> ${code:-000}"
  return 1
}

# Notify via a single de-duplicated GitHub issue (comment if one is already open), else log only.
notify() {
  local title="$1" body="$2"
  log "NOTIFY: $title"
  if [[ -z "${GH_NOTIFY_REPO:-}" ]] || ! command -v gh >/dev/null; then
    log "$body"
    return 0
  fi
  local existing
  existing="$(gh issue list --repo "$GH_NOTIFY_REPO" --state open \
    --search "$NOTIFY_MARKER in:title" --json number --jq '.[0].number' 2>/dev/null || true)"
  if [[ -n "$existing" ]]; then
    gh issue comment "$existing" --repo "$GH_NOTIFY_REPO" --body "$body" >/dev/null 2>&1 \
      || log "notify: gh issue comment failed"
  else
    gh issue create --repo "$GH_NOTIFY_REPO" \
      --title "$NOTIFY_MARKER $title" --body "$body" >/dev/null 2>&1 \
      || log "notify: gh issue create failed"
  fi
}

main() {
  command -v curl >/dev/null || {
    log "ERROR: curl not found"
    exit 2
  }
  command -v jq >/dev/null || {
    log "ERROR: jq not found"
    exit 2
  }
  if [[ "${#NAMES[@]}" -eq 0 ]]; then
    log "no backend hosts configured (set RAILWAY_URL / RENDER_URL / ORACLE_URL)"
    exit 0
  fi

  # Probe all candidate hosts first: this both (a) keeps free hosts (e.g. Render, which sleeps
  # after ~15 min idle) warm, and (b) identifies the highest-priority healthy host to fail over
  # to if prod is down.
  log "probe round 1:"
  local desired1
  desired1="$(probe_round)"

  # Is the live prod site currently served by a healthy backend (whichever host it points at)?
  local ph=0
  prod_backend_healthy || ph=$?
  if [[ "$ph" -eq 2 ]]; then
    log "PROD_URL not set; cannot determine current prod health — refusing to switch blindly. Set the PROD_URL repo variable."
    exit 2
  fi
  if [[ "$ph" -eq 0 ]]; then
    log "prod backend healthy; no action (hosts pinged to stay warm)"
    exit 0
  fi
  log "prod backend is DOWN -- evaluating failover"

  # Prod is down: fail over to the highest-priority healthy candidate.
  if [[ -z "$desired1" ]]; then
    notify "ALL BACKENDS DOWN" "Prod /health is failing and no configured backend returned 200 at $(date -u +%FT%TZ). Routing left unchanged."
    log "prod down and all candidates down; leaving routing unchanged"
    exit 1
  fi
  local desired_url
  desired_url="$(url_of "$desired1")"
  log "highest-priority healthy backend: $desired1 ($desired_url)"

  if [[ "$APPLY" -eq 0 ]]; then
    [[ "${FAILOVER_DISABLED:-}" == "true" ]] && log "FAILOVER_DISABLED=true (probe-only)"
    log "--no-apply: would fail over to $desired1 but not switching"
    exit 0
  fi

  # Anti-flap: require prod to still be down AND the target stable after a short delay.
  log "prod down + candidate $desired1 healthy; confirming after ${CONFIRM_DELAY}s ..."
  sleep "$CONFIRM_DELAY"
  local ph2=0
  prod_backend_healthy || ph2=$?
  if [[ "$ph2" -eq 0 ]]; then
    log "prod recovered during confirmation window; holding"
    exit 0
  fi
  log "probe round 2:"
  local desired2 desired2_url
  desired2="$(probe_round)"
  if [[ -z "$desired2" ]]; then
    notify "ALL BACKENDS DOWN" "Prod down and all candidates down at $(date -u +%FT%TZ)."
    exit 1
  fi
  if [[ "$desired2" != "$desired1" ]]; then
    log "target changed between rounds ($desired1 -> $desired2); transient, holding"
    exit 0
  fi
  desired2_url="$(url_of "$desired2")"

  log "failing over prod to $desired2 ($desired2_url)"
  if bash "$SCRIPT_DIR/switch-backend.sh" --url "$desired2_url" "$desired2"; then
    notify "failed over to $desired2" "Prod /health was failing; switched BACKEND_URL to $desired2_url ($desired2) at $(date -u +%FT%TZ) after two confirmations."
  else
    notify "FAILOVER ATTEMPT FAILED" "Tried to switch to $desired2_url ($desired2) but scripts/switch-backend.sh returned non-zero at $(date -u +%FT%TZ). Manual intervention needed."
    exit 1
  fi
}

main
