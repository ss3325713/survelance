"""Motion-based video recording and background incident processing for PySURVEILLANCE.

Features:
1. Motion-triggered video recording: Starts immediately when camera motion is detected,
   without waiting for AI classification.
2. Inactivity timer: 15-second countdown timer that resets with every new qualifying motion.
3. Maximum segment duration: Configurable segment cap (default 60s). If continuous
   motion exceeds cap, current segment cleanly rolls over into the next segment under the same session.
4. Separate segments & incident linking: Multiple video segments linked to the parent incident session.
5. Persistent Queue: SQLite-backed video_jobs table tracking the exact lifecycle:
   RECORDING -> QUEUED -> PROCESSING -> VERIFYING -> COMPLETED -> VIDEO DELETED.
6. Verification Safeguards: Source video is NEVER deleted until all extracted images are verified
   on disk (existing, non-zero file size, readable). Failed jobs retain videos for safe retries.
7. Startup Recovery: Interrupted recording/processing jobs are safely inspected and resumed on boot.
8. Decoupled Processing: Independent background worker thread with bounded concurrency and resource throttling.
9. Image Quality Selection: Selects representative frames based on Laplacian variance (sharpness/blur)
   and exposure, running YOLOv8 detection and appending frames to the incident image gallery.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from wheat_watch.broadcaster import broadcaster
from wheat_watch.config import app_config
from wheat_watch.detector import create_detector, detector
from wheat_watch.events import event_store
from wheat_watch.storage import storage_manager

logger = logging.getLogger("wheat_watch.video_recording")


class VideoJobStatus:
    RECORDING = "RECORDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VideoJobStore:
    """Thread-safe SQLite storage for video recording jobs and queue states."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = app_config.storage.get("db_path", "storage/events.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS video_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    segment_index INTEGER DEFAULT 1,
                    video_path TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_sec REAL DEFAULT 0.0,
                    frame_count INTEGER DEFAULT 0,
                    fps REAL DEFAULT 10.0,
                    width INTEGER DEFAULT 0,
                    height INTEGER DEFAULT 0,
                    extracted_frames_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_video_jobs_status ON video_jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_video_jobs_event_id ON video_jobs(event_id)")
            conn.commit()

    def create_job(
        self,
        video_path: str,
        event_id: Optional[int],
        segment_index: int,
        fps: float,
        width: int,
        height: int,
    ) -> int:
        now_iso = datetime.now().astimezone().isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO video_jobs (
                    event_id, segment_index, video_path, status, created_at,
                    fps, width, height
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    segment_index,
                    str(video_path),
                    VideoJobStatus.RECORDING,
                    now_iso,
                    fps,
                    width,
                    height,
                ),
            )
            conn.commit()
            job_id = cursor.lastrowid
            logger.info(f"Video job #{job_id} created [RECORDING] -> {Path(video_path).name} (Event #{event_id}, Seg #{segment_index})")
            return job_id

    def mark_queued(self, job_id: int, duration_sec: float, frame_count: int) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE video_jobs
                SET status = ?, duration_sec = ?, frame_count = ?
                WHERE id = ?
                """,
                (VideoJobStatus.QUEUED, round(duration_sec, 2), frame_count, job_id),
            )
            conn.commit()
            logger.info(f"Video job #{job_id} marked [QUEUED] (Duration: {duration_sec:.1f}s, Frames: {frame_count})")

    def get_next_queued_job(self) -> Optional[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM video_jobs
                WHERE status = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (VideoJobStatus.QUEUED,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def mark_processing(self, job_id: int) -> None:
        now_iso = datetime.now().astimezone().isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE video_jobs
                SET status = ?, started_at = ?
                WHERE id = ?
                """,
                (VideoJobStatus.PROCESSING, now_iso, job_id),
            )
            conn.commit()
            logger.info(f"Video job #{job_id} marked [PROCESSING]")

    def mark_verifying(self, job_id: int, extracted_count: int) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE video_jobs
                SET status = ?, extracted_frames_count = ?
                WHERE id = ?
                """,
                (VideoJobStatus.VERIFYING, extracted_count, job_id),
            )
            conn.commit()
            logger.info(f"Video job #{job_id} marked [VERIFYING] (Extracted: {extracted_count} frames)")

    def mark_completed(self, job_id: int) -> None:
        now_iso = datetime.now().astimezone().isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE video_jobs
                SET status = ?, completed_at = ?, error_message = NULL
                WHERE id = ?
                """,
                (VideoJobStatus.COMPLETED, now_iso, job_id),
            )
            conn.commit()
            logger.info(f"Video job #{job_id} marked [COMPLETED]")

    def mark_failed(self, job_id: int, error_message: str) -> None:
        now_iso = datetime.now().astimezone().isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE video_jobs
                SET status = ?, completed_at = ?, error_message = ?
                WHERE id = ?
                """,
                (VideoJobStatus.FAILED, now_iso, error_message, job_id),
            )
            conn.commit()
            logger.warning(f"Video job #{job_id} marked [FAILED]: {error_message}")

    def retry_job(self, job_id: int) -> bool:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return False
            vpath = row["video_path"]
            if not os.path.exists(vpath) or os.path.getsize(vpath) == 0:
                logger.error(f"Cannot retry job #{job_id}: video file {vpath} does not exist or is empty.")
                return False

            conn.execute(
                """
                UPDATE video_jobs
                SET status = ?, error_message = NULL, retry_count = retry_count + 1
                WHERE id = ?
                """,
                (VideoJobStatus.QUEUED, job_id),
            )
            conn.commit()
            logger.info(f"Video job #{job_id} queued for retry (Retry #{row['retry_count'] + 1})")
            return True

    def recover_interrupted_jobs(self) -> int:
        """Startup recovery: recovers pending jobs after unclean shutdowns."""
        recovered = 0
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM video_jobs
                WHERE status IN (?, ?, ?)
                """,
                (VideoJobStatus.RECORDING, VideoJobStatus.PROCESSING, VideoJobStatus.VERIFYING),
            )
            rows = cursor.fetchall()
            for r in rows:
                jid = r["id"]
                vpath = r["video_path"]
                if os.path.exists(vpath) and os.path.getsize(vpath) > 1024:
                    conn.execute(
                        "UPDATE video_jobs SET status = ?, error_message = 'Recovered after application restart' WHERE id = ?",
                        (VideoJobStatus.QUEUED, jid),
                    )
                    recovered += 1
                    logger.info(f"Recovered interrupted video job #{jid} -> marked QUEUED for processing.")
                else:
                    conn.execute(
                        "UPDATE video_jobs SET status = ?, error_message = 'Interrupted recording; file missing or zero bytes' WHERE id = ?",
                        (VideoJobStatus.FAILED, jid),
                    )
            conn.commit()
        return recovered

    def get_queue_stats(self) -> Dict[str, int]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT status, COUNT(*) as cnt
                FROM video_jobs
                GROUP BY status
                """
            )
            counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
            return {
                "queued": counts.get(VideoJobStatus.QUEUED, 0),
                "processing": counts.get(VideoJobStatus.PROCESSING, 0) + counts.get(VideoJobStatus.VERIFYING, 0),
                "completed": counts.get(VideoJobStatus.COMPLETED, 0),
                "failed": counts.get(VideoJobStatus.FAILED, 0),
                "recording": counts.get(VideoJobStatus.RECORDING, 0),
                "total": sum(counts.values()),
            }

    def list_jobs(self, event_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if event_id is not None:
                cursor.execute(
                    "SELECT * FROM video_jobs WHERE event_id = ? ORDER BY id DESC LIMIT ?",
                    (event_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM video_jobs ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [dict(r) for r in cursor.fetchall()]

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class VideoRecorder:
    """Manages motion-triggered video writing, inactivity timers, and segment rollovers."""

    def __init__(self, job_store: VideoJobStore) -> None:
        self.job_store = job_store
        self._lock = threading.RLock()

        self.is_recording = False
        self.is_finalizing: bool = False
        self.active_job_id: Optional[int] = None
        self.active_video_path: Optional[str] = None
        self.active_event_id: Optional[int] = None
        self.segment_index: int = 1

        self.segment_start_time: float = 0.0
        self.last_motion_time: float = 0.0
        self.last_closed_time: float = 0.0
        self.last_error: Optional[str] = None
        self.frame_count: int = 0
        self._writer: Optional[cv2.VideoWriter] = None

        self._frame_size: Tuple[int, int] = (0, 0)
        self._last_frame_write_time: float = 0.0

        # Ensure temp storage directory exists
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> Path:
        cfg = app_config.video_recording
        p = Path(cfg.get("temp_storage_dir", "storage/temp_recordings"))
        p.mkdir(parents=True, exist_ok=True)
        return p

    def update_event_id(self, event_id: int) -> None:
        """Attach or update the incident session ID for the active recording segment."""
        with self._lock:
            self.active_event_id = event_id
            if self.active_job_id:
                try:
                    with self.job_store._lock, self.job_store._get_connection() as conn:
                        conn.execute("UPDATE video_jobs SET event_id = ? WHERE id = ?", (event_id, self.active_job_id))
                        conn.commit()
                except Exception as e:
                    logger.warning(f"Failed to update event_id on active video job: {e}")

    def on_frame(self, frame: np.ndarray, has_motion: bool, event_id: Optional[int] = None) -> None:
        """Called on every processed frame in the pipeline loop."""
        cfg = app_config.video_recording
        if not cfg.get("enabled", True):
            if self.is_recording:
                self.close_recording(reason="disabled")
            return

        now = time.time()
        inactivity_timeout = float(cfg.get("inactivity_timeout_sec", 15.0))
        max_duration = float(cfg.get("max_segment_duration_sec", 60.0))
        rec_fps = float(cfg.get("recording_fps", 10.0))
        frame_interval = 1.0 / max(1.0, rec_fps)

        with self._lock:
            if event_id is not None and self.active_event_id is None:
                self.active_event_id = event_id

            if has_motion:
                self.last_motion_time = now
                if not self.is_recording:
                    # 1. Qualifying motion detected -> START RECORDING IMMEDIATELY
                    self._start_segment(frame, event_id=event_id, segment_index=self.segment_index)
                else:
                    # 2. Check if maximum segment duration reached while motion continues (default 60s)
                    duration = now - self.segment_start_time
                    if duration >= max_duration:
                        logger.info(
                            f"Segment #{self.segment_index} duration reached {duration:.1f}s (max {max_duration:.1f}s). "
                            "Rolling over smoothly to next segment under same session."
                        )
                        prev_seg = self.segment_index
                        self.is_finalizing = True
                        self._close_segment(reason="max_duration_rotation")
                        self.is_finalizing = False
                        self.segment_index = prev_seg + 1
                        self._start_segment(frame, event_id=self.active_event_id, segment_index=self.segment_index)
                        broadcaster.broadcast_sync(
                            "segment_rotated",
                            {
                                "previous_segment": prev_seg,
                                "new_segment": self.segment_index,
                                "event_id": self.active_event_id,
                                "reason": "max_duration_rotation",
                                "timestamp": datetime.now().astimezone().isoformat(),
                            },
                        )

                # Write frame to active writer respecting target recording FPS
                if self.is_recording and self._writer is not None:
                    if now - self._last_frame_write_time >= (frame_interval * 0.85):
                        self._writer.write(frame)
                        self.frame_count += 1
                        self._last_frame_write_time = now

            else:
                # No motion detected in this frame
                if self.is_recording:
                    inactivity_elapsed = now - self.last_motion_time
                    if inactivity_elapsed >= inactivity_timeout:
                        # 3. Inactivity timeout expired (15s stillness) -> CLOSE RECORDING
                        logger.info(
                            f"No motion detected for {inactivity_elapsed:.1f}s (timeout: {inactivity_timeout}s). Closing video recording."
                        )
                        self.close_recording(reason="inactivity_timeout")
                    else:
                        # Continue writing frames during 15s countdown to preserve context
                        if self._writer is not None and (now - self._last_frame_write_time >= (frame_interval * 0.85)):
                            self._writer.write(frame)
                            self.frame_count += 1
                            self._last_frame_write_time = now

    def _start_segment(self, initial_frame: np.ndarray, event_id: Optional[int], segment_index: int) -> None:
        h, w = initial_frame.shape[:2]
        self._frame_size = (w, h)
        cfg = app_config.video_recording
        rec_fps = float(cfg.get("recording_fps", 10.0))
        temp_dir = self._ensure_storage_dir()

        ts_str = time.strftime("%Y%m%d_%H%M%S")
        millis = int((time.time() % 1) * 1000)
        filename = f"rec_{ts_str}_{millis:03d}_seg{segment_index}.mp4"
        filepath = str(temp_dir / filename)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(filepath, fourcc, rec_fps, (w, h))

        if not writer.isOpened():
            logger.error(f"Failed to open VideoWriter for {filepath}")
            self.is_recording = False
            self._writer = None
            self.last_error = f"Failed to open VideoWriter for {filepath}"
            return

        self._writer = writer
        self.is_recording = True
        self.is_finalizing = False
        self.active_video_path = filepath
        self.active_event_id = event_id
        self.segment_index = segment_index
        self.segment_start_time = time.time()
        self.last_motion_time = self.segment_start_time
        self.frame_count = 1
        self._last_frame_write_time = self.segment_start_time

        # Write first frame
        self._writer.write(initial_frame)

        # Create persistent database entry
        self.active_job_id = self.job_store.create_job(
            video_path=filepath,
            event_id=event_id,
            segment_index=segment_index,
            fps=rec_fps,
            width=w,
            height=h,
        )

        broadcaster.broadcast_sync(
            "recording_started",
            {
                "job_id": self.active_job_id,
                "event_id": self.active_event_id,
                "segment_index": self.segment_index,
                "video_path": filepath,
                "timestamp": datetime.now().astimezone().isoformat(),
            },
        )

    def _close_segment(self, reason: str = "inactivity_timeout") -> Optional[int]:
        if not self.is_recording or self._writer is None:
            return None

        job_id = self.active_job_id
        vpath = self.active_video_path
        self._writer.release()
        self._writer = None

        duration = max(0.1, time.time() - self.segment_start_time)
        frames = self.frame_count
        file_size = os.path.getsize(vpath) if vpath and os.path.exists(vpath) else 0

        logger.info(f"Video segment closed ({reason}): {vpath} (Duration: {duration:.1f}s, Frames: {frames}, Size: {file_size}B)")

        if job_id and file_size > 1024 and frames >= 2:
            self.job_store.mark_queued(job_id, duration_sec=duration, frame_count=frames)
            broadcaster.broadcast_sync(
                "video_job_queued",
                {
                    "job_id": job_id,
                    "event_id": self.active_event_id,
                    "segment_index": self.segment_index,
                    "duration_sec": round(duration, 1),
                    "frame_count": frames,
                    "reason": reason,
                },
            )
        elif job_id:
            self.job_store.mark_failed(job_id, f"Incomplete recording: {frames} frames, {file_size} bytes")

        return job_id

    def close_recording(self, reason: str = "inactivity_timeout") -> None:
        """Cleanly close the active recording and reset session segment indices."""
        with self._lock:
            if not self.is_recording:
                return
            self.is_finalizing = True
            closed_job_id = self._close_segment(reason=reason)
            self.is_finalizing = False
            self.is_recording = False
            self.active_job_id = None
            self.active_video_path = None
            self.active_event_id = None
            self.segment_index = 1
            self.frame_count = 0
            self.last_closed_time = time.time()

            broadcaster.broadcast_sync(
                "recording_stopped",
                {
                    "closed_job_id": closed_job_id,
                    "reason": reason,
                    "timestamp": datetime.now().astimezone().isoformat(),
                },
            )

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            cur_duration = 0.0
            inactivity_remaining = 0.0
            inact_timeout = float(app_config.video_recording.get("inactivity_timeout_sec", 15.0))
            max_duration = float(app_config.video_recording.get("max_segment_duration_sec", 60.0))

            if self.is_recording:
                cur_duration = max(0.0, now - self.segment_start_time)
                inactivity_remaining = max(0.0, inact_timeout - (now - self.last_motion_time))

            queue_stats = self.job_store.get_queue_stats()
            worker_stat = video_processor.get_status()
            worker_phase = worker_stat.get("worker_phase", "IDLE")

            # Determine one of 8 distinct states:
            # IDLE, RECORDING, FINALIZING, QUEUED, PROCESSING, VERIFYING, COMPLETED, FAILED
            if self.is_finalizing:
                overall_state = "FINALIZING"
            elif self.is_recording:
                overall_state = "RECORDING"
            elif worker_phase == "VERIFYING":
                overall_state = "VERIFYING"
            elif worker_phase == "PROCESSING":
                overall_state = "PROCESSING"
            elif queue_stats.get("queued", 0) > 0:
                overall_state = "QUEUED"
            elif worker_stat.get("last_failed_time") and (now - worker_stat["last_failed_time"] < 12.0):
                overall_state = "FAILED"
            elif worker_stat.get("last_completed_time") and (now - worker_stat["last_completed_time"] < 12.0):
                overall_state = "COMPLETED"
            else:
                overall_state = "IDLE"

            return {
                "overall_state": overall_state,
                "is_recording": self.is_recording,
                "is_finalizing": self.is_finalizing,
                "current_job_id": self.active_job_id,
                "current_event_id": self.active_event_id,
                "segment_index": self.segment_index,
                "recording_duration_sec": round(cur_duration, 1),
                "inactivity_remaining_sec": round(inactivity_remaining, 1),
                "inactivity_timeout_sec": inact_timeout,
                "max_segment_duration_sec": max_duration,
                "frame_count": self.frame_count,
                "last_closed_time": self.last_closed_time if self.last_closed_time > 0 else None,
                "queue": queue_stats,
                "worker": worker_stat,
            }


class VideoProcessorWorker:
    """Asynchronous background worker that processes queued videos, extracts frames,
    runs AI classification, verifies images on disk, and safely deletes temporary videos.
    """

    def __init__(self, job_store: VideoJobStore) -> None:
        self.job_store = job_store
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.current_processing_job: Optional[Dict[str, Any]] = None
        # Isolated detector instance with dedicated C++ DNN buffers to prevent thread collisions
        self.detector = create_detector()
        self.worker_phase: str = "IDLE"
        self.last_completed_job_id: Optional[int] = None
        self.last_completed_time: Optional[float] = None
        self.last_failed_job_id: Optional[int] = None
        self.last_failed_error: Optional[str] = None
        self.last_failed_time: Optional[float] = None

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            # Recover interrupted jobs from previous application runs
            recovered = self.job_store.recover_interrupted_jobs()
            if recovered > 0:
                logger.info(f"Startup recovery: Resumed {recovered} interrupted video jobs.")

            self._thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="VideoProcessorWorker",
            )
            self._thread.start()
            logger.info("VideoProcessorWorker thread started.")

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            logger.info("VideoProcessorWorker thread stopped.")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "worker_phase": self.worker_phase,
                "is_running": self._running,
                "current_job_id": self.current_processing_job.get("id") if self.current_processing_job else None,
                "last_completed_job_id": self.last_completed_job_id,
                "last_completed_time": self.last_completed_time,
                "last_failed_job_id": self.last_failed_job_id,
                "last_failed_error": self.last_failed_error,
                "last_failed_time": self.last_failed_time,
            }

    def _worker_loop(self) -> None:
        while self._running:
            try:
                job = self.job_store.get_next_queued_job()
                if not job:
                    if self.worker_phase not in ("COMPLETED", "FAILED"):
                        self.worker_phase = "IDLE"
                    time.sleep(1.0)
                    continue

                self.current_processing_job = job
                self.worker_phase = "PROCESSING"
                try:
                    self._process_single_job(job)
                    self.last_completed_job_id = job["id"]
                    self.last_completed_time = time.time()
                    self.worker_phase = "COMPLETED"
                except Exception as je:
                    logger.error(f"Error processing video job #{job['id']}: {je}", exc_info=True)
                    self.job_store.mark_failed(job["id"], str(je))
                    self.last_failed_job_id = job["id"]
                    self.last_failed_error = str(je)
                    self.last_failed_time = time.time()
                    self.worker_phase = "FAILED"
                    broadcaster.broadcast_sync("video_job_failed", {"job_id": job["id"], "error": str(je)})
                finally:
                    self.current_processing_job = None
            except Exception as e:
                logger.error(f"Unexpected exception in video worker loop: {e}", exc_info=True)
                time.sleep(1.0)

    def _process_single_job(self, job: Dict[str, Any]) -> None:
        job_id = job["id"]
        vpath = job["video_path"]
        event_id = job.get("event_id")
        segment_index = job.get("segment_index", 1)

        logger.info(f"Starting background processing for video job #{job_id}: {vpath}")
        self.worker_phase = "PROCESSING"
        self.job_store.mark_processing(job_id)
        broadcaster.broadcast_sync("video_job_processing", {"job_id": job_id, "event_id": event_id})

        if not os.path.exists(vpath):
            self.job_store.mark_failed(job_id, f"Video file not found: {vpath}")
            return

        cap = cv2.VideoCapture(vpath)
        if not cap.isOpened():
            self.job_store.mark_failed(job_id, f"Failed to open video file: {vpath}")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
        if total_frames <= 0:
            cap.release()
            self.job_store.mark_failed(job_id, "Video contains 0 frames.")
            return

        cfg = app_config.video_recording
        max_extracts = int(cfg.get("max_extracted_frames", 6))
        min_sharpness = float(cfg.get("min_sharpness", 35.0))

        # 1. First pass: sample candidate frames across the video and score quality
        # Step interval: sample approximately 1 frame every 0.5 - 1.0 second
        step = max(1, int(video_fps * 0.5))
        candidates: List[Dict[str, Any]] = []

        frame_idx = 0
        while cap.isOpened() and self._running:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Compute Laplacian variance for motion blur / sharpness
                sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                mean_lux = float(np.mean(gray))

                # Discard completely blown-out or pitch-black frames
                if 12.0 < mean_lux < 248.0:
                    candidates.append({
                        "frame_idx": frame_idx,
                        "frame": frame.copy(),
                        "sharpness": sharpness,
                        "mean_lux": mean_lux,
                        "time_offset_sec": frame_idx / video_fps,
                    })

            frame_idx += 1
            # Cooperative yield for CPU protection on low-powered machines
            if frame_idx % 20 == 0:
                time.sleep(0.01)

        cap.release()

        if not candidates:
            self.job_store.mark_failed(job_id, "No suitable frames found with acceptable visibility.")
            return

        # 2. Select top representative frames temporally distributed across the segment
        # Sort candidates by sharpness
        candidates.sort(key=lambda c: c["sharpness"], reverse=True)

        selected_candidates: List[Dict[str, Any]] = []
        min_time_distance_sec = max(0.8, (total_frames / video_fps) / max_extracts)

        for cand in candidates:
            # Check temporal diversity: ensure selected frames are spaced apart
            too_close = any(abs(cand["time_offset_sec"] - sc["time_offset_sec"]) < min_time_distance_sec for sc in selected_candidates)
            if not too_close or len(selected_candidates) < 2:
                selected_candidates.append(cand)
            if len(selected_candidates) >= max_extracts:
                break

        # Re-sort chronologically
        selected_candidates.sort(key=lambda c: c["time_offset_sec"])

        # 3. AI Detection & Image Extraction
        try:
            job_start_dt = datetime.fromisoformat(job["created_at"])
        except Exception:
            job_start_dt = datetime.now().astimezone()

        extracted_images_metadata: List[Dict[str, Any]] = []
        created_file_paths: List[str] = []

        highest_prio_cat = None
        highest_prio_label = None
        highest_prio_conf = 0.0

        for idx, cand in enumerate(selected_candidates, 1):
            frame = cand["frame"]
            frame_offset = cand["time_offset_sec"]
            frame_dt = job_start_dt + timedelta(seconds=frame_offset)
            frame_ts_iso = frame_dt.isoformat()
            sharpness_val = cand["sharpness"]

            # Run isolated YOLOv8 object detector
            detections = self.detector.detect(frame)
            primary_cat = "General motion"
            primary_label = f"Video Frame #{cand['frame_idx']} (+{frame_offset:.1f}s)"
            primary_conf = 0.50

            if detections:
                detections.sort(key=lambda d: d.get("confidence", 0.0), reverse=True)
                top_det = detections[0]
                primary_cat = top_det["category"]
                primary_label = f"{top_det['label']} (+{frame_offset:.1f}s)"
                primary_conf = top_det["confidence"]

                # Track highest priority entity to escalate event category if applicable
                from wheat_watch.pipeline import CATEGORY_PRIORITY
                if CATEGORY_PRIORITY.get(primary_cat, 0) > CATEGORY_PRIORITY.get(highest_prio_cat or "", 0):
                    highest_prio_cat = primary_cat
                    highest_prio_label = top_det["label"]
                    highest_prio_conf = primary_conf

            # Annotate candidate frame using isolated detector
            header = f"SEG #{segment_index} | {primary_label} | Sharpness: {sharpness_val:.0f}"
            annotated = self.detector.annotate_frame(frame, detections=detections, header_text=header)

            # Save frame to disk with 'video_extract' tag
            saved_path = storage_manager.save_event_image(
                annotated,
                category=primary_cat,
                tag=f"extract_seg{segment_index}_f{idx}",
            )
            created_file_paths.append(saved_path)

            extracted_images_metadata.append({
                "path": saved_path,
                "tag": "video_extract",
                "segment_index": segment_index,
                "frame_index": cand["frame_idx"],
                "time_offset_sec": round(frame_offset, 2),
                "timestamp": frame_ts_iso,
                "label": primary_label,
                "category": primary_cat,
                "confidence": round(primary_conf, 3),
                "sharpness": round(sharpness_val, 1),
                "detections": detections,
            })

            # Small yield to prevent CPU spikes
            time.sleep(0.04)

        # 4. Verification Phase (VERIFYING)
        # CRITICAL SAFETY RULE: Never delete video before verifying extracted images exist & are readable
        self.worker_phase = "VERIFYING"
        self.job_store.mark_verifying(job_id, len(created_file_paths))
        broadcaster.broadcast_sync("video_job_verifying", {"job_id": job_id, "extracted_count": len(created_file_paths)})

        verification_passed = True
        failed_reason = ""

        if not created_file_paths:
            verification_passed = False
            failed_reason = "Zero extracted images generated."
        else:
            for p in created_file_paths:
                if not os.path.exists(p):
                    verification_passed = False
                    failed_reason = f"Extracted image missing: {p}"
                    break
                sz = os.path.getsize(p)
                if sz < 1024:
                    verification_passed = False
                    failed_reason = f"Extracted image corrupt/empty ({sz} bytes): {p}"
                    break
                # Validate image header can be parsed
                test_img = cv2.imread(p)
                if test_img is None or test_img.shape[0] == 0 or test_img.shape[1] == 0:
                    verification_passed = False
                    failed_reason = f"Extracted image unreadable by OpenCV: {p}"
                    break

        if not verification_passed:
            logger.error(f"Verification FAILED for video job #{job_id}: {failed_reason}. Retaining original video {vpath}.")
            self.job_store.mark_failed(job_id, f"Verification failed: {failed_reason}")
            broadcaster.broadcast_sync("video_job_failed", {"job_id": job_id, "error": failed_reason})
            return

        # 5. Verification PASSED -> Link extracted images to Event Session in SQLite
        if event_id:
            try:
                self._attach_extracts_to_event(
                    event_id=event_id,
                    job_id=job_id,
                    segment_index=segment_index,
                    extracted_images=extracted_images_metadata,
                    escalate_category=highest_prio_cat,
                    escalate_label=highest_prio_label,
                    escalate_conf=highest_prio_conf,
                )
            except Exception as e:
                logger.error(f"Failed attaching video extracts to Event #{event_id}: {e}")

        # 6. Safely Delete Temporary Source Video
        try:
            if os.path.exists(vpath):
                os.remove(vpath)
                logger.info(f"Verified successfully. Temporary source video DELETED: {vpath}")
        except Exception as e:
            logger.warning(f"Failed deleting temporary video {vpath}: {e}")

        self.job_store.mark_completed(job_id)
        broadcaster.broadcast_sync(
            "video_job_completed",
            {
                "job_id": job_id,
                "event_id": event_id,
                "segment_index": segment_index,
                "extracted_count": len(created_file_paths),
                "extracted_images": extracted_images_metadata,
            },
        )
        logger.info(f"Video job #{job_id} COMPLETED successfully. {len(created_file_paths)} representative frames extracted.")

    def _attach_extracts_to_event(
        self,
        event_id: int,
        job_id: int,
        segment_index: int,
        extracted_images: List[Dict[str, Any]],
        escalate_category: Optional[str] = None,
        escalate_label: Optional[str] = None,
        escalate_conf: Optional[float] = None,
    ) -> None:
        """Appends extracted video frames to event details without overwriting existing initial/final images."""
        with event_store._lock, event_store._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return

            try:
                details = json.loads(row["details"]) if row["details"] else {}
            except Exception:
                details = {}

            existing_images = details.get("images", [])
            existing_tags = details.get("tags", [])
            video_segments = details.get("video_segments", [])

            # Record video segment metadata
            segment_record = {
                "segment_index": segment_index,
                "job_id": job_id,
                "status": "completed",
                "extracted_count": len(extracted_images),
                "processed_at": datetime.now().astimezone().isoformat(),
            }
            # Replace or append segment record
            video_segments = [s for s in video_segments if s.get("segment_index") != segment_index]
            video_segments.append(segment_record)

            # Append extracted images to gallery alongside initial and final images
            for ext in extracted_images:
                existing_images.append(ext)
                if "video_extract" not in existing_tags:
                    existing_tags.append("video_extract")

            details["images"] = existing_images
            details["tags"] = existing_tags
            details["video_segments"] = video_segments
            details["video_processing_status"] = "completed"

            # Check for category escalation from video analysis
            final_cat = row["category"]
            final_label = row["label"]
            final_conf = row["confidence"]

            if escalate_category:
                from wheat_watch.pipeline import CATEGORY_PRIORITY
                if CATEGORY_PRIORITY.get(escalate_category, 0) > CATEGORY_PRIORITY.get(row["category"], 0):
                    final_cat = escalate_category
                    final_label = escalate_label or row["label"]
                    final_conf = escalate_conf or row["confidence"]
                    logger.info(f"Event #{event_id} ESCALATED from video analysis: [{row['category']}] -> [{final_cat}] {final_label}")

            conn.execute(
                """
                UPDATE events
                SET category = ?, label = ?, confidence = ?, details = ?
                WHERE id = ?
                """,
                (final_cat, final_label, final_conf, json.dumps(details), event_id),
            )
            conn.commit()


# Global singletons
video_job_store = VideoJobStore()
video_recorder = VideoRecorder(video_job_store)
video_processor = VideoProcessorWorker(video_job_store)
