# Software Architecture & Developer Manual

## Project: Smart Waste Sentinel (Edge AI System)

---

## 1. System Architecture Overview

```mermaid
graph TD
    subgraph SENSORY_LAYER ["Sensory & Video Input Layer"]
        CAM["Raspberry Pi Camera 3<br/>(Sony IMX708 PDAF)"]
        BH["BH1750 Light Sensor<br/>(I2C Bus 1 @ 0x23)"]
    end

    subgraph HARDWARE_DRIVERS ["Hardware Abstraction Layer"]
        STREAM["CameraStream Worker<br/>(Picamera2 / libcamera)"]
        I2C_DRV["BH1750 Driver<br/>(smbus2)"]
        GPIO_DRV["LED Controller<br/>(GPIOZero / GPIO 18)"]
    end

    subgraph EDGE_AI_CORE ["Edge AI Intelligence Engine"]
        DETECTOR["EdgeAIDetector<br/>(YOLOv8n / YOLOv11n)"]
        MOT["Multi-Object Centroid Tracker"]
        STATE_MACHINE["Spatiotemporal Dumping Logic<br/>(Separation & Abandonment Engine)"]
    end

    subgraph STORAGE_ALERT ["Persistence & Notification"]
        DB["SQLite 3 Database<br/>(WAL Mode Engine)"]
        ALERT_MGR["Alert Manager<br/>(Real-Time Dispatch & Cooldown)"]
        DISK["Local Storage<br/>(Annotated JPG Evidence)"]
    end

    subgraph WEB_DASHBOARD ["Presentation & Telemetry Layer"]
        FLASK["Flask 3.0 Web Application"]
        STREAM_API["MJPEG Video Stream (/video_feed)"]
        REST_API["REST Telemetry APIs (/api/...)"]
        UI["Tailwind CSS Web Dashboard"]
    end

    CAM --> STREAM
    BH --> I2C_DRV
    I2C_DRV --> GPIO_DRV

    STREAM --> DETECTOR
    DETECTOR --> MOT
    MOT --> STATE_MACHINE
    I2C_DRV --> STATE_MACHINE

    STATE_MACHINE -->|Incident Verified| DISK
    STATE_MACHINE -->|Persist Event| DB
    STATE_MACHINE -->|Broadcast Alert| ALERT_MGR

    STREAM --> STREAM_API
    DB --> REST_API
    ALERT_MGR --> REST_API

    STREAM_API --> UI
    REST_API --> UI
```

---

## 2. Real-Time End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Violator as Pedestrian / Violator
    participant Cam as Pi Camera Module 3
    participant BH as BH1750 (I2C)
    participant Core as Background AI Worker
    participant Logic as Dumping Reasoner
    participant LED as GPIO 18 (LED Ring)
    participant DB as SQLite Engine
    participant UI as Flask Dashboard

    loop Every 1.5 Seconds
        BH->>Core: Read Lux level
        alt Lux < 30.0 (Dusk/Night)
            Core->>LED: turn_on() (3.3V to Transistor Gate)
        else Lux > 50.0 (Daylight)
            Core->>LED: turn_off()
        end
    end

    loop Continuous Video Loop (30 FPS)
        Cam->>Core: Capture frame (RGB)
        Core->>Core: YOLOv8n Inference (Bounding Boxes)
        Violator->>Cam: Carries waste item into frame
        Core->>Logic: Update tracks (Person track + Waste track)
        Note over Logic: State: ATTACHED (Distance < 85px)
        Violator->>Cam: Places waste on ground & walks away
        Core->>Logic: Waste stationary, Person distance > 110px
        Note over Logic: State: SEPARATING -> CONFIRMING
        loop 12 Consecutive Frames (~1.5s)
            Logic->>Logic: Verify waste remains stationary
        end
        Logic->>Core: Incident Verified (ID: INC-20260925-01)
        Core->>Core: Render bounding boxes & ALERT HUD
        Core->>DB: INSERT into events, images, alerts, sensor_data
        Core->>UI: Dispatch toast alert & update KPI counters
    end

    UI->>UI: Play alert chime, display live camera stream & evidence card
