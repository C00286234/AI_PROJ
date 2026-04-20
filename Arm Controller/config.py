###############################################################################
# config.py — Single source of truth for all constants
# All servo limits, named poses, and calibration values live here.
# Nothing in this file changes at runtime.
###############################################################################

# --- Serial ---
SERIAL_PORT = "COM5"
SERIAL_BAUD = 115200  # lssc.LSS_DefaultBaud

# --- Servo IDs ---
SERVO_BASE    = 1
SERVO_MIDDLE  = 2
SERVO_TOP     = 3
SERVO_WRIST   = 4
SERVO_GRIPPER = 5

ALL_SERVO_IDS = [SERVO_BASE, SERVO_MIDDLE, SERVO_TOP, SERVO_WRIST, SERVO_GRIPPER]

# --- Safe position limits (tenths-of-degrees, inclusive) ---
SERVO_LIMITS = {
    SERVO_BASE:    (-900,  900),
    SERVO_MIDDLE:  (-900,    0),   # -900 = parallel to ground, 0 = straight up
    SERVO_TOP:     (   0,  850),   #    0 = straight up, 850 = parallel to bottom arm
    SERVO_WRIST:   (-800,    0),   # -800 = straight up, 0 = straight out
    SERVO_GRIPPER: (   0,  750),   #    0 = open, 750 = fully closed
}

# --- Named poses (dict keyed by servo ID) ---
POSE_HOME = {
    SERVO_BASE:    0,
    SERVO_MIDDLE:  -900,
    SERVO_TOP:      850,
    SERVO_WRIST:   -400,
    SERVO_GRIPPER:    0,
}

POSE_READY = {
    SERVO_BASE:    0,
    SERVO_MIDDLE:  -450,
    SERVO_TOP:      400,
    SERVO_WRIST:   -200,
    SERVO_GRIPPER:    0,
}

POSE_WAVE_A = {
    SERVO_BASE:    -300,
    SERVO_MIDDLE:  -500,
    SERVO_TOP:      200,
    SERVO_WRIST:   -400,
    SERVO_GRIPPER:    0,
}

POSE_WAVE_B = {
    SERVO_BASE:     300,
    SERVO_MIDDLE:  -500,
    SERVO_TOP:      200,
    SERVO_WRIST:   -400,
    SERVO_GRIPPER:    0,
}

POSE_REACH = {
    SERVO_BASE:      0,
    SERVO_MIDDLE:  0,
    SERVO_TOP:      0,
    SERVO_WRIST:   0,
    SERVO_GRIPPER:    100,
}

POSE_BOW = {
    SERVO_BASE:      0,
    SERVO_MIDDLE:  -800,
    SERVO_TOP:      700,
    SERVO_WRIST:   -600,
    SERVO_GRIPPER:    0,
}

# --- Movement ---
# Max speed is set on each servo at startup using the LSS built-in motion controller.
# Units: tenths-of-degrees per second. 370 = 37 deg/s (smooth and controlled).
SERVO_MAX_SPEED = 370

# How long to wait for each move to complete before returning from move_servo_smooth.
# Must be long enough for the slowest movement to finish.
MOVE_COMPLETION_TIMEOUT = 2.5   # seconds

# --- Gesture stability ---
GESTURE_STABLE_FRAMES = 60   # consecutive identical detections required before firing

# --- Supported gesture labels ---
SUPPORTED_GESTURES = [
    "THUMBS_UP",
    "OKAY_SIGN",
    "THREE_FINGERS",
    "OPEN_PALM",
    "FIST",
    "POINT",
    "PEACE",
]

# --- Camera ---
CAMERA_INDEX   = 0
FRAME_WIDTH    = 640
FRAME_HEIGHT   = 480

# --- Gesture → behaviour mapping ---
GESTURE_BEHAVIOUR_MAP = {
    "OPEN_PALM":     "HOME / OPEN_GRIPPER (manual)",
    "FIST":          "EMERGENCY_STOP (auto) / CLOSE_GRIPPER (manual)",
    "THUMBS_UP":     "MODE_AUTOMATIC",
    "OKAY_SIGN":     "MODE_MANUAL",
    "POINT":         "WAVE (auto) / ROTATE_RIGHT (manual)",
    "PEACE":         "REACH (auto) / ROTATE_LEFT (manual)",
    "THREE_FINGERS": "BOW (auto) / MIDDLE_UP (manual)",
}
