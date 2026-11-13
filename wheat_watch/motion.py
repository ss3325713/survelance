"""Motion detection engine for Wheat Watch.

Uses background subtraction (MOG2) with:
1. Dedicated Night Surveillance Mode (Auto, On, Off) with separate day/night profiles.
2. Real-time luminance measurement and adaptive night transition with hysteresis.
3. Global exposure & lighting change suppression.
4. Temporal persistence (2-frame confirmation).
5. Calibration warm-up during mode switches.
6. Spatial motion mask verification for AI detections.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.motion")


class MotionDetector:
    """Robust motion detector with Day/Night surveillance profiles and illumination suppression."""

    def __init__(self) -> None:
        self._analysis_width = 320
        self._analysis_height = 240

        # Night mode state
        night_cfg = app_config.night_mode
        self.mode: str = night_cfg.get("mode", "auto")  # "off", "on", "auto"
        self.active_mode: str = "day"
        self.measured_brightness: float = 80.0  # Exponential moving average

        self._load_active_profile()

        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300,
            varThreshold=self.threshold,
            detectShadows=False,
        )

        self._stabilization_counter = 12  # Warm-up frames on launch
        self._prev_mean_luminance: Optional[float] = None
        self._consecutive_motion_count = 0
        self._required_consecutive = 2
        self._last_fg_mask: Optional[np.ndarray] = None

    def _load_active_profile(self) -> None:
        """Load Day or Night profile parameters from config."""
        night_cfg = app_config.night_mode
        profile = night_cfg.get(self.active_mode, {})

        if self.active_mode == "night":
            self.threshold = profile.get("motion_threshold", 34)
            self.min_area = profile.get("min_motion_area", 350)
            self.max_motion_percent = profile.get("max_motion_percent", 18.0)
            self.light_change_threshold = profile.get("light_change_threshold", 12.0)
        else:
            self.threshold = profile.get("motion_threshold", 25)
            self.min_area = profile.get("min_motion_area", 250)
            self.max_motion_percent = profile.get("max_motion_percent", 22.0)
            self.light_change_threshold = profile.get("light_change_threshold", 7.5)

        if hasattr(self, "subtractor") and self.subtractor is not None:
            try:
                self.subtractor.setVarThreshold(float(self.threshold))
            except Exception as e:
                logger.warning(f"Failed to update MOG2 varThreshold: {e}")

    def set_threshold(self, threshold: int) -> int:
        """Set motion sensitivity VarThreshold dynamically on the active background subtractor."""
        val = int(threshold)
        if val < 5:
            val = 5
        elif val > 150:
            val = 150
        self.threshold = val
        if hasattr(self, "subtractor") and self.subtractor is not None:
            try:
                self.subtractor.setVarThreshold(float(val))
            except Exception as e:
                logger.warning(f"Failed to set MOG2 VarThreshold: {e}")

        # Update active profile in night_mode and pipeline
        night_cfg = dict(app_config.night_mode)
        active_prof = dict(night_cfg.get(self.active_mode, {}))
        active_prof["motion_threshold"] = val
        night_cfg[self.active_mode] = active_prof
        app_config.update({
            "night_mode": night_cfg,
            "pipeline": {
                "motion_threshold": val
            }
        })
        logger.info(f"Updated motion VarThreshold to: {val} (active profile: {self.active_mode})")
        return self.threshold

    def set_night_mode(self, mode: str) -> Dict[str, Any]:
        """Manually set night mode to 'off', 'on', or 'auto'."""
        mode = mode.lower()
        if mode not in ("off", "on", "auto"):
            mode = "auto"

        self.mode = mode
        app_config.update({"night_mode": {"mode": mode}})

        prev_active = self.active_mode
        if self.mode == "on":
            self.active_mode = "night"
        elif self.mode == "off":
            self.active_mode = "day"
        else:
            auto_thresh = float(app_config.night_mode.get("auto_threshold", 45.0))
            self.active_mode = "night" if self.measured_brightness < auto_thresh else "day"

        self._load_active_profile()
        if prev_active != self.active_mode:
            self.trigger_stabilization(count=10)

        logger.info(f"Night mode setting changed to: {self.mode} (Active profile: {self.active_mode})")
        return self.get_night_status()

    def get_night_status(self) -> Dict[str, Any]:
        """Return current night mode state and brightness telemetry."""
        conf = float(
            app_config.pipeline.get("detection_confidence")
            or app_config.pipeline.get("min_confidence")
            or 0.45
        )
        return {
            "mode": self.mode,
            "active_mode": self.active_mode,
            "is_night": (self.active_mode == "night"),
            "measured_brightness": round(self.measured_brightness, 1),
            "threshold": self.threshold,
            "min_area": self.min_area,
            "light_change_threshold": self.light_change_threshold,
            "confidence": conf,
            "min_confidence": conf,
        }

    def reset(self) -> None:
        """Reset background model completely."""
        self._load_active_profile()
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300,
            varThreshold=self.threshold,
            detectShadows=False,
        )
        self._prev_mean_luminance = None
        self._consecutive_motion_count = 0
        self._stabilization_counter = 10
        self._last_fg_mask = None
        logger.info(f"Motion detector reset with {self.active_mode.upper()} profile.")

    def trigger_stabilization(self, count: int = 15) -> None:
        """Rapidly adapt background model to new camera/lighting settings without alerting."""
        self._stabilization_counter = max(self._stabilization_counter, count)
        self._consecutive_motion_count = 0
        self._load_active_profile()
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300,
            varThreshold=self.threshold,
            detectShadows=False,
        )
        self._prev_mean_luminance = None
        self._last_fg_mask = None
        logger.info(f"Motion detector stabilization activated for {count} frames ({self.active_mode.upper()}).")

    def process_frame(
        self,
        frame: np.ndarray,
    ) -> Tuple[bool, List[Tuple[int, int, int, int]], float, bool]:
        """Process frame and return (has_motion, bounding_boxes, motion_percent, is_calibrating)."""
        orig_h, orig_w = frame.shape[:2]

        # Downscale for ultra-fast motion check
        small = cv2.resize(frame, (self._analysis_width, self._analysis_height))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)

        # 1. Measure frame mean luminance & update brightness EMA
        curr_mean_luminance = float(np.mean(gray))
        self.measured_brightness = 0.92 * self.measured_brightness + 0.08 * curr_mean_luminance

        # Check Night Mode transition
        night_cfg = app_config.night_mode
        self.mode = night_cfg.get("mode", "auto")
        auto_thresh = float(night_cfg.get("auto_threshold", 45.0))
        hysteresis = float(night_cfg.get("hysteresis", 8.0))

        prev_active = self.active_mode
        if self.mode == "on":
            self.active_mode = "night"
        elif self.mode == "off":
            self.active_mode = "day"
        else:
            # Auto mode with hysteresis
            if self.measured_brightness < auto_thresh:
                self.active_mode = "night"
            elif self.measured_brightness > (auto_thresh + hysteresis):
                self.active_mode = "day"

        if prev_active != self.active_mode:
            logger.info(f"Night Surveillance transitioned: [{self.active_mode.upper()}] (lux: {self.measured_brightness:.1f})")
            self.trigger_stabilization(count=10)

        # 2. Check frame-to-frame delta for sudden light shifts
        lum_delta = 0.0
        if self._prev_mean_luminance is not None:
            lum_delta = abs(curr_mean_luminance - self._prev_mean_luminance)
        self._prev_mean_luminance = curr_mean_luminance

        # 3. Calibration / Stabilization mode
        if self._stabilization_counter > 0:
            self._stabilization_counter -= 1
            self.subtractor.apply(blurred, learningRate=0.35)
            self._consecutive_motion_count = 0
            self._last_fg_mask = np.zeros((self._analysis_height, self._analysis_width), dtype=np.uint8)
            return False, [], 0.0, True

        # 4. Suppress sudden global illumination shifts (light switch, headlights, flash)
        if lum_delta > self.light_change_threshold:
            self.subtractor.apply(blurred, learningRate=0.40)
            self._consecutive_motion_count = 0
            self._last_fg_mask = np.zeros((self._analysis_height, self._analysis_width), dtype=np.uint8)
            logger.debug(
                f"Suppressed lighting shift (delta {lum_delta:.1f} > {self.light_change_threshold:.1f}, {self.active_mode})"
            )
            return False, [], 0.0, True

        # 5. Background Subtraction
        fg_mask = self.subtractor.apply(blurred)

        # Morphological operations to clean isolated pixel noise and fill target holes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)

        # Calculate motion percentage
        non_zero = cv2.countNonZero(fg_mask)
        total_pixels = self._analysis_width * self._analysis_height
        motion_percent = (non_zero / total_pixels) * 100.0

        # 6. Suppress Massive Frame-Wide Motion (Camera shaking, auto-exposure hunting, glare)
        if motion_percent > self.max_motion_percent:
            self.subtractor.apply(blurred, learningRate=0.30)
            self._consecutive_motion_count = 0
            self._last_fg_mask = np.zeros((self._analysis_height, self._analysis_width), dtype=np.uint8)
            logger.debug(f"Suppressed global motion ({motion_percent:.1f}% > {self.max_motion_percent}%).")
            return False, [], round(motion_percent, 2), True

        # Save latest mask for spatial verification
        self._last_fg_mask = fg_mask.copy()

        # 7. Extract Localized Motion Contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        scale_x = orig_w / self._analysis_width
        scale_y = orig_h / self._analysis_height

        motion_boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            # Filter noise slivers
            min_dim = 12 if self.active_mode == "night" else 10
            if w < min_dim or h < min_dim:
                continue

            orig_box = (
                int(x * scale_x),
                int(y * scale_y),
                int(w * scale_x),
                int(h * scale_y),
            )
            motion_boxes.append(orig_box)

        # 8. Temporal Persistence (Requires 2 consecutive frames with valid motion)
        min_motion_pct = 0.45 if self.active_mode == "night" else 0.35
        has_localized_movement = len(motion_boxes) > 0 and motion_percent >= min_motion_pct
        if has_localized_movement:
            self._consecutive_motion_count += 1
        else:
            self._consecutive_motion_count = 0

        has_motion = has_localized_movement and (self._consecutive_motion_count >= self._required_consecutive)
        return has_motion, motion_boxes, round(motion_percent, 2), False

    def has_motion_in_box(
        self,
        box: List[int],
        orig_w: int,
        orig_h: int,
    ) -> Tuple[bool, float]:
        """Check if a detected bounding box [x1, y1, x2, y2] contains actual moving pixels."""
        if self._last_fg_mask is None:
            return False, 0.0

        x1, y1, x2, y2 = box
        sx1 = max(0, min(self._analysis_width - 1, int(x1 * self._analysis_width / orig_w)))
        sy1 = max(0, min(self._analysis_height - 1, int(y1 * self._analysis_height / orig_h)))
        sx2 = max(sx1 + 1, min(self._analysis_width, int(x2 * self._analysis_width / orig_w)))
        sy2 = max(sy1 + 1, min(self._analysis_height, int(y2 * self._analysis_height / orig_h)))

        roi = self._last_fg_mask[sy1:sy2, sx1:sx2]
        if roi.size == 0:
            return False, 0.0

        moving_pixels = cv2.countNonZero(roi)
        total_box_pixels = roi.size
        motion_ratio = moving_pixels / total_box_pixels

        min_px = 20 if self.active_mode == "night" else 15
        min_ratio = 0.03 if self.active_mode == "night" else 0.02
        is_moving = moving_pixels >= min_px and motion_ratio >= min_ratio
        return is_moving, motion_ratio


# Global motion detector
motion_detector = MotionDetector()
