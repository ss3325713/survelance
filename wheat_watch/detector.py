"""Object detection and classification engine for Wheat Watch.

Runs YOLOv8n ONNX via OpenCV DNN. Strictly adheres to:
1. Person detection without facial recognition or identity tracking.
2. Bird detection.
3. Animal classification: ordinary COCO models do NOT claim monkey identification.
   Shows 'Animal detected — species unconfirmed' unless a verified monkey model is installed.
4. General motion and unknown objects.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from wheat_watch.config import app_config

logger = logging.getLogger("wheat_watch.detector")

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

ANIMAL_CLASSES = {
    "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"
}

CATEGORY_COLORS = {
    "Person": (0, 140, 255),                                  # Orange / Red-Orange
    "Bird": (255, 215, 0),                                    # Cyan / Gold
    "Animal detected — species unconfirmed": (0, 215, 255),    # Yellow / Amber
    "Other recognized animal": (0, 200, 200),                 # Warm Amber
    "Possible monkey": (50, 50, 235),                         # Red Alert
    "General motion": (50, 205, 50),                          # Green
    "Unknown object": (180, 105, 255),                        # Violet / Pink
}


class ObjectDetector:
    """YOLOv8n object detector with verified classification categories."""

    def __init__(self, model_path: str = "models/yolov8n.onnx") -> None:
        self.model_path = Path(model_path)
        self.net: Optional[cv2.dnn.Net] = None
        self.monkey_net: Optional[cv2.dnn.Net] = None
        self.is_monkey_model_installed = False
        self._load_models()

    def _load_models(self) -> None:
        if not self.model_path.exists():
            logger.error(f"YOLO model not found at {self.model_path}")
            return

        try:
            logger.info(f"Loading YOLOv8 ONNX model from {self.model_path}...")
            self.net = cv2.dnn.readNetFromONNX(str(self.model_path))
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            logger.info("YOLOv8 ONNX model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.net = None

        # Check for optional verified monkey model
        monkey_path = Path(app_config.pipeline.get("monkey_model_path", "models/monkey_classifier.onnx"))
        if monkey_path.exists():
            try:
                self.monkey_net = cv2.dnn.readNetFromONNX(str(monkey_path))
                self.is_monkey_model_installed = True
                logger.info("Verified monkey classifier model loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load monkey model: {e}")
                self.is_monkey_model_installed = False
        else:
            self.is_monkey_model_installed = False
            logger.info(
                "No monkey model installed. Policy enforced: Ordinary COCO model cannot identify monkeys. "
                "Animal detections will report as 'Animal detected — species unconfirmed'."
            )

    def get_monkey_status(self) -> Dict[str, Any]:
        return {
            "installed": self.is_monkey_model_installed,
            "policy": (
                "Verified monkey model active."
                if self.is_monkey_model_installed
                else "Ordinary COCO model cannot identify monkeys. Animal detections report as 'Animal detected — species unconfirmed'."
            ),
        }

    def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Run object detection on the frame."""
        if self.net is None:
            return []

        if confidence_threshold is None:
            confidence_threshold = app_config.pipeline.get("detection_confidence", 0.40)

        h, w = frame.shape[:2]

        # Prepare 640x640 letterbox or resize
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (640, 640)),
            1.0 / 255.0,
            (640, 640),
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        preds = self.net.forward()[0]  # shape (84, 8400)

        boxes = []
        confidences = []
        class_ids = []

        # YOLOv8 output: rows 0..3 are normalized center-x, center-y, width, height
        # rows 4..83 are class scores
        scores_matrix = preds[4:, :]
        max_scores = np.max(scores_matrix, axis=0)
        best_classes = np.argmax(scores_matrix, axis=0)

        candidate_cols = np.where(max_scores >= confidence_threshold)[0]

        for col in candidate_cols:
            conf = float(max_scores[col])
            cid = int(best_classes[col])
            xc, yc, bw, bh = preds[:4, col]

            x1 = int((xc - bw / 2.0) * w)
            y1 = int((yc - bh / 2.0) * h)
            width = int(bw * w)
            height = int(bh * h)

            # Clamp coordinates
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            width = max(1, min(w - x1, width))
            height = max(1, min(h - y1, height))

            boxes.append([x1, y1, width, height])
            confidences.append(conf)
            class_ids.append(cid)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, 0.45)
        if len(indices) == 0:
            return []

        results = []
        for idx in indices:
            i = int(idx)
            cid = class_ids[i]
            conf = confidences[i]
            x, y, bw, bh = boxes[i]
            raw_class = COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else "unknown"

            # Determine category per specifications
            category, label = self._classify_detection(raw_class, conf, frame[y:y+bh, x:x+bw])

            results.append(
                {
                    "category": category,
                    "label": label,
                    "confidence": round(conf, 3),
                    "raw_class": raw_class,
                    "box": [x, y, x + bw, y + bh],  # [x1, y1, x2, y2]
                }
            )

        return results

    def _classify_detection(
        self,
        raw_class: str,
        conf: float,
        crop: np.ndarray,
    ) -> Tuple[str, str]:
        """Classify into one of the required distinct categories."""
        # 1. Person: Strictly no facial recognition or person identification
        if raw_class == "person":
            return "Person", f"Person ({conf*100:.0f}%)"

        # 2. Bird
        if raw_class == "bird":
            return "Bird", f"Bird ({conf*100:.0f}%)"

        # 3. Animal
        if raw_class in ANIMAL_CLASSES:
            if self.is_monkey_model_installed and self.monkey_net and crop.size > 0:
                is_monkey, monkey_conf = self._evaluate_monkey_crop(crop)
                if is_monkey:
                    return "Possible monkey", f"Possible monkey ({monkey_conf*100:.0f}%)"
                return "Other recognized animal", f"{raw_class.capitalize()} ({conf*100:.0f}%)"
            else:
                # Per architecture requirements:
                # "Until such a model is installed, show 'Animal detected — species unconfirmed' rather than guessing."
                return "Animal detected — species unconfirmed", f"Animal detected — species unconfirmed ({conf*100:.0f}%)"

        # 4. Unknown Object
        return "Unknown object", f"{raw_class.capitalize()} ({conf*100:.0f}%)"

    def _evaluate_monkey_crop(self, crop: np.ndarray) -> Tuple[bool, float]:
        """Evaluate crop using the verified monkey model if installed."""
        try:
            blob = cv2.dnn.blobFromImage(cv2.resize(crop, (224, 224)), 1.0 / 255.0, (224, 224), swapRB=True)
            self.monkey_net.setInput(blob)
            out = self.monkey_net.forward()
            score = float(np.max(out))
            if score > 0.65:
                return True, score
        except Exception as e:
            logger.debug(f"Monkey classifier evaluation error: {e}")
        return False, 0.0

    def annotate_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        motion_boxes: Optional[List[Tuple[int, int, int, int]]] = None,
        header_text: Optional[str] = None,
    ) -> np.ndarray:
        """Draw bounding boxes, badges, and watermark on the frame."""
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Draw motion contours if provided
        if motion_boxes:
            for mx, my, mw, mh in motion_boxes:
                cv2.rectangle(annotated, (mx, my), (mx + mw, my + mh), (100, 255, 100), 1, cv2.LINE_AA)

        # Draw object bounding boxes
        for det in detections:
            cat = det["category"]
            label = det["label"]
            x1, y1, x2, y2 = det["box"]
            color = CATEGORY_COLORS.get(cat, (255, 255, 255))

            # Bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

            # Label badge
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.55
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
            badge_y1 = max(0, y1 - th - 8)
            badge_y2 = y1

            # Background rectangle for text
            cv2.rectangle(annotated, (x1, badge_y1), (x1 + tw + 8, badge_y2), color, -1)
            # Text label
            text_color = (0, 0, 0) if color[0] + color[1] + color[2] > 380 else (255, 255, 255)
            cv2.putText(annotated, label, (x1 + 4, badge_y2 - 4), font, scale, text_color, thickness, cv2.LINE_AA)

        # Draw header watermark
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
        status_line = f"PySURVEILLANCE | {ts_str}"
        if header_text:
            status_line += f" | {header_text}"

        cv2.rectangle(annotated, (0, 0), (w, 28), (20, 20, 20), -1)
        cv2.putText(annotated, status_line, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)

        return annotated


# Global detector instance
detector = ObjectDetector()
