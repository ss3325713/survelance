"""Real-time push message broadcaster for connected browsers.

Uses Server-Sent Events (SSE) to push instant notifications, detection events,
and alarm triggers to all active dashboard sessions in real time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional, Set

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.broadcaster")


class PushBroadcaster:
    """Thread-safe event broadcaster for Server-Sent Events (SSE)."""

    def __init__(self) -> None:
        self._queues: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the running asyncio event loop."""
        self._loop = loop

    async def register(self) -> asyncio.Queue:
        """Register a new client queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues.add(q)
        logger.info(f"Connected browser client registered for push stream. Active listeners: {len(self._queues)}")
        return q

    async def unregister(self, q: asyncio.Queue) -> None:
        """Unregister a disconnected client queue."""
        async with self._lock:
            self._queues.discard(q)
        logger.info(f"Browser client disconnected from push stream. Remaining listeners: {len(self._queues)}")

    @property
    def client_count(self) -> int:
        return len(self._queues)

    def broadcast_sync(self, event_type: str, data: Dict[str, Any]) -> None:
        """Dispatch a push message from any synchronous worker thread."""
        if not app_config.push.get("enabled", True) and event_type not in ("push_config", "system"):
            # If backend push is disabled, skip regular notifications
            return

        # Category authorization filtering for push messages
        if event_type == "detection":
            category = data.get("category", "")
            if category == "General motion" and not app_config.push.get("push_on_general_motion", False):
                return
            if category == "Unknown object" and not app_config.push.get("push_on_unknown_objects", False):
                return
            alert_cats = app_config.push.get("alert_categories")
            if alert_cats is not None and category not in alert_cats:
                return

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data), self._loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.broadcast(event_type, data))
            except RuntimeError:
                logger.debug("No active event loop available to broadcast push message.")

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast an event asynchronously to all connected client queues."""
        payload = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        dead_queues = []
        async with self._lock:
            for q in list(self._queues):
                try:
                    if q.full():
                        try:
                            q.get_nowait()  # Discard oldest to keep latest push
                        except asyncio.QueueEmpty:
                            pass
                    q.put_nowait(payload)
                except Exception:
                    dead_queues.append(q)

            for dq in dead_queues:
                self._queues.discard(dq)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Yield Server-Sent Events (SSE) to an open HTTP connection."""
        q = await self.register()
        try:
            # Initial handshake
            handshake = json.dumps(
                {
                    "status": "connected",
                    "push_enabled": app_config.push.get("enabled", True),
                    "browser_audio": app_config.push.get("browser_audio", True),
                    "connected_clients": len(self._queues),
                    "timestamp": time.time(),
                }
            )
            yield f"event: handshake\ndata: {handshake}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: {msg['type']}\ndata: {json.dumps(msg['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment to prevent client/proxy timeout
                    yield ": keepalive\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await self.unregister(q)


broadcaster = PushBroadcaster()
