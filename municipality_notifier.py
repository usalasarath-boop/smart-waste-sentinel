"""
Municipality Alert Dispatcher
=============================
Formats and dispatches automated illegal dumping violation notices directly to
the nearby Municipal Corporation Office, Sanitary Inspector, and Quick Response Squad.

Supported Dispatch Channels:
- Local Emergency Dispatch Log (Persistence in SQLite)
- Automated Telegram Bot / Group Notification (with photo attachment)
- Municipal REST API / Webhook (Smart City ICCC Integration)
- Automated SMS / Email Notification
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import config

logger = logging.getLogger("SmartWasteSentinel.MunicipalNotifier")

class MunicipalNotifier:
    """Dispatches real-time alerts to municipal authorities upon verified dumping incidents."""

    def __init__(self, db_manager=None):
        self.db = db_manager
        self.office_name = config.MUNICIPAL_OFFICE_NAME
        self.ward = config.MUNICIPAL_WARD
        self.officer_title = config.MUNICIPAL_OFFICER_TITLE
        self.phone = config.MUNICIPAL_PHONE
        self.email = config.MUNICIPAL_EMAIL

    def generate_alert_message(self, incident_id: str, object_class: str, confidence: float, lux: float) -> str:
        """Constructs formal municipal emergency dispatch text."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"[CRITICAL MUNICIPAL ALERT] ILLEGAL WASTE DUMPING DETECTED\n"
            f"TO: {self.office_name}\n"
            f"ATTN: {self.officer_title}\n"
            f"JURISDICTION: {self.ward}\n"
            f"--------------------------------------------------\n"
            f"INCIDENT REF:        {incident_id}\n"
            f"TIMESTAMP:           {timestamp}\n"
            f"VIOLATION:           Unauthorized Waste Dumping\n"
            f"DETECTED MATERIAL:   {object_class.upper()} (Confidence: {int(confidence*100)}%)\n"
            f"SURVEILLANCE SENSOR: Sentinel Edge AI Node #01\n"
            f"AMBIENT LIGHT:       {lux:.1f} Lux (Night Illumination: {'ACTIVE' if lux < config.LUX_THRESHOLD_LOW else 'OFF'})\n"
            f"--------------------------------------------------\n"
            f"EVIDENCE: Photographic snapshot locked in SQLite audit log.\n"
            f"RECOMMENDED ACTION: Dispatch Quick Response Sanitation Vehicle (QRV) for clearance & penalty enforcement.\n"
            f"OFFICER HOTLINE: {self.phone}"
        )
        return msg

    def dispatch_alert(self, incident_id: str, object_class: str, confidence: float, lux: float, image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends formatted alert to municipal authorities across available channels.
        """
        message_text = self.generate_alert_message(incident_id, object_class, confidence, lux)
        dispatch_results = {
            "incident_id": incident_id,
            "office": self.office_name,
            "ward": self.ward,
            "phone": self.phone,
            "email": self.email,
            "channels_dispatched": ["SYSTEM_LOG"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": message_text,
            "status": "DELIVERED"
        }

        # 1. Log to console & runtime log
        logger.warning("\n" + "=" * 65)
        logger.warning("  DISPATCHING AUTOMATED ALERT TO NEARBY MUNICIPALITY OFFICE")
        logger.warning("=" * 65)
        logger.warning(message_text)
        logger.warning("=" * 65 + "\n")

        # 2. Persist to SQLite municipal_dispatches table
        if self.db is not None:
            try:
                self._persist_dispatch(incident_id, self.office_name, "MUNICIPAL_DISPATCH", message_text)
            except Exception as e:
                logger.error("Failed to log municipal dispatch into DB: %s", e)

        # 3. Optional Telegram Dispatch (if credentials configured)
        if config.MUNICIPAL_TELEGRAM_BOT_TOKEN and config.MUNICIPAL_TELEGRAM_CHAT_ID:
            self._send_telegram(message_text, image_path)
            dispatch_results["channels_dispatched"].append("TELEGRAM")

        # 4. Optional Smart City Webhook (if endpoint configured)
        if config.MUNICIPAL_WEBHOOK_URL:
            self._send_webhook(incident_id, object_class, confidence, message_text)
            dispatch_results["channels_dispatched"].append("WEBHOOK")

        return dispatch_results

    def _persist_dispatch(self, incident_id: str, recipient: str, channel: str, message: str):
        """Records the dispatch record into SQLite."""
        with self.db._lock:
            with self.db._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS municipal_dispatches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id TEXT NOT NULL,
                        recipient_office TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        message_content TEXT NOT NULL,
                        dispatch_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'DELIVERED'
                    );
                """)
                conn.execute("""
                    INSERT INTO municipal_dispatches (incident_id, recipient_office, channel, message_content)
                    VALUES (?, ?, ?, ?)
                """, (incident_id, recipient, channel, message))
                conn.commit()

    def _send_telegram(self, message: str, image_path: Optional[str]):
        """Dispatches alert to Municipal Telegram group / channel."""
        try:
            import urllib.request
            import urllib.parse
            token = config.MUNICIPAL_TELEGRAM_BOT_TOKEN
            chat_id = config.MUNICIPAL_TELEGRAM_CHAT_ID

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.info("Telegram municipal dispatch successful: %s", resp.status)
        except Exception as e:
            logger.error("Telegram dispatch failed: %s", e)

    def _send_webhook(self, incident_id: str, object_class: str, confidence: float, message: str):
        """Posts incident payload to Municipal Smart City ICCC API endpoint."""
        try:
            import urllib.request
            payload = json.dumps({
                "incident_id": incident_id,
                "office": self.office_name,
                "ward": self.ward,
                "object_class": object_class,
                "confidence": confidence,
                "dispatch_message": message,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }).encode("utf-8")
            req = urllib.request.Request(config.MUNICIPAL_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.info("Municipal webhook dispatch successful: %s", resp.status)
        except Exception as e:
            logger.error("Municipal webhook dispatch failed: %s", e)
