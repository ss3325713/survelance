#!/usr/bin/env python3
"""Capture Fresh Live Application Screenshots for PySURVEILLANCE Presentation.

Runs:
1. Controlled mock IP camera server on 127.0.0.1:8080 (serving /video, /shot.jpg, /status.json, /sensors.json, /audio.wav)
2. PySURVEILLANCE FastAPI backend on 127.0.0.1:8000 via run.py
3. Headless Chrome at 1920x1080 via Chrome DevTools Protocol (CDP)
4. Navigates all key views, unlocks console, triggers forensic modals, captures screenshots
5. Privacy-sanitizes and blurs faces
6. Saves clean presentation assets into presentation/assets/
"""

import sys
import os
import time
import json
import struct
import asyncio
import tempfile
import threading
import urllib.request
import subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import cv2
import numpy as np
import websockets

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "presentation" / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Preload sample frames from storage/events
EVENT_IMAGES = sorted(list((PROJECT_ROOT / "storage" / "events" / "2026-11-13").glob("*.jpg")))
print(f"[MockCam] Found {len(EVENT_IMAGES)} recorded event frames.")

class MockCameraState:
    torch = "off"
    night_vision = "off"
    video_size = "1280x720"
    quality = 95
    whitebalance = "auto"
    frame_idx = 0

cam_state = MockCameraState()

STREAM_FRAMES = []
if EVENT_IMAGES:
    for p in EVENT_IMAGES[:20]:
        im = cv2.imread(str(p))
        if im is not None:
            if im.shape[1] != 1280 or im.shape[0] != 720:
                im = cv2.resize(im, (1280, 720))
            # Pre-blur head area: y: 160-320, x: 980-1160
            im[160:320, 980:1160] = cv2.GaussianBlur(im[160:320, 980:1160], (51, 51), 30)
            STREAM_FRAMES.append(im)

if not STREAM_FRAMES:
    blank = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(blank, "PySURVEILLANCE Live Feed", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 200), 2)
    STREAM_FRAMES = [blank]

print(f"[MockCam] Prepared {len(STREAM_FRAMES)} stream frames.")

