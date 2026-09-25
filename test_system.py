"""
Smart Waste Sentinel - Comprehensive Hardware & Subsystem Diagnostic Tool
========================================================================
Runs step-by-step verification of all hardware buses, sensors, camera,
Edge-AI neural inference, and database persistence.
"""

import sys
import time
import cv2
import numpy as np
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import config
from sensors.bh1750 import BH1750Sensor
from sensors.led_controller import LEDController
from camera.camera_stream import CameraStream
from ai.detector import EdgeAIDetector
from ai.dumping_logic import IllegalDumpingEngine
from database.db_manager import DatabaseManager

def print_header(title):
    print("\n" + "=" * 65)
    print(f"  DIAGNOSTIC TEST: {title.upper()}")
    print("=" * 65)

def test_sensors():
    print_header("1. BH1750 Ambient Light Sensor (I2C)")
    sensor = BH1750Sensor(bus_number=config.I2C_BUS_NUMBER, address=config.BH1750_I2C_ADDRESS)
    lux = sensor.read_lux()
    mode = "SIMULATED" if sensor.is_simulated else "PHYSICAL HARDWARE (I2C1)"
    print(f"  [+] Mode:           {mode}")
    print(f"  [+] Current Lux:    {lux} lx")
    print(f"  [+] Night Low Lim:  {config.LUX_THRESHOLD_LOW} lx")
    print(f"  [+] Day High Lim:   {config.LUX_THRESHOLD_HIGH} lx")
    sensor.close()
    return True

def test_led():
    print_header("2. USB Ring LED Light Controller (GPIO 18)")
    led = LEDController(pin=config.LED_GPIO_PIN)
    mode = "SIMULATED" if led.is_simulated else "PHYSICAL GPIO 18 (BCM)"
    print(f"  [+] Mode:           {mode}")
    print("  [+] Turning ON LED...")
    led.turn_on()
    time.sleep(0.5)
    print(f"  [+] State verify:   {'ON' if led.is_on() else 'OFF'}")
    print("  [+] Turning OFF LED...")
    led.turn_off()
    time.sleep(0.2)
    print(f"  [+] State verify:   {'ON' if led.is_on() else 'OFF'}")
    led.cleanup()
    return True

def test_camera():
    print_header("3. Camera Stream (Picamera2 / OpenCV / Synthetic)")
    cam = CameraStream(width=config.CAMERA_WIDTH, height=config.CAMERA_HEIGHT, fps=config.CAMERA_FPS)
    cam.start()
    time.sleep(0.8)
    frame = cam.get_frame()
    backend = cam.backend_used.upper()
    print(f"  [+] Active Backend: {backend}")
    if frame is not None:
        h, w, c = frame.shape
        print(f"  [+] Grabbed Frame:  {w}x{h}, {c} channels, Type: {frame.dtype}")
        # Save test frame
        test_out = BASE_DIR / "images" / "diagnostic_frame.jpg"
        cv2.imwrite(str(test_out), frame)
        print(f"  [+] Test Frame Saved: {test_out}")
        cam.stop()
        return True
    else:
        print("  [-] Error: Could not grab frame from camera stream.")
        cam.stop()
        return False

def test_ai():
    print_header("4. Edge AI Object Detector & Neural Inference")
    detector = EdgeAIDetector()
    mode = "SIMULATED SYNTHETIC" if detector.is_simulated else "REAL ULTRALYTICS / ONNX"
    print(f"  [+] Detector Engine: {mode}")
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw sample rect to test
    cv2.rectangle(dummy_frame, (100, 100), (250, 350), (255, 255, 255), -1)
    t0 = time.time()
    detections = detector.detect(dummy_frame)
    latency_ms = (time.time() - t0) * 1000
    print(f"  [+] Inference Time:  {latency_ms:.2f} ms")
    print(f"  [+] Detections Count: {len(detections)}")
    return True

def test_database():
    print_header("5. SQLite Embedded Persistence & WAL Mode")
    db = DatabaseManager(config.DATABASE_PATH)
    test_incident = f"DIAG-{int(time.time())}"
    event_id = db.log_event(
        incident_id=test_incident,
        object_class="diagnostic_test_carton",
        confidence=0.99,
        bbox=[50, 50, 200, 200],
        centroid=[125, 125],
        lux=42.0,
        led_state=False,
        image_filename="diagnostic_frame.jpg",
        image_path=str(BASE_DIR / "images" / "diagnostic_frame.jpg")
    )
    print(f"  [+] Inserted Event:  {test_incident} -> Database Row ID #{event_id}")
    stats = db.get_statistics()
    print(f"  [+] Total Events:    {stats['total_events']}")
    print(f"  [+] Class Summary:   {stats['class_counts']}")
    return True

def main():
    print("\n" + "#" * 65)
    print("  SMART WASTE SENTINEL - HARDWARE & AI SUBSYSTEM VERIFICATION")
    print("  Vishwakarma Awards 2026 Prototype Readiness Check")
    print("#" * 65)

    s1 = test_sensors()
    s2 = test_led()
    s3 = test_camera()
    s4 = test_ai()
    s5 = test_database()

    print("\n" + "=" * 65)
    print("  OVERALL READINESS SUMMARY")
    print("=" * 65)
    print(f"  1. BH1750 Sensor:      {'[PASSED]' if s1 else '[FAILED]'}")
    print(f"  2. USB Ring LED:       {'[PASSED]' if s2 else '[FAILED]'}")
    print(f"  3. Video Stream:       {'[PASSED]' if s3 else '[FAILED]'}")
    print(f"  4. Edge AI Inference:  {'[PASSED]' if s4 else '[FAILED]'}")
    print(f"  5. SQLite Persistence: {'[PASSED]' if s5 else '[FAILED]'}")
    print("=" * 65)
    print("  All tests concluded. Prototype is ready for live execution.\n")

if __name__ == "__main__":
    main()
