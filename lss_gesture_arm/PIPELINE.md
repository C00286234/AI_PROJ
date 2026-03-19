# System Pipeline — Gesture-Controlled Lynxmotion LSS Robotic Arm

## 1. System Overview

The system has three physical components that work together:

```
┌─────────────────────┐     ┌──────────────────────┐
│   LAPTOP CAMERA (0) │     │  USB WEBCAM (1)       │
│   Faces YOU         │     │  Faces the WORKSPACE  │
│   Captures gestures │     │  Captures objects     │
└────────┬────────────┘     └──────────┬────────────┘
         │                             │
         ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                  main.py (Python)                   │
│                                                     │
│  gesture_recogniser.py    vision.py                 │
│  (MediaPipe Hands)        (OpenCV HSV detection)    │
│           │                       │                 │
│           └──────────┬────────────┘                 │
│                      ▼                              │
│               behaviours.py                         │
│               (State machine)                       │
│                      │                              │
│                      ▼                              │
│               arm_controller.py                     │
│               (Safety + serial commands)            │
└──────────────────────┬──────────────────────────────┘
                       │ USB Serial (COM7)
                       ▼
         ┌─────────────────────────┐
         │  Lynxmotion LSS Arm     │
         │  5 smart servos (1–5)   │
         │  Base / Bottom / Top /  │
         │  Wrist / Gripper        │
         └─────────────────────────┘
```

**You** show hand gestures to the laptop camera. The system recognises your gesture and triggers a behaviour. If that behaviour involves picking up an object, the USB webcam watches the workspace and guides the arm to align with the red object before descending.

---

## 2. The Main Loop — What Happens Every Frame

`main.py` runs a continuous loop at camera frame rate (~30 fps). Every iteration:

```
1. Read a frame from the GESTURE camera (laptop)
2. Read a frame from the WORKSPACE camera (USB webcam)
3. Pass gesture frame → GestureRecogniser.process_frame()
        → Returns: gesture name (or "NONE") + confidence
4. If gesture == "FIST":  trigger EMERGENCY_STOP immediately
   Else if gesture != "NONE": trigger the mapped behaviour
5. Call BehaviourEngine.update(workspace_frame)
        → State machine runs one tick
        → If in PICK_SCAN state: colour detection runs on workspace_frame
        → Arm moves if required
6. Draw overlays on both frames
7. Show both windows: "Gesture Camera (YOU)" and "Workspace Camera (ARM)"
8. Check for Q key (quit) or C key (clear estop)
9. Repeat
```

---

## 3. The Gesture Pipeline

How raw camera pixels become a confirmed gesture name:

```
Laptop camera frame (BGR)
        │
        ▼
  Flip horizontally (mirror so left/right match natural hand view)
        │
        ▼
  Convert BGR → RGB  (MediaPipe requires RGB)
        │
        ▼
  MediaPipe Hands model
  (neural network, detects 21 hand landmarks per hand)
        │
        ▼
  Hand landmarks (21 x,y,z coordinates in normalised 0–1 space)
        │
        ▼
  _classify() — finger extension logic:
  ┌──────────────────────────────────────────────────────┐
  │ For each finger (Index, Middle, Ring, Pinky):        │
  │   Extended = tip.y < PIP.y  (tip is higher up)      │
  │                                                      │
  │ For Thumb:                                           │
  │   Extended = tip.x < IP.x  (right hand)             │
  │            = tip.x > IP.x  (left hand)              │
  │                                                      │
  │ Compare [thumb, index, middle, ring, pinky] pattern  │
  │ against 6 known gesture patterns.                    │
  │ Best match score must be ≥ 0.8 (4/5 fingers match)  │
  └──────────────────────────────────────────────────────┘
        │
        ▼
  Raw gesture name (e.g. "POINT")
        │
        ▼
  Stability filter:
  ┌──────────────────────────────────────────────────────┐
  │ Count consecutive frames with same raw gesture.      │
  │ Only output a gesture name after 8 consecutive       │
  │ identical frames. This prevents accidental triggers  │
  │ from brief hand movements between gestures.          │
  └──────────────────────────────────────────────────────┘
        │
        ▼
  Stable gesture name → BehaviourEngine.trigger_gesture()
```

**Gesture patterns:**

| Gesture       | Thumb | Index | Middle | Ring  | Pinky |
|---------------|-------|-------|--------|-------|-------|
| OPEN_PALM     | ext   | ext   | ext    | ext   | ext   |
| FIST          | curl  | curl  | curl   | curl  | curl  |
| PEACE         | any   | ext   | ext    | curl  | curl  |
| THUMBS_UP     | ext   | curl  | curl   | curl  | curl  |
| POINT         | any   | ext   | curl   | curl  | curl  |
| THREE_FINGERS | any   | ext   | ext    | ext   | curl  |

