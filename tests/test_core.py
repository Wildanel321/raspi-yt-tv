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

class TestPiMusicCore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_queue_file = config.QUEUE_FILE
        config.QUEUE_FILE = Path(self.temp_dir.name) / "test_queue.json"

    def tearDown(self):
        config.QUEUE_FILE = self.orig_queue_file
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

if __name__ == "__main__":
    unittest.main()
