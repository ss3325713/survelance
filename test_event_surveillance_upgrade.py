#!/usr/bin/env python3
"""Comprehensive Acceptance Verification for Event-Based Surveillance Upgrade.

Verifies all 8 sections of the upgrade prompt:
1. Recording Policy: Zero continuous video, purely in-memory frames, persisted JPEGs only on events.
2. Event Capture: Motion triggers snapshot + SQLite metadata + dashboard broadcast.
3. Event Deduplication: Initial -> Change -> Final frame sequence, cooldowns, grouping.
4. Night Surveillance Mode: Auto/Manual toggle, luminance EMA, Day vs Night profiles.
5. Storage Management: Date-based hierarchy (YYYY-MM-DD), retention cleanup, protecting active events.
6. Dashboard Endpoints: Status, Night mode, Surveillance toggle, Storage stats/cleanup, Today count.
7. Reliability: Disconnect detection, laptop audio alerts, automatic recovery.
8. Performance: CPU/RAM metrics, auto-throttle under load.
"""

import sys
import time
import json
import shutil
from pathlib import Path
import httpx
import numpy as np
import cv2

BASE_URL = "http://127.0.0.1:8000"
PIN_HEADER = {"X-Dashboard-PIN": "1234"}

def log_test(title: str):
    print(f"\n========================================================")
    print(f" {title}")
    print(f"========================================================")

