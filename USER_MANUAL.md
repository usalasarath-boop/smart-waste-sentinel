# Smart Waste Sentinel - Operational & User Manual

## System Overview
The **Smart Waste Sentinel** is an autonomous Edge-AI surveillance device. Once powered, it boots in under 30 seconds, begins continuous camera surveillance, monitors ambient illuminance, autonomously controls auxiliary lighting, and logs any illegal dumping violations without requiring human supervision.

---

## 1. Physical Placement & Setup

1. **Tripod Deployment:** Mount the unit at a height of 1.5 to 2.5 meters overlooking the designated waste surveillance zone.
2. **Camera Angle:** Tilt the camera at a downward angle of ~15° to 30° toward the ground plane. Ensure the horizon or distant sky does not dominate more than 20% of the frame to prevent lens flare.
3. **Sensor Alignment:** Ensure the BH1750 ambient light sensor is unobstructed and pointed toward the scene being monitored.
4. **Power Connection:** Connect the official 27W USB-C power supply to the Pi 5. The red LED on the Pi will illuminate solid, followed by green blinking (SD activity).

---

## 2. Accessing the Web Dashboard

1. Connect your laptop, tablet, or phone to the same Wi-Fi network as the Raspberry Pi.
2. Open any modern web browser (Chrome, Firefox, Safari, Edge) and enter:
   ```text
   http://sentinel-pi.local:5000
   # or http://<PI_IP_ADDRESS>:5000
   ```
3. The dashboard is fully responsive and adjusts automatically for mobile and desktop screens.

---

## 3. Navigating Dashboard Screens

### 3.1 Live Monitor (Home Screen)
- **Live Video Stream (`/video_feed`):**
  - Displays low-latency (sub-100ms) MJPEG video directly from Camera Module 3.
  - Detected persons are bounded in **Orange**, vehicles in **Light Blue**, and waste items in **Red**.
  - When an illegal dumping incident occurs, the top HUD banner flashes red: `[CRITICAL ALERT] ILLEGAL DUMPING ACTIVITY DETECTED`.
- **Ambient Illuminance Gauge:**
  - Displays live Lux measured by the BH1750 sensor.
  - If illuminance drops below 30 Lux, the indicator highlights "Night Mode (<30 lx)" and the USB Ring LED illuminates automatically.
- **USB Ring LED Card:**
  - Indicates the active hardware state of GPIO 18 (`ACTIVE` in green, `OFF` in slate).
  - Includes a quick `Toggle Now` button for manual override.
- **Real-Time Alerts Feed:**
  - A scrollable chronological feed of verified violations.
  - Automatically pops up a floating alert toast in the upper-right corner and sounds an audible alarm chime when a new violation is detected.
- **Evidence Snapshots Carousel:**
  - Shows the 5 most recent incident evidence photos captured by the system with confidence ratings and timestamps.

### 3.2 Incidents & Forensic Evidence (`/history`)
- **Immutable SQLite Audit Trail:**
  - Displays a tabular log containing Incident ID, Timestamp, Detected Waste Class, and Confidence Score.
- **High-Resolution Forensic Inspector:**
  - Click on any thumbnail or click `Inspect Full-Res` to open the modal image viewer.
  - Shows full-resolution snapshot with bounding boxes marking the dumped object and violator.
- **Export Audit CSV:**
  - Click `Export Audit CSV` to immediately download a formatted spreadsheet (`SmartWasteSentinel_Incident_Audit.csv`) for municipal legal enforcement.

### 3.3 Circular Waste Analytics (`/analytics`)
- **Temporal Vulnerability (Incidents by Hour):**
  - Identifies peak violation time slots (e.g. 10 PM to 4 AM), allowing city authorities to deploy physical patrol vehicles during the most vulnerable hours.
- **Waste Material Composition Distribution:**
  - Interactive doughnut chart classifying dumped waste into Plastics, Mixed Waste, Boxes, and Containers.
- **Recyclable Diversion Metric:**
  - Estimates the percentage of dumped material that is recoverable for circular economy reprocessing.

### 3.4 Controls & Demonstration Console (`/settings`)
- **Jury Demonstration Buttons:**
  - `Simulate Nighttime Condition (12 Lux)`: Instantly sets internal illuminance to 12 Lux. The system enters night mode and switches ON the LED ring.
  - `Simulate Daylight Condition (180 Lux)`: Sets illuminance to 180 Lux. The LED ring switches OFF.
  - `Resume Real Sensor Telemetry`: Reconnects real optical readings from the physical BH1750.
- **GPIO Pinout Reference Table:**
  - Displays physical pin numbers, electrical specifications, and wiring functions.

---

## 4. Operational Maintenance & Power Down

- **Soft Shutdown:**
  - Never abruptly pull the power cord while the database is writing.
  - Open terminal and run:
    ```bash
    sudo poweroff
    ```
  - Wait 10 seconds until the green LED turns off completely, then disconnect power.
