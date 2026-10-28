#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y python3 curl ca-certificates pkg-config build-essential libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev libxdo-dev file wget git
if ! command -v cargo >/dev/null 2>&1; then
  echo 'Instala Rust con: https://rustup.rs/ (recomendado rustup)'
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo 'Instala Node.js LTS 22 o superior y vuelve a ejecutar.'
  exit 1
fi
cd "$(dirname "$0")/../app" && npm install
