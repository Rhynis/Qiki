# Gasbot — Lịch sử Collaboration Claude + Codex

> **Repo:** https://github.com/Rhynis/Gas-Rag-bot
> **Working dir:** `/Users/rhynis/Projects/Gasbot`
> **Stack:** FastAPI backend + Next.js 16 frontend
> **Workflow:** Claude (planner/reviewer) + Codex (implementer) + Rhynis (owner)
> **Updated:** 2026-06-12 — backfill toàn bộ Phase 4.1–4.3 + ~70 fix post-launch (tới PR #175). Trước: 2026-05-29 (Phase 3.4).

---

## Tổng quan Phase Status

| Phase | Issue | PR | Status |
|---|---|---|---|
| 1.x (Scaffold) | — | — | ✅ Done |
| Chore: shadcn + config | — | #2 | ✅ Merged |
| 2.1 Authentication | #1 | #3 | ✅ Merged |
| 2.2 Product Catalog | #4 | #5 | ✅ Merged |
| Chore: CI infra fix | — | #7 | ✅ Merged — CI xanh lần đầu |
| 2.3 Cart & Checkout | #8 | #9 | ✅ Merged |
| 2.4 Admin Dashboard | #10 | #11 | ✅ Merged |
| 3.1 LLM Provider Abstraction | #12 | #13 | ✅ Merged |
| 3.2 Vietnamese Embeddings & KB | #14 | #15 | ✅ Merged |
| 3.3 RAG Pipeline with Safety | #16 | #17 | ✅ Merged |
| 3.4 Intent Classification & Conversation | #18 | #19 | ✅ Merged |
| 4.1 Continuous Learning | #20 | #21 | ✅ Merged |
| 4.2 Evaluation Framework | #22 | #23 | ✅ Merged |
| 4.3 Production Deployment (code prep) | #24 | #25 | ✅ Merged |
| **Post-launch (prod live)** | — | #26–#175 | 🟢 **Live & iterating** |

> Từ #26 trở đi không còn theo phase — là chuỗi fix/feature production sau khi go-live. Chi tiết: section **"Post-launch — Production Iteration"** bên dưới.

---

## Workflow Setup

### Roles

| Role | Who | Responsibility |
|---|---|---|
| Planner / Reviewer | Claude | Đọc `gasbot_build_plan.md`, viết issues, review PRs |
| Implementer | Codex | Đọc WORKFLOW.md + issue, tạo branch, mở PR |
| Owner | Rhynis | Relay sang Codex, approve, merge PRs |

### Nguyên tắc cốt lõi
- **One phase, one branch, one PR** — không trộn phases
- **Issue = source of truth cho scope/criteria** — build plan = code details
- Khi conflict giữa issue và build plan → **theo issue**
- **Branch protection cho phép owner merge với `--admin`** khi mình là người duy nhất approve

### Prompt template gửi Codex

```
Repo: https://github.com/Rhynis/Gas-Rag-bot
Working directory: /Users/rhynis/Projects/Gasbot

Đọc theo thứ tự:
1. /Users/rhynis/Projects/Gasbot/WORKFLOW.md
2. GitHub issue #N: https://github.com/Rhynis/Gas-Rag-bot/issues/N
3. /Users/rhynis/Projects/Gasbot/gasbot_build_plan.md, section "Phase X.Y" (lines A–B)

Quy tắc: Issue là source of truth cho scope/criteria. Build plan cho code details.
Khi conflict, theo issue.

Tạo branch `phase-X.Y-<slug>` từ main, implement, chạy hết acceptance commands,
mở PR với title "[Phase X.Y] <Title>", body có `Closes #N` + verbatim terminal output.

QUAN TRỌNG — trước khi push, chạy ĐỦ 4 lệnh:
1. cd backend && ruff format --check . && ruff check .
2. cd frontend && npm run format:check && npm run lint
3. cd backend && mypy app/
4. cd backend && pip-audit --strict
```

### PR Review Process (Claude)
```bash
gh pr view {N} --repo Rhynis/Gas-Rag-bot           # metadata + body
gh pr diff {N} --repo Rhynis/Gas-Rag-bot --name-only  # list files
gh pr diff {N} --repo Rhynis/Gas-Rag-bot           # full diff
gh pr checks {N} --repo Rhynis/Gas-Rag-bot         # CI status
gh run view <run-id> --repo Rhynis/Gas-Rag-bot --log-failed | tail -150  # log CI fail
gh pr comment {N} --repo Rhynis/Gas-Rag-bot --body "..."   # post review
gh pr merge {N} --squash --admin --repo Rhynis/Gas-Rag-bot  # merge
```
⚠️ **KHÔNG dùng** `gh pr review N --request-changes` — GitHub block self-review trên PR cùng account.

---

## Lưu ý kỹ thuật quan trọng (tích lũy qua các phases)

### 1. mypy type-arg trên endpoint files mới (recurring)
Mọi file `app/api/v1/endpoints/*.py` mới phải được thêm vào `[[tool.mypy.overrides]]` trong `backend/pyproject.toml` với `disable_error_code = ["type-arg"]`.

**Lý do:** FastAPI's `Request` type thiếu type parameter ở mọi endpoint, và CI chạy `mypy --strict`.

**Danh sách hiện tại (sau Phase 3.4):**
```toml
[[tool.mypy.overrides]]
module = [
  "app.main",
  "app.core.security_middleware",
  "app.db.redis",
  "app.api.v1.endpoints.auth",
  "app.api.v1.endpoints.products",
  "app.api.v1.endpoints.orders",
  "app.api.v1.endpoints.admin_users",
  "app.api.v1.endpoints.admin_dashboard",
  "app.api.v1.endpoints.knowledge_base",
  "app.api.v1.endpoints.rag",
  "app.api.v1.endpoints.conversations",
]
disable_error_code = ["type-arg"]
```

### 2. Format check — Codex không tự chạy (recurring)
Ruff/prettier/ESLint luôn fail trong CI vì Codex không chạy format check local trước khi push. **Bắt buộc** embed các lệnh này vào acceptance criteria của mọi issue:
```bash
cd backend && ruff format --check . && ruff check .
cd frontend && npm run format:check && npm run lint
```
Fix khi fail: `ruff format .` (backend), `npx prettier --write "**/*.{ts,tsx}"` (frontend).

### 3. Tenacity + mypy strict
`@retry` decorator từ tenacity cần `# type: ignore[arg-type]` trên decorator và `# type: ignore[misc, no-any-return]` tại call site khi dùng mypy strict.

### 4. asyncpg migration constraint
asyncpg không cho multi-statement trong một `op.execute()`. Mỗi `CREATE TABLE / CREATE INDEX / COMMENT / CREATE TRIGGER` = một `op.execute()` riêng.

### 5. ESLint setState-in-effect (Phase 3.2)
Không thể gọi `void fetchFn()` trực tiếp trong `useEffect` nếu `fetchFn` set state. Pattern đúng:
```tsx
const [refreshKey, setRefreshKey] = useState(0)
useEffect(() => {
  let cancelled = false
  async function load() {
    // ... fetch + setState
    if (!cancelled) setData(...)
  }
  void load()
  return () => { cancelled = true }
}, [dep1, dep2, refreshKey])

// Trigger re-fetch:
setRefreshKey((k) => k + 1)
```

### 6. pip-audit sau khi thêm dependency
Luôn chạy `pip-audit --strict` sau khi thêm dependency mới. Ví dụ: `jinja2==3.1.3` có 4 CVE → bump lên `3.1.6`.

### 7. `filters: list[ColumnElement[bool]] = []`
Khi build dynamic filter list trong SQLAlchemy, type phải khai báo tường minh là `list[ColumnElement[bool]]` để mypy không infer thành `list[BinaryExpression[bool]]` (gây lỗi khi có `is_()` hoặc `ilike()`).

### 8. httpOnly Cookie architecture
- Access token: `gasbot_access_token` — httpOnly, samesite=lax, path=/
- Refresh token: `gasbot_refresh_token` — httpOnly, samesite=lax, path=/api/v1/auth
- `LoginResponse` body chỉ có `{token_type, user}` — KHÔNG có raw token
- Frontend axios: `withCredentials: true`, KHÔNG đọc cookie từ JS
- `get_current_user`: cookie → Bearer fallback (cho curl/test)

### 9. Stock concurrency
- `decrement_stock`, `increment_stock`, `get_many_for_update` đều dùng `.with_for_update()`
- Order create: SERIALIZABLE isolation + SELECT FOR UPDATE
- Test bắt buộc: `test_concurrent_decrement_no_oversell` (10 tasks song song, real Postgres)

### 10. Safety checker — KHÔNG THƯƠNG LƯỢNG
- Emergency response phải là hằng số `SAFETY_EMERGENCY_RESPONSE_VI` — không gọi LLM
- Phải có số hotline `1900-1234`
- `test_safety_query_does_not_call_llm` phải verify `llm.generate.assert_not_called()`
- Evaluation script exit non-zero nếu safety_detection_rate < 100%

---

## CI Status (tổng hợp sau Phase 3.4)

| Workflow | Trạng thái | Ghi chú |
|---|---|---|
| Backend CI (test) | ✅ Green | Chạy: ruff, mypy, alembic upgrade head, pytest --cov, pip-audit |
| Frontend CI (test) | ✅ Green | Chạy: type-check, lint, format:check, vitest --coverage, build |
| Deploy Backend | ❌ Fail (expected) | Railway secrets chưa cấu hình |
| Deploy Frontend | ❌ Fail (expected) | Vercel secrets chưa cấu hình |

Deploy fail là intentional — commit `af4d837` disable deploy trigger cho đến khi Railway/Vercel sẵn sàng.

---

## Phase 1.x — Audit (2026-05-29)

### CI
Phase 1.x được commit thẳng vào main (không qua PR), nên không có CI run riêng cho Phase 1.x. Tuy nhiên mọi CI từ Phase 2.1 trở đi đều include toàn bộ code Phase 1.x và pass.

### Tests hiện có
**Backend:**
- `tests/core/test_input_validation.py` — 25 tests: phone validator, tax code, prompt injection (`is_safe`), PII masker ✅
- `tests/core/test_security.py` — 8 tests: JWT create/decode, bcrypt hash, verify_password, refresh token JTI ✅
- `tests/api/test_health.py` — 1 test: `/health` endpoint ✅
- `alembic upgrade head` trong CI verify toàn bộ migrations ✅

**Frontend:**
- `tests/auth/validation.test.ts` — 4 tests: Zod schemas, Vietnamese error messages ✅
- `tests/utils/format.test.ts` — 6 tests: VND price, date, phone mask ✅
- `tests/auth/store.test.ts` — 2 tests: verify no raw token in localStorage ✅
- `tests/auth/api-client.test.ts` — 1 test: verify `withCredentials: true` ✅

### Gaps nhỏ (low risk)
- `PromptInjectionDetector.sanitize()` chưa có test (chỉ `is_safe()` được test)
- `app/core/security_middleware.py` không có dedicated test
- DB stored procedures (`generate_order_number`, `match_documents`, v.v.) không có unit test riêng — tested ngầm qua integration tests

---

## Phase 1.1 — Repository Initialization

**Commit:** `09d67e6` (commit thẳng vào main, không qua PR)
**Status:** ✅ Done

### Mục tiêu
Monorepo scaffold với đầy đủ công cụ dev.

### Files tạo
- `docker-compose.yml` — PostgreSQL (`pgvector/pgvector:pg16`) + Redis (`redis:7-alpine`) với health checks
- `Makefile` — `help`, `setup`, `dev`, `test`, `lint`, `format`, `clean`, `migrate`, `seed`, `docker-up`, `docker-down`
- `scripts/setup.sh` — one-command setup, check node≥20 + python≥3.11, copy .env.example
- `scripts/test-all.sh` — run both frontend + backend test suites
- `.env.example` — tất cả env vars documented (Database, Redis, LLM, JWT, CORS, Rate limits, Supabase, Sentry, Langfuse)
- `LICENSE` — MIT
- `.editorconfig` — indent_style=space, 4 (Python) / 2 (TS/JSON), LF line endings
- `docs/` skeleton — architecture.md, api.md, deployment.md, security.md, development.md (headers only)

### Không có unit tests (đúng — infrastructure only)

---

## Phase 1.2 — Backend Foundation with Security

**Commit:** `09d67e6` | **Status:** ✅ Done

### Mục tiêu
FastAPI app với security-first architecture, async SQLAlchemy, structured logging, input validation.

### Files tạo

**Core:**
- `backend/requirements.txt` — FastAPI, uvicorn, pydantic v2, SQLAlchemy async, asyncpg, alembic, PyJWT, passlib[bcrypt], structlog, slowapi, redis, tenacity, sentry-sdk, email-validator, pgvector
- `backend/requirements-dev.txt` — pytest, pytest-asyncio, pytest-cov, pytest-mock, httpx, faker, fakeredis, ruff, mypy, pip-audit
- `backend/pyproject.toml` — ruff (line-length=100, select E/F/W/I/N/B/A/C4/UP/RUF/S/BLE/ASYNC), mypy strict, pytest asyncio_mode=auto, coverage

**app/core/:**
- `config.py` — `Settings(BaseSettings)` với `@lru_cache`, field ENVIRONMENT/DATABASE_URL/JWT_SECRET_KEY/REDIS_URL/LLM_PROVIDER/... `@computed_field`: `is_production`, `is_development`, `cors_origins_list`
- `exceptions.py` — `GasBotException` base → `NotFoundException(404)`, `ValidationException(400)`, `UnauthorizedException(401)`, `ForbiddenException(403)`, `ConflictException(409)`, `RateLimitException(429)`, `LLMException(503)`, `InsufficientStockException`, `IdempotencyException`
- `security.py` — `get_password_hash`, `verify_password` (bcrypt), `create_access_token` (type="access"), `create_refresh_token` (type="refresh", có jti), `decode_token` → raise `UnauthorizedException` nếu expired/invalid
- `security_middleware.py` — `SecurityHeadersMiddleware` (X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, HSTS production only, CSP, Permissions-Policy, xóa Server header), `RequestIdMiddleware` (X-Request-ID), `AuditLogMiddleware` (log admin + POST/PATCH/DELETE)
- `input_validation.py` — `VietnamesePhoneValidator` (+84/0, normalize), `VietnameseTaxCodeValidator` (10 digits hoặc 10-3), `PromptInjectionDetector` (SUSPICIOUS_PATTERNS list, `is_safe()` + `sanitize()`), `PIIMasker` (mask_phone, mask_email, mask_dict với SENSITIVE_KEYS set)
- `logging.py` — structlog với `_pii_masking_processor`, dev: ConsoleRenderer(colors), prod: JSONRenderer

**app/db/:**
- `base.py` — `Base(DeclarativeBase)`, `UUIDMixin` (UUID pk + uuid_generate_v4), `TimestampMixin` (created_at, updated_at với server_default + onupdate)
- `session.py` — `create_async_engine` (pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600), `AsyncSessionLocal`, `get_db()` dependency (yield + auto-commit/rollback/close), `check_db_health()`

**app/main.py** — lifespan (configure_logging + Sentry), middleware order (RequestId → AuditLog → SecurityHeaders → CORS), exception handlers cho tất cả `GasBotException`, `GET /health` (200 OK), `GET /health/detailed` (DB + Redis status), docs=None in production

**backend/Dockerfile** — multi-stage (builder: pip install --user, runner: non-root `gasbot` user, HEALTHCHECK curl /health)

**Tests:**
- `tests/conftest.py` — event_loop, test_db_engine, db_session (rollback sau mỗi test), test_app, test_client (httpx), mock_redis (fakeredis)
- `tests/core/test_security.py` — 8 tests (hash, verify, JWT create/decode/expire/invalid, refresh jti)
- `tests/core/test_input_validation.py` — 25 tests (phone, tax code, prompt injection, PII masker)
- `tests/api/test_health.py` — 1 test (`/health` → 200 OK)

### Security middleware stack
```
Request → RequestIdMiddleware → AuditLogMiddleware → SecurityHeadersMiddleware → CORS → Route
```
Headers được add: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, CSP. HSTS chỉ trong production.

---

## Phase 1.3 — Frontend Foundation

**Commit:** `09d67e6` | **Status:** ✅ Done (shadcn theme đổi từ orange → zinc trong PR #2)

### Mục tiêu
Next.js 14 App Router, TypeScript strict, Tailwind, shadcn/ui, Axios với auth interceptors, Vitest.

### Files tạo

**Config:**
- `tsconfig.json` — strict=true, noUncheckedIndexedAccess, noImplicitAny, noImplicitReturns, noUnusedLocals, noUnusedParameters
- `next.config.mjs` — reactStrictMode, poweredByHeader=false, output='standalone', security headers
- `.prettierrc` — semi=false, singleQuote=true, trailingComma=es5, printWidth=100, prettier-plugin-tailwindcss
- `.eslintrc.json` — next/core-web-vitals + prettier
- `vitest.config.ts` — jsdom, coverage provider v8, alias @/* → ./

**lib/:**
- `lib/supabase/client.ts` — `createBrowserClient<Database>()` (dùng trong Client Components)
- `lib/supabase/server.ts` — `createServerClient()` với Next.js `cookies()` API (Server Components)
- `lib/api/client.ts` — `ApiError(status, code, detail)`, axios instance (`baseURL=NEXT_PUBLIC_API_URL`, timeout=30s), request interceptor (inject Bearer từ Supabase session, thêm `Idempotency-Key` UUID cho POST/PATCH/PUT), response interceptor (normalize → ApiError)
  > ⚠️ **Lưu ý Phase 2.1:** client.ts được refactor trong Phase 2.1 sang httpOnly cookie architecture — không còn inject token từ Supabase session, thay bằng `withCredentials: true`
- `lib/constants/index.ts` — APP_NAME, ROUTES, PAGINATION, INTENT_CATEGORIES, ORDER_STATUS, ORDER_STATUS_LABELS_VI, PAYMENT_METHOD_LABELS_VI
- `lib/utils/format.ts` — `formatPrice` (Intl VND), `formatNumber` (vi-VN), `formatDate` (DD/MM/YYYY HH:mm), `formatPhone`, `formatPhoneMasked`

**app/:**
- `app/layout.tsx` — `lang="vi"`, Inter font + Vietnamese subset, Providers, Toaster
- `app/page.tsx` — landing: hero "Mua gas LPG dễ dàng với AI hỗ trợ", CTA → /products, 3 feature cards
- `components/providers.tsx` — QueryClientProvider (staleTime 5min), React Query DevTools dev only

**middleware.ts** — cookie-based route protection. Public: `/`, `/products`, `/track`, `/login`, `/register`. Protected: `/orders`, `/account`. Admin: `/admin` (check user_metadata.role). Redirect unauthorized → `/login?redirectTo=...`

**Tests:**
- `tests/setup.ts` — @testing-library/jest-dom/vitest, cleanup afterEach
- `tests/utils/format.test.ts` — 6 tests (price, number, date, phone, phone masked)
- `tests/auth/validation.test.ts` — 4 tests (register schema, weak password, mismatched confirm, login required)
- `tests/auth/store.test.ts` — 2 tests (setUser/setSession stores no raw token, clearAuth)
- `tests/auth/api-client.test.ts` — 1 test (withCredentials=true, no Authorization header)

### Lưu ý quan trọng
- shadcn ban đầu init với baseColor=**orange** nhưng PR #2 đổi sang **zinc**. Mọi file mới từ Phase 2.x trở đi phải dùng zinc CSS variables.
- `next.config.mjs` set security headers ở layer Next.js (bổ sung cho backend SecurityHeadersMiddleware)

---

## Phase 1.4 — Database Schema Migration (7 Tables)

**Commit:** `09d67e6` | **Migration:** `001_initial_schema.py` | **Status:** ✅ Done (fix split statements trong PR #7)

### Mục tiêu
Alembic migration tạo toàn bộ schema: 7 tables, 4 functions, 6 triggers, RLS policies, pg extensions.

### Extensions
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"
CREATE EXTENSION IF NOT EXISTS vector         -- pgvector 768 dims
CREATE EXTENSION IF NOT EXISTS pg_trgm        -- fuzzy Vietnamese text search
```

### 7 Tables

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, email, full_name, phone, role, is_active | role ∈ {customer, staff, admin} |
| `products` | id, sku, name, brand, size_kg, price, stock_quantity, safety_info | pg_trgm index trên name |
| `orders` | id, order_number, user_id (nullable), customer_*, delivery_*, subtotal, shipping_fee, total_amount, vat_info JSONB, payment_method, status, source, idempotency_key | Guest checkout: user_id=NULL |
| `order_items` | order_id, product_id (nullable), product_name/brand/size_kg (snapshot), quantity, unit_price, subtotal, is_exchange | Snapshot fields preserve history |
| `conversations` | id, user_id (nullable), session_id, status, assigned_to, escalated_at, satisfaction_rating | status ∈ {active, escalated, resolved, abandoned} |
| `messages` | id, conversation_id, role, content, intent, intent_confidence, llm_provider, llm_model, tokens_used, latency_ms, retrieved_documents JSONB, feedback_score, flagged_for_review, reviewed_by, review_action, corrected_content | role ∈ {user, assistant, staff, system} |
| `knowledge_base` | id, title, content, category, source, embedding VECTOR(768), metadata JSONB, is_active, source_message_id | category ∈ {safety, product_info, delivery, pricing, company, faq, technical} |

### 4 DB Functions

| Function | Mục đích |
|---|---|
| `generate_order_number()` | Format GB-YYYYMMDD-XXXX, auto-increment per day |
| `match_documents(embedding, threshold, count, category)` | Vector cosine similarity search từ knowledge_base |
| `get_customer_orders(phone, limit)` | Lấy orders theo phone (guest hoặc registered) |
| `calculate_order_total(order_id)` | SUM(order_items.subtotal) + shipping_fee |

### 6 Triggers

| Trigger | On | Action |
|---|---|---|
| `trigger_set_order_number` | BEFORE INSERT orders | Gán order_number nếu NULL |
| `trigger_users_updated_at` | BEFORE UPDATE users | NEW.updated_at = NOW() |
| `trigger_products_updated_at` | BEFORE UPDATE products | NEW.updated_at = NOW() |
| `trigger_orders_updated_at` | BEFORE UPDATE orders | NEW.updated_at = NOW() |
| `trigger_conversations_updated_at` | BEFORE UPDATE conversations | NEW.updated_at = NOW() |
| `trigger_knowledge_base_updated_at` | BEFORE UPDATE knowledge_base | NEW.updated_at = NOW() |

### RLS Policies
- `products_public_active_select` — SELECT WHERE is_active = TRUE
- `knowledge_base_public_active_select` — SELECT WHERE is_active = TRUE
- `orders_guest_insert` — INSERT WITH CHECK (TRUE) — cho phép guest tạo order
- `conversations_guest_insert` — INSERT WITH CHECK (TRUE)
- `messages_insert` — INSERT WITH CHECK (TRUE)

### FK quan trọng
- `orders.referral_conversation_id → conversations.id` (thêm sau khi tạo 2 bảng riêng lẻ)
- `knowledge_base.source_message_id → messages.id` (đóng feedback loop: approved message → KB entry)

### asyncpg constraint (fix trong PR #7)
Ban đầu migration dùng `op.execute()` với multi-statement SQL → asyncpg raise `cannot insert multiple commands into a prepared statement`. Fix: split 14 calls → **115 calls riêng lẻ**.

---

## Phase 1.5 — Deployment Pipeline

**Commit:** `09d67e6` + fixes `af4d837`, `48db99b` | **Status:** ✅ Done (deploy secrets chưa cấu hình)

### CI Workflows

**`ci-backend.yml`** (trigger: push/PR trên `backend/**`):
```
pip install → ruff check → ruff format --check → mypy app/ → alembic upgrade head → pytest --cov --cov-fail-under=70 → pip-audit --strict
```
Services: pgvector/pgvector:pg16 + redis:7-alpine

**`ci-frontend.yml`** (trigger: push/PR trên `frontend/**`):
```
npm ci → type-check → lint → format:check → test:coverage → build
```

### Deploy Workflows
- `deploy-backend.yml` → Railway (`railway up --service backend`)
- `deploy-frontend.yml` → Vercel (`vercel-action@v25 --prod`)

**Secrets cần cấu hình** (chưa có, deploy đang fail expected):

| Secret | Lấy từ |
|---|---|
| `VERCEL_TOKEN` | Vercel dashboard → Account Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel project settings |
| `VERCEL_PROJECT_ID` | Vercel project settings |
| `RAILWAY_TOKEN` | Railway → Account Settings → Tokens |

### Config files
- `frontend/vercel.json` — framework=nextjs, regions=["sin1"], env vars mapping
- `backend/railway.json` — Dockerfile build, startCommand: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`, healthcheckPath=/health

### CI Status hiện tại
- Backend CI: ✅ Green (pass liên tục từ Phase 2.1+)
- Frontend CI: ✅ Green
- Deploy Backend: ❌ Fail (expected — RAILWAY_TOKEN chưa có)
- Deploy Frontend: ❌ Fail (expected — VERCEL_TOKEN chưa có)

---

## Phase 2.1 — Authentication System

**Issue:** #1 | **PR:** #3 | **Branch:** `phase-2.1-authentication`
**Status:** ✅ Merged (squash commit `337ae82`)

### Backend files
- `app/models/user.py` — SQLAlchemy User model (UUIDMixin, TimestampMixin, role, is_active, `is_admin()` method)
- `app/schemas/user.py` — UserBase/Create/Update/Response, LoginRequest/Response, TokenRefresh, PasswordChange/Reset
- `app/repositories/user_repository.py` — CRUD + list_users với fixed count query
- `app/services/auth_service.py` — register, login, refresh, logout, verify_token, change_password, password reset
- `app/api/v1/dependencies/auth.py` — get_current_user (cookie-first + Bearer fallback), active/admin/staff/optional
- `app/api/v1/endpoints/auth.py` — 8 endpoints với SlowAPI rate limits

### Test results
- Backend: **65 tests passed**, coverage auth_service **81%**
- Frontend: **13 tests passed**

---

## Phase 2.2 — Product Catalog

**Issue:** #4 | **PR:** #5 | **Branch:** `phase-2.2-product-catalog`
**Status:** ✅ Merged (squash commit `fc2238f`)

### Key technical decisions
- `size_kg ∈ {Decimal("6"), Decimal("12"), Decimal("45")}` — KHÔNG float `6.0`
- SKU: `^[A-Z0-9-]+$`, normalize `.upper().strip()`
- Router include products **không có prefix** — paths literal trong endpoint decorators
- `decrement_stock` / `increment_stock` / `get_many_for_update` đều `.with_for_update()`
- `test_concurrent_decrement_no_oversell`: 10 tasks song song, stock=5, assert 5 success + 5 fail + final=0

### Test results
- Backend: **107 tests passed**, product_service 100%, product_repository 98%
- Frontend: **16 tests passed**

---

## Chore: CI Infra Fix — PR #7

**Branch:** `chore/fix-ci-infra` | **Status:** ✅ Merged (`a4c1a2f`)

**Fixes:**
- `001_initial_schema.py`: split 14 multi-statement `op.execute()` → 115 calls riêng lẻ (asyncpg constraint)
- Frontend: `npm i -D @vitest/coverage-v8@^4.1.7`
- `conftest.py`: `os.environ["DATABASE_URL"]` → `os.environ.setdefault(...)` (không ghi đè CI credentials)

CI trên main **xanh lần đầu** kể từ commit đầu.

---

## Phase 2.3 — Cart & Checkout

**Issue:** #8 | **PR:** #9 | **Branch:** `phase-2.3-cart-checkout`
**Status:** ✅ Merged

### Key technical decisions
- Order create: `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` → `get_many_for_update` → validate stock → decrement → create order
- Idempotency: UUID v4 `Idempotency-Key` header, same key trả về same order
- `@retry(retry=retry_if_exception(is_serialization_failure), stop=stop_after_attempt(3))` trên endpoint
  - `# type: ignore[arg-type]` trên decorator, `# type: ignore[misc, no-any-return]` tại call site
- Migration 002: `ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255)` (ORM có nhưng migration 001 thiếu)

### CI fixes trong review
- mypy type-arg: `orders.py` → thêm vào pyproject.toml overrides
- Migration 002 tạo mới để add `hashed_password` column
- `test_order_from_chatbot_records_source_and_conversation`: bỏ `referral_conversation_id=uuid4()` (FK constraint)

### Test results
- **134 passed**, coverage 86%

---

## Phase 2.4 — Admin Dashboard

**Issue:** #10 | **PR:** #11 | **Branch:** `phase-2.4-admin-dashboard`
**Status:** ✅ Merged

### Key technical decisions
- `filters: list[ColumnElement[bool]] = []` trong admin_users.py (mypy arg-type fix)
- Admin dashboard endpoints: `/admin/dashboard/stats`, `/admin/dashboard/recent-orders`, `/admin/users`, v.v.

### CI fixes trong review
- `ruff format`: `admin_dashboard.py`
- `prettier`: `stats-overview.tsx`, `admin.ts`
- mypy: thêm `admin_users` và `admin_dashboard` vào overrides
- mypy arg-type: `filters: list[ColumnElement[bool]] = []` explicit annotation

### Test results
- **151 passed**, coverage 86%

---

## Phase 3.1 — LLM Provider Abstraction

**Issue:** #12 | **PR:** #13 | **Branch:** `phase-3.1-llm-provider`
**Status:** ✅ Merged

### Key technical decisions
- `BaseLLMProvider` ABC → `GeminiProvider`, `OllamaProvider`
- `LLMFactory` singleton pattern
- `PromptLibrary` với Jinja2 templates tiếng Việt
- `LLMObservability` (Langfuse integration)

### CI fixes trong review
- **pip-audit**: `jinja2==3.1.3` có 4 CVEs → bump lên `jinja2==3.1.6`

### Test results
- **188 passed** (37 targeted), coverage 86%, mypy 58 source files

---

## Phase 3.2 — Vietnamese Embeddings & Knowledge Base

**Issue:** #14 | **PR:** #15 | **Branch:** `phase-3.2-embeddings-kb`
**Status:** ✅ Merged

### Key technical decisions
- `EmbeddingService` singleton, lazy-load `keepitreal/vietnamese-sbert` (768 dims), run in thread pool
- `VietnameseTextProcessor`: NFC normalization, underthesea sentence segmentation, smart chunking với overlap
- Hybrid search: `0.7 * vector_cosine + 0.3 * ts_rank`
- `KnowledgeBaseResponse` KHÔNG expose embedding vector
- 51 seed documents tiếng Việt (safety/products/delivery/faq/company)
- Embedding tests: mock SBERT trong tests (CI không download model)

### CI fixes trong review
- ESLint `react-hooks/set-state-in-effect`: refactor `page.tsx` KB → refreshKey + inline async pattern (xem mục ESLint setState-in-effect)
- `prettier`: 3 KB component files
- `ruff format`: `knowledge_base_service.py`, `tests/conftest.py`
- mypy: thêm `knowledge_base` vào overrides

### Test results
- **208 passed** (20 targeted), coverage 83%

---

## Phase 3.3 — RAG Pipeline with Safety

**Issue:** #16 | **PR:** #17 | **Branch:** `phase-3.3-rag-pipeline`
**Status:** ✅ Merged

### Key technical decisions
- Pipeline: safety check → retrieval → context build → LLM generation
- `SafetyChecker`: keyword matching (fast, predictable), 100% recall bắt buộc
- `SAFETY_EMERGENCY_RESPONSE_VI`: hằng số, KHÔNG gọi LLM, có `1900-1234`
- `test_safety_query_does_not_call_llm`: assert `llm.generate.assert_not_called()`
- Evaluation script: exit non-zero nếu safety_detection_rate < 100%
- `safety.py`: 100% coverage riêng

### Test results
- **329 passed** (121 targeted), coverage 83%
- Safety detection: **100.0%**, false positive: **0.0%** (86 test cases: 55 positive + 31 negative)
- `safety.py`: **100%** coverage

---

## Phase 3.4 — Intent Classification & Conversation Management

**Issue:** #18 | **PR:** #19 | **Branch:** `phase-3.4-intent-conversation`
**Status:** ✅ Merged

### Key technical decisions
- 8 intent categories: Python Enum (`IntentCategory`), không có DB table
- Hybrid classifier: embedding threshold 0.7 → dùng embedding; < 0.7 → fallback LLM
  - Exception: `SAFETY_EMERGENCY` luôn double-check bằng LLM
- Routing: safety → complaint → technical_issue → payment_issue → low_confidence → explicit_request → >8 turns → negative_feedback
- Auto-flag: `intent_confidence < 0.6` → `flagged_for_review = True`; `feedback == -1` → `flag_for_review()`
- Frontend: `refetchInterval: isOpen && conversationId ? 3000 : false` (polling 3s khi chat open)
- `EmergencyBanner` hiển thị khi `message.is_emergency`, có số `1900-1234`
- Embedding classifier mock trong tests (không load model thật)
- mypy overrides: thêm `app.api.v1.endpoints.conversations`

### Test results
- **358 passed** (29 targeted), coverage 82%

---

## Phase 4.1 — Continuous Learning (Review Queue & KB Feedback Loop)

**Issue:** #20 | **PR:** #21 | **Branch:** `phase-4.1-continuous-learning` | **Merged:** 2026-05-30

- Review queue backend: flagged messages → approve / reject / add-to-KB + review statistics.
- `MessageRepository` thêm `get_flagged_for_review`, `get_previous_message`, `update` (không đổi auto-flag logic / migration).
- Admin review UI: React Query hooks, API client, annotation workflow, KB dialog, statistics widgets.
- Tests: `test_review_service.py` 8 passed; full suite 366 items, coverage ≥ 70%.

---

## Phase 4.2 — Evaluation Framework (Intent Metrics & Safety CI Gate)

**Issue:** #22 | **PR:** #23 | **Branch:** `phase-4.2-evaluation-framework` | **Merged:** 2026-05-30

- `IntentEvaluator`: accuracy, per-intent precision/recall/F1, macro F1, confusion matrix.
- Bộ test intent tiếng Việt 96 case phủ cả 8 intent categories.
- `scripts.run_evaluation --suite {safety,intent,rag,all}`; **safety là default, exit non-zero nếu detection < 100%**.
- CI backend thêm bước safety evaluation sau pytest. Không thêm `ragas`/`datasets`.
- `pytest tests/evaluation` 8 passed; safety suite 86 case → detection 100%, false-positive 0%.

---

## Phase 4.3 — Production Deployment prep (Ops Runbook & Security Verification)

**Issue:** #24 | **PR:** #25 | **Branch:** `phase-4.3-deployment-prep` | **Merged:** 2026-05-30

- `docs/operations.md`: logs, debugging, scaling, backup/restore, incident response.
- `docs/deployment.md`: pre-deploy checklist, env var reference, monitoring, security audit, rollback, 7 sự cố prod thường gặp.
- `frontend/.env.example` (public frontend deploy vars).
- `scripts/verify_security_headers.py` + tests qua `TestClient(create_app())`.
- **Scope guard:** không deploy thật, không tạo secret/cloud account, không đổi dependency/middleware/migration.

---

## Post-launch — Production Iteration (#26 → #175)

> Sau Phase 4.3 dự án **go-live thật** (Vercel + Railway + Supabase + Gemini-Vertex). Từ đây không còn theo phase build-plan — là chuỗi fix/feature production. Gom theo cụm chủ đề; mỗi dòng = 1 PR đã merge.

### Cụm A — Go-live & Deploy Hardening (2026-05-30→31)
| PR | Tóm tắt |
|---|---|
| #26 | Railway healthcheck timeout 300s + log unbuffered |
| #27 | asyncpg qua Supabase Supavisor pooler (`statement_cache_size=0`) |
| #28 | Không chạy alembic lúc container boot |
| #29 | Chạy uvicorn qua shell để `$PORT` expand |
| #30 | Bỏ legacy `@secret` env refs khỏi vercel.json |
| #32 | Chore (tạm): surface 500 traceback để debug deploy |
| #33, #34 | HuggingFace cache writable cho non-root user (chown nhanh) |
| #36 | Auth cookie `SameSite=None` cho cross-site deploy |

### Cụm B — LLM/RAG Resilience (Gemini ↔ Groq/Jina/Vertex)
| PR | Tóm tắt |
|---|---|
| #31, #35 | Trích text Gemini từ `parts` (thinking-model safe) + size token budget |
| #37 | Migrate sang `google-genai` SDK + tắt thinking (perf) |
| #38, #39 | Gemini embeddings thay local SBERT (fix OOM) + truncate 768 dim |
| #46 | LLM fallback **Gemini→Groq** + Sentry alert |
| #49, #56 | Hotfix embed APIError 500 + RAG tx abort + embed dim |
| #50 | Embed fallback **Gemini→Jina** |
| #52 | Vertex AI mode |
| #54 | Intent embed quota fallback |
| #147 | Gỡ dep chết `torch` + `sentence-transformers` |

### Cụm C — Chat UX & Qiki bot (#40→#70)
| PR | Tóm tắt |
|---|---|
| #40, #42 | Optimistic message; type-while-waiting, Enter-to-send, feedback lock, copy |
| #44 | Like xanh / Dislike đỏ + client throttle (tránh 429) |
| #60, #61 | Product catalog context vào prompt; IME + autoscroll |
| #62, #65 | Thu địa chỉ 2-tier; polish markdown/date/phường→quận |
| #70 | Qiki typing indicator (status động khi chờ) |

### Cụm D — Rebrand & Delivery Zone
| PR | Tóm tắt |
|---|---|
| #67 | Delivery zone Bình Thạnh + Thủ Đức |
| #68 | **Rebrand → "Cửa hàng Gas Quốc Cường" + bot "Qiki"** |

### Cụm E — Chat Product Cards & Order Intake (#73→#86)
| PR | Tóm tắt |
|---|---|
| #73, #74 | Khung sản phẩm trong chat; chốt đơn qua chat |
| #76 | Guard chặn private key lọt repo (secret-scan) |
| #79 | Docs: chatbot pipeline diagram |
| #78, #81, #85 | Chat card UX; brand filter cho brand nhiều chữ / substring |
| #86 | Fix chat message loss / revert |

### Cụm F — Landing / Storefront (#88→#102)
| PR | Tóm tắt |
|---|---|
| #88, #90 | Landing UX + floating contact; footer (map, giờ, địa chỉ, thanh toán, các bước) |
| #92, #93 | Khu vực giao + tooltip phường; polish hero card/CTA/steps/scroll-trap |
| #96 | Badge giờ thực, fix Qiki kẹt, lọc card brand |
| #98 | Danh mục **Nước Uống** + đơn vị + note phụ phí |
| #100, #102 | Dropdown nền/nav hover, brand filter, chốt đơn nước, toast; fix tailwind popover transparency |

### Cụm G — Chat Order-Flow Hardening (#103→#154, cụm lớn nhất)
| PR | Tóm tắt |
|---|---|
| #103, #105 | Chat nước/gas intent + cards theo danh mục; order cards context + prompt khu phố |
| #107, #113 | Order state + phone validation + card scope; smarter order flow |
| #114, #119 | Track lookup + phone display; đặt đơn mới cùng chat + tái dùng SĐT |
| #121, #123, #125 | Order message/confirmations; giảm escalation + brand order intent; catalog phrase override complaint |
| #128, #129 | Đơn nhiều sản phẩm + fix loop xác nhận; phí ship gas free / nước +5k/bình |
| #131, #134 | Multi-item extraction 2 SP/câu (ưu tiên deterministic); fix LLM bịa gas từ câu địa chỉ |
| #136, #137 | Hỏi size gas + huỷ/off-topic giữa đơn; bỏ carve-out confirmed (gas-ma từ địa chỉ) |
| #140, #141 | Validate số khu phố theo phường; `_match_product` token-set thay substring |
| #144, #150 | Inference guard địa chỉ+SL+COD; order-state TTL 30 phút (chống stale hijack) |
| #151, #154 | Nút "Trò chuyện mới" + auto-reset idle; đặt thêm sau khi đã tạo đơn không lặp |
| #109, #115, #146 | Chore: sync seed real catalog; đơn giản mã đơn; câu từ chối off-topic lịch sự |

### Cụm H — UI Polish & Recent Fixes (#118, #155→#175)
| PR | Tóm tắt |
|---|---|
| #118 | Badge giờ mở cửa kẹt build-time (hydration) + nbsp trong giờ |
| #155, #157 | Tooltip nhanh + dropdown hover; trang SP: scrollbar filter, Tên Z-A, tách Sắp xếp, wrap text |
| #159, #161, #163 | Hero ép 3 dòng cố định + hạ cỡ chữ; select modal=false + card clickable |
| #166, #167 | Luôn hiện tóm tắt đơn + tư vấn gas không đổ card; header dropdown nav + filter Loại |
| #168 | Chore: dịch nốt comment tiếng Việt → English |
| #170, #174 | Add-gas-to-order chat flow; same-origin API proxy |
| **#175** | **Relax password policy + login toast → bottom-right** (chi tiết riêng bên dưới) |

---

## Fix #172 — Relax password policy + move login toast (PR #175)

**Issue:** #172 | **PR:** #175 | **Branch:** `fix-password-policy-and-toast-position`
**Status:** ✅ Merged (squash `f301759`) — 2026-06-12

### Thay đổi
- **Backend** `app/schemas/user.py` → `validate_password_strength` chỉ còn `8 <= len <= 128`; bỏ uppercase/lowercase/digit/special. Dùng chung cho `UserCreate`, `PasswordChangeRequest`, `PasswordResetConfirm`.
- **Frontend** `lib/validations/auth.ts` → `passwordSchema` = `.min(8).max(128)`, message "Mật khẩu tối thiểu 8 ký tự". Bỏ 4 regex complexity.
- **Frontend** helper text mới ở register + reset form; strength meter đổi sang length-based (`ceil(len/8)`).
- **Toast** `app/layout.tsx` → Sonner `position` từ `top-right` sang `bottom-right` (không che account menu sau login).
- **Tests** thêm `tests/api/test_user_password_policy.py` (8 pass / 7 fail) + cập nhật frontend validation tests.

### ⚠️ Deviation từ build plan
`gasbot_build_plan.md:3453,3463` vẫn ghi "min 12 chars with complexity". Fix này cố ý nới theo quyết định owner trong issue #172 → áp dụng rule "khi conflict, theo issue". Build plan ở điểm này đã stale (chưa sửa).

### Self-test CI (Claude chạy lại trên `main`, 2026-06-12)
- Backend: ruff format ✅ · ruff check ✅ · mypy (99 files) ✅ · pip-audit ✅ · **pytest 588 passed** (DB `gasbot_issue172_acceptance`)
- Frontend: type-check ✅ · lint ✅ · **vitest 32 passed** · format:check ✅ · build ✅
- GitHub CI: tất cả checks xanh (Vercel, secret-scan, 2× test job)

> ⚠️ History file này đang trễ: thiếu Phase 4.1–4.3 và các fix #166–#171 (chưa backfill).

---

## Coverage tổng hợp (backend)

| Phase | Tests | Coverage |
|---|---|---|
| 2.1 | 65 | ~80% |
| 2.2 | 107 | 86% |
| 2.3 | 134 | 86% |
| 2.4 | 151 | 86% |
| 3.1 | 188 | 86% |
| 3.2 | 208 | 83% |
| 3.3 | 329 | 83% |
| 3.4 | 358 | 82% |

---

*Updated: 2026-06-12 sau merge PR #175 (Fix #172 password policy + toast). Trước đó: 2026-05-29 sau Phase 3.4.*
