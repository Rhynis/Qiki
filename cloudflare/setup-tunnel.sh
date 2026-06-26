#!/usr/bin/env bash

set -euo pipefail

echo "================================================"
echo "Cloudflare Tunnel Setup for GasBot Demo Mode"
echo "================================================"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed."
  echo "Install it first with: brew install cloudflare/cloudflare/cloudflared"
  exit 1
fi

echo ""
echo "Step 1: Login to Cloudflare"
echo "This opens a browser. Select the Cloudflare account and domain you want to use."
cloudflared tunnel login

echo ""
echo "Step 2: Create tunnel"
read -r -p "Tunnel name (default: gasbot-demo): " TUNNEL_NAME
TUNNEL_NAME=${TUNNEL_NAME:-gasbot-demo}

cloudflared tunnel create "$TUNNEL_NAME"

TUNNEL_ID=$(cloudflared tunnel list | awk -v name="$TUNNEL_NAME" '$2 == name { print $1; exit }')
if [[ -z "$TUNNEL_ID" ]]; then
  echo "Could not find tunnel ID for $TUNNEL_NAME."
  exit 1
fi

echo "Tunnel ID: $TUNNEL_ID"

echo ""
echo "Step 3: Create DNS route"
read -r -p "Your Cloudflare domain (for example, example.com): " DOMAIN
read -r -p "Subdomain for Ollama (default: ollama-demo): " SUBDOMAIN
SUBDOMAIN=${SUBDOMAIN:-ollama-demo}
FULL_HOSTNAME="${SUBDOMAIN}.${DOMAIN}"

cloudflared tunnel route dns "$TUNNEL_NAME" "$FULL_HOSTNAME"

echo ""
echo "Step 4: Write Cloudflare config"
CONFIG_PATH="$HOME/.cloudflared/config.yml"
mkdir -p "$HOME/.cloudflared"

cat >"$CONFIG_PATH" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: $FULL_HOSTNAME
    service: http://localhost:11434
    originRequest:
      noTLSVerify: true
      httpHostHeader: localhost:11434
  - service: http_status:404
EOF

echo ""
echo "Config created at: $CONFIG_PATH"
echo "Public Ollama URL: https://$FULL_HOSTNAME"
echo ""
echo "Next steps:"
echo "1. Ensure Ollama is installed: brew install ollama"
echo "2. Start demo mode: ./scripts/start-local-demo.sh"
echo "3. Set production backend env vars:"
echo "   LLM_PROVIDER=ollama"
echo "   ENVIRONMENT=local-demo"
echo "   OLLAMA_BASE_URL=https://$FULL_HOSTNAME"
echo ""
echo "Setup complete."
