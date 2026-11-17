"""
Pi Music - Wi-Fi Manager using NetworkManager (nmcli)
Provides Wi-Fi scanning, connection status, IP reporting, network connection,
disconnection, reconnection, and captive portal detection.
All operations run asynchronously in background threads.
"""

import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

from pimusic.utils.logger import get_logger

logger = get_logger("WifiManager")

class WifiNetwork:
    """Represents a scanned Wi-Fi access point."""
    def __init__(self, ssid: str, signal: int, security: str, in_use: bool = False, bssid: str = ""):
        self.ssid = ssid
        self.signal = max(0, min(100, signal))   # 0-100%
        self.security = security                 # WPA2, WPA3, Open, etc.
        self.in_use = in_use                     # Currently connected
        self.bssid = bssid

    @property
    def is_open(self) -> bool:
        sec = self.security.lower()
        return not sec or "open" in sec or "--" in sec

    def __repr__(self) -> str:
        return f"<WifiNetwork {self.ssid} ({self.signal}%) {'[Connected]' if self.in_use else ''}>"


class WifiManager:
    """Manages Wi-Fi scanning, connection, reconnection, and captive portal detection."""

    CAPTIVE_PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
    CAPTIVE_FALLBACK_URL = "http://detectportal.firefox.com/canonical.html"

    def __init__(self):
        self.has_nmcli = shutil.which("nmcli") is not None
        self._is_scanning = False
        self._is_connecting = False
        self._is_checking_portal = False
        self.active_interface = self._detect_wifi_interface()

        # Cached state
        self.last_status: Dict[str, any] = {
            "connected": False,
            "state": "disconnected",  # "connected", "portal", "connecting", "disconnected"
            "ssid": "",
            "ip": "No Connection",
            "signal": 0,
            "portal_detected": False,
            "portal_url": "",
            "interface": self.active_interface
        }

    def _detect_wifi_interface(self) -> str:
        """Finds primary wireless interface name (e.g. wlan0)."""
        if not self.has_nmcli:
            return "wlan0"
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE", "device"],
                capture_output=True,
                text=True,
                timeout=2
            )
            for line in res.stdout.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 2 and parts[1] == "wifi":
                    return parts[0].strip()
        except Exception:
            pass
        return "wlan0"

    def is_connected(self) -> bool:
        """Checks if device has an active Wi-Fi or network connection."""
        status = self.get_status()
        return status.get("connected", False)

    def get_status(self) -> Dict[str, any]:
        """Gets current connection status, SSID, signal, and IP address."""
        if not self.has_nmcli:
            # Fallback for desktop simulation
            return dict(self.last_status)

        try:
            # 1. Check general network connectivity
            gen_res = subprocess.run(
                ["nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general", "status"],
                capture_output=True,
                text=True,
                timeout=2
            )
            gen_out = gen_res.stdout.strip().lower()
            is_portal_nm = "portal" in gen_out
            is_full = "full" in gen_out
            is_connected_gen = "connected" in gen_out or is_full or is_portal_nm

            # 2. Find active Wi-Fi device details
            dev_res = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
                capture_output=True,
                text=True,
                timeout=2
            )
            ssid = ""
            for line in dev_res.stdout.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 4 and parts[1] == "wifi" and "connected" in parts[2]:
                    ssid = parts[3].strip()
                    break

            # 3. Find current IP address
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

            # 4. Find active Wi-Fi signal percentage
            signal = 0
            if ssid:
                sig_res = subprocess.run(
                    ["nmcli", "-t", "-f", "IN-USE,SIGNAL", "dev", "wifi"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                for line in sig_res.stdout.strip().split("\n"):
                    parts = line.split(":")
                    if len(parts) >= 2 and parts[0] == "*":
                        try:
                            signal = int(parts[1].strip())
                        except ValueError:
                            signal = 75
                        break
                if signal == 0:
                    signal = 75

            # Determine connection state
            if is_portal_nm or self.last_status.get("portal_detected", False):
                state_str = "portal"
            elif ssid and (is_full or is_connected_gen):
                state_str = "connected"
            elif self._is_connecting:
                state_str = "connecting"
            else:
                state_str = "disconnected"

            self.last_status = {
                "connected": bool(ssid) and (is_connected_gen or is_portal_nm),
                "state": state_str,
                "ssid": ssid or ("Online (Ethernet)" if is_full else "Disconnected"),
                "ip": ip,
                "signal": signal if ssid else 0,
                "portal_detected": is_portal_nm or self.last_status.get("portal_detected", False),
                "portal_url": self.last_status.get("portal_url", ""),
                "interface": self.active_interface
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
            logger.info("Scanning for Wi-Fi networks...")
            networks: List[WifiNetwork] = []
            try:
                if not self.has_nmcli:
                    # Simulation networks
                    time.sleep(0.5)
                    networks = [
                        WifiNetwork("Home-WiFi", 88, "WPA2", in_use=True),
                        WifiNetwork("CoffeeShop_Guest", 74, "Open", in_use=False),
                        WifiNetwork("Pi-Hotspot", 65, "WPA2", in_use=False),
                        WifiNetwork("Campus_Portal", 52, "Open", in_use=False),
                        WifiNetwork("Neighbor_5G", 30, "WPA3", in_use=False),
                    ]
                else:
                    # Request fresh scan
                    subprocess.run(["nmcli", "dev", "wifi", "rescan"], stderr=subprocess.DEVNULL, timeout=5)
                    time.sleep(0.5)
                    res = subprocess.run(
                        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE,BSSID", "dev", "wifi", "list"],
                        capture_output=True,
                        text=True,
                        timeout=6
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
                            bssid = parts[4].strip() if len(parts) >= 5 else ""
                            networks.append(WifiNetwork(ssid, signal, security, in_use, bssid))

                    # Sort by: currently connected first, then highest signal strength
                    networks.sort(key=lambda n: (n.in_use, n.signal), reverse=True)
            except Exception as e:
                logger.error(f"Error scanning Wi-Fi: {e}")
            finally:
                self._is_scanning = False
                logger.info(f"Scan finished. Found {len(networks)} networks.")
                callback(networks)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def connect_async(self, ssid: str, password: str, callback: Callable[[bool, str], None]) -> None:
        """Connect to specified Wi-Fi network asynchronously."""
        if self._is_connecting:
            callback(False, "Connection already in progress")
            return

        def _worker():
            self._is_connecting = True
            self.last_status["state"] = "connecting"
            logger.info(f"Connecting to Wi-Fi SSID: {ssid}...")
            try:
                if not self.has_nmcli:
                    time.sleep(1.0)
                    is_portal = ("portal" in ssid.lower() or "guest" in ssid.lower())
                    self.last_status = {
                        "connected": True,
                        "state": "portal" if is_portal else "connected",
                        "ssid": ssid,
                        "ip": "192.168.1.112",
                        "signal": 85,
                        "portal_detected": is_portal,
                        "portal_url": "http://192.168.1.1/login" if is_portal else "",
                        "interface": "wlan0"
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
                    # Trigger captive portal check right after connecting
                    self.check_captive_portal_async(lambda detected, url: None)
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

    def disconnect_async(self, callback: Callable[[bool, str], None]) -> None:
        """Disconnect active Wi-Fi connection without affecting playback or other apps."""
        def _worker():
            logger.info(f"Disconnecting Wi-Fi interface {self.active_interface}...")
            try:
                if not self.has_nmcli:
                    time.sleep(0.5)
                    self.last_status = {
                        "connected": False,
                        "state": "disconnected",
                        "ssid": "Disconnected",
                        "ip": "No IP",
                        "signal": 0,
                        "portal_detected": False,
                        "portal_url": "",
                        "interface": self.active_interface
                    }
                    callback(True, "Wi-Fi disconnected")
                    return

                res = subprocess.run(
                    ["nmcli", "dev", "disconnect", self.active_interface],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0:
                    self.last_status["connected"] = False
                    self.last_status["state"] = "disconnected"
                    self.last_status["ssid"] = "Disconnected"
                    self.last_status["ip"] = "No IP"
                    self.last_status["portal_detected"] = False
                    callback(True, "Wi-Fi disconnected")
                else:
                    err = res.stderr.strip() or "Failed to disconnect"
                    callback(False, err)
            except Exception as e:
                callback(False, str(e))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def reconnect_async(self, callback: Callable[[bool, str], None]) -> None:
        """Reconnect to the active interface or last known Wi-Fi network."""
        def _worker():
            logger.info("Reconnecting Wi-Fi...")
            try:
                if not self.has_nmcli:
                    time.sleep(0.5)
                    self.last_status["connected"] = True
                    self.last_status["state"] = "connected"
                    self.last_status["ip"] = "192.168.1.105"
                    self.last_status["signal"] = 80
                    callback(True, "Reconnected successfully")
                    return

                res = subprocess.run(
                    ["nmcli", "dev", "connect", self.active_interface],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if res.returncode == 0:
                    self.get_status()
                    self.check_captive_portal_async(lambda detected, url: None)
                    callback(True, "Reconnected successfully")
                else:
                    err = res.stderr.strip() or "Failed to reconnect"
                    callback(False, err)
            except Exception as e:
                callback(False, str(e))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def check_captive_portal_async(self, callback: Callable[[bool, str], None]) -> None:
        """
        Probe for captive portal using HTTP 204 check and NetworkManager connectivity status.
        Runs asynchronously in background thread.
        """
        if self._is_checking_portal:
            return

        def _worker():
            self._is_checking_portal = True
            logger.info("Checking for captive portal...")
            portal_detected = False
            portal_url = ""

            try:
                # 1. First probe via nmcli if available
                if self.has_nmcli:
                    res = subprocess.run(
                        ["nmcli", "networking", "connectivity", "check"],
                        capture_output=True,
                        text=True,
                        timeout=4
                    )
                    con_state = res.stdout.strip().lower()
                    if "portal" in con_state:
                        portal_detected = True

                # 2. HTTP Probe to standard 204 endpoint
                req = urllib.request.Request(
                    self.CAPTIVE_PROBE_URL,
                    headers={"User-Agent": "Mozilla/5.0 (Linux; Android) PiMusic/1.0"}
                )
                try:
                    # Open without automatic redirect following to capture redirect location
                    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                        def redirect_request(self, req, fp, code, msg, headers, newurl):
                            return None

                    opener = urllib.request.build_opener(NoRedirectHandler)
                    with opener.open(req, timeout=4) as resp:
                        # Standard 204 check returns status 204 and 0 bytes
                        if resp.status != 204:
                            portal_detected = True
                            portal_url = resp.geturl()
                except urllib.error.HTTPError as he:
                    if he.code in (301, 302, 307):
                        portal_detected = True
                        portal_url = he.headers.get("Location") or self.CAPTIVE_FALLBACK_URL
                except Exception:
                    pass

                if portal_detected and not portal_url:
                    portal_url = self.CAPTIVE_FALLBACK_URL

                self.last_status["portal_detected"] = portal_detected
                self.last_status["portal_url"] = portal_url
                if portal_detected:
                    self.last_status["state"] = "portal"
                    logger.warning(f"Captive portal detected: {portal_url}")
                else:
                    logger.info("No captive portal detected. Internet access verified.")

            except Exception as e:
                logger.debug(f"Captive portal probe error: {e}")
            finally:
                self._is_checking_portal = False
                callback(portal_detected, portal_url)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def open_portal_browser(self, portal_url: str = "") -> Tuple[bool, str]:
        """
        Launches a lightweight browser for manual portal login.
        Never saves credentials (launches in private/temp mode if supported).
        """
        target_url = portal_url or self.last_status.get("portal_url") or "http://connectivitycheck.gstatic.com/generate_204"

        # List of candidate lightweight browsers on Raspberry Pi OS / Linux
        browsers = [
            ("netsurf-gtk", ["netsurf-gtk", target_url]),
            ("dillo", ["dillo", target_url]),
            ("midori", ["midori", "-p", target_url]),  # private mode
            ("surf", ["surf", target_url]),
            ("links2", ["links2", "-g", target_url]),
            ("x-www-browser", ["x-www-browser", target_url]),
            ("chromium-browser", ["chromium-browser", "--incognito", "--temp-profile", f"--app={target_url}"])
        ]

        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"

        for name, cmd in browsers:
            if shutil.which(name):
                try:
                    logger.info(f"Launching lightweight browser '{name}' for captive portal: {target_url}")
                    subprocess.Popen(cmd, env=env)
                    return True, f"Opened portal with {name}"
                except Exception as e:
                    logger.warning(f"Failed to launch {name}: {e}")

        # Fallback if no browser is installed
        msg = "No browser found. Please install netsurf-gtk or dillo: sudo apt install -y netsurf-gtk"
        logger.error(msg)
        return False, msg
