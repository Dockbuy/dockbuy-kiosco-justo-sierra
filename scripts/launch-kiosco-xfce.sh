#!/usr/bin/env bash
# Arranque desde la sesión gráfica XFCE; no reinicia Tauri si se cierra con Alt+F4.
set -uo pipefail
HOME_DIR="${HOME:?}"
PROJECT="${HOME_DIR}/repositorio/justo-sierra-kiosco"
LOG_DIR="${HOME_DIR}/.local/state/justo-sierra-kiosco"
mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/autoinicio.log" 2>&1
printf '\n==== Inicio %s ====\n' "$(date -Is)"
export PATH="$HOME_DIR/.cargo/bin:$HOME_DIR/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PARK_DEVICE="${PARK_DEVICE:-/dev/usb/lp0}"
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo 'No hay sesión gráfica disponible; se cancela inicio.'
  exit 1
fi
if [[ ! -f "$PROJECT/scripts/start-demo.sh" ]]; then
  echo "No se encuentra $PROJECT/scripts/start-demo.sh"
  exit 1
fi
# Evita dos instancias si se inicia manualmente el lanzador varias veces.
exec 9>"$LOG_DIR/autoinicio.lock"
if ! flock -n 9; then
  echo 'Ya hay una instancia iniciada mediante este lanzador.'
  exit 0
fi
cd "$PROJECT"
# Esperar a que termine de cargar el escritorio y dispositivos.
sleep 5
bash scripts/start-demo.sh
status=$?
printf '==== Kiosco cerrado (%s), estado %s ====\n' "$(date -Is)" "$status"
exit "$status"
