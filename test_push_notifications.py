"""Test Suite for Connected Browser Force Push Notifications."""

import asyncio
import json
import threading
import time
import httpx

BASE_URL = "http://127.0.0.1:8000"


def test_push_endpoints():
    print("[1] Testing Push Status API...")
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        r = client.get("/api/push/status")
        assert r.status_code == 200, f"Push status failed: {r.text}"
        status_data = r.json()
        print(f"    Current Push Status: {status_data}")
        assert "enabled" in status_data
        assert "connected_clients" in status_data

        print("\n[2] Testing Sound File Static Mount...")
        r_sound = client.get("/sounds/person.wav")
        assert r_sound.status_code == 200, "Sound mount failed"
        assert len(r_sound.content) > 1000, "Sound file empty"
        print(f"    Sound file accessible: {len(r_sound.content)} bytes")

        print("\n[3] Testing Push Toggle API...")
        # Toggle OFF
        r_off = client.post("/api/push/toggle", json={"enabled": False})
        assert r_off.status_code == 200
        assert r_off.json()["config"]["enabled"] is False
        print("    Successfully toggled push OFF")

        # Toggle ON
        r_on = client.post("/api/push/toggle", json={"enabled": True})
        assert r_on.status_code == 200
        assert r_on.json()["config"]["enabled"] is True
        print("    Successfully toggled push ON")


def test_sse_stream_and_broadcast():
    print("\n[4] Testing Real-Time SSE Push Stream and Broadcast...")
    events_received = []
    stop_event = threading.Event()

    def listen_sse():
        with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
            with client.stream("GET", "/api/push/stream") as response:
                assert response.status_code == 200
                current_event = None
                for line in response.iter_lines():
                    if stop_event.is_set():
                        break
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        current_event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and current_event:
                        data_str = line.split(":", 1)[1].strip()
                        events_received.append((current_event, json.loads(data_str)))
                        if current_event == "detection":
                            stop_event.set()
                            break

    listener_thread = threading.Thread(target=listen_sse, daemon=True)
    listener_thread.start()

    time.sleep(1.0)  # Allow SSE client to register

    print("    Dispatching test push alert via POST /api/push/test...")
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        r = client.post("/api/push/test")
        assert r.status_code == 200, f"Test push failed: {r.text}"
        print(f"    Server response: {r.json()}")

    listener_thread.join(timeout=5.0)

    print(f"    Received SSE events: {[e[0] for e in events_received]}")
    assert any(e[0] == "handshake" for e in events_received), "Handshake event not received"
    assert any(e[0] == "detection" for e in events_received), "Detection push event not received"

    detection_data = next(e[1] for e in events_received if e[0] == "detection")
    print(f"    Detection Payload: {detection_data['category']} - {detection_data['label']}")
    assert detection_data["category"] == "Person"
    assert detection_data["confidence"] == 0.98

    print("\n[PASS] All Force Push Notifications and Real-Time SSE Tests Succeeded!")


if __name__ == "__main__":
    test_push_endpoints()
    test_sse_stream_and_broadcast()
