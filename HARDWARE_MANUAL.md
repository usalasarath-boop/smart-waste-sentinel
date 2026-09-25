# Hardware Manual & Circuit Architecture

## Project: Smart Waste Sentinel (Raspberry Pi 5 Prototype)

---

## 1. Hardware Bill of Materials (BOM)

| Component | Quantity | Interface / Protocol | Operating Voltage | Purpose |
|---|---|---|---|---|
| **Raspberry Pi 5 (8GB)** | 1 | Main Board | 5.1V / 5.0A USB-C (27W) | Edge AI Compute & Web Server |
| **Pi Camera Module 3** | 1 | MIPI CSI-2 (15-to-22 pin) | Internal 3.3V / 1.8V | Live video stream & object capture |
| **BH1750 Sensor Module** | 1 | I2C Bus (SDA/SCL) | 3.3V DC | Real-time ambient light measurement |
| **5V USB Ring LED Light** | 1 | Switched 5V Rail | 5V DC (0.5A - 1.5A) | Nighttime scene illumination |
| **2N2222 NPN or IRLZ44N MOSFET** | 1 | Discrete Semiconductor | 3.3V Logic Trigger | Low-side power switch for LED |
| **1kΩ Resistor (1/4W)** | 1 | Through-hole | N/A | Base/Gate current-limiting resistor |
| **10kΩ Resistor (1/4W)** | 1 | Through-hole | N/A | Pull-down resistor for Gate stability |
| **Mini Tripod with 1/4" mount** | 1 | Mechanical | N/A | Rigid mounting for camera & sensor |
| **Official 27W Power Adapter**| 1 | USB Type-C PD | 5.1V @ 5.0A | Dedicated power to RPi 5 |
| **Breadboard & Jumper Wires** | 1 set | Interconnect | 300V rated | Solderless rapid prototyping |

---

## 2. Complete Circuit Schematic Diagram

```text
                               +-----------------------------+
                               |   Raspberry Pi 5 (8GB)      |
                               |                             |
  +------------------+         | [Pin 1: 3.3V] --------------+--------+
  | BH1750 Ambient   |         |                             |        |
  | Light Sensor     |         | [Pin 3: GPIO 2 / SDA1] -----+-----+  |
  |                  |         |                             |     |  |
  |  VCC  <----------+---------+-----------------------------+     |  |
  |  GND  <----------+---------+ [Pin 6: GND]                      |  |
  |  SDA  <----------+---------+-----------------------------------+  |
  |  SCL  <----------+---------+ [Pin 5: GPIO 3 / SCL1]               |
  |  ADDR <----------+---------+ [Pin 9: GND] (Addr = 0x23)          |
  +------------------+         |                                      |
                               |                                      |
                               | [Pin 12: GPIO 18]                    |
                               |        |                             |
                               +--------|-----------------------------+
                                        |
                                      [1kΩ] Resistor
                                        |
                                        v
                                    +-------+
                                    | Base  | (2N2222 NPN)
                                    +-------+
                              Emitter /   \ Collector
                                     /     \
                                    v       \
                                 [GND]       \
                               (Pin 14)       \
                                               \
                                                v
                                         [ - Negative ]
                                    +-----------------------+
                                    | 5V USB Ring LED Light |
                                    +-----------------------+
                                         [ + Positive ]
                                                ^
                                                |
                               +----------------+
                               |
                        [Pin 2: 5V Rail]
```

---

## 3. Raspberry Pi 5 40-Pin Header Pinout Table

| Pin # | Pin Name | Wire Color | Connected Component Pin | Description |
|---|---|---|---|---|
| **Pin 1** | **3.3V Power** | Red | **BH1750 VCC** | Regulated 3.3V power supply |
| **Pin 2** | **5.0V Power** | Orange | **USB Ring LED (+)** | High-current 5V rail for LED power |
| **Pin 3** | **GPIO 2 (SDA1)** | Yellow | **BH1750 SDA** | I2C Data Line |
| **Pin 5** | **GPIO 3 (SCL1)** | Green | **BH1750 SCL** | I2C Clock Line |
| **Pin 6** | **GND** | Black | **BH1750 GND** | Common Ground reference |
| **Pin 9** | **GND** | Brown | **BH1750 ADDR** | Tied to GND to fix address to `0x23` |
| **Pin 12** | **GPIO 18** | Blue | **1kΩ -> Transistor Base** | Active-high logic trigger for illumination |
| **Pin 14** | **GND** | Black | **Transistor Emitter** | Circuit Ground return |

