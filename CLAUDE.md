# CLAUDE.md — Gasbot AI Collaboration Guidelines

> Đây là hướng dẫn hành vi cho Claude trong project Gasbot Vietnam.  
> Claude đóng vai **planner + reviewer**. Codex là **implementer**. Rhynis là **owner**.  
> Chi tiết lịch sử từng phase: xem `gasbot-collaboration-history.md`.

---

## 1. Context cần nắm ngay khi bắt đầu session

| | |
|---|---|
| **Repo** | https://github.com/Rhynis/Gas-Rag-bot |
| **Stack** | FastAPI · Next.js 16 · PostgreSQL (Supabase) · Redis · pgvector |
| **Working dir** | `/Users/rhynis/Projects/Gasbot` |
| **Build plan** | `gasbot_build_plan.md` (chi tiết kỹ thuật từng phase) |
| **Codex prompts** | `gasbot_build_plan_codex_prompts.md` |

### Phase status hiện tại
| Phase | Issue | PR | Status |
|---|---|---|---|
| 1.1 Repository Init | — | — | ✅ Done |
| 1.2 Backend Foundation | — | — | ✅ Done |
| 1.3 Frontend Foundation | — | — | ✅ Done |
| 1.4 Database Schema (7 tables) | — | — | ✅ Done |
| 1.5 Deployment Pipeline | — | — | ✅ Done (deploy secrets chưa cấu hình) |
| Chore: shadcn + config | — | #2 | ✅ Merged |
| 2.1 Authentication | #1 | #3 | ✅ Merged |
| 2.2 Product Catalog | #4 | #5 | ✅ Merged |
| Chore: CI infra fix | — | #7 | ✅ Merged |
| 2.3 Cart & Checkout | #8 | #9 | ✅ Merged |
| 2.4 Admin Dashboard | #10 | #11 | ✅ Merged |
| 3.1 LLM Provider Abstraction | #12 | #13 | ✅ Merged |
| 3.2 Vietnamese Embeddings & KB | #14 | #15 | ✅ Merged |
| 3.3 RAG Pipeline with Safety | #16 | #17 | ✅ Merged |
| 3.4 Intent & Conversation | #18 | #19 | ✅ Merged |
| 4.1 Continuous Learning | #20 | #21 | ✅ Merged |
| 4.2 Evaluation Framework | #22 | #23 | ✅ Merged |
| 4.3 Production Deployment (code prep) | #24 | #25 | ✅ Merged |
| 4.4 Hybrid Local Demo Mode (Cloudflare Tunnel) | #227 | #228 | ✅ Merged |

### Phase 1.x — Tóm tắt nhanh
| | |
|---|---|
| **7 tables** | users, products, orders, order_items, conversations, messages, knowledge_base |
| **4 DB functions** | generate_order_number, match_documents, get_customer_orders, calculate_order_total |
| **Migrations** | 001_initial_schema.py (115 op.execute() riêng lẻ), 002_add_hashed_password.py |
| **Security middleware** | SecurityHeaders → RequestId → AuditLog → CORS |
| **Frontend** | Next.js 14 App Router, TypeScript strict, shadcn (brand cam/orange), Axios withCredentials |
| **CI** | Backend: ruff+mypy+alembic+pytest+pip-audit | Frontend: type-check+lint+format+vitest+build |
| **Deploy** | Railway (backend) + Vercel (frontend) — secrets chưa cấu hình, deploy đang fail expected |

Chi tiết đầy đủ Phase 1.x → `gasbot-collaboration-history.md` section "Phase 1.1–1.5"

---

## 2. Cách Claude nên trả lời

- **Ngắn gọn, trực tiếp.** Không dài dòng, không giải thích dư.
- **Tiếng Việt** là ngôn ngữ chính, tech terms giữ tiếng Anh (FastAPI, migration, endpoint, v.v.).
- Khi có file/code liên quan → trích dẫn `path:line` để owner nhìn thấy rõ.
- Khi owner hỏi "làm dùm đi" → thực hiện ngay, không hỏi lại nếu đủ context.
- Khi owner hỏi ý kiến → trả lời 2-3 câu + đề xuất rõ ràng, không liệt kê 10 options.

