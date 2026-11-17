# raspi-yt-tv

Launcher YouTube fullscreen untuk Raspberry Pi OS Desktop (32-bit/64-bit) dengan Labwc/Wayland dan NetworkManager.

## Fitur
- Memilih jaringan Wi-Fi dari daftar hasil scan.
- Menggunakan profil Wi-Fi tersimpan, atau meminta password Wi-Fi jika diperlukan.
- Tidak menyimpan password portal kafe. Login portal dilakukan manual di browser.
- Mengecek koneksi internet sebelum membuka YouTube.
- Chromium berjalan fullscreen/kiosk.
- Shortcut Wi-Fi tetap tersedia di menu aplikasi setelah Chromium ditutup.

## Target dan catatan
Dibuat untuk Raspberry Pi 3 dengan Raspberry Pi OS Desktop, Labwc, NetworkManager, dan microSD 16 GB. Target realistis adalah YouTube sampai 720p; resolusi dan kelancaran aktual bergantung codec, koneksi, dan beban CPU/GPU Pi 3. 720p tidak dijamin untuk semua video.

## Instalasi

Buka Terminal pada Raspberry Pi, ekstrak ZIP, masuk ke folder hasil ekstrak, lalu jalankan:

```bash
cd raspi-yt-tv
chmod +x install.sh
./install.sh
```

Installer meminta sudo untuk memasang paket yang belum tersedia dan menambahkan autostart Labwc. Setelah selesai, logout/login atau reboot.

## Alur pemakaian
1. Saat desktop mulai, launcher memeriksa internet.
2. Jika belum tersambung, pilih Wi-Fi dari jendela yang muncul.
3. Jika Wi-Fi meminta password, masukkan password Wi-Fi.
4. Jika jaringan memakai captive portal, browser akan membuka `http://neverssl.com`. Login portal secara manual, lalu tutup jendela browser portal.
5. Konfirmasi pemeriksaan koneksi. Jika belum berhasil, ulangi login atau pilih jaringan lain.
6. Setelah internet terdeteksi, YouTube dibuka fullscreen.

Untuk mengganti Wi-Fi kapan saja: tutup Chromium dengan **Alt+F4**, lalu buka **Menu aplikasi → Internet → Wi-Fi Selector**. Setelah tersambung, buka **YouTube TV** dari menu aplikasi.

## Pengaturan
- URL YouTube dapat diubah di `~/.config/raspi-yt-tv/config`.
- Default URL: `https://www.youtube.com/`.

## Menghapus
Dari folder hasil ekstrak:

```bash
./uninstall.sh
```

Uninstaller menghapus autostart dan file aplikasi ini, tetapi tidak menghapus profil Wi-Fi NetworkManager atau konfigurasi desktop lain.

## Troubleshooting singkat
- Pastikan Wi-Fi dikelola NetworkManager: `nmcli general status`.
- Jika daftar Wi-Fi kosong: `nmcli dev wifi rescan` lalu buka Wi-Fi Selector lagi.
- Jika Chromium tidak ditemukan: `sudo apt update && sudo apt install chromium`.
- Jika autostart tidak jalan, jalankan manual:
  `~/.local/bin/raspi-yt-tv/start-youtube.sh`

Tidak ada password captive portal yang disimpan oleh skrip ini.
