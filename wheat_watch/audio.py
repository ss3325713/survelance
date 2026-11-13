"""Laptop-side audio playback engine for Wheat Watch.

Plays sounds independently of the browser via system audio (paplay / aplay).
Enforces configurable per-category cooldowns to prevent repetitive fatigue.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from wheat_watch.config import app_config
from wheat_watch.broadcaster import broadcaster

logger = logging.getLogger("wheat_watch.audio")

SOUNDS_DIR = Path("sounds")


class AudioManager:
    """Manages system-level audio playback and category cooldowns."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_played: Dict[str, float] = {}
        self._player = self._detect_player()
        logger.info(f"AudioManager initialized using player: {self._player}")

    def _detect_player(self) -> Optional[str]:
        for candidate in ["paplay", "aplay", "pw-play", "mpv"]:
            if shutil.which(candidate):
                return candidate
        return None

    def get_sound_file_for_category(self, category: str) -> Optional[Path]:
        cat_lower = category.lower()
        if "monkey" in cat_lower:
            f = SOUNDS_DIR / "monkey.wav"
        elif "person" in cat_lower:
            f = SOUNDS_DIR / "person.wav"
        elif "animal" in cat_lower or "bird" in cat_lower:
            f = SOUNDS_DIR / "animal.wav"
        else:
            f = SOUNDS_DIR / "motion.wav"

        return f if f.exists() else None

    def can_play(self, category: str) -> bool:
        """Check if sound is enabled, cooldown has expired, and category is authorized for audio alarm."""
        if not app_config.alarm.get("sound_enabled", True):
            return False

        # Target classification policy: suppress ambient/static noise unless explicitly enabled
        if category == "General motion" and not app_config.alarm.get("alarm_on_general_motion", False):
            return False
        if category == "Unknown object" and not app_config.alarm.get("alarm_on_unknown_objects", False):
            return False

        alert_cats = app_config.alarm.get("alert_categories")
        if alert_cats is not None and category not in alert_cats:
            return False

        cooldowns = app_config.alarm.get("cooldowns", {})
        cd = cooldowns.get(category, 20.0)

        with self._lock:
            last = self._last_played.get(category, 0.0)
            now = time.time()
            return (now - last) >= cd

    def play_alert(self, category: str, force: bool = False) -> bool:
        """Play alert sound for category if not suppressed by cooldown."""
        if not force and not self.can_play(category):
            logger.debug(f"Audio alert for '{category}' suppressed by cooldown.")
            return False

        sound_file = self.get_sound_file_for_category(category)
        if not sound_file:
            logger.warning(f"No sound file found for category '{category}'")
            return False

        with self._lock:
            self._last_played[category] = time.time()

        self._spawn_playback(str(sound_file))
        logger.info(f"Playing laptop alarm for category: '{category}' ({sound_file.name})")
        broadcaster.broadcast_sync("alarm", {"category": category, "file": sound_file.name, "forced": force})
        return True

    def play_disconnect_alert(self) -> bool:
        """Trigger camera disconnection warning sound on laptop speakers."""
        disconnect_file = SOUNDS_DIR / "disconnect.wav"
        if not disconnect_file.exists():
            disconnect_file = SOUNDS_DIR / "test.wav"

        # Cooldown: debounce disconnect alert at most once every 10 seconds
        with self._lock:
            last = self._last_played.get("camera_disconnect", 0.0)
            now = time.time()
            if now - last < 10.0:
                return False
            self._last_played["camera_disconnect"] = now

        if disconnect_file.exists():
            logger.warning("Playing laptop speaker camera-disconnected alert sound.")
            self._spawn_playback(str(disconnect_file))
            broadcaster.broadcast_sync("camera_disconnected", {
                "message": "Camera disconnected! Retrying connection...",
                "timestamp": time.time(),
            })
            return True
        return False

    def test_alarm(self) -> bool:
        """Trigger test sound immediately."""
        test_file = SOUNDS_DIR / "test.wav"
        if not test_file.exists():
            test_file = SOUNDS_DIR / "motion.wav"

        if test_file.exists():
            logger.info("Playing manual test alarm sound...")
            self._spawn_playback(str(test_file))
            broadcaster.broadcast_sync("alarm", {"category": "Test", "file": test_file.name, "forced": True})
            return True
        logger.error("Test sound file does not exist.")
        return False

    def _spawn_playback(self, filepath: str) -> None:
        if not self._player:
            logger.warning("No audio player binary found on system.")
            return

        def _run() -> None:
            try:
                cmd = [self._player, filepath]
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5.0,
                    check=False,
                )
            except Exception as e:
                logger.error(f"Error during audio playback: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()


# Global audio manager instance
audio_manager = AudioManager()
