# ADR-0002: Postgres checkpointer alongside Redis, kept out of Alembic

## Status

Accepted

## Context

The LangGraph agent (ADR-0001) needs durable, cross-turn state: every
superstep of a graph run is checkpointed so a run can resume after a crash and
`interrupt()`/HITL can pause a run and resume it later, possibly in a different
process. LangGraph ships `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`)
for exactly this.

Qiki already has two persistence layers, each with an established owner:

- **Postgres via SQLAlchemy/Alembic** (`backend/app/db/session.py`,
  `backend/migrations/`) — the business schema: `products`, `orders`,
  `conversations`, `messages`, etc. Every table is a tracked, reviewed
  migration.
- **Redis** (`backend/app/db/redis.py`) — short-lived, non-durable state:
  auth blacklist, rate limiting, the query-embedding cache, and
  `AdminChatService`'s pending-confirmation tokens (300s TTL). Nothing in
  Redis is expected to survive a flush.

Neither is the right owner for checkpoint state as-is: it needs to be durable
(so Redis is wrong) and it is *not* app business data with a reviewed schema
(so mixing it into the Alembic-owned schema is wrong too). It also isn't
optional at read time — the checkpointer needs to be reachable every time the
agent runs, unlike Redis's cache tables that degrade gracefully when empty.

## Decision

1. **Same Supabase Postgres instance, separate connection mechanism, self-managed
   tables.** `AsyncPostgresSaver` creates and owns its own tables
   (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`)
   via its own `await checkpointer.setup()` call — **not** an Alembic migration.
   Alembic continues to own only the business schema; running `.setup()` is a
   one-time, idempotent step done at application startup (`backend/app/main.py`
   `lifespan`), gated behind `AGENT_ENABLED` so it never runs — and never opens
   the extra connection pool — when the flag is off.

   `LANGGRAPH_DB_URI` defaults to the app's `DATABASE_URL` with the
   `+asyncpg` SQLAlchemy dialect suffix stripped back to plain
   `postgresql://`, because the checkpointer connects via **`psycopg`
   (v3)**, a completely separate driver from the `asyncpg`/SQLAlchemy pool
   the rest of the app uses. This is a second, independent connection pool
   to the same database, not a shared one — `AsyncPostgresSaver` is
   constructed from a `psycopg_pool.AsyncConnectionPool`, built and opened in
   `lifespan` exactly like the existing `app.state.redis` client, and stored
   as `app.state.agent_checkpointer` for reuse across requests.

2. **Same Supavisor-pooler gotcha as asyncpg, addressed the psycopg way.**
   `db/session.py` already works around Supabase's Supavisor pooler not
   supporting server-side prepared statements in transaction-pooling mode
   (`connect_args={"statement_cache_size": 0}` for asyncpg — see the
   `railway-supabase-deploy` history). psycopg has the same failure mode and
   the same fix under a different name: the pool's connection `kwargs` set
   `prepare_threshold=None`, which disables server-side `PREPARE` entirely so
   pooled connections never get a statement id that outlives the physical
   connection they were prepared on. (For reference, LangGraph's own
   `AsyncPostgresSaver.from_conn_string()` convenience constructor — which we
   do *not* use, since it opens a single unpooled connection unsuitable for
   concurrent requests — sets `prepare_threshold=0` internally for the same
   reason, confirming this isn't a hypothetical risk.)

   The pool's connection `kwargs` also set `autocommit=True`. This one is not
   about the pooler: `checkpointer.setup()` issues `CREATE INDEX CONCURRENTLY`
   for its own tables, which Postgres refuses to run inside a transaction
   block, and psycopg opens connections in explicit-transaction mode
   (`autocommit=False`) by default. Confirmed by actually running `.setup()`
   against a local Postgres without this flag: it fails startup with
   `psycopg.errors.ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run
   inside a transaction block` — `from_conn_string()` sets the same flag,
   again for the same reason.

3. **`thread_id = session_id`.** The existing conversation `session_id`
   (already the identity a customer's browser/session carries across turns) is
   reused as the LangGraph `thread_id`, so one conversation's checkpoints are
   naturally scoped and resumable without inventing a second identifier.

4. **Redis is unchanged.** It keeps doing what it already does — cache,
   rate limiting, blacklist, `AdminChatService`'s short-lived pending tokens —
   none of which need to survive a process restart. The checkpointer does not
   replace Redis; it fills the durable-state gap Redis was never meant to
   cover.

5. **Keep state lean.** `AsyncPostgresSaver` writes a checkpoint on every
   superstep, so `QikiAgentState` (ADR-0001) stores references and short
   structured results — message history, IDs, tool call/result summaries — not
   large blobs. Retrieved-document content in particular should stay bounded
   (the same documents the existing RAG context builder already truncates to)
   rather than growing unbounded across a long-running thread.

## Consequences

**Easier:**
- Alembic's migration history stays exclusively business schema — no
  LangGraph-internal tables to explain in a future migration review, and no
  risk of Alembic and `AsyncPostgresSaver.setup()` racing to define the same
  table differently.
- The checkpointer can evolve independently: upgrading
  `langgraph-checkpoint-postgres` and re-running `.setup()` is a library
  concern, not a migration the team writes and reviews by hand.
- Because the flag defaults off, a deployment that never sets `AGENT_ENABLED`
  never opens the second connection pool and never calls `.setup()` — the
  existing `/chat` RAG path has zero marginal runtime cost from this decision.

**Harder / riskier:**
- A second, unaudited-by-Alembic set of tables now lives in the same
  database; `\dt` on the Supabase instance will show tables Alembic doesn't
  know about. This is deliberate (item 1) but worth flagging to anyone doing
  ad hoc schema review.
- Two connection pools to the same Postgres instance (SQLAlchemy/asyncpg for
  business data, psycopg for checkpoints) means two places that can each run
  out of connections under load, and two client libraries whose Supavisor
  workarounds must both be kept correct if the pooler's behavior changes.
- `.setup()` must run before the graph is used; if it's skipped (e.g. a
  deploy that sets `AGENT_ENABLED=true` without restarting through the
  `lifespan` startup path) the first graph run fails outright rather than
  degrading gracefully. This is why `.setup()` lives in `lifespan`, not lazily
  on first request.