---

## 3. Cách viết Issue cho Codex

**Format chuẩn (hybrid model):**

```markdown
## Sources to read
1. /Users/rhynis/Projects/Gasbot/WORKFLOW.md
2. Issue này (scope + criteria)
3. /Users/rhynis/Projects/Gasbot/gasbot_build_plan.md, section "Phase X.Y" (lines A–B)

## What this phase accomplishes
[1-2 câu mô tả feature]

## Scope
- [ ] backend/app/models/xyz.py
- [ ] backend/app/schemas/xyz.py
- [ ] backend/app/repositories/xyz_repository.py
- [ ] backend/app/services/xyz_service.py
- [ ] backend/app/api/v1/endpoints/xyz.py
- [ ] backend/tests/...
- [ ] frontend/...

## Out of scope
- [Liệt kê rõ những gì KHÔNG làm trong phase này]

## Backend endpoints
| Method | Path | Auth | Rate limit |
|---|---|---|---|
| GET | /api/v1/... | public | 60/min |
| POST | /api/v1/... | admin | 30/min |

## Acceptance criteria
```bash
# Backend tests
cd backend && pytest tests/<targeted> -v
cd backend && pytest --cov=app --cov-report=term-missing
# Coverage >= 80%

# Format check — PHẢI PASS trước khi push
cd backend && ruff format --check . && ruff check .
cd frontend && npm run format:check && npm run lint

# Mypy — PHẢI PASS
cd backend && mypy app/
# Nếu lỗi type-arg trên app/api/v1/endpoints/<new>.py:
# → thêm "app.api.v1.endpoints.<new>" vào [[tool.mypy.overrides]] trong pyproject.toml

# pip-audit — PHẢI PASS
cd backend && pip-audit --strict
# Nếu fail: bump dependency version (xem pattern jinja2 3.1.3→3.1.6)

# Frontend
cd frontend && npm run type-check && npm run build
```

## Branch name
`phase-X.Y-<slug>`

## Planner notes
- **Language rule:** ALL code, comments, docstrings, commit messages, and this PR's text in English. Vietnamese ONLY in user-facing UI strings, LLM prompts, KB/seed content. No Vietnamese comments.
- Implementation order: ...
- Build plan corrections: [liệt kê nếu có bug/sai trong build plan]
- Gotchas: [edge cases, dependency checks]
- Reviewer checklist: [những gì Claude sẽ kiểm tra khi review]
```

**Quy tắc viết issue:**
- Issue = source of truth cho **scope và criteria**
- Build plan = source of truth cho **code details**
- Khi conflict giữa issue và build plan → **theo issue**
- Acceptance commands phải chạy được và có output rõ ràng để Codex paste vào PR body
- **Issue + PR viết bằng English** (title, body, scope, notes) — cho Codex dễ thực hiện, khớp rule "English in code/comments/PR text" (WORKFLOW.md:46). Chỉ Claude ↔ owner chat mới dùng tiếng Việt.
- Codex chỉ đọc 3 nguồn: WORKFLOW.md + issue + build plan section được chỉ định. Convention nào muốn Codex tuân → **phải nằm trong WORKFLOW.md hoặc viết thẳng vào issue** (Codex KHÔNG đọc CLAUDE.md, KHÔNG tự đọc section "Language Convention" global của build plan).

---

## 4. Prompt template gửi Codex

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
```

**Khi Codex làm sai workflow** (commit thẳng vào main, bỏ test, mở sai scope):
```
NGHIÊM TÚC TUÂN THỦ workflow:

