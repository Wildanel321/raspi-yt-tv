#!/usr/bin/env bash
# ==============================================================================
# Pi Music - Startup Script
# Automatically detects HDMI display vs Headless mode, configures audio/BT,
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

# 2. Unblock Bluetooth radio if soft-blocked by rfkill
if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock bluetooth >/dev/null 2>&1 || true
fi

# 3. Audio Output Hardware Gain (0dB clean line-level on Pi 3.5mm jack; MPV controls volume)
if command -v amixer >/dev/null 2>&1; then
    amixer -c 0 sset 'PCM' 96% unmute >/dev/null 2>&1 || true
    amixer sset 'PCM' 96% unmute >/dev/null 2>&1 || true
    amixer sset 'Headphones' 96% unmute >/dev/null 2>&1 || true
fi

# 4. Detect whether an HDMI monitor is connected
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

# 5. Headless Launch (no HDMI monitor detected or --headless requested)
if [ "$FORCE_HEADLESS" = true ] || [ "$HDMI_CONNECTED" = false ]; then
    echo "[INFO] No HDMI display detected (or headless mode requested)."
    echo "[INFO] Starting Pi Music in Headless Web Mode on port ${WEB_PORT}..."
    exec "$PYTHON_CMD" main.py --headless --web-port "$WEB_PORT"
fi

# 6. HDMI GUI + Web Remote Launch
export FRAMEBUFFER="/dev/fb0"
echo "[INFO] HDMI display detected. Starting GUI + Web Remote (port ${WEB_PORT})..."

X_RUNNING=false
if [ -n "$DISPLAY" ] && command -v xset >/dev/null 2>&1 && xset q >/dev/null 2>&1; then
    X_RUNNING=true
fi

if [ "$X_RUNNING" = true ]; then
    echo "[INFO] Using existing X11 display ($DISPLAY)..."
    exec "$PYTHON_CMD" main.py --fullscreen --web-port "$WEB_PORT"
elif command -v xinit >/dev/null 2>&1; then
    echo "[INFO] Starting lightweight X11 wrapper on HDMI display (1280x720)..."
    unset DISPLAY
    # Clean stale X0 lock/socket left by previous SIGKILL if Xorg is not running
    if ! pgrep -x Xorg >/dev/null 2>&1; then
        rm -f /tmp/.X0-lock /tmp/.X11-unix/X0 2>/dev/null || true
    fi
    X_CLIENT_SCRIPT="/tmp/pimusic-xclient.sh"
    cat > "$X_CLIENT_SCRIPT" <<EOF
#!/usr/bin/env bash
xset s off -dpms s noblank 2>/dev/null || true
if command -v xrandr >/dev/null 2>&1; then
    xrandr --output HDMI-1 --mode 1280x720 2>/dev/null || xrandr --output HDMI-1 --auto 2>/dev/null || true
fi
exec "$PYTHON_CMD" "$SCRIPT_DIR/main.py" --fullscreen --web-port "$WEB_PORT"
EOF
    chmod +x "$X_CLIENT_SCRIPT"
    xinit "$X_CLIENT_SCRIPT" -- :0 -s 0 dpms
    EXIT_CODE=$?
    if [ "$EXIT_CODE" -ne 0 ]; then
        echo "[WARN] X11 exited with code $EXIT_CODE. Falling back to Headless Web Mode..."
        exec "$PYTHON_CMD" main.py --headless --web-port "$WEB_PORT"
    fi
    exit 0
else
    echo "[INFO] Starting Pi Music directly on HDMI KMS/framebuffer..."
    exec "$PYTHON_CMD" main.py --fullscreen --web-port "$WEB_PORT"
fi
