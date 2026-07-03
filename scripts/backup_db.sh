#!/usr/bin/env bash
# Encrypted daily Postgres backup for the live shop.
#
# Pipeline: pg_dump (custom format) -> GPG AES256 -> upload to S3-compatible storage
# (Cloudflare R2 / B2 / S3) -> prune to the last KEEP_LAST daily objects. Independent of
# Supabase's short built-in retention.
#
#   scripts/backup_db.sh            # full run: dump -> encrypt -> verify -> upload -> prune
#   scripts/backup_db.sh --dry-run  # dump -> encrypt -> verify locally; SKIP upload + prune
#
# Never prints the DB URL, the passphrase, or dump contents to logs.
#
# Environment (full run):
#   BACKUP_DATABASE_URL    plain postgresql:// on the Supabase session pooler :5432 or the
#                          direct connection. NOT the transaction pooler :6543 (pg_dump fails
#                          there) and NOT the +asyncpg driver URL (stripped automatically).
#   BACKUP_GPG_PASSPHRASE  symmetric passphrase used to encrypt/decrypt the dump.
#   S3_ENDPOINT            S3-compatible endpoint, e.g. https://<acct>.r2.cloudflarestorage.com
#   S3_BUCKET              bucket name.
#   S3_ACCESS_KEY_ID       S3 access key id.
#   S3_SECRET_ACCESS_KEY   S3 secret access key.
# Optional:
#   S3_PREFIX              key prefix inside the bucket (default: gasbot).
#   KEEP_LAST              number of daily objects to retain (default: 30).
#   PG_DUMP / PG_RESTORE   client binaries (default: pg_dump / pg_restore on PATH). The client
#                          major version MUST be >= the server major version; pin
#                          postgresql-client-17 in CI.
#   DRYRUN_DATABASE_URL    DB to dump in --dry-run when BACKUP_DATABASE_URL is unset
#                          (default: postgresql:///postgres via the local socket).
set -euo pipefail

S3_PREFIX="${S3_PREFIX:-gasbot}"
KEEP_LAST="${KEEP_LAST:-30}"
PG_DUMP="${PG_DUMP:-pg_dump}"
PG_RESTORE="${PG_RESTORE:-pg_restore}"

DRY_RUN=0
case "${1:-}" in
  --dry-run) DRY_RUN=1 ;;
  "") ;;
  -h | --help)
    sed -n '2,20p' "$0"
    exit 0
    ;;
  *)
    echo "usage: $0 [--dry-run]" >&2
    exit 2
    ;;
esac

