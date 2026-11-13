#!/usr/bin/env python3
"""PySURVEILLANCE - Intelligent Field Surveillance & Security Monitoring Platform.

Main application entrypoint. Binds to 0.0.0.0:8000.
"""

import logging
import os
import signal
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from wheat_watch.config import app_config
from wheat_watch.network import get_lan_ip


def handle_signals(sig, frame):
    print("\n[PySURVEILLANCE] Received shutdown signal. Terminating gracefully...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, handle_signals)
    signal.signal(signal.SIGTERM, handle_signals)

    lan_ip = get_lan_ip()
    host = app_config.server.get("host", "0.0.0.0")
    port = app_config.server.get("port", 8000)
    phone_ip = app_config.camera.get("phone_ip", "192.168.31.211")
    phone_port = app_config.camera.get("phone_port", 8080)

    banner = f"""
========================================================================
🛡️  PySURVEILLANCE — Intelligent Security & Field Defense Console
========================================================================
 [✓] Local Network Binding : {host}:{port}
 [✓] Laptop Access URL     : http://127.0.0.1:{port}
 [✓] Phone Dashboard URL   : http://{lan_ip}:{port}
 [✓] Redmi 10 Camera       : http://{phone_ip}:{phone_port}/video
 [✓] Redmi 10 Microphone   : http://{phone_ip}:{phone_port}/audio.wav
 [✓] Hardware Flashlight   : Motion-Triggered (15s Inactivity Timeout)
 [✓] Audio Engine Active   : Laptop system speakers (paplay/aplay)
 [✓] Security Firewall     : Local LAN Enforced | PBKDF2 PIN Protected
 [✓] Power Manager         : systemd-inhibit active monitoring
========================================================================
"""
    print(banner)

    uvicorn.run(
        "wheat_watch.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
