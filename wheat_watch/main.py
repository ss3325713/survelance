"""Wheat Watch FastAPI Backend Application.

Binds to 0.0.0.0, enforces local network restrictions, serves the responsive dashboard,
provides live MJPEG preview, event APIs, camera tests, and laptop alarm controls.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import platform
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wheat_watch.audio import audio_manager
from wheat_watch.broadcaster import broadcaster
from wheat_watch.camera import CameraWorker, camera_worker
from wheat_watch.config import app_config
from wheat_watch.detector import detector
from wheat_watch.events import event_store
from wheat_watch.flashlight import flashlight_controller
from wheat_watch.metrics import metrics
from wheat_watch.microphone import microphone_detector
from wheat_watch.motion import motion_detector
from wheat_watch.network import generate_qr_svg, get_lan_ip, is_local_network_ip
from wheat_watch.pipeline import pipeline
from wheat_watch.power import power_manager
from wheat_watch.security import hash_pin, rate_limiter, security_logger, session_manager, verify_pin_hash
from wheat_watch.storage import storage_manager
from wheat_watch.video_recording import video_job_store, video_processor, video_recorder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("wheat_watch.main")

app = FastAPI(
    title="PySURVEILLANCE",
    description="Surveillance and Field Defense System with Phone Camera Integration",
    version="2.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage directories
STATIC_DIR = Path("static")
STORAGE_DIR = Path("storage/events")
SOUNDS_DIR = Path("sounds")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/storage", StaticFiles(directory="storage"), name="storage")
if SOUNDS_DIR.exists():
    app.mount("/sounds", StaticFiles(directory=str(SOUNDS_DIR)), name="sounds")


# Middleware: Enforce Local Network Access Restriction
@app.middleware("http")
async def local_network_security_middleware(request: Request, call_next):
    if app_config.server.get("restrict_local_network", True):
        client_host = request.client.host if request.client else ""
        # Check forwarded headers if behind proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_host = forwarded.split(",")[0].strip()

        if not is_local_network_ip(client_host):
            logger.warning(f"Blocked unauthorized non-LAN connection attempt from {client_host}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Forbidden",
                    "message": "Access is strictly restricted to local network devices. Public access denied.",
                },
            )

    response = await call_next(request)
    return response


# Dependency: Verify PIN or valid session for sensitive actions
def verify_pin_auth(request: Request) -> bool:
    if not app_config.server.get("pin_required", True):
        return True

    client_ip = request.client.host if request.client else ""
    token = (
        request.headers.get("X-Dashboard-Token")
        or request.headers.get("X-Session-Token")
        or request.cookies.get("wheat_watch_session")
    )

    if token:
        session = session_manager.validate_session(token, client_ip)
        if session:
            return True

    # Header-based PIN authentication (legacy/CLI test fallback)
    pin = request.headers.get("X-Dashboard-PIN")
    if pin:
        server_cfg = app_config.server
        stored_hash = server_cfg.get("dashboard_pin_hash")
        stored_salt = server_cfg.get("dashboard_pin_salt")
        if stored_hash and stored_salt:
            if verify_pin_hash(pin, stored_hash, stored_salt):
                return True
        elif pin == server_cfg.get("dashboard_pin"):
            return True

    security_logger.warning(
        f"[SECURITY AUDIT] Unauthorized attempt to access protected endpoint: {request.url.path} from IP {client_ip}"
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="PIN authentication required for this action.",
    )


# --- Request Models ---
class PINVerifyRequest(BaseModel):
    pin: str


class PINSetupRequest(BaseModel):
    pin: str
    confirm_pin: str


class CameraTestRequest(BaseModel):
    phone_ip: Optional[str] = None
    phone_port: Optional[int] = None
    camera_host: Optional[str] = None
    camera_port: Optional[int] = None
    video_endpoint: str = "/video"
    snapshot_endpoint: str = "/shot.jpg"
    video_url: Optional[str] = None


class ImageControlsRequest(BaseModel):
    resolution: Optional[str] = None
    quality: Optional[int] = None
    exposure: Optional[int] = None
    exposure_compensation: Optional[int] = None
    gamma: Optional[float] = None
    brightness: Optional[int] = None
    contrast: Optional[float] = None
    auto_hdr: Optional[bool] = None
    white_balance: Optional[str] = None
    torch: Optional[bool] = None
    night_vision: Optional[bool] = None


class PushToggleRequest(BaseModel):
    enabled: Optional[bool] = None
    browser_audio: Optional[bool] = None
    desktop_notifications: Optional[bool] = None


class NightModeRequest(BaseModel):
    mode: str  # "off", "on", "auto"


class FlashlightModeRequest(BaseModel):
    mode: str  # "auto", "manual", "off"


class SurveillanceToggleRequest(BaseModel):
    active: Optional[bool] = None
    enabled: Optional[bool] = None


class DetectionThresholdsRequest(BaseModel):
    motion_threshold: Optional[int] = None
    min_confidence: Optional[float] = None
    detection_confidence: Optional[float] = None


class ConfigUpdateRequest(BaseModel):
    camera: Optional[Dict[str, Any]] = None
    pipeline: Optional[Dict[str, Any]] = None
    alarm: Optional[Dict[str, Any]] = None
    power: Optional[Dict[str, Any]] = None
    server: Optional[Dict[str, Any]] = None
    push: Optional[Dict[str, Any]] = None
    night_mode: Optional[Dict[str, Any]] = None
    event_grouping: Optional[Dict[str, Any]] = None
    storage: Optional[Dict[str, Any]] = None
    flashlight: Optional[Dict[str, Any]] = None
    audio_detection: Optional[Dict[str, Any]] = None
    video_recording: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class VideoConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    inactivity_timeout_sec: Optional[float] = None
    max_segment_duration_sec: Optional[float] = None
    recording_fps: Optional[float] = None
    max_extracted_frames: Optional[int] = None
    min_sharpness: Optional[float] = None


# --- API Endpoints ---


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serve the responsive dashboard UI."""
    dashboard_file = STATIC_DIR / "index.html"
    if dashboard_file.exists():
        with open(dashboard_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>PySURVEILLANCE loading...</h1>")


@app.get("/sw.js")
async def serve_service_worker():
    """Serve Service Worker at root scope for device notification delivery."""
    sw_file = STATIC_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(
            sw_file,
            media_type="application/javascript",
            headers={
                "Service-Worker-Allowed": "/",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    return Response(content="// sw unavailable", media_type="application/javascript")


@app.get("/manifest.json")
async def serve_manifest():
    """Serve Web App Manifest for mobile PWA install and notification support."""
    manifest_file = STATIC_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(manifest_file, media_type="application/manifest+json")
    return Response(content="{}", media_type="application/json")


@app.get("/api/status")
async def get_system_status():
    """Retrieve full telemetry, camera state, and monitoring health."""
    lan_ip = get_lan_ip()
    port = app_config.server.get("port", 8000)
    phone_url = f"http://{lan_ip}:{port}"
    laptop_url = f"http://127.0.0.1:{port}"

    mon_status = pipeline.get_status()
    return {
        "status": "online",
        "host_system": {
            "hostname": platform.node() or "Linux Host",
            "system": platform.system(),
            "release": platform.release(),
        },
        "monitoring": mon_status,
        "live_detection": mon_status.get("live_detection", {}),
        "video_recording": mon_status.get("video_recording", {}),
        "camera": camera_worker.get_status(),
        "metrics": metrics.get_system_stats(),
        "network": {
            "laptop_lan_ip": lan_ip,
            "port": port,
            "laptop_url": laptop_url,
            "phone_access_url": phone_url,
        },
        "alarm": {
            "sound_enabled": app_config.alarm.get("sound_enabled", True),
            "cooldowns": app_config.alarm.get("cooldowns", {}),
        },
        "night_mode": motion_detector.get_night_status(),
        "flashlight": flashlight_controller.get_status(),
        "microphone": microphone_detector.get_status(),
        "phone_device": camera_worker.get_phone_device_telemetry(),
        "storage": storage_manager.get_storage_stats(),
        "today_events_count": event_store.get_today_count(),
        "monkey_model": detector.get_monkey_status(),
        "summary": event_store.get_summary_stats(),
    }


@app.get("/api/camera/phone_details")
async def get_camera_phone_details():
    """Retrieve detailed hardware diagnostics, battery level, temperature and optics from Redmi 10."""
    return camera_worker.get_phone_device_telemetry(max_cache_age=1.5)


@app.get("/api/qr")
async def get_qr_code():
    """Generate QR code SVG for instant mobile dashboard access."""
    lan_ip = get_lan_ip()
    port = app_config.server.get("port", 8000)
    url = f"http://{lan_ip}:{port}"
    svg = generate_qr_svg(url)
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/auth/status")
async def get_auth_status(request: Request):
    """Check authentication status, PIN initialization status, and active lockout state."""
    client_ip = request.client.host if request.client else ""
    is_locked, remaining_sec = rate_limiter.is_locked_out(client_ip)
    token = (
        request.headers.get("X-Dashboard-Token")
        or request.headers.get("X-Session-Token")
        or request.cookies.get("wheat_watch_session")
    )
    is_authenticated = False
    if token:
        session = session_manager.validate_session(token, client_ip)
        if session:
            is_authenticated = True

    return {
        "pin_required": app_config.server.get("pin_required", True),
        "pin_initialized": app_config.is_pin_initialized,
        "is_authenticated": is_authenticated,
        "is_locked": is_locked,
        "lockout_remaining_seconds": remaining_sec if is_locked else 0,
    }


@app.post("/api/auth/setup")
async def setup_initial_pin(req: PINSetupRequest, request: Request, response: Response):
    """First-run initialization of master PIN. Only permitted if no PIN has been initialized."""
    client_ip = request.client.host if request.client else ""
    if app_config.is_pin_initialized:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Master PIN has already been initialized."},
        )
    if len(req.pin) < 4:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "message": "PIN must be at least 4 characters long."},
        )
    if req.pin != req.confirm_pin:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "message": "PIN and Confirmation PIN do not match."},
        )

    h, s = hash_pin(req.pin)
    app_config.server["dashboard_pin_hash"] = h
    app_config.server["dashboard_pin_salt"] = s
    app_config.server["dashboard_pin"] = "****"
    app_config.save()

    rate_limiter.record_success(client_ip)
    token, csrf_token = session_manager.create_session(client_ip)
    is_https = request.url.scheme == "https"
    response.set_cookie(
        key="wheat_watch_session",
        value=token,
        max_age=86400,
        httponly=True,
        samesite="lax",
        secure=is_https,
    )
    security_logger.info(f"[SECURITY AUDIT] Master PIN successfully initialized from {client_ip}.")
    return {
        "success": True,
        "token": token,
        "session_id": token,
        "csrf_token": csrf_token,
        "message": "Master PIN created successfully. Session established.",
    }


