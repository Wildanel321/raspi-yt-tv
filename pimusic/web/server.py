"""
Pi Music - Lightweight Web Remote Control Server
Provides a zero-dependency HTTP server and REST API so Pi Music can be controlled
from any phone, tablet, or laptop browser when running without an HDMI monitor
(or simultaneously alongside HDMI).
"""

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from config import APP_NAME, APP_VERSION, WEB_HOST, WEB_PORT
from pimusic.core.system_info import SystemInfo
from pimusic.core.youtube import Track
from pimusic.utils.logger import get_logger

logger = get_logger("WebServer")

STATIC_DIR = Path(__file__).parent / "static"


def get_local_ip() -> str:
    """Best-effort LAN IP detection without spawning subprocesses."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        finally:
            s.close()
    except Exception:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


class _PiMusicHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, app, web_server):
        self.app = app
        self.web_server = web_server
        super().__init__(server_address, RequestHandlerClass)


class _PiMusicRequestHandler(BaseHTTPRequestHandler):
    """Handles static web UI and JSON REST API requests."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep stdout/journald clean and CPU overhead minimal on Pi 3
        logger.debug("HTTP %s - %s", self.address_string(), format % args)

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", payload)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        if length > 256 * 1024:
            raise ValueError("Request body too large")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._serve_index()
            return

        if path == "/api/state":
            self._send_json(self.server.web_server.build_state())
            return

        if path == "/api/search":
            q = (query.get("q") or [""])[0].strip()
            if not q:
                self._send_json({"tracks": [], "query": ""})
                return
            try:
                tracks = self.server.app.youtube.search_sync(q)
                self._send_json({
                    "query": q,
                    "tracks": [self._serialize_track(t) for t in tracks]
                })
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                self._send_json({"error": str(e), "tracks": []}, status=500)
            return

        if path == "/api/bluetooth/devices":
            bt = self.server.app.bluetooth
            devices = [
                {
                    "mac": d.mac,
                    "name": d.name,
                    "paired": d.paired,
                    "connected": d.connected,
                    "trusted": d.trusted,
                }
                for d in bt.get_devices()
            ]
            self._send_json({
                "devices": devices,
                "is_scanning": bt.is_scanning,
                "is_connecting": bt.is_connecting,
                "audio_output": bt.audio_output_mode,
                "status": bt.last_status,
            })
            return

        if path == "/api/wifi/networks":
            ws = self.server.web_server
            self._send_json({
                "networks": ws.wifi_networks,
                "is_scanning": self.server.app.wifi._is_scanning,
                "status": self.server.app.wifi.get_status(),
            })
            return

        if path == "/api/wifi/status":
            self._send_json({"status": self.server.app.wifi.get_status(force=True)})
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        app = self.server.app
        ws = self.server.web_server

        try:
            body = self._read_json_body()
        except Exception as e:
            self._send_json({"error": f"Invalid JSON: {e}"}, status=400)
            return

        try:
            if path == "/api/player/toggle":
                app.toggle_play_pause()
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/player/stop":
                app.stop()
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/player/next":
                app.play_next()
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/player/prev":
                app.play_previous()
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/player/seek":
                pos = float(body.get("position", 0.0))
                app.player.seek(pos)
                self._send_json({"ok": True, "position": app.player.current_time})
                return

            if path == "/api/player/volume":
                vol = int(body.get("volume", app.player.volume))
                app.set_volume(vol)
                self._send_json({"ok": True, "volume": app.player.volume})
                return

            if path == "/api/player/repeat":
                mode = body.get("mode")
                if mode in ("off", "all", "one"):
                    app.playlist.repeat_mode = mode
                else:
                    order = ["off", "all", "one"]
                    idx = order.index(app.playlist.repeat_mode) if app.playlist.repeat_mode in order else 0
                    app.playlist.repeat_mode = order[(idx + 1) % len(order)]
                self._send_json({"ok": True, "repeat_mode": app.playlist.repeat_mode})
                return

            if path == "/api/player/shuffle":
                if "enabled" in body:
                    app.playlist.shuffle = bool(body["enabled"])
                else:
                    app.playlist.shuffle = not app.playlist.shuffle
                self._send_json({"ok": True, "shuffle": app.playlist.shuffle})
                return

            if path == "/api/play":
                track_data = body.get("track")
                if not isinstance(track_data, dict) or not track_data.get("video_id"):
                    self._send_json({"error": "Missing track data"}, status=400)
                    return
                track = Track.from_dict(track_data)
                app.play_track_now(track)
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/queue/add":
                track_data = body.get("track")
                if not isinstance(track_data, dict) or not track_data.get("video_id"):
                    self._send_json({"error": "Missing track data"}, status=400)
                    return
                track = Track.from_dict(track_data)
                if body.get("play_next"):
                    app.playlist.play_next(track)
                else:
                    app.playlist.add_track(track)
                self._send_json({"ok": True, "queue_length": len(app.playlist.queue)})
                return

            if path == "/api/queue/jump":
                index = int(body.get("index", -1))
                track = app.play_index(index)
                if track is None:
                    self._send_json({"error": "Invalid queue index"}, status=400)
                    return
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/queue/remove":
                index = int(body.get("index", -1))
                removed = app.playlist.remove_at(index)
                if not removed:
                    self._send_json({"error": "Invalid queue index"}, status=400)
                    return
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/queue/clear":
                app.playlist.clear()
                self._send_json({"ok": True, "state": ws.build_state()})
                return

            if path == "/api/bluetooth/scan":
                app.bluetooth.scan_devices_async()
                self._send_json({"ok": True, "message": "Bluetooth scan started"})
                return

            if path == "/api/bluetooth/connect":
                mac = str(body.get("mac", "")).strip()
                if not mac:
                    self._send_json({"error": "Missing device MAC address"}, status=400)
                    return

                def _on_bt_connected(success: bool, msg: str):
                    ws.last_bluetooth_message = msg
                    if success:
                        app.set_audio_output_mode("bluetooth", mac)

                app.bluetooth.connect_device_async(mac, _on_bt_connected)
                self._send_json({"ok": True, "message": f"Connecting to {mac}..."})
                return

            if path == "/api/bluetooth/disconnect":
                mac = str(body.get("mac", "")).strip() or None

                def _on_bt_disconnected(success: bool, msg: str):
                    ws.last_bluetooth_message = msg
                    if success:
                        app.set_audio_output_mode("jack")

                app.bluetooth.disconnect_device_async(mac, _on_bt_disconnected)
                self._send_json({"ok": True, "message": "Disconnecting Bluetooth..."})
                return

            if path == "/api/bluetooth/output":
                mode = str(body.get("mode", "jack")).strip().lower()
                if mode not in ("jack", "bluetooth"):
                    self._send_json({"error": "Mode must be 'jack' or 'bluetooth'"}, status=400)
                    return
                app.set_audio_output_mode(mode)
                self._send_json({"ok": True, "audio_output": app.bluetooth.audio_output_mode})
                return

            if path == "/api/wifi/scan":
                def _on_wifi_scan(networks):
                    ws.wifi_networks = [
                        {
                            "ssid": n.ssid,
                            "signal": n.signal,
                            "security": n.security,
                            "in_use": n.in_use,
                            "is_open": n.is_open,
                        }
                        for n in networks
                    ]

                app.wifi.scan_networks_async(_on_wifi_scan)
                self._send_json({"ok": True, "message": "Wi-Fi scan started"})
                return

            if path == "/api/wifi/connect":
                ssid = str(body.get("ssid", "")).strip()
                password = str(body.get("password", ""))
                if not ssid:
                    self._send_json({"error": "Missing SSID"}, status=400)
                    return

                def _on_wifi_connect(success: bool, msg: str):
                    ws.last_wifi_message = msg

                app.wifi.connect_async(ssid, password, _on_wifi_connect)
                self._send_json({"ok": True, "message": f"Connecting to {ssid}..."})
                return

            if path == "/api/system/reboot":
                self._send_json({"ok": True, "message": "Rebooting Raspberry Pi..."})
                threading.Timer(0.5, SystemInfo.reboot_system).start()
                return

            if path == "/api/system/shutdown":
                self._send_json({"ok": True, "message": "Shutting down Raspberry Pi..."})
                threading.Timer(0.5, SystemInfo.shutdown_system).start()
                return

            self._send_json({"error": "Unknown endpoint"}, status=404)
        except Exception as e:
            logger.error(f"API error on {path}: {e}")
            self._send_json({"error": str(e)}, status=500)

    def _serve_index(self) -> None:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            self._send_bytes(500, "text/plain; charset=utf-8", b"Web UI index.html not found.")
            return
        body = index_path.read_bytes()
        self._send_bytes(200, "text/html; charset=utf-8", body)

    @staticmethod
    def _serialize_track(track: Track) -> Dict[str, Any]:
        d = track.to_dict()
        d["duration_str"] = track.duration_str
        return d


