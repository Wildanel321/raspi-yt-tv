#!/usr/bin/env bash
# ==============================================================================
# Pi Music - Uninstaller Script
# Safely stops service, removes autostart, and optionally clears caches.
# ==============================================================================

set -e

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${RED}======================================================${NC}"
echo -e "${RED}         Pi Music - Uninstaller                     ${NC}"
echo -e "${RED}======================================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Please run with sudo:${NC} sudo bash scripts/uninstall.sh"
    exit 1
fi

ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. Stop and Disable Systemd Service
echo -e "\n${YELLOW}[1/3] Stopping and removing systemd service...${NC}"
if systemctl is-active --quiet pi-music.service; then
    systemctl stop pi-music.service || true
fi

if systemctl is-enabled --quiet pi-music.service 2>/dev/null; then
    systemctl disable pi-music.service || true
fi

if [ -f "/etc/systemd/system/pi-music.service" ]; then
    rm -f "/etc/systemd/system/pi-music.service"
    systemctl daemon-reload
    systemctl reset-failed || true
    echo -e "${GREEN}[OK] pi-music.service removed.${NC}"
fi

# 2. Clean Virtual Environment
echo -e "\n${YELLOW}[2/3] Cleaning Python virtual environment...${NC}"
if [ -d "$SCRIPT_DIR/venv" ]; then
    rm -rf "$SCRIPT_DIR/venv"
    echo -e "${GREEN}[OK] Removed project venv.${NC}"
fi

# 3. Optional Cache and Configuration Removal
echo -e "\n${YELLOW}[3/3] User Data & Cache Cleanup...${NC}"
CACHE_DIR="$USER_HOME/.cache/pimusic"
CONFIG_DIR="$USER_HOME/.config/pimusic"

read -p "Do you want to delete cached thumbnails and saved playlists ($CACHE_DIR, $CONFIG_DIR)? [y/N]: " -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    rm -rf "$CACHE_DIR" "$CONFIG_DIR"
    echo -e "${GREEN}[OK] Cache and playlist data removed.${NC}"
else
    echo -e "[INFO] Cache and playlist configurations preserved."
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}       Pi Music uninstalled successfully.            ${NC}"
echo -e "${GREEN}======================================================${NC}"
