###############################################################################
# main.py — Entry point for gesture-controlled Lynxmotion LSS robotic arm
#
# Controls:
#   OPEN_PALM     → HOME position
#   FIST          → EMERGENCY STOP (hold any pose)
#   PEACE (✌)     → WAVE sequence
#   THUMBS UP     → PLACE object at drop zone (only if carrying)
#   POINT (☝)     → PICK UP sequence (find red object, grab, lift)
#   THREE FINGERS → DEMO pose
#   Q key         → Quit cleanly
#   C key         → Clear emergency stop (also clears via OPEN_PALM gesture)
#
# Cameras:
#   CAMERA_GESTURE_INDEX (default 0) — laptop built-in, faces you → gestures
#   CAMERA_VISION_INDEX  (default 1) — USB webcam, faces workspace → arm sees objects
#
# Display:
#   Left window  — gesture camera feed with hand landmarks + state HUD
#   Right window — workspace camera feed with colour detection overlay
###############################################################################

import logging
import sys

import cv2
import numpy as np
import config
from arm_controller import ArmController
from gesture_recogniser import GestureRecogniser
from vision import ColourDetector
from behaviours import BehaviourEngine, State

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

_GESTURE_LEGEND = [
    ("OPEN_PALM",     "HOME"),
    ("FIST",          "EMERGENCY STOP"),
    ("PEACE",         "WAVE"),
    ("THUMBS_UP",     "PLACE (if carrying)"),
    ("POINT",         "PICK UP red object"),
    ("THREE_FINGERS", "DEMO POSE"),
]


def draw_hud(frame: np.ndarray, state_name: str, carrying: bool) -> np.ndarray:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 100), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    state_colour = (0, 255, 0) if state_name == "IDLE" else (0, 200, 255)
    if state_name == "EMERGENCY_STOP":
        state_colour = (0, 0, 255)

    cv2.putText(frame, f"STATE: {state_name}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, state_colour, 2)

    carry_label = "CARRYING: YES" if carrying else "CARRYING: NO"
    carry_colour = (0, 255, 128) if carrying else (160, 160, 160)
    cv2.putText(frame, carry_label, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, carry_colour, 2)

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


def open_camera(index: int, label: str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        log.error("Cannot open %s (camera index %d)", label, index)
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    log.info("Opened %s on index %d", label, index)
    return cap


def main():
    arm = ArmController()
    recogniser = GestureRecogniser()
    detector = ColourDetector()

    if not arm.connect():
        log.error("Could not connect to arm on %s — running in camera-only mode.",
                  config.SERIAL_PORT)

    recogniser.start()

    # --- Open both cameras ---
    gesture_cap = open_camera(config.CAMERA_GESTURE_INDEX, "gesture camera (laptop)")
    vision_cap  = open_camera(config.CAMERA_VISION_INDEX,  "workspace camera (USB)")

    if gesture_cap is None:
        log.error("Gesture camera is required. Exiting.")
        arm.disconnect()
        recogniser.stop()
        sys.exit(1)

    if vision_cap is None:
        log.warning("Workspace camera not found on index %d.", config.CAMERA_VISION_INDEX)
        log.warning("Colour-guided pick-up will be disabled. Check USB webcam connection.")
        log.warning("To change the index, edit CAMERA_VISION_INDEX in config.py.")

    engine = BehaviourEngine(arm, detector)
    log.info("System ready — show gestures to the laptop camera to control the arm.")
    log.info("Point the USB webcam at the workspace so the arm can see the red object.")
    log.info("Press Q to quit.")

    # Blank frame used when workspace camera is unavailable
    blank = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.putText(blank, "Workspace camera not found", (60, config.FRAME_HEIGHT // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 200), 2)
    cv2.putText(blank, f"Check USB webcam (index {config.CAMERA_VISION_INDEX})",
                (60, config.FRAME_HEIGHT // 2 + 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (160, 160, 160), 1)

    try:
        while True:
            # --- Read gesture camera (laptop) ---
            ret_g, gesture_frame = gesture_cap.read()
            if not ret_g:
                log.warning("Gesture camera read failed — retrying")
                continue

            # --- Read workspace camera (USB webcam) ---
            workspace_frame = blank.copy()
            if vision_cap is not None:
                ret_v, ws_frame = vision_cap.read()
                if ret_v:
                    workspace_frame = ws_frame

            # --- Gesture recognition (laptop camera) ---
            gesture_result = recogniser.process_frame(gesture_frame)

            if gesture_result.name == "FIST":
                engine.trigger_gesture("FIST")
            elif gesture_result.name != "NONE":
                engine.trigger_gesture(gesture_result.name)

            # --- State machine tick (passes workspace frame for colour detection) ---
            engine.update(workspace_frame)

            # --- Build gesture display (left window) ---
            gesture_display = recogniser.draw_landmarks(gesture_frame, gesture_result)
            gesture_display = draw_hud(gesture_display, engine.get_state_name(), arm.is_carrying())
            gesture_display = draw_legend(gesture_display)

            # --- Build workspace display (right window) ---
            workspace_display = workspace_frame.copy()
            if engine.get_state() == State.PICK_SCAN:
                colour_result = detector.detect_red(workspace_frame)
                workspace_display = detector.draw_detection(workspace_display, colour_result)

            # Label the workspace window
            cv2.putText(workspace_display, "WORKSPACE CAM", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            cv2.putText(workspace_display, "Point this at the arm + objects",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)

            # --- Show windows ---
            cv2.imshow("Gesture Camera (YOU)", gesture_display)
            cv2.imshow("Workspace Camera (ARM)", workspace_display)

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
        gesture_cap.release()
        if vision_cap is not None:
            vision_cap.release()
        cv2.destroyAllWindows()
        log.info("Done.")


if __name__ == "__main__":
    main()
