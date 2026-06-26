#!/usr/bin/env bash

set -euo pipefail

MODEL="qwen2.5:7b-instruct-q4_K_M"
OLLAMA_BASE_URL="http://localhost:11434"

echo "Starting GasBot Local Demo Mode..."
echo ""

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install it with: brew install ollama"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Run ./cloudflare/setup-tunnel.sh first."
  exit 1
fi

if ! curl -fsS "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve >/tmp/gasbot-ollama.log 2>&1 &
  sleep 5
fi

if ! curl -fsS "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
  echo "Ollama did not become ready at $OLLAMA_BASE_URL."
  exit 1
fi

if ! ollama list | awk '{ print $1 }' | grep -qx "$MODEL"; then
  echo "Pulling $MODEL. This can take several minutes the first time."
  ollama pull "$MODEL"
fi

echo "Pre-warming $MODEL..."
curl -fsS "$OLLAMA_BASE_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"prompt\":\"Hello\",\"stream\":false}" \
  >/dev/null

echo ""
echo "Starting Cloudflare Tunnel..."
echo "Set the production backend OLLAMA_BASE_URL to your Cloudflare hostname from setup."
echo "Demo mode is active. Press Ctrl+C to stop the tunnel."

cloudflared tunnel run
