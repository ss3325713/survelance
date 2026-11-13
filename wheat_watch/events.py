"""Event management and persistence for Wheat Watch.

Stores detected events into an SQLite database to preserve history across restarts.
Supports event deduplication sessions (grouping initial, change, and final images),
today's statistics, timeline queries, and safe retention deletion.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.events")


class EventStore:
    """Thread-safe SQLite storage for surveillance events."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = app_config.storage.get("db_path", "storage/events.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._active_sessions: Dict[int, Dict[str, Any]] = {}
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    label TEXT NOT NULL,
                    details TEXT,
                    image_path TEXT NOT NULL,
                    acknowledged INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'completed',
                    end_timestamp TEXT
                )
                """
            )
            # Add columns if migrating from earlier schema
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(events)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            if "status" not in existing_cols:
                conn.execute("ALTER TABLE events ADD COLUMN status TEXT DEFAULT 'completed'")
            if "end_timestamp" not in existing_cols:
                conn.execute("ALTER TABLE events ADD COLUMN end_timestamp TEXT")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)")
            conn.commit()

    def start_event_session(
        self,
        category: str,
        confidence: float,
        label: str,
        image_path: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a new deduplicated event session."""
        if timestamp is None:
            timestamp = datetime.now().astimezone().isoformat()

        det_dict = dict(details or {})
        det_dict["images"] = [
            {"path": image_path, "tag": "initial", "timestamp": timestamp, "label": label}
        ]
        det_dict["start_time"] = timestamp
        det_dict["tags"] = ["initial"]
        details_json = json.dumps(det_dict)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (timestamp, category, confidence, label, details, image_path, acknowledged, status, end_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, 0, 'active', ?)
                """,
                (timestamp, category, round(confidence, 3), label, details_json, image_path, timestamp),
            )
            conn.commit()
            event_id = cursor.lastrowid

        event_record = {
            "id": event_id,
            "timestamp": timestamp,
            "category": category,
            "confidence": round(confidence, 3),
            "label": label,
            "details": det_dict,
            "image_path": image_path,
            "status": "active",
            "end_timestamp": timestamp,
            "acknowledged": False,
        }
        with self._lock:
            self._active_sessions[event_id] = event_record

        logger.info(f"Event session #{event_id} STARTED: [{category}] {label} (image: {Path(image_path).name})")
        return event_record

    def update_event_session(
        self,
        event_id: int,
        new_image_path: Optional[str] = None,
        tag: str = "change",
        category: Optional[str] = None,
        label: Optional[str] = None,
        confidence: Optional[float] = None,
        new_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add a change image or escalate category of an active event session."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return None

            try:
                det_dict = json.loads(row["details"]) if row["details"] else {}
            except Exception:
                det_dict = {}

            now_iso = datetime.now().astimezone().isoformat()
            images_list = det_dict.get("images", [])
            tags_list = det_dict.get("tags", ["initial"])

            if new_image_path:
                images_list.append({
                    "path": new_image_path,
                    "tag": tag,
                    "timestamp": now_iso,
                    "label": label or row["label"],
                })
                if tag not in tags_list:
                    tags_list.append(tag)

            det_dict["images"] = images_list
            det_dict["tags"] = tags_list
            if new_details:
                for k, v in new_details.items():
                    if k != "images":
                        det_dict[k] = v

            final_category = category or row["category"]
            final_label = label or row["label"]
            final_conf = round(confidence, 3) if confidence is not None else row["confidence"]

            cursor.execute(
                """
                UPDATE events
                SET category = ?, label = ?, confidence = ?, details = ?, end_timestamp = ?
                WHERE id = ?
                """,
                (final_category, final_label, final_conf, json.dumps(det_dict), now_iso, event_id),
            )
            conn.commit()

            updated_record = {
                "id": event_id,
                "timestamp": row["timestamp"],
                "category": final_category,
                "confidence": final_conf,
                "label": final_label,
                "details": det_dict,
                "image_path": row["image_path"],
                "status": row["status"],
                "end_timestamp": now_iso,
                "acknowledged": bool(row["acknowledged"]),
            }
            self._active_sessions[event_id] = updated_record
            logger.info(f"Event session #{event_id} UPDATED with '{tag}' image: [{final_category}] {final_label}")
            return updated_record

    def close_event_session(
        self,
        event_id: int,
        final_image_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Finalize an active event session when motion ceases."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                self._active_sessions.pop(event_id, None)
                return None

            try:
                det_dict = json.loads(row["details"]) if row["details"] else {}
            except Exception:
                det_dict = {}

            now_iso = datetime.now().astimezone().isoformat()
            images_list = det_dict.get("images", [])
            tags_list = det_dict.get("tags", ["initial"])

            if final_image_path:
                images_list.append({
                    "path": final_image_path,
                    "tag": "final",
                    "timestamp": now_iso,
                    "label": "Motion Ended",
                })
                if "final" not in tags_list:
                    tags_list.append("final")

            # Compute session duration
            try:
                t0 = datetime.fromisoformat(row["timestamp"])
                t1 = datetime.fromisoformat(now_iso)
                dur = max(0.0, (t1 - t0).total_seconds())
            except Exception:
                dur = 0.0

            det_dict["images"] = images_list
            det_dict["tags"] = tags_list
            det_dict["session_duration_sec"] = round(dur, 1)

            cursor.execute(
                """
                UPDATE events
                SET status = 'completed', end_timestamp = ?, details = ?
                WHERE id = ?
                """,
                (now_iso, json.dumps(det_dict), event_id),
            )
            conn.commit()
            self._active_sessions.pop(event_id, None)

            logger.info(f"Event session #{event_id} CLOSED (duration: {dur:.1f}s, images: {len(images_list)}).")
            return {
                "id": event_id,
                "timestamp": row["timestamp"],
                "category": row["category"],
                "confidence": row["confidence"],
                "label": row["label"],
                "details": det_dict,
                "image_path": row["image_path"],
                "status": "completed",
                "end_timestamp": now_iso,
                "acknowledged": bool(row["acknowledged"]),
            }

    def get_active_image_paths(self) -> Set[str]:
        """Return all file paths associated with active ongoing event sessions to protect from retention purging."""
        paths: Set[str] = set()
        with self._lock:
            for s in self._active_sessions.values():
                if "image_path" in s:
                    paths.add(str(Path(s["image_path"]).resolve()))
                for img in s.get("details", {}).get("images", []):
                    if "path" in img:
                        paths.add(str(Path(img["path"]).resolve()))
        return paths

    def record_event(
        self,
        category: str,
        confidence: float,
        label: str,
        image_path: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an immediate single event (backward compatible with original API)."""
        if timestamp is None:
            timestamp = datetime.now().astimezone().isoformat()

        det_dict = dict(details or {})
        det_dict.setdefault("images", [
            {"path": image_path, "tag": "initial", "timestamp": timestamp, "label": label}
        ])
        det_dict.setdefault("tags", ["initial"])
        details_json = json.dumps(det_dict)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (timestamp, category, confidence, label, details, image_path, acknowledged, status, end_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, 0, 'completed', ?)
                """,
                (timestamp, category, round(confidence, 3), label, details_json, image_path, timestamp),
            )
            conn.commit()
            event_id = cursor.lastrowid

        event_record = {
            "id": event_id,
            "timestamp": timestamp,
            "category": category,
            "confidence": round(confidence, 3),
            "label": label,
            "details": det_dict,
            "image_path": image_path,
            "status": "completed",
            "end_timestamp": timestamp,
            "acknowledged": False,
        }
        logger.info(f"Event #{event_id} recorded: [{category}] {label} (conf: {confidence:.2f})")
        return event_record

    def list_events(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List events ordered chronologically descending."""
        query = "SELECT * FROM events"
        params: List[Any] = []

        if category and category != "all":
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        events = []
        for r in rows:
            try:
                details = json.loads(r["details"]) if r["details"] else {}
            except Exception:
                details = {}

            img_p = r["image_path"] if "image_path" in r.keys() else ""
            init_p = img_p
            final_p = img_p
            if details and "images" in details and isinstance(details["images"], list):
                for im in details["images"]:
                    if isinstance(im, dict):
                        if im.get("tag") == "initial":
                            init_p = im.get("path", init_p)
                        elif im.get("tag") == "final":
                            final_p = im.get("path", final_p)

            events.append(
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "category": r["category"],
                    "confidence": r["confidence"],
                    "label": r["label"],
                    "details": details,
                    "image_path": img_p,
                    "snapshot_path": img_p,
                    "initial_snapshot_path": init_p,
                    "final_snapshot_path": final_p,
                    "status": r["status"] if "status" in r.keys() else "completed",
                    "end_timestamp": r["end_timestamp"] if "end_timestamp" in r.keys() else r["timestamp"],
                    "acknowledged": bool(r["acknowledged"]),
                }
            )
        return events

    def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            r = cursor.fetchone()
            if not r:
                return None
            try:
                details = json.loads(r["details"]) if r["details"] else {}
            except Exception:
                details = {}

            img_p = r["image_path"] if "image_path" in r.keys() else ""
            init_p = img_p
            final_p = img_p
            if details and "images" in details and isinstance(details["images"], list):
                for im in details["images"]:
                    if isinstance(im, dict):
                        if im.get("tag") == "initial":
                            init_p = im.get("path", init_p)
                        elif im.get("tag") == "final":
                            final_p = im.get("path", final_p)

            return {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "category": r["category"],
                "confidence": r["confidence"],
                "label": r["label"],
                "details": details,
                "image_path": img_p,
                "snapshot_path": img_p,
                "initial_snapshot_path": init_p,
                "final_snapshot_path": final_p,
                "status": r["status"] if "status" in r.keys() else "completed",
                "end_timestamp": r["end_timestamp"] if "end_timestamp" in r.keys() else r["timestamp"],
                "acknowledged": bool(r["acknowledged"]),
            }

    def delete_event(self, event_id: int) -> bool:
        """Delete an event and all its associated image files (initial, change, final)."""
        event = self.get_event(event_id)
        if not event:
            return False

        files_to_remove: Set[str] = set()
        if event.get("image_path"):
            files_to_remove.add(event["image_path"])

        for img in event.get("details", {}).get("images", []):
            if "path" in img:
                files_to_remove.add(img["path"])

        for fpath in files_to_remove:
            try:
                p = Path(fpath)
                if p.exists() and p.is_file():
                    p.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete event image file {fpath}: {e}")

        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()

        with self._lock:
            self._active_sessions.pop(event_id, None)

        return True

    def delete_records_for_files(self, deleted_files: List[str]) -> int:
        """Purge events whose primary image path or additional images match deleted files."""
        if not deleted_files:
            return 0
        resolved_set = {str(Path(f).resolve()) for f in deleted_files}

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, image_path FROM events")
            rows = cursor.fetchall()
            ids_to_delete = []
            for r in rows:
                if str(Path(r["image_path"]).resolve()) in resolved_set:
                    ids_to_delete.append(r["id"])

            if ids_to_delete:
                placeholders = ",".join("?" for _ in ids_to_delete)
                cursor.execute(f"DELETE FROM events WHERE id IN ({placeholders})", ids_to_delete)
                conn.commit()
                return len(ids_to_delete)
        return 0

    def clear_all(self) -> int:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT image_path, details FROM events")
            rows = cursor.fetchall()
            for r in rows:
                try:
                    p = Path(r["image_path"])
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
                try:
                    det = json.loads(r["details"]) if r["details"] else {}
                    for img in det.get("images", []):
                        p2 = Path(img["path"])
                        if p2.exists():
                            p2.unlink()
                except Exception:
                    pass
            cursor.execute("DELETE FROM events")
            conn.commit()
            self._active_sessions.clear()
            return cursor.rowcount

    def get_today_count(self) -> int:
        """Count events that occurred today (local date)."""
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM events WHERE timestamp LIKE ?", (f"{today_prefix}%",))
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary counts, today's count, category breakdown, and latest event."""
        today_prefix = datetime.now().strftime("%Y-%m-%d")

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM events")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as cnt FROM events WHERE timestamp LIKE ?", (f"{today_prefix}%",))
            today_count = cursor.fetchone()["cnt"]

            cursor.execute("SELECT category, COUNT(*) as cnt FROM events GROUP BY category")
            counts = {r["category"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute("SELECT category, COUNT(*) as cnt FROM events WHERE timestamp LIKE ? GROUP BY category", (f"{today_prefix}%",))
            today_counts = {r["category"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1")
            latest = cursor.fetchone()

        latest_dict = None
        if latest:
            try:
                det = json.loads(latest["details"]) if latest["details"] else {}
            except Exception:
                det = {}
            latest_dict = {
                "id": latest["id"],
                "timestamp": latest["timestamp"],
                "category": latest["category"],
                "label": latest["label"],
                "confidence": latest["confidence"],
                "image_path": latest["image_path"],
                "details": det,
                "status": latest["status"] if "status" in latest.keys() else "completed",
            }

        return {
            "total_events": total,
            "today_count": today_count,
            "category_counts": counts,
            "today_category_counts": today_counts,
            "latest_event": latest_dict,
        }

    def check_integrity(self) -> Dict[str, Any]:
        """Perform SQLite integrity checks and report database health."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchall()
            status_text = integrity_result[0][0] if integrity_result else "UNKNOWN"
            is_healthy = (status_text.lower() == "ok")

            cursor.execute("SELECT COUNT(*) FROM events")
            row_count = cursor.fetchone()[0]

            db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "status": "healthy" if is_healthy else "corrupted",
            "integrity_check": status_text,
            "row_count": row_count,
            "file_size_bytes": db_size_bytes,
            "file_size_kb": round(db_size_bytes / 1024, 1),
            "db_path": str(self.db_path),
        }

    def create_backup(self, backup_dir: Optional[str] = None) -> str:
        """Create a point-in-time hot backup of the SQLite database using SQLite Backup API."""
        if backup_dir is None:
            b_dir = Path("storage/backups")
        else:
            b_dir = Path(backup_dir)
        b_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = b_dir / f"events_backup_{ts}.db"

        with self._lock, self._get_connection() as src_conn:
            dst_conn = sqlite3.connect(str(backup_file))
            try:
                src_conn.backup(dst_conn)
                logger.info(f"Database point-in-time backup created: {backup_file} ({backup_file.stat().st_size} bytes)")
            finally:
                dst_conn.close()

        return str(backup_file)


event_store = EventStore()
