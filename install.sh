#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [[ -z "${TARGET_HOME:-}" || ! -d "$TARGET_HOME" ]]; then
  echo "Tidak bisa menentukan home user: $TARGET_USER" >&2
  exit 1
fi

echo "Target user: $TARGET_USER"
echo "Memeriksa dependensi..."
if ! command -v apt-get >/dev/null 2>&1; then
  echo "Installer ini ditujukan untuk Raspberry Pi OS berbasis Debian." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y chromium zenity curl network-manager

if ! systemctl is-active --quiet NetworkManager; then
  echo "NetworkManager belum aktif. Mencoba mengaktifkannya..."
  sudo systemctl enable --now NetworkManager
fi

APP_DIR="$TARGET_HOME/.local/bin/raspi-yt-tv"
CONFIG_DIR="$TARGET_HOME/.config/raspi-yt-tv"
APP_MENU="$TARGET_HOME/.local/share/applications"
LABWC_DIR="$TARGET_HOME/.config/labwc"
mkdir -p "$APP_DIR" "$CONFIG_DIR" "$APP_MENU" "$LABWC_DIR"

install -m 755 "$SCRIPT_DIR/bin/"*.sh "$APP_DIR/"
cat > "$CONFIG_DIR/config" <<'EOF'
YOUTUBE_URL="https://www.youtube.com/"
EOF

# Simpan autostart lama sebelum menambahkan satu baris milik aplikasi ini.
AUTOSTART="$LABWC_DIR/autostart"
touch "$AUTOSTART"
if ! grep -Fq '# raspi-yt-tv autostart' "$AUTOSTART"; then
  cp -n "$AUTOSTART" "$AUTOSTART.before-raspi-yt-tv" 2>/dev/null || true
  cat >> "$AUTOSTART" <<EOF

# raspi-yt-tv autostart
"$APP_DIR/start-youtube.sh" &
EOF
fi

sed "s|@APP_DIR@|$APP_DIR|g" "$SCRIPT_DIR/applications/youtube-tv.desktop" > "$APP_MENU/youtube-tv.desktop"
sed "s|@APP_DIR@|$APP_DIR|g" "$SCRIPT_DIR/applications/wifi-selector.desktop" > "$APP_MENU/wifi-selector.desktop"
chmod 644 "$APP_MENU/"*.desktop

chown -R "$TARGET_USER":"$(id -gn "$TARGET_USER")" "$TARGET_HOME/.local/bin/raspi-yt-tv" "$CONFIG_DIR" "$APP_MENU" "$LABWC_DIR"
echo
echo "Instalasi selesai. Logout/login atau reboot untuk menjalankan autostart."
echo "Shortcut tersedia di menu aplikasi: YouTube TV dan Wi-Fi Selector."
