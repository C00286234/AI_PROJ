###############################################################################
# config.py — Single source of truth for all constants
# All servo limits, named poses, and calibration values live here.
# Nothing in this file changes at runtime.
###############################################################################

# --- Serial ---
SERIAL_PORT = "COM12"
SERIAL_BAUD = 115200  # lssc.LSS_DefaultBaud

# --- Servo IDs ---
SERVO_BASE    = 1
SERVO_BOTTOM  = 2
SERVO_TOP     = 3
SERVO_WRIST   = 4
SERVO_GRIPPER = 5

ALL_SERVO_IDS = [SERVO_BASE, SERVO_BOTTOM, SERVO_TOP, SERVO_WRIST, SERVO_GRIPPER]

# --- Safe position limits (tenths-of-degrees, inclusive) ---
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

POSE_REACH = {
    SERVO_BASE:      0,
    SERVO_BOTTOM:  -600,
    SERVO_TOP:      600,
    SERVO_WRIST:   -100,
    SERVO_GRIPPER:    0,
}

POSE_BOW = {
    SERVO_BASE:      0,
    SERVO_BOTTOM:  -800,
    SERVO_TOP:      700,
    SERVO_WRIST:   -600,
    SERVO_GRIPPER:    0,
}

# --- Movement ---
DEFAULT_SPEED       = 50    # tenths-of-degrees per second (slow and safe)
FAST_SPEED          = 100   # used for wave / demo
INTERPOLATION_STEP  = 5   # position delta per interpolation tick (smaller = smoother)
INTERPOLATION_DELAY = 0.1   # seconds between ticks (higher = slower movement)

# --- Gesture stability ---
GESTURE_STABLE_FRAMES = 1   # consecutive identical detections required before firing

# --- Camera ---
CAMERA_INDEX   = 0
FRAME_WIDTH    = 640
FRAME_HEIGHT   = 480

# --- Gesture → behaviour mapping ---
GESTURE_BEHAVIOUR_MAP = {
    "OPEN_PALM":     "HOME",
    "FIST":          "EMERGENCY_STOP",
    "PEACE":         "WAVE",
    "THUMBS_UP":     "BOW",
    "POINT":         "REACH",
    "THREE_FINGERS": "DEMO_POSE",
}
