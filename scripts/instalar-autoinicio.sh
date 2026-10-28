#!/usr/bin/env bash
set -euo pipefail
PROJECT="${HOME}/repositorio/justo-sierra-kiosco"
SOURCE="$PROJECT/scripts/launch-kiosco-xfce.sh"
TARGET_DIR="${HOME}/.config/autostart"
TARGET="$TARGET_DIR/justo-sierra-kiosco.desktop"
[[ -f "$SOURCE" ]] || { echo "Falta: $SOURCE" >&2; exit 1; }
mkdir -p "$TARGET_DIR"
chmod +x "$SOURCE"
cat > "$TARGET" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Kiosco Justo Sierra
Comment=Iniciar kiosco al abrir sesion XFCE
Exec=$SOURCE
TryExec=$SOURCE
Terminal=false
X-GNOME-Autostart-enabled=true
Hidden=false
DESKTOP
printf 'Autoinicio instalado: %s\n' "$TARGET"
printf 'Reinicia el equipo para probarlo. Alt+F4 cierra Tauri sin reiniciarlo.\n'
