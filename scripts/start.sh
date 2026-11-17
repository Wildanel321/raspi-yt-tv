#!/usr/bin/env bash
# ==============================================================================
# Pi Music - Startup Script
# Automatically configures display, audio environment, and launches Pi Music.
# Configured for native HDMI Output (TV / Monitor / Car Head Unit).
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# 1. Python Environment Detection
if [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    echo "[ERROR] Python 3 not found!"
    exit 1
fi

# 2. Native HDMI Display Configuration
export FRAMEBUFFER="/dev/fb0"
# Wake up and force HDMI output if sleeping
echo on > /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null || true
echo "[INFO] Using native HDMI display output (/dev/fb0)"

# 3. Audio Output Default Route
# Unmute HDMI audio and 3.5mm jack
if command -v amixer >/dev/null 2>&1; then
    amixer sset 'PCM' 80% unmute >/dev/null 2>&1 || true
    amixer sset 'Headphones' 80% unmute >/dev/null 2>&1 || true
fi

# 4. Display Server Selection (Lightweight X11 for HDMI)
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
    exec "$PYTHON_CMD" main.py --fullscreen
elif command -v xinit >/dev/null 2>&1; then
    echo "[INFO] Starting lightweight X11 wrapper on HDMI display..."
    unset DISPLAY
    exec xinit "$PYTHON_CMD" main.py --fullscreen -- :0 -s 0 dpms
else
    echo "[INFO] Starting Pi Music directly on HDMI framebuffer..."
    exec "$PYTHON_CMD" main.py --fullscreen
fi