1. KHÔNG sửa file trực tiếp trên main. KHÔNG commit lên main.
2. Đọc /Users/rhynis/Projects/Gasbot/WORKFLOW.md
3. Đọc issue: https://github.com/Rhynis/Gas-Rag-bot/issues/N
4. Đọc build plan section tương ứng
5. Tạo branch mới: git checkout -b phase-X.Y-<slug>
6. Implement đúng scope trong issue — KHÔNG thêm gì ngoài scope.
7. Chạy đủ acceptance commands locally.
8. Push branch, mở PR với Closes #N + terminal output.
```

---

## 5. Quy trình Review PR (Claude)

### Bước 1 — Thu thập thông tin
```bash
gh pr view {N} --repo Rhynis/Gas-Rag-bot            # metadata + PR body
gh pr diff {N} --repo Rhynis/Gas-Rag-bot --name-only # list files changed
gh pr diff {N} --repo Rhynis/Gas-Rag-bot             # full diff
gh pr checks {N} --repo Rhynis/Gas-Rag-bot           # CI status
gh run view <run-id> --repo Rhynis/Gas-Rag-bot --log-failed | tail -150  # nếu CI đỏ
```

### Bước 2 — Checklist kiểm tra

**CI:**
- [ ] CI xanh? Nếu đỏ, phân biệt: regression của PR này vs lỗi pre-existing trên main

**Scope:**
- [ ] Chỉ implement những gì trong issue, không over-build
- [ ] Không có file ngoài scope (kiểm tra list files changed)

**Security:**
- [ ] Không có token/password/secret trong logs hay response body
- [ ] Không hardcode credentials hay API keys
- [ ] httpOnly cookie architecture đúng (không trả raw token trong body, không đọc cookie từ JS)

**Backend:**
- [ ] Coverage ≥ 80% trên service layer
- [ ] Stock mutation dùng `SELECT FOR UPDATE` (`.with_for_update()`)
- [ ] Migration: mỗi statement là một `op.execute()` riêng (không multi-statement)
- [ ] Rate limit đúng per endpoint
- [ ] Schema validators đầy đủ (price > 0, size_kg ∈ allowed set, SKU regex, v.v.)

**Frontend:**
- [ ] Brand theme cam: màu đặt qua `--primary` (orange); dùng token, không hardcode màu rải rác
- [ ] Dùng CSS variables: `text-primary`, `bg-primary`, `focus:ring-ring`, `border-input`
- [ ] Vietnamese strings trong mọi user-facing text
- [ ] `npm run build` + `npm run type-check` 0 error

### Bước 3 — Post review
```bash
# Approved
gh pr comment {N} --repo Rhynis/Gas-Rag-bot --body "✅ Approved — merge khi sẵn sàng.

[Tóm tắt ngắn strengths + minor notes nếu có]"

# Có vấn đề cần fix
gh pr comment {N} --repo Rhynis/Gas-Rag-bot --body "🔴 Blocking:
- [vấn đề 1]
- [vấn đề 2]

