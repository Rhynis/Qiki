# ADR-0001: LangGraph agent orchestration alongside the hand-rolled flows

## Status

Accepted

## Context

Qiki already has two hand-rolled orchestration flows that work in production today:

1. **`ConversationService._plan_response`** (`backend/app/services/conversation_service.py`) —
   a ~400-line decision tree that classifies intent, then branches through safety,
   greeting, price lookup, catalog listing, order-in-progress, follow-up capture,
   handoff, and clarification cases before falling through to the RAG pipeline.
   Every branch is a Python `if`/`elif` reading and mutating local variables; the
   whole function is the unit of work for one customer turn.
2. **`AdminChatService`** (`backend/app/services/admin_chat_service.py`) — a
   narrower, single-mutation flow: parse an admin instruction → resolve it against
   the live catalog → validate → **stop and ask for confirmation** → on a second
   request that echoes a token, re-validate and apply the mutation, with an audit
   record. This is Qiki's existing human-in-the-loop (HITL) precedent.

Both work and are well-tested. The question this ADR answers is not "is the
hand-rolled approach broken" — it isn't — but "what do we gain, and what do we
give up, by expressing new agentic behavior (multi-step tool use, a
planner/verifier loop, more HITL mutations) in LangGraph instead of extending
these two flows further?"

Looking at `AdminChatService` specifically as the closest existing analogue to
what an agent "pause and wait for a human" step needs:

- The pending action lives in **Redis** as a JSON blob under a hand-rolled key
  (`admin_chat:pending:{token}`), with a 300s TTL and an app-level "claim it
  atomically via `GETDEL`" convention to stop a double-confirm from applying a
  mutation twice.
- The token is opaque and single-purpose. To add a *second* kind of pausable
  action (say, an order that needs delivery-zone confirmation) requires a new
  Redis key scheme, a new claim protocol, and a new re-validation path — the
  pattern is not reusable, it's a template to copy.
- If the process crashes between `_plan` and `_execute_pending`, the pending
  token silently expires (300s TTL) and the admin just re-issues the command.
  That's *fine* for a single-mutation flow with a short window, but it is not a
  general resume mechanism — there is no way to inspect "where did this
  multi-step task get to" beyond the one JSON blob.
