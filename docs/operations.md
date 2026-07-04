# Operations Runbook

This runbook covers day-two operations for GasBot after the owner deploys the
production stack.

## Ops Quick Commands (copy-paste)

Run from anywhere with the `gh` CLI authenticated. `--repo Rhynis/Gas-Rag-bot` is included so
these work from any directory. All three ops workflows also have a "Run workflow" button under
GitHub → Actions.

**IMPORTANT:** `gh workflow run` only *triggers* the workflow and returns immediately — it does
NOT tell you whether it succeeded. To see the result you must watch the run (below). Do not paste
lines starting with `#` into zsh (they error); they are comments here.

```bash
# ── Switch which backend prod points at, AND wait + report the result (recommended) ──
bash scripts/switch.sh render        # or: railway | oracle
#   → prints "✅ SWITCHED …" or "❌ FAILED …" and checks the live site

# ── Run the encrypted DB backup now, then watch it to completion ──
gh workflow run "DB Backup" --repo Rhynis/Gas-Rag-bot
gh run watch "$(gh run list --workflow 'DB Backup' -R Rhynis/Gas-Rag-bot -L1 --json databaseId -q '.[0].databaseId')" -R Rhynis/Gas-Rag-bot

# ── Health monitor / failover: probe-only (no switch) then a real run, watching each ──
gh workflow run "Monitor & Failover" --repo Rhynis/Gas-Rag-bot -f no_apply=true
gh run watch "$(gh run list --workflow 'Monitor & Failover' -R Rhynis/Gas-Rag-bot -L1 --json databaseId -q '.[0].databaseId')" -R Rhynis/Gas-Rag-bot

# ── Watch the latest run of a SPECIFIC workflow (change the name in quotes) ──
gh run watch "$(gh run list --workflow 'Switch Backend' -R Rhynis/Gas-Rag-bot -L1 --json databaseId -q '.[0].databaseId')" -R Rhynis/Gas-Rag-bot
```

Always pass `--workflow '<Name>'` when watching a run. Do NOT use a bare `gh run list -L1`
(no `--workflow`): "Monitor & Failover" runs every 5 minutes on a schedule, so the single latest
run across the repo is almost always that scheduled job, not the one you just triggered.

Run status: `in_progress` = running · `completed` + `success` = done ✓ · `completed` + `failure` = failed ✗.

Notes: the scheduled failover only *reacts to outages* and does **not** auto-fail-back to the
primary — use `Switch Backend -f target=render` (or `scripts/switch.sh render`) to move prod back
deliberately. Backend URLs come from the `RAILWAY_URL` / `RENDER_URL` / `ORACLE_URL` repo variables.

## View Logs

### Railway Backend

1. Open the Railway project and select the backend service.
2. Use the Deployments tab for deploy logs and the Logs tab for live runtime logs.
3. Filter by request ID when debugging API issues. Responses include `X-Request-ID`.
4. Check `/health` for basic liveness and `/health/detailed` for database, Redis, and LLM status.

### Vercel Frontend

1. Open the Vercel project and inspect the latest deployment.
2. Use Build Logs for failed builds and Function Logs for runtime SSR/proxy failures.
3. Confirm `NEXT_PUBLIC_API_URL` points to the Railway backend URL.

### Supabase Database

1. Use Supabase Dashboard > Logs > Postgres for query and connection errors.
2. Use Supabase Dashboard > Database > Replication/Backups for recovery state.
3. Use SQL editor for read-only investigation. Avoid manual writes during incidents unless approved.

## Debug Production Issues

- **Sentry:** backend errors are captured when `SENTRY_DSN` is set and `ENVIRONMENT=production`.
  Start with the exception stack, request path, release/deployment time, and request ID.
- **Health checks:** call `/health/detailed` from a trusted terminal. `database=error` points to
  Supabase credentials/networking; `redis=error` points to Railway Redis URL or service health.
