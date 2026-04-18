###############################################################################
# behaviours.py — Mode-aware state machine for high-level arm behaviours
#
# Modes:
#   - AUTOMATIC (default on startup)
#   - MANUAL
#
# Gesture rules:
#   - FIST        -> EMERGENCY_STOP (automatic mode), GRIPPER_CLOSE (manual mode)
#   - THUMBS_UP   -> AUTOMATIC mode
#   - THUMBS_DOWN -> MANUAL mode
#
# AUTOMATIC mode:
#   - OPEN_PALM     -> HOME (reset pose)
#   - POINT         -> WAVE
#   - PEACE         -> REACH
#   - THREE_FINGERS -> BOW
#
# MANUAL mode (continuous while held):
#   - L_SHAPE             -> middle up
#   - UPSIDE_DOWN_L_SHAPE -> middle down
#   - OPEN_PALM           -> gripper open
#   - POINT               -> base rotate left
#   - PEACE               -> base rotate right
###############################################################################

import time
import logging
from enum import Enum, auto
from typing import Optional

import config
from arm_controller import ArmController

log = logging.getLogger(__name__)


class State(Enum):
    IDLE           = auto()
    HOMING         = auto()
    WAVING         = auto()
    REACHING       = auto()
    BOWING         = auto()
    EMERGENCY_STOP = auto()


