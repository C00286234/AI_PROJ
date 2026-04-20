# Code Guide - Gesture-Controlled Lynxmotion LSS Arm

This guide reflects the current code in this repository as of April 20, 2026.

## 1. What This Project Does

The system reads hand gestures from a camera using MediaPipe HandLandmarker + an SVM classifier, then drives a Lynxmotion LSS arm through a behavior engine.

Runtime pipeline:

```text
Camera frame
  -> GestureRecogniser (MediaPipe landmarks + SVM)
  -> BehaviourEngine (mode + state logic)
  -> ArmController (safety clamping + servo commands)
  -> LSS bus (or FakeServo simulation)
```

## 2. Current Project Layout

```text
AI_PROJ/
  main.py
  hand_landmarker.task
  README.md
  requirements.txt

  Arm Controller/
    arm_controller.py
    behaviours.py
    config.py
    lss.py
    lss_const.py

  Camera Module/
    capture_landmarks.py
    gesture_recogniser.py
    train_model.py
    hand_landmarker.task
    model+dataset/
      gestures_dataset.csv
      alt/
        gestures_dataset.csv
    alt/

  Docs/
    CODE_GUIDE.md
```

Notes:
- `main.py` imports modules by appending `Arm Controller` and `Camera Module` to `sys.path`.
- Runtime SVM model path is `Camera Module/model+dataset/model.pkl`.
- Runtime hand landmark model path in code is `hand_landmarker.task` at repo root.

## 3. Key Runtime Files

### `main.py`

Responsibilities:
- Initializes `ArmController`, `GestureRecogniser`, and `BehaviourEngine`.
- Opens camera with dimensions from config (`640x480`).
- Runs per-frame loop:
1. Read frame.
2. Get gesture from recogniser.
3. Send gesture to behavior engine every frame.
4. Update behavior engine.
5. Draw landmarks + HUD + legend.
6. Handle keyboard (`q` quit, `c` clear e-stop).

Important behavior:
- Default mode is automatic.
- Gestures are forwarded continuously each frame (manual controls can be continuous while a gesture is held).

### `Arm Controller/config.py`

Single source of constants:
- Serial: `SERIAL_PORT = "COM5"`, `SERIAL_BAUD = 115200`.
- Servo IDs: base, middle, top, wrist, gripper (`1..5`).
- Safety limits (`SERVO_LIMITS`) in tenths of degrees.
- Named poses: `POSE_HOME`, `POSE_READY`, `POSE_WAVE_A`, `POSE_WAVE_B`, `POSE_REACH`, `POSE_BOW`.
- Motion settings:
  - `SERVO_MAX_SPEED = 370`
  - `MOVE_COMPLETION_TIMEOUT = 2.5` (defined, not actively used by current arm motion code)
- Gesture stability:
  - `GESTURE_STABLE_FRAMES = 60`
- Supported label set:
  - `THUMBS_UP`, `OKAY_SIGN`, `THREE_FINGERS`, `OPEN_PALM`, `FIST`, `POINT`, `PEACE`

Practical effect of stability:
- At ~30 FPS, requiring 60 identical frames is about $60/30 = 2$ seconds before a stable gesture is emitted.

### `Camera Module/gesture_recogniser.py`

Responsibilities:
- Creates MediaPipe HandLandmarker (Tasks API, VIDEO mode, `num_hands=1`).
- Loads trained model bundle (`scaler` + `svm`) from `model.pkl`.
- For each frame:
1. Flip frame horizontally.
2. Convert BGR to RGB.
3. Detect hand landmarks.
4. Flatten 21 landmarks to 63 features.
5. Scale with `StandardScaler`.
6. Predict label with SVM.
7. Apply stability filter.

Output model:
- Returns a `GestureResult` with:
  - `name` (stable gesture)
  - `raw_name` (instantaneous SVM output)
  - `confidence` (currently fixed `1.0`)
  - `landmarks`

Failure behavior:
- If `model.pkl` is missing, startup raises `FileNotFoundError` with retraining instruction.
- If no hand is detected, stable output eventually returns `NONE`.

### `Arm Controller/behaviours.py`

Contains:
- State enum: `IDLE`, `HOMING`, `WAVING`, `REACHING`, `BOWING`, `EMERGENCY_STOP`
- `BehaviourEngine` that handles:
  - mode switching (automatic/manual)
  - state transitions
  - manual control actions

