"""
Pi Music - Configuration Module
Constants, paths, audio settings, and display configurations.
Optimized for Raspberry Pi 3 (1GB RAM) with 3.5" TFT SPI LCD (480x320).
"""

import os
import platform
from pathlib import Path

# Application Metadata
APP_NAME = "Pi Music"
APP_VERSION = "1.0.0"

# Display Configuration
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)

# Frame rate configuration (Pi 3 CPU & SPI bus optimization)
FPS_ACTIVE = 20     # Smooth response during touch interaction
FPS_IDLE = 8        # Minimal redraws when idle to stop SPI bus flicker

# Audio & Playback Configuration
DEFAULT_VOLUME = 70
VOLUME_STEP = 5
MAX_VOLUME = 100
MIN_VOLUME = 0

# ALSA Device on Raspberry Pi 3.5mm jack
# Defaults to "alsa/default" or "alsa/hw:Headphones" on modern Raspberry Pi OS
ALSA_DEFAULT_DEVICE = "alsa/default"
ALSA_JACK_DEVICE = "alsa/hw:Headphones"

# MPV IPC Socket
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    MPV_SOCKET_PATH = r"\\.\pipe\mpv-pimusic-socket"
else:
    MPV_SOCKET_PATH = "/tmp/mpv-pimusic.sock"

# File & Directory Paths
HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".config" / "pimusic"
CACHE_DIR = HOME_DIR / ".cache" / "pimusic"
THUMBNAIL_DIR = CACHE_DIR / "thumbnails"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
QUEUE_FILE = CONFIG_DIR / "queue.json"

# Memory optimization limits for Raspberry Pi 3 (1GB RAM)
MAX_CACHE_THUMBNAILS = 50          # Maximum thumbnails kept in memory
THUMBNAIL_SIZE_LARGE = (120, 120)  # Now Playing screen thumbnail
THUMBNAIL_SIZE_SMALL = (44, 44)    # Search & Queue list item thumbnail
MAX_SEARCH_RESULTS = 25            # Limit search results to keep memory low

# UI Colors (Modern Dark Theme)
COLOR_BG = (18, 18, 18)                 # Deep charcoal background #121212
COLOR_SURFACE = (30, 30, 30)           # Dark card/panel background #1E1E1E
COLOR_SURFACE_LIGHT = (48, 48, 48)     # Hover / active button background #303030
COLOR_SURFACE_BORDER = (60, 60, 60)    # Subtle border line #3C3C3C

COLOR_ACCENT = (255, 33, 33)           # YouTube Red Accent #FF2121
COLOR_ACCENT_HOVER = (255, 77, 77)     # Lighter Red #FF4D4D
COLOR_ACCENT_MUTED = (160, 24, 24)     # Dim Red for disabled/inactive #A01818

COLOR_TEXT_PRIMARY = (255, 255, 255)   # High-contrast white #FFFFFF
COLOR_TEXT_SECONDARY = (170, 170, 170) # Light grey for subtitle / metadata #AAAAAA
COLOR_TEXT_MUTED = (110, 110, 110)     # Dim grey for hints / inactive #6E6E6E

COLOR_SUCCESS = (76, 175, 80)          # Green for connected/success #4CAF50
COLOR_WARNING = (255, 179, 0)          # Amber for buffering/warning #FFB300
COLOR_DANGER = (244, 67, 54)           # Red for errors/alerts #F44336
COLOR_INFO = (33, 150, 243)            # Blue for informative tags #2196F3

# UI Layout Coordinates for 480x320 Screen
STATUS_BAR_HEIGHT = 24
NAV_BAR_HEIGHT = 38
CONTENT_Y = STATUS_BAR_HEIGHT
CONTENT_HEIGHT = SCREEN_HEIGHT - STATUS_BAR_HEIGHT - NAV_BAR_HEIGHT  # 320 - 24 - 38 = 258px

# Ensure directories exist
def init_directories():
    """Create essential config and cache directories."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
