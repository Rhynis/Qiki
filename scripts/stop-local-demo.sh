#!/usr/bin/env bash

set -euo pipefail

pkill cloudflared
echo "Cloudflare Tunnel stopped."

# Uncomment this if you also want to stop the local Ollama server.
# pkill ollama
