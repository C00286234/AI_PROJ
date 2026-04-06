# Code Guide — Gesture-Controlled Lynxmotion LSS Robotic Arm

A complete walkthrough of every file in the project. The system uses a laptop camera to recognise hand gestures via MediaPipe, classifies them with a trained SVM model, and triggers behaviours on a Lynxmotion LSS 4-DoF robotic arm over serial.

---

## System Architecture

```
                    Laptop Camera (index 0)
                           |
                           v
                  +-----------------+
                  |  main.py        |  Main loop (~30 fps)
                  |                 |
                  |  Read frame     |
                  |       |         |
                  |       v         |
                  |  gesture_       |
                  |  recogniser.py  |
                  |  (MediaPipe +   |
                  |   trained SVM)  |
                  |       |         |
                  |  gesture name   |
                  |       |         |
                  |       v         |
                  |  behaviours.py  |
                  |  (state machine)|
                  |       |         |
                  |       v         |
                  |  arm_           |
                  |  controller.py  |
                  |  (safety +      |
                  |   serial cmds)  |
                  +-----------------+
                           |
                    USB Serial (COM12)
                           |
                           v
                  +-----------------+
                  | Lynxmotion LSS  |
                  | 5 servos:       |
                  |  1=Base         |
                  |  2=Bottom arm   |
                  |  3=Top arm      |
                  |  4=Wrist        |
                  |  5=Gripper      |
                  +-----------------+
```

---

## File Overview

| File | Purpose |
|------|---------|
| `config.py` | All constants: servo IDs, limits, poses, speeds, camera, gesture mapping |
| `gesture_recogniser.py` | MediaPipe landmark detection + SVM classification + stability filter |
| `behaviours.py` | 7-state machine mapping gestures to arm behaviours |
| `arm_controller.py` | Servo communication with safety clamping and smooth interpolation |
| `main.py` | Entry point: camera loop, gesture routing, HUD display |
| `lss.py` | Lynxmotion serial protocol library (bundled, LGPL-3.0) |
| `lss_const.py` | LSS protocol constants (bundled, LGPL-3.0) |
| `capture_landmarks.py` | Data collection tool: captures MediaPipe landmarks to CSV |
| `train_model.py` | Trains SVM classifier on captured landmarks, outputs model.pkl |
| `gestures_dataset.csv` | Training data: 1200 samples (200 per gesture x 6 gestures) |
| `model.pkl` | Trained SVM model + StandardScaler (loaded at runtime) |
| `hand_landmarker.task` | MediaPipe hand landmark model (~4 MB, auto-downloaded on first run) |

---

## 1. `config.py` — Constants

All tuneable values live here. Nothing in this file changes at runtime.

### Serial Connection
```python
SERIAL_PORT = "COM12"
SERIAL_BAUD = 115200
```
The Windows COM port for the LSS arm's USB adapter. 115200 is the default LSS baud rate.

### Servo IDs and Limits
Each servo has a unique ID (1-5) and safe position limits in tenths-of-degrees:

| Servo | ID | Min | Max | Notes |
|-------|----|-----|-----|-------|
| Base | 1 | -900 | 900 | Full rotation range |
| Bottom | 2 | -900 | 0 | -900 = parallel to ground |
| Top | 3 | 0 | 850 | 850 = parallel to bottom arm |
| Wrist | 4 | -800 | 0 | -800 = straight up |
| Gripper | 5 | 0 | 750 | 0 = open, 750 = fully closed |

The `clamp()` function in `arm_controller.py` enforces these limits on every command.

### Named Poses
Pre-defined joint positions for common arm configurations:

- **POSE_HOME** — Arm folded down, gripper open. Safe resting state.
- **POSE_READY** — Arm raised to working height.
- **POSE_WAVE_A / POSE_WAVE_B** — Two positions for the wave sequence (base swings left/right).
- **POSE_DEMO** — A demonstration pose with partial gripper close.
- **POSE_REACH** — Arm extended forward.
- **POSE_BOW** — Arm lowered in a bow motion.

