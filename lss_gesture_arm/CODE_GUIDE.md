# Code Guide — File-by-File Walkthrough

Every file, class, and function explained section by section.

---

## 1. `config.py` — The Single Source of Truth

**Responsibility:** Stores every constant used across the project. No logic lives here — only values. Every other module imports from config but nothing ever writes to it at runtime.

### Serial Connection
```python
SERIAL_PORT = "COM7"
SERIAL_BAUD = 115200
```
`COM7` is the Windows serial port that the LSS arm's USB adapter appears on. `115200` is the default baud rate for LSS servos (defined in `lss_const.py` as `LSS_DefaultBaud`).

### Servo IDs
```python
SERVO_BASE=1, SERVO_BOTTOM=2, SERVO_TOP=3, SERVO_WRIST=4, SERVO_GRIPPER=5
```
Each physical servo has a unique ID burned into its firmware. The ID is what you use to address it in serial commands. Using named constants (not raw numbers) throughout the code means if an ID ever changes, you update it in one place only.

### Servo Limits
```python
SERVO_LIMITS = {
    SERVO_BASE:    (-900,  900),
    SERVO_BOTTOM:  (-900,    0),
    SERVO_TOP:     (   0,  850),
    SERVO_WRIST:   (-800,    0),
    SERVO_GRIPPER: (   0,  750),
}
```
All positions are in tenths-of-degrees (so 900 = 90.0°). These are the safe mechanical limits discovered from `testRanges.py`. The `clamp()` function in `arm_controller.py` uses this dict to ensure no command ever exceeds these values. Exceeding them causes the arm's built-in failsafe to shut it down.

### Named Poses
Each pose is a dict mapping servo ID → target position. Key poses:
- **POSE_HOME**: Arm folded down safely, gripper open. Safe resting state.
- **POSE_READY**: Arm raised to working height, ready to receive commands.
- **POSE_SCAN**: Arm raised and extended forward so the camera has a clear view of the workspace.
- **POSE_PICK_DOWN**: Arm lowered to table level for gripping. Base is set dynamically at runtime.
- **POSE_CARRY**: Arm raised holding an object. Gripper value (600) reflects a closed grip.
- **POSE_DROP_ZONE**: Fixed position to the right side where the arm places objects.
- **POSE_WAVE_A / POSE_WAVE_B**: Two alternating positions used for the wave sequence.

### Movement Constants
```python
DEFAULT_SPEED       = 300   # tenths-of-degrees per second
FAST_SPEED          = 600
INTERPOLATION_STEP  = 30    # position units per tick
INTERPOLATION_DELAY = 0.03  # seconds between ticks
```
`INTERPOLATION_STEP` and `INTERPOLATION_DELAY` were taken directly from the empirical timing in `testRanges.py` (the original test code used `time.sleep(.03)`). This is the minimum delay for smooth servo movement without triggering the LSS failsafe.

### Gesture Stability
```python
GESTURE_STABLE_FRAMES = 8
```
A gesture must be detected identically for 8 consecutive frames before it fires. At 30 fps, that is ~0.27 seconds of consistent hand position. This prevents accidental triggers from transitional hand shapes between gestures.

### Colour Detection (HSV)
```python
RED_HSV_LOWER_1 = (  0, 120,  70)
RED_HSV_UPPER_1 = ( 10, 255, 255)
RED_HSV_LOWER_2 = (170, 120,  70)
RED_HSV_UPPER_2 = (180, 255, 255)
MIN_COLOUR_AREA = 1500
```
Red is unusual in HSV: the hue wraps around at 180°, so red appears at both ends (0–10° and 170–180°). Two masks are needed and combined with OR. The saturation minimum of 120 excludes white/grey objects. The value minimum of 70 excludes very dark objects. `MIN_COLOUR_AREA` of 1500 px² rejects small noise blobs.

### Cameras
```python
CAMERA_GESTURE_INDEX = 0   # laptop built-in → faces user
CAMERA_VISION_INDEX  = 1   # USB webcam → faces workspace
```
Separated so that gesture recognition and object detection never share a camera feed.

### Calibration
```python
BASE_DEG_PER_PIXEL = 0.8
```
How many servo units (tenths-of-degrees) to rotate the base per pixel that the object is off-centre in the camera frame. At 640px wide and 0.8 units/px, the full frame width represents 512 servo units — close to the full ±900 base range. **This must be tuned empirically on the actual arm.**