---

## 4. Subsystem Wiring Walkthrough

### 4.1 BH1750 Light Sensor Wiring
1. Connect **BH1750 VCC** to **Pin 1 (3.3V)**.  
   > [!CAUTION]
   > Do NOT connect BH1750 VCC to the 5V pin! Doing so can pull the I2C lines above 3.3V, causing permanent damage to the Raspberry Pi 5 SoC.
2. Connect **BH1750 GND** to **Pin 6 (GND)**.
3. Connect **BH1750 SDA** to **Pin 3 (GPIO 2)**.
4. Connect **BH1750 SCL** to **Pin 5 (GPIO 3)**.
5. Connect **BH1750 ADDR** to **Pin 9 (GND)**. This forces the I2C slave address to `0x23`. If left floating, noise can switch the address to `0x5C`.

### 4.2 USB Ring LED Driver Circuit Wiring
1. Strip the USB cable of the Ring LED light to expose the **Red (+5V)** and **Black (GND)** conductors.
2. Connect the **Red wire (+5V)** directly to **Pin 2 (5V Rail)** on the Raspberry Pi 5.
3. Connect the **Black wire (GND)** to the **Collector** of a 2N2222 NPN transistor (or the **Drain** if using an IRLZ44N N-MOSFET).
4. Connect the **Emitter** of the transistor (or **Source** if MOSFET) to **Pin 14 (GND)** on the Raspberry Pi.
5. Connect **Pin 12 (GPIO 18)** to one leg of a **1kΩ resistor**.
6. Connect the other leg of the **1kΩ resistor** to the **Base** of the transistor (or **Gate** of the MOSFET).
7. *(Optional but recommended)*: Place a **10kΩ resistor** between Base and GND to ensure the transistor stays fully switched OFF when the Pi boots up.

### 4.3 Raspberry Pi Camera Module 3 Connection
1. Locate the **CAM/DISP0** or **CAM/DISP1** port on the Raspberry Pi 5.
2. Note that Raspberry Pi 5 uses high-density 22-pin 0.5mm pitch FPC connectors (different from the 15-pin 1.0mm pitch on RPi 4). Ensure you are using the **15-to-22 pin adapter ribbon cable** included with Camera Module 3.
3. Gently pull up the plastic collar of the camera port.
4. Insert the ribbon cable with the **silver contacts facing the HDMI ports** and the blue backing facing the USB ports.
5. Push the plastic collar down firmly to lock the ribbon in place.

---

## 5. Physical Assembly & Tripod Mounting

1. **Mounting Plate:** Secure the Raspberry Pi 5 in an official case with active cooling fan to ensure thermal stability during sustained neural inference.
2. **Tripod Attachment:** Affix the Camera Module 3 and the BH1750 sensor side-by-side on an acrylic mounting bracket or 3D-printed fixture attached to the 1/4" tripod screw thread.
3. **Sensor Alignment:** Ensure the white diffusion dome of the BH1750 points directly toward the monitored zone so that ambient illuminance matches the camera's visual scene.
4. **Ring Light Positioning:** Mount the Ring LED concentrically around the camera lens to eliminate harsh casting shadows and uniformly illuminate the surveillance perimeter.

---

## 6. Hardware Troubleshooting Matrix

| Symptom | Probable Cause | Diagnostic Command | Remediation |
|---|---|---|---|
| `i2cdetect` shows empty grid | I2C not enabled in kernel | `ls /dev/i2c*` | Run `sudo raspi-config` -> Interface Options -> I2C -> Enable |
| `i2cdetect` shows `0x5C` instead of `0x23` | ADDR pin floating or tied to 3.3V | `i2cdetect -y 1` | Connect ADDR pin firmly to GND |
| Camera not detected | Ribbon cable loose or reversed | `rpicam-hello --list-cameras` | Reseat 22-pin ribbon cable; ensure contacts face HDMI ports |
| LED Ring stays ON continuously | Transistor shorted or inverted logic | `pinctrl get 18` | Verify 1kΩ resistor on Base; check transistor pinout (E-B-C) |
| System throttles or restarts | Insufficient power supply | `vcgencmd get_throttled` | Use official 27W 5.1V / 5.0A USB-C power supply |
