#!/usr/bin/env python3
"""Capture high-resolution screenshots of Incident History, Forensic Snapshot Modal,
and Overview Latest Incident Detection Card.
"""

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

async def capture_incidents():
    user_data = tempfile.mkdtemp()
    print(f"Launching Chrome profile at {user_data}")
    chrome = subprocess.Popen([
        "google-chrome",
        "--headless=new",
        "--remote-debugging-port=9222",
        "--no-sandbox",
        "--disable-gpu",
        f"--user-data-dir={user_data}",
        f"{BASE_URL}/#overview"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ws_url = None
        for _ in range(25):
            try:
                with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=1) as resp:
                    tabs = json.loads(resp.read().decode())
                    page_tabs = [t for t in tabs if t.get("type") == "page"]
                    if page_tabs:
                        ws_url = page_tabs[0]["webSocketDebuggerUrl"]
                        break
            except Exception:
                await asyncio.sleep(0.3)

        assert ws_url, "DevTools WS connection failed"
        print(f"Connected to WS: {ws_url}")

        async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
            async def send(method, params=None):
                payload = {"id": int(time.time()*1000) % 100000, "method": method}
                if params:
                    payload["params"] = params
                await ws.send(json.dumps(payload))
                while True:
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    if msg.get("id") == payload["id"]:
                        return msg

            async def eval_js(expr):
                res = await send("Runtime.evaluate", {
                    "expression": expr,
                    "returnByValue": True,
                    "awaitPromise": True
                })
                return res.get("result", {}).get("result", {}).get("value")

            async def screenshot(name):
                res = await send("Page.captureScreenshot", {"format": "jpeg", "quality": 90})
                import base64
                data = base64.b64decode(res["result"]["data"])
                out_path = Path("static/screenshots") / name
                out_path.write_bytes(data)
                print(f"Captured: {out_path} ({len(data)} bytes)")
                return out_path

            await send("Page.enable")
            await send("Runtime.enable")
            await send("DOM.enable")
            await send("Emulation.setDeviceMetricsOverride", {
                "width": 1920,
                "height": 1080,
                "deviceScaleFactor": 1,
                "mobile": False
            })

            # Navigate to overview and wait
            await send("Page.navigate", {"url": f"{BASE_URL}/#overview"})
            await asyncio.sleep(2.0)

            # Unlock console with PIN if needed
            await eval_js("""
                (async () => {
                    const input = document.getElementById('pinInput');
                    const form = document.getElementById('pinForm');
                    if (input && form) {
                        input.value = '1234';
                        document.querySelector('#pinForm button[type="submit"]').click();
                        await new Promise(r => setTimeout(r, 600));
                    }
                })()
            """)

            # 1. Capture Overview with Latest Incident Card
            await asyncio.sleep(1.0)
            await screenshot("incident_overview_latest_card.png")

            # 2. Navigate to Incident History View
            await eval_js("navigateToView('incidents'); window.location.hash = 'incidents';")
            await asyncio.sleep(1.5)
            await screenshot("incident_history_timeline.png")

            # 3. Switch to Gallery View Layout
            await eval_js("""
                (() => {
                    const galleryTab = document.getElementById('viewTabGallery');
                    if (galleryTab) galleryTab.click();
                })()
            """)
            await asyncio.sleep(1.0)
            await screenshot("incident_history_gallery.png")

            # Switch back to timeline
            await eval_js("""
                (() => {
                    const timelineTab = document.getElementById('viewTabTimeline');
                    if (timelineTab) timelineTab.click();
                })()
            """)
            await asyncio.sleep(0.5)

            # 4. Open the latest incident card to trigger Forensic Comparison Modal
            opened = await eval_js("""
                (async () => {
                    const firstCard = document.querySelector('.incident-card');
                    if (firstCard) {
                        const evId = firstCard.getAttribute('data-event-id');
                        if (window.PySurveillance && window.PySurveillance.inspectEvent) {
                            await window.PySurveillance.inspectEvent(parseInt(evId));
                        } else {
                            firstCard.click();
                        }
                        await new Promise(r => setTimeout(r, 1500));
                        return {
                            opened: true,
                            id: evId,
                            title: document.getElementById('eventDetailTitle') ? document.getElementById('eventDetailTitle').innerText : '',
                            category: document.getElementById('eventDetailCategory') ? document.getElementById('eventDetailCategory').innerText : '',
                            label: document.getElementById('eventDetailLabel') ? document.getElementById('eventDetailLabel').innerText : ''
                        };
                    }
                    return { opened: false };
                })()
            """)
            print("Modal open result:", opened)

            # 5. Capture Initial Frame tab in modal
            await eval_js("document.getElementById('btnCompInitial').click();")
            await asyncio.sleep(0.6)
            await screenshot("incident_modal_initial_frame.png")

            # 6. Capture Peak / Final Frame tab in modal
            await eval_js("document.getElementById('btnCompFinal').click();")
            await asyncio.sleep(0.6)
            await screenshot("incident_modal_final_frame.png")

            # 7. Capture Side-by-Side Comparison tab in modal
            await eval_js("document.getElementById('btnCompSideBySide').click();")
            await asyncio.sleep(0.6)
            await screenshot("incident_modal_side_by_side.png")

            print("All incident screenshots captured successfully!")

    finally:
        chrome.terminate()

if __name__ == "__main__":
    asyncio.run(capture_incidents())
