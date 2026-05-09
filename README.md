# YOLOV11n Powered Lane Hopping detection and Automated Traffic Violation Reporting System for Road Safety Enforcement

An automated road lane-violation detection system built on a small robot platform. The robot drives on a scaled road, detects when it crosses lane markings using an IR sensor, classifies the line type (yellow or white) using a YOLO vision model, and reports violations to a cloud server with snapshots and email notifications.

---

## Repository Structure

```
ntsa-robot/
├── server/              ← Node/Python backend deployed on Render
│   ├── app.py
│   ├── requirements.txt
│   └── ...
├── pi/                  ← Raspberry Pi vision + IR detection
│   └── NEWER_IR.py
├── esp32/               ← ESP32 motor control + BLE
│   └── motion.ino
└── README.md
```

---

## How the System Works

### The Two-Sensor Approach

The system uses two sensors working as a team because no single sensor can do both jobs reliably:

**IR Sensor (front-bottom of robot)**
Detects *that* a line was crossed. It shines infrared light downward — black tarmac absorbs it, white/yellow markings reflect it back. When reflection is detected, it fires a GPIO interrupt on the Pi. It does not know which line it crossed.

**Camera + YOLO (front-top of robot, angled downward)**
Detects *which* line was crossed. It runs a trained YOLO model continuously and keeps a rolling 1-second history of every line label it sees. When the IR fires, the Pi looks back into that history and picks the most recently seen label — yellow or white.

The camera sees the line slightly before the IR sensor physically crosses it (camera is higher and angled forward), so the 1-second lookback window reliably catches the correct classification.

### Violation Logic

| Line Crossed | Condition | Outcome |
|---|---|---|
| Yellow | Obstruction detected ahead | Emergency exception — no fine |
| Yellow | 1st or 2nd crossing | Warning issued |
| Yellow | 3rd crossing onwards | Fine issued |
| White | Obstruction detected ahead | Justified crossing — no action |
| White | 1–2 crossings in 3 minutes | Lane change noted |
| White | 3+ crossings in 3 minutes | Reckless driving fine |

Every violation event: saves a snapshot, generates a fine reference number, posts to the cloud server, and triggers an email to the driver.

---

## Hardware

### Raspberry Pi 4 (Vision + IR)

| Component | Detail |
|---|---|
| Camera | Raspberry Pi Camera Module (front-top, angled downward) |
| IR Sensor | TCRT5000-based reflectance module (front-bottom, ~15mm from ground) |
| OS | Raspberry Pi OS (64-bit) |
| Python | 3.9+ |

**IR Sensor Wiring (Pi 4 physical pins):**

```
IR Sensor Pin    →    Raspberry Pi 4 Pin
─────────────────────────────────────────
VCC              →    Pin 1  (3.3V)
GND              →    Pin 6  (GND)
OUT              →    Pin 12 (GPIO 18 / BCM 18)
```

> Use 3.3V not 5V. Pi GPIO pins are 3.3V tolerant only.
> Mount IR sensor centred on the vehicle underside, ~15mm from the road surface.
> Adjust the onboard potentiometer until the sensor reliably triggers on white/yellow markings but stays inactive on black tarmac.

### ESP32 (Motor Control)

| Component    |   Detail     |
|--------------|-----------|
| Motor Driver | HW-094 (L298N compatible) |
| IMU          | MPU6050 (I2C: SDA=21, SCL=22) |
| Control      | BLE UART (any BLE joystick app) |

**ESP32 Pin Mapping:**

```
LEFT  motor  →  IN1=33, IN2=13, PWM(ENA)=14
RIGHT motor  →  IN1=26, IN2=27, PWM(ENB)=25
```

**BLE Commands:**

| Key | Action |
|---|---|
| `F` | Forward |
| `B` | Backward |
| `R` | Spin right |
| `L` | Spin left |
| `S` | Stop |
| `A` | Auto/gyro straight mode |
| `M` | Manual mode |
| `C` | Recalibrate gyro |
| `D` | Hardware diagnostic report |
| `V` | Toggle live IMU stream |
| `1` / `2` | Speed down / up (±10) |
| `3` / `4` | Min / max speed |
| `75.0` etc | Speed slider (0–100%) |

The ESP32 uses the MPU6050 gyroscope to self-correct drift during straight-line driving. On startup it auto-calibrates for 2 seconds — keep the robot still during this time.

---

## Software Setup

### Raspberry Pi

**1. Install dependencies:**
```bash
pip install ultralytics picamera2 RPi.GPIO Pillow opencv-python requests
```

**2. Place your trained YOLO model:**
```bash
# The model folder should sit next to NEWER_IR.py
pi/
├── NEWER_IR.py
└── best_ncnn_model/      ← YOLO NCNN export
    ├── metadata.yaml
    └── ...
```

