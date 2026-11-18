"""
Unit tests for Pi Music core components.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from config import SCREEN_WIDTH, SCREEN_HEIGHT
from pimusic.core.youtube import Track
from pimusic.core.playlist import PlaylistManager
from pimusic.core.system_info import SystemInfo
from pimusic.core.wifi import WifiManager, WifiNetwork
from pimusic.core.bluetooth import BluetoothManager, BluetoothDevice

class TestPiMusicCore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_queue_file = config.QUEUE_FILE
        import pimusic.core.playlist as playlist_mod
        self.orig_pm_queue_file = playlist_mod.QUEUE_FILE
        tmp_queue = Path(self.temp_dir.name) / "test_queue.json"
        config.QUEUE_FILE = tmp_queue
        playlist_mod.QUEUE_FILE = tmp_queue

    def tearDown(self):
        import pimusic.core.playlist as playlist_mod
        config.QUEUE_FILE = self.orig_queue_file
        playlist_mod.QUEUE_FILE = self.orig_pm_queue_file
        self.temp_dir.cleanup()

    def test_dimensions(self):
        self.assertEqual(SCREEN_WIDTH, 480)
        self.assertEqual(SCREEN_HEIGHT, 320)

    def test_track_formatting(self):
        t1 = Track(
            video_id="test1234",
            title="Bohemian Rhapsody",
            artist="Queen",
            duration=354,
            thumbnail_url="https://example.com/thumb.jpg"
        )
        self.assertEqual(t1.duration_str, "05:54")
        d = t1.to_dict()
        self.assertEqual(d["video_id"], "test1234")
        t2 = Track.from_dict(d)
        self.assertEqual(t2.title, "Bohemian Rhapsody")

    def test_playlist_manager(self):
        queue_path = Path(self.temp_dir.name) / "test_queue.json"
        pm = PlaylistManager(queue_file=queue_path)
        pm.clear()
        self.assertEqual(len(pm.queue), 0)
        self.assertIsNone(pm.current_track)

        t1 = Track("1", "Song 1", "Artist 1", 180, "")
        t2 = Track("2", "Song 2", "Artist 2", 200, "")
        t3 = Track("3", "Song 3", "Artist 3", 220, "")

        pm.add_track(t1)
        pm.add_track(t2)
        pm.add_track(t3)
        self.assertEqual(len(pm.queue), 3)

        # Jump to track 0
        pm.jump_to(0)
        self.assertEqual(pm.current_track.video_id, "1")

        # Next
        next_t = pm.next_track()
        self.assertIsNotNone(next_t)
        self.assertEqual(next_t.video_id, "2")

        # Previous
        prev_t = pm.previous_track()
        self.assertIsNotNone(prev_t)
        self.assertEqual(prev_t.video_id, "1")

        # Play now insertion
        t_now = Track("now", "Song Now", "Artist Now", 150, "")
        pm.play_now(t_now)
        self.assertEqual(pm.current_track.video_id, "now")

        # Remove track
        pm.remove_at(0)
        self.assertEqual(len(pm.queue), 3)

    def test_system_info(self):
        time_str = SystemInfo.get_time_string()
        self.assertTrue(":" in time_str)
        used, total, pct = SystemInfo.get_ram_usage()
        self.assertGreater(total, 0)
        self.assertGreaterEqual(pct, 0.0)

    def test_wifi_manager(self):
        wm = WifiManager()
        status = wm.get_status()
        self.assertIn("connected", status)
        self.assertIn("ssid", status)
        self.assertIn("state", status)
        self.assertIn("portal_detected", status)

        # Test disconnect / reconnect callbacks in simulation mode
        results = []
        wm.disconnect_async(lambda success, msg: results.append(("disconnect", success)))
        wm.reconnect_async(lambda success, msg: results.append(("reconnect", success)))
        wm.check_captive_portal_async(lambda detected, url: results.append(("portal", detected)))

        # Wait briefly for worker threads
        import time
        time.sleep(1.2)
        actions = [r[0] for r in results]
        self.assertIn("disconnect", actions)
        self.assertIn("reconnect", actions)
        self.assertIn("portal", actions)

        net_open = WifiNetwork("Guest", 70, "Open")
        net_sec = WifiNetwork("Secure", 80, "WPA2")
        self.assertTrue(net_open.is_open)
        self.assertFalse(net_sec.is_open)

    def test_bluetooth_manager(self):
        bm = BluetoothManager()
        # Test default audio output preference
        self.assertIn(bm.audio_output_mode, ["jack", "bluetooth"])
        bm.save_audio_output_pref("bluetooth")
        self.assertEqual(bm.audio_output_mode, "bluetooth")
        bm.save_audio_output_pref("jack")
        self.assertEqual(bm.audio_output_mode, "jack")

        # Test BluetoothDevice representation and status
        d1 = BluetoothDevice("FC:58:FA:12:34:56", "JBL Flip 5", paired=True, connected=False)
        self.assertEqual(d1.mac, "FC:58:FA:12:34:56")
        self.assertEqual(d1.name, "JBL Flip 5")
        self.assertTrue(d1.paired)
        self.assertFalse(d1.connected)

        # Test simulation devices
        bm._mock_simulation_devices()
        devs = bm.get_devices()
        self.assertGreater(len(devs), 0)

        # Test connect / disconnect async
        results = []
        bm.connect_device_async("FC:58:FA:12:34:56", lambda success, msg: results.append(("connect", success)))
        import time
        time.sleep(1.2)
        self.assertTrue(any(r[0] == "connect" for r in results))

        bm.disconnect_device_async("FC:58:FA:12:34:56", lambda success, msg: results.append(("disconnect", success)))
        time.sleep(0.5)
        self.assertTrue(any(r[0] == "disconnect" for r in results))

    def test_headless_web_remote(self):
        import json
        import urllib.request
        import urllib.error
        from pimusic.ui.app import App

        app = App(headless=True, enable_web=True, web_port=0)
        try:
            self.assertTrue(app.headless)
            self.assertIsNotNone(app.web_server)
            port = app.web_server.port
            self.assertGreater(port, 0)
            base = f"http://127.0.0.1:{port}"

            # 1. Serve index HTML
            with urllib.request.urlopen(f"{base}/", timeout=3) as resp:
                self.assertEqual(resp.status, 200)
                html = resp.read().decode("utf-8")
                self.assertIn("Pi Music Remote", html)

            # 2. Fetch state JSON
            with urllib.request.urlopen(f"{base}/api/state", timeout=3) as resp:
                self.assertEqual(resp.status, 200)
                state = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(state["app"]["headless"])
                self.assertIn("player", state)
                self.assertIn("playlist", state)
                self.assertIn("system", state)

            # 3. Add track to queue via POST
            sample_track = {
                "video_id": "abc123xyz",
                "title": "Test Track",
                "artist": "Test Artist",
                "duration": 215,
                "thumbnail_url": "",
                "webpage_url": "https://www.youtube.com/watch?v=abc123xyz"
            }
            req = urllib.request.Request(
                f"{base}/api/queue/add",
                data=json.dumps({"track": sample_track}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(res["ok"])
                self.assertEqual(res["queue_length"], 1)

            # 4. Volume, repeat, shuffle, audio output endpoints
            for endpoint, payload in [
                ("/api/player/volume", {"volume": 55}),
                ("/api/player/repeat", {"mode": "all"}),
                ("/api/player/shuffle", {"enabled": True}),
                ("/api/bluetooth/output", {"mode": "jack"}),
                ("/api/queue/clear", {}),
            ]:
                req = urllib.request.Request(
                    f"{base}{endpoint}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(res["ok"])

            self.assertEqual(app.player.volume, 55)
            self.assertEqual(app.playlist.repeat_mode, "all")
            self.assertTrue(app.playlist.shuffle)
            self.assertEqual(len(app.playlist.queue), 0)

            # 4b. Wi-Fi Selector endpoints (saved profiles + save + connect-saved + forget)
            req = urllib.request.Request(
                f"{base}/api/wifi/save",
                data=json.dumps({"ssid": "Cafe-Test", "password": "secret123"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.assertTrue(json.loads(resp.read().decode("utf-8"))["ok"])
            import time as _t
            _t.sleep(0.5)
            with urllib.request.urlopen(f"{base}/api/wifi/networks", timeout=3) as resp:
                wifi_data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("saved", wifi_data)
                self.assertTrue(any(s["ssid"] == "Cafe-Test" for s in wifi_data["saved"]))

            # 5. Unknown endpoint returns 404
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"{base}/api/does-not-exist", timeout=3)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            app.shutdown()

if __name__ == "__main__":
    unittest.main()