---

## 2. `lss_const.py` — LSS Protocol Constants

**Responsibility:** Defines all string and numeric constants used by the LSS serial protocol. This is the official library file from Lynxmotion (LGPL-3.0).

### What is the LSS Protocol?
The Lynxmotion Smart Servo communicates over serial (UART). Commands are ASCII strings in the format:
```
#<ID><COMMAND><VALUE>\r
```
For example: `#2D-500\r` means "servo ID 2, move (D) to position -500".

Responses from the servo use `*` instead of `#`:
```
*<ID><COMMAND><VALUE>\r
```

### Key Constant Groups

**Communication basics:**
```python
LSS_CommandStart    = "#"     # start of every command sent to servo
LSS_CommandReplyStart = "*"   # start of every reply from servo
LSS_CommandEnd      = "\r"    # carriage return terminates every packet
LSS_DefaultBaud     = 115200  # serial baud rate
```

**LED colours (0–7):**
```python
LSS_LED_Black=0, LSS_LED_Red=1, LSS_LED_Green=2, LSS_LED_Blue=3 ...
```

**Action commands (sent to servo):**
```python
LSS_ActionMove     = "D"    # move to absolute position
LSS_ActionHold     = "H"    # lock servo in current position
LSS_ActionLimp     = "L"    # release servo (goes limp)
LSS_ActionColorLED = "LED"  # set LED colour
```

**Query commands (read from servo):**
```python
LSS_QueryPosition  = "QD"   # read current position
LSS_QueryStatus    = "Q"    # read servo status
LSS_QueryVoltage   = "QV"   # read voltage
```

---

## 3. `lss.py` — LSS Serial Communication Library

**Responsibility:** Implements the actual serial communication with LSS servos. This is the official Lynxmotion Python library (LGPL-3.0), bundled in the project folder because it is not on PyPI.

### Module-level functions

#### `initBus(portName, portBaud)`
Opens the serial port and stores it as a class attribute on `LSS.bus`. All servo objects share the same bus object (one serial connection for all servos).
```python
LSS.bus = serial.Serial(portName, portBaud)
LSS.bus.timeout = 0.1  # 100ms read timeout prevents hanging
```

#### `closeBus()`
Closes and deletes the serial connection cleanly. Called on shutdown.

#### `genericWrite(id, cmd, param=None)`
Builds and sends a command string to the serial bus:
```python
# Without parameter:  "#2H\r"  (servo 2, hold)
# With parameter:     "#2D-500\r"  (servo 2, move to -500)
LSS.bus.write((LSS_CommandStart + str(id) + cmd + str(param) + LSS_CommandEnd).encode())
```

#### `genericRead_Blocking_int(id, cmd)`
Reads a response from the bus and parses the integer value out of it:
1. Reads bytes until it finds the `*` start character
2. Reads until it finds the `\r` end character
3. Uses regex `r"(\d{1,3})([A-Z]{1,4})(-?\d{1,18})"` to parse ID, command, and value
4. Validates the ID and command match what was requested
5. Returns the value string (caller must cast to int), or `None` on any failure

The `None` return on failure is important — `arm_controller.py` always guards against it with `int(pos) if pos is not None else cached_value`.

### `LSS` Class

Each LSS servo gets one instance. All instances share `LSS.bus`.

```python
myServo = lss.LSS(2)   # create object for servo ID 2
```

**Key methods used by the project:**
- `move(pos)` — sends `#<id>D<pos>\r` — moves to absolute position
- `hold()` — sends `#<id>H\r` — locks servo in place (used for emergency stop)
- `getPosition()` — queries and returns current position as a string
- `setColorLED(color)` — sets the servo's LED colour

---

## 4. `arm_controller.py` — Low-Level Arm Control

**Responsibility:** The only module that ever sends commands to the physical arm. Every position passes through safety clamping. Provides smooth interpolated movement and named pose helpers.

### `_FakeServo` class

A simulation stub used when the LSS library is not connected (offline development). Implements the same interface as `lss.LSS` so the rest of the code works identically with or without the arm plugged in.

### `ArmController` class

