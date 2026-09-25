# Complete Installation & Deployment Guide

## Target Hardware: Raspberry Pi 5 (8GB)
**Operating System:** Raspberry Pi OS 64-bit (Debian Bookworm)  
**Assumed Audience:** First-time Raspberry Pi / Embedded Systems Builder

---

## Step 1: Flashing the OS & Initial Setup

1. Download and install the **Raspberry Pi Imager** on your PC/Mac from [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. Insert a high-speed MicroSD card (Class 10, UHS-I, 32GB or 64GB recommended).
3. In Raspberry Pi Imager:
   - **Device:** Select `Raspberry Pi 5`.
   - **Operating System:** Select `Raspberry Pi OS (64-bit)` (Recommended / Bookworm).
   - **Storage:** Choose your MicroSD card.
4. Click **Next** and click **Edit Settings**:
   - Set Hostname: `sentinel-pi`
   - Set Username & Password (e.g., user: `pi`, password: `your_password`)
   - Configure your local Wi-Fi SSID and password
   - Under the **Services** tab, enable **SSH** with password authentication.
5. Click **Save** and write the OS to the card.
6. Once complete, insert the MicroSD card into the Raspberry Pi 5 and power it on using the official 27W USB-C power supply.

---

## Step 2: System Update & Hardware Bus Activation

1. Find the Pi's IP address from your Wi-Fi router or connect a monitor and keyboard.
2. Open a terminal or SSH into the Pi:
   ```bash
   ssh pi@sentinel-pi.local
   # or ssh pi@<PI_IP_ADDRESS>
   ```
3. Update the package repositories:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   ```
4. Enable the **I2C interface**:
   ```bash
   sudo raspi-config
   ```
   - Navigate to `Interface Options` -> `I2C` -> Select `Yes` (Enable).
   - Navigate to `Finish` and reboot if prompted:
     ```bash
     sudo reboot
     ```
5. Install system hardware utilities:
   ```bash
   sudo apt install -y i2c-tools python3-pip python3-venv python3-picamera2 python3-opencv git
   ```

---

## Step 3: Hardware Verification

### 3.1 Verify I2C Bus & BH1750 Light Sensor
With the BH1750 wired to Pin 1 (3.3V), Pin 6 (GND), Pin 3 (SDA), Pin 5 (SCL), and Pin 9 (ADDR to GND):
```bash
sudo i2cdetect -y 1
```
**Expected Output:**
You should see `23` at row `20`, column `3`:
```text
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- 23 -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
```
*(If you see `5c`, the ADDR pin is connected to 3.3V or floating. Connect ADDR to GND to fix it to `23`.)*

### 3.2 Verify Camera Module 3
```bash
rpicam-hello --timeout 2000
```
A preview window should appear, showing the Camera Module 3 stream with continuous autofocus active!

---

## Step 4: Project Code Deployment & Virtual Environment

1. Clone or copy the project files to the Pi's home directory:
   ```bash
   cd ~
   git clone <YOUR_GIT_REPO_URL> SmartWasteSentinel
   cd SmartWasteSentinel
   ```
2. Create a Python Virtual Environment with system site packages enabled (this ensures access to precompiled `picamera2` and `libcamera` bindings):
   ```bash
   python3 -m venv --system-site-packages sentinel_env
   source sentinel_env/bin/activate
   ```
3. Install required Python packages:
   ```bash
   pip install --upgrade pip
   pip install Flask smbus2 gpiozero ultralytics
   ```

---

## Step 5: Diagnostic System Verification

Before launching the full web dashboard, run the automated diagnostic script:
```bash
python test_system.py
```
**Expected Output:**
```text
#################################################################
  SMART WASTE SENTINEL - HARDWARE & AI SUBSYSTEM VERIFICATION
  Vishwakarma Awards 2026 Prototype Readiness Check
#################################################################

=================================================================
  DIAGNOSTIC TEST: 1. BH1750 AMBIENT LIGHT SENSOR (I2C)
=================================================================
  [+] Mode:           PHYSICAL HARDWARE (I2C1)
  [+] Current Lux:    48.2 lx
  [+] Night Low Lim:  30.0 lx
  [+] Day High Lim:   50.0 lx

=================================================================
  DIAGNOSTIC TEST: 2. USB RING LED LIGHT CONTROLLER (GPIO 18)
=================================================================
  [+] Mode:           PHYSICAL GPIO 18 (BCM)
  [+] Turning ON LED...
  [+] State verify:   ON
  [+] Turning OFF LED...
  [+] State verify:   OFF

=================================================================
  DIAGNOSTIC TEST: 3. CAMERA STREAM (PICAMERA2 / OPENCV)
=================================================================
  [+] Active Backend: PICAMERA2
  [+] Grabbed Frame:  640x480, 3 channels

=================================================================
  DIAGNOSTIC TEST: 4. EDGE AI OBJECT DETECTOR & NEURAL INFERENCE
=================================================================
  [+] Detector Engine: REAL ULTRALYTICS / ONNX
  [+] Inference Time:  52.4 ms
  [+] Detections Count: 1

=================================================================
  DIAGNOSTIC TEST: 5. SQLITE EMBEDDED PERSISTENCE & WAL MODE
=================================================================
  [+] Inserted Event:  DIAG-1727271000 -> Database Row ID #1
  [+] Total Events:    1

=================================================================
  OVERALL READINESS SUMMARY
=================================================================
  1. BH1750 Sensor:      [PASSED]
  2. USB Ring LED:       [PASSED]
  3. Video Stream:       [PASSED]
  4. Edge AI Inference:  [PASSED]
  5. SQLite Persistence: [PASSED]
=================================================================
```

---

## Step 6: Launching the Prototype

Start the main orchestrator:
```bash
python app.py
```
Open any web browser on your laptop or smartphone connected to the same Wi-Fi network:
```text
http://<RASPBERRY_PI_IP>:5000
```
You will now see the live surveillance dashboard with the real-time AI HUD, ambient light gauge, and incident evidence gallery!

---

## Step 7: Auto-Start on Boot (Systemd Service)

To make the prototype completely autonomous so it starts automatically whenever power is plugged in at the awards venue:

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/sentinel.service
   ```
2. Paste the following configuration:
   ```ini
   [Unit]
   Description=Smart Waste Sentinel Edge AI Surveillance
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/SmartWasteSentinel
   ExecStart=/home/pi/SmartWasteSentinel/sentinel_env/bin/python app.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sentinel.service
   sudo systemctl start sentinel.service
   ```
4. Check service status:
   ```bash
   sudo systemctl status sentinel.service
   ```
Now your prototype will boot automatically in under 25 seconds upon plugging in the power adapter!
