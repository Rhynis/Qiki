# Local Demo Mode

Local Demo Mode lets GasBot answer production demo traffic with a local Ollama model running on
the owner's Mac. The production frontend and backend stay deployed, while the backend points its
LLM provider at a Cloudflare Tunnel URL that forwards to `localhost:11434`.

## Architecture

```text
User browser
  |
  v
Production frontend (Vercel)
  |
  v
Production backend (Railway)
  |
  v
Cloudflare Tunnel
  |
  v
Owner Mac -> Ollama -> Qwen 2.5 7B
```

The frontend detects demo mode through `/health/detailed`. When the backend reports
`llm_provider=ollama`, the app shows the Vietnamese demo banner at the top of the page.

## Prerequisites

- A Mac with enough memory for `qwen2.5:7b-instruct-q4_K_M`.
- Ollama installed locally.
- `cloudflared` installed locally.
- A Cloudflare account with a domain routed through Cloudflare.
- Access to update production backend environment variables.

## One-Time Tunnel Setup

Run the interactive setup script:

```bash
./cloudflare/setup-tunnel.sh
```

The script logs in to Cloudflare, creates a tunnel, routes DNS, and writes the active local
configuration to `~/.cloudflared/config.yml`. The committed
`cloudflare/config.template.yml` is only a placeholder template and must not contain real tunnel
IDs, domains, or credential paths.

## Starting Local Demo Mode

Run:

```bash
./scripts/start-local-demo.sh
```

The script checks that Ollama and `cloudflared` are installed, starts Ollama if needed, pulls
`qwen2.5:7b-instruct-q4_K_M` when missing, pre-warms the model, and runs the Cloudflare Tunnel.

## Production Environment Variables

The owner updates production backend variables manually when demo mode should be active:

```env
LLM_PROVIDER=ollama
ENVIRONMENT=local-demo
OLLAMA_BASE_URL=https://ollama-demo.YOUR_DOMAIN.com
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
```

Use `OLLAMA_BASE_URL`. The backend settings are case-sensitive and ignore unknown variables, so
only the documented variable name will switch the provider URL.

To return production to the cloud model, switch the production backend back to the normal Gemini
configuration.

## Stopping Local Demo Mode

Run:

```bash
./scripts/stop-local-demo.sh
```

This stops `cloudflared`. Ollama is intentionally left running by default; the stop command is
documented as a commented line in the script.

## Interview Talking Points

- GasBot uses a pluggable LLM provider abstraction, so the same chatbot can run against Gemini or
  local Ollama.
- Cloudflare Tunnel makes the local Mac reachable by the production backend without opening router
  ports or committing credentials.
- The demo highlights practical cost and privacy tradeoffs: stable cloud inference for normal
  production use, local inference for controlled demos or sensitive experiments.
- The `/health/detailed` endpoint exposes the active provider, and the frontend banner makes the
  local mode visible during a live walkthrough.
