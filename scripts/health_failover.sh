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
# Applying a switch needs VERCEL_TOKEN + VERCEL_ORG_ID + VERCEL_PROJECT_ID (to read the current
# BACKEND_URL and redeploy via scripts/switch-backend.sh). Notifications use `gh` + GH_TOKEN when
# GH_NOTIFY_REPO is set; otherwise they are logged. Set FAILOVER_DISABLED=true to force probe-only.
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

# Read the current production BACKEND_URL from the Vercel API (needs the VERCEL_* vars).
# Logs the HTTP status / lookup outcome on failure (never the token or the value) so a
# misconfigured token or a missing env is diagnosable from the workflow log.
current_backend_url() {
  [[ -n "${VERCEL_TOKEN:-}" && -n "${VERCEL_PROJECT_ID:-}" && -n "${VERCEL_ORG_ID:-}" ]] || {
    log "vercel: missing VERCEL_TOKEN/ORG/PROJECT"
    return 1
  }
  local resp http body value
  resp="$(curl -sS -m 15 -w $'\n%{http_code}' \
    -H "Authorization: Bearer $VERCEL_TOKEN" \
    "https://api.vercel.com/v9/projects/$VERCEL_PROJECT_ID/env?decrypt=true&teamId=$VERCEL_ORG_ID" \
    2>/dev/null)" || {
    log "vercel: env API request failed (network/timeout)"
    return 1
  }
  http="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  if [[ "$http" != "200" ]]; then
    log "vercel: env API HTTP $http (check token scope/team + decrypt permission)"
    return 1
  fi
  value="$(printf '%s' "$body" \
    | jq -r 'first(.envs[]? | select(.key=="BACKEND_URL" and (.target|index("production"))) | .value) // empty')"
  if [[ -z "$value" ]]; then
    # Log the env keys + targets (never values) so a missing/mis-targeted BACKEND_URL,
    # or a token that lists envs but cannot decrypt values, is diagnosable.
    log "vercel: BACKEND_URL(production) not found/decrypted. keys=$(printf '%s' "$body" | jq -rc '[.envs[]? | {key, target, hasValue:(.value!=null and .value!="")}]' 2>/dev/null)"
    return 1
  fi
  printf '%s' "${value%/}"
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

  log "probe round 1:"
  local desired1
  desired1="$(probe_round)"

  # All hosts down: never switch (a dead host is no better); shout.
  if [[ -z "$desired1" ]]; then
    notify "ALL BACKENDS DOWN" "No configured backend returned 200 on /health at $(date -u +%FT%TZ). Routing left unchanged."
    log "all backends down; leaving routing unchanged"
    exit 1
  fi

  local desired_url
  desired_url="$(url_of "$desired1")"
  log "desired backend by priority: $desired1 ($desired_url)"

  if [[ "$APPLY" -eq 0 ]]; then
    [[ "${FAILOVER_DISABLED:-}" == "true" ]] && log "FAILOVER_DISABLED=true (probe-only)"
    log "--no-apply: not reading Vercel or switching"
    exit 0
  fi

  # Reconcile against the current Vercel target.
  local current
  if ! current="$(current_backend_url)"; then
    log "ERROR: cannot read current BACKEND_URL (need VERCEL_TOKEN/ORG/PROJECT); refusing to switch blindly"
    exit 2
  fi
  log "current BACKEND_URL: $current"

  if [[ "$current" == "$desired_url" ]]; then
    log "already pointing at the highest-priority healthy host; no-op"
    exit 0
  fi

  # Anti-flap: require the desired host to hold across a second round before flipping prod.
  log "switch warranted ($current -> $desired_url); confirming after ${CONFIRM_DELAY}s ..."
  sleep "$CONFIRM_DELAY"
  log "probe round 2:"
  local desired2 desired2_url
  desired2="$(probe_round)"
  if [[ "$desired2" != "$desired1" ]]; then
    log "desired changed between rounds ($desired1 -> ${desired2:-none}); transient, holding"
    exit 0
  fi
  desired2_url="$(url_of "$desired2")"
  if [[ "$current" == "$desired2_url" ]]; then
    log "current recovered to desired between rounds; holding"
    exit 0
  fi

  log "failing over: $current -> $desired2_url ($desired2)"
  if bash "$SCRIPT_DIR/switch-backend.sh" --url "$desired2_url" "$desired2"; then
    notify "failed over to $desired2" "Backend routing switched $current -> $desired2_url ($desired2) at $(date -u +%FT%TZ) after two consecutive failing rounds for the previous host."
  else
    notify "FAILOVER ATTEMPT FAILED" "Tried to switch $current -> $desired2_url ($desired2) but scripts/switch-backend.sh returned non-zero at $(date -u +%FT%TZ). Manual intervention needed."
    exit 1
  fi
}

main
