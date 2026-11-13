"""Network utilities for Wheat Watch.

Detects local LAN IPv4 address, restricts access to LAN, and generates QR code.
"""

from __future__ import annotations

import io
import ipaddress
import logging
import socket
from typing import Optional

logger = logging.getLogger("wheat_watch.network")


def get_lan_ip() -> str:
    """Identify the laptop's local LAN IPv4 address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually transmit packets, just resolves routing table interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        logger.warning(f"Could not determine LAN IP via socket routing: {e}")
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def is_local_network_ip(ip_str: str) -> bool:
    """Validate that the client IP is on the local network (private or loopback)."""
    if not ip_str:
        return False
    if ip_str in ("testclient", "localhost"):
        return True
    # Clean port if present
    if ":" in ip_str and not ip_str.startswith("["):
        parts = ip_str.split(":")
        if len(parts) == 2 and parts[1].isdigit():
            ip_str = parts[0]
            
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        return False


def generate_qr_svg(url: str) -> str:
    """Generate an SVG string for a QR code encoding the URL."""
    try:
        import qrcode
        import qrcode.image.svg

        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(url, image_factory=factory, box_size=10, border=2)
        stream = io.BytesIO()
        img.save(stream)
        return stream.getvalue().decode("utf-8")
    except Exception as e:
        logger.debug(f"QR code generation fallback: {e}")
        return ""