### Movement Parameters
```python
DEFAULT_SPEED       = 50    # tenths-of-degrees per second
FAST_SPEED          = 100   # used for wave / demo
INTERPOLATION_STEP  = 5     # position delta per tick
INTERPOLATION_DELAY = 0.1   # seconds between ticks
```
Movement is interpolated in small steps to avoid triggering the LSS built-in failsafe, which shuts the arm down if it receives a large position jump.

### Gesture Settings
```python
GESTURE_STABLE_FRAMES = 1   # consecutive identical detections before firing
```
Set to 1 for immediate response. Increase to 5-8 for production to prevent accidental triggers.

### Gesture-to-Behaviour Mapping
```python
GESTURE_BEHAVIOUR_MAP = {
    "OPEN_PALM":     "HOME",
    "FIST":          "EMERGENCY_STOP",
    "PEACE":         "WAVE",
    "THUMBS_UP":     "BOW",
    "POINT":         "REACH",
    "THREE_FINGERS": "DEMO_POSE",
}
```

---

## 2. `gesture_recogniser.py` — Gesture Detection

This is the core AI component. It combines two models:
1. **MediaPipe HandLandmarker** — a neural network that detects 21 hand landmarks (x, y, z coordinates) from a camera frame
2. **Trained SVM classifier** — takes those 63 features (21 landmarks x 3 coords) and predicts which gesture is being shown

### The ML Pipeline

```
Camera frame (BGR)
       |
       v
  Flip horizontally (mirror view)
       |
       v
  Convert BGR -> RGB
       |
       v
  MediaPipe HandLandmarker
  (neural network, detects 21 hand landmarks)
       |
       v
  21 landmarks -> flatten to 63 floats [x0, y0, z0, x1, y1, z1, ...]
       |
       v
  StandardScaler.transform()  (normalise features, same scaling as training)
       |
       v
  SVM.predict()  (trained on our captured hand data)
       |
       v
  Raw gesture name (e.g. "POINT")
       |
       v
  Stability filter (N consecutive identical frames required)
       |
       v
  Stable gesture name -> passed to BehaviourEngine
```

### How the SVM Replaced Rule-Based Classification

Previously, `_classify()` used hand-coded rules checking which fingers were extended:
```python
# Old approach: if thumb up and all others down -> THUMBS_UP
patterns = {"THUMBS_UP": [True, False, False, False, False], ...}
```

Now, `_classify()` feeds the raw landmark coordinates into the trained SVM:
```python
# New approach: let the model decide based on training data
features = [lm.x, lm.y, lm.z for each landmark]
scaled = self._scaler.transform([features])
name = self._svm.predict(scaled)[0]
```

The SVM approach is better because:
- It learns from YOUR actual hand shapes, not generic geometric rules
- It can capture subtle differences that simple up/down checks miss
- Adding a new gesture only requires capturing more data and retraining

### Fallback
If `model.pkl` is missing, the old rule-based logic is still present as a fallback so the system never fails to start.

### Stability Filter
```python
def _apply_stability(self, raw: str) -> None:
    if raw == self._last_raw:
        self._stable_count += 1
    else:
        self._stable_count = 1
        self._last_raw = raw

    if self._stable_count >= config.GESTURE_STABLE_FRAMES:
        self._stable_gesture = raw
```
A gesture must be detected identically for `GESTURE_STABLE_FRAMES` consecutive frames before it fires. This prevents accidental triggers from transitional hand shapes.

### Drawing
`draw_landmarks()` renders the hand skeleton and detected gesture name on the camera frame for the live display window.

---

## 3. `arm_controller.py` — Servo Control

The only module that sends commands to the physical arm. Every position is safety-clamped before reaching hardware.

### Safety Contract
1. Every position passes through `clamp()` — it is impossible to exceed safe limits
2. `move_servo_smooth()` checks `_estop` on every interpolation tick
3. Serial exceptions are caught and logged, never crash the main loop

### Key Methods

