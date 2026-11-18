"""
Pi Music - Bluetooth Audio & Device Manager
Manages Bluetooth scanning, pairing, connecting, disconnecting, and audio routing
via bluetoothctl and bluez-alsa on Raspberry Pi OS.
All network and device commands run asynchronously in background threads.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional

from config import CONFIG_DIR, IS_WINDOWS, ALSA_DEFAULT_DEVICE
from pimusic.utils.logger import get_logger

logger = get_logger("BluetoothManager")

AUDIO_OUTPUT_PREF_FILE = CONFIG_DIR / "audio_output.json"


class BluetoothDevice:
    """Represents a discovered or paired Bluetooth device."""

    def __init__(
        self,
        mac: str,
        name: str,
        paired: bool = False,
        connected: bool = False,
        trusted: bool = False,
        rssi: Optional[int] = None,
        icon: str = "audio-card"
    ):
        self.mac = mac.upper()
        self.name = name.strip() or mac
        self.paired = paired
        self.connected = connected
        self.trusted = trusted
        self.rssi = rssi
        self.icon = icon

    def __repr__(self) -> str:
        status = []
        if self.connected:
            status.append("Connected")
        elif self.paired:
            status.append("Paired")
        st = f" [{' '.join(status)}]" if status else ""
        return f"<BluetoothDevice {self.name} ({self.mac}){st}>"


class BluetoothManager:
    """Manages Bluetooth device discovery, pairing, and audio routing."""

    def __init__(self):
        self.has_bluetoothctl = shutil.which("bluetoothctl") is not None
        self._is_scanning = False
        self._is_connecting = False
        self._lock = threading.Lock()

        # Cache of scanned and paired devices: mac -> BluetoothDevice
        self._devices: Dict[str, BluetoothDevice] = {}

        # Audio output preference: "jack" (default 3.5mm) or "bluetooth"
        self.audio_output_mode = self._load_audio_output_pref()

        # Last status cache
        self.last_status: Dict[str, any] = {
            "powered": False,
            "connected": False,
            "connected_mac": "",
            "connected_name": "",
            "audio_output": self.audio_output_mode
        }

        # Initialize powered state and populate paired devices
        if self.has_bluetoothctl:
            threading.Thread(target=self._initial_setup, daemon=True).start()

    def _load_audio_output_pref(self) -> str:
        """Loads saved audio output selection ('jack' or 'bluetooth')."""
        try:
            if AUDIO_OUTPUT_PREF_FILE.exists():
                with open(AUDIO_OUTPUT_PREF_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("mode", "jack")
        except Exception:
            pass
        return "jack"

    def save_audio_output_pref(self, mode: str):
        """Saves audio output selection."""
        self.audio_output_mode = mode
        self.last_status["audio_output"] = mode
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(AUDIO_OUTPUT_PREF_FILE, "w", encoding="utf-8") as f:
                json.dump({"mode": mode}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save audio output pref: {e}")

    def _initial_setup(self):
        """Power on bluetooth adapter and query paired devices."""
        try:
            if shutil.which("rfkill"):
                subprocess.run(["rfkill", "unblock", "bluetooth"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            subprocess.run(["bluetoothctl", "agent", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            subprocess.run(["bluetoothctl", "default-agent"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            self.refresh_devices()
        except Exception as e:
            logger.warning(f"Bluetooth initial setup error: {e}")

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    @property
    def is_connecting(self) -> bool:
        return self._is_connecting

    def is_connected(self) -> bool:
        """Checks if a Bluetooth audio device is currently connected."""
        with self._lock:
            for dev in self._devices.values():
                if dev.connected:
                    return True
        return False

    def get_connected_device(self) -> Optional[BluetoothDevice]:
        """Returns the currently connected Bluetooth device if any."""
        with self._lock:
            for dev in self._devices.values():
                if dev.connected:
                    return dev
        return None

    def get_devices(self) -> List[BluetoothDevice]:
        """Returns sorted list of known devices: Connected first, Paired second, others last."""
        with self._lock:
            dev_list = list(self._devices.values())

        def sort_key(d: BluetoothDevice):
            score = 0
            if d.connected:
                score -= 200
            elif d.paired:
                score -= 100
            return (score, d.name.lower())

        return sorted(dev_list, key=sort_key)

    def refresh_devices(self):
        """Queries bluetoothctl for known paired and scanned devices synchronously."""
        if not self.has_bluetoothctl:
            return

        try:
            # 1. Get paired devices
            paired_res = subprocess.run(
                ["bluetoothctl", "paired-devices"],
                capture_output=True,
                text=True,
                timeout=4
            )
            paired_macs = set()
            for line in paired_res.stdout.splitlines():
                # Format: Device XX:XX:XX:XX:XX:XX DeviceName
                m = re.match(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", line.strip())
                if m:
                    mac, name = m.group(1).upper(), m.group(2).strip()
                    paired_macs.add(mac)
                    with self._lock:
                        if mac not in self._devices:
                            self._devices[mac] = BluetoothDevice(mac=mac, name=name, paired=True)
                        else:
                            self._devices[mac].name = name or self._devices[mac].name
                            self._devices[mac].paired = True

            # 2. Check info for each paired device to see if connected
            connected_found = False
            for mac in paired_macs:
                info_res = subprocess.run(
                    ["bluetoothctl", "info", mac],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                is_conn = "Connected: yes" in info_res.stdout
                is_trusted = "Trusted: yes" in info_res.stdout
                with self._lock:
                    if mac in self._devices:
                        self._devices[mac].connected = is_conn
                        self._devices[mac].trusted = is_trusted
                        if is_conn:
                            connected_found = True
                            self.last_status["connected"] = True
                            self.last_status["connected_mac"] = mac
                            self.last_status["connected_name"] = self._devices[mac].name

            if not connected_found:
                self.last_status["connected"] = False
                self.last_status["connected_mac"] = ""
                self.last_status["connected_name"] = ""

        except Exception as e:
            logger.debug(f"Error querying bluetooth devices: {e}")

    def scan_devices_async(self, callback: Optional[Callable[[List[BluetoothDevice]], None]] = None):
        """Runs a Bluetooth scan in the background for 6-8 seconds."""
        if self._is_scanning:
            return

        def _worker():
            self._is_scanning = True
            logger.info("Starting Bluetooth device discovery scan...")
            try:
                if self.has_bluetoothctl:
                    # Run discovery scan with timeout
                    subprocess.run(
                        ["bluetoothctl", "--timeout", "7", "scan", "on"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10
                    )
                    # Query all discovered devices
                    devs_res = subprocess.run(
                        ["bluetoothctl", "devices"],
                        capture_output=True,
                        text=True,
                        timeout=4
                    )
                    for line in devs_res.stdout.splitlines():
                        m = re.match(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", line.strip())
                        if m:
                            mac, name = m.group(1).upper(), m.group(2).strip()
                            with self._lock:
                                if mac not in self._devices:
                                    self._devices[mac] = BluetoothDevice(mac=mac, name=name)
                                else:
                                    self._devices[mac].name = name or self._devices[mac].name

                    self.refresh_devices()
                else:
                    # Desktop simulation mock devices
                    time.sleep(1.5)
                    self._mock_simulation_devices()

            except Exception as e:
                logger.error(f"Bluetooth scan failed: {e}")
            finally:
                self._is_scanning = False
                if callback:
                    callback(self.get_devices())

        threading.Thread(target=_worker, daemon=True).start()

    def connect_device_async(self, mac: str, callback: Optional[Callable[[bool, str], None]] = None):
        """Pairs, trusts, and connects to a Bluetooth device asynchronously."""
        if self._is_connecting:
            return

        def _worker():
            self._is_connecting = True
            mac_clean = mac.upper()
            logger.info(f"Connecting to Bluetooth device {mac_clean}...")
            success = False
            msg = ""

            try:
                if self.has_bluetoothctl:
                    # 1. Trust device
                    subprocess.run(["bluetoothctl", "trust", mac_clean], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                    
                    # 2. Pair device if not already paired
                    with self._lock:
                        is_paired = self._devices.get(mac_clean, BluetoothDevice(mac_clean, "")).paired

                    if not is_paired:
                        subprocess.run(["bluetoothctl", "pair", mac_clean], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

                    # 3. Connect device
                    res = subprocess.run(
                        ["bluetoothctl", "connect", mac_clean],
                        capture_output=True,
                        text=True,
                        timeout=12
                    )

                    # Verify connection
                    info_res = subprocess.run(
                        ["bluetoothctl", "info", mac_clean],
                        capture_output=True,
                        text=True,
                        timeout=4
                    )

                    if "Connected: yes" in info_res.stdout or "Connection successful" in res.stdout:
                        success = True
                        with self._lock:
                            if mac_clean in self._devices:
                                self._devices[mac_clean].connected = True
                                self._devices[mac_clean].paired = True
                                self._devices[mac_clean].trusted = True
                        msg = f"Connected to {self._devices.get(mac_clean, BluetoothDevice(mac_clean, '')).name}"
                    else:
                        msg = "Failed to connect. Make sure device is in pairing mode."
                else:
                    # Desktop simulation
                    time.sleep(1.0)
                    with self._lock:
                        if mac_clean in self._devices:
                            self._devices[mac_clean].connected = True
                            self._devices[mac_clean].paired = True
                    success = True
                    msg = "Connected (Simulation)"

            except subprocess.TimeoutExpired:
                msg = "Connection timed out."
            except Exception as e:
                msg = f"Connection error: {e}"
            finally:
                self._is_connecting = False
                self.refresh_devices()
                if callback:
                    callback(success, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def disconnect_device_async(self, mac: Optional[str] = None, callback: Optional[Callable[[bool, str], None]] = None):
        """Disconnects a Bluetooth device asynchronously."""
        def _worker():
            mac_clean = (mac or self.last_status.get("connected_mac", "")).upper()
            logger.info(f"Disconnecting Bluetooth device {mac_clean}...")
            success = False
            msg = ""

            try:
                if self.has_bluetoothctl and mac_clean:
                    res = subprocess.run(
                        ["bluetoothctl", "disconnect", mac_clean],
                        capture_output=True,
                        text=True,
                        timeout=6
                    )
                    success = "Successful disconnected" in res.stdout or "disconnect" in res.stdout.lower()
                    msg = "Disconnected."
                else:
                    success = True
                    msg = "Disconnected (Simulation)"

                with self._lock:
                    if mac_clean in self._devices:
                        self._devices[mac_clean].connected = False

            except Exception as e:
                msg = f"Disconnect error: {e}"
            finally:
                self.refresh_devices()
                if callback:
                    callback(success, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def remove_device_async(self, mac: str, callback: Optional[Callable[[bool, str], None]] = None):
        """Unpairs and removes a Bluetooth device asynchronously."""
        def _worker():
            mac_clean = mac.upper()
            try:
                if self.has_bluetoothctl:
                    subprocess.run(["bluetoothctl", "remove", mac_clean], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                with self._lock:
                    self._devices.pop(mac_clean, None)
                if callback:
                    callback(True, f"Device {mac_clean} removed.")
            except Exception as e:
                if callback:
                    callback(False, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _mock_simulation_devices(self):
        """Mock devices when testing on non-Linux systems."""
        mocks = [
            ("FC:58:FA:12:34:56", "JBL Flip 5", True, False),
            ("E8:07:BF:AB:CD:EF", "Sony WH-1000XM4", True, False),
            ("00:1A:7D:DA:71:02", "Anker Soundcore 2", False, False),
            ("44:23:7C:11:22:33", "AirPods Pro", False, False),
        ]
        with self._lock:
            for mac, name, paired, connected in mocks:
                if mac not in self._devices:
                    self._devices[mac] = BluetoothDevice(mac=mac, name=name, paired=paired, connected=connected)
