"""Intelligent flashlight controller for PySURVEILLANCE.

Automates the Redmi 10 LED flashlight using camera motion detection in low-light environments.

CORE RULES & POLICIES:
1. Primary Trigger: Camera-based motion detection under dark/low-light conditions.
2. STRICT POLICY: Audio is NOT a flashlight trigger.
3. Inactivity Duration: 15-second inactivity timeout. Continuous qualifying motion
   actively resets the countdown.
4. Duration Bounds:
   - Min ON time: Configurable minimum (10.0s) to prevent rapid strobing.
   - Max ON time: Safety cutoff (120.0s) to protect phone hardware/battery.
5. Operating Modes:
   - AUTO: Automatic sensor evaluation.
   - MANUAL: User forced ON (overrides automation).
   - OFF: User forced OFF (automation disabled).
6. Hardware Verification:
   - Explicit commands (/enabletorch, /disabletorch).
   - Actual hardware state is tracked independently from requested state.
   - Never report flashlight ON if the phone command failed.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Any, Deque, Dict, List, Optional

from wheat_watch.broadcaster import broadcaster
from wheat_watch.camera import camera_worker
from wheat_watch.config import app_config
from wheat_watch.motion import motion_detector

logger = logging.getLogger("wheat_watch.flashlight")


class FlashlightController:
    """Manages intelligent flashlight automation, inactivity countdown, and hardware telemetry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Operational modes & hardware states
        cfg = app_config.flashlight
        self.mode: str = cfg.get("mode", "auto").lower()  # "auto", "manual", "off"
        self.is_on: bool = False  # Actual confirmed hardware state
        self.requested_state: bool = False  # Last requested state

        # Timing & Triggers
        self.turn_on_time: float = 0.0
        self.last_motion_time: float = 0.0
        self.last_activation_time: Optional[float] = None
        self.active_trigger: Optional[str] = None  # "CAMERA_MOTION", "MANUAL", None
        self.last_trigger: Optional[str] = None
        self.last_trigger_time: float = 0.0

        # Telemetry & Diagnostics
        self.lighting_condition: str = "UNKNOWN"  # "DARK", "BRIGHT", "UNKNOWN"
        self.motion_detected: bool = False
        self.last_command_result: str = "IDLE"
        self.last_error: Optional[str] = None
        self._last_command_time: float = 0.0

        # In-memory automation event log (last 20 events)
        self.event_log: Deque[Dict[str, Any]] = collections.deque(maxlen=20)
        self._log_event("INITIALIZED", f"FlashlightController initialized in {self.mode.upper()} mode")

    def _log_event(self, action: str, details: str, result: str = "OK") -> None:
        """Record an automation lifecycle entry in the in-memory circular log."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": round(time.time(), 2),
            "mode": self.mode,
            "action": action,
            "details": details,
            "result": result,
            "hardware_is_on": self.is_on,
        }
        self.event_log.append(entry)

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """Switch between AUTO, MANUAL (forced ON), and OFF."""
        mode = mode.lower()
        if mode == "on":
            mode = "manual"
        elif mode not in ("auto", "manual", "off"):
            mode = "auto"

        with self._lock:
            prev_mode = self.mode
            self.mode = mode
            app_config.update({"flashlight": {"mode": mode}})

            logger.info(f"Flashlight mode switched: {prev_mode.upper()} -> {self.mode.upper()}")
            self._log_event("MODE_CHANGE", f"Switched mode to {self.mode.upper()}")

            if self.mode == "manual":
                self.requested_state = True
                success = self._send_hardware_command(True, trigger="MANUAL")
                if not success:
                    logger.warning("Manual flashlight ON command failed on camera device.")
            elif self.mode == "off":
                self.requested_state = False
                success = self._send_hardware_command(False)
                if not success:
                    logger.warning("Manual flashlight OFF command failed on camera device.")
            elif self.mode == "auto":
                # Returning to AUTO resumes automatic sensor evaluation
                now = time.time()
                self.last_motion_time = now
                logger.info("Resumed AUTO flashlight surveillance mode.")

            status = self.get_status()
            broadcaster.broadcast_sync("flashlight", status)
            return status

    def handle_manual_torch_toggle(self, target_state: bool) -> Dict[str, Any]:
        """Support manual torch toggling from camera controls card."""
        target_mode = "manual" if target_state else "off"
        return self.set_mode(target_mode)

    def process_sensor_activity(
        self,
        has_camera_motion: bool,
        is_low_light: bool,
        has_audio_activity: Optional[bool] = None,
        measured_brightness: float = 0.0,
    ) -> Dict[str, Any]:
        """Tick function called by pipeline loop to evaluate camera motion and ambient darkness.

        STRICT SPECIFICATION: Audio is NOT a trigger for flashlight automation.
        """
        now = time.time()

        with self._lock:
            self.lighting_condition = "DARK" if is_low_light else "BRIGHT"
            self.motion_detected = has_camera_motion

            # 1. Mode check: Forced OFF
            if self.mode == "off":
                self.requested_state = False
                if self.is_on:
                    self._send_hardware_command(False)
                return self.get_status()

            # 2. Mode check: Forced MANUAL ON
            if self.mode == "manual":
                self.requested_state = True
                if not self.is_on:
                    self._send_hardware_command(True, trigger="MANUAL")
                return self.get_status()

            # 3. AUTO Mode: Sensor evaluation
            cfg = app_config.flashlight
            min_on_time = float(cfg.get("min_on_time_sec", 10.0))
            max_on_time = float(cfg.get("max_on_time_sec", 120.0))
            inactivity_timeout = float(cfg.get("inactivity_timeout_sec", 15.0))
            stabilization_frames = int(cfg.get("stabilization_frames", 15))

            # Primary qualifying trigger: Motion in darkness
            qualifying_motion = has_camera_motion and is_low_light

            # CASE A: Flashlight is currently OFF -> Evaluate for activation
            if not self.is_on:
                self.requested_state = False
                if qualifying_motion:
                    self.requested_state = True
                    success = self._send_hardware_command(True, trigger="CAMERA_MOTION")
                    if success:
                        self.turn_on_time = now
                        self.last_motion_time = now
                        self.last_activation_time = now
                        self.active_trigger = "CAMERA_MOTION"
                        self.last_trigger = "CAMERA_MOTION"
                        self.last_trigger_time = now
                        self._log_event(
                            "AUTO_ACTIVATE",
                            f"Activated by camera motion in darkness (brightness={measured_brightness:.1f})",
                            result="SUCCESS",
                        )
                        logger.info(
                            f"Flashlight turned ON automatically. Trigger: CAMERA_MOTION. "
                            f"Low-light condition confirmed."
                        )
                        # Stabilize motion detector for sudden exposure jump
                        motion_detector.trigger_stabilization(count=stabilization_frames)
                        camera_worker.set_active_detections(
                            [], [], header_text="🔦 Flashlight Active [Motion in Darkness]", duration=1.5
                        )
                        broadcaster.broadcast_sync("flashlight", self.get_status())
                return self.get_status()

            # CASE B: Flashlight is currently ON -> Track continuous motion & inactivity countdown
            elapsed_on = max(0.0, now - self.turn_on_time)

            # Continuous motion resets the inactivity countdown timer
            if has_camera_motion:
                self.last_motion_time = now

            inactivity_duration = max(0.0, now - self.last_motion_time)

            # Check 1: Maximum ON safety cutoff (prevent LED/battery thermal stress)
            if elapsed_on >= max_on_time:
                logger.warning(
                    f"Flashlight reached safety maximum ON duration ({max_on_time}s). Automatically turning OFF."
                )
                self._turn_off_auto(reason="MAX_ON_TIME_EXCEEDED")
                return self.get_status()

            # Check 2: 15-second inactivity timeout (after minimum on-time satisfied)
            if elapsed_on >= min_on_time and inactivity_duration >= inactivity_timeout:
                logger.info(
                    f"Flashlight turned OFF automatically after {inactivity_timeout}s without motion "
                    f"(Total active: {elapsed_on:.1f}s)."
                )
                self._turn_off_auto(reason="INACTIVITY_TIMEOUT_15S")
                return self.get_status()

            return self.get_status()

    def _turn_off_auto(self, reason: str) -> None:
        """Turn off flashlight in AUTO mode and trigger brief exposure stabilization."""
        self.requested_state = False
        success = self._send_hardware_command(False)
        if success:
            self.active_trigger = None
            self._log_event("AUTO_DEACTIVATE", f"Turned off: {reason}", result="SUCCESS")
            motion_detector.trigger_stabilization(count=10)
            broadcaster.broadcast_sync("flashlight", self.get_status())

    def _send_hardware_command(self, turn_on: bool, trigger: Optional[str] = None) -> bool:
        """Send explicit ON (/enabletorch) or OFF (/disabletorch) command to camera device."""
        if not camera_worker.has_flashlight:
            self.last_command_result = "UNSUPPORTED"
            return False

        now = time.time()
        # Rate limit hardware commands to at most once per 250ms
        if now - self._last_command_time < 0.25:
            time.sleep(0.1)

        self._last_command_time = time.time()
        cmd_name = "torch"
        success = camera_worker.send_camera_command(cmd_name, turn_on)

        if success:
            self.is_on = turn_on
            self.last_command_result = "SUCCESS"
            self.last_error = None
            if turn_on:
                self.active_trigger = trigger or "MANUAL"
            else:
                self.active_trigger = None
            # Keep app_config in sync
            app_config.image_controls["torch"] = turn_on
            return True
        else:
            err = f"Failed to send {'/enabletorch' if turn_on else '/disabletorch'} to phone camera."
            self.last_command_result = f"FAILED: {err}"
            self.last_error = err
            self._log_event(
                "HARDWARE_ERROR",
                f"Command {'ON' if turn_on else 'OFF'} failed on camera endpoint",
                result="FAILED",
            )
            logger.error(err)
            # NEVER report flashlight ON if the phone did not confirm it!
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive real-time flashlight status, timers, and event log."""
        with self._lock:
            now = time.time()
            time_on = 0.0
            countdown = 0.0

            cfg = app_config.flashlight
            inactivity_timeout = float(cfg.get("inactivity_timeout_sec", 15.0))

            if self.is_on and self.turn_on_time > 0:
                time_on = round(now - self.turn_on_time, 1)
                inactivity_dur = max(0.0, now - self.last_motion_time)
                countdown = max(0.0, round(inactivity_timeout - inactivity_dur, 1))

            return {
                "supported": camera_worker.has_flashlight,
                "mode": self.mode,  # "auto", "manual", "off"
                "is_on": self.is_on,  # Actual verified hardware state
                "requested_state": self.requested_state,
                "lighting_condition": self.lighting_condition,
                "motion_detected": self.motion_detected,
                "active_trigger": self.active_trigger,
                "last_trigger": self.last_trigger,
                "last_activation_time": self.last_activation_time,
                "time_on_sec": time_on,
                "inactivity_countdown_sec": countdown,
                "inactivity_timeout_sec": inactivity_timeout,
                "min_on_time_sec": float(cfg.get("min_on_time_sec", 10.0)),
                "max_on_time_sec": float(cfg.get("max_on_time_sec", 120.0)),
                "last_command_result": self.last_command_result,
                "last_error": self.last_error,
                "event_log": list(self.event_log),
            }


# Global singleton instance
flashlight_controller = FlashlightController()