class WebServer:
    """Background HTTP server that exposes Pi Music over the local network."""

    def __init__(self, app: Any, host: str = WEB_HOST, port: int = WEB_PORT):
        self.app = app
        self.host = host
        self.port = port
        self._httpd: Optional[_PiMusicHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.wifi_networks: List[Dict[str, Any]] = []
        self.last_wifi_message: str = ""
        self.last_bluetooth_message: str = ""
        self._hostname = socket.gethostname()
        self._cached_sys_time = 0.0
        self._cached_sys: Dict[str, Any] = {}

    def start(self) -> bool:
        """Start the web remote server in a daemon thread."""
        if self._httpd is not None:
            return True
        try:
            self._httpd = _PiMusicHTTPServer(
                (self.host, self.port),
                _PiMusicRequestHandler,
                self.app,
                self,
            )
            self.port = self._httpd.server_address[1]
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                kwargs={"poll_interval": 0.5},
                daemon=True,
                name="PiMusicWebServer",
            )
            self._thread.start()
            ip = get_local_ip()
            logger.info(f"Web Remote active at http://{ip}:{self.port} (http://{self._hostname}.local:{self.port})")
            return True
        except Exception as e:
            logger.error(f"Failed to start Web Remote on {self.host}:{self.port}: {e}")
            self._httpd = None
            return False

    def stop(self) -> None:
        """Cleanly stop the HTTP server."""
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception as e:
                logger.debug(f"Error closing web server: {e}")
            self._httpd = None
            logger.info("Web Remote stopped.")

    def get_access_url(self) -> str:
        ip = get_local_ip()
        return f"http://{ip}:{self.port}"

    def _get_system_snapshot(self) -> Dict[str, Any]:
        now = time.time()
        if now - self._cached_sys_time >= 2.0 or not self._cached_sys:
            used_mb, total_mb, ram_pct = SystemInfo.get_ram_usage()
            self._cached_sys = {
                "cpu_temp": SystemInfo.get_cpu_temp(),
                "ram_used_mb": used_mb,
                "ram_total_mb": total_mb,
                "ram_pct": ram_pct,
                "cpu_load_pct": SystemInfo.get_cpu_load_pct(),
                "time": SystemInfo.get_time_string(),
                "hostname": self._hostname,
                "ip": get_local_ip(),
                "port": self.port,
                "headless": getattr(self.app, "headless", False),
            }
            self._cached_sys_time = now
        return dict(self._cached_sys)

    def build_state(self) -> Dict[str, Any]:
        """Build complete JSON state snapshot for the Web UI."""
        app = self.app
        current = app.playlist.current_track
        current_dict = None
        if current is not None:
            current_dict = current.to_dict()
            current_dict["duration_str"] = current.duration_str

        queue_list = []
        for idx, t in enumerate(app.playlist.queue):
            item = t.to_dict()
            item["index"] = idx
            item["duration_str"] = t.duration_str
            item["is_current"] = (idx == app.playlist.current_index)
            queue_list.append(item)

        duration = app.player.duration or (current.duration if current else 0)
        wifi_status = app.wifi.get_status()
        bt = app.bluetooth

        return {
            "app": {
                "name": APP_NAME,
                "version": APP_VERSION,
                "headless": getattr(app, "headless", False),
                "ad_free": True,
            },
            "player": {
                "is_playing": app.player.is_playing,
                "is_paused": app.player.is_paused,
                "is_buffering": app.player.is_buffering,
                "current_time": round(app.player.current_time, 1),
                "duration": round(float(duration), 1),
                "volume": app.player.volume,
                "alsa_device": app.player.alsa_device,
                "has_mpv": app.player.has_mpv,
            },
            "current_track": current_dict,
            "playlist": {
                "current_index": app.playlist.current_index,
                "repeat_mode": app.playlist.repeat_mode,
                "shuffle": app.playlist.shuffle,
                "queue": queue_list,
            },
            "wifi": {
                **wifi_status,
                "message": self.last_wifi_message,
            },
            "bluetooth": {
                **bt.last_status,
                "is_scanning": bt.is_scanning,
                "is_connecting": bt.is_connecting,
                "message": self.last_bluetooth_message,
            },
            "system": self._get_system_snapshot(),
        }