@app.post("/api/auth/verify")
async def verify_pin(req: PINVerifyRequest, request: Request, response: Response):
    """Verify dashboard PIN with rate limiting, brute-force lockout, and salted PBKDF2 hashing."""
    client_ip = request.client.host if request.client else ""

    # Check brute-force lockout
    is_locked, remaining_sec = rate_limiter.is_locked_out(client_ip)
    if is_locked:
        security_logger.warning(
            f"[SECURITY AUDIT] Rejected login attempt from locked-out IP {client_ip} ({remaining_sec}s remaining)."
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "message": f"Too many failed login attempts. Temporarily locked out. Try again in {remaining_sec} seconds.",
            },
        )

    server_cfg = app_config.server
    stored_hash = server_cfg.get("dashboard_pin_hash")
    stored_salt = server_cfg.get("dashboard_pin_salt")

    valid = False
    if stored_hash and stored_salt:
        valid = verify_pin_hash(req.pin, stored_hash, stored_salt)

    if not valid:
        # Backward-compatible migration if an unhashed custom raw PIN was stored previously
        raw_pin = server_cfg.get("dashboard_pin")
        if raw_pin and raw_pin != "****" and req.pin == raw_pin:
            valid = True
            h, s = hash_pin(req.pin)
            server_cfg["dashboard_pin_hash"] = h
            server_cfg["dashboard_pin_salt"] = s
            server_cfg["dashboard_pin"] = "****"
            app_config.save()

    if valid:
        rate_limiter.record_success(client_ip)
        token, csrf_token = session_manager.create_session(client_ip)
        is_https = request.url.scheme == "https"
        response.set_cookie(
            key="wheat_watch_session",
            value=token,
            max_age=86400,
            httponly=True,
            samesite="lax",
            secure=is_https,
        )
        return {
            "success": True,
            "token": token,
            "session_id": token,
            "csrf_token": csrf_token,
            "message": "PIN verified successfully.",
        }

    locked_now, attempts_left = rate_limiter.record_failure(client_ip)
    if locked_now:
        msg = f"Incorrect PIN. Maximum attempts exceeded. Locked out for {attempts_left} seconds."
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"success": False, "message": msg},
        )

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"success": False, "message": f"Incorrect dashboard PIN. {attempts_left} attempts remaining."},
    )


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    """Invalidate session token and clear authentication cookie."""
    token = request.headers.get("X-Dashboard-Token") or request.cookies.get("wheat_watch_session")
    if token:
        session_manager.invalidate_session(token)
    response.delete_cookie(key="wheat_watch_session")
    return {"success": True, "message": "Logged out successfully."}


