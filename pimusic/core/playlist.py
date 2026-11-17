"""
Pi Music - Playlist & Queue Manager
Handles track ordering, queue additions, next/previous navigation,
shuffle/repeat modes, and state persistence.
"""

import random
from typing import List, Optional
from config import QUEUE_FILE
from pimusic.core.youtube import Track
from pimusic.utils.cache import save_json, load_json
from pimusic.utils.logger import get_logger

logger = get_logger("PlaylistManager")

class PlaylistManager:
    """Manages the playback queue and track progression."""

    def __init__(self, queue_file=None):
        self.queue_file = queue_file or QUEUE_FILE
        self.queue: List[Track] = []
        self.current_index: int = -1
        self.repeat_mode: str = "off"  # "off", "all", "one"
        self.shuffle: bool = False
        self._load_saved_queue()

    def _load_saved_queue(self):
        """Load queue from disk if available."""
        data = load_json(self.queue_file)
        if data and isinstance(data, dict):
            raw_queue = data.get("queue", [])
            self.queue = [Track.from_dict(t) for t in raw_queue if isinstance(t, dict)]
            self.current_index = data.get("current_index", -1)
            if self.current_index >= len(self.queue):
                self.current_index = -1
            logger.info(f"Loaded {len(self.queue)} tracks from saved queue.")

    def save_queue(self):
        """Save current queue to disk."""
        data = {
            "queue": [t.to_dict() for t in self.queue],
            "current_index": self.current_index
        }
        save_json(self.queue_file, data)

    @property
    def current_track(self) -> Optional[Track]:
        """Returns the currently active track or None."""
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def add_track(self, track: Track) -> int:
        """Append track to queue. Returns track index."""
        self.queue.append(track)
        self.save_queue()
        return len(self.queue) - 1

    def play_now(self, track: Track) -> Track:
        """Immediately insert and switch to track."""
        if self.current_index >= 0 and self.current_index < len(self.queue):
            self.queue.insert(self.current_index + 1, track)
            self.current_index += 1
        else:
            self.queue.append(track)
            self.current_index = len(self.queue) - 1
        self.save_queue()
        return track

    def play_next(self, track: Track) -> None:
        """Queue track to play immediately after the current track."""
        if self.current_index >= 0 and self.current_index < len(self.queue):
            self.queue.insert(self.current_index + 1, track)
        else:
            self.queue.append(track)
            if self.current_index == -1:
                self.current_index = 0
        self.save_queue()

    def next_track(self) -> Optional[Track]:
        """Advance to next track according to repeat/shuffle rules."""
        if not self.queue:
            return None

        if self.repeat_mode == "one":
            return self.current_track

        if self.shuffle and len(self.queue) > 1:
            indices = [i for i in range(len(self.queue)) if i != self.current_index]
            self.current_index = random.choice(indices)
        else:
            if self.current_index + 1 < len(self.queue):
                self.current_index += 1
            else:
                if self.repeat_mode == "all":
                    self.current_index = 0
                else:
                    return None

        self.save_queue()
        return self.current_track

    def previous_track(self) -> Optional[Track]:
        """Go back to previous track in queue."""
        if not self.queue:
            return None

        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = 0

        self.save_queue()
        return self.current_track

    def jump_to(self, index: int) -> Optional[Track]:
        """Jump directly to track at index."""
        if 0 <= index < len(self.queue):
            self.current_index = index
            self.save_queue()
            return self.current_track
        return None

    def remove_at(self, index: int) -> bool:
        """Remove track at specified index."""
        if 0 <= index < len(self.queue):
            del self.queue[index]
            if self.current_index >= len(self.queue):
                self.current_index = len(self.queue) - 1
            self.save_queue()
            return True
        return False

    def move(self, from_idx: int, to_idx: int) -> bool:
        """Move track from one position to another in queue."""
        if 0 <= from_idx < len(self.queue) and 0 <= to_idx < len(self.queue):
            track = self.queue.pop(from_idx)
            self.queue.insert(to_idx, track)
            if self.current_index == from_idx:
                self.current_index = to_idx
            self.save_queue()
            return True
        return False

    def clear(self):
        """Clear all tracks from the queue."""
        self.queue.clear()
        self.current_index = -1
        self.save_queue()
