#!/usr/bin/env bash
# ==============================================================================
# Pi Music - Startup Script
# Automatically detects HDMI display vs Headless mode, configures audio,
# and launches Pi Music with built-in Web Remote Control (port 8080).
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

WEB_PORT="${PIMUSIC_WEB_PORT:-8080}"
FORCE_HEADLESS=false

for arg in "$@"; do
    if [ "$arg" = "--headless" ]; then
        FORCE_HEADLESS=true
    fi
done

# 1. Python Environment Detection
if [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    echo "[ERROR] Python 3 not found!"
    exit 1
fi

# 2. Audio Output Default Route (3.5mm jack / ALSA)
if command -v amixer >/dev/null 2>&1; then
    amixer sset 'PCM' 80% unmute >/dev/null 2>&1 || true
    amixer sset 'Headphones' 80% unmute >/dev/null 2>&1 || true
fi

# 3. Detect whether an HDMI monitor is connected
HDMI_CONNECTED=false
if [ "$FORCE_HEADLESS" = false ]; then
    for status_file in /sys/class/drm/card*-HDMI-*/status; do
        if [ -r "$status_file" ]; then
            if grep -qx "connected" "$status_file" 2>/dev/null; then
                HDMI_CONNECTED=true
                break
            fi
        fi
    done
fi

# 4. Headless Launch (no HDMI monitor detected or --headless requested)
if [ "$FORCE_HEADLESS" = true ] || [ "$HDMI_CONNECTED" = false ]; then
    echo "[INFO] No HDMI display detected (or headless mode requested)."
    echo "[INFO] Starting Pi Music in Headless Web Mode on port ${WEB_PORT}..."
    exec "$PYTHON_CMD" main.py --headless --web-port "$WEB_PORT"
fi

# 5. HDMI GUI + Web Remote Launch
export FRAMEBUFFER="/dev/fb0"
echo "[INFO] HDMI display detected. Starting GUI + Web Remote (port ${WEB_PORT})..."

X_RUNNING=false
if [ -n "$DISPLAY" ]; then
    if command -v xset >/dev/null 2>&1 && xset q >/dev/null 2>&1; then
        X_RUNNING=true
    elif [ -e "/tmp/.X11-unix/X${DISPLAY#*:}" ]; then
        X_RUNNING=true
    fi
fi

if [ "$X_RUNNING" = true ]; then
    echo "[INFO] Using existing X11 display ($DISPLAY)..."
    exec "$PYTHON_CMD" main.py --fullscreen --web-port "$WEB_PORT"
elif command -v xinit >/dev/null 2>&1; then
    echo "[INFO] Starting lightweight X11 wrapper on HDMI display..."
    unset DISPLAY
    xinit "$PYTHON_CMD" main.py --fullscreen --web-port "$WEB_PORT" -- :0 -s 0 dpms
    EXIT_CODE=$?
    if [ "$EXIT_CODE" -ne 0 ]; then
        echo "[WARN] X11 exited with code $EXIT_CODE. Falling back to Headless Web Mode..."
        exec "$PYTHON_CMD" main.py --headless --web-port "$WEB_PORT"
    fi
    exit 0
else
    echo "[INFO] Starting Pi Music directly (auto-falls back to Headless if no display)..."
    exec "$PYTHON_CMD" main.py --fullscreen --web-port "$WEB_PORT"
fi