class BehaviourEngine:
    def __init__(self, arm: ArmController):
        self._arm = arm
        self._state: State = State.IDLE
        self._state_entry_time: float = time.time()
        self._wave_step: int = 0

        self._pending_gesture: Optional[str] = None
        self._last_gesture: str = "NONE"

        self._mode: str = "AUTOMATIC"  # default startup mode

        # Manual direction channels; keyboard/manual input can still set these.
        self._manual_base_dir: int = 0
        self._manual_middle_dir: int = 0
        self._manual_gripper_dir: int = 0

    # ------------------------------------------------------------------ #
    # Public interface                                                   #
    # ------------------------------------------------------------------ #

    def trigger_gesture(self, gesture_name: str) -> None:
        self._pending_gesture = gesture_name or "NONE"

    def set_manual_input(self, base_dir: int = 0, middle_dir: int = 0,
                         gripper_dir: int = 0) -> None:
        self._manual_base_dir = 1 if base_dir > 0 else -1 if base_dir < 0 else 0
        self._manual_middle_dir = 1 if middle_dir > 0 else -1 if middle_dir < 0 else 0
        self._manual_gripper_dir = 1 if gripper_dir > 0 else -1 if gripper_dir < 0 else 0

    def update(self) -> State:
        gesture = self._pending_gesture or "NONE"
        self._pending_gesture = None

        is_new_gesture = gesture != self._last_gesture
        self._last_gesture = gesture

        # FIST behavior:
        # - AUTOMATIC mode: emergency stop
        # - MANUAL mode: gripper close command
        if gesture == "FIST" and self._mode != "MANUAL" and self._state != State.EMERGENCY_STOP:
            self._arm.emergency_stop()
            self._transition(State.EMERGENCY_STOP)
            return self._state

        # Mode switching gestures.
        if gesture == "THUMBS_UP" and self._mode != "AUTOMATIC":
            self._mode = "AUTOMATIC"
            self._reset_manual_dirs()
            log.info("Control mode -> AUTOMATIC")
        elif gesture == "THUMBS_DOWN" and self._mode != "MANUAL":
            self._mode = "MANUAL"
            log.info("Control mode -> MANUAL")

        if self._state == State.EMERGENCY_STOP:
            self._handle_estop(gesture)
            self._reset_manual_dirs()
            return self._state

        if self._state == State.IDLE:
            self._handle_idle(gesture, is_new_gesture)
        elif self._state == State.HOMING:
            self._handle_homing()
        elif self._state == State.WAVING:
            self._handle_waving()
        elif self._state == State.REACHING:
            self._handle_reaching()
        elif self._state == State.BOWING:
            self._handle_bowing()

        # Manual mode is continuous while gesture/keys are held.
        if self._mode == "MANUAL" and not self._arm.is_estopped() and self._state == State.IDLE:
            self._manual_from_gesture(gesture)

        if self._state != State.EMERGENCY_STOP and not self._arm.is_estopped():
            if self._manual_base_dir != 0:
                self._arm.rotate_base_manual(self._manual_base_dir)
            if self._manual_middle_dir != 0:
                self._arm.move_middle_manual(self._manual_middle_dir)
            if self._manual_gripper_dir != 0:
                self._arm.move_gripper_manual(self._manual_gripper_dir)

        return self._state

    def get_state(self) -> State:
        return self._state

    def get_state_name(self) -> str:
        return self._state.name

    def get_mode_name(self) -> str:
        return self._mode

    # ------------------------------------------------------------------ #
    # State handlers                                                       #
    # ------------------------------------------------------------------ #

    def _handle_estop(self, gesture: str) -> None:
        if gesture == "OPEN_PALM":
            self._arm.clear_estop()
            log.info("E-stop cleared by OPEN_PALM")
            self._transition(State.IDLE)

    def _handle_idle(self, gesture: str, is_new_gesture: bool) -> None:
        if gesture == "NONE":
            if self._mode == "MANUAL":
                self._reset_manual_dirs()
            return

        if self._mode == "AUTOMATIC":
            if gesture == "OPEN_PALM" and is_new_gesture:
                self._transition(State.HOMING)
            elif gesture == "POINT" and is_new_gesture:
                self._wave_step = 0
                self._transition(State.WAVING)
            elif gesture == "PEACE" and is_new_gesture:
                self._transition(State.REACHING)
            elif gesture == "THREE_FINGERS" and is_new_gesture:
                self._transition(State.BOWING)
            else:
                self._reset_manual_dirs()

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
            self._arm.move_pose(wave_sequence[self._wave_step])
            self._wave_step += 1
        else:
            self._transition(State.IDLE)

    def _handle_reaching(self) -> None:
        self._arm.move_pose_sequential(
            config.POSE_REACH,
            [config.SERVO_WRIST, config.SERVO_TOP,
             config.SERVO_MIDDLE, config.SERVO_BASE]
        )
        time.sleep(1.0)
        self._arm.go_ready()
        self._transition(State.IDLE)

    def _handle_bowing(self) -> None:
        self._arm.move_pose_sequential(
            config.POSE_BOW,
            [config.SERVO_WRIST, config.SERVO_TOP,
             config.SERVO_MIDDLE, config.SERVO_BASE]
        )
        time.sleep(1.0)
        self._arm.go_ready()
        self._transition(State.IDLE)

    # ------------------------------------------------------------------ #
    # Manual helpers                                                       #
    # ------------------------------------------------------------------ #

    def _manual_from_gesture(self, gesture: str) -> None:
        self._reset_manual_dirs()

        if gesture == "L_SHAPE":
            self._manual_middle_dir = 1
        elif gesture == "UPSIDE_DOWN_L_SHAPE":
            self._manual_middle_dir = -1
        elif gesture == "OPEN_PALM":
            self._manual_gripper_dir = -1
        elif gesture == "FIST":
            self._manual_gripper_dir = 1
        elif gesture == "POINT":
            self._manual_base_dir = -1
        elif gesture == "PEACE":
            self._manual_base_dir = 1

    def _reset_manual_dirs(self) -> None:
        self._manual_base_dir = 0
        self._manual_middle_dir = 0
        self._manual_gripper_dir = 0

    # ------------------------------------------------------------------ #
    # Utilities                                                            #
    # ------------------------------------------------------------------ #

    def _transition(self, new_state: State) -> None:
        if new_state != self._state:
            log.info("State: %s -> %s", self._state.name, new_state.name)
        self._state = new_state
        self._state_entry_time = time.time()

    def _time_in_state(self) -> float:
        return time.time() - self._state_entry_time
