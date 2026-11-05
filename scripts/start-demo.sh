#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Faltan las dependencias Python. Ejecuta bash scripts/install-debian13.sh una vez.'
  exit 1
fi
.venv/bin/python api/server.py &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
cd app
npm run tauri:dev
