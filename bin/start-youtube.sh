#!/usr/bin/env bash
set -u
source "$(dirname "$0")/common.sh"

CHROMIUM="$(find_chromium || true)"
if [[ -z "$CHROMIUM" ]]; then
  notify_error "Chromium tidak ditemukan. Jalankan: sudo apt install chromium"
  exit 1
fi

while ! has_internet; do
  choice="$(zenity --question --title="Koneksi internet" \
    --text="Internet belum terdeteksi.\n\nPilih Yes untuk memilih Wi-Fi, atau No untuk membuka halaman login captive portal / memeriksa koneksi." \
    --ok-label="Pilih Wi-Fi" --cancel-label="Lanjut cek portal" 2>/dev/null; echo $?)"
  if [[ "$choice" == "0" ]]; then
    "$HOME/.local/bin/raspi-yt-tv/wifi-selector.sh" || true
  else
    # Halaman HTTP biasa sering memicu redirect captive portal.
    "$CHROMIUM" --no-first-run --user-data-dir="$HOME/.cache/raspi-yt-tv-portal" \
      "http://neverssl.com" >/dev/null 2>&1 &
    browser_pid=$!
    zenity --info --title="Login Wi-Fi" \
      --text="Selesaikan login pada halaman yang terbuka.\nSetelah berhasil, tutup browser portal lalu tekan OK untuk cek internet." 2>/dev/null || true
    kill "$browser_pid" 2>/dev/null || true
  fi
done

# Beri jeda singkat agar DNS dan route stabil.
sleep 2
exec "$CHROMIUM" --kiosk --no-first-run --disable-infobars \
  --autoplay-policy=no-user-gesture-required \
  --user-data-dir="$HOME/.config/raspi-yt-tv/chromium-profile" \
  "$YOUTUBE_URL"
