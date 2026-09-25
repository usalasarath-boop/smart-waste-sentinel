"""
Smart Waste Sentinel - Configuration Module
===========================================
Central configuration for hardware pins, environmental thresholds,
Edge-AI computer vision pipelines, database settings, and web dashboard.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "sentinel.db"
IMAGES_DIR = BASE_DIR / "images" / "incidents"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "sentinel.log"

# Ensure runtime directories exist
for directory in [DATABASE_DIR, IMAGES_DIR, MODELS_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# 1. HARDWARE GPIO & SENSOR CONFIGURATION (Raspberry Pi 5)
# ==============================================================================
# I2C Bus for BH1750 Ambient Light Sensor
# Pin 3: SDA (GPIO 2), Pin 5: SCL (GPIO 3), Pin 1: 3.3V, Pin 6: GND
I2C_BUS_NUMBER = 1
BH1750_I2C_ADDRESS = 0x23  # Default when ADDR pin is tied to GND; 0x5C if ADDR is VCC

# GPIO Pin for USB Ring LED switching (Transistor / Logic-level MOSFET / Relay)
# Pin 12: GPIO 18 (BCM 18 / PWM0 capable)
LED_GPIO_PIN = 18

# Ambient Light Thresholds (in Lux)
# Hysteresis loop avoids flickering near the boundary:
# When dark: Lux < LUX_THRESHOLD_LOW -> LED ON
# When bright: Lux > LUX_THRESHOLD_HIGH -> LED OFF
LUX_THRESHOLD_LOW = 30.0   # Lux below which nighttime illumination turns ON
LUX_THRESHOLD_HIGH = 50.0  # Lux above which illumination turns OFF
SENSOR_READ_INTERVAL = 1.5 # Seconds between periodic BH1750 pollings

# ==============================================================================
# 2. CAMERA CONFIGURATION (Raspberry Pi Camera Module 3)
# ==============================================================================
# Resolution: 640x480 or 1280x720 recommended for high FPS Edge AI on RPi 5
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
# Backend options: 'auto' (tries Picamera2 first, then OpenCV), 'picam3', or 'opencv'
CAMERA_BACKEND = "auto"
# Camera device index for OpenCV fallback (0 for default USB/V4L2)
OPENCV_DEVICE_INDEX = 0

# ==============================================================================
# 3. EDGE AI & OBJECT DETECTION CONFIGURATION
# ==============================================================================
# Model selection: Ultralytics YOLOv8n / YOLOv11n (weights will auto-download or use ONNX)
DEFAULT_MODEL_NAME = "yolov8n.pt"
MODEL_PATH = MODELS_DIR / DEFAULT_MODEL_NAME

# Detection Confidence & IoU Filter
CONFIDENCE_THRESHOLD = 0.40  # Minimum confidence score for detection
IOU_THRESHOLD = 0.45         # Non-Max Suppression (NMS) IoU overlap limit

# Target Classes Monitored:
# In standard COCO:
# 0: person, 2: car, 3: motorcycle, 5: bus, 7: truck
# 24: backpack, 26: handbag, 28: suitcase, 39: bottle, 41: cup
# In custom waste datasets: 'garbage', 'plastic_bag', 'carton', 'waste'
CLASS_MAPPINGS = {
    # COCO standard categories mapped to sentinel logic
    "person": "person",
    "car": "vehicle",
    "truck": "vehicle",
    "motorcycle": "vehicle",
    "bus": "vehicle",
    "backpack": "waste_candidate",
    "handbag": "waste_candidate",
    "suitcase": "waste_candidate",
    "bottle": "plastic",
    "cup": "waste_candidate",
    "box": "waste_candidate",
    # Custom trained classes
    "garbage": "garbage",
    "trash": "garbage",
    "plastic": "plastic",
    "waste": "garbage",
}

# List of classes treated as deposited waste items
WASTE_CLASSES = {"waste_candidate", "garbage", "plastic", "bottle", "cup", "box"}

# ==============================================================================
# 4. SPATIOTEMPORAL ILLEGAL DUMPING ACTION REASONING
# ==============================================================================
# Minimum distance (in pixels) for an object to be considered separated from person
SEPARATION_DISTANCE_PIXELS = 85.0

# Number of consecutive frames an object must remain stationary to trigger dumping
STATIONARY_CONFIRMATION_FRAMES = 12

# Person moving distance (pixels away from deposit point) to confirm abandonment
PERSON_EXIT_DISTANCE_PIXELS = 110.0

# Maximum displacement (pixels) between frames to consider an object "stationary"
STATIONARY_TOLERANCE_PIXELS = 15.0

# Minimum seconds between triggering duplicate alert events (Alert Cooldown)
ALERT_COOLDOWN_SECONDS = 15.0

# ==============================================================================
# 5. WEB DASHBOARD & NETWORKING
# ==============================================================================
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
SECRET_KEY = os.getenv("SENTINEL_SECRET_KEY", "smart-waste-sentinel-edge-2026")
STREAM_JPEG_QUALITY = 75  # JPEG compression quality (1-100) for MJPEG stream

# ==============================================================================
# 6. MUNICIPALITY NOTIFICATION & DISPATCH CONFIGURATION
# ==============================================================================
MUNICIPAL_OFFICE_NAME = "Central Municipal Corporation - Solid Waste Division"
MUNICIPAL_WARD = "Ward 14 (Greenbelt & Canal Perimeter)"
MUNICIPAL_OFFICER_TITLE = "Chief Sanitary Inspector / Enforcement Squad"
MUNICIPAL_PHONE = "+91 98480 22338"
MUNICIPAL_EMAIL = "sanitation.enforcement@municipalcorp.gov.in"
MUNICIPAL_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MUNICIPAL_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MUNICIPAL_WEBHOOK_URL = os.getenv("MUNICIPAL_WEBHOOK_URL", "")
MUNICIPAL_DISPATCH_ENABLED = True
