"""
Edge AI Object Detector (YOLOv8 / YOLOv11)
===========================================
Executes local neural network inference on Raspberry Pi 5.

Key Optimizations for RPi 5:
- Utilizes PyTorch 64-bit or ONNX Runtime / NCNN backend.
- BCM2712 Quad-core ARM Cortex-A76 @ 2.4GHz executes YOLOv8n at ~14-22 FPS.
- Filters classes specifically needed for illegal dumping monitoring.
"""

import time
import logging
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np

import config

logger = logging.getLogger("SmartWasteSentinel.Detector")

class EdgeAIDetector:
    """Wrapper around YOLOv8/v11 object detector with local acceleration support."""

    def __init__(self, model_path: str = None, conf: float = None, iou: float = None):
        self.model_path = str(model_path or config.MODEL_PATH)
        self.conf = conf if conf is not None else config.CONFIDENCE_THRESHOLD
        self.iou = iou if iou is not None else config.IOU_THRESHOLD
        self.model = None
        self.is_simulated = False

        self._load_model()

    def _load_model(self):
        """Loads Ultralytics YOLO model or falls back to synthetic detector if package missing."""
        try:
            from ultralytics import YOLO
            logger.info("Loading YOLO model from %s...", self.model_path)
            # YOLO auto-downloads yolov8n.pt if not found locally
            self.model = YOLO(self.model_path)
            self.is_simulated = False
            logger.info("YOLO model successfully loaded on Edge AI engine.")
        except Exception as e:
            logger.warning("Could not load Ultralytics YOLO (%s). Operating in SYNTHETIC AI MODE.", e)
            self.model = None
            self.is_simulated = True

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs object detection on a single frame.

        Args:
            frame: BGR numpy image.

        Returns:
            List of detected objects:
            [
                {
                    "class": "person" | "garbage" | "plastic" | "vehicle",
                    "raw_class": "backpack",
                    "confidence": 0.85,
                    "bbox": [x1, y1, x2, y2],
                    "centroid": (cx, cy),
                    "width": w,
                    "height": h
                },
                ...
            ]
        """
        if frame is None:
            return []

        if self.is_simulated:
            return self._synthetic_detect(frame)

        detections = []
        try:
            # Run inference
            results = self.model(frame, conf=self.conf, iou=self.iou, verbose=False)
            if not results or len(results) == 0:
                return detections

            res = results[0]
            names = res.names  # Class ID to name dictionary

            for box in res.boxes:
                cls_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                raw_name = names.get(cls_id, str(cls_id)).lower()

                # Map class to unified sentinel category
                mapped_category = config.CLASS_MAPPINGS.get(raw_name)
                if not mapped_category:
                    # Ignore unrelated objects (e.g. dogs, chairs, birds)
                    continue

                # Bounding box coords [x1, y1, x2, y2]
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy.tolist()

                # Centroid calculation: center of mass
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                w = int(x2 - x1)
                h = int(y2 - y1)

                detections.append({
                    "class": mapped_category,
                    "raw_class": raw_name,
                    "confidence": round(confidence, 2),
                    "bbox": [x1, y1, x2, y2],
                    "centroid": (cx, cy),
                    "width": w,
                    "height": h
                })

        except Exception as e:
            logger.error("Error during YOLO inference: %s", e)

        return detections

    def _synthetic_detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Simulates dynamic dumping sequence: Person enters carrying bags -> drops bags -> departs."""
        h, w, _ = frame.shape
        # 120-step loop (~60 seconds cycle at 2 FPS processing)
        step = int(time.time() * 2) % 120
        detections = []

        # Stationary Dropped Bags Location (on ground)
        ground_bag_y = int(h * 0.70)
        bag1_x = int(w * 0.42)
        bag2_x = int(w * 0.49)

        if step < 30:
            # PHASE 1: Person walking in carrying bags (Co-located, moving together)
            # Person moves towards center
            person_x = int(w * 0.15 + (step / 30.0) * (w * 0.28))
            person_y = int(h * 0.46)
            pw, ph = int(w * 0.14), int(h * 0.38)

            detections.append({
                "class": "person",
                "raw_class": "person",
                "confidence": 0.94,
                "bbox": [person_x, person_y, person_x + pw, person_y + ph],
                "centroid": (person_x + pw // 2, person_y + ph // 2),
                "width": pw, "height": ph
            })
            # Bags moving with person
            b1_x = person_x - 15
            b1_y = person_y + int(ph * 0.6)
            detections.append({
                "class": "garbage",
                "raw_class": "garbage_bag",
                "confidence": 0.91,
                "bbox": [b1_x, b1_y, b1_x + 35, b1_y + 45],
                "centroid": (b1_x + 17, b1_y + 22),
                "width": 35, "height": 45
            })

        elif step < 75:
            # PHASE 2: Person drops the bags and walks away (Separation & Abandonment occurs!)
            # Bags become stationary on the ground
            detections.append({
                "class": "garbage",
                "raw_class": "garbage_bag",
                "confidence": 0.92,
                "bbox": [bag1_x, ground_bag_y, bag1_x + 40, ground_bag_y + 50],
                "centroid": (bag1_x + 20, ground_bag_y + 25),
                "width": 40, "height": 50
            })
            # Person moves away to the right
            depart_progress = (step - 30) / 45.0
            person_x = int(w * 0.45 + depart_progress * (w * 0.45))
            person_y = int(h * 0.46)
            pw, ph = int(w * 0.14), int(h * 0.38)

            detections.append({
                "class": "person",
                "raw_class": "person",
                "confidence": 0.91,
                "bbox": [person_x, person_y, person_x + pw, person_y + ph],
                "centroid": (person_x + pw // 2, person_y + ph // 2),
                "width": pw, "height": ph
            })

        else:
            # PHASE 3: Person has left the scene entirely. Only dumped stationary bags remain.
            # ZERO new captures occur here because this dumped bag was already captured!
            detections.append({
                "class": "garbage",
                "raw_class": "garbage_bag",
                "confidence": 0.89,
                "bbox": [bag1_x, ground_bag_y, bag1_x + 40, ground_bag_y + 50],
                "centroid": (bag1_x + 20, ground_bag_y + 25),
                "width": 40, "height": 50
            })

        return detections

    def annotate_frame(self, frame: np.ndarray, detections: List[Dict[str, Any]], dumping_active: bool = False) -> np.ndarray:
        """
        Renders bounding boxes, HUD indicators, and status tags on frame.
        """
        annotated = frame.copy()
        
        # Color mapping: (B, G, R)
        colors = {
            "person": (255, 140, 0),        # Cyan-blue
            "vehicle": (255, 200, 0),       # Light blue
            "garbage": (0, 0, 255),         # Bright Red
            "plastic": (0, 165, 255),       # Orange
            "waste_candidate": (0, 100, 255)# Red-orange
        }

        for det in detections:
            cat = det["class"]
            color = colors.get(cat, (0, 255, 0))
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            raw = det["raw_class"]

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw centroid point
            cx, cy = det["centroid"]
            cv2.circle(annotated, (cx, cy), 4, color, -1)

            # Draw label banner
            label = f"{raw.upper()} {int(conf * 100)}%"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(annotated, (x1, max(0, y1 - lh - 6)), (x1 + lw + 6, max(lh + 6, y1)), color, -1)
            cv2.putText(annotated, label, (x1 + 3, max(lh + 2, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Draw Global Alert Watermark if Dumping Event is active
        if dumping_active:
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (annotated.shape[1], 42), (0, 0, 200), -1)
            cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)
            cv2.putText(annotated, "[CRITICAL ALERT] ILLEGAL DUMPING ACTIVITY DETECTED", 
                        (20, 28), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 2)

        return annotated
