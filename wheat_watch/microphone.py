"""Local microphone ambient audio activity analyzer for Wheat Watch.

Continuously captures and analyzes ambient sound locally using the laptop microphone.
Uses adaptive noise-floor filtering to detect meaningful sudden or sustained sounds
(footsteps, rustling, voices, banging) while rejecting continuous ambient noise
(fans, wind, environmental hum).

PRIVACY & PERFORMANCE GUARANTEES:
- All processing is completely local and in-memory.
- ZERO continuous audio recording or persistent storage.
- No speech recognition or conversation logging.
- Lightweight RMS energy and SNR ratio calculation using NumPy (<1% CPU).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.microphone")


class MicrophoneDetector:
    """Real-time local microphone activity detector with adaptive noise-floor tracking."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None

        # Audio capture settings
        self.sample_rate = 16000
        self.chunk_samples = 1600  # 100ms per window
        self.bytes_per_chunk = self.chunk_samples * 2  # 16-bit PCM mono = 2 bytes/sample

        # State and telemetry
        self.is_available = False
        self.has_activity = False
        self.current_rms = 0.0
        self.noise_floor = 1200.0
        self.snr = 1.0
        self.last_activity_time = 0.0
        self.last_error: Optional[str] = None
        self._sustained_window_count = 0
        self._reconnect_attempts = 0

        # Synthetic override for automated testing
        self._mock_activity_until = 0.0

    def start(self) -> None:
        """Start background audio capture and analysis thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="MicrophoneDetector",
            )
            self._thread.start()
            logger.info("MicrophoneDetector background thread started.")

    def stop(self) -> None:
        """Stop background audio capture cleanly."""
        with self._lock:
            self._running = False
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=1.0)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                self._process = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("MicrophoneDetector stopped.")

    def trigger_test_activity(self, duration_sec: float = 2.0, rms: float = 4500.0) -> None:
        """Synthetic activity trigger for deterministic verification."""
        with self._lock:
            now = time.time()
            self._mock_activity_until = now + duration_sec
            self.last_activity_time = now
            self.has_activity = True
            self.current_rms = rms
            self.snr = rms / max(1.0, self.noise_floor)
        logger.info(f"Synthetic microphone activity triggered ({duration_sec}s, RMS={rms}).")

    @property
    def is_active(self) -> bool:
        """Check if meaningful sound activity occurred recently."""
        now = time.time()
        with self._lock:
            if now < self._mock_activity_until:
                return True
            cooldown = float(app_config.audio_detection.get("activity_cooldown_sec", 1.0))
            return (now - self.last_activity_time) < cooldown

    def get_status(self) -> Dict[str, Any]:
        """Return real-time microphone diagnostics and noise telemetry."""
        with self._lock:
            active = self.is_active
            return {
                "enabled": bool(app_config.audio_detection.get("enabled", True)),
                "is_available": self.is_available,
                "has_activity": active,
                "current_rms": round(self.current_rms, 1),
                "noise_floor": round(self.noise_floor, 1),
                "snr": round(self.snr, 2),
                "last_activity_time": self.last_activity_time if self.last_activity_time > 0 else None,
                "last_error": self.last_error,
            }

    def _capture_loop(self) -> None:
        """Continuous audio streaming loop via arecord subprocess."""
        while self._running:
            if not app_config.audio_detection.get("enabled", True):
                time.sleep(0.5)
                continue

            arecord_bin = shutil.which("arecord")
            if not arecord_bin:
                with self._lock:
                    self.is_available = False
                    self.last_error = "arecord binary not found on system."
                logger.warning("arecord not found. Audio activity detection disabled.")
                time.sleep(5.0)
                continue

            cmd = [
                arecord_bin,
                "-q",
                "-t", "raw",
                "-f", "S16_LE",
                "-r", str(self.sample_rate),
                "-c", "1",
            ]

            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                with self._lock:
                    self.is_available = True
                    self.last_error = None
                    self._reconnect_attempts = 0
                logger.info(f"Connected to local microphone stream ({self.sample_rate} Hz, 16-bit mono).")

                while self._running:
                    if self._process.poll() is not None:
                        raise RuntimeError(f"arecord exited with code {self._process.returncode}")

                    raw_chunk = self._process.stdout.read(self.bytes_per_chunk)
                    if not raw_chunk or len(raw_chunk) < self.bytes_per_chunk:
                        time.sleep(0.01)
                        continue

                    # Analyze in-memory 100ms PCM window
                    self._process_audio_chunk(raw_chunk)

            except Exception as e:
                with self._lock:
                    self.is_available = False
                    self.last_error = str(e)
                    self._reconnect_attempts += 1
                logger.warning(f"Microphone stream error (attempt #{self._reconnect_attempts}): {e}. Retrying in 3s...")
                if self._process:
                    try:
                        self._process.terminate()
                    except Exception:
                        pass
                    self._process = None
                time.sleep(3.0)

    def _process_audio_chunk(self, raw_bytes: bytes) -> None:
        """Lightweight NumPy signal processing for 100ms window."""
        cfg = app_config.audio_detection
        spike_multiplier = float(cfg.get("spike_multiplier", 3.0))
        sustained_thresh = float(cfg.get("sustained_threshold_rms", 2500.0))
        min_trigger_rms = float(cfg.get("min_trigger_rms", 1800.0))
        alpha = float(cfg.get("noise_floor_alpha", 0.05))

        # Convert raw 16-bit PCM to float array
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(samples**2)))

        now = time.time()
        detected_event = False

        with self._lock:
            self.current_rms = rms
            self.snr = rms / max(1.0, self.noise_floor)

            # Check 1: Sudden sound spike above ambient noise floor
            is_spike = (rms >= self.noise_floor * spike_multiplier) and (rms >= min_trigger_rms)

            # Check 2: Sustained sound over multiple consecutive windows
            if rms >= sustained_thresh:
                self._sustained_window_count += 1
            else:
                self._sustained_window_count = 0

            is_sustained = (self._sustained_window_count >= int(cfg.get("consecutive_sustained_windows", 2)))

            if is_spike or is_sustained:
                detected_event = True
                self.last_activity_time = now
                self.has_activity = True
                reason = "SUDDEN_SPIKE" if is_spike else "SUSTAINED_SOUND"
                logger.debug(f"Audio activity detected: {reason} (RMS={rms:.1f}, NoiseFloor={self.noise_floor:.1f}, SNR={self.snr:.2f})")
            else:
                # Update background noise floor EMA only during non-active periods
                # (Prevents loud events from immediately skewing the ambient baseline)
                if rms < self.noise_floor * 1.5:
                    self.noise_floor = (1.0 - alpha) * self.noise_floor + alpha * rms
                    self.noise_floor = max(50.0, self.noise_floor)

                cooldown = float(cfg.get("activity_cooldown_sec", 1.0))
                self.has_activity = (now - self.last_activity_time) < cooldown


# Global singleton instance
microphone_detector = MicrophoneDetector()
