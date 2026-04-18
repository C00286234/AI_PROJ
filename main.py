###############################################################################
# main.py — Entry point for gesture-controlled Lynxmotion LSS robotic arm
#
# Controls:
#   OPEN_PALM     → HOME position
#   FIST          → EMERGENCY STOP
#   PEACE         → WAVE sequence
#   THUMBS UP     → BOW
#   POINT         → REACH forward
#   Q key         → Quit cleanly
#   C key         → Clear emergency stop
###############################################################################

import logging
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent
ARM_DIR = ROOT_DIR / "Arm Controller"
CAMERA_DIR = ROOT_DIR / "Camera Module"

for module_dir in (ARM_DIR, CAMERA_DIR):
    module_path = str(module_dir)
    if module_path not in sys.path:
        sys.path.insert(0, module_path)

import config
from arm_controller import ArmController
from gesture_recogniser import GestureRecogniser
from behaviours import BehaviourEngine, State

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

_GESTURE_LEGEND = [
    ("AUTO: FIST",        "EMERGENCY STOP"),
    ("MANUAL: FIST",      "GRIPPER CLOSE"),
    ("THUMBS_UP",     "Switch -> AUTOMATIC"),
    ("THUMBS_DOWN",   "Switch -> MANUAL"),
    ("AUTO: OPEN_PALM",   "HOME"),
    ("AUTO: POINT/PEACE/3", "WAVE / REACH / BOW"),
    ("MANUAL: L / inv-L",   "MIDDLE UP / DOWN"),
    ("MANUAL: OPEN_PALM",   "GRIPPER OPEN"),
    ("MANUAL: POINT/PEACE", "ROTATE LEFT / RIGHT"),
]


def draw_hud(frame: np.ndarray, state_name: str) -> np.ndarray:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 70), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    state_colour = (0, 255, 0) if state_name == "IDLE" else (0, 200, 255)
    if state_name == "EMERGENCY_STOP":
        state_colour = (0, 0, 255)

    cv2.putText(frame, f"STATE: {state_name}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, state_colour, 2)
    cv2.putText(frame, "Q=quit  C=clear estop", (w - 290, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    return frame


def draw_legend(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    y = h - len(_GESTURE_LEGEND) * 22 - 10
    for gesture, behaviour in _GESTURE_LEGEND:
        cv2.putText(frame, f"{gesture}: {behaviour}", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        y += 22
    return frame


def main():
    arm = ArmController()
    recogniser = GestureRecogniser()

    if not arm.connect():
        log.error("Could not connect to arm on %s — running in camera-only mode.",
                  config.SERIAL_PORT)

    recogniser.start()

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        log.error("Cannot open camera index %d", config.CAMERA_INDEX)
        arm.disconnect()
        recogniser.stop()
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    engine = BehaviourEngine(arm)
    log.info("System ready. Show gestures to control the arm. Press Q to quit.")
    log.info("Default mode: AUTOMATIC")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            gesture_result = recogniser.process_frame(frame)

            # Feed current gesture every frame so manual mode can be continuous.
            engine.trigger_gesture(gesture_result.name)
            engine.update()

            display = recogniser.draw_landmarks(frame, gesture_result)
            display = draw_hud(display, engine.get_state_name())
            cv2.putText(display, f"MODE: {engine.get_mode_name()}",
                        (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 220), 2)
            display = draw_legend(display)

            cv2.imshow("LSS Gesture Arm Control", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                log.info("Q pressed — shutting down")
                break
            elif key == ord('c'):
                arm.clear_estop()
                log.info("E-stop manually cleared via keyboard")

    except KeyboardInterrupt:
        log.info("Interrupted by user")

    finally:
        log.info("Shutting down...")
        try:
            arm.disconnect()
        except Exception:
            pass
        recogniser.stop()
        cap.release()
        cv2.destroyAllWindows()
        log.info("Done.")


if __name__ == "__main__":
    main()