- **Langfuse:** LLM traces are recorded when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are
  set. Use traces to inspect prompt, provider latency, and token usage.
- **Railway metrics:** inspect CPU/memory spikes before changing code. Embedding model cold starts
  can temporarily increase memory.
- **Database:** use `EXPLAIN ANALYZE` for slow SQL found in logs. Do not add indexes manually in
  production; create migrations.

## Scale Services

- **Railway backend:** increase CPU/memory first for model-loading or connection pressure. Add
  replicas only after confirming the app is stateless and Redis/database connection limits can
  support it.
- **Vercel frontend:** Vercel scales automatically for static and server-rendered routes. Check
  build output and edge/function logs before changing plan limits.
- **Supabase:** monitor CPU, RAM, disk, active connections, and slow queries. Upgrade the database
  plan before connection saturation affects checkout or chat.
- **Redis:** watch memory and eviction metrics. Increase capacity if rate-limit/session keys are
  evicted unexpectedly.

## Backup And Restore

### Supabase PITR

Use Supabase point-in-time recovery for production-impacting data loss when available on the
project plan. Record the target timestamp in UTC and announce expected downtime before restore.

### Manual Dump

```bash
pg_dump "$DATABASE_URL" --format=custom --file=gasbot-$(date +%Y%m%d-%H%M%S).dump
```

Store dumps in an encrypted location. Never commit dumps to the repository.

### Manual Restore

```bash
pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" gasbot-YYYYMMDD-HHMMSS.dump
```

Restore to staging first when possible. For production, pause writes, restore, run smoke tests, and
then re-enable traffic.

## Automated Encrypted Backups (CI)

`.github/workflows/backup-db.yml` runs `scripts/backup_db.sh` daily at `0 20 * * *` UTC
(03:00 Asia/Ho_Chi_Minh) and on manual `workflow_dispatch`. Each run:

1. `pg_dump --format=custom` of the production database,
2. GPG symmetric encryption (AES256) — the plaintext dump is shredded immediately,
3. upload of the `.dump.gpg` to S3-compatible storage (Cloudflare R2 recommended),
4. prune to the last `KEEP_LAST` (default 30) daily objects,

and, on failure, opens/updates a `[ops-backup]` GitHub issue. The dump contains PII, so it is
**always encrypted before upload**; an unencrypted dump is never uploaded or committed.

### Required GitHub secrets

| Secret | Purpose |
|--------|---------|
| `BACKUP_DATABASE_URL` | Plain `postgresql://` on the Supabase **session pooler `:5432`** or the direct connection. **Not** the transaction pooler `:6543` (pg_dump fails there) and **not** the `+asyncpg` URL (the script strips `+asyncpg` anyway). |
| `BACKUP_GPG_PASSPHRASE` | Symmetric passphrase for the dumps. **Store it safely — losing it means losing the backups.** |
| `S3_ENDPOINT` | S3-compatible endpoint, e.g. `https://<acct>.r2.cloudflarestorage.com`. |
| `S3_BUCKET` | Bucket name. |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Bucket credentials. |

Optional: `S3_PREFIX` (default `gasbot`), `KEEP_LAST` (default `30`).

### Restore from an encrypted dump

```bash
# 1. Download the object from the bucket (Cloudflare R2 example).
aws s3 cp "s3://$S3_BUCKET/gasbot/gasbot-<UTC-timestamp>.dump.gpg" . --endpoint-url "$S3_ENDPOINT"

# 2. Inspect the archive without restoring (validates the passphrase + archive).
gpg --batch --decrypt --passphrase "$BACKUP_GPG_PASSPHRASE" gasbot-<UTC-timestamp>.dump.gpg \
  | pg_restore --list | head

# 3. Restore. Prefer staging first; for prod, pause writes and smoke-test after.
gpg --batch --decrypt --passphrase "$BACKUP_GPG_PASSPHRASE" gasbot-<UTC-timestamp>.dump.gpg \
  > gasbot-restore.dump
pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" gasbot-restore.dump
```

