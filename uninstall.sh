#!/usr/bin/env bash
set -euo pipefail
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
[[ -n "${TARGET_HOME:-}" && -d "$TARGET_HOME" ]] || { echo "Home user tidak ditemukan"; exit 1; }

APP_DIR="$TARGET_HOME/.local/bin/raspi-yt-tv"
AUTOSTART="$TARGET_HOME/.config/labwc/autostart"
if [[ -f "$AUTOSTART" ]]; then
  tmp="$(mktemp)"
  awk '
    /# raspi-yt-tv autostart/ { skip=1; next }
    skip && /start-youtube\.sh/ { skip=0; next }
    { if (!skip) print }
  ' "$AUTOSTART" > "$tmp"
  cat "$tmp" > "$AUTOSTART"
  rm -f "$tmp"
fi

rm -rf "$APP_DIR"
rm -f "$TARGET_HOME/.local/share/applications/youtube-tv.desktop" \
      "$TARGET_HOME/.local/share/applications/wifi-selector.desktop"
echo "Aplikasi raspi-yt-tv dihapus. Profil Wi-Fi dan konfigurasi lain tetap dipertahankan."
