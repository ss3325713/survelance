"""Test camera disconnection and reconnection."""

import time
import httpx

BASE_URL = "http://127.0.0.1:8000"

def main():
    print("=== Testing Camera Disconnection & Reconnection Cycle ===")
    client = httpx.Client(timeout=10.0)

    # 1. Verify initially connected
    r = client.get(f"{BASE_URL}/api/status")
    initial_cam = r.json().get("camera", {})
    print(f"[1] Initial State: {initial_cam.get('state')} (reconnect_attempts={initial_cam.get('reconnect_attempts')})")

    try:
        # 2. Simulate disconnection by pointing to non-existent IP
        print("[2] Triggering disconnection: setting phone_ip to 192.168.31.250...")
        r = client.post(
            f"{BASE_URL}/api/config",
            json={"camera": {"phone_ip": "192.168.31.250"}},
            headers={"X-Dashboard-PIN": "1234"}
        )
        assert r.status_code == 200, f"Config update failed: {r.text}"

        # Wait for disconnection detection
        print("    Waiting 6 seconds for disconnect detection and retry loop...")
        time.sleep(6)

        r = client.get(f"{BASE_URL}/api/status")
        dc_cam = r.json().get("camera", {})
        print(f"[3] Disconnected State: {dc_cam.get('state')} (reconnect_attempts={dc_cam.get('reconnect_attempts')})")
        assert dc_cam.get("state") in ["RECONNECTING", "ERROR", "CONNECTING", "OFFLINE"], f"Expected reconnecting/offline, got {dc_cam.get('state')}"

    finally:
        # 3. Restore valid IP
        print("[4] Restoring valid Redmi 10 IP: 192.168.31.211...")
        r = client.post(
            f"{BASE_URL}/api/config",
            json={"camera": {"phone_ip": "192.168.31.211"}},
            headers={"X-Dashboard-PIN": "1234"}
        )
        assert r.status_code == 200

    # Wait for reconnection
    print("    Waiting for reconnection...")
    reconnected = False
    for i in range(12):
        time.sleep(2)
        r = client.get(f"{BASE_URL}/api/status")
        cam = r.json().get("camera", {})
        print(f"    Check #{i+1}: state={cam.get('state')}, fps={cam.get('fps')}")
        if cam.get("state") in ("ONLINE", "CONNECTED") and cam.get("fps", 0) > 0:
            reconnected = True
            break

    print(f"[5] Reconnection Result: {'SUCCESS [✓]' if reconnected else 'FAILED [✗]'}")
    assert reconnected, "Camera failed to reconnect!"

if __name__ == "__main__":
    main()
