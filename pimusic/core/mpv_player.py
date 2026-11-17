"""
Pi Music - MPV Player IPC Controller
Controls MPV daemon over UNIX domain socket IPC (or named pipe).
Ensures zero-browser, ultra-lightweight, audio-only playback on Raspberry Pi.
"""

import json
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
from typing import Any, Callable, Dict, Optional

from config import MPV_SOCKET_PATH, IS_WINDOWS, DEFAULT_VOLUME
from pimusic.utils.logger import get_logger

logger = get_logger("MPVPlayer")

class MPVPlayer:
    """Controls an MPV process via its JSON IPC interface."""

    def __init__(self, alsa_device: str = "alsa/default"):
        self.alsa_device = alsa_device
        self.mpv_process: Optional[subprocess.Popen] = None
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None

        # Playback State
        self.is_playing = False
        self.is_paused = False
        self.current_time = 0.0
        self.duration = 0.0
        self.volume = DEFAULT_VOLUME
        self.is_buffering = False
        self.current_stream_url: Optional[str] = None
        self.has_mpv = shutil.which("mpv") is not None

        # Callbacks
        self.on_track_end: Optional[Callable[[], None]] = None
        self.on_state_change: Optional[Callable[[], None]] = None

        # Simulation fallback state (if MPV not installed)
        self._sim_thread: Optional[threading.Thread] = None

        if self.has_mpv:
            self._start_mpv_daemon()
            self._connect_ipc()
            self._start_listener()
        else:
            logger.warning("MPV executable not found. Running in simulation mode.")
            self._start_simulation()

    def _start_mpv_daemon(self):
        """Spawns MPV process configured for low-memory, audio-only playback."""
        # Clean up stale socket file on Linux
        if not IS_WINDOWS and os.path.exists(MPV_SOCKET_PATH):
            try:
                os.unlink(MPV_SOCKET_PATH)
            except OSError:
                pass

        mpv_cmd = [
            "mpv",
            "--idle=yes",
            f"--input-ipc-server={MPV_SOCKET_PATH}",
            "--no-video",
            "--no-terminal",
            "--really-quiet",
            f"--volume={self.volume}",
            "--audio-buffer=0.5",
            "--demuxer-max-bytes=10M",
            "--demuxer-readahead-secs=10",
        ]

        if not IS_WINDOWS:
            mpv_cmd.append(f"--ao={self.alsa_device}")

        try:
            logger.info("Spawning MPV background process...")
            self.mpv_process = subprocess.Popen(
                mpv_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Failed to spawn MPV: {e}")

    def _connect_ipc(self) -> bool:
        """Connect to the MPV IPC socket."""
        if IS_WINDOWS:
            return False

        max_retries = 15
        for i in range(max_retries):
            if os.path.exists(MPV_SOCKET_PATH):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(2.0)
                    s.connect(MPV_SOCKET_PATH)
                    self._socket = s
                    self._connected = True
                    logger.info("Connected to MPV IPC socket successfully.")
                    self._observe_properties()
                    return True
                except (socket.error, OSError) as e:
                    time.sleep(0.2)
            else:
                time.sleep(0.2)

        logger.warning("Could not connect to MPV IPC socket. Falling back to simulation.")
        self.has_mpv = False
        self._start_simulation()
        return False

    def _send_command(self, command: list) -> Optional[Dict[str, Any]]:
        """Send a JSON command to MPV over the socket."""
        if not self._connected or not self._socket:
            return None

        msg = json.dumps({"command": command}) + "\n"
        with self._lock:
            try:
                self._socket.sendall(msg.encode("utf-8"))
            except Exception as e:
                logger.error(f"Error sending command to MPV: {e}")
                self._connected = False
                return None
        return None

    def _observe_properties(self):
        """Observe relevant MPV properties for real-time status updates."""
        properties = [
            (1, "time-pos"),
            (2, "duration"),
            (3, "pause"),
            (4, "idle-active"),
            (5, "core-idle")
        ]
        for req_id, prop in properties:
            self._send_command(["observe_property", req_id, prop])

    def _start_listener(self):
        """Thread that reads JSON messages and events from MPV."""
        def _loop():
            buffer = ""
            while not self._stop_event.is_set() and self._connected and self._socket:
                try:
                    data = self._socket.recv(4096)
                    if not data:
                        break
                    buffer += data.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._handle_ipc_message(line)
                except socket.timeout:
                    continue
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.debug(f"MPV IPC read error: {e}")
                    break

        self._listener_thread = threading.Thread(target=_loop, daemon=True)
        self._listener_thread.start()

    def _handle_ipc_message(self, line: str):
        """Parse incoming JSON IPC messages from MPV."""
        try:
            msg = json.loads(line)
            event = msg.get("event")

            if event == "property-change":
                name = msg.get("name")
                val = msg.get("data")
                if name == "time-pos" and val is not None:
                    self.current_time = float(val)
                elif name == "duration" and val is not None:
                    self.duration = float(val)
                elif name == "pause":
                    self.is_paused = bool(val)
                elif name == "core-idle":
                    self.is_buffering = bool(val) and self.is_playing and not self.is_paused
            elif event == "end-file":
                reason = msg.get("reason")
                logger.info(f"MPV track ended: reason={reason}")
                self.is_playing = False
                self.current_time = 0.0
                if reason in ("eof", "stop") and self.on_track_end:
                    self.on_track_end()
            elif event == "playback-restart":
                self.is_playing = True
                self.is_paused = False
                self.is_buffering = False
        except Exception:
            pass

    def play_url(self, stream_url: str):
        """Load and start playing an audio stream URL."""
        logger.info("MPV: Loading audio stream...")
        self.current_stream_url = stream_url
        self.is_playing = True
        self.is_paused = False
        self.current_time = 0.0

        if self.has_mpv and self._connected:
            self._send_command(["loadfile", stream_url, "replace"])
            self._send_command(["set_property", "pause", False])
        else:
            # Simulation playback
            self.duration = 240.0
            self.current_time = 0.0

    def set_audio_output(self, mode: str, bluetooth_mac: Optional[str] = None):
        """
        Switches audio output device between 'jack' (3.5mm analog) and 'bluetooth'.
        Updates the running MPV daemon via IPC or restarts with the new device.
        """
        if mode == "bluetooth":
            if bluetooth_mac:
                self.alsa_device = f"alsa/bluealsa:DEV={bluetooth_mac.upper()},PROFILE=a2dp"
            else:
                self.alsa_device = "alsa/bluealsa"
        else:
            self.alsa_device = "alsa/default"

        logger.info(f"Setting MPV audio device to {self.alsa_device}")
        if self._connected:
            self._send_command(["set_property", "audio-device", self.alsa_device])

    def pause(self):
        """Pause playback."""
        self.is_paused = True
        if self.has_mpv and self._connected:
            self._send_command(["set_property", "pause", True])

    def resume(self):
        """Resume playback."""
        self.is_paused = False
        if self.has_mpv and self._connected:
            self._send_command(["set_property", "pause", False])

    def toggle_pause(self):
        """Toggle play/pause state."""
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    def stop(self):
        """Stop playback completely."""
        self.is_playing = False
        self.is_paused = False
        self.current_time = 0.0
        if self.has_mpv and self._connected:
            self._send_command(["stop"])

    def seek(self, target_seconds: float):
        """Seek to absolute position in seconds."""
        target_seconds = max(0.0, min(self.duration or 3600.0, target_seconds))
        self.current_time = target_seconds
        if self.has_mpv and self._connected:
            self._send_command(["seek", target_seconds, "absolute"])

    def set_volume(self, volume_pct: int):
        """Set volume percentage (0 - 100)."""
        self.volume = max(0, min(100, volume_pct))
        if self.has_mpv and self._connected:
            self._send_command(["set_property", "volume", self.volume])

    def _start_simulation(self):
        """Timer simulation for environments where MPV isn't available."""
        def _sim_loop():
            while not self._stop_event.is_set():
                if self.is_playing and not self.is_paused:
                    self.current_time += 1.0
                    if self.duration > 0 and self.current_time >= self.duration:
                        self.is_playing = False
                        self.current_time = 0.0
                        if self.on_track_end:
                            self.on_track_end()
                time.sleep(1.0)

        self._sim_thread = threading.Thread(target=_sim_loop, daemon=True)
        self._sim_thread.start()

    def shutdown(self):
        """Stop player, terminate MPV process, and close sockets."""
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass

        if self.mpv_process:
            try:
                self.mpv_process.terminate()
                self.mpv_process.wait(timeout=1.0)
            except Exception:
                try:
                    self.mpv_process.kill()
                except Exception:
                    pass

        if not IS_WINDOWS and os.path.exists(MPV_SOCKET_PATH):
            try:
                os.unlink(MPV_SOCKET_PATH)
            except OSError:
                pass
        logger.info("MPV Player shutdown complete.")
