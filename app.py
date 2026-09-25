"""
Smart Waste Sentinel - Main Application Entrypoint
===================================================
Coordinates background Edge-AI surveillance threads, autonomous sensor-driven
illumination loops, SQLite persistence, and Flask web services.
"""

import time
import os
import signal
import sys
import threading
import logging
from pathlib import Path
import cv2

# Initialize Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(name)s: %(message)s"
)
logger = logging.getLogger("SmartWasteSentinel.Main")

# Import subsystem modules
import config
from camera import CameraStream
from sensors import BH1750Sensor, LEDController
from ai import EdgeAIDetector, IllegalDumpingEngine
from database import DatabaseManager
from alerts import AlertManager, MunicipalNotifier
from dashboard import create_dashboard_blueprint
from flask import Flask

def create_app():
    """Application factory for Smart Waste Sentinel."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    # 1. Initialize Subsystems
    logger.info("Initializing Smart Waste Sentinel hardware and AI engines...")
    
    # Database
    db = DatabaseManager(config.DATABASE_PATH)

    # Sensors & Actuators
    bh1750 = BH1750Sensor(bus_number=config.I2C_BUS_NUMBER, address=config.BH1750_I2C_ADDRESS)
    led = LEDController(pin=config.LED_GPIO_PIN)

    # Camera Stream
    camera = CameraStream(
        width=config.CAMERA_WIDTH,
        height=config.CAMERA_HEIGHT,
        fps=config.CAMERA_FPS,
        backend=config.CAMERA_BACKEND,
        device_index=config.OPENCV_DEVICE_INDEX
    )
    camera.start()

    # Edge AI Engines
    detector = EdgeAIDetector(model_path=config.MODEL_PATH, conf=config.CONFIDENCE_THRESHOLD)
    dumping_engine = IllegalDumpingEngine()
    alert_mgr = AlertManager(db_manager=db)
    municipal_notifier = MunicipalNotifier(db_manager=db)

    # 2. Register Dashboard Blueprint
    dashboard_bp = create_dashboard_blueprint(
        camera=camera,
        detector=detector,
        dumping_engine=dumping_engine,
        bh1750=bh1750,
        led=led,
        db=db,
        alert_mgr=alert_mgr,
        municipal_notifier=municipal_notifier
    )
    app.register_blueprint(dashboard_bp)

    # 3. Start Background Surveillance and Sensor Loops
    stop_event = threading.Event()

    def sensor_and_illumination_loop():
        """Monitors ambient light (BH1750) and autonomously controls Ring LED."""
        logger.info("Sensor illumination control loop started.")
        last_log_time = 0.0

        while not stop_event.is_set():
            try:
                lux = bh1750.read_lux()
                current_time = time.time()

                # Hysteresis illumination switching
                if lux < config.LUX_THRESHOLD_LOW:
                    if not led.is_on():
                        led.turn_on()
                        logger.info("Dusk/Night detected (%.1f lx < %.1f lx). Ring LED illuminated.", lux, config.LUX_THRESHOLD_LOW)
                elif lux > config.LUX_THRESHOLD_HIGH:
                    if led.is_on():
                        led.turn_off()
                        logger.info("Daylight restored (%.1f lx > %.1f lx). Ring LED extinguished.", lux, config.LUX_THRESHOLD_HIGH)

                # Periodic sensor logging (every 30 seconds)
                if current_time - last_log_time > 30.0:
                    db.log_sensor_reading(lux, led.is_on())
                    last_log_time = current_time

            except Exception as e:
                logger.error("Error in sensor loop: %s", e)

            time.sleep(config.SENSOR_READ_INTERVAL)

    def ai_surveillance_worker():
        """Continuously pulls frames, runs YOLO inference, and reasons about dumping actions."""
        logger.info("AI surveillance analysis worker started.")

        while not stop_event.is_set():
            try:
                frame = camera.get_frame()
                if frame is None:
                    time.sleep(0.04)
                    continue

                # Run object detection
                detections = detector.detect(frame)

                # Read current telemetry
                lux = bh1750.read_lux()
                led_state = led.is_on()

                # Evaluate spatiotemporal dumping state machine
                dumping_event = dumping_engine.process_frame(detections, lux=lux, led_state=led_state)

                if dumping_event:
                    # Verified Illegal Dumping Incident!
                    incident_id = dumping_event.incident_id
                    image_filename = f"{incident_id}.jpg"
                    image_filepath = config.IMAGES_DIR / image_filename

                    # Save high-resolution annotated snapshot
                    annotated_snapshot = detector.annotate_frame(frame, detections, dumping_active=True)
                    cv2.imwrite(str(image_filepath), annotated_snapshot)
                    logger.info("Saved incident snapshot to %s", image_filepath)

                    # Persist event into SQLite
                    db.log_event(
                        incident_id=incident_id,
                        object_class=dumping_event.object_class,
                        confidence=dumping_event.confidence,
                        bbox=dumping_event.bbox,
                        centroid=list(dumping_event.centroid),
                        lux=lux,
                        led_state=led_state,
                        image_filename=image_filename,
                        image_path=str(image_filepath),
                        resolution=f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}"
                    )

                    # Dispatch real-time alert to UI
                    alert_mgr.trigger_alert(
                        incident_id=incident_id,
                        object_class=dumping_event.object_class,
                        confidence=dumping_event.confidence,
                        lux=lux,
                        image_filename=image_filename
                    )

                    # Dispatch automated alert message to nearby Municipal Corporation Office
                    if config.MUNICIPAL_DISPATCH_ENABLED:
                        municipal_notifier.dispatch_alert(
                            incident_id=incident_id,
                            object_class=dumping_event.object_class,
                            confidence=dumping_event.confidence,
                            lux=lux,
                            image_path=str(image_filepath)
                        )

            except Exception as e:
                logger.error("Error in AI surveillance worker: %s", e)

            # Prevent CPU thrashing; adjust loop speed for Edge AI pacing
            time.sleep(0.03)

    sensor_thread = threading.Thread(target=sensor_and_illumination_loop, name="SensorWorker", daemon=True)
    ai_thread = threading.Thread(target=ai_surveillance_worker, name="AISentryWorker", daemon=True)

    sensor_thread.start()
    ai_thread.start()

    # Graceful shutdown handler
    def cleanup():
        logger.info("Cleaning up resources before shutdown...")
        stop_event.set()
        camera.stop()
        led.cleanup()
        bh1750.close()

    app.cleanup = cleanup
    return app

if __name__ == "__main__":
    app = create_app()
    logger.info("=" * 65)
    logger.info("  SMART WASTE SENTINEL - EDGE AI SURVEILLANCE RUNNING")
    logger.info("  Dashboard URL: http://%s:%d", config.FLASK_HOST, config.FLASK_PORT)
    logger.info("=" * 65)

    try:
        app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False, threaded=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown initiated by user.")
    finally:
        if hasattr(app, "cleanup"):
            app.cleanup()