- `_plan_response` has no persisted intermediate state at all: it is one
  in-memory Python call stack per turn. A crash mid-turn loses the whole turn;
  the client just retries the request from scratch. That's acceptable for a
  single RAG turn (cheap to redo) but would not be for a multi-step task (e.g.
  "find the cheapest 12kg option, check it's in stock in her zone, then draft an
  order") where redoing step 1 after step 3 fails is wasted latency and, once
  tools have side effects, potentially wasted work.

## Decision

Add a **LangGraph `StateGraph`** as a new orchestration layer for the
**agentic** parts of Qiki (multi-step tool use, and future planner/verifier and
mutation-with-approval flows), running **alongside** — not replacing —
`ConversationService`/`AdminChatService`. The existing `/chat` and admin-chat
endpoints are untouched; the new graph is reachable only via a separate,
feature-flagged endpoint (`AGENT_ENABLED`, default off — see the main issue for
the flag).

This is **not** "we built an agent" — it is "we picked a durable execution
substrate for the same kind of hand-rolled step sequencing +
confirm-before-mutate pattern `AdminChatService` already proved out, because
that substrate gives us specific, concrete things the hand-rolled version
doesn't, for close to zero cost while the graph only has 3 read-only tools and
no mutations":

| Concern | Hand-rolled (today) | LangGraph |
| --- | --- | --- |
| Multi-step state across a turn | Local Python variables inside one call stack (`ResponsePlan`, `RagStreamPlan`) | `QikiAgentState` — a typed, versioned channel dict the graph reads/writes at every node |
| Resume after a crash/timeout | None for `_plan_response` (retry the whole turn); a 300s Redis TTL blob for `AdminChatService`'s one pending action | Every superstep is checkpointed to Postgres; `graph.astream(..., config={"configurable": {"thread_id": ...}})` resumes from the last checkpoint, not from scratch |
| Human-in-the-loop pause/resume | Bespoke: a hand-rolled Redis token + `GETDEL` claim + optimistic-concurrency snapshot, written once for exactly one mutation type | `interrupt()` — a standard primitive that pauses the graph and resumes it with `Command(resume=...)`; the same mechanism works for any future pausable step, not a new copy-pasted protocol each time |
| Adding a new step (e.g. a verifier or planner before responding) | Insert another `elif` branch into an already-large function and re-thread every downstream variable it might affect | Add a node and an edge; existing nodes are untouched |
| Observability of *how* an answer was produced | Structured logs per branch (`self.logger.info(...)`), no single "trajectory" object | `graph.astream(stream_mode=["updates", "messages"])` yields the node-by-node trajectory — the same shape a future eval harness (deferred to a separate issue) would score |
| Testing one step in isolation | Have to construct the whole `ConversationService` and drive it through `_plan_response` | Each node is `async def node(state) -> dict` — a plain function, trivially unit-testable |
| **Cost: new dependency surface** | None — stdlib + what's already installed | `langgraph` + `langgraph-checkpoint-postgres` (+ `psycopg`) — a new runtime dependency, a new connection pool (ADR-0002), and a graph-shaped mental model the team has to learn |
| **Cost: marginal complexity for what MVP actually does** | N/A | For 3 read-only tools and no HITL yet, a hand-rolled loop would honestly have been *simpler right now* — the payoff is in what this substrate makes cheap to add *next* (see below), not in the MVP itself |

The two "cost" rows are the honest half of this trade-off, not an
afterthought: this ADR is not claiming LangGraph is free. It is claiming that
paying that cost once, on a 3-tool read-only MVP with no production traffic
depending on it yet, is cheaper than paying it later on top of a bigger
hand-rolled surface, *if* the roadmap includes the things LangGraph is
specifically good at — a verifier/planner step and mutating tools that need
approval. If neither of those materializes, this ADR's premise doesn't hold and
the agent layer should be reconsidered rather than grown.

## Consequences

**Easier:**
- Adding the next tool, or a verifier/planner node, is additive (new node +
  edge) instead of another branch in an already-large function.
- A future mutating tool (e.g. `create_order`) gets `interrupt()`-based
  confirmation for free instead of a bespoke Redis-token protocol per mutation
  type.
- The per-node trajectory is the natural input to a future agent-eval harness
  (tool selection / argument correctness / task completion — tracked as a
  separate issue, out of scope here).
- A long-running or multi-turn task can be resumed from its last checkpoint
  instead of restarted, once tools have real latency or side effects.

**Harder / riskier:**
- A second orchestration mental model now exists in the codebase
  (`_plan_response`'s branching vs. the graph's nodes/edges); a contributor has
  to know which one a given piece of behavior lives in. Mitigated by keeping the
  boundary sharp: existing customer/admin chat paths stay exactly as they are;
  only new agentic behavior goes into the graph.
- A new stateful dependency (the Postgres checkpointer, ADR-0002) that can fail
  in ways the existing Redis-only session model doesn't.
- `langgraph` + `langgraph-checkpoint-postgres` + their transitive deps
  (`langchain-core`, `langsmith`) are a real addition to the dependency and
  attack surface, audited the same as everything else (`pip-audit --strict`).
- The safety-critical path must not regress: the graph's safety short-circuit
  calls `rag/safety.py` directly and **never** the LLM, exactly like
  `RAGPipeline.query`/`query_stream` do today — this is enforced by a test that
  asserts the LLM provider's `generate`/`stream` was never called on an
  emergency query, mirroring the existing RAG safety test.
- Deterministic pricing (#239) is preserved because the `search_products` /
  `check_inventory` tools call `ProductService` directly — the same repository
  methods the RAG/chat paths already use — rather than re-deriving prices.