Use a `pg_restore` whose major version is >= the server's. Restore is a **manual** procedure by
design — there is no auto-restore.

### Local dry run

```bash
# Uses a pinned pg_dump 17 client against a local database; creates and verifies a .dump.gpg,
# then skips upload/prune. Needs no real secret.
PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH" bash scripts/backup_db.sh --dry-run
```

## Backend Health Monitor & Auto-Failover (CI)

`.github/workflows/monitor-failover.yml` runs `scripts/health_failover.sh` every `*/5 * * * *`
and on manual dispatch. It probes each configured backend's `/health`, picks the highest-priority
healthy host, and reconciles Vercel's production `BACKEND_URL` to it by reusing
`scripts/switch-backend.sh`.

**Priority (highest first):** `RAILWAY_URL` → `RENDER_URL` → `ORACLE_URL` (unset hosts skipped).

### How it decides (conservative by design)

- Probes `GET {url}/health` with a short timeout, 2 attempts per host.
- `desired` = the first host in priority order returning **200**. It **never** switches to a host
  that is not currently 200.
- **All hosts down** → it does **not** switch (a dead host is no improvement); it opens/updates an
  `[ops-failover]` issue titled "ALL BACKENDS DOWN" and exits non-zero.
- **Idempotent:** if Vercel already points at `desired`, it is a no-op.
- **Anti-flap:** before flipping production it requires the desired host to be the same across
  **two probe rounds** (`CONFIRM_DELAY` seconds apart) so a single transient blip of the active
  host does not flip routing. Combined with the `*/5` cadence, a switch needs a sustained outage.
- On a switch it opens/updates the `[ops-failover]` issue with `old → new`.

Notifications use the workflow's built-in `GITHUB_TOKEN` via `gh` (no extra secrets, no email
coupling). A single open issue is reused (commented) to avoid duplicate spam.

### Required GitHub config

| Kind | Name | Purpose |
|------|------|---------|
| Secret | `VERCEL_TOKEN` | Read the current `BACKEND_URL` and redeploy. |
| Secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | Select the Vercel project non-interactively. |
| Variable | `RAILWAY_URL`, `RENDER_URL`, `ORACLE_URL` | The priority list (omit a host to skip it). |
| Variable | `FAILOVER_DISABLED` | Set to `true` to make every run probe-only (no switching). |

### Force or disable failover

- **Disable auto-switching:** set repo variable `FAILOVER_DISABLED=true` (runs still probe and
  report), or disable the workflow in the Actions tab.
- **Probe-only, manually:** run the workflow via *Run workflow* with `no_apply=true`, or locally
  `bash scripts/health_failover.sh --no-apply`.
- **Force a specific host:** set `FAILOVER_DISABLED=true`, then pin it manually with
  `./scripts/switch-backend.sh railway|render|oracle` (or `--url <URL> "<label>"`).

### Caveats / sturdier alternatives

GitHub's `*/5` cron is a **floor**: runs are frequently delayed and occasionally skipped, so this
is best-effort free-tier failover, not an SLA. For real monitoring/failover use **UptimeRobot**
(free health checks + alerts) or a **Cloudflare Load Balancer** (managed origin health checks and
automatic failover at the edge).

## Incident Response

1. **Triage:** identify affected surface: frontend, backend, database, Redis, LLM provider, or
   observability.
2. **Stabilize:** if deploy-related, rollback frontend via Vercel deployment history or backend via
   Railway previous deployment.
3. **Communicate:** record start time, impact, suspected cause, and owner actions.
4. **Database changes:** downgrade migrations only when the downgrade path is known safe and data
   loss has been assessed. Prefer forward-fix migrations for non-critical issues.
5. **Verify:** run `/health`, checkout smoke test, chat smoke test, and admin login after recovery.
6. **Follow up:** write a short post-incident note with root cause, detection gap, and prevention.
