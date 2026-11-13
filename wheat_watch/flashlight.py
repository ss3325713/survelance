"""Automatic flashlight controller for Wheat Watch.

Controls the Redmi 10 LED flashlight using complementary visual motion and
microphone ambient sound activity sensors.

BEHAVIOUR & POLICIES:
1. Modes:
   - AUTO: Sensor-driven automation.
   - MANUAL: User forced ON (overrides automation).
   - OFF: User forced OFF (automation disabled).
2. Triggers (Low Light only):
   - Camera motion in low-light -> turns ON flashlight (Trigger: CAMERA).
   - Audio activity when camera visibility is poor -> turns ON flashlight (Trigger: MICROPHONE).
   - Simultaneous camera and audio activity -> turns ON flashlight (Trigger: BOTH).
   - In daylight / bright conditions: Automation is suppressed.
3. Stabilization:
   - Brief camera stabilization triggered upon turning ON/OFF to prevent exposure
     shifts from causing artificial motion detections.
4. Duration Constraints:
   - Inactivity timeout: Turns OFF after 15 seconds without detected activity.
   - Min ON time: Configurable minimum (10.0s).
   - Max ON time: Configurable safety cutoff (120.0s) to prevent battery/LED overheating.
5. Reliability:
   - Explicit commands (/enabletorch, /disabletorch) only. Never toggle.
   - State updated ONLY when hardware command confirms success.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from wheat_watch.broadcaster import broadcaster
from wheat_watch.camera import camera_worker
from wheat_watch.config import app_config
from wheat_watch.motion import motion_detector

logger = logging.getLogger("wheat_watch.flashlight")


class FlashlightController:
    """Manages automatic flashlight state, multi-sensor activity, and timer constraints."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Operational state
        cfg = app_config.flashlight
        self.mode: str = cfg.get("mode", "auto").lower()  # "auto", "manual", "off"
        self.is_on: bool = False

        # Timers & metrics
        self.turn_on_time: float = 0.0
        self.last_activity_time: float = 0.0
        self.active_trigger: Optional[str] = None  # "CAMERA", "MICROPHONE", "BOTH", "MANUAL"
        self.last_trigger: Optional[str] = None
        self.last_trigger_time: float = 0.0
        self.last_error: Optional[str] = None
        self._last_command_time: float = 0.0

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """Switch between AUTO, MANUAL (forced ON), and OFF."""
        mode = mode.lower()
        if mode not in ("auto", "manual", "off"):
            mode = "auto"

        with self._lock:
            prev_mode = self.mode
            self.mode = mode
            app_config.update({"flashlight": {"mode": mode}})

            logger.info(f"Flashlight mode changed from {prev_mode.upper()} to {self.mode.upper()}.")

            if self.mode == "manual":
                # Explicitly command hardware ON
                success = self._send_hardware_command(True, trigger="MANUAL")
                if not success:
                    logger.warning("Manual flashlight ON command failed on camera.")
            elif self.mode == "off":
                # Explicitly command hardware OFF
                success = self._send_hardware_command(False)
                if not success:
                    logger.warning("Manual flashlight OFF command failed on camera.")
            elif self.mode == "auto":
                # Returning to AUTO resumes automatic sensor evaluation
                now = time.time()
                self.last_activity_time = now
                logger.info("Resumed AUTO flashlight surveillance mode.")

            status = self.get_status()
            broadcaster.broadcast_sync("flashlight", status)
            return status

    def handle_manual_torch_toggle(self, target_state: bool) -> Dict[str, Any]:
        """Support existing manual torch control from image controls card."""
        target_mode = "manual" if target_state else "off"
        return self.set_mode(target_mode)

    def process_sensor_activity(
        self,
        has_camera_motion: bool,
        is_low_light: bool,
        has_audio_activity: bool,
    ) -> Dict[str, Any]:
        """Tick function called by pipeline to evaluate multi-sensor triggers."""
        now = time.time()

        with self._lock:
            # 1. Mode check
            if self.mode == "off":
                if self.is_on:
                    self._send_hardware_command(False)
                return self.get_status()

            if self.mode == "manual":
                # Keep ON in manual mode
                if not self.is_on:
                    self._send_hardware_command(True, trigger="MANUAL")
                return self.get_status()

            # 2. AUTO Mode: Sensor evaluation
            cfg = app_config.flashlight
            min_on_time = float(cfg.get("min_on_time_sec", 10.0))
            max_on_time = float(cfg.get("max_on_time_sec", 120.0))
            inactivity_timeout = float(cfg.get("inactivity_timeout_sec", 15.0))
            stabilization_frames = int(cfg.get("stabilization_frames", 15))

            # Determine sensor trigger source
            cam_active = has_camera_motion and is_low_light
            mic_active = has_audio_activity and is_low_light

            sensor_trigger: Optional[str] = None
            if cam_active and mic_active:
                sensor_trigger = "BOTH"
            elif cam_active:
                sensor_trigger = "CAMERA"
            elif mic_active:
                sensor_trigger = "MICROPHONE"

            # CASE A: Flashlight is currently OFF -> Check for activation
            if not self.is_on:
                if sensor_trigger is not None:
                    # Attempt activation
                    success = self._send_hardware_command(True, trigger=sensor_trigger)
                    if success:
                        self.turn_on_time = now
                        self.last_activity_time = now
                        self.active_trigger = sensor_trigger
                        self.last_trigger = sensor_trigger
                        self.last_trigger_time = now
                        logger.info(
                            f"Flashlight turned ON automatically. Trigger source: [{sensor_trigger}]. "
                            f"Camera low-light={is_low_light}, Audio={has_audio_activity}"
                        )
                        # Stabilize motion detector for lighting change
                        motion_detector.trigger_stabilization(count=stabilization_frames)
                        camera_worker.set_active_detections(
                            [], [], header_text=f"🔦 Flashlight Active [{sensor_trigger}]", duration=1.5
                        )
                        broadcaster.broadcast_sync("flashlight", self.get_status())
                return self.get_status()

            # CASE B: Flashlight is currently ON -> Check activity continuation & timeouts
            elapsed_on = max(0.0, now - self.turn_on_time)

            # Activity continuation (any camera motion or audio keeps timer alive)
            if has_camera_motion or has_audio_activity:
                self.last_activity_time = now
                if sensor_trigger and sensor_trigger != self.active_trigger:
                    self.active_trigger = sensor_trigger

            inactivity_duration = max(0.0, now - self.last_activity_time)

            # Check 1: Maximum ON time safety cutoff
            if elapsed_on >= max_on_time:
                logger.warning(
                    f"Flashlight reached maximum ON time ({max_on_time}s). Automatically turning OFF to prevent overheating."
                )
                self._turn_off_auto(reason="MAX_ON_TIME_EXCEEDED")
                return self.get_status()

            # Check 2: Inactivity timeout after minimum ON time has elapsed
            if elapsed_on >= min_on_time and inactivity_duration >= inactivity_timeout:
                logger.info(
                    f"Flashlight turned OFF automatically after {inactivity_timeout}s without detected activity "
                    f"(Total active: {elapsed_on:.1f}s)."
                )
                self._turn_off_auto(reason="INACTIVITY_TIMEOUT")
                return self.get_status()

            return self.get_status()

    def _turn_off_auto(self, reason: str) -> None:
        """Helper to turn off flashlight in AUTO mode with exposure stabilization."""
        success = self._send_hardware_command(False)
        if success:
            self.active_trigger = None
            motion_detector.trigger_stabilization(count=10)
            broadcaster.broadcast_sync("flashlight", self.get_status())

    def _send_hardware_command(self, turn_on: bool, trigger: Optional[str] = None) -> bool:
        """Send explicit ON or OFF command to Redmi 10 IP Webcam and verify success."""
        # Rate limit hardware commands to at most once per 200ms
        now = time.time()
        if now - self._last_command_time < 0.2:
            time.sleep(0.1)

        self._last_command_time = time.time()
        cmd_name = "torch"
        success = camera_worker.send_camera_command(cmd_name, turn_on)

        if success:
            self.is_on = turn_on
            self.last_error = None
            if turn_on:
                if trigger:
                    self.active_trigger = trigger
            else:
                self.active_trigger = None
            # Keep app_config in sync
            app_config.image_controls["torch"] = turn_on
            return True
        else:
            err = f"Failed to send {'/enabletorch' if turn_on else '/disabletorch'} to camera."
            self.last_error = err
            logger.error(err)
            # NEVER claim the flashlight changed state when its command failed!
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return real-time flashlight status and activity telemetry."""
        with self._lock:
            now = time.time()
            time_on = 0.0
            if self.is_on and self.turn_on_time > 0:
                time_on = round(now - self.turn_on_time, 1)

            cfg = app_config.flashlight
            return {
                "mode": self.mode,  # "auto", "manual", "off"
                "is_on": self.is_on,
                "active_trigger": self.active_trigger,
                "last_trigger": self.last_trigger,
                "last_trigger_time": self.last_trigger_time if self.last_trigger_time > 0 else None,
                "time_on_sec": time_on,
                "min_on_time_sec": float(cfg.get("min_on_time_sec", 10.0)),
                "max_on_time_sec": float(cfg.get("max_on_time_sec", 120.0)),
                "inactivity_timeout_sec": float(cfg.get("inactivity_timeout_sec", 15.0)),
                "last_error": self.last_error,
            }


# Global singleton instance
flashlight_controller = FlashlightController()
