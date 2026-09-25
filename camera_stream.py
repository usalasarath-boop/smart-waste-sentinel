"""
Camera Stream Manager (Raspberry Pi Camera Module 3 & OpenCV Fallback)
=====================================================================
Multi-threaded video capture service providing continuous, low-latency frame
delivery for Edge AI inference and real-time MJPEG web streaming.

Hardware Integration:
- Raspberry Pi Camera Module 3 (Sony IMX708 sensor with Phase Detection Auto Focus - PDAF).
- Interfaces over MIPI CSI-2 bus directly to the BCM2712 VideoCore VII ISP on Raspberry Pi 5.
- Uses `picamera2` (official libcamera binding) on Raspberry Pi OS Bookworm.
- Automatically falls back to OpenCV VideoCapture (V4L2 or USB webcam) or synthetic test feed
  if hardware is not physically plugged in.
"""

import time
import logging
import threading
import cv2
import numpy as np

logger = logging.getLogger("SmartWasteSentinel.Camera")

class CameraStream:
    """Threaded camera capture stream with automatic backend selection."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30, backend: str = "auto", device_index: int = 0):
        self.width = width
        self.height = height
        self.fps = fps
        self.backend_choice = backend
        self.device_index = device_index

        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.current_frame = None
        self.backend_used = "none"

        # Internal backend handles
        self.picam2 = None
        self.cap = None

        self._initialize_camera()

    def _initialize_camera(self):
        """Initializes the best available camera backend."""
        # Try Picamera2 first (Native RPi 5 / Camera Module 3)
        if self.backend_choice in ("auto", "picam3"):
            try:
                from picamera2 import Picamera2
                self.picam2 = Picamera2()
                config = self.picam2.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "RGB888"},
                    controls={"FrameRate": self.fps}
                )
                self.picam2.configure(config)
                self.picam2.start()
                self.backend_used = "picamera2"
                logger.info("Initialized Picamera2 (RPi Camera Module 3) at %dx%d @ %d FPS", self.width, self.height, self.fps)
                return
            except Exception as e:
                logger.warning("Picamera2 initialization failed (%s). Attempting OpenCV fallback...", e)
                self.picam2 = None

        # Fallback to OpenCV VideoCapture (USB / V4L2)
        if self.backend_choice in ("auto", "opencv"):
            try:
                self.cap = cv2.VideoCapture(self.device_index)
                if self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                    self.backend_used = "opencv"
                    logger.info("Initialized OpenCV VideoCapture(index=%d) at %dx%d", self.device_index, self.width, self.height)
                    return
                else:
                    logger.warning("OpenCV VideoCapture failed to open device index %d.", self.device_index)
                    self.cap = None
            except Exception as e:
                logger.warning("OpenCV camera initialization error: %s", e)
                self.cap = None

        # Fallback to Synthetic Demo Video Generator
        self.backend_used = "synthetic"
        logger.warning("No physical camera detected. Operating in SYNTHETIC CAMERA MODE (Safe for development & bench testing).")

    def start(self):
        """Starts the dedicated background frame grabbing thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, name="CameraCaptureThread", daemon=True)
        self.thread.start()
        logger.info("Camera capture loop started.")

    def _capture_loop(self):
        """Continuously pulls frames into the shared buffer."""
        frame_interval = 1.0 / max(1, self.fps)
        sim_step = 0

        while self.running:
            loop_start = time.time()
            frame = None

            try:
                if self.backend_used == "picamera2" and self.picam2 is not None:
                    # Picamera2 returns RGB numpy array; convert to BGR for OpenCV consistency
                    rgb_frame = self.picam2.capture_array()
                    frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

                elif self.backend_used == "opencv" and self.cap is not None:
                    ret, raw_frame = self.cap.read()
                    if ret and raw_frame is not None:
                        frame = raw_frame
                    else:
                        logger.warning("Failed to grab frame from OpenCV source.")

                elif self.backend_used == "synthetic":
                    # Generate an active benchmark test pattern with moving elements
                    frame = self._generate_synthetic_frame(sim_step)
                    sim_step += 1

            except Exception as e:
                logger.error("Exception during camera frame acquisition: %s", e)

            if frame is not None:
                with self.lock:
                    self.current_frame = frame

            # Regulate frame rate
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)

    def _generate_synthetic_frame(self, step: int) -> np.ndarray:
        """Generates dynamic test frame showing illegal dumping with person carrying garbage bags."""
        import os
        from pathlib import Path
        ref_path = Path(__file__).resolve().parent.parent / "images" / "incidents" / "INC-VERIFIED-DUMPING-01.jpg"

        if ref_path.exists():
            base_img = cv2.imread(str(ref_path))
            if base_img is not None:
                img = cv2.resize(base_img, (self.width, self.height))
            else:
                img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        else:
            img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            img[:int(self.height * 0.4), :] = [60, 50, 45]
            img[int(self.height * 0.4):, :] = [35, 35, 35]

        # Timestamp & Overlay
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"SENTINEL CAM-01 [ACTIVE SENTRY] - {timestamp_str}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(img, "ZONE: PROHIBITED DUMPING PERIMETER", (15, self.height - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (240, 240, 240), 1)
        return img

    def get_frame(self) -> np.ndarray:
        """Returns the most recent captured frame (BGR format) or None."""
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def get_jpeg(self, quality: int = 75) -> bytes:
        """Encodes the latest frame as JPEG bytes for web streaming."""
        frame = self.get_frame()
        if frame is None:
            # Fallback blank frame
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            cv2.putText(frame, "INITIALIZING CAMERA FEED...", (40, self.height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if ret:
            return buffer.tobytes()
        return b""

    def stop(self):
        """Stops capture loop and safely releases camera hardware."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        logger.info("Camera stream stopped.")
