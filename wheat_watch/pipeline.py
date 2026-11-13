"""Processing pipeline coordinator for Wheat Watch.

Event-based surveillance system with:
1. Pure image-based event persistence (ZERO continuous video recording).
2. Grouped event sessions with deduplication (Initial, Change, and Final image capture).
3. Dedicated Night Surveillance Mode (Auto / On / Off) with ambient lux adaptation.
4. Guaranteed capture of all motion events (never silently discarded).
5. Safe retention management protecting active ongoing events.
6. Real-time broadcast to all connected dashboards and laptop audio alarms.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set

import cv2
import numpy as np

from wheat_watch.audio import audio_manager
from wheat_watch.broadcaster import broadcaster
from wheat_watch.camera import camera_worker
from wheat_watch.config import app_config
from wheat_watch.detector import detector
from wheat_watch.events import event_store
from wheat_watch.flashlight import flashlight_controller
from wheat_watch.metrics import metrics
from wheat_watch.microphone import microphone_detector
from wheat_watch.motion import motion_detector
from wheat_watch.power import power_manager
from wheat_watch.storage import storage_manager

logger = logging.getLogger("wheat_watch.pipeline")

CATEGORY_PRIORITY = {
    "Possible monkey": 100,
    "Person": 90,
    "Animal detected — species unconfirmed": 80,
    "Other recognized animal": 70,
    "Bird": 60,
    "Unknown object": 50,
    "General motion": 10,
}


class PipelineController:
    """Controls the lifecycle and execution of the surveillance pipeline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.is_monitoring = False
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.monitoring_start_time: float = 0.0

        # Timing & detection state
        self.last_motion_time: float = 0.0
        self.last_inference_time: float = 0.0
        self.last_event_category: Optional[str] = None
        self.last_event_time: float = 0.0

        # Event deduplication session state
        self.active_session: Optional[Dict[str, Any]] = None
        self.session_last_motion_time: float = 0.0
        self.session_has_change_image: bool = False
        self.session_captured_categories: Set[str] = set()
        self.session_start_time: float = 0.0
        self._last_annotated_frame: Optional[np.ndarray] = None
        self._last_retention_check: float = 0.0

    def start_monitoring(self) -> Dict[str, Any]:
        """Start continuous field monitoring."""
        with self._lock:
            if self.is_monitoring:
                return {"success": True, "message": "Monitoring is already active."}

            self.is_monitoring = True
            self._running = True
            self.monitoring_start_time = time.time()

            # 1. Start power inhibition
            power_manager.start_inhibition()

            # 2. Start camera acquisition worker & microphone detector
            camera_worker.start()
            microphone_detector.start()

            # 3. Start processing loop thread
            self._thread = threading.Thread(
                target=self._pipeline_loop,
                daemon=True,
                name="PipelineController",
            )
            self._thread.start()

            logger.info("Continuous field monitoring STARTED.")
            return {"success": True, "message": "PySURVEILLANCE monitoring started successfully."}

    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop continuous field monitoring and close active event sessions."""
        with self._lock:
            if not self.is_monitoring:
                return {"success": True, "message": "Monitoring is not currently active."}

            self.is_monitoring = False
            self._running = False

            # Finalize any open event session
            if self.active_session is not None:
                try:
                    event_store.close_event_session(self.active_session["id"])
                except Exception:
                    pass
                self.active_session = None

            # Stop camera worker and microphone detector
            camera_worker.stop()
            microphone_detector.stop()

            # Stop power inhibition
            power_manager.stop_inhibition()

            logger.info("Continuous field monitoring STOPPED by user.")
            return {"success": True, "message": "PySURVEILLANCE monitoring stopped."}

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            uptime_sec = 0.0
            if self.is_monitoring and self.monitoring_start_time > 0:
                uptime_sec = max(0.0, time.time() - self.monitoring_start_time)

            h = int(uptime_sec // 3600)
            m = int((uptime_sec % 3600) // 60)
            s = int(uptime_sec % 60)
            uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

            last_det_age = None
            if self.last_event_time > 0:
                last_det_age = round(time.time() - self.last_event_time, 1)

            return {
                "is_monitoring": self.is_monitoring,
                "power_inhibited": power_manager.is_inhibited,
                "monitoring_uptime_sec": round(uptime_sec, 1),
                "monitoring_uptime_str": uptime_str,
                "last_motion_age_sec": round(time.time() - self.last_motion_time, 1) if self.last_motion_time > 0 else None,
                "last_detection_age_sec": last_det_age,
                "last_detection_timestamp": self.last_event_time if self.last_event_time > 0 else None,
                "last_event_category": self.last_event_category,
                "has_active_event": (self.active_session is not None),
                "active_session_id": self.active_session["id"] if self.active_session else None,
                "night_mode": motion_detector.get_night_status(),
                "flashlight": flashlight_controller.get_status(),
                "microphone": microphone_detector.get_status(),
                "today_events_count": event_store.get_today_count(),
            }

    def _pipeline_loop(self) -> None:
        """Main decoupled processing loop."""
        logger.info("Pipeline processing thread started.")
        frame_counter = 0
        fps_timer = time.time()
        motion_detector.reset()

        while self._running:
            # 1. Fetch dynamic intervals from active profile (Day or Night)
            night_cfg = app_config.night_mode
            active_profile = night_cfg.get(motion_detector.active_mode, {})
            motion_fps = active_profile.get("motion_fps", app_config.pipeline.get("motion_fps", 8.0))
            ai_fps = active_profile.get("ai_fps", app_config.pipeline.get("ai_fps", 1.5))

            target_motion_interval = 1.0 / max(1.0, motion_fps)
            target_ai_interval = 1.0 / max(0.5, ai_fps)

            # Auto-throttle check under high CPU
            if metrics.should_throttle():
                metrics.record_throttled_frame()
                target_motion_interval *= 1.5
                target_ai_interval *= 1.5

            loop_start = time.time()

            # 2. Wait for newest frame from bounded acquisition buffer
            frame = camera_worker.wait_for_frame(timeout=0.3)
            now = time.time()
            has_audio = microphone_detector.is_active

            if frame is None or not self._running:
                # Camera dropped a frame or is reconnecting.
                # If audio activity occurs in dark/poor visibility, tick flashlight controller!
                is_low_light = (motion_detector.active_mode == "night") or (motion_detector.measured_brightness < float(app_config.flashlight.get("lux_threshold", 45.0)))
                flashlight_controller.process_sensor_activity(
                    has_camera_motion=False,
                    is_low_light=is_low_light,
                    has_audio_activity=has_audio,
                )
                continue

            # 3. Motion detection with Night/Day adaptation & exposure suppression
            has_motion, motion_boxes, motion_percent, is_calibrating = motion_detector.process_frame(frame)

            # 4. Automatic Flashlight Sensor Processing (Camera + Microphone)
            is_low_light = (motion_detector.active_mode == "night") or (motion_detector.measured_brightness < float(app_config.flashlight.get("lux_threshold", 45.0)))
            flashlight_controller.process_sensor_activity(
                has_camera_motion=has_motion,
                is_low_light=is_low_light,
                has_audio_activity=has_audio,
            )

            if is_calibrating:
                camera_worker.set_active_detections(
                    detections=[],
                    motion_boxes=[],
                    header_text="Calibrating Lighting / Sensor Mode...",
                    duration=0.8,
                )
                continue

            if has_motion:
                self.last_motion_time = now
                self.session_last_motion_time = now
                metrics.record_motion_event()

                # Check if it is time for AI inference
                time_since_ai = now - self.last_inference_time
                if time_since_ai >= target_ai_interval:
                    self.last_inference_time = now
                    metrics.record_ai_inference()

                    # 4. AI Inference stage
                    detections = detector.detect(frame)
                    h, w = frame.shape[:2]

                    # Spatial Motion Verification: Filter moving vs static targets
                    active_detections = []
                    for det in detections:
                        is_moving, motion_ratio = motion_detector.has_motion_in_box(det["box"], w, h)
                        det["is_moving"] = is_moving
                        det["motion_ratio"] = motion_ratio

                        if det["category"] == "Unknown object":
                            if is_moving:
                                active_detections.append(det)
                        else:
                            # Primary targets: Person, Bird, Animal, Monkey
                            if is_moving or det["confidence"] >= 0.55:
                                active_detections.append(det)

                    # Night-mode classification safety:
                    # Dark images cannot be classified reliably. If dark and AI confidence is borderline,
                    # treat as General motion without claiming unverified species/person.
                    is_low_light = (motion_detector.active_mode == "night") or (motion_detector.measured_brightness < 35.0)

                    if active_detections:
                        active_detections.sort(
                            key=lambda d: (CATEGORY_PRIORITY.get(d["category"], 0), d["confidence"]),
                            reverse=True,
                        )
                        primary_det = active_detections[0]

                        if is_low_light and primary_det["confidence"] < 0.60:
                            category = "General motion"
                            confidence = primary_det["confidence"]
                            label = f"Motion in low light (unconfirmed: {primary_det['label']})"
                        else:
                            category = primary_det["category"]
                            confidence = primary_det["confidence"]
                            label = primary_det["label"]
                    else:
                        # General motion event: DO NOT SILENTLY DISCARD
                        category = "General motion"
                        confidence = min(1.0, max(0.40, motion_percent / 10.0))
                        label = f"General motion ({motion_percent:.1f}% area)"

                    # 5. Annotation stage
                    header_label = f"DETECTED: {label}"
                    if motion_detector.active_mode == "night":
                        header_label += " [NIGHT MODE]"

                    camera_worker.set_active_detections(
                        detections=active_detections,
                        motion_boxes=motion_boxes,
                        header_text=header_label,
                        duration=2.0,
                    )

                    annotated_frame = detector.annotate_frame(
                        frame,
                        detections=active_detections,
                        motion_boxes=motion_boxes,
                        header_text=header_label,
                    )
                    self._last_annotated_frame = annotated_frame.copy()

                    # 6. Event Deduplication & Grouping Logic
                    group_cfg = app_config.event_grouping
                    is_grouping = group_cfg.get("enabled", True)

                    active_paths = event_store.get_active_image_paths()

                    if self.active_session is None or not is_grouping:
                        # ── PHASE 1: INITIAL EVENT IMAGE CAPTURE ──
                        image_path = storage_manager.save_event_image(
                            annotated_frame, category, tag="initial", active_paths=active_paths
                        )

                        event_record = event_store.start_event_session(
                            category=category,
                            confidence=confidence,
                            label=label,
                            image_path=image_path,
                            details={
                                "detections": active_detections,
                                "motion_percent": motion_percent,
                                "night_mode": motion_detector.get_night_status(),
                                "flashlight": flashlight_controller.get_status(),
                                "audio": microphone_detector.get_status(),
                            },
                        )

                        self.active_session = event_record
                        self.session_start_time = now
                        self.session_has_change_image = False
                        self.session_captured_categories = {category}

                        # Broadcast Initial Event to Dashboards
                        broadcaster.broadcast_sync("detection", {
                            "id": event_record["id"],
                            "category": category,
                            "confidence": round(confidence, 3),
                            "label": label,
                            "image_path": image_path,
                            "tag": "initial",
                            "timestamp": event_record["timestamp"],
                            "night_mode": motion_detector.active_mode,
                            "details": event_record["details"],
                        })

                        # Trigger Audio Notification (Laptop Speakers)
                        audio_manager.play_alert(category)

                        self.last_event_category = category
                        self.last_event_time = now

                    else:
                        # ── PHASE 2: MEANINGFUL CHANGE DETECTION ──
                        current_prio = CATEGORY_PRIORITY.get(self.active_session.get("category"), 0)
                        new_prio = CATEGORY_PRIORITY.get(category, 0)

                        is_escalation = (new_prio > current_prio)
                        is_new_category = (category not in self.session_captured_categories and category != "General motion")
                        is_confidence_jump = (confidence - self.active_session.get("confidence", 0.0) >= 0.25)

                        meaningful_change = (is_escalation or is_new_category or is_confidence_jump)

                        if meaningful_change and not self.session_has_change_image:
                            image_path = storage_manager.save_event_image(
                                annotated_frame, category, tag="change", active_paths=active_paths
                            )

                            updated_record = event_store.update_event_session(
                                event_id=self.active_session["id"],
                                new_image_path=image_path,
                                tag="change",
                                category=category if is_escalation else None,
                                label=label if is_escalation else None,
                                confidence=confidence if is_escalation else None,
                                new_details={
                                    "detections": active_detections,
                                    "motion_percent": motion_percent,
                                    "escalated": is_escalation,
                                },
                            )
                            if updated_record:
                                self.active_session = updated_record
                            self.session_has_change_image = True
                            self.session_captured_categories.add(category)

                            # If escalated to higher priority entity (e.g. Person from Motion), sound alarm
                            if is_escalation:
                                audio_manager.play_alert(category)

                            broadcaster.broadcast_sync("detection_update", {
                                "id": self.active_session["id"],
                                "category": category,
                                "label": label,
                                "confidence": round(confidence, 3),
                                "image_path": image_path,
                                "tag": "change",
                                "escalated": is_escalation,
                            })

                else:
                    # Motion detected but awaiting AI sampling interval
                    camera_worker.set_active_detections(
                        detections=[],
                        motion_boxes=motion_boxes,
                        header_text="Motion Detected (Analyzing...)",
                        duration=0.5,
                    )
            else:
                # No motion detected in this frame
                camera_worker.clear_active_detections()

                # ── PHASE 3: EVENT SESSION FINALIZATION ──
                # If motion has ceased for session_timeout_sec, close the active session
                session_timeout = float(app_config.event_grouping.get("session_timeout_sec", 4.0))
                if self.active_session is not None and (now - self.session_last_motion_time >= session_timeout):
                    duration = now - self.session_start_time
                    final_image_path = None

                    # Capture final image if event lasted >= 2.0s
                    capture_final = app_config.event_grouping.get("capture_final", True)
                    if capture_final and duration >= 2.0 and self._last_annotated_frame is not None:
                        active_paths = event_store.get_active_image_paths()
                        final_image_path = storage_manager.save_event_image(
                            self._last_annotated_frame,
                            self.active_session.get("category", "General motion"),
                            tag="final",
                            active_paths=active_paths,
                        )

                    closed = event_store.close_event_session(self.active_session["id"], final_image_path=final_image_path)
                    if closed:
                        broadcaster.broadcast_sync("event_completed", {
                            "id": closed["id"],
                            "duration_sec": closed.get("details", {}).get("session_duration_sec", 0.0),
                            "final_image_path": final_image_path,
                        })

                    self.active_session = None
                    self._last_annotated_frame = None

            # Periodic Retention Cleanup (Runs every 15 minutes)
            if now - self._last_retention_check >= 900.0:
                self._last_retention_check = now
                try:
                    active_paths = event_store.get_active_image_paths()
                    storage_manager.enforce_retention(active_paths=active_paths)
                except Exception as e:
                    logger.debug(f"Periodic retention check exception: {e}")

            # Metrics tracking
            frame_counter += 1
            now_fps = time.time()
            if now_fps - fps_timer >= 1.0:
                metrics.record_processed_frame(frame_counter / (now_fps - fps_timer))
                frame_counter = 0
                fps_timer = now_fps

            # Pace loop to target motion FPS
            processing_duration = time.time() - loop_start
            sleep_needed = target_motion_interval - processing_duration
            if sleep_needed > 0:
                time.sleep(sleep_needed)

        logger.info("Pipeline processing thread terminated.")


pipeline = PipelineController()
