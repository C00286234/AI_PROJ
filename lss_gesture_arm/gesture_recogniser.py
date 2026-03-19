###############################################################################
# gesture_recogniser.py — MediaPipe Hands gesture detection
#
# Classifies one hand's landmarks into 6 gestures using finger extension logic.
# Stability filter prevents accidental single-frame triggers.
###############################################################################

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
import config

log = logging.getLogger(__name__)

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    log.warning("mediapipe not installed — GestureRecogniser in SIMULATION mode")
    _MP_AVAILABLE = False


@dataclass
class GestureResult:
    name: str = "NONE"          # e.g. "OPEN_PALM", "FIST", "NONE"
    confidence: float = 0.0     # 0.0 – 1.0
    landmarks: object = field(default=None, repr=False)


# MediaPipe landmark indices
_THUMB_TIP, _THUMB_IP   = 4, 3
_INDEX_TIP, _INDEX_PIP  = 8, 6
_MIDDLE_TIP, _MIDDLE_PIP = 12, 10
_RING_TIP, _RING_PIP    = 16, 14
_PINKY_TIP, _PINKY_PIP  = 20, 18


class GestureRecogniser:
    def __init__(self):
        self._hands = None
        self._mp_hands = None
        self._mp_draw = None
        self._stable_count: int = 0
        self._last_raw: str = "NONE"
        self._stable_gesture: str = "NONE"

    def start(self) -> None:
        if not _MP_AVAILABLE:
            log.info("GestureRecogniser: simulation mode (no MediaPipe)")
            return
        self._mp_hands = mp.solutions.hands
        self._mp_draw  = mp.solutions.drawing_utils
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6,
        )
        log.info("GestureRecogniser started")

    def stop(self) -> None:
        if self._hands:
            self._hands.close()
            self._hands = None

    # ------------------------------------------------------------------ #
    # Main entry point                                                     #
    # ------------------------------------------------------------------ #

    def process_frame(self, bgr_frame: np.ndarray) -> GestureResult:
        if not _MP_AVAILABLE or self._hands is None:
            return GestureResult()

        # MediaPipe expects RGB
        rgb = cv2.cvtColor(cv2.flip(bgr_frame, 1), cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._hands.process(rgb)
        rgb.flags.writeable = True

        if not results.multi_hand_landmarks:
            self._apply_stability("NONE")
            return GestureResult(name=self._stable_gesture)

        hand_landmarks = results.multi_hand_landmarks[0]
        handedness = (results.multi_handedness[0].classification[0].label
                      if results.multi_handedness else "Right")

        raw_name, conf = self._classify(hand_landmarks, handedness)
        self._apply_stability(raw_name)

        return GestureResult(
            name=self._stable_gesture,
            confidence=conf,
            landmarks=hand_landmarks,
        )

    # ------------------------------------------------------------------ #
    # Stability filter                                                     #
    # ------------------------------------------------------------------ #

    def _apply_stability(self, raw: str) -> None:
        if raw == self._last_raw:
            self._stable_count += 1
        else:
            self._stable_count = 1
            self._last_raw = raw

        if self._stable_count >= config.GESTURE_STABLE_FRAMES:
            self._stable_gesture = raw
        elif raw == "NONE":
            # Reset immediately on hand loss
            self._stable_gesture = "NONE"

    # ------------------------------------------------------------------ #
    # Landmark classification                                              #
    # ------------------------------------------------------------------ #

    def _classify(self, landmarks, handedness: str) -> tuple[str, float]:
        lm = landmarks.landmark

        def finger_extended(tip_idx, pip_idx) -> bool:
            return lm[tip_idx].y < lm[pip_idx].y

        def thumb_extended() -> bool:
            # Compare x-axis; mirror for left hand
            if handedness == "Right":
                return lm[_THUMB_TIP].x < lm[_THUMB_IP].x
            else:
                return lm[_THUMB_TIP].x > lm[_THUMB_IP].x

        thumb  = thumb_extended()
        index  = finger_extended(_INDEX_TIP,  _INDEX_PIP)
        middle = finger_extended(_MIDDLE_TIP, _MIDDLE_PIP)
        ring   = finger_extended(_RING_TIP,   _RING_PIP)
        pinky  = finger_extended(_PINKY_TIP,  _PINKY_PIP)

        # Count how cleanly the detected pattern matches each gesture
        patterns = {
            "OPEN_PALM":     [True,  True,  True,  True,  True ],
            "FIST":          [False, False, False, False, False],
            "PEACE":         [None,  True,  True,  False, False],
            "THUMBS_UP":     [True,  False, False, False, False],
            "POINT":         [None,  True,  False, False, False],
            "THREE_FINGERS": [None,  True,  True,  True,  False],
        }
        detected = [thumb, index, middle, ring, pinky]

        best_name, best_score = "NONE", 0.0
        for name, pattern in patterns.items():
            matches = sum(
                1 for expected, actual in zip(pattern, detected)
                if expected is None or expected == actual
            )
            score = matches / len(pattern)
            if score > best_score:
                best_score = score
                best_name = name

        # Require at least 4/5 match to avoid spurious detections
        if best_score < 0.8:
            return "NONE", 0.0

        return best_name, best_score

    # ------------------------------------------------------------------ #
    # Drawing                                                              #
    # ------------------------------------------------------------------ #

    def draw_landmarks(self, bgr_frame: np.ndarray, result: GestureResult) -> np.ndarray:
        frame = cv2.flip(bgr_frame.copy(), 1)
        if _MP_AVAILABLE and result.landmarks and self._mp_draw:
            self._mp_draw.draw_landmarks(
                frame,
                result.landmarks,
                self._mp_hands.HAND_CONNECTIONS if self._mp_hands else None,
            )

        colour = (0, 255, 0) if result.name != "NONE" else (128, 128, 128)
        cv2.putText(frame, f"Gesture: {result.name}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)
        if result.name != "NONE" and result.name in config.GESTURE_BEHAVIOUR_MAP:
            behaviour = config.GESTURE_BEHAVIOUR_MAP[result.name]
            cv2.putText(frame, f"-> {behaviour}",
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
        return frame