**`clamp(servo_id, position)`** — The most critical safety function:
```python
lo, hi = config.SERVO_LIMITS[servo_id]
return max(lo, min(hi, int(position)))
```

**`move_servo_smooth(servo_id, target, step, delay)`** — Interpolated movement:
```
current = -200, target = -700, step = 5
Tick 1: send -205, sleep 0.1s
Tick 2: send -210, sleep 0.1s
...
Final:  send -700, done
```
Each tick checks `_estop`. If emergency stop fires, the next tick aborts.

**`move_pose_sequential(pose, order, speed)`** — Moves servos one at a time in a specified order. The order matters for safety:
- Wrist first when descending (prevent wrist hitting the table)
- Bottom first when lifting (raise object off surface before folding)

**`emergency_stop()`** — Sends `hold()` to all 5 servos immediately, sets `_estop = True`.

**`clear_estop()`** — Resets `_estop = False`. Only way to re-enable movement.

### Simulation Mode
If the LSS library is not available (no arm connected), `_FakeServo` objects are used. The entire system runs identically in camera-only mode for development/testing.

---

## 4. `behaviours.py` — State Machine

Coordinates gestures and arm movements through 7 states.

### States
```python
class State(Enum):
    IDLE            # Waiting for gesture input
    HOMING          # Moving to HOME position
    WAVING          # Executing wave sequence (4 swings + home)
    REACHING        # Extending arm forward
    BOWING          # Performing bow motion
    DEMO_POSE       # Showing demo position
    EMERGENCY_STOP  # All servos held, waiting for OPEN_PALM to clear
```

### State Diagram
```
              FIST (from ANY state)
                     |
                     v
              EMERGENCY_STOP
                     |
               OPEN_PALM
                     |
                     v
    +-------------IDLE--------------+
    |       |        |       |      |
 OPEN_PALM PEACE   POINT  THUMBS  THREE
    |       |        |     _UP     _FINGERS
    v       v        v      |       |
 HOMING  WAVING  REACHING  v       v
    |       |        |    BOWING  DEMO_POSE
    |   (4 swings)   |      |       |
    |       |      (hold)  (hold)  (hold)
    v       v      1 sec   1 sec   1 sec
   IDLE    IDLE      |      |       |
                  go_ready  |       |
                     |      v       v
                     v    IDLE    IDLE
                   IDLE
```

### How It Works

`update()` is called once per frame from the main loop:
1. Consume the pending gesture (set by `trigger_gesture()`)
2. If FIST: emergency stop immediately (checked before anything else)
3. Dispatch to the current state's handler
4. Return current state for HUD display

Each handler executes its behaviour (blocking arm movements) then transitions back to IDLE.

---

## 5. `main.py` — Entry Point

### Startup Sequence
```
1. Create ArmController, GestureRecogniser
2. arm.connect()         -> serial connection (or simulation mode)
3. recogniser.start()    -> MediaPipe + load SVM model
4. Open camera           -> 640x480
5. Create BehaviourEngine
6. Enter main loop
```

### Main Loop (runs at ~30 fps)
```
1. Read camera frame
2. gesture_result = recogniser.process_frame(frame)
3. If FIST:  trigger emergency stop
   Else if not NONE: trigger the gesture's behaviour
4. engine.update()  -> state machine runs one tick
5. Draw hand skeleton + HUD overlay + gesture legend
6. Display window
7. Check Q (quit) or C (clear estop)
```

### HUD Display
- Top bar: current state (green=IDLE, orange=active, red=EMERGENCY_STOP)
- Bottom: gesture-to-behaviour legend
- Hand skeleton drawn with landmark dots and connections

### Shutdown (finally block)
```
arm.disconnect()   -> go_home() then close serial
recogniser.stop()  -> release MediaPipe
cap.release()      -> release camera
cv2.destroyAllWindows()
```
Runs even on exceptions/KeyboardInterrupt, ensuring the arm always returns home.

---

## 6. `lss.py` / `lss_const.py` — LSS Protocol

