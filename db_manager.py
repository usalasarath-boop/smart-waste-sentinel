"""
Database Manager (Thread-Safe SQLite Engine)
============================================
Handles high-throughput, low-latency persistence for surveillance events,
captured image paths, BH1750 ambient light telemetry, and system alerts.
"""

import sqlite3
import threading
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import config

logger = logging.getLogger("SmartWasteSentinel.DB")

class DatabaseManager:
    """Thread-safe SQLite manager with Write-Ahead Logging (WAL) for concurrent read/write."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._lock = threading.Lock()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates connection configured with WAL journal mode and row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        # WAL mode allows concurrent readers while AI thread writes
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_database(self):
        """Initializes tables from schema.sql."""
        schema_file = config.DATABASE_DIR / "schema.sql"
        if not schema_file.exists():
            logger.error("Database schema file not found at %s", schema_file)
            return

        with self._lock:
            with self._get_connection() as conn:
                with open(schema_file, "r") as f:
                    conn.executescript(f.read())
                conn.commit()
        logger.info("Database initialized successfully at %s", self.db_path)

    def log_event(self, incident_id: str, object_class: str, confidence: float,
                  bbox: List[int], centroid: List[int], lux: float, led_state: bool,
                  image_filename: str, image_path: str, resolution: str = "640x480") -> int:
        """
        Atomically records an illegal dumping event, associated image, alert, and sensor state.
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 1. Insert Event
                cursor.execute("""
                    INSERT INTO events (incident_id, object_class, confidence,
                                        bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                                        centroid_x, centroid_y)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    incident_id, object_class, confidence,
                    bbox[0], bbox[1], bbox[2], bbox[3],
                    centroid[0], centroid[1]
                ))
                event_id = cursor.lastrowid

                # 2. Insert Image Record
                cursor.execute("""
                    INSERT INTO images (event_id, incident_id, image_filename, image_path, resolution)
                    VALUES (?, ?, ?, ?, ?)
                """, (event_id, incident_id, image_filename, image_path, resolution))

                # 3. Insert Alert
                cursor.execute("""
                    INSERT INTO alerts (incident_id, alert_level, message)
                    VALUES (?, ?, ?)
                """, (
                    incident_id, "CRITICAL",
                    f"Illegal dumping of '{object_class.upper()}' detected (Conf: {int(confidence*100)}%)"
                ))

                # 4. Insert Snapshot Sensor Reading
                cursor.execute("""
                    INSERT INTO sensor_data (lux_level, led_state, threshold_low, threshold_high)
                    VALUES (?, ?, ?, ?)
                """, (lux, 1 if led_state else 0, config.LUX_THRESHOLD_LOW, config.LUX_THRESHOLD_HIGH))

                conn.commit()
                logger.info("Logged event %s (ID: %d) into database.", incident_id, event_id)
                return event_id

    def log_sensor_reading(self, lux: float, led_state: bool):
        """Records ambient light and illumination state telemetry."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO sensor_data (lux_level, led_state, threshold_low, threshold_high)
                    VALUES (?, ?, ?, ?)
                """, (lux, 1 if led_state else 0, config.LUX_THRESHOLD_LOW, config.LUX_THRESHOLD_HIGH))
                conn.commit()

    def get_recent_events(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Fetches latest illegal dumping incidents with joined image details."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.id, e.incident_id, e.timestamp, e.object_class, e.confidence,
                       e.status, i.image_filename, i.image_path
                FROM events e
                LEFT JOIN images i ON e.id = i.event_id
                ORDER BY e.timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches latest real-time alerts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, incident_id, alert_level, message, triggered_at, acknowledged
                FROM alerts
                ORDER BY triggered_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_all_events(self):
        """Clears all events, images, alerts, and municipal dispatches from database."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM events;")
                conn.execute("DELETE FROM images;")
                conn.execute("DELETE FROM alerts;")
                try:
                    conn.execute("DELETE FROM municipal_dispatches;")
                except Exception:
                    pass
                try:
                    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('events', 'images', 'alerts', 'municipal_dispatches');")
                except Exception:
                    pass
                conn.commit()
                conn.execute("VACUUM;")
        logger.info("Cleared all events, images, alerts, and dispatches from database.")

    def get_recent_dispatches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent alerts dispatched to the municipal office."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT id, incident_id, recipient_office, channel, message_content, dispatch_timestamp, status
                    FROM municipal_dispatches
                    ORDER BY dispatch_timestamp DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
            except Exception:
                return []

    def get_latest_sensor_data(self) -> Optional[Dict[str, Any]]:
        """Retrieves most recent ambient light & LED telemetry record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lux_level, led_state, timestamp
                FROM sensor_data
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_statistics(self) -> Dict[str, Any]:
        """Calculates system metrics for analytics dashboard and Vishwakarma presentation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total Incidents
            cursor.execute("SELECT COUNT(*) AS total FROM events")
            total_events = cursor.fetchone()["total"]

            # Class Distribution
            cursor.execute("""
                SELECT object_class, COUNT(*) as count
                FROM events
                GROUP BY object_class
                ORDER BY count DESC
            """)
            class_counts = {row["object_class"]: row["count"] for row in cursor.fetchall()}

            # Hourly distribution (past 24h)
            cursor.execute("""
                SELECT strftime('%H:00', timestamp) AS hour_slot, COUNT(*) AS count
                FROM events
                GROUP BY hour_slot
                ORDER BY hour_slot ASC
            """)
            hourly_counts = {row["hour_slot"]: row["count"] for row in cursor.fetchall()}

            # Sensor averages
            cursor.execute("SELECT AVG(lux_level) AS avg_lux FROM sensor_data")
            avg_lux = cursor.fetchone()["avg_lux"] or 0.0

            return {
                "total_events": total_events,
                "class_counts": class_counts,
                "hourly_counts": hourly_counts,
                "avg_lux": round(avg_lux, 2)
            }