```

---

## 3. Spatiotemporal Dumping Activity Reasoning Engine

### 3.1 Why Bounding Boxes Alone Are Insufficient
A raw YOLO object detector detects objects in isolation (e.g., "Person: 0.91", "Backpack: 0.84"). Relying purely on single-frame detection leads to massive false-alarm rates:
- A commuter walking across the street with a bag would trigger an alert.
- Pre-existing roadside litter would trigger continuous alarms every 30 milliseconds.

### 3.2 State Machine Formalization

The sentinel implements a four-stage state machine:

```
[STATE 0: IDLE]
       |
       |  Person and Waste Candidate detected within distance < 85 px
       v
[STATE 1: CARRYING / TRANSIT]
       |
       |  Waste displacement < 15 px across frames (Stationary) AND
       |  Person distance expands > 85 px
       v
[STATE 2: SEPARATION CANDIDATE]
       |
       |  Waste remains stationary for N >= 12 consecutive frames AND
       |  Person exits perimeter (> 110 px) or exits camera view
       v
[STATE 3: VERIFIED ILLEGAL DUMPING] ---> Capture Evidence & Dispatch Alert
       |
       |  15-Second Cooldown Timer
       v
[STATE 4: SUPPRESSED / MONITORED]
```

---

## 4. Custom YOLOv8/v11 Training & Raspberry Pi Optimization

### 4.1 Dataset Collection & Class Strategy
For optimal performance in municipal deployment, train on 5 specialized classes:
1. `person`
2. `vehicle` (Cars, trucks, three-wheelers/auto-rickshaws)
3. `garbage_bag` (Plastic bags, tied trash sacks)
4. `plastic_bottle` (PET bottles, mineral water containers)
5. `packaging_box` (Cardboard cartons, packaging debris)

### 4.2 Annotation Guidelines
- Use **Roboflow** or **Label Studio** in YOLO darknet/txt format.
- Minimum recommended dataset size: **1,500 labeled images** covering daytime, dusk, nighttime (under Ring LED illumination), and rain/wet asphalt conditions.
- Perform mosaic augmentations and random affine transformations to simulate variable camera mounting angles.

### 4.3 Training Script Execution
```bash
# Execute custom training using train_yolo.py
python train_yolo.py --train
```

### 4.4 Model Export to NCNN (Direct Raspberry Pi 5 Acceleration)
Standard PyTorch (`.pt`) execution uses generic CPU kernels. Converting the model to **NCNN** leverages the ARM NEON vector SIMD instructions of the Cortex-A76 cores:
```bash
# Export trained model to NCNN format
yolo export model=runs/detect/smart_waste_sentinel_run/weights/best.pt format=ncnn imgsz=640
```
This reduces inference latency from ~95ms down to **~48ms**, enabling fluid 20+ FPS continuous surveillance!

---

## 5. REST API Specification

| Endpoint | Method | Response Type | Description |
|---|---|---|---|
| `/` | `GET` | HTML | Primary live monitoring surveillance dashboard |
| `/history` | `GET` | HTML | Searchable incident audit trail and forensic viewer |
| `/analytics` | `GET` | HTML | Circular waste composition and hourly charts |
| `/settings` | `GET` | HTML | Hardware threshold calibration and jury test panel |
| `/video_feed` | `GET` | `multipart/x-mixed-replace` | Real-time MJPEG live camera stream with AI HUD |
| `/api/sensor` | `GET` | JSON | Instantaneous BH1750 Lux, LED state, and mode |
| `/api/stats` | `GET` | JSON | Aggregated incident count, class distribution, avg Lux |
| `/api/alerts` | `GET` | JSON | Active FIFO alert queue for real-time dashboard notifications |
| `/api/events` | `GET` | JSON | Paginated database event records |
| `/api/toggle_led` | `POST` | JSON | Manual toggle override of GPIO 18 LED circuit |
| `/api/simulate_lux` | `POST` | JSON | Sets manual Lux override for jury demonstrations |
| `/api/manual_capture` | `POST` | JSON | Forces immediate snapshot capture and audit logging |
| `/incidents/<filename>` | `GET` | Image/JPEG | Serves forensic snapshot evidence |