@app.post("/api/monitoring/start")
async def start_monitoring(auth: bool = Depends(verify_pin_auth)):
    """Start active surveillance monitoring."""
    security_logger.info("[SECURITY AUDIT] Administrative action: START MONITORING requested.")
    res = pipeline.start_monitoring()
    return res


@app.post("/api/monitoring/stop")
async def stop_monitoring(auth: bool = Depends(verify_pin_auth)):
    """Stop active surveillance monitoring."""
    security_logger.info("[SECURITY AUDIT] Administrative action: STOP MONITORING requested.")
    res = pipeline.stop_monitoring()
    return res


@app.post("/api/camera/test")
async def test_camera(req: CameraTestRequest, auth: bool = Depends(verify_pin_auth)):
    """Perform on-demand connection test to camera or stream."""
    target_host = req.camera_host or req.phone_ip or app_config.camera_host
    target_port = req.camera_port or req.phone_port or app_config.camera_port
    result = CameraWorker.test_connection(
        phone_ip=target_host,
        phone_port=target_port,
        video_endpoint=req.video_endpoint,
        snapshot_endpoint=req.snapshot_endpoint,
        video_url=req.video_url,
    )
    return result


@app.post("/api/camera/reconnect")
async def force_camera_reconnect(auth: bool = Depends(verify_pin_auth)):
    """Force camera acquisition worker to cleanly re-establish stream connection."""
    security_logger.info("[SECURITY AUDIT] Camera reconnection requested.")
    camera_worker.request_reconnect()
    return {"success": True, "message": "Camera reconnection requested."}


