"""Phone microphone ambient audio activity analyzer for PySURVEILLANCE.

Captures and analyzes ambient audio directly from the Redmi 10 smartphone
via the IP Webcam audio stream (default: http://PHONE_IP:PORT/audio.wav).

STRICT AUDIO POLICY & PRIVACY GUARANTEES:
- The Redmi 10 microphone is the EXCLUSIVE audio source.
- Never silently use the laptop microphone.
- Do not use the browser's getUserMedia() microphone as a replacement.
- Do not select the system's default audio device.
- Do not introduce an automatic laptop-microphone fallback.
- If IP Webcam audio is unavailable, clearly report PHONE AUDIO DISCONNECTED.
- Keep video and audio connection states independent.
- All processing is local and in-memory. ZERO continuous recording or disk persistence.
- Adaptive noise-floor filtering distinguishes silence from disconnection and filters
  continuous ambient hum (fans, wind) without false alarms.
"""

from __future__ import annotations

import io
import logging
import struct
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import numpy as np

from wheat_watch.broadcaster import broadcaster
from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.microphone")


class MicrophoneDetector:
    """Dedicated phone-audio capture and noise telemetry analyzer."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Audio stream parameters (dynamically negotiated from WAV header or config)
        self.sample_rate = 16000
        self.channels = 1
        self.bits_per_sample = 16
        self.bytes_per_sample = 2
        self.chunk_samples = 1600  # ~100ms window
        self.bytes_per_chunk = self.chunk_samples * self.bytes_per_sample

        # State and telemetry
        self.is_connected = False
        self.is_available = False
        self.connection_state = "DISCONNECTED"  # "CONNECTED", "DISCONNECTED", "CONNECTING"
        self.has_activity = False
        self.current_rms = 0.0
        self.noise_floor = 1200.0
        self.snr = 1.0
        self.last_activity_time = 0.0
        self.last_error: Optional[str] = None
        self._sustained_window_count = 0
        self._reconnect_attempts = 0
        self._stream_response: Optional[Any] = None

        # Synthetic override for automated testing
        self._mock_activity_until = 0.0

    def start(self) -> None:
        """Start background phone audio capture thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self.connection_state = "CONNECTING"
            self._thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="PhoneAudioWorker",
            )
            self._thread.start()
            logger.info("PhoneAudioWorker background thread started.")

    def stop(self) -> None:
        """Stop background audio capture cleanly."""
        with self._lock:
            self._running = False
            if self._stream_response:
                try:
                    self._stream_response.close()
                except Exception:
                    pass
                self._stream_response = None
            self.is_connected = False
            self.is_available = False
            self.connection_state = "DISCONNECTED"

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("PhoneAudioWorker stopped.")

    def trigger_test_activity(self, duration_sec: float = 2.0, rms: float = 4500.0) -> None:
        """Synthetic activity trigger for deterministic test verification."""
        with self._lock:
            now = time.time()
            self._mock_activity_until = now + duration_sec
            self.last_activity_time = now
            self.has_activity = True
            self.current_rms = rms
            self.snr = rms / max(1.0, self.noise_floor)
        logger.info(f"Synthetic phone microphone activity triggered ({duration_sec}s, RMS={rms}).")

    @property
    def is_active(self) -> bool:
        """Check if meaningful sound activity occurred recently on phone microphone."""
        now = time.time()
        with self._lock:
            if now < self._mock_activity_until:
                return True
            if not self.is_connected:
                return False
            cooldown = float(app_config.audio_detection.get("activity_cooldown_sec", 1.0))
            return (now - self.last_activity_time) < cooldown

    def get_status(self) -> Dict[str, Any]:
        """Return real-time phone microphone diagnostics and noise telemetry."""
        with self._lock:
            active = self.is_active
            stream_url = app_config.camera_audio_url

            # Determine human-readable state
            if not self.is_connected:
                state_label = "DISCONNECTED"
            elif active:
                state_label = "ACTIVE"
            else:
                state_label = "SILENT"

            return {
                "source": "Redmi 10 (IP Webcam Audio Stream)",
                "stream_url": stream_url,
                "enabled": bool(app_config.audio_detection.get("enabled", True)),
                "is_connected": self.is_connected,
                "is_available": self.is_available,
                "connection_state": self.connection_state,
                "state": state_label,
                "has_activity": active,
                "current_rms": round(self.current_rms, 1),
                "noise_floor": round(self.noise_floor, 1),
                "snr": round(self.snr, 2),
                "sample_rate": self.sample_rate,
                "channels": self.channels,
                "last_activity_time": self.last_activity_time if self.last_activity_time > 0 else None,
                "last_error": self.last_error,
                "reconnect_attempts": self._reconnect_attempts,
            }

    def _parse_wav_header(self, raw_header: bytes) -> bool:
        """Parse WAV header from start of stream to discover audio parameters."""
        if len(raw_header) < 44 or not raw_header.startswith(b"RIFF") or b"WAVE" not in raw_header[:12]:
            logger.debug("Stream does not contain standard RIFF header; using default 16kHz mono PCM.")
            return False

        try:
            # Parse fmt subchunk
            fmt_pos = raw_header.find(b"fmt ")
            if fmt_pos != -1 and fmt_pos + 24 <= len(raw_header):
                subchunk_size = struct.unpack("<I", raw_header[fmt_pos + 4 : fmt_pos + 8])[0]
                audio_format = struct.unpack("<H", raw_header[fmt_pos + 8 : fmt_pos + 10])[0]
                num_channels = struct.unpack("<H", raw_header[fmt_pos + 10 : fmt_pos + 12])[0]
                sample_rate = struct.unpack("<I", raw_header[fmt_pos + 12 : fmt_pos + 16])[0]
                bits_per_sample = struct.unpack("<H", raw_header[fmt_pos + 22 : fmt_pos + 24])[0]

                if audio_format == 1 and num_channels in (1, 2) and sample_rate > 0:  # PCM
                    self.channels = num_channels
                    self.sample_rate = sample_rate
                    self.bits_per_sample = bits_per_sample
                    self.bytes_per_sample = max(1, bits_per_sample // 8)
                    self.chunk_samples = int(self.sample_rate * 0.1)  # 100ms
                    self.bytes_per_chunk = self.chunk_samples * self.channels * self.bytes_per_sample
                    logger.info(
                        f"Parsed phone audio format: {self.sample_rate} Hz, {self.channels} ch, {self.bits_per_sample}-bit PCM."
                    )
                    return True
        except Exception as e:
            logger.warning(f"Failed to parse RIFF audio header: {e}")

        return False

    def _capture_loop(self) -> None:
        """Continuous audio streaming loop directly from Redmi 10 IP Webcam."""
        backoff_sec = 2.0
        max_backoff_sec = 10.0

        while self._running:
            if not app_config.audio_detection.get("enabled", True):
                with self._lock:
                    self.connection_state = "DISABLED"
                    self.is_connected = False
                    self.is_available = False
                time.sleep(1.0)
                continue

            stream_url = app_config.camera_audio_url

            with self._lock:
                self.connection_state = "CONNECTING"

            try:
                logger.info(f"Connecting to phone microphone audio stream: {stream_url}")
                req = urllib.request.Request(
                    stream_url,
                    headers={"User-Agent": "PySURVEILLANCE-AudioClient/2.0"},
                )

                # Open streaming connection with 4s connect timeout
                resp = urllib.request.urlopen(req, timeout=4.0)
                self._stream_response = resp

                # Inspect start of stream for WAV RIFF header
                initial_bytes = resp.read(44)
                if initial_bytes:
                    self._parse_wav_header(initial_bytes)

                with self._lock:
                    self.is_connected = True
                    self.is_available = True
                    self.connection_state = "CONNECTED"
                    self.last_error = None
                    self._reconnect_attempts = 0
                    backoff_sec = 2.0

                logger.info(
                    f"Successfully connected to phone microphone stream ({stream_url}). "
                    f"Format: {self.sample_rate} Hz, {self.channels}ch."
                )

                # Stream audio chunks continuously
                while self._running:
                    chunk = resp.read(self.bytes_per_chunk)
                    if not chunk or len(chunk) < self.bytes_per_chunk:
                        # End of stream or connection severed
                        raise ConnectionResetError("Phone audio stream closed by remote server.")

                    self._process_audio_chunk(chunk)

            except Exception as e:
                with self._lock:
                    self.is_connected = False
                    self.is_available = False
                    self.connection_state = "DISCONNECTED"
                    self.has_activity = False
                    self.current_rms = 0.0
                    self.last_error = f"PHONE AUDIO DISCONNECTED: {e}"
                    self._reconnect_attempts += 1

                if self._stream_response:
                    try:
                        self._stream_response.close()
                    except Exception:
                        pass
                    self._stream_response = None

                logger.warning(
                    f"Phone microphone stream error (attempt #{self._reconnect_attempts}): {e}. "
                    f"Strict phone policy active — laptop microphone fallback disabled. Retrying in {backoff_sec:.1f}s..."
                )
                time.sleep(backoff_sec)
                backoff_sec = min(max_backoff_sec, backoff_sec * 1.5)

    def _process_audio_chunk(self, raw_bytes: bytes) -> None:
        """Lightweight NumPy signal processing for phone audio window."""
        cfg = app_config.audio_detection
        spike_multiplier = float(cfg.get("spike_multiplier", 3.0))
        sustained_thresh = float(cfg.get("sustained_threshold_rms", 2500.0))
        min_trigger_rms = float(cfg.get("min_trigger_rms", 1800.0))
        alpha = float(cfg.get("noise_floor_alpha", 0.05))

        try:
            # Convert raw bytes to numpy array
            if self.bits_per_sample == 16:
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
            else:
                samples = np.frombuffer(raw_bytes, dtype=np.int8).astype(np.float32) * 256.0

            # If multi-channel, extract first channel
            if self.channels > 1 and len(samples) >= self.channels:
                samples = samples[:: self.channels]

            rms = float(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0.0
        except Exception as e:
            logger.debug(f"Error decoding audio samples: {e}")
            return

        now = time.time()

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

            is_sustained = self._sustained_window_count >= int(cfg.get("consecutive_sustained_windows", 2))

            if is_spike or is_sustained:
                self.last_activity_time = now
                self.has_activity = True
                reason = "SUDDEN_SPIKE" if is_spike else "SUSTAINED_SOUND"
                logger.debug(
                    f"Phone microphone activity detected: {reason} "
                    f"(RMS={rms:.1f}, NoiseFloor={self.noise_floor:.1f}, SNR={self.snr:.2f})"
                )
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