#### `__init__()`
Initialises empty dicts for servo objects and cached positions. `_estop = False` and `_carrying = False`.

#### `connect() → bool`
- If LSS available: calls `lss.initBus()`, creates one `lss.LSS` object per servo ID
- If LSS not available: creates `_FakeServo` objects for each servo (simulation mode)
- Reads back current positions from hardware to initialise the position cache
- Returns `True` on success, `False` if serial connection fails

#### `disconnect()`
Calls `go_home()` first (moves arm to safe position), then `lss.closeBus()`. Safe shutdown sequence.

#### `clamp(servo_id, position) → int`
**The most critical safety function in the entire project.** Every single position value goes through this before touching hardware.
```python
lo, hi = config.SERVO_LIMITS[servo_id]
return max(lo, min(hi, int(position)))
```
It is mathematically impossible for any clamped value to exceed the servo's safe range. No exceptions, no edge cases.

#### `emergency_stop()`
Sets `_estop = True`, then calls `.hold()` on all 5 servos. The hold command locks each servo in its current position immediately. The `_estop` flag is then checked inside `move_servo_smooth()` so any in-progress movement aborts at the next tick (≤30 ms).

#### `clear_estop()`
Resets `_estop = False`. This is the **only** way to re-enable movement after an emergency stop. It requires an explicit call — it never resets itself automatically.

#### `move_servo_smooth(servo_id, target, step, delay)`
The core movement function. Instead of sending one large position jump (which can trigger the LSS failsafe), it steps from the current position to the target in small increments.

```
current = -200, target = -700, step = 30
Tick 1: send -230, sleep 0.03s
Tick 2: send -260, sleep 0.03s
...
Tick 17: send -700  ← final step, loop exits
```

On every tick it checks `self._estop`. If a FIST gesture fires the emergency stop in the main loop, the next tick of this function will detect it and return immediately — maximum 30ms of additional movement before stopping.

#### `move_pose_sequential(pose, order, speed)`
Moves multiple servos one at a time in a specified order. The order matters for safety:
- When **descending** to pick: WRIST → TOP → BOTTOM (neutralise wrist angle before lowering)
- When **lifting** after grip: BOTTOM → TOP → WRIST (raise object off surface first)
Wrong order = arm segments collide with the table or each other.

#### `go_home()`, `go_ready()`
Convenience methods that call `move_pose_sequential` with the appropriate pose and a hardcoded safe ordering.

#### `gripper_open()`, `gripper_close(position)`
Smooth moves of servo 5 only. `gripper_close` defaults to position 600 (firm grip without maxing out the servo).

#### `get_position(servo_id) → int`
Reads position from hardware, updates the cache, and guards against `None` responses:
```python
raw = self._servos[servo_id].getPosition()
pos = int(raw) if raw is not None else self._current_positions[servo_id]
```

---

## 5. `gesture_recogniser.py` — Hand Gesture Detection

**Responsibility:** Takes a camera frame and returns a stable, confirmed gesture name. Uses Google's MediaPipe Hands model for landmark detection, then classifies the gesture using finger geometry.

### `GestureResult` dataclass
A simple container for gesture output:
```python
@dataclass
class GestureResult:
    name: str        # "OPEN_PALM", "FIST", "PEACE", etc., or "NONE"
    confidence: float  # 0.0 to 1.0, fraction of fingers that matched
    landmarks: object  # raw MediaPipe landmark object (for drawing)
```

### `GestureRecogniser` class

#### `start()`
Initialises MediaPipe Hands with:
- `static_image_mode=False` — tracks hand across frames (faster than re-detecting each frame)
- `max_num_hands=1` — only one hand needed
- `min_detection_confidence=0.7` — ignores uncertain detections
- `min_tracking_confidence=0.6` — minimum confidence to keep tracking

#### `process_frame(bgr_frame) → GestureResult`
Full pipeline per frame:
1. Flip frame horizontally (creates mirror view so gestures feel natural)
2. Convert BGR → RGB (MediaPipe requirement)
3. Set `writeable=False` on the array (performance optimisation — avoids copy)
4. Pass to `self._hands.process()` — runs neural network
5. If no hand detected: call `_apply_stability("NONE")`, return current stable gesture
6. Extract hand landmarks and handedness (left or right)
7. Call `_classify(landmarks, handedness)` → raw gesture name + confidence
8. Call `_apply_stability(raw_name)`
9. Return `GestureResult` with the **stable** gesture name