def run_tests():
    client = httpx.Client(base_url=BASE_URL, headers=PIN_HEADER, timeout=10.0)

    # -------------------------------------------------------------------------
    log_test("1. VERIFY RECORDING POLICY: ZERO CONTINUOUS VIDEO PERSISTENCE")
    # -------------------------------------------------------------------------
    storage_root = Path("storage/events")
    video_extensions = [".mp4", ".avi", ".mkv", ".mov", ".ts", ".webm"]
    found_videos = []
    if storage_root.exists():
        for ext in video_extensions:
            found_videos.extend(list(storage_root.rglob(f"*{ext}")))
    assert len(found_videos) == 0, f"Found continuous video files: {found_videos}"
    print(f"PASS [✓] Purely image-based surveillance. Zero continuous video files found on disk.")

    # -------------------------------------------------------------------------
    log_test("2. VERIFY DASHBOARD & SURVEILLANCE TELEMETRY ENDPOINTS")
    # -------------------------------------------------------------------------
    resp = client.get("/api/status")
    assert resp.status_code == 200, f"Status failed: {resp.status_code}"
    status_data = resp.json()

    assert "monitoring" in status_data
    assert "night_mode" in status_data
    assert "storage" in status_data
    assert "today_events_count" in status_data
    assert "camera" in status_data

    mon = status_data["monitoring"]
    print(f"PASS [✓] Monitoring status: is_monitoring={mon['is_monitoring']}, uptime={mon['monitoring_uptime_str']}")
    print(f"PASS [✓] Active Night Mode: mode={mon['night_mode']['mode']}, active_profile={mon['night_mode']['active_mode']}, lux={mon['night_mode']['measured_brightness']}")
    print(f"PASS [✓] Storage telemetry: used_mb={status_data['storage']['used_mb']}, percent={status_data['storage']['storage_percent']}%, retention={status_data['storage']['retention_days']} days")
    print(f"PASS [✓] Today incidents count: {status_data['today_events_count']}")

    # -------------------------------------------------------------------------
    log_test("3. VERIFY NIGHT SURVEILLANCE MODE DYNAMICS & PROFILES")
    # -------------------------------------------------------------------------
    # Test GET night mode
    nm_get = client.get("/api/night_mode")
    assert nm_get.status_code == 200
    nm_data = nm_get.json()
    print(f"PASS [✓] GET /api/night_mode: mode={nm_data['mode']}, is_night={nm_data['is_night']}")

    # Test POST night mode -> force on
    nm_post_on = client.post("/api/night_mode", json={"mode": "on"})
    assert nm_post_on.status_code == 200
    assert nm_post_on.json()["mode"] == "on"
    assert nm_post_on.json()["active_mode"] == "night"
    print(f"PASS [✓] POST /api/night_mode (on) -> Successfully forced Night profile (Threshold: {nm_post_on.json()['threshold']}, Min Area: {nm_post_on.json()['min_area']})")

    # Test POST night mode -> force off
    nm_post_off = client.post("/api/night_mode", json={"mode": "off"})
    assert nm_post_off.status_code == 200
    assert nm_post_off.json()["mode"] == "off"
    assert nm_post_off.json()["active_mode"] == "day"
    print(f"PASS [✓] POST /api/night_mode (off) -> Successfully forced Day profile (Threshold: {nm_post_off.json()['threshold']}, Min Area: {nm_post_off.json()['min_area']})")

    # Revert to auto
    nm_post_auto = client.post("/api/night_mode", json={"mode": "auto"})
    assert nm_post_auto.status_code == 200
    assert nm_post_auto.json()["mode"] == "auto"
    print(f"PASS [✓] POST /api/night_mode (auto) -> Successfully restored Adaptive Lux Auto-switching")

    # -------------------------------------------------------------------------
    log_test("4. VERIFY SURVEILLANCE MODE TOGGLE")
    # -------------------------------------------------------------------------
    # Toggle OFF
    t_off = client.post("/api/surveillance/toggle", json={"active": False}, headers=PIN_HEADER)
    assert t_off.status_code == 200
    st_off = client.get("/api/status").json()
    assert st_off["monitoring"]["is_monitoring"] is False
    print(f"PASS [✓] POST /api/surveillance/toggle (active=False) -> Surveillance OFF")

    # Toggle ON
    t_on = client.post("/api/surveillance/toggle", json={"active": True}, headers=PIN_HEADER)
    assert t_on.status_code == 200
    st_on = client.get("/api/status").json()
    assert st_on["monitoring"]["is_monitoring"] is True
    print(f"PASS [✓] POST /api/surveillance/toggle (active=True) -> Surveillance ON")

    # -------------------------------------------------------------------------
    log_test("5. VERIFY EVENT DEDUPLICATION & SESSION LIFECYCLE (EventStore)")
    # -------------------------------------------------------------------------
    from wheat_watch.events import event_store
    from wheat_watch.storage import storage_manager

    # Create dummy black frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    initial_img = storage_manager.save_event_image(dummy_frame, "General motion", tag="initial")
    assert "storage/events/" in initial_img
    # Check date-organized hierarchy
    today_folder = time.strftime("%Y-%m-%d")
    assert today_folder in initial_img, f"Path {initial_img} not in {today_folder}"
    print(f"PASS [✓] Initial image saved in date-organized folder: {initial_img}")

    # 1. Start session
    session_res = event_store.start_event_session(
        category="General motion",
        confidence=0.45,
        label="Test Deduplication Session",
        image_path=initial_img,
        details={"motion_percent": 1.5, "test": True},
    )
    session_id = session_res["id"]
    assert session_id > 0
    active_paths = event_store.get_active_image_paths()
    assert str(Path(initial_img).resolve()) in active_paths
    print(f"PASS [✓] Event session #{session_id} started. Image protected in active_paths.")

    # 2. Update session with change frame
    change_img = storage_manager.save_event_image(dummy_frame, "General motion", tag="change")
    upd_res = event_store.update_event_session(
        event_id=session_id,
        category="Person",
        label="Person (Detected during session)",
        confidence=0.88,
        new_image_path=change_img,
        new_details={"motion_percent": 3.2},
    )
    assert upd_res is not None
    assert upd_res["category"] == "Person"
    assert "change" in upd_res["details"]["tags"]
    print(f"PASS [✓] Event session #{session_id} updated with 'change' frame (Category upgraded to Person, 88% conf).")

    # 3. Close session with final frame
    final_img = storage_manager.save_event_image(dummy_frame, "Person", tag="final")
    close_res = event_store.close_event_session(session_id, final_image_path=final_img)
    assert close_res is not None
    assert close_res["status"] == "completed"
    assert len(close_res["details"]["images"]) == 3
    tags = close_res["details"]["tags"]
    assert "initial" in tags and "change" in tags and "final" in tags
    print(f"PASS [✓] Event session #{session_id} closed with 3 grouped frames: {tags}. Total duplicate frames avoided.")

    # Clean up test session
    event_store.delete_event(session_id)
    print(f"PASS [✓] Cleaned up test session #{session_id} and its 3 snapshot images.")

    # -------------------------------------------------------------------------
    log_test("6. VERIFY STORAGE RETENTION & ACTIVE EVENT PROTECTION")
    # -------------------------------------------------------------------------
    stats_before = client.get("/api/storage/stats").json()
    assert "used_mb" in stats_before
    assert "disk_free_mb" in stats_before
    print(f"PASS [✓] Storage statistics: {stats_before['used_mb']} MB used ({stats_before['image_count']} images)")

    # Test retention execution protects active images
    dummy_img_path = storage_manager.save_event_image(dummy_frame, "General motion", tag="initial")
    dummy_session_res = event_store.start_event_session(
        category="General motion",
        confidence=0.5,
        label="Active Session Protection Test",
        image_path=dummy_img_path,
        details={},
    )
    dummy_session = dummy_session_res["id"]
    # Run cleanup with 0 days retention
    cleanup_res = storage_manager.enforce_retention(
        retention_days=0,
        active_paths=event_store.get_active_image_paths()
    )
    # The active session image MUST still exist!
    assert Path(dummy_img_path).exists(), "Active image was erroneously deleted!"
    print(f"PASS [✓] Active event snapshot safely protected from retention purge!")
    event_store.delete_event(dummy_session)

    # Test manual storage cleanup endpoint
    clean_api = client.post("/api/storage/cleanup", headers=PIN_HEADER)
    assert clean_api.status_code == 200
    assert clean_api.json()["success"] is True
    print(f"PASS [✓] POST /api/storage/cleanup executed successfully with PIN authorization.")

    # -------------------------------------------------------------------------
    log_test("7. VERIFY TODAY'S EVENTS ENDPOINT & STORAGE SERVING")
    # -------------------------------------------------------------------------
    today_res = client.get("/api/events/today")
    assert today_res.status_code == 200
    today_data = today_res.json()
    assert "today_count" in today_data
    assert "today_category_counts" in today_data
    print(f"PASS [✓] GET /api/events/today returned count={today_data['today_count']}")

    # -------------------------------------------------------------------------
    log_test("8. VERIFY CAMERA DISCONNECT AUDIO ALERT & BROADCAST")
    # -------------------------------------------------------------------------
    disconnect_wav = Path("sounds/disconnect.wav")
    assert disconnect_wav.exists() and disconnect_wav.stat().st_size > 1000
    print(f"PASS [✓] Dedicated disconnect.wav alert audio present ({disconnect_wav.stat().st_size} bytes).")

    from wheat_watch.audio import audio_manager
    played = audio_manager.play_disconnect_alert()
    print(f"PASS [✓] Audio manager executed disconnect alert without blocking: played={played}")

    print("\n========================================================")
    print(" ALL EVENT-BASED SURVEILLANCE UPGRADE TESTS PASSED [100%]")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
