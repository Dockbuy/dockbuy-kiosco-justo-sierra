#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 api/server.py &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
cd app
npm run tauri:dev
