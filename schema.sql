-- =====================================================================
-- Smart Waste Sentinel - Relational Database Schema
-- Embedded SQLite Engine for Raspberry Pi 5
-- =====================================================================

-- 1. Events Table: Records high-level surveillance and illegal dumping incidents
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT UNIQUE NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL DEFAULT 'ILLEGAL_DUMPING',
    object_class TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_x1 INTEGER,
    bbox_y1 INTEGER,
    bbox_x2 INTEGER,
    bbox_y2 INTEGER,
    centroid_x INTEGER,
    centroid_y INTEGER,
    status TEXT DEFAULT 'CONFIRMED'
);

-- 2. Images Table: High-resolution incident snapshot evidence metadata
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    incident_id TEXT NOT NULL,
    image_filename TEXT NOT NULL,
    image_path TEXT NOT NULL,
    resolution TEXT NOT NULL,
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Sensor Data Table: Periodic telemetry of ambient light (BH1750) and LED illumination state
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    lux_level REAL NOT NULL,
    led_state BOOLEAN NOT NULL,
    threshold_low REAL,
    threshold_high REAL
);

-- 4. Alerts Table: Real-time security and municipal action triggers
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    alert_level TEXT NOT NULL DEFAULT 'CRITICAL',
    message TEXT NOT NULL,
    triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    acknowledged BOOLEAN DEFAULT 0
);

-- Performance Indexes for Real-time Dashboard Queries
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_incident_id ON events(incident_id);
CREATE INDEX IF NOT EXISTS idx_images_incident_id ON images(incident_id);
CREATE INDEX IF NOT EXISTS idx_sensor_data_timestamp ON sensor_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered_at ON alerts(triggered_at DESC);
