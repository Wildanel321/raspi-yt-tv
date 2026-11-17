#!/usr/bin/env bash
# ==============================================================================
# Pi Music - 3.5" TFT SPI LCD & XPT2046 Driver Downloader & Installer
# Supports Waveshare 3.5", MHS-35, Keystudio, and generic XPT2046 SPI displays.
# Safely backs up existing configuration before applying changes.
# ==============================================================================

set -e

# ANSI Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}    3.5\" TFT LCD & XPT2046 Driver Downloader / Setup  ${NC}"
echo -e "${CYAN}======================================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Please run this script with sudo:${NC} sudo bash scripts/setup_lcd_driver.sh"
    exit 1
fi

ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. Detect Boot Config File Location
BOOT_CONFIG=""
OVERLAYS_DIR=""

if [ -f "/boot/firmware/config.txt" ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
    OVERLAYS_DIR="/boot/firmware/overlays"
elif [ -f "/boot/config.txt" ]; then
    BOOT_CONFIG="/boot/config.txt"
    OVERLAYS_DIR="/boot/overlays"
else
    echo -e "${RED}[ERROR] Could not find /boot/config.txt or /boot/firmware/config.txt!${NC}"
    exit 1
fi

echo -e "[INFO] Detected boot config: ${GREEN}$BOOT_CONFIG${NC}"

# Check if driver is already configured
if grep -E -q "dtoverlay=(waveshare35a|waveshare35b|tft35a|mhs35|piscreen)" "$BOOT_CONFIG"; then
    echo -e "${YELLOW}[NOTE] A 3.5\" TFT overlay is already active in $BOOT_CONFIG:${NC}"
    grep -E "dtoverlay=(waveshare35a|waveshare35b|tft35a|mhs35|piscreen)" "$BOOT_CONFIG"
    read -p "Do you want to reconfigure or change the driver? [y/N]: " -r reconf
    if [[ ! "$reconf" =~ ^[Yy]$ ]]; then
        echo -e "[INFO] Existing driver configuration kept. Exiting."
        exit 0
    fi
fi

# 2. Select LCD Model
echo -e "\n${YELLOW}Pilih model LCD TFT 3.5 inci Anda:${NC}"
echo -e "  1) Waveshare 3.5\" (A/B) / Spotpear 3.5\" (waveshare35a)"
echo -e "  2) MHS-35 / Keystudio 3.5\" (mhs35 / tft35a)"
echo -e "  3) Download & Pasang Driver Lengkap via GoodTFT/LCD-show (Git)"
echo -e "  4) Batal / Keluar"

read -p "Masukkan pilihan [1-4]: " -r choice

case "$choice" in
    1)
        DRIVER_NAME="waveshare35a"
        ROTATE=90
        USE_GIT=false
        ;;
    2)
        DRIVER_NAME="mhs35"
        ROTATE=90
        USE_GIT=false
        ;;
    3)
        USE_GIT=true
        ;;
    *)
        echo -e "[INFO] Batal memasang driver LCD."
        exit 0
        ;;
esac

# 3. Create Backup of config.txt
BACKUP_FILE="${BOOT_CONFIG}.bak-$(date +%Y%m%d%H%M%S)"
echo -e "\n[INFO] Membuat cadangan konfigurasi: ${GREEN}$BACKUP_FILE${NC}"
cp "$BOOT_CONFIG" "$BACKUP_FILE"

