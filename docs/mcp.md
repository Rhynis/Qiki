# MCP Server

Qiki exposes its read-only agent tools (`search_products`, `check_inventory`,
`lookup_safety_policy`, `find_nearest_store`, `calculate_delivery_fee`) as an
[MCP](https://modelcontextprotocol.io) server, mounted into the same FastAPI
app at `/mcp` — no separate process. This lets any MCP client (Claude
Desktop, the MCP Inspector, or another agent) call Qiki's product/store data
directly, over the current **Streamable HTTP** transport.

Implementation: `backend/app/mcp_server/`. Feature-flagged behind
`MCP_ENABLED` (default `false`) — off by default, zero extra startup cost.

## Enable it locally

```bash
cd backend
MCP_ENABLED=true uvicorn app.main:app --reload
```

The MCP endpoint is now live at `http://localhost:8000/mcp`.

## Auth: get a bearer token

Every MCP tool call requires a valid Qiki access token — same JWT
`AuthService.verify_token` already validates for the REST API
(`app/api/v1/dependencies/auth.py`). There's no separate MCP login: register
or log in through Qiki's normal auth endpoints, then reuse that token.

`LoginResponse` never returns the raw token in its JSON body (it's an
httpOnly cookie by design — see `CLAUDE.md`'s Auth conventions). To get the
raw string for an `Authorization: Bearer` header, read it out of the cookie
jar after logging in via curl:

```bash
# 1. Register (skip if you already have an account)
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"phone": "0909000349", "password": "McpDemo123", "full_name": "MCP Reviewer"}'

# 2. Log in, saving cookies to a jar
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "0909000349", "password": "McpDemo123"}'

# 3. Extract the access token value from the jar
TOKEN=$(grep gasbot_access_token cookies.txt | awk '{print $NF}')
echo "$TOKEN"
```

Any authenticated Qiki user (customer, staff, or admin) can call these
tools — see "Why these tools don't need role-gating" below.

## Test with the MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI:

1. Transport: **Streamable HTTP**
2. URL: `http://localhost:8000/mcp`
3. Headers: `Authorization: Bearer <TOKEN>` (from above)
4. Connect, then **List Tools** — you should see all 5 read-only tools.
5. Call `search_products` with e.g. `{"query": "Elf 12kg"}`.

### Verifying without the Inspector UI (curl)

The Inspector's UI can't be screenshotted from a headless environment, but
the same protocol works over plain curl. Streamable HTTP is a 2-step
handshake: `initialize` first (the response carries an `Mcp-Session-Id`
header), then reuse that session ID for every following call.

```bash
# Unauthenticated call is refused
curl -i -X POST http://localhost:8000/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
# -> 401, WWW-Authenticate: Bearer

# Initialize (grab Mcp-Session-Id from the response headers)
curl -i -X POST http://localhost:8000/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2026-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.1"}}}'

# List tools (SESSION = the Mcp-Session-Id header from above)
curl -X POST http://localhost:8000/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Mcp-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Call search_products
curl -X POST http://localhost:8000/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Mcp-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_products","arguments":{"query":"Elf 12kg"}}}'
```

## Claude Desktop

Add this to `claude_desktop_config.json` (Claude menu -> Settings ->
Developer -> Edit Config):

```json
{
  "mcpServers": {
    "qiki": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <TOKEN>"
      }
    }
  }
}
```

If your Claude Desktop version doesn't yet support a direct `url` entry for
remote Streamable HTTP servers, bridge it with
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) instead:

```json
{
  "mcpServers": {
    "qiki": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8000/mcp",
        "--header",
        "Authorization: Bearer <TOKEN>"
      ]
    }
  }
}
```

Restart Claude Desktop, then ask it something like "what gas cylinders does
Qiki have in stock right now" — it should call `search_products`/
`check_inventory` directly.

## stdio (optional, local-only)

The mounted-into-FastAPI Streamable HTTP path above is the primary
deliverable. For a quick local Inspector session without running the whole
FastAPI app, FastMCP also makes stdio trivial — the same `create_mcp_server()`
tools respond identically, since every tool adapter opens its own DB session
directly (`app/mcp_server/server.py`) rather than depending on FastAPI's
request scope:

```bash
cd backend
python -c "from app.mcp_server.server import create_mcp_server; create_mcp_server().run(transport='stdio')"
```

Note: stdio has no HTTP layer, so the bearer-token gate (`QikiTokenVerifier`)
does not apply here — anyone who can spawn the process can call the tools.
Only use stdio for local, single-user testing, never for a shared deployment.

## Why these tools don't need role-gating

All 5 tools mirror data Qiki already exposes to anonymous users elsewhere:

- `search_products` / `check_inventory` — the same `GET /api/v1/products`
  read endpoints require no auth at all (only admin `POST`/`PATCH`/`DELETE`
  do).
- `lookup_safety_policy` — the *admin* KB search REST endpoint requires
  staff, but the underlying KB content is already surfaced to anonymous
  storefront visitors through Qiki's public chat (`POST
  /chat/agent/stream`, `current_user` optional) — it's the admin CRUD
  surface that's gated, not the informational content itself.
- `find_nearest_store` / `calculate_delivery_fee` — mirror the storefront's
  own public delivery-area and checkout-shipping-fee display.

So there's no natural "this tool needs auth, that one doesn't" split to
enforce per-tool. Instead, the MCP surface as a whole requires *some* valid
Qiki bearer token for every call — a deliberate, conservative default for
demonstrating resource-server-style auth, not a reflection of the
underlying data being sensitive. See `backend/tests/mcp/test_server.py`
for the regression tests (unauthenticated and invalid-token calls both
refused with 401).

## Never a mutating tool

Only the 5 read tools above are ever registered
(`app.mcp_server.server.READ_ONLY_TOOL_NAMES`). Creating an order,
scheduling a delivery, or any other mutation stays inside the LangGraph
agent behind its own HITL/confirm gate — never reachable over MCP.
`tests/mcp/test_server.py::TestToolRegistration` asserts the registered
tool set exactly, so adding a write tool here later would fail loudly
instead of silently shipping.
