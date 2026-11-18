#!/usr/bin/env python3
"""
Pi Music - Lightweight YouTube Music Player for Raspberry Pi 3
Entry point script.
"""

import argparse
import os
import signal
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import WEB_PORT
from pimusic.ui.app import App
from pimusic.utils.logger import get_logger

logger = get_logger("Main")

def main():
    parser = argparse.ArgumentParser(description="Pi Music - YouTube Music Player for Raspberry Pi")
    parser.add_argument("--fullscreen", action="store_true", help="Launch in fullscreen mode")
    parser.add_argument("--windowed", action="store_true", help="Force windowed mode for development")
    parser.add_argument("--headless", action="store_true", help="Run without HDMI/GUI display (Web Remote only)")
    parser.add_argument("--no-cursor", action="store_true", help="Hide mouse cursor (for touchscreen)")
    parser.add_argument("--alsa-device", type=str, default="alsa/default", help="ALSA audio output device")
    parser.add_argument("--web-port", type=int, default=WEB_PORT, help=f"Web remote HTTP port (default: {WEB_PORT})")
    parser.add_argument("--no-web", action="store_true", help="Disable built-in web remote server")
    args = parser.parse_args()

    # Default to fullscreen if running on Linux without explicit --windowed or --headless flag
    is_linux = sys.platform.startswith("linux")
    use_fullscreen = (args.fullscreen or (is_linux and not args.windowed)) and not args.headless

    logger.info("Starting Pi Music...")
    if args.headless:
        logger.info(f"Display Mode: Headless (Web Remote on port {args.web_port})")
    else:
        logger.info(f"Display Mode: {'Fullscreen' if use_fullscreen else 'Windowed (480x320)'}")

    app = App(
        fullscreen=use_fullscreen,
        headless=args.headless,
        enable_web=not args.no_web,
        web_port=args.web_port,
        alsa_device=args.alsa_device,
    )

    if not app.headless and (args.no_cursor or (is_linux and not args.windowed)):
        import pygame
        pygame.mouse.set_visible(False)

    # Register graceful signal handlers
    def _sig_handler(signum, frame):
        logger.info(f"Received signal {signum}. Stopping...")
        app.is_running = False

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as e:
        logger.exception(f"Unhandled exception in Pi Music: {e}")
    finally:
        app.shutdown()
        logger.info("Pi Music exited cleanly.")

if __name__ == "__main__":
    main()
