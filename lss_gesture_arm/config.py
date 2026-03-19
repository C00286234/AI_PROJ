###############################################################################
# config.py — Single source of truth for all constants
# All servo limits, named poses, and calibration values live here.
# Nothing in this file changes at runtime.
###############################################################################

# --- Serial ---
SERIAL_PORT = "COM7"
SERIAL_BAUD = 115200  # lssc.LSS_DefaultBaud

# --- Servo IDs ---
SERVO_BASE    = 1
SERVO_BOTTOM  = 2
SERVO_TOP     = 3
SERVO_WRIST   = 4
SERVO_GRIPPER = 5

ALL_SERVO_IDS = [SERVO_BASE, SERVO_BOTTOM, SERVO_TOP, SERVO_WRIST, SERVO_GRIPPER]

# --- Safe position limits (tenths-of-degrees, inclusive) ---
# Derived from empirical testing in testRanges.py
SERVO_LIMITS = {
    SERVO_BASE:    (-900,  900),
    SERVO_BOTTOM:  (-900,    0),   # -900 = parallel to ground, 0 = straight up
    SERVO_TOP:     (   0,  850),   #    0 = straight up, 850 = parallel to bottom arm
    SERVO_WRIST:   (-800,    0),   # -800 = straight up, 0 = straight out
    SERVO_GRIPPER: (   0,  750),   #    0 = open, 750 = fully closed
}

# --- Named poses (dict keyed by servo ID) ---
POSE_HOME = {
    SERVO_BASE:    0,
    SERVO_BOTTOM:  -900,
    SERVO_TOP:      850,
    SERVO_WRIST:   -400,
    SERVO_GRIPPER:    0,
}

POSE_READY = {
    SERVO_BASE:    0,
    SERVO_BOTTOM:  -450,
    SERVO_TOP:      400,
    SERVO_WRIST:   -200,
    SERVO_GRIPPER:    0,
}

POSE_SCAN = {
    SERVO_BASE:    0,
    SERVO_BOTTOM:  -600,
    SERVO_TOP:      300,
    SERVO_WRIST:   -100,
    SERVO_GRIPPER:    0,
}

POSE_PICK_DOWN = {
    SERVO_BASE:    0,       # overridden dynamically with aligned base position
    SERVO_BOTTOM:  -850,
    SERVO_TOP:      750,
    SERVO_WRIST:    -50,
    SERVO_GRIPPER:    0,
}

POSE_CARRY = {
    SERVO_BASE:    0,       # preserved from pick alignment
    SERVO_BOTTOM:  -500,
    SERVO_TOP:      350,
    SERVO_WRIST:   -300,
    SERVO_GRIPPER:  600,    # closed
}

POSE_DROP_ZONE = {
    SERVO_BASE:     500,
    SERVO_BOTTOM:  -700,
    SERVO_TOP:      600,
    SERVO_WRIST:   -100,
    SERVO_GRIPPER:  600,    # still closed on approach
}

POSE_WAVE_A = {
    SERVO_BASE:    -300,
    SERVO_BOTTOM:  -500,
    SERVO_TOP:      200,
    SERVO_WRIST:   -400,
    SERVO_GRIPPER:    0,
}

POSE_WAVE_B = {
    SERVO_BASE:     300,
    SERVO_BOTTOM:  -500,
    SERVO_TOP:      200,
    SERVO_WRIST:   -400,
    SERVO_GRIPPER:    0,
}

POSE_DEMO = {
    SERVO_BASE:     200,
    SERVO_BOTTOM:  -600,
    SERVO_TOP:      500,
    SERVO_WRIST:   -300,
    SERVO_GRIPPER:  300,
}

# --- Movement ---
DEFAULT_SPEED       = 300   # tenths-of-degrees per second (conservative)
FAST_SPEED          = 600   # used for wave / demo
INTERPOLATION_STEP  = 30    # position delta per interpolation tick
INTERPOLATION_DELAY = 0.03  # seconds between ticks (from testRanges.py empirical timing)

# --- Gesture stability ---
GESTURE_STABLE_FRAMES = 8   # consecutive identical detections required before firing

# --- Colour detection (HSV) ---
# Red wraps around in HSV, so two ranges are needed
RED_HSV_LOWER_1 = (  0, 120,  70)
RED_HSV_UPPER_1 = ( 10, 255, 255)
RED_HSV_LOWER_2 = (170, 120,  70)
RED_HSV_UPPER_2 = (180, 255, 255)
MIN_COLOUR_AREA = 1500      # px², blobs below this are ignored as noise

# --- Cameras ---
# Camera 0: laptop built-in webcam — faces you, used for gesture recognition
# Camera 1: external USB webcam  — faces workspace, used for red object detection
# If your USB webcam shows up on a different index, change CAMERA_VISION_INDEX.
CAMERA_GESTURE_INDEX = 0
CAMERA_VISION_INDEX  = 1
FRAME_WIDTH          = 640
FRAME_HEIGHT         = 480

# --- Arm-camera calibration ---
# Base servo units (tenths-of-degrees) per camera pixel offset from centre.
# Tune empirically: place object at edge of frame, observe required base rotation.
BASE_DEG_PER_PIXEL = 0.8

# --- Scan sweep ---
SCAN_SWEEP_STEP    = 50     # base units per sweep tick when no object visible
SCAN_SWEEP_LIMIT   = 800    # max base units to sweep in each direction
MAX_SCAN_ATTEMPTS  = 3      # full sweeps before giving up
ALIGNMENT_REQUIRED_FRAMES = 5  # frames object must be centred before descending

# --- Gesture → behaviour mapping ---
GESTURE_BEHAVIOUR_MAP = {
    "OPEN_PALM":     "HOME",
    "FIST":          "EMERGENCY_STOP",
    "PEACE":         "WAVE",
    "THUMBS_UP":     "PLACE_SEQUENCE",
    "POINT":         "PICK_UP_SEQUENCE",
    "THREE_FINGERS": "DEMO_POSE",
}