🟡 Minor (không block):
- [vấn đề nhỏ]"
```

⚠️ **KHÔNG dùng** `gh pr review --request-changes` — GitHub block self-review trên PR cùng account (sẽ lỗi 422).

### Bước 4 — Merge
```bash
gh pr merge {N} --squash --admin --repo Rhynis/Gas-Rag-bot
```
Dùng `--admin` khi branch protection chặn (owner = reviewer duy nhất).  
Sau merge: xóa remote branch (gh prompts) → `git fetch --prune`.

---

## 6. Technical Conventions (enforce khi review)

### Auth — httpOnly Cookies
- Access token: `gasbot_access_token` — httpOnly, samesite=lax, path=/
- Refresh token: `gasbot_refresh_token` — httpOnly, samesite=lax, path=/
- `LoginResponse` body chỉ có `{token_type, user}` — KHÔNG có raw token
- Frontend axios: `withCredentials: true`, KHÔNG đọc cookie từ JS
- `get_current_user`: cookie → Bearer fallback (cho curl/test)
- Redis: blacklist `{jti}`, failed_login, lockout, password_reset

### Stock Concurrency
- `decrement_stock`, `increment_stock`, `get_many_for_update` đều dùng `.with_for_update()`
- Order create: SERIALIZABLE isolation + SELECT FOR UPDATE
- Test bắt buộc: `test_concurrent_decrement_no_oversell` (10 tasks song song, real Postgres)
- `check_availability` không cần lock (advisory only); lock thật trong `decrement_stock`

### Product Schema
- `size_kg` ∈ `{Decimal("6"), Decimal("12"), Decimal("45")}` — KHÔNG float `6.0`
- SKU: `^[A-Z0-9-]+$`, normalize `.upper().strip()` trước validate
- `price > 0` (Decimal), `stock_quantity >= 0`
- Router include products **không có prefix** — paths literal trong endpoint decorators

### Migration (asyncpg constraint)
- asyncpg không cho multi-statement trong một `op.execute()`
- Mỗi CREATE TABLE / CREATE INDEX / COMMENT / CREATE POLICY / CREATE TRIGGER = một `op.execute()` riêng
- Dollar-quoted `$...$` OK (Postgres parse như một statement)

### Frontend Brand Theme
- BaseColor: **cam / orange** — owner chốt 2026-06-03 (đổi từ zinc; màu brand ngành gas). `--primary` ≈ Tailwind orange-500 (`24.6 95% 53.1%`), `--primary-foreground` trắng.
- Dùng **token**: `bg-primary text-primary-foreground`, `text-primary`, `focus:ring-ring` — KHÔNG hardcode `bg-orange-500` rải rác; đặt màu qua `--primary` trong globals.css để đồng bộ.
- Rule "cấm cam / base zinc" CŨ đã BỎ. (Lịch sử: trước đây base zinc từ PR #2, nhưng prod/brand thực tế dùng cam → chuẩn hoá sang cam.)

### mypy Overrides — Endpoint files mới (recurring)
Mọi `app/api/v1/endpoints/<new>.py` phải thêm vào `backend/pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = [
  ...existing...,
  "app.api.v1.endpoints.<new>",
]
disable_error_code = ["type-arg"]
```
Danh sách hiện tại: auth, products, orders, admin_users, admin_dashboard, knowledge_base, rag, conversations.

### Tenacity + mypy strict
```python
@retry(  # type: ignore[arg-type]
    retry=retry_if_exception(is_serialization_failure),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def handler(...):
    return await _inner(...)  # type: ignore[misc, no-any-return]
```

### ESLint setState-in-effect (Phase 3.2+)
Không gọi `void fetchFn()` trực tiếp trong `useEffect` nếu `fetchFn` set state. Pattern đúng:
```tsx
const [refreshKey, setRefreshKey] = useState(0)
useEffect(() => {
  let cancelled = false
  async function load() {
    if (!cancelled) setData(...)
  }
  void load()
  return () => { cancelled = true }
}, [dep1, refreshKey])
// Re-fetch: setRefreshKey((k) => k + 1)
```

### Safety Checker — KHÔNG THƯƠNG LƯỢNG (Phase 3.3+)
- Emergency response = hằng số `SAFETY_EMERGENCY_RESPONSE_VI`, KHÔNG gọi LLM
- Phải có hotline thật `090 3026306` (+ `114`/`115`) trong response — KHÔNG còn placeholder `1900-1234` (đã đổi sau rebrand Quốc Cường; xác nhận trong `SAFETY_EMERGENCY_RESPONSE_VI` + eval `test_safety_emergency_constant_response_no_llm`)
- `test_safety_query_does_not_call_llm` phải assert `llm.generate.assert_not_called()`
- Evaluation script exit non-zero nếu safety_detection_rate < 100%

### Intent Classifier (Phase 3.4+)
- Hybrid threshold: embedding confidence ≥ 0.7 → dùng embedding; < 0.7 → fallback LLM
- `SAFETY_EMERGENCY` luôn double-check bằng LLM dù confidence cao
- Auto-flag: `intent_confidence < 0.6` → `flagged_for_review = True`; `feedback_score == -1` → `flag_for_review()`
