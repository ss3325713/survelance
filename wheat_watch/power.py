"""Power and sleep inhibition management for Wheat Watch.

Prevents the laptop from automatically suspending or sleeping during active monitoring.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from typing import Optional

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.power")


class PowerManager:
    """Manages system sleep and idle inhibition."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inhibit_proc: Optional[subprocess.Popen] = None
        self._is_inhibited = False
        self._systemd_inhibit = shutil.which("systemd-inhibit")

    @property
    def is_inhibited(self) -> bool:
        return self._is_inhibited

    def start_inhibition(self) -> bool:
        """Start inhibiting sleep if configured."""
        if not app_config.power.get("prevent_sleep", True):
            logger.info("Sleep inhibition disabled in configuration.")
            return False

        with self._lock:
            if self._inhibit_proc and self._inhibit_proc.poll() is None:
                return True  # Already running

            if not self._systemd_inhibit:
                logger.warning("systemd-inhibit not found. Laptop power management cannot be inhibited.")
                return False

            try:
                cmd = [
                    self._systemd_inhibit,
                    "--what=idle:sleep",
                    "--who=PySURVEILLANCE",
                    "--why=Active agricultural monitoring and security",
                    "sleep",
                    "infinity",
                ]
                self._inhibit_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._is_inhibited = True
                logger.info("Laptop sleep/idle inhibition ACTIVATED via systemd-inhibit.")
                return True
            except Exception as e:
                logger.error(f"Failed to start systemd-inhibit: {e}")
                self._is_inhibited = False
                return False

    def stop_inhibition(self) -> None:
        """Stop inhibiting sleep."""
        with self._lock:
            if self._inhibit_proc:
                try:
                    self._inhibit_proc.terminate()
                    self._inhibit_proc.wait(timeout=1.0)
                except Exception:
                    try:
                        self._inhibit_proc.kill()
                    except Exception:
                        pass
                finally:
                    self._inhibit_proc = None

            self._is_inhibited = False
            logger.info("Laptop sleep/idle inhibition DEACTIVATED.")


power_manager = PowerManager()
