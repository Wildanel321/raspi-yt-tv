# Troubleshooting Guide - Pi Music

This guide covers common issues and resolutions when running **Pi Music** on a Raspberry Pi 3 with a 3.5" TFT SPI LCD (480×320) and XPT2046 touchscreen.

---

## 🔊 1. Audio Issues (No sound from 3.5mm Headphone Jack)

### Symptom: Song is playing in the UI, but no sound comes out of the 3.5mm jack.

#### Cause A: Raspberry Pi audio output routed to HDMI instead of the 3.5mm jack.
**Fix**: Force the ALSA driver to route output through the 3.5mm jack:
```bash
# Set output routing: 1 = 3.5mm Headphone Jack, 2 = HDMI, 0 = Auto
amixer cset numid=3 1
```

#### Cause B: ALSA hardware audio is disabled in `config.txt`.
**Fix**: Check your boot configuration file (`/boot/firmware/config.txt` or `/boot/config.txt`):
```ini
dtparam=audio=on
```
If missing, add it, save, and reboot.

#### Cause C: PCM / Headphone volume is muted or at 0%.
**Fix**: Open `alsamixer` in terminal:
```bash
alsamixer
```
- Press **F6** to select `bcm2835 Headphones`.
- Ensure the volume bar is green (press **M** if it shows `[MM]` for muted).
- Or run:
```bash
amixer sset 'PCM' 80% unmute
amixer sset 'Headphones' 80% unmute
```

#### Verification:
Test audio directly using a pure sine wave tone:
```bash
speaker-test -t sine -f 440 -c 2 -l 2
```

---

## 🖥️ 2. Display Issues (Blank Screen or Black Display)

### Symptom: Backlight turns on, but screen remains white or black.

#### Cause A: TFT SPI LCD driver overlay is not loaded.
**Fix**: Check if the secondary framebuffer `/dev/fb1` exists:
```bash
ls -l /dev/fb*
```
If only `/dev/fb0` exists, your SPI LCD driver is not loaded. Ensure your manufacturer driver (e.g. Waveshare35a, Keystudio, MHS-35) is enabled in `/boot/config.txt`:
```ini
# For Waveshare 3.5" TFT A:
dtoverlay=waveshare35a:rotate=90

# Or for generic TFT 35:
dtoverlay=tft35a:rotate=90
```

#### Cause B: Pygame rendering to the wrong framebuffer.
**Fix**: If running without X11, define the target framebuffer explicitly:
```bash
export FRAMEBUFFER=/dev/fb1
export SDL_FBDEV=/dev/fb1
```
*(Note: `scripts/start.sh` handles this auto-detection automatically).*

---

## 👆 3. Touchscreen Issues (XPT2046 Coordinates Inverted or Misaligned)

### Symptom: Tapping the screen registers touches in the opposite corner or axes are inverted.

#### Solution: Calibrate XPT2046 using X11 Libinput Calibration

1. Install `xinput-calibrator`:
   ```bash
   sudo apt-get install -y xinput-calibrator
   ```

2. Run calibrator inside the X session:
   ```bash
   xinput_calibrator
   ```

3. If touch is rotated 90 degrees or inverted, create or update `/etc/X11/xorg.conf.d/99-calibration.conf`:
   ```bash
   sudo mkdir -p /etc/X11/xorg.conf.d
   sudo nano /etc/X11/xorg.conf.d/99-calibration.conf
   ```

   Add the appropriate calibration matrix (example for Waveshare 3.5"):
   ```text
   Section "InputClass"
           Identifier      "calibration"
           MatchProduct    "ADS7846 Touchscreen"
           Option  "MinX"  "3936"
           Option  "MaxX"  "227"
           Option  "MinY"  "268"
           Option  "MaxY"  "3880"
           Option  "SwapXY" "1"
           Option  "InvertX" "1"
           Option  "InvertY" "0"
   EndSection
   ```

4. For modern `libinput`, set the TransformationMatrix in `/etc/X11/xorg.conf.d/40-libinput.conf`:
   ```text
   Section "InputClass"
           Identifier "libinput touchscreen catchall"
           MatchIsTouchscreen "on"
           MatchDevicePath "/dev/input/event*"
           Driver "libinput"
           Option "TransformationMatrix" "0 -1 1 1 0 0 0 0 1"
   EndSection
   ```

---

## 🌐 4. Wi-Fi Issues (NetworkManager)

### Symptom: Wi-Fi status shows "Disconnected" or "No Connection".

1. Ensure NetworkManager service is active:
   ```bash
   sudo systemctl status NetworkManager
   sudo systemctl enable --now NetworkManager
   ```

2. Verify that Wi-Fi interface (`wlan0`) is not blocked:
   ```bash
   rfkill unblock wifi
   rfkill unblock all
   ```

3. Manually scan Wi-Fi using `nmcli`:
   ```bash
   nmcli dev wifi list
   ```

4. Connect manually from terminal if needed:
   ```bash
   nmcli dev wifi connect "YOUR_SSID" password "YOUR_PASSWORD"
   ```

---

## 📺 5. YouTube Streaming Issues (`yt-dlp` & MPV)

### Symptom: Song hangs on `[Buffering...]` or search fails.

#### Cause A: Outdated `yt-dlp` version.
YouTube frequently updates its video player signatures. If `yt-dlp` is older than a few weeks, extraction might fail.

**Fix**: Update `yt-dlp` inside the Pi Music environment:
```bash
cd ~/raspi-yt-tv
sudo ./venv/bin/pip install --upgrade yt-dlp
```

#### Cause B: MPV IPC socket permission or stale socket.
**Fix**: Clear stale sockets and test MPV manually:
```bash
rm -f /tmp/mpv-pimusic.sock
mpv --idle=yes --input-ipc-server=/tmp/mpv-pimusic.sock --no-video
```

---

## ⚡ 6. High CPU or Temperature on Pi 3

### Check CPU Temperature:
```bash
vcgencmd measure_temp
```
- If temperature exceeds 80°C, the Pi 3 will automatically throttle CPU frequency.
- Ensure the Pi 3 has a small passive heatsink and adequate ventilation.
- **Pi Music** includes built-in dynamic framerate throttling: it automatically drops from 25 FPS to 12 FPS when idle, keeping CPU load minimal (~5-8%).

### Check Available Memory:
```bash
free -h
```
If available memory is low, make sure no browser processes (`chromium-browser`, `firefox`) are lingering:
```bash
pkill -f chromium || true
```

---

## 🔄 7. How to Restart or View Systemd Service Logs

```bash
# View live service logs with timestamps
journalctl -u pi-music.service -f

# Restart the service
sudo systemctl restart pi-music.service

# Check service status
sudo systemctl status pi-music.service
```
