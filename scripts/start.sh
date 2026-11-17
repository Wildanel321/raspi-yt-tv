#!/usr/bin/env bash
# ==============================================================================
# Pi Music - Startup Script
# Automatically configures display, touchscreen environment, and launches Pi Music.
# Compatible with Raspberry Pi OS Lite (32-bit) with 3.5" TFT SPI LCD (480x320).
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

# 2. Hardware Display & Touchscreen Auto-Detection
# Most 3.5" SPI LCDs (Waveshare, Keystudio, MHS35) map to /dev/fb1
if [ -e "/dev/fb1" ]; then
    export FRAMEBUFFER="/dev/fb1"
    export SDL_FBDEV="/dev/fb1"
    echo "[INFO] Detected SPI TFT LCD at /dev/fb1"
elif [ -e "/dev/fb0" ]; then
    export FRAMEBUFFER="/dev/fb0"
    export SDL_FBDEV="/dev/fb0"
    echo "[INFO] Using default display at /dev/fb0"
fi

# Detect XPT2046 / ADS7846 Touchscreen input event device
TOUCH_DEV=""
for dev in /dev/input/event*; do
    if [ -e "$dev" ]; then
        DEV_NAME=$(udevadm info --query=property --name="$dev" 2>/dev/null | grep "ID_INPUT_TOUCHSCREEN=1" || true)
        if [ -n "$DEV_NAME" ]; then
            TOUCH_DEV="$dev"
            break
        fi
    fi
done

if [ -n "$TOUCH_DEV" ]; then
    export SDL_MOUSEDRV="TSLIB"
    export SDL_MOUSEDEV="$TOUCH_DEV"
    export TSLIB_TSDEVICE="$TOUCH_DEV"
    echo "[INFO] Detected touchscreen device at $TOUCH_DEV"
fi

# 3. Audio Output Default Route (3.5mm Headphone Jack)
# bcm2835 headphone jack numid=3 1 (1 = Jack, 2 = HDMI, 0 = Auto)
if command -v amixer >/dev/null 2>&1; then
    amixer cset numid=3 1 >/dev/null 2>&1 || true
fi

# 4. Display Server Selection (Lightweight X11 vs Direct Framebuffer)
# Verify if an X server is actually responding on $DISPLAY
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
    exec "$PYTHON_CMD" main.py --fullscreen --no-cursor
elif command -v xinit >/dev/null 2>&1; then
    echo "[INFO] Starting lightweight X11 wrapper on TFT display..."
    unset DISPLAY
    exec xinit "$PYTHON_CMD" main.py --fullscreen --no-cursor -- :0 -nocursor -s 0 dpms
else
    echo "[INFO] Starting Pi Music directly on framebuffer..."
    exec "$PYTHON_CMD" main.py --fullscreen --no-cursor
fi