#### `_classify(landmarks, handedness) → (str, float)`
Determines which gesture is being shown.

**Finger extension check:**
```python
def finger_extended(tip_idx, pip_idx) -> bool:
    return lm[tip_idx].y < lm[pip_idx].y
```
In MediaPipe's normalised coordinate space, y=0 is the top of the frame and y=1 is the bottom. So a finger tip that is *higher* than its PIP (middle) joint has a *smaller* y value. This reliably detects whether a finger is pointing up (extended) or folded down (curled).

**Thumb check (different because thumb moves sideways):**
```python
# Right hand: tip is to the left of IP joint when extended
return lm[THUMB_TIP].x < lm[THUMB_IP].x
```

**Pattern matching:**
Each known gesture has a pattern like `[True, False, False, False, False]` (thumb only = THUMBS_UP). `None` means "don't care" for that finger. The detected state `[thumb, index, middle, ring, pinky]` is compared to each pattern, scoring how many fingers match. Best score above 0.8 (4/5 fingers) wins.

#### `_apply_stability_filter(raw)`
Tracks how many consecutive frames the same raw gesture was detected. Only updates `_stable_gesture` when the count reaches `GESTURE_STABLE_FRAMES` (8). If the raw gesture is "NONE", the stable gesture resets immediately (hand has left the frame).

#### `draw_landmarks(bgr_frame, result) → frame`
Draws the MediaPipe hand skeleton on the (flipped) frame. Also overlays the gesture name and the mapped behaviour from `GESTURE_BEHAVIOUR_MAP`.

---

## 6. `vision.py` — Red Object Detection

**Responsibility:** Detects a red object in a camera frame and reports where it is horizontally — LEFT, CENTRE, or RIGHT. Used by the PICK_SCAN state to steer the arm.

### `ColourDetectionResult` dataclass
```python
@dataclass
class ColourDetectionResult:
    found: bool                          # was any object detected?
    bbox: (x, y, w, h)                  # bounding box in pixels
    centre_x: int                        # centroid x position
    centre_y: int                        # centroid y position
    horizontal_zone: str                 # "LEFT", "CENTRE", "RIGHT", or "NONE"
    area: float                          # contour area in px²
    frame_width: int                     # used to compute zone thresholds
```

### `ColourDetector` class

#### `__init__()`
Pre-creates two morphological kernels at startup (reusing them each frame is faster than creating new ones every time):
- `_kernel_open`: 3×3 ellipse — removes small noise
- `_kernel_close`: 5×5 ellipse — fills holes in detected region

#### `detect_red(bgr_frame) → ColourDetectionResult`
Full detection pipeline:

**Step 1 — Colour space conversion:**
```python
hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
```
HSV (Hue, Saturation, Value) separates colour information from brightness, making colour detection far more robust to changes in room lighting than working in BGR.

**Step 2 — Dual red mask:**
```python
mask1 = cv2.inRange(hsv, (0,120,70), (10,255,255))    # red near 0°
mask2 = cv2.inRange(hsv, (170,120,70), (180,255,255))  # red near 360°
mask  = cv2.bitwise_or(mask1, mask2)
```
The result is a binary image: white pixels = red object, black pixels = everything else.

**Step 3 — Noise reduction:**
```python
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel_open,  iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close, iterations=2)
```
OPEN removes small isolated white blobs (noise). CLOSE fills small black gaps inside the object (e.g. a highlight reflection on a red ball).

**Step 4 — Find contours:**
```python
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
largest = max(contours, key=cv2.contourArea)
```
Contours are outlines of connected white regions. Taking the largest one assumes the biggest red region is the target object.

**Step 5 — Centroid via moments:**
```python
M = cv2.moments(largest)
cx = int(M["m10"] / M["m00"])  # x centroid
cy = int(M["m01"] / M["m00"])  # y centroid
```
Image moments give the exact centre of mass of the contour shape.

**Step 6 — Zone classification:**
Frame width (640px) is divided into thirds: 0–213 = LEFT, 213–426 = CENTRE, 426–640 = RIGHT.