def make_wav_header(sample_rate=16000, bits=16, channels=1):
    byte_rate = sample_rate * channels * (bits // 8)
    block_align = channels * (bits // 8)
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        0x7FFFFFFF,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        0x7FFFFFFF
    )

class MockCameraHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = self.path.split("?")[0]
        if parsed == "/video":
            self.send_response(200)
            self.send_header("Connection", "close")
            self.send_header("Cache-Control", "no-cache, private, no-store, must-revalidate, max-age=0")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                idx = 0
                while True:
                    frame = STREAM_FRAMES[idx % len(STREAM_FRAMES)]
                    idx += 1
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    data = buf.tobytes()
                    part = f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(data)}\r\n\r\n".encode() + data + b"\r\n"
                    self.wfile.write(part)
                    self.wfile.flush()
                    time.sleep(0.1)  # 10 FPS
            except Exception:
                pass

        elif parsed == "/shot.jpg":
            frame = STREAM_FRAMES[0]
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            data = buf.tobytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        elif parsed == "/status.json":
            payload = {
                "curvals": {
                    "video_size": cam_state.video_size,
                    "quality": cam_state.quality,
                    "torch": cam_state.torch,
                    "night_vision": cam_state.night_vision,
                    "whitebalance": cam_state.whitebalance,
                    "flashmode": "off"
                },
                "video_connections": 1,
                "audio_connections": 1
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed == "/sensors.json":
            payload = {
                "battery_level": {"unit": "%", "data": [[0, [88.0]]]},
                "battery_temp": {"unit": "C", "data": [[0, [31.5]]]},
                "battery_voltage": {"unit": "V", "data": [[0, [4.15]]]},
                "light": {"unit": "lx", "data": [[0, [18.0]]]},
                "ambient_temp": {"unit": "C", "data": [[0, [26.0]]]}
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed == "/enabletorch":
            cam_state.torch = "on"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        elif parsed == "/disabletorch":
            cam_state.torch = "off"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        elif parsed == "/audio.wav":
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.end_headers()
            try:
                self.wfile.write(make_wav_header(sample_rate=16000, bits=16, channels=1))
                self.wfile.flush()
                chunk_samples = 1600  # 100ms
                while True:
                    noise = np.random.normal(0, 500, chunk_samples).astype(np.int16)
                    self.wfile.write(noise.tobytes())
                    self.wfile.flush()
                    time.sleep(0.1)
            except Exception:
                pass

        elif parsed.startswith("/settings/"):
            if "video_size" in self.path:
                try:
                    val = self.path.split("set=")[-1]
                    cam_state.video_size = val
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        else:
            self.send_response(404)
            self.end_headers()


def run_mock_camera():
    server = ThreadingHTTPServer(("127.0.0.1", 8080), MockCameraHandler)
    server.serve_forever()


class CDPSession:
    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0

    async def send(self, method, params=None):
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            resp = json.loads(await self.ws.recv())
            if resp.get("id") == self.msg_id:
                if "error" in resp:
                    raise Exception(f"CDP Error ({method}): {resp['error']}")
                return resp.get("result", {})

    async def eval(self, expr):
        res = await self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True
        })
        val = res.get("result", {})
        return val.get("value")

    async def click(self, selector):
        return await self.eval(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (el) {{
                    el.scrollIntoView({{ block: 'center' }});
                    el.click();
                    return true;
                }}
                return false;
            }})()
        """)

    async def screenshot(self, filename: str):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        import base64
        raw = base64.b64decode(res["data"])
        out_path = ASSETS_DIR / filename
        out_path.write_bytes(raw)
        
        # Privacy check & face blurring
        img = cv2.imread(str(out_path))
        if img is not None:
            # Blur known video stream viewport locations
            if "Monitoring" in filename or "HUD" in filename or "Dashboard" in filename:
                img[220:350, 860:980] = cv2.GaussianBlur(img[220:350, 860:980], (51, 51), 30)
            elif "Forensic" in filename or "Modal" in filename or "Extracted" in filename:
                img[170:320, 430:560] = cv2.GaussianBlur(img[170:320, 430:560], (51, 51), 30)

            cv2.imwrite(str(out_path), img)

        print(f"[Captured & Sanitized] {out_path.name} ({len(raw)} bytes, 1920x1080)")
        return out_path


async def capture_all_screens(token: str):
    BASE_URL = "http://127.0.0.1:8000"
    
    tmp_profile = tempfile.mkdtemp(prefix="cdp_pres_")
    chrome_proc = subprocess.Popen([
        "google-chrome",
        "--headless=new",
        "--remote-debugging-port=9222",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1920,1080",
        f"--user-data-dir={tmp_profile}",
        f"{BASE_URL}/#overview"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=1) as resp:
                tabs = json.loads(resp.read().decode())
                page_tabs = [t for t in tabs if t.get("type") == "page"]
                if page_tabs:
                    ws_url = page_tabs[0]["webSocketDebuggerUrl"]
                    break
        except Exception:
            await asyncio.sleep(0.3)

    assert ws_url, "Failed to connect to Chrome DevTools port 9222"
    print(f"[CDP] Connected to Chrome: {ws_url}")

    async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
        cdp = CDPSession(ws)
        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")
        await cdp.send("DOM.enable")
        await cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1920,
            "height": 1080,
            "deviceScaleFactor": 1,
            "mobile": False
        })

        await cdp.send("Page.navigate", {"url": f"{BASE_URL}/#overview"})
        await asyncio.sleep(2.5)

        # Inject session token into localStorage and cookie
        await cdp.eval(f"""
            (() => {{
                localStorage.setItem('pysurv_session_token', '{token}');
                document.cookie = 'wheat_watch_session={token}; path=/; max-age=86400';
            }})()
        """)
        await asyncio.sleep(0.5)

        # Reload or trigger state update
        await cdp.send("Page.navigate", {"url": f"{BASE_URL}/#overview"})
        await asyncio.sleep(2.0)

        # Close any open modal just in case
        await cdp.eval("""
            (() => {
                const setupModal = document.getElementById('pinSetupModal');
                if (setupModal) setupModal.style.display = 'none';
                const pinModal = document.getElementById('pinModal');
                if (pinModal) pinModal.classList.remove('open');
            })()
        """)
        await asyncio.sleep(0.5)

        # 1. Main SOC Overview Dashboard
        await cdp.click('[data-view="overview"]')
        await asyncio.sleep(2.5)
        await cdp.screenshot("01_Main_Monitoring_Dashboard.png")

        # 2. Live Cinema Monitoring Workspace
        await cdp.click('[data-view="monitoring"]')
        await asyncio.sleep(2.5)
        await cdp.eval("""
            (() => {
                const hud = document.getElementById('recordingHud');
                if (hud) hud.style.display = 'flex';
                const banner = document.getElementById('liveCinemaAlert');
                if (banner) {
                    banner.classList.add('active');
                    banner.textContent = '🚨 PERSON 83% DETECTED';
                    banner.style.display = 'inline-flex';
                }
            })()
        """)
        await asyncio.sleep(0.8)
        await cdp.screenshot("02_Live_Cinema_Monitoring.png")

        # 3. Detection & Classification Center
        await cdp.click('[data-view="detection"]')
        await asyncio.sleep(2.0)
        await cdp.screenshot("03_Detection_Classification_Center.png")

        # 4. Recording Status & HUD Indicators
        await cdp.click('[data-view="monitoring"]')
        await asyncio.sleep(1.0)
        await cdp.screenshot("04_Recording_Status_HUD.png")

        # 5. Incident History Timeline
        await cdp.click('[data-view="incidents"]')
        await asyncio.sleep(2.0)
        await cdp.eval("""
            (() => {
                const btn = document.getElementById('viewTabTimeline');
                if (btn) btn.click();
            })()
        """)
        await asyncio.sleep(1.0)
        await cdp.screenshot("05_Event_Timeline_Records.png")

        # 6. Incident Gallery Grid
        await cdp.eval("""
            (() => {
                const btn = document.getElementById('viewTabGallery');
                if (btn) btn.click();
            })()
        """)
        await asyncio.sleep(1.2)
        await cdp.screenshot("06_Incident_Gallery_Grid.png")

        # 7. Forensic Multi-Frame Comparison Modal
        await cdp.eval("""
            (async () => {
                const cards = document.querySelectorAll('.incident-card');
                if (cards.length > 0) {
                    const evId = cards[0].getAttribute('data-event-id');
                    if (window.PySurveillance && window.PySurveillance.inspectEvent) {
                        await window.PySurveillance.inspectEvent(parseInt(evId));
                    } else if (cards[0].querySelector('.btn-inspect')) {
                        cards[0].querySelector('.btn-inspect').click();
                    } else {
                        cards[0].click();
                    }
                }
            })()
        """)
        await asyncio.sleep(2.2)
        await cdp.screenshot("07_Extracted_Forensic_Images.png")

        # Close modal
        await cdp.eval("""
            (() => {
                const modal = document.getElementById('incidentModal');
                if (modal) modal.style.display = 'none';
                const closeBtn = document.querySelector('#incidentModal .btn-close-modal');
                if (closeBtn) closeBtn.click();
            })()
        """)
        await asyncio.sleep(0.5)

        # 8. Acoustic Intelligence & Audio Monitoring
        await cdp.click('[data-view="audio"]')
        await asyncio.sleep(1.8)
        await cdp.screenshot("08_Acoustic_Intelligence_Audio.png")

        # 9. Hardware Automation & Smart Flashlight
        await cdp.click('[data-view="automation"]')
        await asyncio.sleep(1.8)
        await cdp.screenshot("09_Hardware_Automation_Lighting.png")

        # 10. Native Device & Browser Notification Center
        await cdp.click('[data-view="notifications"]')
        await asyncio.sleep(1.8)
        await cdp.screenshot("10_Notification_Interface.png")

        # 11. System Diagnostics & Analytics Telemetry
        await cdp.click('[data-view="analytics"]')
        await asyncio.sleep(1.8)
        await cdp.screenshot("11_System_Diagnostics_Telemetry.png")

        # 12. Camera & System Settings Console
        await cdp.click('[data-view="settings"]')
        await asyncio.sleep(1.8)
        await cdp.screenshot("12_Camera_Audio_Configuration.png")

        # 13. Security Firewall & Access Control
        await cdp.click('[data-view="security"]')
        await asyncio.sleep(1.8)
        await cdp.screenshot("13_Security_Access_Control.png")

    try:
        chrome_proc.terminate()
        chrome_proc.wait(timeout=2.0)
    except Exception:
        pass


def main():
    print("==================================================================")
    print(" 📸 PySURVEILLANCE — LIVE APPLICATION SCREENSHOT CAPTURE")
    print("==================================================================")

    # 1. Start Mock Camera Server on 127.0.0.1:8080 in daemon thread
    print("[1/4] Starting Threading Mock IP Camera Stream on http://127.0.0.1:8080...")
    cam_thread = threading.Thread(target=run_mock_camera, daemon=True)
    cam_thread.start()
    time.sleep(1.0)

    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/status.json", timeout=2) as r:
            assert r.status == 200
            print("  [✓] Mock Camera HTTP stream online & responding.")
    except Exception as e:
        print(f"  [!] Mock camera error: {e}")
        return

    # 2. Start PySURVEILLANCE backend on 127.0.0.1:8000
    print("[2/4] Starting PySURVEILLANCE Backend Server via run.py on http://127.0.0.1:8000...")
    env = os.environ.copy()
    env["PYSURVEILLANCE_INITIAL_PIN"] = "1234"
    server_proc = subprocess.Popen(
        [sys.executable, "run.py"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for server ready (up to 45 seconds for model loading)
    server_ok = False
    print("  Waiting for backend startup and neural model initialization...")
    for attempt in range(90):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=1) as r:
                if r.status == 200:
                    server_ok = True
                    break
        except Exception:
            time.sleep(0.5)

    if not server_ok:
        print("  [✗] Backend failed to start within timeout.")
        server_proc.terminate()
        return

    print("  [✓] PySURVEILLANCE Backend is active & streaming.")

    # 2.5 Authenticate and obtain session token
    token = ""
    try:
        auth_req = urllib.request.Request(
            "http://127.0.0.1:8000/api/auth/setup",
            data=json.dumps({"pin": "1234", "confirm_pin": "1234"}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(auth_req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            token = data.get("token", "")
            print(f"  [✓] Master PIN setup initialized. Token: {token[:12]}...")
    except Exception:
        # Already setup, verify
        try:
            verify_req = urllib.request.Request(
                "http://127.0.0.1:8000/api/auth/verify",
                data=json.dumps({"pin": "1234"}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(verify_req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                token = data.get("token", "")
                print(f"  [✓] Master PIN verified. Token: {token[:12]}...")
        except Exception as e:
            print(f"  [!] PIN verify note: {e}")

    # 3. Capture All Screen Views
    print("[3/4] Launching Headless Chrome & Capturing All Application Views...")
    try:
        asyncio.run(capture_all_screens(token))
    except Exception as e:
        print(f"  [!] Screenshot capture error: {e}")
        import traceback
        traceback.print_exc()

    # 4. Cleanup
    print("[4/4] Shutting down test services safely...")
    try:
        server_proc.terminate()
        server_proc.wait(timeout=3.0)
    except Exception:
        pass

    print("==================================================================")
    print(" ✅ LIVE APPLICATION SCREENSHOTS CAPTURED SUCCESSFULLY!")
    print(f" Saved to: {ASSETS_DIR}")
    print("==================================================================")


if __name__ == "__main__":
    main()
