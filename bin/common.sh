#!/usr/bin/env bash
set -u
APP_CONFIG="${HOME}/.config/raspi-yt-tv/config"
YOUTUBE_URL="https://www.youtube.com/"
if [[ -f "$APP_CONFIG" ]]; then
  # File config lokal milik user.
  source "$APP_CONFIG"
fi

notify_error() {
  zenity --error --title="raspi-yt-tv" --text="$1" 2>/dev/null || \
    printf '%s\n' "$1" >&2
}

has_internet() {
  local code
  code="$(curl -L -sS --max-time 8 -o /dev/null -w '%{http_code}' \
    https://connectivitycheck.gstatic.com/generate_204 2>/dev/null || true)"
  [[ "$code" == "204" ]]
}

find_chromium() {
  command -v chromium || command -v chromium-browser || command -v chromium-gtk
}