#### `draw_detection(bgr_frame, result) → frame`
Draws the bounding box in red, centroid as a yellow dot, zone boundaries as grey vertical lines, and a text label showing which zone the object is in. Zone label turns green when "CENTRE" (aligned).

---

## 7. `behaviours.py` — State Machine

**Responsibility:** Coordinates all subsystems (arm, gesture, vision) through a 12-state machine. Decides what the arm does next based on current state + gesture input + camera data.

### `State` enum
```python
class State(Enum):
    IDLE, HOMING, WAVING,
    PICK_SCAN, PICK_DESCEND, PICK_GRIP, PICK_LIFT,
    PLACE_APPROACH, PLACE_DROP, PLACE_RETREAT,
    DEMO_POSE, EMERGENCY_STOP
```
The arm is always in exactly one state.

### `BehaviourEngine` class

#### `__init__(arm, detector)`
Stores references to `ArmController` and `ColourDetector`. Initialises all state tracking variables:
- `_state = State.IDLE`
- `_aligned_base`: records the base position after scan alignment (used during descend/lift)
- `_alignment_frames`: counts consecutive frames where object is centred
- `_scan_direction / _scan_attempts`: control the sweep behaviour when no object found
- `_pending_gesture`: set by `trigger_gesture()`, consumed once in `update()`

#### `trigger_gesture(gesture_name)`
Called from `main.py` when a stable gesture fires. Simply stores the gesture name in `_pending_gesture`. It is consumed (set to None) at the start of the next `update()` call.

#### `update(colour_frame) → State`
Called once per main loop tick. Structure:
```
1. Consume _pending_gesture
2. If gesture == "FIST" and not already stopped:
       arm.emergency_stop()
       _transition(EMERGENCY_STOP)
       return
3. Dispatch to current state handler
4. Return current state
```
The FIST check always runs first — it is unconditional.

#### `_handle_estop(gesture)`
Waits for OPEN_PALM. When received: calls `arm.clear_estop()` and transitions to IDLE.

#### `_handle_idle(gesture)`
Routes gestures to their entry states:
- OPEN_PALM → HOMING
- PEACE → WAVING (resets wave step counter)
- POINT → resets scan variables, calls `arm.go_ready()`, enters PICK_SCAN
- THUMBS_UP → PLACE_APPROACH (only if `arm.is_carrying()`)
- THREE_FINGERS → DEMO_POSE

#### `_handle_homing()`
Calls `arm.go_home()` (blocking, returns when done), then transitions to IDLE.

#### `_handle_waving()`
Uses `_wave_step` as a counter through a 5-pose sequence:
`[POSE_WAVE_A, POSE_WAVE_B, POSE_WAVE_A, POSE_WAVE_B, POSE_HOME]`
Each call to this handler executes one step. After all 5 steps, transitions to IDLE.

#### `_handle_pick_scan(colour_frame)`
The most complex handler. Runs every frame during pick-up alignment:

```python
# On first entry (time_in_state < 0.1s): move to POSE_SCAN
# Every tick:
result = detector.detect_red(colour_frame)
if result.found:
    pixel_offset = result.centre_x - (frame_width / 2)
    base_delta   = int(pixel_offset * BASE_DEG_PER_PIXEL)
    new_base     = clamp(current_base + base_delta)
    move_servo_smooth(SERVO_BASE, new_base, step=15)  # fine steps for accuracy

    if zone == "CENTRE":
        alignment_frames += 1
        if alignment_frames >= 5:
            aligned_base = current_base_position
            transition(PICK_DESCEND)
    else:
        alignment_frames = 0
else:
    # Sweep: move base left/right to search
    # Reverse on hitting limit, give up after 3 full sweeps
```

Note that `step=15` (half the default) is used during alignment to approach the centre position gradually rather than overshooting.

#### `_handle_pick_descend()`
Builds the pick-down pose with the recorded `_aligned_base`:
```python
pose = dict(config.POSE_PICK_DOWN)
pose[SERVO_BASE] = self._aligned_base   # preserve alignment
arm.move_pose_sequential(pose, [WRIST, TOP, BOTTOM])
transition(PICK_GRIP)
```

#### `_handle_pick_grip()`
Closes gripper to 600, waits 0.3s, reads back actual position. If position < 350, the grip is weak (object slipped) — retries at 700. Transitions to PICK_LIFT regardless (the arm still lifts).

