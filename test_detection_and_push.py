#!/usr/bin/env python3
"""Targeted CDP Verification for Detection Center Controls and Device Notification Center."""

import sys
import os
import time
import json
import asyncio
import tempfile
import urllib.request
import subprocess
from pathlib import Path
import websockets

BASE_URL = "http://127.0.0.1:8000"
ARTIFACTS_DIR = Path(os.environ.get("PYSURVEILLANCE_ARTIFACTS_DIR", "/tmp/pysurveillance_artifacts"))

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

    async def screenshot(self, path):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        import base64
        with open(path, "wb") as f:
            f.write(base64.b64decode(res["data"]))
        print(f"[CDP] Screenshot saved: {path}")

async def run_tests():
    chrome_proc = None
    tmp_profile = tempfile.mkdtemp(prefix="cdp_test_pysurv_")
    try:
        chrome_args = [
            "google-chrome",
            "--headless=new",
            "--remote-debugging-port=9222",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={tmp_profile}",
            f"{BASE_URL}/#overview"
        ]
        chrome_proc = subprocess.Popen(chrome_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for Chrome DevTools port
        ws_url = None
        for _ in range(30):
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
        print(f"[CDP] Connected to Chrome DevTools WebSocket: {ws_url}")

        async with websockets.connect(ws_url) as ws:
            cdp = CDPSession(ws)
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")

            # Grant notifications permission via CDP
            await cdp.send("Browser.grantPermissions", {
                "origin": BASE_URL,
                "permissions": ["notifications"]
            })

            # Navigate to PySURVEILLANCE
            print(f"[CDP] Navigating to {BASE_URL}...")
            await cdp.send("Page.navigate", {"url": BASE_URL})
            await asyncio.sleep(2.0)

            # Authenticate PIN 1234
            auth_res = await cdp.eval("""
                (async () => {
                    const res = await fetch('/api/auth/verify', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ pin: '1234' })
                    });
                    const d = await res.json();
                    if (d.success && d.token) {
                        localStorage.setItem('pysurv_session_token', d.token);
                        if (window.PySurveillance) {
                            // reload settings
                            return { ok: true, token: d.token };
                        }
                    }
                    return { ok: false };
                })()
            """)
            print(f"[CDP] PIN auth result: {auth_res}")

            # 1. Test Service Worker Registration
            sw_res = await cdp.eval("""
                (async () => {
                    if (!('serviceWorker' in navigator)) return { sw: false };
                    const reg = await navigator.serviceWorker.ready;
                    return {
                        sw: true,
                        scope: reg ? reg.scope : null,
                        active: !!(reg && reg.active),
                        notificationPermission: Notification.permission
                    };
                })()
            """)
            print(f"[CDP] Service Worker & Notification state: {sw_res}")

            # 2. Test Detection Center View and Sliders
            print("[CDP] Navigating to #detection view...")
            await cdp.eval("window.PySurveillance.navigateToView('detection')")
            await asyncio.sleep(1.0)

            # Read initial values
            init_vals = await cdp.eval("""
                ({
                    sliderThresh: document.getElementById('detThresholdSlider')?.value,
                    sliderConf: document.getElementById('detConfidenceSlider')?.value,
                    displayThresh: document.getElementById('detMotionThresh')?.textContent,
                    displayConf: document.getElementById('detConfidenceDisplay')?.textContent
                })
            """)
            print(f"[CDP] Initial Detection Center values: {init_vals}")

            # Move sliders to 35 and 0.50
            slider_update = await cdp.eval("""
                (() => {
                    const slThresh = document.getElementById('detThresholdSlider');
                    const slConf = document.getElementById('detConfidenceSlider');
                    slThresh.value = 35;
                    slThresh.dispatchEvent(new Event('input'));
                    slConf.value = 0.50;
                    slConf.dispatchEvent(new Event('input'));
                    return {
                        threshVal: document.getElementById('detThresholdVal')?.textContent,
                        confVal: document.getElementById('detConfidenceVal')?.textContent,
                        detMotionThresh: document.getElementById('detMotionThresh')?.textContent,
                        detConfidenceDisplay: document.getElementById('detConfidenceDisplay')?.textContent
                    };
                })()
            """)
            print(f"[CDP] After slider input event: {slider_update}")

            # Click Apply Detection Thresholds button
            print("[CDP] Clicking 'Apply Detection Thresholds' button...")
            click_apply = await cdp.eval("""
                (async () => {
                    const btn = document.getElementById('detSaveSettingsBtn');
                    btn.click();
                    await new Promise(r => setTimeout(r, 600));
                    return {
                        btnText: btn.textContent,
                        displayThresh: document.getElementById('detMotionThresh')?.textContent,
                        displayConf: document.getElementById('detConfidenceDisplay')?.textContent
                    };
                })()
            """)
            print(f"[CDP] Apply button click result: {click_apply}")
            await asyncio.sleep(1.0)

            # Capture screenshot of Detection Center
            det_shot = ARTIFACTS_DIR / "detection_center_controls_verified.png"
            await cdp.screenshot(str(det_shot))

            # 3. Test Notifications Center
            print("[CDP] Navigating to #notifications view...")
            await cdp.eval("window.PySurveillance.navigateToView('notifications')")
            await asyncio.sleep(1.0)

            # Click Send Test Push button
            print("[CDP] Clicking 'Send Test Push' button...")
            push_click = await cdp.eval("""
                (async () => {
                    const btn = document.getElementById('notifTestPushBtn');
                    btn.click();
                    await new Promise(r => setTimeout(r, 2000));
                    const banner = document.querySelector('.push-card');
                    const notifications = await (await navigator.serviceWorker.ready).getNotifications();
                    return {
                        bannerVisible: !!banner,
                        bannerTitle: banner ? banner.querySelector('div > div:first-child')?.textContent : null,
                        bannerBody: banner ? banner.querySelector('div > div:last-child')?.textContent : null,
                        deviceNotificationsCount: notifications.length,
                        firstDeviceNotificationTitle: notifications.length > 0 ? notifications[0].title : null
                    };
                })()
            """)
            print(f"[CDP] Send Test Push result: {push_click}")

            # Capture screenshot of Notifications Center
            notif_shot = ARTIFACTS_DIR / "device_notification_center_verified.png"
            await cdp.screenshot(str(notif_shot))

            # Verify backend thresholds
            live_thresh = await cdp.eval("""
                (async () => {
                    const res = await fetch('/api/detection/thresholds');
                    return await res.json();
                })()
            """)
            print(f"[CDP] Live Backend /api/detection/thresholds: {live_thresh}")

            assert live_thresh.get("motion_threshold") == 35, f"Expected motion_threshold 35, got {live_thresh.get('motion_threshold')}"
            assert live_thresh.get("detection_confidence") == 0.50, f"Expected detection_confidence 0.50, got {live_thresh.get('detection_confidence')}"
            print("[CDP] ALL TESTS PASSED SUCCESSFULLY!")

    finally:
        if chrome_proc:
            chrome_proc.terminate()
            chrome_proc.wait()
        import shutil
        shutil.rmtree(tmp_profile, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(run_tests())
