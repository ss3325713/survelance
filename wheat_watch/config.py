"""Wheat Watch Configuration Manager.

Handles persistent configuration, validation, and defaults.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("wheat_watch.config")

CONFIG_FILE_PATH = Path("wheat_watch_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    # Camera Configuration (Supports generic IP cameras and smartphones via HTTP/MJPEG and RTSP)
    "camera": {
        "source_name": "IP Camera",
        "device_profile": "auto",  # "auto", "ip_webcam", "generic"
        "camera_host": "127.0.0.1",
        "camera_port": 8080,
        "phone_ip": "127.0.0.1",  # Backward-compatibility alias
        "phone_port": 8080,        # Backward-compatibility alias
        "video_url": "",           # Full stream URL (e.g. http://<IP>:<PORT>/video or rtsp://<IP>/stream)
        "snapshot_url": "",        # Full snapshot URL (e.g. http://<IP>:<PORT>/shot.jpg)
        "audio_url": "",           # Full audio stream URL (e.g. http://<IP>:<PORT>/audio.wav)
        "video_endpoint": "/video",
        "snapshot_endpoint": "/shot.jpg",
        "audio_endpoint": "/audio.wav",
        "username": "",
        "password": "",
        "timeout_sec": 5.0,
        "reconnect_delay_sec": 2.0,
        "reconnect_backoff": 1.5,
        "max_reconnect_delay_sec": 15.0,
        "reconnect_timeout_sec": 60.0,
    },
    # Dashboard & Server Configuration
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
        "dashboard_pin": "****",
        "dashboard_pin_hash": "",
        "dashboard_pin_salt": "",
        "pin_required": True,
        "pin_initialized": False,
        "session_secret": secrets.token_hex(32),
        "restrict_local_network": True,
    },
    # Pipeline & Processing Performance
    "pipeline": {
        "target_width": 1280,
        "target_height": 720,
        "motion_fps": 8.0,
        "motion_threshold": 25,
        "min_motion_area": 250,
        "max_motion_percent": 22.0,
        "require_motion_overlap": True,
        "ai_fps": 1.5,
        "detection_confidence": 0.45,
        "auto_throttle_cpu": True,
        "cpu_throttle_threshold": 85.0,
        "monkey_model_path": "models/monkey_classifier.onnx",
    },
    # Camera Image Quality & Exposure Controls
    "image_controls": {
        "resolution": "1280x720",
        "quality": 95,
        "exposure_compensation": -2,
        "gamma": 0.75,
        "brightness": -15,
        "contrast": 1.15,
        "auto_hdr": False,
        "white_balance": "auto",
        "torch": False,
        "night_vision": False,
    },
    # Alarm System
    "alarm": {
        "sound_enabled": True,
        "volume": 1.0,
        "alarm_on_general_motion": False,
        "alarm_on_unknown_objects": False,
        "alert_categories": [
            "Person",
            "Bird",
            "Animal detected — species unconfirmed",
            "Other recognized animal",
            "Possible monkey",
        ],
        "cooldowns": {
            "General motion": 15,
            "Person": 30,
            "Bird": 20,
            "Other recognized animal": 25,
            "Animal detected — species unconfirmed": 25,
            "Possible monkey": 15,
            "Unknown object": 20,
        },
    },
    # Power Management
    "power": {
        "prevent_sleep": True,
    },
    # Force Push Messages to Connected Browsers
    "push": {
        "enabled": True,
        "browser_audio": True,
        "desktop_notifications": True,
        "push_on_general_motion": False,
        "push_on_unknown_objects": False,
        "min_confidence": 0.35,
        "alert_categories": [
            "Person",
            "Bird",
            "Animal detected — species unconfirmed",
            "Other recognized animal",
            "Possible monkey",
        ],
    },
    # Night Surveillance Mode
    "night_mode": {
        "mode": "auto",  # "off", "on", "auto"
        "auto_threshold": 45.0,  # Below this mean luminance triggers night profile
        "hysteresis": 8.0,
        "day": {
            "motion_threshold": 25,
            "min_motion_area": 250,
            "max_motion_percent": 22.0,
            "light_change_threshold": 7.5,
            "motion_fps": 8.0,
            "ai_fps": 1.5,
        },
        "night": {
            "motion_threshold": 34,
            "min_motion_area": 350,
            "max_motion_percent": 18.0,
            "light_change_threshold": 12.0,
            "motion_fps": 6.0,
            "ai_fps": 1.0,
        },
    },
    # Event Deduplication & Grouping
    "event_grouping": {
        "enabled": True,
        "cooldown_sec": 10.0,
        "session_timeout_sec": 4.0,  # Motion pause to finalize event
        "capture_initial": True,
        "capture_change": True,
        "capture_final": True,
    },
    # Storage & Persistence
    "storage": {
        "events_dir": "storage/events",
        "db_path": "storage/events.db",
        "retention_days": 14,
        "max_storage_mb": 2048,
    },
    # Automatic Flashlight Control
    "flashlight": {
        "mode": "auto",  # "auto", "manual", "off"
        "lux_threshold": 45.0,
        "min_on_time_sec": 10.0,
        "max_on_time_sec": 120.0,
        "inactivity_timeout_sec": 15.0,
        "stabilization_frames": 15,
    },
    # Local Microphone Ambient Sound Activity Detection
    "audio_detection": {
        "enabled": True,
        "sample_rate": 16000,
        "chunk_size": 1600,
        "spike_multiplier": 3.0,
        "sustained_threshold_rms": 2500.0,
        "min_trigger_rms": 1800.0,
        "consecutive_sustained_windows": 2,
        "noise_floor_alpha": 0.05,
        "activity_cooldown_sec": 1.0,
    },
    # Motion-Triggered Video Recording & Background Incident Processing
    "video_recording": {
        "enabled": True,
        "inactivity_timeout_sec": 15.0,
        "max_segment_duration_sec": 60.0,
        "recording_fps": 10.0,
        "temp_storage_dir": "storage/temp_recordings",
        "background_concurrency": 1,
        "max_extracted_frames": 6,
        "min_sharpness": 35.0,
    },
}


class Config:
    def __init__(self, config_dict: Dict[str, Any]) -> None:
        self._data = config_dict

    @classmethod
    def load(cls) -> "Config":
        EXPOSED_SECRETS = {
            "d9cf8c1fe9c4aed7a04c564aebf364c8a52fc1aa9afd036def9297e172679649",
        }
        EXPOSED_HASHES = {
            "7f75353ea4783e6eb52a0b53f49af9b0c9d4e52f994b1aee10e7c614897c9a57",
        }

        if CONFIG_FILE_PATH.exists():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                merged = cls._merge_defaults(DEFAULT_CONFIG, data)
                server_cfg = merged.setdefault("server", {})

                # Rotate exposed or missing session secret
                if not server_cfg.get("session_secret") or server_cfg.get("session_secret") in EXPOSED_SECRETS:
                    server_cfg["session_secret"] = secrets.token_hex(32)
                    logger.info("Generated and rotated fresh session secret token.")

                # Invalidate exposed PIN hash
                if server_cfg.get("dashboard_pin_hash") in EXPOSED_HASHES:
                    server_cfg["dashboard_pin_hash"] = ""
                    server_cfg["dashboard_pin_salt"] = ""
                    server_cfg["dashboard_pin"] = "****"
                    server_cfg["pin_initialized"] = False
                    logger.warning("Revoked exposed master PIN hash. Safe reinitialization required.")

                # Check for existing valid salted hash
                has_hash = bool(server_cfg.get("dashboard_pin_hash") and server_cfg.get("dashboard_pin_salt"))
                
                # Check for environment variable initial PIN override (for automated headless setups/testing)
                env_pin = os.environ.get("PYSURVEILLANCE_INITIAL_PIN")
                if not has_hash and env_pin and len(env_pin.strip()) >= 4:
                    from wheat_watch.security import hash_pin
                    h, s = hash_pin(env_pin.strip())
                    server_cfg["dashboard_pin_hash"] = h
                    server_cfg["dashboard_pin_salt"] = s
                    server_cfg["dashboard_pin"] = "****"
                    server_cfg["pin_initialized"] = True
                    has_hash = True
                elif not has_hash:
                    # Check if legacy plaintext PIN was specified
                    raw_pin = server_cfg.get("dashboard_pin")
                    if raw_pin and raw_pin != "****":
                        from wheat_watch.security import hash_pin
                        h, s = hash_pin(str(raw_pin))
                        server_cfg["dashboard_pin_hash"] = h
                        server_cfg["dashboard_pin_salt"] = s
                        server_cfg["dashboard_pin"] = "****"
                        server_cfg["pin_initialized"] = True
                        has_hash = True
                    else:
                        server_cfg["pin_initialized"] = False
                else:
                    server_cfg["pin_initialized"] = True

                instance = cls(merged)
                instance.save()
                return instance
            except Exception as e:
                logger.error(f"Failed to load config, falling back to defaults: {e}")

        # Fresh default config (when wheat_watch_config.json does not exist)
        example_path = Path("wheat_watch_config.example.json")
        base_data = dict(DEFAULT_CONFIG)
        if example_path.exists():
            try:
                with open(example_path, "r", encoding="utf-8") as f:
                    ex_data = json.load(f)
                base_data = cls._merge_defaults(base_data, ex_data)
            except Exception as e:
                logger.warning(f"Failed to read example config template: {e}")

        instance = cls(base_data)
        server_cfg = instance._data.setdefault("server", {})
        server_cfg["session_secret"] = secrets.token_hex(32)

        env_pin = os.environ.get("PYSURVEILLANCE_INITIAL_PIN")
        if env_pin and len(env_pin.strip()) >= 4:
            from wheat_watch.security import hash_pin
            h, s = hash_pin(env_pin.strip())
            server_cfg["dashboard_pin_hash"] = h
            server_cfg["dashboard_pin_salt"] = s
            server_cfg["dashboard_pin"] = "****"
            server_cfg["pin_initialized"] = True
        else:
            server_cfg["dashboard_pin_hash"] = ""
            server_cfg["dashboard_pin_salt"] = ""
            server_cfg["dashboard_pin"] = "****"
            server_cfg["pin_initialized"] = False

        instance.save()
        return instance

    @staticmethod
    def _merge_defaults(defaults: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(defaults)
        for key, val in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = Config._merge_defaults(result[key], val)
            else:
                result[key] = val
        return result

    def save(self) -> None:
        try:
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            logger.info("Configuration saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def update(self, updates: Dict[str, Any]) -> None:
        if "server" in updates and isinstance(updates["server"], dict):
            new_pin = updates["server"].pop("dashboard_pin", None)
            if new_pin and new_pin != "****":
                from wheat_watch.security import hash_pin
                h, s = hash_pin(str(new_pin))
                updates["server"]["dashboard_pin_hash"] = h
                updates["server"]["dashboard_pin_salt"] = s
                updates["server"]["dashboard_pin"] = "****"
                updates["server"]["pin_initialized"] = True
            else:
                if "dashboard_pin_hash" in self._data.get("server", {}):
                    updates["server"].setdefault("dashboard_pin_hash", self._data["server"]["dashboard_pin_hash"])
                    updates["server"].setdefault("dashboard_pin_salt", self._data["server"]["dashboard_pin_salt"])
                    updates["server"]["pin_initialized"] = bool(self._data["server"]["dashboard_pin_hash"])
                updates["server"]["dashboard_pin"] = "****"
        self._data = self._merge_defaults(self._data, updates)
        self.save()

    @property
    def camera(self) -> Dict[str, Any]:
        return self._data["camera"]

    @property
    def server(self) -> Dict[str, Any]:
        return self._data["server"]

    @property
    def pipeline(self) -> Dict[str, Any]:
        return self._data["pipeline"]

    @property
    def image_controls(self) -> Dict[str, Any]:
        return self._data.setdefault("image_controls", dict(DEFAULT_CONFIG["image_controls"]))

    @property
    def alarm(self) -> Dict[str, Any]:
        return self._data["alarm"]

    @property
    def power(self) -> Dict[str, Any]:
        return self._data["power"]

    @property
    def push(self) -> Dict[str, Any]:
        return self._data.setdefault("push", dict(DEFAULT_CONFIG["push"]))

    @property
    def storage(self) -> Dict[str, Any]:
        return self._data.setdefault("storage", dict(DEFAULT_CONFIG["storage"]))

    @property
    def night_mode(self) -> Dict[str, Any]:
        return self._data.setdefault("night_mode", dict(DEFAULT_CONFIG["night_mode"]))

    @property
    def event_grouping(self) -> Dict[str, Any]:
        return self._data.setdefault("event_grouping", dict(DEFAULT_CONFIG["event_grouping"]))

    @property
    def flashlight(self) -> Dict[str, Any]:
        return self._data.setdefault("flashlight", dict(DEFAULT_CONFIG["flashlight"]))

    @property
    def audio_detection(self) -> Dict[str, Any]:
        return self._data.setdefault("audio_detection", dict(DEFAULT_CONFIG["audio_detection"]))

    @property
    def video_recording(self) -> Dict[str, Any]:
        return self._data.setdefault("video_recording", dict(DEFAULT_CONFIG["video_recording"]))

    @property
    def is_pin_initialized(self) -> bool:
        """Check if a salted PBKDF2 hash is set for the master PIN."""
        server_cfg = self.server
        return bool(server_cfg.get("dashboard_pin_hash") and server_cfg.get("dashboard_pin_salt"))

    @property
    def camera_video_url(self) -> str:
        cam = self.camera
        if cam.get("video_url") and str(cam["video_url"]).strip():
            return str(cam["video_url"]).strip()
        host = cam.get("camera_host") or cam.get("phone_ip", "127.0.0.1")
        port = cam.get("camera_port") or cam.get("phone_port", 8080)
        ep = cam.get("video_endpoint", "/video")
        if not ep.startswith("/"):
            ep = "/" + ep
        return f"http://{host}:{port}{ep}"

    @property
    def camera_snapshot_url(self) -> str:
        cam = self.camera
        if cam.get("snapshot_url") and str(cam["snapshot_url"]).strip():
            return str(cam["snapshot_url"]).strip()
        host = cam.get("camera_host") or cam.get("phone_ip", "127.0.0.1")
        port = cam.get("camera_port") or cam.get("phone_port", 8080)
        ep = cam.get("snapshot_endpoint", "/shot.jpg")
        if not ep.startswith("/"):
            ep = "/" + ep
        return f"http://{host}:{port}{ep}"

    @property
    def camera_audio_url(self) -> str:
        cam = self.camera
        if cam.get("audio_url") and str(cam["audio_url"]).strip():
            return str(cam["audio_url"]).strip()
        host = cam.get("camera_host") or cam.get("phone_ip", "127.0.0.1")
        port = cam.get("camera_port") or cam.get("phone_port", 8080)
        ep = cam.get("audio_endpoint", "/audio.wav")
        if not ep.startswith("/"):
            ep = "/" + ep
        return f"http://{host}:{port}{ep}"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)


# Global singleton instance
app_config = Config.load()
