"""Single camera acquisition worker for PySURVEILLANCE.

Acquires MJPEG stream from IP Webcam on Redmi 10 using a bounded queue
with latest-frame replacement strategy. Handles auto-reconnection, safe
reconfigurations (without stopping the camera server), stream frame verification,
thread-safe pause/resume coordination, and rollback to last working configuration on failure.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import cv2
import httpx
import numpy as np

from wheat_watch.config import app_config
from wheat_watch.metrics import metrics

logger = logging.getLogger("wheat_watch.camera")


class CameraWorker:
    """Manages video acquisition, safe reconfigurations, and recovery for IP Webcam on Redmi 10."""

    STATE_ONLINE = "ONLINE"
    STATE_CONNECTED = "ONLINE"  # Backward compatibility alias
    STATE_RECONFIGURING = "RECONFIGURING"
    STATE_RECONNECTING = "RECONNECTING"
    STATE_CONNECTING = "CONNECTING"
    STATE_OFFLINE = "OFFLINE"
    STATE_DISCONNECTED = "OFFLINE"  # Backward compatibility alias
    STATE_ERROR = "ERROR"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reconfig_lock = threading.Lock()
        self._frame_cond = threading.Condition(self._lock)

        self._latest_raw_frame: Optional[np.ndarray] = None
        self._latest_processed_frame: Optional[np.ndarray] = None
        self._latest_timestamp: float = 0.0

        self.state = self.STATE_OFFLINE
        self.last_error: Optional[str] = None
        self._disconnect_reason: str = "System initialized"
        self.reconnect_attempts = 0
        self.fps = 0.0
        self.latency_ms = 0.0
        self.resolution: Tuple[int, int] = (0, 0)
        self.total_frames = 0

        # Last working configuration preservation for automatic rollbacks
        self._last_working_config: Dict[str, Any] = {
            "resolution": "1280x720",
            "target_width": 1280,
            "target_height": 720,
        }

        # Image Enhancement & Quality controls
        img_cfg = app_config.image_controls
        self.gamma: float = float(img_cfg.get("gamma", 0.75))
        self.brightness: int = int(img_cfg.get("brightness", -15))
        self.contrast: float = float(img_cfg.get("contrast", 1.15))
        self.auto_hdr: bool = bool(img_cfg.get("auto_hdr", False))
        self.stream_quality: int = int(img_cfg.get("quality", 95))
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self._lut_table = self._compute_lut()

        # Detection overlay state
        self._active_detections: list = []
        self._active_motion_boxes: list = []
        self._detections_expiry: float = 0.0
        self._header_text: str = "Monitoring Active"

        self._reconnect_requested: bool = False
        self._is_reconfiguring: bool = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._reconnect_start_time: float = 0.0

        # Thread-safe cooperative pause/resume for reconfiguration
        self._pause_requested = threading.Event()
        self._paused_event = threading.Event()
        self._resume_event = threading.Event()
        self._verified_online_event = threading.Event()
        self._resume_event.set()

        # Cached phone device telemetry (battery, temperature, optics)
        self._phone_telemetry_cache: Optional[Dict[str, Any]] = None
        self._phone_telemetry_time: float = 0.0

    def request_reconnect(self) -> None:
        """Signal acquisition loop to cleanly re-establish stream connection."""
        with self._lock:
            self._reconnect_requested = True
            if self.state in (self.STATE_ONLINE, self.STATE_CONNECTING):
                self.state = self.STATE_RECONNECTING
                self._disconnect_reason = "Camera reconnection requested"

    def _compute_lut(self) -> np.ndarray:
        """Combine gamma correction, contrast, and brightness into a fast 256-byte LUT."""
        inv_gamma = 1.0 / max(0.1, self.gamma)
        table = np.zeros((256,), dtype=np.uint8)
        for i in range(256):
            # 1. Gamma curve (recovers highlights from overexposure)
            val = ((i / 255.0) ** inv_gamma) * 255.0
            # 2. Contrast & brightness
            val = (val - 128.0) * self.contrast + 128.0 + self.brightness
            table[i] = int(np.clip(val, 0, 255))
        return table

    def update_image_controls(self, updates: Dict[str, Any]) -> None:
        """Update live software tone mapping in real-time."""
        with self._lock:
            if "gamma" in updates:
                self.gamma = float(updates["gamma"])
            if "brightness" in updates:
                self.brightness = int(updates["brightness"])
            if "contrast" in updates:
                self.contrast = float(updates["contrast"])
            if "auto_hdr" in updates:
                self.auto_hdr = bool(updates["auto_hdr"])
            if "quality" in updates:
                self.stream_quality = int(updates["quality"])
            self._lut_table = self._compute_lut()
        logger.info(
            f"Updated software image controls: gamma={self.gamma}, brightness={self.brightness}, "
            f"contrast={self.contrast}, hdr={self.auto_hdr}"
        )

    def enhance_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply real-time exposure correction and tone mapping."""
        if self._lut_table is None:
            return frame
        adjusted = cv2.LUT(frame, self._lut_table)
        if self.auto_hdr:
            lab = cv2.cvtColor(adjusted, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l2 = self._clahe.apply(l)
            adjusted = cv2.cvtColor(cv2.merge((l2, a, b)), cv2.COLOR_LAB2BGR)
        return adjusted

    def get_camera_hw_curvals(self, timeout: float = 1.5) -> Optional[Dict[str, Any]]:
        """Fetch active hardware settings directly from Redmi 10 IP Webcam."""
        cam = app_config.camera
        ip = cam.get("phone_ip", "192.168.31.211")
        port = cam.get("phone_port", 8080)
        try:
            r = httpx.get(f"http://{ip}:{port}/status.json", timeout=timeout)
            if r.status_code == 200:
                return r.json().get("curvals", {})
        except Exception as e:
            logger.debug(f"Failed to query camera status.json: {e}")
        return None

    def get_phone_device_telemetry(self, max_cache_age: float = 3.0) -> Dict[str, Any]:
        """Fetch real-time phone diagnostics including battery, temperature, optics and sensor status."""
        now = time.time()
        if self._phone_telemetry_cache and (now - self._phone_telemetry_time < max_cache_age):
            return self._phone_telemetry_cache

        cam = app_config.camera
        ip = cam.get("phone_ip", "192.168.31.211")
        port = cam.get("phone_port", 8080)

        curvals: Dict[str, Any] = {}
        video_connections = 0
        audio_connections = 0
        try:
            r = httpx.get(f"http://{ip}:{port}/status.json", timeout=1.8)
            if r.status_code == 200:
                data = r.json()
                curvals = data.get("curvals", {})
                video_connections = data.get("video_connections", 0)
                audio_connections = data.get("audio_connections", 0)
        except Exception:
            pass

        sensors: Dict[str, Any] = {}
        try:
            r_sen = httpx.get(f"http://{ip}:{port}/sensors.json", timeout=1.8)
            if r_sen.status_code == 200:
                sensors = r_sen.json()
        except Exception:
            pass

        def extract_latest(sensor_obj: Any) -> Optional[float]:
            if isinstance(sensor_obj, dict) and "data" in sensor_obj and sensor_obj["data"]:
                latest = sensor_obj["data"][-1]
                if len(latest) >= 2 and latest[1]:
                    try:
                        return float(latest[1][0])
                    except (ValueError, TypeError, IndexError):
                        pass
            return None

        battery_level = extract_latest(sensors.get("battery_level"))
        battery_temp = extract_latest(sensors.get("battery_temp"))
        battery_voltage = extract_latest(sensors.get("battery_voltage"))
        ambient_temp = extract_latest(sensors.get("temp")) or extract_latest(sensors.get("ambient_temp"))
        ambient_lux = extract_latest(sensors.get("light"))

        sensors_enabled = bool(sensors and len(sensors) > 0)

        res = {
            "model": "Redmi 10 (IP Webcam)",
            "phone_ip": ip,
            "phone_port": port,
            "is_online": self.state == self.STATE_ONLINE,
            "video_connections": video_connections,
            "audio_connections": audio_connections,
            "battery_level": round(battery_level, 1) if battery_level is not None else None,
            "battery_temp": round(battery_temp, 1) if battery_temp is not None else None,
            "battery_voltage": round(battery_voltage, 2) if battery_voltage is not None else None,
            "ambient_temp": round(ambient_temp, 1) if ambient_temp is not None else None,
            "ambient_lux": round(ambient_lux, 1) if ambient_lux is not None else None,
            "sensors_logging_enabled": sensors_enabled,
            "sensor_help_hint": "Live sensors active." if sensors_enabled else "In IP Webcam on Redmi 10: Scroll down to Data logging ➔ enable 'Log sensors' to stream live battery % & temperature.",
            "torch": curvals.get("torch", "off"),
            "flashmode": curvals.get("flashmode", "off"),
            "night_vision": curvals.get("night_vision", "off"),
            "iso": curvals.get("iso", "auto"),
            "aperture": curvals.get("aperture", "1.8"),
            "focal_length": curvals.get("focal_length", "4.266"),
            "exposure_ns": curvals.get("exposure_ns"),
            "video_size": curvals.get("video_size", "1920x1080"),
            "timestamp": now,
        }

        self._phone_telemetry_cache = res
        self._phone_telemetry_time = now
        return res

    def send_camera_command(self, cmd: str, val: Any) -> bool:
        """Send hardware control commands directly to Redmi 10 IP Webcam."""
        cam = app_config.camera
        ip = cam.get("phone_ip", "192.168.31.211")
        port = cam.get("phone_port", 8080)
        try:
            if cmd == "torch":
                ep = "/enabletorch" if val else "/disabletorch"
                httpx.get(f"http://{ip}:{port}{ep}", timeout=2.0)
            elif cmd == "night_vision":
                nv = "on" if val else "off"
                httpx.get(f"http://{ip}:{port}/settings/night_vision?set={nv}", timeout=2.0)
            elif cmd == "exposure_compensation":
                httpx.get(f"http://{ip}:{port}/settings/exposure?set={val}", timeout=2.0)
            elif cmd == "quality":
                httpx.get(f"http://{ip}:{port}/settings/quality?set={val}", timeout=2.0)
            elif cmd == "white_balance":
                httpx.get(f"http://{ip}:{port}/settings/whitebalance?set={val}", timeout=2.0)
            elif cmd == "resolution":
                httpx.get(f"http://{ip}:{port}/settings/video_size?set={val}", timeout=3.0)
            return True
        except Exception as e:
            logger.error(f"Failed to send camera command {cmd}={val}: {e}")
            return False

    def _verify_stream_frames(
        self,
        cap: cv2.VideoCapture,
        required_frames: int = 2,
        timeout_sec: float = 3.5,
    ) -> Tuple[bool, Optional[np.ndarray]]:
        """Read and verify valid decodable frames from an open stream before declaring online."""
        t_start = time.time()
        valid_count = 0
        last_frame = None
        while time.time() - t_start < timeout_sec:
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                valid_count += 1
                last_frame = frame
                if valid_count >= required_frames:
                    return True, last_frame
            time.sleep(0.04)
        return False, None

    def reconfigure_camera(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Safely apply camera configuration with cooperative thread pausing and rollback support."""
        if not self._reconfig_lock.acquire(blocking=False):
            return {
                "success": False,
                "state": self.state,
                "message": "Camera is currently reconfiguring. Please wait for completion.",
            }

        try:
            self._is_reconfiguring = True
            with self._lock:
                self.state = self.STATE_RECONFIGURING
                self._disconnect_reason = f"Reconfiguring camera settings: {list(updates.keys())}"
                self.last_error = None
                self.fps = 0.0

            logger.info(f"[RECONFIGURING] {self._disconnect_reason}")
            from wheat_watch.broadcaster import broadcaster
            broadcaster.broadcast_sync("camera_reconfiguring", {
                "message": "Applying camera settings. Reconfiguring video stream...",
                "updates": list(updates.keys()),
            })

            # 1. Update software LUT controls immediately (client-side latency free)
            self.update_image_controls(updates)

            cam = app_config.camera
            ip = cam.get("phone_ip", "192.168.31.211")
            port = cam.get("phone_port", 8080)

            # Query phone's current hardware state to avoid redundant command spam
            hw_curvals = self.get_camera_hw_curvals(timeout=2.0) or {}
            current_hw_res = hw_curvals.get("video_size")

            target_res = updates.get("resolution")
            res_change_needed = bool(target_res and (target_res != current_hw_res))

            # Validate target dimensions and check against supported resolutions
            new_w, new_h = 1280, 720
            supported_sizes = (
                "1920x1080", "1280x720", "640x480", "1280x576", "1080x1080",
                "1024x768", "800x600", "800x480", "720x480", "640x360", "320x240"
            )
            if res_change_needed:
                if target_res not in supported_sizes:
                    logger.warning(f"Unsupported resolution '{target_res}' requested. Rejecting.")
                    return {
                        "success": False,
                        "state": self.state,
                        "message": f"Resolution '{target_res}' is not supported by phone camera.",
                        "resolution": self._last_working_config.get("resolution", "1280x720"),
                    }
                try:
                    parts = target_res.split("x")
                    new_w, new_h = int(parts[0]), int(parts[1])
                except Exception as e:
                    logger.error(f"Invalid resolution format '{target_res}': {e}")
                    res_change_needed = False

            if res_change_needed:
                # Store last working config before release
                if self.resolution[0] > 0 and self.resolution[1] > 0:
                    self._last_working_config = {
                        "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
                        "target_width": self.resolution[0],
                        "target_height": self.resolution[1],
                    }

                # Step A: Cooperatively request _run_loop to cleanly release VideoCapture and pause
                logger.info("[RECONFIGURING] Requesting stream reader cooperative pause and clean socket closure...")
                self._resume_event.clear()
                self._paused_event.clear()
                self._pause_requested.set()
                self._paused_event.wait(timeout=2.5)
                logger.info("[RECONFIGURING] Stream reader paused. Camera socket cleanly closed.")

                # Step B: Dispatch resolution command to Redmi 10
                try:
                    cfg_url = f"http://{ip}:{port}/settings/video_size?set={target_res}"
                    resp = httpx.get(cfg_url, timeout=4.0)
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code} from /settings/video_size")
                    logger.info(f"[RECONFIGURING] Dispatched video_size={target_res} successfully.")
                except Exception as e:
                    logger.error(f"Failed to set video_size={target_res}: {e}")
                    return self._rollback_and_restore(f"Camera rejected video_size command: {e}")

                # Step C: Give phone camera sensor 600ms to settle preview session
                time.sleep(0.6)

                # Step D: Poll phone status to verify it has applied the new resolution
                poll_ok = False
                for attempt in range(8):
                    cur = self.get_camera_hw_curvals(timeout=1.5)
                    if cur and cur.get("video_size") == target_res:
                        poll_ok = True
                        break
                    time.sleep(0.35)

                if not poll_ok:
                    logger.warning(f"Phone did not confirm video_size={target_res} within polling window.")

            # Apply other hardware settings sequentially with pacing
            if "quality" in updates and str(updates["quality"]) != str(hw_curvals.get("quality")):
                time.sleep(0.15)
                try:
                    httpx.get(f"http://{ip}:{port}/settings/quality?set={updates['quality']}", timeout=2.0)
                except Exception as e:
                    logger.debug(f"Paced quality update: {e}")

            if "night_vision" in updates:
                desired_nv = "on" if updates["night_vision"] else "off"
                if desired_nv != hw_curvals.get("night_vision"):
                    time.sleep(0.15)
                    try:
                        httpx.get(f"http://{ip}:{port}/settings/night_vision?set={desired_nv}", timeout=2.0)
                    except Exception as e:
                        logger.debug(f"Paced night_vision update: {e}")

            if "white_balance" in updates and str(updates["white_balance"]) != str(hw_curvals.get("whitebalance")):
                time.sleep(0.15)
                try:
                    httpx.get(f"http://{ip}:{port}/settings/whitebalance?set={updates['white_balance']}", timeout=2.0)
                except Exception as e:
                    logger.debug(f"Paced white_balance update: {e}")

            if "torch" in updates:
                from wheat_watch.flashlight import flashlight_controller
                flashlight_controller.handle_manual_torch_toggle(bool(updates["torch"]))

            # Persist image_controls to config
            current_cfg = dict(app_config.image_controls)
            current_cfg.update(updates)
            app_config.update({"image_controls": current_cfg})

            if res_change_needed:
                # Step E: Resume stream reader loop and wait for verified frame acquisition
                logger.info("[RECONFIGURING] Resuming stream reader and awaiting verified frame acquisition...")
                self._verified_online_event.clear()
                self._pause_requested.clear()
                self._resume_event.set()

                # Wait up to 6.0 seconds for reader thread to connect and verify frames
                online_ok = self._verified_online_event.wait(timeout=6.0)
                if not online_ok:
                    return self._rollback_and_restore(f"Stream verification timed out at {target_res}")

                # Success! Update pipeline target dimensions and last working config
                app_config.pipeline["target_width"] = new_w
                app_config.pipeline["target_height"] = new_h
                from wheat_watch.motion import motion_detector
                motion_detector.trigger_stabilization(count=20)

                self._last_working_config = {
                    "resolution": target_res,
                    "target_width": new_w,
                    "target_height": new_h,
                }
            else:
                with self._lock:
                    if self.state != self.STATE_ONLINE and self.total_frames > 0:
                        self.state = self.STATE_ONLINE

            return {
                "success": True,
                "message": f"Camera reconfigured to {self.resolution[0]}x{self.resolution[1]} successfully.",
                "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
                "controls": current_cfg,
            }

        finally:
            self._pause_requested.clear()
            self._resume_event.set()
            self._is_reconfiguring = False
            self._reconfig_lock.release()

    def _rollback_and_restore(self, reason: str) -> Dict[str, Any]:
        """Rollback to last working camera configuration when a new configuration fails."""
        last_cfg = dict(self._last_working_config)
        fallback_res = last_cfg.get("resolution", "1280x720")
        fallback_w = last_cfg.get("target_width", 1280)
        fallback_h = last_cfg.get("target_height", 720)
        logger.warning(f"[ROLLBACK] {reason}. Reverting to last working configuration: {fallback_res}")

        # Pause reader thread cooperatively
        self._resume_event.clear()
        self._paused_event.clear()
        self._pause_requested.set()
        self._paused_event.wait(timeout=2.0)

        cam = app_config.camera
        ip = cam.get("phone_ip", "192.168.31.211")
        port = cam.get("phone_port", 8080)

        try:
            httpx.get(f"http://{ip}:{port}/settings/video_size?set={fallback_res}", timeout=4.0)
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to dispatch rollback command: {e}")

        app_config.pipeline["target_width"] = fallback_w
        app_config.pipeline["target_height"] = fallback_h

        # Resume reader to reconnect fallback
        self._verified_online_event.clear()
        self._pause_requested.clear()
        self._resume_event.set()

        online_ok = self._verified_online_event.wait(timeout=6.0)

        with self._lock:
            if online_ok:
                self.state = self.STATE_ONLINE
                self.last_error = f"Configuration failed ({reason}). Reverted to {fallback_res}."
                msg = f"Reconfiguration failed. Restored last working resolution ({fallback_res})."
                success = False
            else:
                self.state = self.STATE_ERROR
                self.last_error = f"Reconfiguration failed and rollback failed: {reason}"
                msg = f"Critical error: could not restore stream: {self.last_error}"
                success = False

        from wheat_watch.broadcaster import broadcaster
        broadcaster.broadcast_sync("camera_rollback", {
            "error": reason,
            "restored_resolution": fallback_res,
            "state": self.state,
        })
        return {"success": success, "message": msg, "resolution": fallback_res, "error": reason}

    def reset_camera_settings(self) -> Dict[str, Any]:
        """Reset camera settings to balanced anti-glare surveillance defaults safely."""
        defaults = {
            "resolution": "1280x720",
            "quality": 95,
            "gamma": 0.75,
            "brightness": -15,
            "contrast": 1.15,
            "auto_hdr": False,
            "torch": False,
            "night_vision": False,
        }
        logger.info("[RECONFIGURING] Resetting camera settings to defaults.")
        return self.reconfigure_camera(defaults)

    def set_active_detections(
        self,
        detections: list,
        motion_boxes: list,
        header_text: str = "Monitoring Active",
        duration: float = 1.5,
    ) -> None:
        """Update detection overlay to be rendered at full camera acquisition FPS."""
        with self._lock:
            self._active_detections = detections
            self._active_motion_boxes = motion_boxes
            self._header_text = header_text
            self._detections_expiry = time.time() + duration

    def clear_active_detections(self) -> None:
        with self._lock:
            self._active_detections = []
            self._active_motion_boxes = []
            self._header_text = "Monitoring Active (Quiet)"

    def start(self) -> None:
        """Start camera reader worker."""
        if self._running:
            return
        self._running = True
        self._pause_requested.clear()
        self._paused_event.clear()
        self._resume_event.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CameraWorker")
        self._thread.start()
        logger.info("CameraWorker background thread started.")

    def stop(self) -> None:
        """Stop camera reader worker."""
        self._running = False
        self._pause_requested.set()
        self._resume_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        with self._lock:
            self.state = self.STATE_OFFLINE
        logger.info("CameraWorker stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return real-time camera connection status."""
        with self._lock:
            return {
                "state": self.state,
                "is_online": (self.state == self.STATE_ONLINE),
                "last_error": self.last_error,
                "disconnect_reason": self._disconnect_reason,
                "reconnect_attempts": self.reconnect_attempts,
                "fps": round(self.fps, 1),
                "latency_ms": round(self.latency_ms, 1),
                "resolution": f"{self.resolution[0]}x{self.resolution[1]}" if self.resolution[0] > 0 else "N/A",
                "last_working_resolution": self._last_working_config.get("resolution", "1280x720"),
                "total_frames": self.total_frames,
                "last_frame_age_sec": round(time.time() - self._latest_timestamp, 2) if self._latest_timestamp > 0 else None,
                "stream_url": app_config.camera_video_url,
                "snapshot_url": app_config.camera_snapshot_url,
            }

    def get_latest_frame(self, processed: bool = True) -> Optional[np.ndarray]:
        """Fetch latest acquired frame (bounded queue / latest-frame strategy)."""
        with self._lock:
            if processed and self._latest_processed_frame is not None:
                return self._latest_processed_frame.copy()
            if self._latest_raw_frame is not None:
                return self._latest_raw_frame.copy()
            return None

    def set_processed_frame(self, frame: np.ndarray) -> None:
        """Update live preview with annotated detections."""
        with self._lock:
            self._latest_processed_frame = frame
            self._frame_cond.notify_all()

    def wait_for_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Wait until a new frame is received or timeout occurs."""
        with self._frame_cond:
            if self._frame_cond.wait(timeout=timeout):
                if self._latest_raw_frame is not None:
                    return self._latest_raw_frame.copy()
        return None

    def _run_loop(self) -> None:
        """Main acquisition and auto-reconnection loop. Sole owner of cv2.VideoCapture."""
        target_w = app_config.pipeline.get("target_width", 1280)
        target_h = app_config.pipeline.get("target_height", 720)

        reconnect_delay = float(app_config.camera.get("reconnect_delay_sec", 2.0))
        backoff_multiplier = float(app_config.camera.get("reconnect_backoff", 1.5))
        max_reconnect_delay = float(app_config.camera.get("max_reconnect_delay_sec", 15.0))
        reconnect_timeout = float(app_config.camera.get("reconnect_timeout_sec", 60.0))

        frame_count = 0
        fps_timer = time.time()
        consecutive_read_failures = 0
        cap: Optional[cv2.VideoCapture] = None

        while self._running:
            # 1. Cooperative pause check (for clean, exclusive hardware reconfigurations)
            if self._pause_requested.is_set():
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                self._paused_event.set()
                self._resume_event.wait(timeout=0.25)
                continue

            # 2. Check if we need to open stream connection
            if cap is None or not cap.isOpened():
                url = app_config.camera_video_url

                if self.reconnect_attempts == 0:
                    self._reconnect_start_time = time.time()
                    with self._lock:
                        if not self._is_reconfiguring and self.state != self.STATE_RECONNECTING:
                            self.state = self.STATE_CONNECTING
                else:
                    elapsed = time.time() - self._reconnect_start_time
                    with self._lock:
                        if elapsed > reconnect_timeout:
                            self.state = self.STATE_OFFLINE
                            self.last_error = f"Camera offline: unreachable after {self.reconnect_attempts} attempts ({elapsed:.1f}s)."
                        elif not self._is_reconfiguring:
                            self.state = self.STATE_RECONNECTING
                            self.last_error = f"Reconnecting attempt #{self.reconnect_attempts} ({self._disconnect_reason})"

                logger.info(
                    f"[{self.state}] Connecting to camera stream at {url} "
                    f"(attempt #{self.reconnect_attempts})..."
                )

                try:
                    t_start = time.time()
                    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                    if not cap.isOpened():
                        raise RuntimeError(f"Could not open MJPEG stream at {url}")

                    # Read & verify initial stream frames
                    verified, first_frame = self._verify_stream_frames(cap, required_frames=2, timeout_sec=3.5)
                    if not verified or first_frame is None:
                        raise RuntimeError("Stream connected but frames could not be decoded.")

                    self.latency_ms = (time.time() - t_start) * 1000.0
                    self.reconnect_attempts = 0
                    consecutive_read_failures = 0

                    with self._lock:
                        prev_state = self.state
                        self.state = self.STATE_ONLINE
                        self.last_error = None
                        self._disconnect_reason = ""
                        self.resolution = (first_frame.shape[1], first_frame.shape[0])
                        self._latest_raw_frame = first_frame
                        self._latest_timestamp = time.time()
                        self.total_frames += 1
                        self._frame_cond.notify_all()

                    self._verified_online_event.set()

                    if prev_state != self.STATE_ONLINE:
                        logger.info(
                            f"[ONLINE] Connected to camera stream successfully ({self.resolution[0]}x{self.resolution[1]}). "
                            f"Surveillance active."
                        )
                        from wheat_watch.broadcaster import broadcaster
                        broadcaster.broadcast_sync("camera_connected", {
                            "message": "Camera online. Surveillance active.",
                            "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
                        })

                except Exception as e:
                    err_msg = str(e)
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
                    cap = None
                    self.reconnect_attempts += 1
                    self.fps = 0.0

                    sleep_time = min(
                        reconnect_delay * (backoff_multiplier ** min(self.reconnect_attempts - 1, 6)),
                        max_reconnect_delay,
                    )
                    logger.warning(
                        f"[{self.state}] Camera connection attempt #{self.reconnect_attempts} failed: {err_msg}. "
                        f"Retrying in {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)
                    continue

            # 3. Read active frame from open capture
            try:
                if self._reconnect_requested:
                    self._reconnect_requested = False
                    logger.info("[RECONNECT] User requested camera reconnection.")
                    with self._lock:
                        self.state = self.STATE_RECONNECTING
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
                        cap = None
                    continue

                ret, raw_frame = cap.read()
                if not ret or raw_frame is None:
                    consecutive_read_failures += 1
                    if consecutive_read_failures > 15:
                        raise RuntimeError("Exceeded maximum consecutive read errors from video stream.")
                    time.sleep(0.04)
                    continue

                consecutive_read_failures = 0
                now = time.time()

                # Scale frame to current pipeline target size if needed
                target_w = app_config.pipeline.get("target_width", 1280)
                target_h = app_config.pipeline.get("target_height", 720)
                h, w = raw_frame.shape[:2]
                if w != target_w or h != target_h:
                    frame_to_store = cv2.resize(raw_frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
                else:
                    frame_to_store = raw_frame

                # Tone mapping / enhancement
                frame_to_store = self.enhance_frame(frame_to_store)

                with self._lock:
                    self._latest_raw_frame = frame_to_store
                    self._latest_timestamp = now
                    self.total_frames += 1
                    self.resolution = (frame_to_store.shape[1], frame_to_store.shape[0])

                    from wheat_watch.detector import detector
                    if now < self._detections_expiry and (self._active_detections or self._active_motion_boxes):
                        self._latest_processed_frame = detector.annotate_frame(
                            frame_to_store,
                            detections=self._active_detections,
                            motion_boxes=self._active_motion_boxes,
                            header_text=self._header_text,
                        )
                    else:
                        self._latest_processed_frame = detector.annotate_frame(
                            frame_to_store,
                            detections=[],
                            motion_boxes=[],
                            header_text=self._header_text if self._header_text else "Monitoring Active",
                        )

                    self._frame_cond.notify_all()

                frame_count += 1
                elapsed = now - fps_timer
                if elapsed >= 1.0:
                    self.fps = frame_count / elapsed
                    metrics.record_camera_frame(self.fps)
                    frame_count = 0
                    fps_timer = now

            except Exception as e:
                err_msg = str(e)
                was_online = False
                with self._lock:
                    was_online = (self.state == self.STATE_ONLINE)
                    if not self._is_reconfiguring:
                        self.state = self.STATE_RECONNECTING
                        self._disconnect_reason = f"Stream read error: {err_msg}"
                        self.last_error = err_msg
                        self.reconnect_attempts += 1
                    self.fps = 0.0

                logger.warning(f"[DISCONNECTED] Camera stream disconnected: {self._disconnect_reason}")
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None

                if was_online and not self._is_reconfiguring:
                    from wheat_watch.audio import audio_manager
                    audio_manager.play_disconnect_alert()
                    from wheat_watch.broadcaster import broadcaster
                    broadcaster.broadcast_sync("camera_disconnected", {
                        "reason": self._disconnect_reason,
                        "reconnect_attempts": self.reconnect_attempts,
                    })

                time.sleep(reconnect_delay)

        # Cleanup on exit
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    @staticmethod
    def test_connection(
        phone_ip: str,
        phone_port: int,
        video_endpoint: str = "/video",
        snapshot_endpoint: str = "/shot.jpg",
        timeout: float = 3.0,
    ) -> Dict[str, Any]:
        """Test reachability and camera response for configuration dialog."""
        # Step 1: TCP Port check
        t0 = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((phone_ip, phone_port))
            s.close()
        except Exception as e:
            return {
                "success": False,
                "stage": "tcp_connect",
                "error": f"Cannot connect to {phone_ip}:{phone_port} - {e}",
                "message": "TCP port is unreachable. Ensure phone is on the same Wi-Fi and IP Webcam server is started.",
            }

        tcp_latency_ms = (time.time() - t0) * 1000.0

        # Step 2: HTTP Snapshot test
        snap_ep = snapshot_endpoint if snapshot_endpoint.startswith("/") else f"/{snapshot_endpoint}"
        snap_url = f"http://{phone_ip}:{phone_port}{snap_ep}"

        try:
            t1 = time.time()
            resp = httpx.get(snap_url, timeout=timeout)
            http_latency_ms = (time.time() - t1) * 1000.0

            if resp.status_code != 200:
                return {
                    "success": False,
                    "stage": "snapshot_http",
                    "status_code": resp.status_code,
                    "error": f"HTTP {resp.status_code} returned from {snap_url}",
                    "message": "Phone responded but snapshot endpoint failed.",
                }

            # Verify image decode
            img_arr = np.frombuffer(resp.content, np.uint8)
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            if img is None:
                return {
                    "success": False,
                    "stage": "image_decode",
                    "error": "Failed to decode JPEG from snapshot response.",
                }

            h, w = img.shape[:2]
            server_header = resp.headers.get("server", "IP Webcam")

            return {
                "success": True,
                "tcp_latency_ms": round(tcp_latency_ms, 1),
                "http_latency_ms": round(http_latency_ms, 1),
                "resolution": f"{w}x{h}",
                "server": server_header,
                "bytes_received": len(resp.content),
                "message": f"Connection verified! Camera active at {w}x{h} ({http_latency_ms:.1f}ms latency).",
            }

        except Exception as e:
            return {
                "success": False,
                "stage": "http_request",
                "error": str(e),
                "message": f"HTTP test failed: {e}",
            }


camera_worker = CameraWorker()