# 4. Method Execution
if [ "$USE_GIT" = true ]; then
    echo -e "\n${YELLOW}[Git Download] Mengunduh repository driver LCD-show...${NC}"
    TARGET_DIR="$USER_HOME/LCD-show"
    
    # Install git if missing
    if ! command -v git >/dev/null 2>&1; then
        apt-get update -y && apt-get install -y git
    fi

    if [ -d "$TARGET_DIR" ]; then
        echo -e "[INFO] Direktori $TARGET_DIR sudah ada, memperbarui..."
        cd "$TARGET_DIR" && git pull || true
    else
        echo -e "[INFO] Cloning https://github.com/goodtft/LCD-show.git..."
        sudo -u "$ACTUAL_USER" git clone --depth=1 https://github.com/goodtft/LCD-show.git "$TARGET_DIR"
    fi

    chmod -R 755 "$TARGET_DIR"
    echo -e "${GREEN}[OK] Repository LCD-show berhasil diunduh ke $TARGET_DIR.${NC}"

    echo -e "\n${YELLOW}Pilih skrip eksekusi LCD-show:${NC}"
    echo -e "  1) ./LCD35-show (Waveshare 3.5\" Type A/B)"
    echo -e "  2) ./MHS35-show (MHS 3.5\" High Speed)"
    echo -e "  3) ./MPI3501-show (Keystudio / MPI 3.5\")"
    read -p "Pilihan skrip [1-3]: " -r git_choice

    SCRIPT_NAME=""
    case "$git_choice" in
        1) SCRIPT_NAME="LCD35-show" ;;
        2) SCRIPT_NAME="MHS35-show" ;;
        3) SCRIPT_NAME="MPI3501-show" ;;
        *) SCRIPT_NAME="LCD35-show" ;;
    esac

    echo -e "\n${YELLOW}[PERINGATAN] Driver LCD-show akan mengonfigurasi display dan me-reboot Raspberry Pi.${NC}"
    read -p "Jalankan $SCRIPT_NAME sekarang? [Y/n]: " -r run_now
    if [[ ! "$run_now" =~ ^[Nn]$ ]]; then
        cd "$TARGET_DIR"
        exec bash "./$SCRIPT_NAME"
    else
        echo -e "[INFO] Anda dapat menjalankannya nanti dengan: cd $TARGET_DIR && sudo ./$SCRIPT_NAME"
        exit 0
    fi

else
    # Native Overlay & Calibration Setup
    echo -e "\n${YELLOW}[Native Setup] Mengonfigurasi Device Tree Overlay untuk $DRIVER_NAME...${NC}"

    # Ensure SPI is enabled
    if ! grep -q "^dtparam=spi=on" "$BOOT_CONFIG"; then
        echo "dtparam=spi=on" >> "$BOOT_CONFIG"
        echo -e "[OK] Ditambahkan: dtparam=spi=on"
    fi

    # Add dtoverlay if not already present
    OVERLAY_LINE="dtoverlay=$DRIVER_NAME:rotate=$ROTATE,speed=27000000,fps=30"
    if ! grep -q "dtoverlay=$DRIVER_NAME" "$BOOT_CONFIG"; then
        echo "" >> "$BOOT_CONFIG"
        echo "# Pi Music 3.5 inch TFT SPI LCD Overlay" >> "$BOOT_CONFIG"
        echo "$OVERLAY_LINE" >> "$BOOT_CONFIG"
        echo -e "${GREEN}[OK] Berhasil menambahkan $OVERLAY_LINE ke $BOOT_CONFIG${NC}"
    fi

    # 5. Configure XPT2046 Touchscreen Calibration File
    echo -e "\n[INFO] Mengonfigurasi kalibrasi touchscreen XPT2046..."
    mkdir -p /etc/X11/xorg.conf.d

    CALIB_FILE="/etc/X11/xorg.conf.d/99-calibration.conf"
    cat <<'EOF' > "$CALIB_FILE"
Section "InputClass"
        Identifier      "calibration"
        MatchProduct    "ADS7846 Touchscreen|XPT2046 Touchscreen"
        Option  "MinX"  "3936"
        Option  "MaxX"  "227"
        Option  "MinY"  "268"
        Option  "MaxY"  "3880"
        Option  "SwapXY" "1"
        Option  "InvertX" "1"
        Option  "InvertY" "0"
EndSection
EOF
    echo -e "${GREEN}[OK] File kalibrasi touchscreen tersimpan di $CALIB_FILE.${NC}"

    echo -e "\n${GREEN}======================================================${NC}"
    echo -e "${GREEN}   Konfigurasi Driver LCD 3.5\" Selesai!              ${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo -e "Pengaturan driver telah ditambahkan ke $BOOT_CONFIG."
    echo -e "Driver memerlukan reboot agar SPI framebuffer (/dev/fb1) aktif."
    echo -e "\nApakah Anda ingin me-reboot Raspberry Pi sekarang? [y/N]"
    read -r -t 15 reboot_now || reboot_now="n"
    if [[ "$reboot_now" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}[INFO] Me-reboot sistem sekarang...${NC}"
        reboot
    else
        echo -e "[INFO] Silakan reboot manual nanti dengan perintah: ${CYAN}sudo reboot${NC}"
    fi
fi
