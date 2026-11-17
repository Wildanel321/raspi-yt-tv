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

# 2. Inspect Existing Display and Touchscreen Configuration
echo -e "\n${YELLOW}[Step 1/5] Checking Display & Touchscreen Configuration...${NC}"
BOOT_CONFIG=""
if [ -f "/boot/firmware/config.txt" ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
elif [ -f "/boot/config.txt" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

LCD_DRIVER_FOUND=false

if [ -n "$BOOT_CONFIG" ]; then
    echo -e "[INFO] Checking $BOOT_CONFIG for TFT configuration..."

    # Detect configured TFT overlays
    if grep -E -q '^[[:space:]]*dtoverlay=(fbtft|waveshare35a|waveshare35b|tft35a|mhs35|piscreen)' "$BOOT_CONFIG"; then
        echo -e "${GREEN}[OK] TFT overlay configuration detected.${NC}"
        LCD_DRIVER_FOUND=true
    fi
else
    echo -e "${YELLOW}[WARNING] Could not locate /boot/config.txt. Skipping config check.${NC}"
fi

# Detect active framebuffer, including manually configured ILI9486
if [ -e "/dev/fb1" ] || [ -e "/sys/class/graphics/fb1" ]; then
    echo -e "${GREEN}[OK] LCD framebuffer /dev/fb1 detected.${NC}"
    LCD_DRIVER_FOUND=true
fi

if [ "$LCD_DRIVER_FOUND" = false ]; then
    echo -e "${YELLOW}[NOTE] LCD TFT 3.5 inch belum terdeteksi.${NC}"
    read -r -t 15 -p "Install LCD driver sekarang? [y/N] " install_lcd || install_lcd="n"

    if [[ "$install_lcd" =~ ^[Yy]$ ]]; then
        chmod +x "$SCRIPT_DIR/scripts/setup_lcd_driver.sh"
        bash "$SCRIPT_DIR/scripts/setup_lcd_driver.sh"
        echo -e "${GREEN}[OK] LCD driver setup selesai.${NC}"
    else
        echo -e "[INFO] Melewati instalasi driver LCD."
    fi
fi

# Detect XPT2046 touchscreen kernel driver
if grep -q "ADS7846 Touchscreen" /proc/bus/input/devices 2>/dev/null; then
    echo -e "${GREEN}[OK] XPT2046 / ADS7846 touchscreen detected.${NC}"
elif [ -d "/sys/bus/spi/drivers/ads7846" ]; then
    echo -e "${GREEN}[OK] ADS7846 kernel driver available.${NC}"
else
    echo -e "${YELLOW}[NOTE] Touchscreen belum terdeteksi.${NC}"
fi

# Check XPT2046 touchscreen calibration files
if [ -f "/etc/X11/xorg.conf.d/99-calibration.conf" ]; then
    echo -e "${GREEN}[OK] XPT2046 touchscreen calibration file detected in /etc/X11/xorg.conf.d/99-calibration.conf${NC}"
else
    echo -e "[INFO] Touchscreen will use default evdev/libinput calibration."
fi

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
    network-manager
    libsdl2-2.0-0
    xinit
    xserver-xorg
    xserver-xorg-input-libinput
    xserver-xorg-input-evdev
    x11-xserver-utils
    git
    curl
    netsurf-gtk
)

echo -e "[INFO] Installing: ${PACKAGES[*]}"
apt-get "${APT_OPTS[@]}" install -y --fix-missing --no-install-recommends "${PACKAGES[@]}"

# 4. Audio Configuration (3.5mm Headphone Jack)
echo -e "\n${YELLOW}[Step 3/5] Configuring Audio Output (3.5mm Jack)...${NC}"
# Route audio to 3.5mm jack
amixer cset numid=3 1 >/dev/null 2>&1 || true
# Unmute and set default volume to 75%
amixer sset 'PCM' 75% unmute >/dev/null 2>&1 || true
amixer sset 'Headphones' 75% unmute >/dev/null 2>&1 || true
echo -e "${GREEN}[OK] Audio configured for 3.5mm analog jack.${NC}"

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

# 6. Install & Configure Systemd Service
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
Environment=DISPLAY=:0
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
