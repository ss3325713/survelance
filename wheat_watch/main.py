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
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
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
from wheat_watch.storage import storage_manager

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
if SOUNDS_DIR.exists():
    app.mount("/sounds", StaticFiles(directory=str(SOUNDS_DIR)), name="sounds")

# In-memory active tokens
ACTIVE_PIN_SESSIONS = set()


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


# Dependency: Verify PIN for sensitive actions
def verify_pin_auth(request: Request) -> bool:
    if not app_config.server.get("pin_required", True):
        return True

    pin = request.headers.get("X-Dashboard-PIN")
    token = request.headers.get("X-Dashboard-Token")

    configured_pin = app_config.server.get("dashboard_pin", "1234")
    if pin and pin == configured_pin:
        return True

    if token and token in ACTIVE_PIN_SESSIONS:
        return True

    # Also check cookie
    cookie_token = request.cookies.get("wheat_watch_session")
    if cookie_token and cookie_token in ACTIVE_PIN_SESSIONS:
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="PIN authentication required for this action.",
    )


# --- Request Models ---
class PINVerifyRequest(BaseModel):
    pin: str


class CameraTestRequest(BaseModel):
    phone_ip: str
    phone_port: int
    video_endpoint: str = "/video"
    snapshot_endpoint: str = "/shot.jpg"


class ImageControlsRequest(BaseModel):
    resolution: Optional[str] = None
    quality: Optional[int] = None
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


# --- API Endpoints ---


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serve the responsive dashboard UI."""
    dashboard_file = STATIC_DIR / "index.html"
    if dashboard_file.exists():
        with open(dashboard_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>PySURVEILLANCE loading...</h1>")


@app.get("/api/status")
async def get_system_status():
    """Retrieve full telemetry, camera state, and monitoring health."""
    lan_ip = get_lan_ip()
    port = app_config.server.get("port", 8000)
    phone_url = f"http://{lan_ip}:{port}"
    laptop_url = f"http://127.0.0.1:{port}"

    return {
        "status": "online",
        "monitoring": pipeline.get_status(),
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
        "storage": storage_manager.get_storage_stats(),
        "today_events_count": event_store.get_today_count(),
        "monkey_model": detector.get_monkey_status(),
        "summary": event_store.get_summary_stats(),
    }


@app.get("/api/qr")
async def get_qr_code():
    """Generate QR code SVG for instant mobile dashboard access."""
    lan_ip = get_lan_ip()
    port = app_config.server.get("port", 8000)
    url = f"http://{lan_ip}:{port}"
    svg = generate_qr_svg(url)
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/api/auth/verify")
async def verify_pin(req: PINVerifyRequest, response: Response):
    """Verify dashboard PIN and issue a session token."""
    configured_pin = app_config.server.get("dashboard_pin", "1234")
    if req.pin == configured_pin:
        token = secrets.token_hex(24)
        ACTIVE_PIN_SESSIONS.add(token)
        response.set_cookie(
            key="wheat_watch_session",
            value=token,
            max_age=86400,
            httponly=True,
            samesite="lax",
        )
        return {"success": True, "token": token, "message": "PIN verified successfully."}
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"success": False, "message": "Incorrect dashboard PIN."},
    )


@app.post("/api/monitoring/start")
async def start_monitoring(auth: bool = Depends(verify_pin_auth)):
    """Start active surveillance monitoring."""
    res = pipeline.start_monitoring()
    return res


@app.post("/api/monitoring/stop")
async def stop_monitoring(auth: bool = Depends(verify_pin_auth)):
    """Stop active surveillance monitoring."""
    res = pipeline.stop_monitoring()
    return res


@app.post("/api/camera/test")
async def test_camera(req: CameraTestRequest):
    """Perform on-demand connection test to phone camera."""
    result = CameraWorker.test_connection(
        phone_ip=req.phone_ip,
        phone_port=req.phone_port,
        video_endpoint=req.video_endpoint,
        snapshot_endpoint=req.snapshot_endpoint,
    )
    return result


@app.post("/api/camera/reconnect")
async def force_camera_reconnect():
    """Force camera acquisition worker to cleanly re-establish stream connection."""
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
async def update_camera_controls(req: ImageControlsRequest):
    """Safely update camera quality, exposure, resolution, and tone mapping in real-time."""
    updates = req.dict(exclude_unset=True)
    if not updates:
        return {"success": True, "message": "No controls provided."}

    # Delegate to CameraWorker's safe reconfiguration engine off the main event loop
    res = await asyncio.to_thread(camera_worker.reconfigure_camera, updates)
    return res


@app.post("/api/camera/reset")
async def reset_camera_controls():
    """Reset camera quality, exposure, resolution, and tone mapping to balanced defaults safely."""
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
async def set_night_mode_endpoint(req: NightModeRequest):
    """Set Night Surveillance mode: 'off', 'on', or 'auto'."""
    res = motion_detector.set_night_mode(req.mode)
    broadcaster.broadcast_sync("night_mode", res)
    return res


@app.post("/api/surveillance/toggle")
async def toggle_surveillance_endpoint(req: Optional[SurveillanceToggleRequest] = None, auth: bool = Depends(verify_pin_auth)):
    """Toggle field surveillance monitoring ON or OFF."""
    target_active = not pipeline.is_monitoring if (req is None or req.active is None) else req.active
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
    active_paths = event_store.get_active_image_paths()
    res = storage_manager.enforce_retention(active_paths=active_paths)
    return {"success": True, "cleanup": res, "stats": storage_manager.get_storage_stats()}


@app.get("/api/storage/{filename:path}")
async def get_stored_image(filename: str):
    """Serve recorded event image supporting both date subdirectories and legacy flat files."""
    events_root = STORAGE_DIR.resolve()
    
    # 1. Direct path check
    target_path = (STORAGE_DIR / filename).resolve()
    
    # 2. If not found, check if filename is a basename in subdirectories
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
    """Retrieve current system configuration (sanitizing PIN)."""
    data = app_config.to_dict()
    # Mask PIN for security
    data["server"]["dashboard_pin"] = "****"
    return data


@app.post("/api/config")
async def update_config(updates: ConfigUpdateRequest, auth: bool = Depends(verify_pin_auth)):
    """Update settings."""
    upd_dict = {}
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
        # Only update PIN if provided and non-empty
        server_upd = dict(updates.server)
        if server_upd.get("dashboard_pin") == "****":
            server_upd.pop("dashboard_pin")
        upd_dict["server"] = server_upd

    app_config.update(upd_dict)
    if updates.push:
        await broadcaster.broadcast("push_config", app_config.push)
    return {"success": True, "message": "Settings updated successfully."}


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
async def toggle_push_status(req: PushToggleRequest):
    """Toggle force push messages on/off or update push preferences."""
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
async def send_test_push():
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
    pipeline.stop_monitoring()
    microphone_detector.stop()
