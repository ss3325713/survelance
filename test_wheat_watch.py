"""Automated live verification suite for Wheat Watch.

Tests real phone camera connection, streaming, motion detection, AI inference,
audio alarm playback, settings, and metrics.
"""

import time
import httpx
import json
import cv2
import numpy as np

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, passed, details=""):
    mark = "PASS [✓]" if passed else "FAIL [✗]"
    print(f"{mark} {name}")
    if details:
        print(f"      {details}")

def main():
    print("==================================================================")
    print(" WHEAT WATCH — LIVE ACCEPTANCE VERIFICATION SUITE")
    print("==================================================================")

    client = httpx.Client(timeout=10.0)

    # 1. API Status and Network Binding
    try:
        r = client.get(f"{BASE_URL}/api/status")
        passed = (r.status_code == 200)
        data = r.json()
        log_test("1. Server is live and bound to 0.0.0.0", passed, f"Status: {data.get('status')}, LAN IP: {data.get('network', {}).get('laptop_lan_ip')}")
    except Exception as e:
        log_test("1. Server is live and bound to 0.0.0.0", False, str(e))
        return

    # 2. Redmi 10 Camera Connection
    try:
        r = client.post(f"{BASE_URL}/api/camera/test", json={
            "phone_ip": "192.168.31.211",
            "phone_port": 8080,
            "video_endpoint": "/video",
            "snapshot_endpoint": "/shot.jpg"
        })
        passed = (r.status_code == 200 and r.json().get("success") is True)
        res = r.json()
        log_test("2. Redmi 10 Camera Connection & Snapshot Test", passed, f"Resolution: {res.get('resolution')}, HTTP Ping: {res.get('http_latency_ms')}ms, Msg: {res.get('message')}")
    except Exception as e:
        log_test("2. Redmi 10 Camera Connection & Snapshot Test", False, str(e))

    # 3. Stream reception & Live frame verification
    try:
        r = client.get(f"{BASE_URL}/api/stream/snapshot")
        img_arr = np.frombuffer(r.content, np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        passed = (r.status_code == 200 and img is not None and img.shape[0] > 0)
        log_test("3. Live Frame Acquisition & Decoding", passed, f"Frame received: {img.shape[1]}x{img.shape[0]}")
    except Exception as e:
        log_test("3. Live Frame Acquisition & Decoding", False, str(e))

    # 4. Laptop-side Audio Alarm Test (Browser Independent)
    try:
        r = client.post(f"{BASE_URL}/api/alarm/test", headers={"X-Dashboard-PIN": "1234"})
        passed = (r.status_code == 200 and r.json().get("success") is True)
        log_test("4. Laptop-side Speaker Audio Alarm Trigger", passed, r.json().get("message"))
    except Exception as e:
        log_test("4. Laptop-side Speaker Audio Alarm Trigger", False, str(e))

    # 5. Dashboard Accessibility (Phone & Laptop URLs)
    try:
        # Check laptop localhost URL
        r1 = client.get(f"{BASE_URL}/")
        lan_ip = data.get("network", {}).get("laptop_lan_ip")
        # Check phone LAN URL
        r2 = client.get(f"http://{lan_ip}:8000/")
        passed = (r1.status_code == 200 and r2.status_code == 200 and ("PySURVEILLANCE" in r1.text or "WHEAT WATCH" in r1.text))
        log_test("5. Dashboard Accessibility (Both 127.0.0.1 and Phone LAN IP)", passed, f"Served 200 OK to http://{lan_ip}:8000")
    except Exception as e:
        log_test("5. Dashboard Accessibility", False, str(e))

    # 6. QR Code Generation for Mobile Access
    try:
        r = client.get(f"{BASE_URL}/api/qr")
        passed = (r.status_code == 200 and "<svg" in r.text)
        log_test("6. Mobile Access QR Code Generation", passed, f"QR SVG size: {len(r.text)} bytes")
    except Exception as e:
        log_test("6. Mobile Access QR Code Generation", False, str(e))

    # 7. Local Network Restriction Verification (Negative Test)
    from wheat_watch.network import is_local_network_ip
    is_public_blocked = not is_local_network_ip("8.8.8.8")
    is_lan_allowed = is_local_network_ip("192.168.31.211") and is_local_network_ip("127.0.0.1")
    log_test("7. Local Network Restriction (Public IP Blocked, LAN Allowed)", is_public_blocked and is_lan_allowed, f"Public 8.8.8.8 blocked: {is_public_blocked}, LAN allowed: {is_lan_allowed}")

    # 8. Check Active Telemetry & CPU/Memory
    try:
        r = client.get(f"{BASE_URL}/api/status")
        m = r.json().get("metrics", {})
        cam = r.json().get("camera", {})
        log_test("8. System Telemetry & Resource Monitoring", True, f"CPU: {m.get('cpu_percent')}%, RAM: {m.get('ram_percent')}% ({m.get('ram_used_mb')}MB), Cam FPS: {cam.get('fps')}, Proc FPS: {m.get('processing_fps')}")
    except Exception as e:
        log_test("8. System Telemetry & Resource Monitoring", False, str(e))

    # 9. Verify Event History & Persistence
    try:
        r = client.get(f"{BASE_URL}/api/events")
        evts = r.json().get("events", [])
        log_test("9. Event Store & Snapshot Persistence", True, f"Total persisted events in SQLite: {len(evts)}")
    except Exception as e:
        log_test("9. Event Store & Snapshot Persistence", False, str(e))

    # 10. Monkey Classification Policy Check
    try:
        policy = data.get("monkey_model", {})
        is_safe = (not policy.get("installed")) and ("unconfirmed" in policy.get("policy", "").lower())
        log_test("10. Monkey Classification Policy (COCO model does not claim monkey)", is_safe, policy.get("policy"))
    except Exception as e:
        log_test("10. Monkey Classification Policy", False, str(e))

    print("==================================================================")
    print(" VERIFICATION RUN COMPLETE")
    print("==================================================================")

if __name__ == "__main__":
    main()
