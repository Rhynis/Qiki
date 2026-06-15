# Hosting — multi-host backend with one-command switch

The backend runs on **three interchangeable hosts** so the shop never depends on one provider:

| Host | Cost | Notes |
|------|------|-------|
| **Railway** | $5/mo (or trial) | Current primary. Auto-deploys from `main`. |
| **Render (free)** | $0 | Sleeps after ~15 min idle → ~30–60 s cold start. Keep warm with an uptime pinger. Auto-deploys from `main`. |
| **Oracle Cloud (Always Free)** | $0 forever | Always-on VM, no cold start. Needs an international card at signup + VPS setup. Manual deploy via `deploy/oracle/deploy.sh`. |

All three run the **same Docker image** and share **one Upstash Redis + one Supabase Postgres**.
The Vercel frontend proxies `/api/*` to whichever host `BACKEND_URL` points at.

## Shared infrastructure (set up once)

- **Postgres** — Supabase (already used). `DATABASE_URL` (pooler URL, asyncpg).
- **Redis** — [Upstash](https://upstash.com) free tier. Create a Redis DB, copy the
  `rediss://...` (TLS) URL into `REDIS_URL`. `redis==5.0.1` supports `rediss://` natively — no
  code change. Moving Redis off Railway also lightens Railway usage.

## Environment parity (critical)

Every host must use the **same** values for these, or switching breaks sessions:

| Var | Why |
|-----|-----|
| **`JWT_SECRET_KEY`** | HS256-signs auth tokens. Different value on another host → all tokens rejected → everyone logged out on switch. **Must be identical.** |
| `DATABASE_URL` | Same Supabase DB. |
| `REDIS_URL` | Same Upstash Redis (sessions, blacklist, password-reset tokens). |
| `ENVIRONMENT=production` | Secure cookies. |
| `FRONTEND_URL`, `CORS_ORIGINS` | The Vercel origin. |
| `GEMINI_*`, `GROQ_API_KEY`, `JINA_API_KEY` | Chat/RAG. |
| `EMAIL_PROVIDER`, `SMTP_*`, `EMAIL_FROM` | Password-reset email. |

Easiest: copy the full env from Railway and paste it into each new host.

## Per-host setup

### Render (`render.yaml`)
1. Render → **New → Blueprint** → connect the repo → it reads `render.yaml`.
2. Set every `sync: false` var in the dashboard (paste from Railway). Region: Singapore.
3. Deploy → note the `https://<name>.onrender.com` URL → put it in
   `scripts/switch-backend.sh` (`RENDER_URL`).
4. Cold start: add a free uptime monitor (UptimeRobot / cron-job.org) hitting
   `https://<name>.onrender.com/health` every ~10 min to keep it warm.

### Oracle Cloud (`deploy/oracle/`)
1. Create an Always-Free VM (Ubuntu). Install Docker + the compose plugin, nginx, certbot.
2. Clone the repo. Copy `deploy/oracle/.env.example` → `deploy/oracle/.env` and fill it
   (same values as the other hosts). **Never commit `.env`.**
3. Run `bash deploy/oracle/deploy.sh` (builds + starts the backend on `127.0.0.1:8000`).
4. Configure nginx from `deploy/oracle/nginx.conf` (set your hostname), then
   `sudo certbot --nginx -d api.YOUR-DOMAIN` for TLS.
5. Put the `https://api.YOUR-DOMAIN` URL in `scripts/switch-backend.sh` (`ORACLE_URL`).
6. Re-deploy latest `main` anytime: re-run `deploy/oracle/deploy.sh`.

### Railway
Already set up. Just point `REDIS_URL` at Upstash (so it shares state with the others) and
ensure `JWT_SECRET_KEY` matches.

## Switching hosts (one command)

```bash
./scripts/switch-backend.sh railway   # or render | oracle
```

Sets the Vercel `BACKEND_URL` prod env and redeploys (~2 min — Vercel needs a redeploy for env
changes to take effect). One-time: `npm i -g vercel && vercel login && (cd frontend && vercel link)`.