---

## 4. The Colour Detection Pipeline

How the workspace camera finds the red object:

```
USB webcam frame (BGR)
        │
        ▼
  Convert BGR → HSV colour space
  (HSV separates colour (hue) from brightness,
   making detection robust to lighting changes)
        │
        ▼
  Build red mask — TWO ranges needed because red wraps
  around in HSV (0° and 360° are both red):
  ┌─────────────────────────────┐
  │ Mask 1: Hue 0–10   (red)   │
  │ Mask 2: Hue 170–180 (red)  │
  │ Combined with bitwise OR   │
  └─────────────────────────────┘
        │
        ▼
  Morphological OPEN  (3×3, 2 iterations)
  → Removes small noise specks from the mask
        │
        ▼
  Morphological CLOSE (5×5, 2 iterations)
  → Fills small holes inside the detected region
        │
        ▼
  cv2.findContours() — finds outlines of white regions in mask
        │
        ▼
  Pick the largest contour.
  Reject if area < 1500 px² (too small = noise, not an object)
        │
        ▼
  Compute centroid using image moments (M10/M00, M01/M00)
        │
        ▼
  Classify horizontal zone:
  ┌─────────────────────────────┐
  │ Frame divided into thirds:  │
  │  0–213px   → LEFT           │
  │  213–426px → CENTRE         │
  │  426–640px → RIGHT          │
  └─────────────────────────────┘
        │
        ▼
  ColourDetectionResult(found, bbox, centre_x, centre_y,
                        horizontal_zone, area)
  → Used by PICK_SCAN state to steer the arm base
```

---

## 5. The State Machine

The system is always in exactly one of 12 states. `BehaviourEngine.update()` is called once per frame and runs the current state's handler.

```
                    ┌──────────────────────────────────────────────────┐
                    │  FIST gesture fires from ANY state               │
                    │              │                                   │
                    │              ▼                                   │
                    │      EMERGENCY_STOP ◄─────────────────────────  │
                    │              │                                   │
                    │    OPEN_PALM gesture                             │
                    │              │                                   │
                    └──────────────┼───────────────────────────────────┘
                                   │
              ┌────────────────────▼──────────────────────┐
              │                  IDLE                      │
              └──┬──────┬──────────┬──────────┬───────────┘
                 │      │          │           │
           OPEN  │  PEACE│      POINT       THREE
           PALM  │      │          │        FINGERS
                 ▼      ▼          ▼           ▼
             HOMING   WAVING   PICK_SCAN    DEMO_POSE
               │        │         │            │
           go_home()  wave A↔B    │         demo pose
               │      × 2 then    │         + go_ready
               │      go_home     │            │
               ▼        │         │ aligned    ▼
             IDLE ◄──────┘         ▼          IDLE
                              PICK_DESCEND
                                   │
                                   ▼
                               PICK_GRIP
                                   │
                                   ▼
                               PICK_LIFT
                                   │
                               set carrying=True
                                   │
                                   ▼
                                 IDLE ◄── THUMBS_UP now available
                                   │
                             THUMBS_UP
                           (only if carrying)
                                   │
                                   ▼
                           PLACE_APPROACH
                                   │
                                   ▼
                            PLACE_DROP
                           (open gripper)
                                   │
                                   ▼
                           PLACE_RETREAT
                                   │
                                   ▼
                                 IDLE
```

**State transition rules:**
- EMERGENCY_STOP is reachable from every state without exception
- Only OPEN_PALM clears EMERGENCY_STOP (or press C on keyboard)
- PICK states form a strict one-way chain — no gesture can skip ahead
- PLACE is only reachable from IDLE when `arm.is_carrying() == True`
- HOMING, DEMO_POSE auto-return to IDLE when movement completes

---

## 6. The Pick-Up Sequence — Detailed

This is the most complex behaviour and earns the highest marks for complexity. It uses the workspace camera to guide the arm to the object.

### Phase 1 — PICK_SCAN

**Triggered by:** POINT gesture from IDLE

**Goal:** Rotate the base servo until the red object is centred in the workspace camera frame.