The official Lynxmotion Python library (LGPL-3.0), bundled because it is not on PyPI.

### Protocol Format
Commands sent to servos: `#<ID><COMMAND><VALUE>\r`
- `#2D-500\r` = servo 2, move to position -500
- `#1H\r` = servo 1, hold current position
- `#3LED2\r` = servo 3, set LED to green

### Key Methods Used
- `LSS(id)` — create a servo object
- `.move(pos)` — move to absolute position
- `.hold()` — lock servo in place
- `.getPosition()` — read current position
- `initBus(port, baud)` / `closeBus()` — open/close serial connection

---

## 7. `capture_landmarks.py` — Data Collection

Collects training data by recording MediaPipe hand landmarks while you hold each gesture.

### Usage
```
python capture_landmarks.py
```

### How It Works
1. Cycles through all 6 gestures
2. For each gesture: shows live camera preview with hand skeleton
3. Press SPACE to start capturing — records 200 samples (~20 seconds)
4. Each sample: MediaPipe extracts 21 landmarks -> flattened to 63 floats (x,y,z per landmark)
5. Saved to `gestures_dataset.csv` with columns: `lm0_x, lm0_y, lm0_z, ..., lm20_z, label`

### Controls
- SPACE — start capturing (requires hand visible)
- S — skip to next gesture
- Q — quit early

### Output
`gestures_dataset.csv` — 1200 rows (200 per gesture), 64 columns (63 features + label). Appends if run again.

---

## 8. `train_model.py` — Model Training

Trains an SVM classifier on the captured landmark data.

### Usage
```
python train_model.py
```

### Pipeline
1. **Load** `gestures_dataset.csv`
2. **Split** 80% train / 20% test (stratified by gesture)
3. **Scale** features with `StandardScaler` (SVM requires normalised inputs)
4. **Train** `SVC(kernel="rbf", C=10, gamma="scale")`
5. **Evaluate** — prints accuracy, per-gesture precision/recall, confusion matrix
6. **Save** scaler + SVM together as `model.pkl`

### Why SVM?
- Works well on small, structured datasets (1200 samples x 63 features)
- RBF kernel handles non-linear gesture boundaries
- Fast prediction at runtime (important for real-time ~30 fps loop)
- Feature scaling via StandardScaler is saved alongside the model so the same transformation is applied at runtime

### Output
`model.pkl` — a pickle file containing `{"scaler": StandardScaler, "svm": SVC}`, loaded by `gesture_recogniser.py` on startup.

---

## 9. How to Run the Full System

### First Time Setup
```bash
# 1. Install dependencies
pip install mediapipe opencv-python numpy pandas scikit-learn

# 2. Capture your gesture data
python capture_landmarks.py

# 3. Train the model
python train_model.py

# 4. Run the system
python main.py
```

### Re-training
If gesture accuracy drops (different lighting, different person):
```bash
python capture_landmarks.py   # appends new data
python train_model.py          # retrains on all data
python main.py                 # uses updated model
```

### Controls During Operation
| Input | Action |
|-------|--------|
| OPEN_PALM gesture | Move arm to HOME position |
| FIST gesture | Emergency stop (from any state) |
| PEACE gesture | Wave sequence |
| THUMBS_UP gesture | Bow |
| POINT gesture | Reach forward |
| THREE_FINGERS gesture | Demo pose |
| Q key | Quit |
| C key | Clear emergency stop |

---

## 10. Safety Design

Safety is layered at multiple levels:

1. **Position clamping** — `clamp()` makes it impossible to exceed safe servo limits
2. **Interpolated movement** — small steps prevent LSS failsafe shutdown
3. **Emergency stop** — FIST gesture checked first on every frame, overrides any state
4. **E-stop latency** — maximum 100ms (one interpolation tick) before movement halts
5. **Sequential joint ordering** — prevents arm segments from colliding
6. **Graceful shutdown** — `finally` block ensures arm goes home even on crash
7. **Simulation mode** — system runs without arm connected for safe development
