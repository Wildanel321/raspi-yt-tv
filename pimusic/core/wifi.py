"""
Pi Music - Wi-Fi Manager using NetworkManager (nmcli)
Provides Wi-Fi scanning, connection status, IP reporting, and network connection.
"""

import shutil
import subprocess
import threading
from typing import Callable, Dict, List, Optional

from pimusic.utils.logger import get_logger

logger = get_logger("WifiManager")

class WifiNetwork:
    """Represents a scanned Wi-Fi access point."""
    def __init__(self, ssid: str, signal: int, security: str, in_use: bool = False):
        self.ssid = ssid
        self.signal = signal          # 0-100%
        self.security = security      # WPA2, WPA3, Open, etc.
        self.in_use = in_use          # Currently connected

    def __repr__(self) -> str:
        return f"<WifiNetwork {self.ssid} ({self.signal}%) {'[Connected]' if self.in_use else ''}>"


class WifiManager:
    """Manages Wi-Fi scanning and connection via NetworkManager nmcli."""

    def __init__(self):
        self.has_nmcli = shutil.which("nmcli") is not None
        self._is_scanning = False
        self._is_connecting = False
        self.last_status: Dict[str, str] = {
            "connected": False,
            "ssid": "",
            "ip": "No Connection",
            "signal": 0
        }

    def is_connected(self) -> bool:
        """Checks if device has an active internet or Wi-Fi connection."""
        status = self.get_status()
        return status.get("connected", False)

    def get_status(self) -> Dict[str, any]:
        """Gets current connection status, SSID, and IP address."""
        if not self.has_nmcli:
            # Fallback for desktop simulation / systems without nmcli
            return {
                "connected": True,
                "ssid": "Home-WiFi (Sim)",
                "ip": "192.168.1.105",
                "signal": 85
            }

        try:
            # Check general connectivity
            res = subprocess.run(
                ["nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general", "status"],
                capture_output=True,
                text=True,
                timeout=2
            )
            state_line = res.stdout.strip().split(":")
            is_online = "full" in res.stdout.lower() or "connected" in res.stdout.lower()

            # Find active Wi-Fi connection details
            dev_res = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
                capture_output=True,
                text=True,
                timeout=2
            )
            ssid = ""
            for line in dev_res.stdout.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 4 and parts[1] == "wifi" and parts[2] == "connected":
                    ssid = parts[3]
                    break

            # Find IP address
            ip = "No IP"
            ip_res = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=2
            )
            ips = ip_res.stdout.strip().split()
            if ips:
                ip = ips[0]

            self.last_status = {
                "connected": is_online and bool(ssid),
                "ssid": ssid or ("Online (Ethernet)" if is_online else "Disconnected"),
                "ip": ip,
                "signal": 80 if ssid else 0
            }
            return self.last_status
        except Exception as e:
            logger.debug(f"Error checking Wi-Fi status: {e}")
            return self.last_status

    def scan_networks_async(self, callback: Callable[[List[WifiNetwork]], None]) -> None:
        """Scan available Wi-Fi networks in a background thread."""
        if self._is_scanning:
            return

        def _worker():
            self._is_scanning = True
            networks: List[WifiNetwork] = []
            try:
                if not self.has_nmcli:
                    # Simulation networks
                    networks = [
                        WifiNetwork("Home-WiFi", 88, "WPA2", in_use=True),
                        WifiNetwork("Pi-Hotspot", 65, "WPA2", in_use=False),
                        WifiNetwork("Office_Guest", 42, "Open", in_use=False),
                        WifiNetwork("Neighbor_Net", 25, "WPA3", in_use=False),
                    ]
                else:
                    # Request rescan
                    subprocess.run(["nmcli", "dev", "wifi", "rescan"], stderr=subprocess.DEVNULL, timeout=5)
                    # Fetch list
                    res = subprocess.run(
                        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi", "list"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    seen_ssids = set()
                    for line in res.stdout.strip().split("\n"):
                        if not line:
                            continue
                        parts = line.split(":")
                        if len(parts) >= 4:
                            ssid = parts[0].strip()
                            if not ssid or ssid == "--" or ssid in seen_ssids:
                                continue
                            seen_ssids.add(ssid)
                            try:
                                signal = int(parts[1].strip())
                            except ValueError:
                                signal = 50
                            security = parts[2].strip() or "Open"
                            in_use = parts[3].strip() == "*"
                            networks.append(WifiNetwork(ssid, signal, security, in_use))

                    # Sort by signal strength descending
                    networks.sort(key=lambda n: (n.in_use, n.signal), reverse=True)
            except Exception as e:
                logger.error(f"Error scanning Wi-Fi: {e}")
            finally:
                self._is_scanning = False
                callback(networks)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def connect_async(self, ssid: str, password: str, callback: Callable[[bool, str], None]) -> None:
        """Connect to specified Wi-Fi network in background thread."""
        if self._is_connecting:
            callback(False, "Connection already in progress")
            return

        def _worker():
            self._is_connecting = True
            logger.info(f"Connecting to Wi-Fi SSID: {ssid}...")
            try:
                if not self.has_nmcli:
                    # Simulation mode
                    self.last_status = {
                        "connected": True,
                        "ssid": ssid,
                        "ip": "192.168.1.112",
                        "signal": 90
                    }
                    callback(True, f"Connected to {ssid}")
                    return

                cmd = ["nmcli", "dev", "wifi", "connect", ssid]
                if password:
                    cmd.extend(["password", password])

                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if res.returncode == 0:
                    logger.info(f"Successfully connected to {ssid}")
                    self.get_status()
                    callback(True, f"Connected to {ssid}")
                else:
                    err_msg = res.stderr.strip() or res.stdout.strip() or "Failed to connect"
                    logger.warning(f"Connection failed: {err_msg}")
                    callback(False, err_msg)
            except subprocess.TimeoutExpired:
                callback(False, "Connection timed out")
            except Exception as e:
                callback(False, str(e))
            finally:
                self._is_connecting = False

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
