"""Image storage and retention management for Wheat Watch.

Organizes images by date (storage/events/YYYY-MM-DD), enforces 14-day retention,
never deletes images from active ongoing events, and reports storage telemetry.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import cv2
import numpy as np

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.storage")


class StorageManager:
    """Handles saving event images, date-based folder organization, and retention."""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        if base_dir is None:
            base_dir = app_config.storage.get("events_dir", "storage/events")
        self.events_dir = Path(base_dir)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self._cached_stats: Optional[Dict[str, Any]] = None
        self._cached_stats_time: float = 0.0

    def save_event_image(
        self,
        frame: np.ndarray,
        category: str,
        tag: str = "initial",
        active_paths: Optional[Set[str]] = None,
    ) -> str:
        """Save an event frame to a date-organized folder (storage/events/YYYY-MM-DD/).
        
        Tags: 'initial', 'change', 'final', 'snapshot'.
        """
        date_str = time.strftime("%Y-%m-%d")
        day_dir = self.events_dir / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        ts = time.strftime("%Y%m%d_%H%M%S")
        millis = int((time.time() % 1) * 1000)
        safe_cat = "".join(c if c.isalnum() else "_" for c in category).strip("_").lower()
        filename = f"{ts}_{millis:03d}_{safe_cat}_{tag}.jpg"
        filepath = day_dir / filename

        # Save with quality 85
        cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self._cached_stats = None
        
        # Periodically enforce retention
        self.enforce_retention(active_paths=active_paths)
        return str(filepath)

    def enforce_retention(
        self,
        retention_days: Optional[int] = None,
        max_mb: Optional[int] = None,
        active_paths: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Automatically delete expired images (> retention_days) and purge DB records.
        
        CRITICAL RULE: Never deletes images from active events.
        """
        if retention_days is None:
            retention_days = int(app_config.storage.get("retention_days", 14))
        if max_mb is None:
            max_mb = int(app_config.storage.get("max_storage_mb", 2048))

        active_set: Set[str] = set()
        if active_paths:
            active_set = {str(Path(p).resolve()) for p in active_paths}

        deleted_files: List[str] = []
        now = time.time()
        cutoff_seconds = now - (retention_days * 86400.0)

        # 1. Collect all jpg files (both flat legacy and date-organized subdirectories)
        all_files: List[Path] = []
        for p in self.events_dir.rglob("*.jpg"):
            if p.is_file():
                all_files.append(p)

        freed_bytes = 0

        # 2. Time-based retention (older than retention_days)
        for f in all_files:
            try:
                resolved_path = str(f.resolve())
                # Never delete images belonging to active events
                if resolved_path in active_set:
                    continue

                if f.stat().st_mtime < cutoff_seconds:
                    sz = f.stat().st_size
                    f.unlink()
                    freed_bytes += sz
                    deleted_files.append(str(f))
            except Exception as e:
                logger.debug(f"Failed to remove expired file {f}: {e}")

        # 3. Size-based retention if total directory size still exceeds max_mb
        remaining_files: List[Path] = []
        total_bytes = 0
        for p in self.events_dir.rglob("*.jpg"):
            try:
                if p.is_file():
                    total_bytes += p.stat().st_size
                    remaining_files.append(p)
            except (FileNotFoundError, OSError):
                pass

        max_bytes = max_mb * 1024 * 1024

        if total_bytes > max_bytes:
            def safe_mtime(f: Path) -> float:
                try:
                    return f.stat().st_mtime
                except (FileNotFoundError, OSError):
                    return 0.0

            # Sort oldest first
            remaining_files.sort(key=safe_mtime)
            for f in remaining_files:
                try:
                    resolved_path = str(f.resolve())
                    if resolved_path in active_set:
                        continue

                    sz = f.stat().st_size
                    f.unlink()
                    freed_bytes += sz
                    deleted_files.append(str(f))
                    if total_bytes - freed_bytes <= max_bytes * 0.85:
                        break
                except Exception:
                    pass

        # 4. Clean up empty date subdirectories
        for d in self.events_dir.iterdir():
            if d.is_dir():
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                except Exception:
                    pass

        # 5. Purge matching SQLite records for deleted files
        if deleted_files:
            try:
                from wheat_watch.events import event_store
                event_store.delete_records_for_files(deleted_files)
                logger.info(
                    f"Storage retention enforced: removed {len(deleted_files)} files "
                    f"({freed_bytes / (1024*1024):.2f} MB freed, retention: {retention_days} days)."
                )
            except Exception as e:
                logger.warning(f"Error purging DB records during retention cleanup: {e}")

        self._cached_stats = None
        return {
            "deleted_count": len(deleted_files),
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "retention_days": retention_days,
        }

    def get_storage_stats(self, force: bool = False) -> Dict[str, Any]:
        """Compute comprehensive storage usage telemetry with short TTL caching."""
        now = time.time()
        if not force and self._cached_stats is not None and (now - self._cached_stats_time < 5.0):
            return self._cached_stats

        total_bytes = 0
        file_count = 0
        min_mtime: Optional[float] = None
        max_mtime: Optional[float] = None

        try:
            for f in self.events_dir.rglob("*.jpg"):
                try:
                    if f.is_file():
                        st = f.stat()
                        file_count += 1
                        total_bytes += st.st_size
                        m = st.st_mtime
                        if min_mtime is None or m < min_mtime:
                            min_mtime = m
                        if max_mtime is None or m > max_mtime:
                            max_mtime = m
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error scanning storage files: {e}")

        max_mb = int(app_config.storage.get("max_storage_mb", 2048))
        retention_days = int(app_config.storage.get("retention_days", 14))

        # Check partition disk space
        try:
            usage = shutil.disk_usage(str(self.events_dir))
            disk_total_mb = round(usage.total / (1024 * 1024), 1)
            disk_free_mb = round(usage.free / (1024 * 1024), 1)
            disk_used_pct = round((usage.used / usage.total) * 100.0, 1)
        except Exception:
            disk_total_mb = 0.0
            disk_free_mb = 0.0
            disk_used_pct = 0.0

        oldest_date: Optional[str] = None
        newest_date: Optional[str] = None
        if min_mtime is not None:
            oldest_date = datetime.fromtimestamp(min_mtime).strftime("%Y-%m-%d %H:%M")
        if max_mtime is not None:
            newest_date = datetime.fromtimestamp(max_mtime).strftime("%Y-%m-%d %H:%M")

        used_mb = round(total_bytes / (1024 * 1024), 2)
        storage_pct = round((used_mb / max_mb) * 100.0, 1) if max_mb > 0 else 0.0

        stats = {
            "events_dir": str(self.events_dir),
            "image_count": file_count,
            "used_mb": used_mb,
            "max_mb": max_mb,
            "storage_percent": storage_pct,
            "retention_days": retention_days,
            "disk_free_mb": disk_free_mb,
            "disk_total_mb": disk_total_mb,
            "disk_used_pct": disk_used_pct,
            "oldest_event": oldest_date,
            "newest_event": newest_date,
        }
        self._cached_stats = stats
        self._cached_stats_time = now
        return stats


storage_manager = StorageManager()
