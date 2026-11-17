#!/usr/bin/env bash
set -u
source "$(dirname "$0")/common.sh"

if ! command -v nmcli >/dev/null 2>&1; then
  notify_error "Perintah nmcli tidak ditemukan. Pastikan NetworkManager terpasang."
  exit 1
fi

nmcli radio wifi on >/dev/null 2>&1 || true
nmcli dev wifi rescan >/dev/null 2>&1 || true
sleep 2

mapfile -t ssids < <(nmcli -g SSID dev wifi list 2>/dev/null | awk 'NF' | awk '!seen[$0]++')
if ((${#ssids[@]} == 0)); then
  zenity --info --title="Wi-Fi Selector" --text="Tidak ada jaringan ditemukan. Coba scan lagi atau pindah lebih dekat ke access point." 2>/dev/null
  exit 0
fi

selected="$(zenity --list --title="Pilih jaringan Wi-Fi" \
  --text="Pilih SSID yang ingin digunakan." \
  --column="SSID" --print-column=1 --height=420 --width=600 "${ssids[@]}" 2>/dev/null)" || exit 0
[[ -n "$selected" ]] || exit 0

# Coba koneksi tanpa meminta password terlebih dahulu. Ini memberi kesempatan
# NetworkManager memakai kredensial dari profil yang sudah tersimpan.
if nmcli --wait 25 dev wifi connect "$selected" 2>/dev/null; then
  zenity --info --title="Wi-Fi" --text="Terhubung ke $selected." 2>/dev/null
  exit 0
fi

password="$(zenity --password --title="Password Wi-Fi" --text="Masukkan password Wi-Fi untuk: $selected" 2>/dev/null)" || exit 0
if nmcli --wait 30 dev wifi connect "$selected" password "$password"; then
  unset password
  zenity --info --title="Wi-Fi" --text="Berhasil terhubung ke $selected." 2>/dev/null
else
  unset password
  notify_error "Gagal terhubung ke $selected. Periksa password atau coba jaringan lain."
  exit 1
fi