Mode logic:
- `THUMBS_UP` -> automatic mode.
- `OKAY_SIGN` -> manual mode.

Automatic mode actions (from `IDLE`, new gesture edge only):
- `OPEN_PALM` -> `HOMING`
- `POINT` -> `WAVING`
- `PEACE` -> `REACHING`
- `THREE_FINGERS` -> `BOWING`

Manual mode actions (continuous while gesture is held):
- `OPEN_PALM` -> gripper open step
- `FIST` -> gripper close step
- `POINT` -> base rotate right step
- `PEACE` -> base rotate left step
- `THREE_FINGERS` -> middle joint up step

Emergency stop behavior:
- `FIST` triggers e-stop only in automatic mode.
- In `EMERGENCY_STOP`, `OPEN_PALM` clears e-stop and returns to `IDLE`.

### `Arm Controller/arm_controller.py`

Hardware abstraction and safety:
- Connects to LSS bus if library is available.
- Falls back to `_FakeServo` simulation if not available.
- Clamps all servo targets through `SERVO_LIMITS`.
- Supports:
  - single servo movement
  - sequential pose movement
  - manual nudge controls
  - e-stop hold/clear

Important detail:
- Current `move_servo_smooth` implementation sends target directly then sleeps `0.2s` (it is not multi-step interpolation in this version).

### `Arm Controller/lss.py` and `Arm Controller/lss_const.py`

Bundled Lynxmotion serial protocol implementation used by `arm_controller.py`.

## 4. Data Collection and Training

### `Camera Module/capture_landmarks.py`

Purpose:
- Captures hand landmarks per gesture and appends rows to CSV.

Current settings:
- Gesture set comes from `config.SUPPORTED_GESTURES`.
- `SAMPLES_PER_GESTURE = 200`
- `CAPTURE_DELAY = 0.1` seconds.
- Output CSV path: `Camera Module/model+dataset/gestures_dataset.csv`.

Controls:
- `SPACE` start capture for current gesture.
- `S` skip gesture.
- `Q` quit.

### `Camera Module/train_model.py`

Purpose:
- Trains an SVM classifier and writes `model.pkl`.

Pipeline:
1. Load dataset CSV.
2. Split 80/20 with stratification.
3. Scale features with `StandardScaler`.
4. Train `SVC(kernel="rbf", C=1, gamma="scale")`.
5. Print accuracy, classification report, confusion matrix.
6. Save `{ "scaler": scaler, "svm": svm }` with `pickle`.

## 5. Gesture Reference (Current Implementation)

### Mode switching

| Gesture | Effect |
|---|---|
| `THUMBS_UP` | Switch to AUTOMATIC mode |
| `OKAY_SIGN` | Switch to MANUAL mode |

### Automatic mode

| Gesture | Effect |
|---|---|
| `FIST` | Emergency stop |
| `OPEN_PALM` | Home pose |
| `POINT` | Wave sequence |
| `PEACE` | Reach sequence |
| `THREE_FINGERS` | Bow sequence |

### Manual mode

| Gesture | Effect |
|---|---|
| `OPEN_PALM` | Gripper open (step) |
| `FIST` | Gripper close (step) |
| `POINT` | Base rotate right (step) |
| `PEACE` | Base rotate left (step) |
| `THREE_FINGERS` | Middle joint up (step) |

## 6. Run Commands (From Repo Root)

Install deps:

```bash
pip install -r requirements.txt
```

Capture dataset:

```bash
python "Camera Module/capture_landmarks.py"
```

Train model:

```bash
python "Camera Module/train_model.py"
```

Run system:

```bash
python main.py
```

Runtime keyboard controls:
- `q` -> quit
- `c` -> clear e-stop

## 7. Safety Summary

- Servo targets are clamped to configured mechanical limits.
- E-stop calls `hold()` on all servos and blocks normal movement.
- Disconnect path attempts to send arm home before closing bus.
- Simulation fallback allows camera/logic testing without hardware.

## 8. Maintenance Notes

- If you add gestures, keep these in sync:
1. `config.SUPPORTED_GESTURES`
2. captured CSV labels
3. trained model (`model.pkl`)
4. behavior mapping logic in `behaviours.py`
5. legend in `main.py`

- If module paths change, update both:
1. `sys.path.append(...)` in `main.py`
2. model/data path constants in camera scripts
