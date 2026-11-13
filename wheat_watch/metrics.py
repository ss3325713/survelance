"""System resource and pipeline performance monitoring.

Monitors CPU, RAM, FPS, and triggers dynamic throttling under high load.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict

import psutil

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.metrics")


class MetricsCollector:
    """Tracks system resources and pipeline FPS metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process = psutil.Process(os.getpid())
        
        self.camera_fps: float = 0.0
        self.processing_fps: float = 0.0
        self.total_frames_received: int = 0
        self.total_motion_detected: int = 0
        self.total_ai_inferences: int = 0
        self.throttled_frames_count: int = 0
        self.is_currently_throttled: bool = False
        
        self._last_cpu_percent: float = 0.0
        self._last_sample_time: float = time.time()
        
        # Start background sampling thread
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def _sample_loop(self) -> None:
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=1.0)
                with self._lock:
                    self._last_cpu_percent = cpu
                    threshold = app_config.pipeline.get("cpu_throttle_threshold", 85.0)
                    auto_throttle = app_config.pipeline.get("auto_throttle_cpu", True)
                    if auto_throttle and cpu >= threshold:
                        self.is_currently_throttled = True
                    else:
                        self.is_currently_throttled = False
            except Exception as e:
                logger.debug(f"Metrics sampling error: {e}")
                time.sleep(1.0)

    def should_throttle(self) -> bool:
        with self._lock:
            return self.is_currently_throttled

    def record_camera_frame(self, fps: float) -> None:
        with self._lock:
            self.camera_fps = fps
            self.total_frames_received += 1

    def record_processed_frame(self, fps: float) -> None:
        with self._lock:
            self.processing_fps = fps

    def record_motion_event(self) -> None:
        with self._lock:
            self.total_motion_detected += 1

    def record_ai_inference(self) -> None:
        with self._lock:
            self.total_ai_inferences += 1

    def record_throttled_frame(self) -> None:
        with self._lock:
            self.throttled_frames_count += 1

    def get_system_stats(self) -> Dict[str, Any]:
        with self._lock:
            cpu = self._last_cpu_percent
            is_throttled = self.is_currently_throttled
            cam_fps = self.camera_fps
            proc_fps = self.processing_fps

        mem = psutil.virtual_memory()
        proc_mem = self._process.memory_info().rss / (1024 * 1024)  # MB

        # Temperatures if available
        temp_c: Optional[float] = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temp_c = entries[0].current
                        break
        except Exception:
            pass

        return {
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(mem.percent, 1),
            "ram_used_mb": round(mem.used / (1024 * 1024), 1),
            "ram_total_mb": round(mem.total / (1024 * 1024), 1),
            "process_ram_mb": round(proc_mem, 1),
            "temperature_c": round(temp_c, 1) if temp_c is not None else None,
            "camera_fps": round(cam_fps, 1),
            "processing_fps": round(proc_fps, 1),
            "total_frames_received": self.total_frames_received,
            "total_motion_detected": self.total_motion_detected,
            "total_ai_inferences": self.total_ai_inferences,
            "is_throttled": is_throttled,
            "throttled_frames_count": self.throttled_frames_count,
        }


metrics = MetricsCollector()
