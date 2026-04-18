# Gesture-Controlled Lynxmotion LSS Robotic Arm

A system that uses hand gestures to control a Lynxmotion LSS 4-DoF robotic arm. Gestures are detected via a laptop camera using MediaPipe for hand landmark extraction and a trained SVM classifier for gesture recognition.

## How It Works

```
Camera -> MediaPipe (21 hand landmarks) -> SVM Classifier -> State Machine -> Arm Servos
```

1. The laptop camera captures your hand
2. MediaPipe extracts 21 hand landmarks (63 features: x, y, z per landmark)
3. A trained SVM model classifies the landmarks into a gesture name
4. The state machine triggers the corresponding arm behaviour
5. The arm controller sends safe, interpolated commands over serial

## Gestures and Behaviours

| Gesture | Show this | Arm behaviour |
|---------|-----------|---------------|
| OPEN_PALM | All 5 fingers open, palm facing camera | Move to HOME position |
| FIST | Make a fist | EMERGENCY STOP (from any state) |
| PEACE | Peace sign (index + middle up) | WAVE sequence |
| THUMBS_UP | Thumbs up | BOW |
| POINT | Index finger only up | REACH forward |

## Setup

### 1. Install dependencies

```bash
pip install mediapipe opencv-python numpy pandas scikit-learn pyserial
```

### 2. Capture gesture training data

Hold each gesture in front of the camera. The script captures 200 samples per gesture (~20 seconds each).

```bash
python "Camera Module/capture_landmarks.py"
```

Controls: SPACE = start capturing, S = skip gesture, Q = quit

### 3. Train the classifier

```bash
python "Camera Module/train_model.py"
```

This trains an SVM on the captured landmarks and saves `Camera Module/model+dataset/model.pkl`. You should see accuracy and a confusion matrix printed.

### 4. Run the system

```bash
python main.py
```

Controls: Q = quit, C = clear emergency stop

## Re-training

If accuracy drops (different lighting, different person, etc.), re-capture and retrain:

```bash
python "Camera Module/capture_landmarks.py"   # appends new data to the CSV
python "Camera Module/train_model.py"         # retrains on all data
```

## Configuration

All tuneable values are in `Arm Controller/config.py`:

- `SERIAL_PORT` — COM port for the arm (default: COM12)
- `CAMERA_INDEX` — camera index (default: 0)
- `GESTURE_STABLE_FRAMES` — consecutive identical detections before a gesture fires (default: 1)
- `INTERPOLATION_STEP` / `INTERPOLATION_DELAY` — movement smoothness
- `DEFAULT_SPEED` / `FAST_SPEED` — servo movement speed
- Servo limits and named poses

## Project Structure

```
AI_PROJ/
    main.py
    hand_landmarker.task
    gestures_dataset.csv
    Arm Controller/
        arm_controller.py
        behaviours.py
        config.py
        lss.py
        lss_const.py
    Camera Module/
        gesture_recogniser.py
        capture_landmarks.py
        train_model.py
        model+dataset/
            gestures_dataset.csv
            model.pkl
    Docs/
        CODE_GUIDE.md
```

## Safety

- All servo positions are clamped to safe mechanical limits
- FIST gesture triggers emergency stop from any state
- Movement is interpolated in small steps to prevent LSS failsafe shutdown
- System runs in simulation mode if the arm is not connected
- Graceful shutdown ensures the arm returns to HOME on exit
