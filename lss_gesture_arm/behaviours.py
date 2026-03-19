###############################################################################
# behaviours.py — State machine for high-level arm behaviours
#
# State transition rules:
#   - FIST → EMERGENCY_STOP from ANY state (checked first in update())
#   - OPEN_PALM clears estop and returns to IDLE
#   - PICK states form a strict chain; gestures cannot skip ahead
#   - PLACE is only reachable from IDLE while arm is carrying an object
###############################################################################

import time
import logging
from enum import Enum, auto
from typing import Optional

import numpy as np
import config
from arm_controller import ArmController
from vision import ColourDetector, ColourDetectionResult

log = logging.getLogger(__name__)


class State(Enum):
    IDLE           = auto()
    HOMING         = auto()
    WAVING         = auto()
    PICK_SCAN      = auto()
    PICK_DESCEND   = auto()
    PICK_GRIP      = auto()
    PICK_LIFT      = auto()
    PLACE_APPROACH = auto()
    PLACE_DROP     = auto()
    PLACE_RETREAT  = auto()
    DEMO_POSE      = auto()
    EMERGENCY_STOP = auto()


class BehaviourEngine:
    def __init__(self, arm: ArmController, detector: ColourDetector):
        self._arm = arm
        self._detector = detector
        self._state: State = State.IDLE
        self._state_entry_time: float = time.time()

        # Pick-up alignment tracking
        self._aligned_base: int = 0
        self._alignment_frames: int = 0
        self._scan_base: int = 0
        self._scan_direction: int = 1
        self._scan_attempts: int = 0

        # Wave sequence step
        self._wave_step: int = 0

        # Pending gesture trigger (set from main loop, consumed in update)
        self._pending_gesture: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def trigger_gesture(self, gesture_name: str) -> None:
        """Called by main loop when a stable gesture fires."""
        self._pending_gesture = gesture_name

    def update(self, colour_frame: np.ndarray) -> State:
        """One tick of the state machine. Call once per main loop iteration."""
        gesture = self._pending_gesture
        self._pending_gesture = None

        # --- FIST overrides everything, always ---
        if gesture == "FIST" and self._state != State.EMERGENCY_STOP:
            self._arm.emergency_stop()
            self._transition(State.EMERGENCY_STOP)
            return self._state

        # --- State handlers ---
        if self._state == State.EMERGENCY_STOP:
            self._handle_estop(gesture)

        elif self._state == State.IDLE:
            self._handle_idle(gesture)

        elif self._state == State.HOMING:
            self._handle_homing()

        elif self._state == State.WAVING:
            self._handle_waving()

        elif self._state == State.PICK_SCAN:
            self._handle_pick_scan(colour_frame)

        elif self._state == State.PICK_DESCEND:
            self._handle_pick_descend()

        elif self._state == State.PICK_GRIP:
            self._handle_pick_grip()

        elif self._state == State.PICK_LIFT:
            self._handle_pick_lift()

        elif self._state == State.PLACE_APPROACH:
            self._handle_place_approach()

        elif self._state == State.PLACE_DROP:
            self._handle_place_drop()

        elif self._state == State.PLACE_RETREAT:
            self._handle_place_retreat()

        elif self._state == State.DEMO_POSE:
            self._handle_demo()

        return self._state

    def get_state(self) -> State:
        return self._state

    def get_state_name(self) -> str:
        return self._state.name

    # ------------------------------------------------------------------ #
    # State handlers                                                       #
    # ------------------------------------------------------------------ #

    def _handle_estop(self, gesture: Optional[str]) -> None:
        # Only OPEN_PALM clears the estop
        if gesture == "OPEN_PALM":
            self._arm.clear_estop()
            log.info("E-stop cleared by OPEN_PALM")
            self._transition(State.IDLE)

    def _handle_idle(self, gesture: Optional[str]) -> None:
        if gesture is None:
            return
        if gesture == "OPEN_PALM":
            self._transition(State.HOMING)
        elif gesture == "PEACE":
            self._wave_step = 0
            self._transition(State.WAVING)
        elif gesture == "POINT":
            self._scan_base = 0
            self._scan_direction = 1
            self._scan_attempts = 0
            self._alignment_frames = 0
            self._arm.go_ready()
            self._transition(State.PICK_SCAN)
        elif gesture == "THUMBS_UP" and self._arm.is_carrying():
            self._transition(State.PLACE_APPROACH)
        elif gesture == "THREE_FINGERS":
            self._transition(State.DEMO_POSE)

    def _handle_homing(self) -> None:
        self._arm.go_home()
        self._transition(State.IDLE)

    def _handle_waving(self) -> None:
        wave_sequence = [
            config.POSE_WAVE_A,
            config.POSE_WAVE_B,
            config.POSE_WAVE_A,
            config.POSE_WAVE_B,
            config.POSE_HOME,
        ]
        if self._wave_step < len(wave_sequence):
            self._arm.move_pose(wave_sequence[self._wave_step],
                                speed=config.FAST_SPEED)
            self._wave_step += 1
        else:
            self._transition(State.IDLE)

    def _handle_pick_scan(self, colour_frame: np.ndarray) -> None:
        """Align base to red object using camera feedback."""
        # Move to scan pose on first entry
        if self._time_in_state() < 0.1:
            self._arm.move_pose_sequential(
                config.POSE_SCAN,
                [config.SERVO_WRIST, config.SERVO_TOP,
                 config.SERVO_BOTTOM, config.SERVO_BASE]
            )

        result: ColourDetectionResult = self._detector.detect_red(colour_frame)

        if result.found:
            # Proportional base correction
            pixel_offset = result.centre_x - (result.frame_width / 2)
            base_delta = int(pixel_offset * config.BASE_DEG_PER_PIXEL)
            current_base = self._arm._current_positions.get(config.SERVO_BASE, 0)
            new_base = self._arm.clamp(config.SERVO_BASE, current_base + base_delta)
            self._arm.move_servo_smooth(config.SERVO_BASE, new_base, step=15)

            if result.horizontal_zone == "CENTRE":
                self._alignment_frames += 1
                if self._alignment_frames >= config.ALIGNMENT_REQUIRED_FRAMES:
                    self._aligned_base = self._arm._current_positions[config.SERVO_BASE]
                    log.info("Object aligned at base=%d — descending", self._aligned_base)
                    self._transition(State.PICK_DESCEND)
            else:
                self._alignment_frames = 0
        else:
            # Sweep base to search
            self._alignment_frames = 0
            current_base = self._arm._current_positions.get(config.SERVO_BASE, 0)
            new_base = current_base + self._scan_direction * config.SCAN_SWEEP_STEP
            clamped = self._arm.clamp(config.SERVO_BASE, new_base)

            if clamped != new_base:
                # Hit limit — reverse direction and count attempt
                self._scan_direction *= -1
                self._scan_attempts += 1
                log.info("Scan sweep reversal (%d/%d)", self._scan_attempts, config.MAX_SCAN_ATTEMPTS)

            if self._scan_attempts >= config.MAX_SCAN_ATTEMPTS:
                log.warning("Object not found after %d sweeps — returning to IDLE", self._scan_attempts)
                self._arm.go_home()
                self._transition(State.IDLE)
                return

            self._arm.move_servo_smooth(config.SERVO_BASE, clamped, step=config.SCAN_SWEEP_STEP)

    def _handle_pick_descend(self) -> None:
        """Lower arm to pick position, preserving aligned base."""
        pose = dict(config.POSE_PICK_DOWN)
        pose[config.SERVO_BASE] = self._aligned_base
        # Order: wrist → top → bottom (prevents hitting surface)
        self._arm.move_pose_sequential(
            pose,
            [config.SERVO_WRIST, config.SERVO_TOP, config.SERVO_BOTTOM]
        )
        self._transition(State.PICK_GRIP)

    def _handle_pick_grip(self) -> None:
        self._arm.gripper_close(600)
        time.sleep(0.3)  # dwell to ensure grip

        actual = self._arm.get_position(config.SERVO_GRIPPER)
        if actual < 350:
            log.warning("Grip weak (pos=%d) — retrying", actual)
            self._arm.gripper_close(700)
            time.sleep(0.3)

        self._transition(State.PICK_LIFT)

    def _handle_pick_lift(self) -> None:
        """Lift object. Order: bottom → top → wrist (raise before folding)."""
        pose = dict(config.POSE_CARRY)
        pose[config.SERVO_BASE] = self._aligned_base
        self._arm.move_pose_sequential(
            pose,
            [config.SERVO_BOTTOM, config.SERVO_TOP, config.SERVO_WRIST]
        )
        self._arm.set_carrying(True)
        log.info("Pick-up complete — arm is carrying object")
        self._transition(State.IDLE)

    def _handle_place_approach(self) -> None:
        self._arm.move_pose_sequential(
            config.POSE_DROP_ZONE,
            [config.SERVO_WRIST, config.SERVO_TOP,
             config.SERVO_BOTTOM, config.SERVO_BASE]
        )
        self._transition(State.PLACE_DROP)

    def _handle_place_drop(self) -> None:
        self._arm.gripper_open()
        time.sleep(0.4)  # dwell to ensure release
        self._arm.set_carrying(False)
        log.info("Object placed at drop zone")
        self._transition(State.PLACE_RETREAT)

    def _handle_place_retreat(self) -> None:
        self._arm.go_ready()
        self._transition(State.IDLE)

    def _handle_demo(self) -> None:
        self._arm.move_pose(config.POSE_DEMO, speed=config.FAST_SPEED)
        time.sleep(1.0)
        self._arm.go_ready()
        self._transition(State.IDLE)

    # ------------------------------------------------------------------ #
    # Utilities                                                            #
    # ------------------------------------------------------------------ #

    def _transition(self, new_state: State) -> None:
        if new_state != self._state:
            log.info("State: %s → %s", self._state.name, new_state.name)
        self._state = new_state
        self._state_entry_time = time.time()

    def _time_in_state(self) -> float:
        return time.time() - self._state_entry_time