#### `_handle_pick_lift()`
Lifts using safe order [BOTTOM, TOP, WRIST]:
```python
pose = dict(config.POSE_CARRY)
pose[SERVO_BASE] = self._aligned_base
arm.move_pose_sequential(pose, [BOTTOM, TOP, WRIST])
arm.set_carrying(True)
transition(IDLE)
```
`set_carrying(True)` enables the THUMBS_UP gesture path in `_handle_idle()`.

#### `_handle_place_approach()`, `_handle_place_drop()`, `_handle_place_retreat()`
Linear sequence: move to drop zone → open gripper + `set_carrying(False)` → go_ready → IDLE.

#### `_handle_demo()`
Moves to `POSE_DEMO`, waits 1 second, then `go_ready()` and returns to IDLE.

#### `_transition(new_state)`
Updates `_state`, records `_state_entry_time`, and logs the transition. `_time_in_state()` uses the entry time to check if the state was just entered (used in `_handle_pick_scan` to move to POSE_SCAN only on first entry).

---

## 8. `main.py` — Entry Point and Main Loop

**Responsibility:** Initialises all subsystems, runs the main loop, routes frames to the correct processors, handles display, and shuts down cleanly.

### `open_camera(index, label) → VideoCapture`
Opens a camera by index, sets resolution to 640×480, logs which camera opened. Returns `None` (not `sys.exit`) if the camera is not found — this allows the system to continue in gesture-only mode if the USB webcam is missing.

### `main()` — Startup sequence
```
1. Create ArmController, GestureRecogniser, ColourDetector
2. arm.connect()  — attempt serial connection (continues if fails)
3. recogniser.start()  — initialise MediaPipe
4. open_camera(CAMERA_GESTURE_INDEX)  — laptop camera (required, exits if missing)
5. open_camera(CAMERA_VISION_INDEX)   — USB webcam (optional, warns if missing)
6. Create BehaviourEngine(arm, detector)
7. Enter main loop
```

### Main loop
```
while True:
    ret_g, gesture_frame   = gesture_cap.read()
    ret_v, workspace_frame = vision_cap.read()  # uses blank frame if unavailable

    gesture_result = recogniser.process_frame(gesture_frame)

    # FIST first, always
    if gesture_result.name == "FIST":
        engine.trigger_gesture("FIST")
    elif gesture_result.name != "NONE":
        engine.trigger_gesture(gesture_result.name)

    engine.update(workspace_frame)  # workspace frame passed here

    # Build displays
    gesture_display   = recogniser.draw_landmarks(gesture_frame, gesture_result)
    gesture_display   = draw_hud(gesture_display, state_name, carrying)
    gesture_display   = draw_legend(gesture_display)

    workspace_display = workspace_frame.copy()
    if engine.get_state() == State.PICK_SCAN:
        colour_result     = detector.detect_red(workspace_frame)
        workspace_display = detector.draw_detection(workspace_display, colour_result)

    cv2.imshow("Gesture Camera (YOU)",  gesture_display)
    cv2.imshow("Workspace Camera (ARM)", workspace_display)

    key = cv2.waitKey(1)
    if key == ord('q'): break
    if key == ord('c'): arm.clear_estop()
```

Note that `detector.detect_red()` is **only called** when in `PICK_SCAN` state. At all other times, the workspace frame is just displayed raw. This avoids wasting processing time on colour detection when it is not needed.

### `draw_hud(frame, state_name, carrying)`
Draws a semi-transparent dark bar across the top of the gesture window. Shows current state (colour-coded: green=IDLE, orange=active, red=EMERGENCY_STOP) and whether the arm is carrying an object.

### `draw_legend(frame)`
Draws the gesture→behaviour cheat sheet in small text at the bottom of the gesture window.

### Shutdown sequence (`finally` block)
```
arm.disconnect()       → go_home() then close serial
recogniser.stop()      → release MediaPipe resources
gesture_cap.release()  → release laptop camera
vision_cap.release()   → release USB webcam
cv2.destroyAllWindows()
```
The `finally` block runs even if an exception or KeyboardInterrupt occurs, ensuring the arm always returns to HOME position and the serial port is released cleanly.