@app.post("/api/alarm/test")
async def test_laptop_alarm(auth: bool = Depends(verify_pin_auth)):
    """Play test alarm through laptop speakers."""
    played = audio_manager.test_alarm()
    return {
        "success": played,
        "message": "Test alarm triggered on laptop speakers." if played else "Failed to play sound.",
    }


@app.get("/api/camera/controls")
async def get_camera_controls():
    """Retrieve active camera hardware controls and software tone mapping settings."""
    cfg = app_config.image_controls
    return {
        "controls": cfg,
        "active_resolution": f"{camera_worker.resolution[0]}x{camera_worker.resolution[1]}",
        "gamma": camera_worker.gamma,
        "brightness": camera_worker.brightness,
        "contrast": camera_worker.contrast,
        "auto_hdr": camera_worker.auto_hdr,
        "stream_quality": camera_worker.stream_quality,
    }


@app.post("/api/camera/controls")
async def update_camera_controls(req: ImageControlsRequest, auth: bool = Depends(verify_pin_auth)):
    """Safely update camera quality, exposure, resolution, and tone mapping in real-time."""
    updates = req.dict(exclude_unset=True)
    if not updates:
        return {"success": True, "message": "No controls provided."}

    if "exposure" in updates and "exposure_compensation" not in updates:
        updates["exposure_compensation"] = updates["exposure"]

    security_logger.info(f"[SECURITY AUDIT] Camera controls updated: {list(updates.keys())}")
    # Delegate to CameraWorker's safe reconfiguration engine off the main event loop
    res = await asyncio.to_thread(camera_worker.reconfigure_camera, updates)
    return res


@app.post("/api/camera/reset")
async def reset_camera_controls(auth: bool = Depends(verify_pin_auth)):
    """Reset camera quality, exposure, resolution, and tone mapping to balanced defaults safely."""
    security_logger.info("[SECURITY AUDIT] Camera controls reset to defaults.")
    res = await asyncio.to_thread(camera_worker.reset_camera_settings)
    return res


@app.get("/api/stream/live")
async def live_stream(request: Request):
    """Multiplexed MJPEG stream for dashboard browsers with clean RFC 2046 boundary."""
    async def frame_generator():
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                frame = camera_worker.get_latest_frame(processed=True)
                if frame is None:
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cam_state = camera_worker.state
                    if cam_state == CameraWorker.STATE_RECONFIGURING:
                        txt = "PySURVEILLANCE - RECONFIGURING CAMERA..."
                    elif cam_state == CameraWorker.STATE_RECONNECTING:
                        txt = f"PySURVEILLANCE - RECONNECTING (Try #{camera_worker.reconnect_attempts})..."
                    elif cam_state in (CameraWorker.STATE_OFFLINE, CameraWorker.STATE_ERROR):
                        txt = "PySURVEILLANCE - CAMERA OFFLINE"
                    else:
                        txt = "PySURVEILLANCE - CONNECTING TO CAMERA..."
                    cv2.putText(
                        frame,
                        txt,
                        (25, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (200, 200, 200),
                        1,
                        cv2.LINE_AA,
                    )

                ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret:
                    frame_bytes = jpeg.tobytes()
                    # Standard MJPEG boundary without buggy Content-Length header
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + frame_bytes
                        + b"\r\n"
                    )
                await asyncio.sleep(0.05)  # ~20 FPS non-blocking
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0",
            "Pragma": "no-cache",
            "Expires": "-1",
            "Connection": "close",
        },
    )


