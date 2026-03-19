###############################################################################
# vision.py — OpenCV red object detection
#
# Detects the largest red object in a camera frame and returns its position
# relative to the frame (LEFT / CENTRE / RIGHT) for arm alignment.
###############################################################################

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
import config

log = logging.getLogger(__name__)


@dataclass
class ColourDetectionResult:
    found: bool = False
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h) pixels
    centre_x: int = 0
    centre_y: int = 0
    horizontal_zone: str = "NONE"   # "LEFT", "CENTRE", "RIGHT", or "NONE"
    area: float = 0.0
    frame_width: int = config.FRAME_WIDTH


class ColourDetector:
    def __init__(self):
        self._kernel_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # ------------------------------------------------------------------ #
    # Main detection                                                       #
    # ------------------------------------------------------------------ #

    def detect_red(self, bgr_frame: np.ndarray) -> ColourDetectionResult:
        h, w = bgr_frame.shape[:2]
        result = ColourDetectionResult(frame_width=w)

        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
        mask = self._build_red_mask(hsv)

        # Noise reduction
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  self._kernel_open,  iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel_close, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return result

        # Largest contour above area threshold
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < config.MIN_COLOUR_AREA:
            return result

        x, y, cw, ch = cv2.boundingRect(largest)
        M = cv2.moments(largest)
        if M["m00"] == 0:
            return result

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        result.found = True
        result.bbox = (x, y, cw, ch)
        result.centre_x = cx
        result.centre_y = cy
        result.area = area
        result.horizontal_zone = self._get_zone(cx, w)
        return result

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _build_red_mask(self, hsv: np.ndarray) -> np.ndarray:
        mask1 = cv2.inRange(hsv,
                            np.array(config.RED_HSV_LOWER_1),
                            np.array(config.RED_HSV_UPPER_1))
        mask2 = cv2.inRange(hsv,
                            np.array(config.RED_HSV_LOWER_2),
                            np.array(config.RED_HSV_UPPER_2))
        return cv2.bitwise_or(mask1, mask2)

    def _get_zone(self, cx: int, frame_width: int) -> str:
        third = frame_width // 3
        if cx < third:
            return "LEFT"
        elif cx < 2 * third:
            return "CENTRE"
        else:
            return "RIGHT"

    # ------------------------------------------------------------------ #
    # Drawing                                                              #
    # ------------------------------------------------------------------ #

    def draw_detection(self, bgr_frame: np.ndarray, result: ColourDetectionResult) -> np.ndarray:
        frame = bgr_frame.copy()
        w = result.frame_width

        # Zone dividers
        third = w // 3
        cv2.line(frame, (third, 0), (third, frame.shape[0]), (200, 200, 200), 1)
        cv2.line(frame, (2 * third, 0), (2 * third, frame.shape[0]), (200, 200, 200), 1)

        if result.found and result.bbox:
            x, y, bw, bh = result.bbox
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 0, 255), 2)
            cv2.circle(frame, (result.centre_x, result.centre_y), 5, (0, 255, 255), -1)
            zone_colour = (0, 255, 0) if result.horizontal_zone == "CENTRE" else (0, 165, 255)
            cv2.putText(frame, f"Red [{result.horizontal_zone}]",
                        (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, zone_colour, 2)
        return frame
