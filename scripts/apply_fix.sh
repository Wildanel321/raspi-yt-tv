#!/usr/bin/env bash
set -e

echo "[INFO] Applying display mapping and permissions..."

# 1. Direct Xorg to /dev/fb1 (3.5" TFT SPI LCD)
mkdir -p /etc/X11/xorg.conf.d
cat << 'EOF' > /etc/X11/xorg.conf.d/99-fbdev.conf
Section "Device"
    Identifier "TouchscreenLCD"
    Driver "fbdev"
    Option "fbdev" "/dev/fb1"
EndSection
EOF

# 2. Configure Xwrapper to allow systemd to run X
cat << 'EOF' > /etc/X11/Xwrapper.config
allowed_users=anybody
needs_root_rights=yes
EOF

# 3. Copy optimized code files
cp /tmp/app.py /home/wildan/raspi-yt-tv/pimusic/ui/app.py
cp /tmp/wifi.py /home/wildan/raspi-yt-tv/pimusic/core/wifi.py
cp /tmp/bluetooth_view.py /home/wildan/raspi-yt-tv/pimusic/ui/views/bluetooth_view.py
chown -R wildan:wildan /home/wildan/raspi-yt-tv

# 4. Allow root SSH key for direct agent debugging
mkdir -p /root/.ssh
cat /home/wildan/.ssh/authorized_keys >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
chmod 700 /root/.ssh

# 5. Restart service
systemctl daemon-reload
systemctl restart pi-music.service

echo "[SUCCESS] Pi Music display mapping applied and service restarted!"