@app.get("/api/stream/snapshot")
async def get_snapshot():
    """Retrieve current frame as single JPEG."""
    frame = camera_worker.get_latest_frame(processed=True)
    if frame is None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


@app.get("/api/events")
async def get_events(
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Retrieve recorded detection events."""
    events = event_store.list_events(category=category, limit=limit, offset=offset)
    return {"events": events, "count": len(events)}


@app.get("/api/events/today")
async def get_today_events():
    """Retrieve today's event count and breakdown."""
    stats = event_store.get_summary_stats()
    return {
        "today_count": stats.get("today_count", 0),
        "today_category_counts": stats.get("today_category_counts", {}),
        "total_events": stats.get("total_events", 0),
        "latest_event": stats.get("latest_event"),
    }


@app.get("/api/events/{event_id}")
async def get_event_detail(event_id: int):
    """Retrieve detailed event info."""
    event = event_store.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.delete("/api/events/{event_id}")
async def delete_event(event_id: int, auth: bool = Depends(verify_pin_auth)):
    """Delete an event and its snapshot image."""
    success = event_store.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"success": True, "message": f"Event #{event_id} deleted."}


@app.post("/api/events/clear")
async def clear_events(auth: bool = Depends(verify_pin_auth)):
    """Clear all recorded event history and files."""
    deleted_count = event_store.clear_all()
    return {"success": True, "deleted_count": deleted_count}


@app.get("/api/night_mode")
async def get_night_mode_status():
    """Get current Night Surveillance mode, active profile, and measured ambient brightness."""
    return motion_detector.get_night_status()


@app.post("/api/night_mode")
async def set_night_mode_endpoint(req: NightModeRequest, auth: bool = Depends(verify_pin_auth)):
    """Set Night Surveillance mode: 'off', 'on', or 'auto'."""
    security_logger.info(f"[SECURITY AUDIT] Night mode changed to: {req.mode}")
    res = motion_detector.set_night_mode(req.mode)
    broadcaster.broadcast_sync("night_mode", res)
    return res


@app.post("/api/surveillance/toggle")
async def toggle_surveillance_endpoint(req: Optional[SurveillanceToggleRequest] = None, auth: bool = Depends(verify_pin_auth)):
    """Toggle field surveillance monitoring ON or OFF."""
    target_active = None
    if req is not None:
        target_active = req.active if req.active is not None else req.enabled
    if target_active is None:
        target_active = not pipeline.is_monitoring

    if target_active:
        res = pipeline.start_monitoring()
    else:
        res = pipeline.stop_monitoring()
    broadcaster.broadcast_sync("surveillance_mode", {"active": pipeline.is_monitoring})
    return res


@app.get("/api/flashlight/status")
async def get_flashlight_status():
    """Retrieve current flashlight mode, hardware state, and multi-sensor triggers."""
    return flashlight_controller.get_status()


@app.post("/api/flashlight/mode")
async def set_flashlight_mode(req: FlashlightModeRequest, auth: bool = Depends(verify_pin_auth)):
    """Set flashlight mode: 'auto', 'manual', or 'off'."""
    return flashlight_controller.set_mode(req.mode)


@app.get("/api/microphone/status")
async def get_microphone_status():
    """Retrieve real-time microphone availability, current RMS level, and noise floor."""
    return microphone_detector.get_status()


@app.post("/api/microphone/test")
async def test_microphone_activity(duration: float = 2.0, rms: float = 4500.0, auth: bool = Depends(verify_pin_auth)):
    """Simulate audio activity for deterministic verification testing."""
    microphone_detector.trigger_test_activity(duration_sec=duration, rms=rms)
    return {
        "success": True,
        "message": f"Triggered test audio activity for {duration}s.",
        "status": microphone_detector.get_status(),
    }


@app.get("/api/storage/stats")
async def get_storage_statistics():
    """Get disk usage, retention settings, and event image statistics."""
    return storage_manager.get_storage_stats()


@app.post("/api/storage/cleanup")
async def trigger_storage_cleanup_endpoint(auth: bool = Depends(verify_pin_auth)):
    """Manually trigger retention cleanup of expired event images and database records."""
    security_logger.info("[SECURITY AUDIT] Storage retention cleanup manually triggered.")
    active_paths = event_store.get_active_image_paths()
    res = storage_manager.enforce_retention(active_paths=active_paths)
    return {"success": True, "cleanup": res, "stats": storage_manager.get_storage_stats()}


