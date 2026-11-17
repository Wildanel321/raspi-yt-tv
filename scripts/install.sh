#!/usr/bin/env bash
# ==============================================================================
# Pi Music - Automatic Installer
# Targeted for Raspberry Pi 3 (1GB RAM) running Raspberry Pi OS Lite (32-bit)
# With 3.5" SPI TFT LCD (480x320) & XPT2046 Touchscreen
# ==============================================================================

set -e

# ANSI Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}       Pi Music - Automated Installer               ${NC}"
echo -e "${CYAN}   Lightweight YouTube Music for Raspberry Pi 3       ${NC}"
echo -e "${CYAN}======================================================${NC}"

# 1. User & Directory Resolution
ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "[INFO] Target User: ${GREEN}$ACTUAL_USER${NC}"
echo -e "[INFO] Installation Directory: ${GREEN}$SCRIPT_DIR${NC}"

# Check for root / sudo privileges
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Please run this installer with sudo:${NC} sudo bash scripts/install.sh"
    exit 1
fi

# 2. Display Configuration Check (Native HDMI Output)
echo -e "\n${YELLOW}[Step 1/5] Configuring Display for Native HDMI Output...${NC}"
# Clean any leftover SPI LCD configs to ensure clean HDMI rendering
rm -f /etc/X11/xorg.conf.d/99-fbdev.conf 2>/dev/null || true
echo -e "${GREEN}[OK] Native HDMI output configured (/dev/fb0 with VC4 KMS driver).${NC}"

# 3. Install System Dependencies
echo -e "\n${YELLOW}[Step 2/5] Installing Required System Packages...${NC}"
# Use ForceIPv4 and retries to prevent IPv6 unreachable and timeout errors on Raspberry Pi
APT_OPTS=(-o "Acquire::ForceIPv4=true" -o "Acquire::Retries=3")
apt-get "${APT_OPTS[@]}" update -y

PACKAGES=(
    python3
    python3-pip
    python3-venv
    python3-pygame
    mpv
    alsa-utils
    bluez
    bluez-tools
    bluez-alsa-utils
    network-manager
    libsdl2-2.0-0
    xinit
    xserver-xorg
    xserver-xorg-input-libinput
    xserver-xorg-input-evdev
    x11-xserver-utils
    xinput
    xinput-calibrator
    git
    curl
    netsurf-gtk
)

echo -e "[INFO] Installing: ${PACKAGES[*]}"
apt-get "${APT_OPTS[@]}" install -y --fix-missing --no-install-recommends "${PACKAGES[@]}"

# 4. Audio & Bluetooth Configuration
echo -e "\n${YELLOW}[Step 3/5] Configuring Audio Output (3.5mm Jack & Bluetooth)...${NC}"
# Route audio to 3.5mm jack by default
amixer cset numid=3 1 >/dev/null 2>&1 || true
# Unmute and set default volume to 75%
amixer sset 'PCM' 75% unmute >/dev/null 2>&1 || true
amixer sset 'Headphones' 75% unmute >/dev/null 2>&1 || true

# Add user to required groups (audio, video, input, bluetooth)
usermod -a -G audio,video,input,bluetooth "$ACTUAL_USER" || true

# Enable and start Bluetooth services
systemctl enable bluetooth.service >/dev/null 2>&1 || true
systemctl start bluetooth.service >/dev/null 2>&1 || true
if systemctl list-unit-files | grep -q "bluealsa"; then
    systemctl enable bluealsa.service >/dev/null 2>&1 || true
    systemctl start bluealsa.service >/dev/null 2>&1 || true
fi

echo -e "${GREEN}[OK] Audio configured for 3.5mm analog jack and Bluetooth.${NC}"

# 5. Python Environment & Dependencies
echo -e "\n${YELLOW}[Step 4/5] Setting up Python Dependencies & yt-dlp...${NC}"
# Create dedicated virtual environment to comply with PEP 668 on Debian Bookworm
VENV_DIR="$SCRIPT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "[INFO] Creating Python virtual environment at $VENV_DIR..."
    sudo -u "$ACTUAL_USER" python3 -m venv --system-site-packages "$VENV_DIR"
fi

echo -e "[INFO] Installing/Updating Python packages via pip..."
sudo -u "$ACTUAL_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$ACTUAL_USER" "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
# Ensure yt-dlp is latest version for YouTube extraction compatibility
sudo -u "$ACTUAL_USER" "$VENV_DIR/bin/pip" install --upgrade yt-dlp

chmod +x "$SCRIPT_DIR/scripts/start.sh"
chmod +x "$SCRIPT_DIR/main.py"

# 6. Configure X11 Permissions & LCD Framebuffer for Systemd
# 6. Configure X11 Permissions for Systemd
echo -e "\n${YELLOW}[Step 5/5] Configuring X11 Permissions for HDMI Service...${NC}"
# Allow non-console users to run X server from systemd service
if [ -d "/etc/X11" ]; then
    cat << 'EOF' > /etc/X11/Xwrapper.config
allowed_users=anybody
needs_root_rights=yes
EOF
fi

# Clean any stale SPI fbdev configuration so Xorg uses the native HDMI GPU driver
rm -f /etc/X11/xorg.conf.d/99-fbdev.conf 2>/dev/null || true

# 7. Install & Configure Systemd Service
echo -e "\n${YELLOW}[Step 5/5] Configuring Systemd Autostart Service...${NC}"
SERVICE_FILE="/etc/systemd/system/pi-music.service"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Pi Music - YouTube Music Player
After=network-online.target sound.target
Wants=network-online.target sound.target

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u "$ACTUAL_USER")
ExecStart=/bin/bash $SCRIPT_DIR/scripts/start.sh
Restart=on-failure
RestartSec=5s
KillMode=mixed
TimeoutStopSec=10s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pi-music.service
echo -e "${GREEN}[OK] pi-music.service created and enabled for autostart.${NC}"

# Ensure cache directories exist for user
CACHE_DIR="$USER_HOME/.cache/pimusic"
CONFIG_DIR="$USER_HOME/.config/pimusic"
sudo -u "$ACTUAL_USER" mkdir -p "$CACHE_DIR/thumbnails" "$CONFIG_DIR"

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}       Installation Complete Successfully!           ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "You can manage Pi Music with the following commands:"
echo -e "  - Start service:   ${CYAN}sudo systemctl start pi-music${NC}"
echo -e "  - Stop service:    ${CYAN}sudo systemctl stop pi-music${NC}"
echo -e "  - View live logs:  ${CYAN}journalctl -u pi-music -f${NC}"
echo -e "  - Manual test run: ${CYAN}bash scripts/start.sh${NC}"
echo -e "\nWould you like to start Pi Music right now? (y/N)"
read -r -t 10 response || response="n"
if [[ "$response" =~ ^[Yy]$ ]]; then
    systemctl start pi-music.service
    echo -e "${GREEN}[OK] Pi Music service started!${NC}"
fi