# Timestamped logs to stderr. Callers must never pass secret values here.
log() { printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*" >&2; }
die() {
  log "ERROR: $*"
  exit 1
}

WORKDIR="$(mktemp -d)"
cleanup() {
  # Shred any plaintext dump before removing the scratch dir.
  find "$WORKDIR" -type f -name '*.dump' -exec shred -u {} + 2>/dev/null || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

require_env() {
  local name
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || die "missing required env: $name"
  done
}

# Resolve the connection string: strip the +asyncpg driver suffix and reject the
# transaction pooler port, which pg_dump cannot use.
resolve_db_url() {
  local url="$1"
  url="${url//+asyncpg/}"
  if [[ "$url" == *":6543"* ]]; then
    die "BACKUP_DATABASE_URL uses the transaction pooler :6543; use the session pooler :5432 or the direct connection"
  fi
  printf '%s' "$url"
}

main() {
  command -v gpg >/dev/null || die "gpg not found"
  command -v "$PG_DUMP" >/dev/null || die "$PG_DUMP not found"
  command -v "$PG_RESTORE" >/dev/null || die "$PG_RESTORE not found"

  local db_url passphrase
  if [[ "$DRY_RUN" -eq 1 ]]; then
    db_url="$(resolve_db_url "${BACKUP_DATABASE_URL:-${DRYRUN_DATABASE_URL:-postgresql:///postgres}}")"
    # A throwaway passphrase keeps --dry-run runnable without any real secret.
    passphrase="${BACKUP_GPG_PASSPHRASE:-dry-run-$$-$(date +%s)}"
  else
    require_env BACKUP_DATABASE_URL BACKUP_GPG_PASSPHRASE \
      S3_ENDPOINT S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY
    command -v aws >/dev/null || die "aws CLI not found"
    db_url="$(resolve_db_url "$BACKUP_DATABASE_URL")"
    passphrase="$BACKUP_GPG_PASSPHRASE"
  fi

  local stamp base dump enc
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  base="gasbot-${stamp}.dump"
  dump="$WORKDIR/$base"
  enc="$dump.gpg"

  log "dumping database (custom format) ..."
  # The URL is passed as a single argument; pg_dump does not echo it to logs.
  "$PG_DUMP" "$db_url" --format=custom --no-owner --no-privileges --file="$dump" \
    || die "pg_dump failed (check client>=server major version and that the URL is :5432/direct)"
  log "dump complete ($(du -h "$dump" | cut -f1))"

  log "encrypting with GPG AES256 ..."
  # Passphrase is read from fd 3, never placed in argv/ps or the log.
  gpg --batch --yes --quiet --symmetric --cipher-algo AES256 \
    --passphrase-fd 3 --output "$enc" "$dump" 3<<<"$passphrase" \
    || die "gpg encryption failed"
  shred -u "$dump" 2>/dev/null || rm -f "$dump"
  log "encrypted -> $base.gpg ($(du -h "$enc" | cut -f1))"

  log "verifying encrypted archive (gpg -d | pg_restore --list) ..."
  local dec entries
  dec="$WORKDIR/verify.dump"
  gpg --batch --yes --quiet --decrypt --passphrase-fd 3 "$enc" 3<<<"$passphrase" >"$dec" \
    || die "verification failed: could not decrypt the archive"
  "$PG_RESTORE" --list "$dec" >/dev/null \
    || die "verification failed: pg_restore could not read the archive"
  entries="$("$PG_RESTORE" --list "$dec" | grep -cv '^;' || true)"
  shred -u "$dec" 2>/dev/null || rm -f "$dec"
  log "verified: archive readable ($entries restorable entries)"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] OK: produced and verified $base.gpg; skipping upload and prune"
    return 0
  fi

  upload "$enc" "$base"
  prune
  log "backup complete"
}

upload() {
  local enc="$1" base="$2"
  log "uploading to s3://$S3_BUCKET/$S3_PREFIX/$base ..."
  # aws reads credentials from these env vars; they are never echoed.
  AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY" \
    aws s3 cp "$enc" "s3://$S3_BUCKET/$S3_PREFIX/$base" \
    --endpoint-url "$S3_ENDPOINT" --only-show-errors \
    || die "upload failed"
  log "upload complete"
}

# Keep the most recent KEEP_LAST objects under the prefix; delete older ones.
# Object keys embed a sortable UTC timestamp, so lexical sort == chronological.
prune() {
  log "pruning to the last $KEEP_LAST objects ..."
  local keys
  keys="$(
    AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY" \
      aws s3api list-objects-v2 \
      --bucket "$S3_BUCKET" --prefix "$S3_PREFIX/" \
      --endpoint-url "$S3_ENDPOINT" \
      --query 'sort_by(Contents,&Key)[].Key' --output text 2>/dev/null | tr '\t' '\n' | grep -E '\.dump\.gpg$' || true
  )"
  local total
  total="$(printf '%s\n' "$keys" | grep -c . || true)"
  if [[ "${total:-0}" -le "$KEEP_LAST" ]]; then
    log "prune: $total objects, nothing to delete"
    return 0
  fi
  local delete_count=$((total - KEEP_LAST))
  local key
  printf '%s\n' "$keys" | grep . | head -n "$delete_count" | while IFS= read -r key; do
    log "prune: deleting old object"
    AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY" \
      aws s3 rm "s3://$S3_BUCKET/$key" --endpoint-url "$S3_ENDPOINT" --only-show-errors \
      || log "prune: failed to delete an object (continuing)"
  done
  log "prune: removed $delete_count old object(s)"
}

main
