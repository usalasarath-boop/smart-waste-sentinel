"""
Flask Dashboard & REST API Routes
=================================
Serves modern web interface, live MJPEG video stream, telemetry APIs,
and incident evidence gallery.
"""

import time
import logging
from pathlib import Path
from flask import Blueprint, render_template, Response, jsonify, request, send_from_directory

import config

logger = logging.getLogger("SmartWasteSentinel.Routes")

def create_dashboard_blueprint(camera, detector, dumping_engine, bh1750, led, db, alert_mgr, municipal_notifier=None):
    """Factory function injecting service instances into the Flask Blueprint."""
    bp = Blueprint("dashboard", __name__)

    # --------------------------------------------------------------------------
    # 1. Web Page Views
    # --------------------------------------------------------------------------
    @bp.route("/")
    def index():
        """Main real-time surveillance dashboard."""
        recent_events = db.get_recent_events(limit=5)
        recent_alerts = db.get_recent_alerts(limit=5)
        recent_dispatches = db.get_recent_dispatches(limit=5)
        stats = db.get_statistics()
        return render_template(
            "index.html",
            recent_events=recent_events,
            recent_alerts=recent_alerts,
            recent_dispatches=recent_dispatches,
            stats=stats,
            led_state=led.is_on(),
            municipal_office=config.MUNICIPAL_OFFICE_NAME,
            municipal_ward=config.MUNICIPAL_WARD,
            municipal_phone=config.MUNICIPAL_PHONE
        )

    @bp.route("/history")
    def history():
        """Searchable incident log and captured image gallery."""
        events = db.get_recent_events(limit=50)
        return render_template("history.html", events=events)

    @bp.route("/analytics")
    def analytics():
        """Visual intelligence, circular waste stats, and hourly distributions."""
        stats = db.get_statistics()
        return render_template("analytics.html", stats=stats)

    @bp.route("/settings")
    def settings():
        """Hardware threshold tuning and testing console."""
        return render_template(
            "settings.html",
            config=config,
            led_state=led.is_on()
        )

    # --------------------------------------------------------------------------
    # 2. Live Video Streaming Endpoint (MJPEG)
    # --------------------------------------------------------------------------
    def generate_frames():
        """Generator yielding multipart MJPEG frames with Edge AI HUD annotations."""
        while True:
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            # Run detection for live video HUD
            detections = detector.detect(frame)
            is_dumping = (time.time() - dumping_engine.last_alert_time) < 4.0

            # Render HUD overlays
            annotated_frame = detector.annotate_frame(frame, detections, dumping_active=is_dumping)

            # Encode as JPEG
            import cv2
            ret, buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), config.STREAM_JPEG_QUALITY])
            if not ret:
                time.sleep(0.02)
                continue

            frame_bytes = buffer.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.03)  # Approx 30 FPS cap for stream

    @bp.route("/video_feed")
    def video_feed():
        """MJPEG video streaming route."""
        return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    # --------------------------------------------------------------------------
    # 3. REST API Endpoints
    # --------------------------------------------------------------------------
    @bp.route("/api/sensor")
    def api_sensor():
        """Returns instantaneous BH1750 Lux and Ring LED status."""
        lux = bh1750.read_lux()
        is_lit = led.is_on()
        return jsonify({
            "lux": lux,
            "led_active": is_lit,
            "threshold_low": config.LUX_THRESHOLD_LOW,
            "threshold_high": config.LUX_THRESHOLD_HIGH,
            "night_mode": is_lit,
            "is_simulated_sensor": bh1750.is_simulated,
            "is_simulated_led": led.is_simulated
        })

    @bp.route("/api/stats")
    def api_stats():
        """Returns statistics for charts and KPI cards."""
        stats = db.get_statistics()
        return jsonify(stats)

    @bp.route("/api/alerts")
    def api_alerts():
        """Returns pending real-time alerts for dynamic toast notifications."""
        alerts = alert_mgr.get_pending_alerts()
        return jsonify(alerts)

    @bp.route("/api/events")
    def api_events():
        """Returns recent events list."""
        events = db.get_recent_events(limit=25)
        return jsonify(events)

    @bp.route("/api/toggle_led", methods=["POST"])
    def api_toggle_led():
        """Manual LED override for demonstration testing."""
        new_state = led.toggle()
        return jsonify({"success": True, "led_active": new_state})

    @bp.route("/api/simulate_lux", methods=["POST"])
    def api_simulate_lux():
        """Judge/User demo endpoint: manually force Lux level to test night mode."""
        data = request.get_json() or {}
        lux = data.get("lux")
        if lux is not None:
            bh1750.set_simulation_lux(float(lux))
            return jsonify({"success": True, "simulated_lux": float(lux)})
        else:
            bh1750.set_simulation_lux(None)  # Reset to auto
            return jsonify({"success": True, "simulated_lux": "auto"})

    @bp.route("/api/manual_capture", methods=["POST"])
    def api_manual_capture():
        """Forces an immediate snapshot and logs a test incident."""
        frame = camera.get_frame()
        if frame is None:
            return jsonify({"success": False, "error": "Camera frame not available"}), 500

        incident_id = f"MANUAL-{time.strftime('%Y%m%d-%H%M%S')}"
        filename = f"{incident_id}.jpg"
        filepath = config.IMAGES_DIR / filename

        import cv2
        cv2.imwrite(str(filepath), frame)

        lux = bh1750.read_lux()
        is_lit = led.is_on()

        event_id = db.log_event(
            incident_id=incident_id,
            object_class="manual_inspection",
            confidence=1.0,
            bbox=[0, 0, config.CAMERA_WIDTH, config.CAMERA_HEIGHT],
            centroid=[config.CAMERA_WIDTH // 2, config.CAMERA_HEIGHT // 2],
            lux=lux,
            led_state=is_lit,
            image_filename=filename,
            image_path=str(filepath)
        )

        alert_mgr.trigger_alert(incident_id, "manual_inspection", 1.0, lux, filename)
        return jsonify({"success": True, "incident_id": incident_id, "event_id": event_id})

    @bp.route("/api/clear_all_incidents", methods=["POST"])
    def api_clear_all_incidents():
        """Deletes all captured evidence photos from disk and purges database records."""
        deleted_count = 0
        try:
            # 1. Delete all images in incidents directory
            for img_file in config.IMAGES_DIR.glob("*.*"):
                try:
                    img_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error("Could not delete file %s: %s", img_file, e)

            # 2. Clear database records
            db.clear_all_events()

            # 3. Clear memory queues
            dumping_engine.recent_events.clear()
            alert_mgr.alert_queue.clear()

            logger.info("Successfully deleted %d stored photos and purged audit logs.", deleted_count)
            return jsonify({"success": True, "deleted_count": deleted_count})
        except Exception as e:
            logger.error("Error clearing incidents: %s", e)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/municipal_dispatches")
    def api_municipal_dispatches():
        """Returns recent alert dispatches sent to the municipal office."""
        dispatches = db.get_recent_dispatches(limit=10)
        return jsonify(dispatches)

    @bp.route("/api/test_municipal_alert", methods=["POST"])
    def api_test_municipal_alert():
        """Manually triggers a test alert dispatch to the municipal office."""
        incident_id = f"MUNI-DISPATCH-{time.strftime('%Y%m%d-%H%M%S')}"
        lux = bh1750.read_lux()
        if municipal_notifier is not None:
            res = municipal_notifier.dispatch_alert(
                incident_id=incident_id,
                object_class="garbage_bag",
                confidence=0.95,
                lux=lux,
                image_path=str(config.IMAGES_DIR / "INC-VERIFIED-DUMPING-01.jpg")
            )
            return jsonify({"success": True, "dispatch": res})
        return jsonify({"success": False, "error": "Municipal notifier not initialized"}), 500

    # --------------------------------------------------------------------------
    # 4. Static Evidence File Serving
    # --------------------------------------------------------------------------
    @bp.route("/incidents/<path:filename>")
    def serve_incident_image(filename):
        """Serves captured evidence photos from disk."""
        return send_from_directory(str(config.IMAGES_DIR), filename)

    return bp
