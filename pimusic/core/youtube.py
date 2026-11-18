"""
Pi Music - YouTube Search and Stream Resolver
Uses yt-dlp to perform fast, lightweight searches and resolve direct audio stream URLs.
All network operations run in background threads to keep Pygame UI responsive.
"""

import concurrent.futures
import time
from typing import Callable, Dict, List, Optional

from config import MAX_SEARCH_RESULTS
from pimusic.utils.logger import get_logger

logger = get_logger("YouTubeService")

class Track:
    """Represents a playable YouTube audio track."""
    def __init__(
        self,
        video_id: str,
        title: str,
        artist: str,
        duration: int,
        thumbnail_url: str,
        webpage_url: str = "",
        stream_url: str = ""
    ):
        self.video_id = video_id
        self.title = title or "Unknown Title"
        self.artist = artist or "Unknown Artist"
        self.duration = duration or 0  # Duration in seconds
        self.thumbnail_url = thumbnail_url
        self.webpage_url = webpage_url or f"https://www.youtube.com/watch?v={video_id}"
        self.stream_url = stream_url
        self.resolved_at = 0.0

    @property
    def duration_str(self) -> str:
        """Formats seconds into MM:SS or HH:MM:SS."""
        if self.duration <= 0:
            return "--:--"
        mins, secs = divmod(int(self.duration), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def to_dict(self) -> Dict[str, any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "artist": self.artist,
            "duration": self.duration,
            "thumbnail_url": self.thumbnail_url,
            "webpage_url": self.webpage_url
        }

    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> "Track":
        return cls(
            video_id=data.get("video_id", ""),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            duration=data.get("duration", 0),
            thumbnail_url=data.get("thumbnail_url", ""),
            webpage_url=data.get("webpage_url", "")
        )

    def is_stream_expired(self) -> bool:
        """YouTube direct audio URLs typically expire after 5-6 hours."""
        if not self.stream_url:
            return True
        return (time.time() - self.resolved_at) > 14400  # 4 hours


class YouTubeService:
    """Handles searching YouTube and extracting direct audio streams via yt-dlp."""

    def __init__(self):
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._active_search_future = None
        self._active_resolve_future = None

        # yt-dlp options optimized for low memory & CPU on Pi 3
        self._base_ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "noplaylist": True,
            "source_address": "0.0.0.0",  # bind to ipv4
            "socket_timeout": 8,
        }

    def search_sync(self, query: str) -> List[Track]:
        """Synchronously search YouTube or resolve a direct YouTube URL."""
        query = query.strip()
        if not query:
            return []

        logger.info(f"Searching YouTube for: '{query}'...")
        tracks: List[Track] = []
        import yt_dlp

        is_url = query.startswith(("http://", "https://")) and (
            "youtube.com" in query or "youtu.be" in query or "music.youtube.com" in query
        )

        ydl_opts = dict(self._base_ydl_opts)
        ydl_opts["extract_flat"] = not is_url

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            target = query if is_url else f"ytsearch{MAX_SEARCH_RESULTS}:{query}"
            res = ydl.extract_info(target, download=False)
            if not res:
                return []

            entries = res.get("entries", []) if "entries" in res else [res]

            for entry in entries:
                if not entry:
                    continue
                video_id = entry.get("id") or entry.get("url")
                if not video_id:
                    continue

                title = entry.get("title", "Unknown Title")
                artist = entry.get("uploader") or entry.get("channel", "YouTube")
                duration = entry.get("duration", 0)

                thumb = ""
                thumbnails = entry.get("thumbnails", [])
                if thumbnails:
                    thumb = thumbnails[-1].get("url", "")
                elif entry.get("thumbnail"):
                    thumb = entry.get("thumbnail")
                else:
                    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                tracks.append(
                    Track(
                        video_id=video_id,
                        title=title,
                        artist=artist,
                        duration=int(duration) if duration else 0,
                        thumbnail_url=thumb,
                        webpage_url=f"https://www.youtube.com/watch?v={video_id}"
                    )
                )

        logger.info(f"Found {len(tracks)} results for '{query}'")
        return tracks

    def search_async(
        self,
        query: str,
        callback: Callable[[List[Track]], None],
        error_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """Search YouTube tracks in background thread."""
        query = query.strip()
        if not query:
            callback([])
            return

        def _worker():
            try:
                tracks = self.search_sync(query)
                callback(tracks)
            except Exception as e:
                logger.error(f"YouTube search error: {e}")
                if error_callback:
                    error_callback(str(e))
                else:
                    callback([])

        self._active_search_future = self._executor.submit(_worker)

    def resolve_audio_stream_async(
        self,
        track: Track,
        callback: Callable[[Track, Optional[str]], None]
    ) -> None:
        """Resolve direct audio streaming URL for MPV."""
        # Check if already resolved and valid
        if track.stream_url and not track.is_stream_expired():
            callback(track, track.stream_url)
            return

        def _worker():
            logger.info(f"Resolving audio stream for: {track.title} ({track.video_id})...")
            try:
                import yt_dlp

                # Select best audio stream (m4a or opus/webm)
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
                    "skip_download": True,
                    "noplaylist": True,
                    "socket_timeout": 10,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(track.webpage_url, download=False)
                    stream_url = info.get("url")

                    # Update track metadata if more details are now available
                    if not track.duration and info.get("duration"):
                        track.duration = int(info["duration"])
                    if (not track.artist or track.artist == "YouTube") and info.get("uploader"):
                        track.artist = info["uploader"]

                    track.stream_url = stream_url
                    track.resolved_at = time.time()

                    logger.info(f"Audio stream resolved for '{track.title}'")
                    callback(track, stream_url)
            except Exception as e:
                logger.error(f"Failed to resolve audio stream for {track.video_id}: {e}")
                callback(track, None)

        self._active_resolve_future = self._executor.submit(_worker)

    def shutdown(self):
        """Cleanly shutdown thread pool."""
        self._executor.shutdown(wait=False)
