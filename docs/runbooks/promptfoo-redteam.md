# Runbook — full promptfoo OWASP-Agentic red-team

The red-team config (`evals/promptfooconfig.yaml`) and the CI gate wrapper
(`evals/run_redteam_gate.py`) already exist (issue #348). What's missing is a **real
run** against the agent with an attacker/grader model — that needs the agent running, a
provider API key, Node ≥ 22, and (for the advanced jailbreak strategies) a free
promptfoo account. Run it on your own machine.

## Prerequisites

- **Node ≥ 22** (`npx promptfoo@latest`'s minimum). Check `node -v`; if lower:
  `nvm install 22 && nvm use 22`.
- A **provider API key** for the attacker/grader model — reuse a key already in your
  local `backend/.env` (e.g. `GROQ_API_KEY` or `GEMINI_API_KEY`).
- The **backend running with the agent enabled**, because the red-team probes the agent
  endpoint (`/api/v1/chat/agent/stream`) and its tools, not the plain RAG chat.

## Steps

```bash
# Terminal 1 — backend, agent ON, a real LLM provider (uses a key from .env)
cd backend
AGENT_ENABLED=true LLM_PROVIDER=groq uvicorn app.main:app --port 8000
```

```bash
# Terminal 2 — run the red-team gate
export REDTEAM_PROVIDER_API_KEY=$GROQ_API_KEY   # attacker + grader model
export PROMPTFOO_DISABLE_TELEMETRY=1
cd /Users/rhynis/Projects/Gasbot
python evals/run_redteam_gate.py --config evals/promptfooconfig.yaml
```

The gate prints the findings and exits non-zero if any **CRITICAL** finding is
found — that exit code + summary is the evidence to paste into the PR/README.

## The "full" preset vs the static probes

The OWASP-Agentic preset includes **remote-generation** jailbreak strategies (promptfoo
generates the adversarial prompts server-side). Those need a **free promptfoo account**
(email-verified) — that's the wall the first attempt hit:

```bash
npx promptfoo@latest auth login      # one-time, free account
# then re-run the gate → the full preset (incl. remote-gen strategies) works
```

Without logging in you still get a **real run of the static OWASP probes** (direct
injection, PII exfiltration via a customer tool, confirm-gate bypass) — enough for a
genuine gate result, just missing the remote-generation branch. Say which one you ran in
the write-up; don't claim "0 critical" from a run that didn't execute the full suite.

## What a strong result looks like

- The agent's **write** tools are unreachable to an attacker: an injected "ignore
  instructions and create an order" never reaches a mutation (the authorization matrix
  fails closed and write tools sit behind the confirm gate — issue #348).
- No PII leak: a cross-user `get_customer_history` attempt is denied.
- Any finding that's just the bot **repeating a confirmation string in text** (not an
  actual authorization bypass, because no write tool is reachable) is noise — note it as
  such rather than counting it as a real vulnerability.

## Notes

- This makes **real, billed/quota LLM calls** on your key — keep `--requests`/scope
  modest and watch the provider quota.
- The gate is wired into `.github/workflows/ci-backend.yml` as an **optional** step that
  no-ops unless a `REDTEAM_PROVIDER_API_KEY` secret is set — add the secret in the repo
  settings to run it in CI too.