```
On entry:
  → Arm moves to POSE_SCAN (raised, looking forward)
  → scan_base = 0, scan_direction = +1, scan_attempts = 0

Every frame tick:
  → Run ColourDetector.detect_red(workspace_frame)

  If object FOUND:
    pixel_offset = object_centre_x - (frame_width / 2)
    base_delta   = pixel_offset × BASE_DEG_PER_PIXEL (0.8)
    new_base     = clamp(current_base + base_delta)
    move base servo smoothly to new_base

    If horizontal_zone == "CENTRE" for 5 consecutive frames:
      → Record aligned_base position
      → Transition to PICK_DESCEND

  If object NOT FOUND:
    → Sweep base left/right by 50 units per tick
    → On reaching limit: reverse direction, increment scan_attempts
    → After 3 full sweeps with no object: go_home() → IDLE (give up)
```

### Phase 2 — PICK_DESCEND

**Goal:** Lower the arm to the pick position directly above the object.

```
Safe joint order (prevents arm hitting surface):
  1. WRIST  → neutralise wrist angle first
  2. TOP    → fold top arm segment
  3. BOTTOM → lower bottom arm to table level

Base is locked to the aligned_base value from Phase 1.
→ Transition to PICK_GRIP when movement completes
```

### Phase 3 — PICK_GRIP

**Goal:** Close the gripper around the object and verify the grip.

```
gripper_close(600)   → closes to position 600 (out of max 750)
time.sleep(0.3)      → dwell to let gripper settle
get_position(SERVO_GRIPPER)  → read back actual position
  If position < 350: object may have slipped → retry at 700
→ Transition to PICK_LIFT
```

### Phase 4 — PICK_LIFT

**Goal:** Raise the arm with the object without dropping it.

```
Safe joint order (lifts object before folding):
  1. BOTTOM → raise the bottom arm first (lifts object off surface)
  2. TOP    → fold top arm
  3. WRIST  → adjust wrist to carry angle

set_carrying(True)   → enables THUMBS_UP gesture for placing
→ Transition to IDLE
```

---

## 7. The Safety System

### Emergency Stop
- FIST gesture is checked **before** anything else in `update()` on every frame
- Calls `arm.emergency_stop()` which sends `LSS_ActionHold` to all 5 servos simultaneously
- Sets `_estop = True` internally
- `move_servo_smooth()` checks `_estop` on every interpolation tick (every 30 ms)
- Only `clear_estop()` (via OPEN_PALM or C key) re-enables movement

### Position Clamping
Every single position value passes through `clamp()` before reaching the hardware:

```python
def clamp(self, servo_id, position):
    lo, hi = SERVO_LIMITS[servo_id]
    return max(lo, min(hi, int(position)))
```

Safe ranges (tenths of degrees):
- Base: -900 to +900
- Bottom arm: -900 to 0
- Top arm: 0 to 850
- Wrist: -800 to 0
- Gripper: 0 to 750

No code path can ever send a position outside these limits.

### Interpolated Movement
The LSS arm has a built-in failsafe that shuts down if it receives a command to jump too far too fast. `move_servo_smooth()` prevents this by stepping in increments of 30 units with a 0.03 second delay between steps (these values were derived empirically from `testRanges.py`).

```
Current pos: -200  →  Target: -700
Steps: -230, -260, -290, ... -670, -700
Delay: 0.03s between each step
Total ~16 steps × 0.03s = ~0.5 seconds for a 500-unit move
```

### Serial Error Handling
All LSS library calls are wrapped in try/except. If a serial exception occurs (cable disconnected, arm powered off), the error is logged and `_connected` is set to False — the main loop continues running in camera-only mode rather than crashing.

---

## 8. How the Two Cameras Split Responsibilities

```
┌──────────────────────────────────────────────────────────┐
│              LAPTOP CAMERA (index 0)                     │
│                                                          │
│  Input to:  GestureRecogniser.process_frame()            │
│  Output:    Stable gesture name every 8 frames           │
│  Used by:   BehaviourEngine.trigger_gesture()            │
│  Display:   "Gesture Camera (YOU)" window                │
│                                                          │
│  Physical:  Faces you at all times                       │
│  Never:     Used for object detection                    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              USB WEBCAM (index 1)                        │
│                                                          │
│  Input to:  BehaviourEngine.update(workspace_frame)      │
│             ColourDetector.detect_red() during PICK_SCAN │
│  Output:    ColourDetectionResult (zone, centroid, bbox) │
│  Used by:   _handle_pick_scan() to steer base servo      │
│  Display:   "Workspace Camera (ARM)" window              │
│                                                          │
│  Physical:  Mounted above or beside the workspace table  │
│             Fixed position — arm and objects in view     │
│  Never:     Used for gesture recognition                 │
└──────────────────────────────────────────────────────────┘
```

The two streams never mix. Gesture frames go only to MediaPipe. Workspace frames go only to OpenCV colour detection. Both windows are shown simultaneously so you can monitor both views during a demo.