**3. Configure at the top of `NEWER_IR.py`:**
```python
VEHICLE_PLATE     = "KBQ987D"         # your vehicle plate
DRIVER_EMAIL      = "driver@gmail.com" # email to notify on violation
CLOUD_SERVER_URL  = "https://your-server.onrender.com"
IR_SENSOR_PIN     = 18                # BCM GPIO pin for IR OUT
IR_ACTIVE_LOW     = True              # True for most IR modules
IR_YOLO_LOOKBACK_SECONDS = 1.0        # widen if robot moves fast
```

**4. Run:**
```bash
cd pi/
python3 NEWER_IR.py
```

### ESP32

**1. Install Arduino libraries** (via Arduino Library Manager):
- `Adafruit MPU6050`
- `Adafruit Unified Sensor`
- `ESP32 BLE Arduino` (included with ESP32 board package)

**2. Board settings in Arduino IDE:**
```
Board   : ESP32 Dev Module
Upload Speed : 921600
```

**3. Flash `motion.ino`** and open Serial Monitor at 115200 baud to confirm MPU6050 is found and gyro calibration completes.

**4. Connect** via any BLE UART app (e.g. "Serial Bluetooth Terminal" on Android) — device name is `ESP32_Robot`.

### Cloud Server (Render)

The server receives violation reports from the Pi and sends email notifications to the driver.

**Environment variables to set in Render dashboard** (Settings → Environment):
```
GMAIL_ADDRESS      = your-sending-gmail@gmail.com
GMAIL_APP_PASSWORD = xxxx xxxx xxxx xxxx
```

> Gmail App Passwords require 2-Step Verification to be enabled on the sending account.
> Go to myaccount.google.com/apppasswords to generate one.

**API endpoint the Pi posts to:**
```
POST /api/violation
Content-Type: application/json

{
  "fine_ref":           "NTSA-2026-05-05-KBQ987D-0001",
  "vehicle_plate":      "KBQ987D",
  "driver_email":       "driver@gmail.com",
  "date":               "2026-05-05",
  "time":               "14:32:01",
  "session_violations": 1,
  "total_violations":   1,
  "offence":            "Yellow line crossed - warning issued",
  "image_b64":          "<base64 encoded jpeg or empty string>"
}
```

---

## Repo + Render Setup

This repo contains code for three separate systems. Render only deploys the `server/` folder — it ignores the Pi and ESP32 code entirely.

**To configure Render to deploy only the server:**
```
Render Dashboard → your service → Settings → Root Directory → server
```

After setting this, any push to the repo will redeploy only the server folder.

---

## Troubleshooting

**IR sensor triggers but no violation fires**
- Check the terminal for `[IR] Triggered but no line seen by YOLO` — if this appears, widen `IR_YOLO_LOOKBACK_SECONDS` or slow the robot down
- Confirm YOLO is detecting lines: look for `yellow_line` / `white_line` labels in the live display

**IR sensor never triggers**
- Check wiring (VCC to 3.3V, not 5V)
- Adjust the potentiometer on the IR module — turn it slowly until the indicator LED flicks on when over a white/yellow line and off on black tarmac
- Confirm `IR_ACTIVE_LOW = True` matches your module's behaviour

**Violations not appearing on web dashboard**
- Run `curl -X POST https://your-server.onrender.com/api/violation ...` from the Pi terminal to test the connection directly
- Check Render logs for errors

**No email received**
- Check spam folder first
- Confirm `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are set in Render's environment variables panel, not just in local code
- Verify 2-Step Verification is enabled on the Gmail account

**ESP32 drifting during straight runs**
- Send `C` over BLE to recalibrate the gyro (keep robot still for 2 seconds)
- If it corrects in the wrong direction, swap the correction sign in `driveStraightWithCorrection()` in `motion.ino`
- Increase `kP` if drift is persistent; decrease if the robot wobbles side to side

**MPU6050 not found on ESP32**
- Check I2C wiring: SDA=21, SCL=22, VCC=3.3V
- Confirm no other device is conflicting on the I2C bus

---

## Fine Reference Format

```
WARN-YYYY-MM-DD-[PLATE]-[COUNT]       ← yellow line warning
NTSA-YYYY-MM-DD-[PLATE]-[COUNT]       ← yellow line fine
RECKLESS-YYYY-MM-DD-[PLATE]-[COUNT]   ← white line reckless fine
EXCPT-YYYY-MM-DD-[PLATE]-[COUNT]      ← emergency exception (obstruction)
```

---

## Left-Hand Traffic Note

This system is configured for **Kenyan left-hand traffic rules**:
- Yellow continuous centre line is on the **right side** of the vehicle
- Crossing the yellow line is the more serious offence (oncoming traffic lane)
- White broken lines separate same-direction lanes
