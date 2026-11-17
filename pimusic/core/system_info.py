"""
Pi Music - System Information & Hardware Control
Retrieves system metrics (CPU, RAM, Temp), manages ALSA audio volume,
and handles power operations.
"""

import os
import re
import shutil
import subprocess
import time
from typing import Dict, Optional, Tuple

from pimusic.utils.logger import get_logger

logger = get_logger("SystemInfo")

class SystemInfo:
    """Provides hardware metrics, volume control, and power commands."""

    @staticmethod
    def get_time_string() -> str:
        """Returns current time in HH:MM format."""
        return time.strftime("%H:%M")

    @staticmethod
    def get_cpu_temp() -> Optional[float]:
        """Reads Raspberry Pi CPU temperature from sysfs."""
        temp_paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/devices/virtual/thermal/thermal_zone0/temp"
        ]
        for path in temp_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        temp_str = f.read().strip()
                        return round(float(temp_str) / 1000.0, 1)
                except Exception:
                    pass
        return None

    @staticmethod
    def get_ram_usage() -> Tuple[int, int, float]:
        """
        Returns (used_mb, total_mb, percentage).
        Reads /proc/meminfo on Linux or falls back to estimates.
        """
        meminfo_path = "/proc/meminfo"
        if os.path.exists(meminfo_path):
            try:
                mem = {}
                with open(meminfo_path, "r") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip().split()[0]
                            mem[key] = int(val)
                total_kb = mem.get("MemTotal", 1024 * 1024)
                available_kb = mem.get("MemAvailable", mem.get("MemFree", 0) + mem.get("Buffers", 0) + mem.get("Cached", 0))
                used_kb = total_kb - available_kb
                used_mb = int(used_kb / 1024)
                total_mb = int(total_kb / 1024)
                pct = round((used_kb / total_kb) * 100, 1)
                return used_mb, total_mb, pct
            except Exception:
                pass
        return (320, 1024, 31.2)

    @staticmethod
    def get_cpu_load_pct() -> float:
        """Returns 1-minute load average percentage."""
        try:
            if hasattr(os, "getloadavg"):
                load1, _, _ = os.getloadavg()
                cpu_count = os.cpu_count() or 4
                pct = min(100.0, round((load1 / cpu_count) * 100, 1))
                return pct
        except Exception:
            pass
        return 15.0

    @staticmethod
    def set_alsa_volume(volume_pct: int) -> bool:
        """Sets ALSA master or PCM volume via amixer."""
        volume_pct = max(0, min(100, volume_pct))
        if not shutil.which("amixer"):
            return False

        # Try common controls on Raspberry Pi
        controls = ["PCM", "Master", "Headphones", "Speaker"]
        for ctrl in controls:
            try:
                res = subprocess.run(
                    ["amixer", "sset", ctrl, f"{volume_pct}%"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def get_alsa_volume() -> Optional[int]:
        """Reads current ALSA volume percentage via amixer."""
        if not shutil.which("amixer"):
            return None

        controls = ["PCM", "Master", "Headphones"]
        for ctrl in controls:
            try:
                out = subprocess.check_output(
                    ["amixer", "sget", ctrl],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=2
                )
                match = re.search(r"\[([0-9]{1,3})%\]", out)
                if match:
                    return int(match.group(1))
            except Exception:
                pass
        return None

    @staticmethod
    def shutdown_system() -> None:
        """Gracefully shuts down Raspberry Pi."""
        logger.info("Initiating system shutdown...")
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
        except Exception as e:
            logger.error(f"Failed to shutdown: {e}")

    @staticmethod
    def reboot_system() -> None:
        """Gracefully reboots Raspberry Pi."""
        logger.info("Initiating system reboot...")
        try:
            subprocess.run(["sudo", "reboot"], check=False)
        except Exception as e:
            logger.error(f"Failed to reboot: {e}")
