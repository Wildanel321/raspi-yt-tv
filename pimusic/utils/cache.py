"""
Pi Music - Cache & Storage Manager
Handles thumbnail disk/memory caching and persistence of settings and queue.
"""

import hashlib
import json
import os
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional
import pygame

from config import THUMBNAIL_DIR, MAX_CACHE_THUMBNAILS, SETTINGS_FILE, QUEUE_FILE
from pimusic.utils.logger import get_logger

logger = get_logger("CacheManager")

class ThumbnailCache:
    """Thread-safe LRU cache for pygame thumbnail surfaces."""
    def __init__(self, max_items: int = MAX_CACHE_THUMBNAILS):
        self.max_items = max_items
        self._memory_cache: OrderedDict[str, pygame.Surface] = OrderedDict()

    def _url_to_path(self, url: str) -> Path:
        """Hash URL into a local filename."""
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        return THUMBNAIL_DIR / f"{url_hash}.jpg"

    def get(self, url: str, target_size: Optional[tuple[int, int]] = None) -> Optional[pygame.Surface]:
        """Fetch surface from memory or disk cache."""
        if not url:
            return None

        cache_key = f"{url}_{target_size}" if target_size else url

        # 1. Check RAM cache
        if cache_key in self._memory_cache:
            self._memory_cache.move_to_end(cache_key)
            return self._memory_cache[cache_key]

        # 2. Check Disk cache
        file_path = self._url_to_path(url)
        if file_path.exists():
            try:
                surface = pygame.image.load(str(file_path)).convert_alpha()
                if target_size:
                    surface = pygame.transform.smoothscale(surface, target_size)
                self.put(cache_key, surface)
                return surface
            except Exception as e:
                logger.warning(f"Failed to load cached thumbnail {file_path}: {e}")
                try:
                    file_path.unlink()
                except OSError:
                    pass

        return None

    def put(self, key: str, surface: pygame.Surface) -> None:
        """Store surface in memory cache with LRU eviction."""
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
        self._memory_cache[key] = surface
        if len(self._memory_cache) > self.max_items:
            self._memory_cache.popitem(last=False)

    def download_and_cache(self, url: str, target_size: Optional[tuple[int, int]] = None) -> Optional[pygame.Surface]:
        """Download image from url, save to disk, and return pygame.Surface."""
        if not url:
            return None

        cached = self.get(url, target_size)
        if cached:
            return cached

        file_path = self._url_to_path(url)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Linux; Android) PiMusic/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                img_data = response.read()

            with open(file_path, "wb") as f:
                f.write(img_data)

            surface = pygame.image.load(str(file_path)).convert_alpha()
            if target_size:
                surface = pygame.transform.smoothscale(surface, target_size)

            cache_key = f"{url}_{target_size}" if target_size else url
            self.put(cache_key, surface)
            return surface
        except Exception as e:
            logger.debug(f"Failed to download thumbnail {url}: {e}")
            return None


def save_json(filepath: Path, data: Any) -> bool:
    """Save data to JSON file atomically."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        temp_file = filepath.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(filepath)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {e}")
        return False


def load_json(filepath: Path, default: Any = None) -> Any:
    """Safely load JSON file or return default."""
    if not filepath.exists():
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading JSON from {filepath}: {e}")
        return default