@app.post("/api/storage/backup")
async def trigger_database_backup(auth: bool = Depends(verify_pin_auth)):
    """Create a point-in-time hot backup of the SQLite database."""
    security_logger.info("[SECURITY AUDIT] Point-in-time database backup triggered.")
    backup_path = event_store.create_backup()
    return {"success": True, "backup_path": backup_path, "message": "Database backup created successfully."}


@app.get("/api/database/health")
async def get_database_health():
    """Verify SQLite database integrity, file size, and row count."""
    return event_store.check_integrity()


@app.get("/api/storage/{filename:path}")
async def get_stored_image(filename: str):
    """Serve recorded event image supporting both date subdirectories and legacy flat files."""
    events_root = STORAGE_DIR.resolve()
    
    clean_name = filename.lstrip("/")
    if clean_name.startswith("storage/"):
        clean_name = clean_name[len("storage/"):]
    if clean_name.startswith("events/"):
        clean_name = clean_name[len("events/"):]
    
    # 1. Cleaned path check
    target_path = (STORAGE_DIR / clean_name).resolve()
    
    # 2. Raw path check
    if not target_path.exists() or not target_path.is_file():
        target_path = (STORAGE_DIR / filename).resolve()
    
    # 3. Basename search fallback
    if not target_path.exists() or not target_path.is_file():
        base = Path(filename).name
        matched = list(STORAGE_DIR.rglob(base))
        if matched and matched[0].is_file():
            target_path = matched[0].resolve()

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")

    # Security: Ensure path is within STORAGE_DIR
    try:
        target_path.relative_to(events_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    with open(target_path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/jpeg")


@app.get("/api/config")
async def get_config():
    """Retrieve current system configuration (sanitizing PIN and secret hashes)."""
    data = app_config.to_dict()
    # Mask PIN and purge cryptographic secrets from response
    server_cfg = data.get("server", {})
    server_cfg["dashboard_pin"] = "****"
    server_cfg.pop("dashboard_pin_hash", None)
    server_cfg.pop("dashboard_pin_salt", None)
    server_cfg.pop("session_secret", None)
    return data


@app.post("/api/config")
async def update_config(updates: ConfigUpdateRequest, auth: bool = Depends(verify_pin_auth)):
    """Update settings (supports both nested config dicts and flat form fields)."""
    raw_dict = updates.dict(exclude_unset=True)
    upd_dict = {}

    # 1. Process structured sections
    if updates.camera:
        upd_dict["camera"] = updates.camera
        camera_worker.request_reconnect()
    if updates.pipeline:
        upd_dict["pipeline"] = updates.pipeline
    if updates.alarm:
        upd_dict["alarm"] = updates.alarm
    if updates.power:
        upd_dict["power"] = updates.power
    if updates.push:
        upd_dict["push"] = updates.push
    if updates.night_mode:
        upd_dict["night_mode"] = updates.night_mode
        if "mode" in updates.night_mode:
            motion_detector.set_night_mode(updates.night_mode["mode"])
    if updates.event_grouping:
        upd_dict["event_grouping"] = updates.event_grouping
    if updates.storage:
        upd_dict["storage"] = updates.storage
    if updates.flashlight:
        upd_dict["flashlight"] = updates.flashlight
        if "mode" in updates.flashlight:
            flashlight_controller.set_mode(updates.flashlight["mode"])
    if updates.audio_detection:
        upd_dict["audio_detection"] = updates.audio_detection
    if updates.server:
        server_upd = dict(updates.server)
        if server_upd.get("dashboard_pin") == "****":
            server_upd.pop("dashboard_pin")
        upd_dict["server"] = server_upd

    # 2. Process flat form field compatibility
    cam_flat = {}
    for k in ("phone_ip", "phone_port", "video_endpoint", "snapshot_endpoint", "audio_endpoint"):
        if k in raw_dict:
            cam_flat[k] = raw_dict[k]
    if cam_flat:
        upd_dict.setdefault("camera", {}).update(cam_flat)
        camera_worker.request_reconnect()

    pipe_flat = {}
    for k in ("motion_fps", "ai_fps", "motion_threshold", "min_confidence", "detection_confidence", "auto_throttle"):
        if k in raw_dict:
            pipe_flat[k] = raw_dict[k]
    if "motion_threshold" in pipe_flat:
        motion_detector.set_threshold(int(pipe_flat["motion_threshold"]))
    if "min_confidence" in pipe_flat:
        conf_val = float(pipe_flat["min_confidence"])
        pipe_flat["detection_confidence"] = conf_val
        pipe_flat["min_confidence"] = conf_val
    elif "detection_confidence" in pipe_flat:
        conf_val = float(pipe_flat["detection_confidence"])
        pipe_flat["min_confidence"] = conf_val
        pipe_flat["detection_confidence"] = conf_val
    if pipe_flat:
        upd_dict.setdefault("pipeline", {}).update(pipe_flat)

    alarm_flat = {}
    if "sound_alarm_enabled" in raw_dict:
        alarm_flat["sound_enabled"] = bool(raw_dict["sound_alarm_enabled"])
    elif "sound_enabled" in raw_dict:
        alarm_flat["sound_enabled"] = bool(raw_dict["sound_enabled"])
    cd_flat = {}
    for k, target in (("cooldown_person", "person"), ("cooldown_animal", "animal"), ("cooldown_motion", "motion")):
        if k in raw_dict:
            cd_flat[target] = int(raw_dict[k])
    if cd_flat:
        alarm_flat["cooldowns"] = cd_flat
    if alarm_flat:
        upd_dict.setdefault("alarm", {}).update(alarm_flat)

    if "dashboard_pin" in raw_dict and raw_dict["dashboard_pin"] and raw_dict["dashboard_pin"] != "****":
        from wheat_watch.security import hash_pin
        h, s = hash_pin(str(raw_dict["dashboard_pin"]))
        upd_dict.setdefault("server", {})["dashboard_pin_hash"] = h
        upd_dict.setdefault("server", {})["dashboard_pin_salt"] = s
        upd_dict.setdefault("server", {})["dashboard_pin"] = "****"

    app_config.update(upd_dict)
    if "push" in upd_dict:
        await broadcaster.broadcast("push_config", app_config.push)
    return {"success": True, "message": "Settings updated and persisted successfully."}


@app.get("/api/detection/thresholds")
async def get_detection_thresholds():
    """Get live motion sensitivity threshold and AI inference confidence cutoff."""
    conf = float(
        app_config.pipeline.get("detection_confidence")
        or app_config.pipeline.get("min_confidence")
        or 0.45
    )
    thresh = int(motion_detector.threshold)
    return {
        "success": True,
        "motion_threshold": thresh,
        "detection_confidence": conf,
        "min_confidence": conf,
        "active_profile": motion_detector.active_mode,
        "min_area": motion_detector.min_area,
    }


@app.post("/api/detection/thresholds")
async def set_detection_thresholds(
    req: DetectionThresholdsRequest,
    auth: bool = Depends(verify_pin_auth),
):
    """Dynamically set motion VarThreshold and YOLO confidence cutoff with zero downtime."""
    resp = {}
    if req.motion_threshold is not None:
        thresh = motion_detector.set_threshold(req.motion_threshold)
        resp["motion_threshold"] = thresh

    conf = req.detection_confidence if req.detection_confidence is not None else req.min_confidence
    if conf is not None:
        conf_val = round(float(conf), 2)
        app_config.update({
            "pipeline": {
                "detection_confidence": conf_val,
                "min_confidence": conf_val,
            }
        })
        resp["detection_confidence"] = conf_val
        resp["min_confidence"] = conf_val

    # Broadcast updated thresholds to all connected clients over SSE
    await broadcaster.broadcast("thresholds_updated", {
        "motion_threshold": motion_detector.threshold,
        "detection_confidence": app_config.pipeline.get("detection_confidence", 0.45),
    })

    return {
        "success": True,
        "message": "Detection thresholds updated successfully in real time.",
        **resp,
    }


# --- Video Recording & Background Queue Endpoints ---


@app.get("/api/video/status")
async def get_video_status():
    """Real-time motion recording status, segment duration, inactivity timer, and background queue stats."""
    return video_recorder.get_status()


@app.get("/api/video/jobs")
async def list_video_jobs(event_id: Optional[int] = None, limit: int = 50):
    """Retrieve video processing jobs with optional filter by event ID."""
    jobs = video_job_store.list_jobs(event_id=event_id, limit=limit)
    stats = video_job_store.get_queue_stats()
    return {
        "success": True,
        "jobs": jobs,
        "stats": stats,
    }


@app.get("/api/video/jobs/{job_id}")
async def get_video_job(job_id: int):
    """Retrieve details and extracted images for a single video job."""
    job = video_job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Video job #{job_id} not found.")
    return {"success": True, "job": job}


@app.post("/api/video/jobs/{job_id}/retry")
async def retry_video_job(job_id: int, auth: bool = Depends(verify_pin_auth)):
    """Retry a failed video processing job if source video is still on disk."""
    success = video_job_store.retry_job(job_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry job #{job_id}. Source video file may be missing or unrecoverable.",
        )
    return {"success": True, "message": f"Video job #{job_id} re-queued for background processing."}


@app.get("/api/video/config")
async def get_video_config():
    """Retrieve video recording and background processing configuration."""
    return {"success": True, "config": app_config.video_recording}


@app.post("/api/video/config")
async def update_video_config(req: VideoConfigUpdateRequest, auth: bool = Depends(verify_pin_auth)):
    """Update video recording timeouts, FPS, and frame extraction parameters."""
    cur = dict(app_config.video_recording)
    if req.enabled is not None:
        cur["enabled"] = req.enabled
    if req.inactivity_timeout_sec is not None:
        cur["inactivity_timeout_sec"] = float(req.inactivity_timeout_sec)
    if req.max_segment_duration_sec is not None:
        cur["max_segment_duration_sec"] = float(req.max_segment_duration_sec)
    if req.recording_fps is not None:
        cur["recording_fps"] = float(req.recording_fps)
    if req.max_extracted_frames is not None:
        cur["max_extracted_frames"] = int(req.max_extracted_frames)
    if req.min_sharpness is not None:
        cur["min_sharpness"] = float(req.min_sharpness)

    app_config.update({"video_recording": cur})
    await broadcaster.broadcast("video_config_updated", cur)
    return {
        "success": True,
        "message": "Video recording configuration updated.",
        "config": cur,
    }


# --- Server-Sent Events (SSE) & Push Notification Endpoints ---


@app.get("/api/push/stream")
async def stream_push_messages(request: Request):
    """Server-Sent Events (SSE) push stream for connected browsers."""
    return StreamingResponse(
        broadcaster.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/push/status")
async def get_push_status():
    """Retrieve push notification configuration and active listener count."""
    return {
        "enabled": app_config.push.get("enabled", True),
        "browser_audio": app_config.push.get("browser_audio", True),
        "desktop_notifications": app_config.push.get("desktop_notifications", True),
        "connected_clients": broadcaster.client_count,
    }


@app.post("/api/push/toggle")
async def toggle_push_status(req: PushToggleRequest, auth: bool = Depends(verify_pin_auth)):
    """Toggle force push messages on/off or update push preferences."""
    security_logger.info("[SECURITY AUDIT] Push preferences updated.")
    push_cfg = dict(app_config.push)
    if req.enabled is not None:
        push_cfg["enabled"] = req.enabled
    if req.browser_audio is not None:
        push_cfg["browser_audio"] = req.browser_audio
    if req.desktop_notifications is not None:
        push_cfg["desktop_notifications"] = req.desktop_notifications

    app_config.update({"push": push_cfg})

    # Broadcast updated configuration to all connected browser tabs immediately
    await broadcaster.broadcast("push_config", {
        "enabled": push_cfg.get("enabled", True),
        "browser_audio": push_cfg.get("browser_audio", True),
        "desktop_notifications": push_cfg.get("desktop_notifications", True),
    })

    return {
        "success": True,
        "message": f"Push notifications {'ENABLED' if push_cfg.get('enabled') else 'DISABLED'}.",
        "config": push_cfg,
    }


@app.post("/api/push/test")
async def send_test_push(auth: bool = Depends(verify_pin_auth)):
    """Send an immediate test push notification to all connected browsers."""
    now_iso = datetime.now().astimezone().isoformat()
    recent_events = event_store.list_events(limit=1)
    img_path = recent_events[0]["image_path"] if recent_events else "storage/events/test.jpg"

    test_payload = {
        "id": 999999,
        "category": "Person",
        "confidence": 0.98,
        "label": "Test Push: Person Detected near Wheat Perimeter",
        "image_path": img_path,
        "timestamp": now_iso,
        "details": {"test": True, "source": "Manual Test Push"},
    }
    await broadcaster.broadcast("detection", test_payload)
    return {"success": True, "message": "Test push message dispatched to all connected browsers."}


@app.on_event("startup")
async def on_startup():
    logger.info("PySURVEILLANCE application starting...")
    broadcaster.set_loop(asyncio.get_running_loop())
    # Start microphone background analyzer
    microphone_detector.start()
    # Auto-start monitoring on startup
    pipeline.start_monitoring()


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("PySURVEILLANCE application shutting down gracefully...")
    video_recorder.close_recording("shutdown")
    pipeline.stop_monitoring()
    microphone_detector.stop()
    video_processor.stop()
