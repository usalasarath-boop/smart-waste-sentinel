"""
Alert Manager (Real-time Notification & Cooldown Dispatcher)
============================================================
Coordinates instantaneous alert dispatching across web dashboard clients,
database logging, and optional hardware strobe/buzzers.
"""

import time
import logging
from collections import deque
from typing import List, Dict, Any, Optional

import config

logger = logging.getLogger("SmartWasteSentinel.Alerts")

class AlertManager:
    """Manages system alerts, ephemeral notification queues, and siren hooks."""

    def __init__(self, db_manager = None):
        self.db_manager = db_manager
        # Ephemeral FIFO buffer of recent alerts for live UI polling
        self.alert_queue = deque(maxlen=20)
        self.last_alert_time = 0.0
        self.alert_count = 0

    def trigger_alert(self, incident_id: str, object_class: str, confidence: float,
                      lux: float, image_filename: str) -> Dict[str, Any]:
        """
        Processes and broadcasts a verified illegal dumping alert.
        """
        now = time.time()
        self.last_alert_time = now
        self.alert_count += 1

        alert_payload = {
            "id": self.alert_count,
            "incident_id": incident_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": "CRITICAL",
            "title": f"Illegal Dumping: {object_class.upper()}",
            "message": f"Unauthorized waste deposition detected with {int(confidence*100)}% confidence.",
            "lux": lux,
            "image": image_filename
        }

        self.alert_queue.appendleft(alert_payload)
        logger.warning("DISPATCHED ALERT: %s (%s)", alert_payload["title"], incident_id)
        return alert_payload

    def get_pending_alerts(self) -> List[Dict[str, Any]]:
        """Returns the latest buffered alerts."""
        return list(self.alert_queue)
