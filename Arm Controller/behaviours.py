import time
import logging
from enum import Enum, auto

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
        self._state = State.IDLE
        self._state_entry_time = time.time()
        self._wave_step = 0
        self._pending_gesture = "NONE"
        self._last_gesture = "NONE"
        self._is_automatic_mode = True

    def trigger_gesture(self, gesture_name):
        self._pending_gesture = gesture_name or "NONE"

    def update(self):
        gesture = self._pending_gesture or "NONE"
        self._pending_gesture = None

        is_new_gesture = gesture != self._last_gesture
        self._last_gesture = gesture

        if gesture == "FIST" and self._is_automatic_mode and self._state != State.EMERGENCY_STOP:
            self._arm.emergency_stop()
            self._transition(State.EMERGENCY_STOP)
            return self._state

        if gesture == "THUMBS_UP":
            self._is_automatic_mode = True
        elif gesture == "OKAY_SIGN":
            self._is_automatic_mode = False

        if self._state == State.EMERGENCY_STOP:
            if gesture == "OPEN_PALM":
                self._arm.clear_estop()
                self._transition(State.HOMING)
            return self._state

        if self._state == State.IDLE:
            if self._is_automatic_mode:
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
                self._run_manual(gesture, is_new_gesture)
        elif self._state == State.HOMING:
            self._arm.go_home()
            self._transition(State.IDLE)
        elif self._state == State.WAVING:
            wave_sequence = [
                config.POSE_WAVE_A,
                config.POSE_WAVE_B,
                config.POSE_WAVE_A,
                config.POSE_WAVE_B,
                config.POSE_HOME
            ]
            if self._wave_step < len(wave_sequence):
                self._arm.move_pose(wave_sequence[self._wave_step])
                self._wave_step += 1
            else:
                self._transition(State.IDLE)
        elif self._state == State.REACHING:
            self._arm.move_pose_sequential(
                config.POSE_REACH,
                [config.SERVO_WRIST, config.SERVO_TOP, config.SERVO_MIDDLE, config.SERVO_BASE],
            )
            time.sleep(1.0)
            self._arm.go_ready()
            self._transition(State.IDLE)
        elif self._state == State.BOWING:
            self._arm.move_pose_sequential(
                config.POSE_BOW,
                [config.SERVO_WRIST, config.SERVO_TOP, config.SERVO_MIDDLE, config.SERVO_BASE],
            )
            time.sleep(1.0)
            self._arm.go_ready()
            self._transition(State.IDLE)

        return self._state

    def _run_manual(self, gesture, is_new_gesture=False):
        if self._arm.is_estopped():
            return

        if gesture == "OPEN_PALM":
            self._arm.move_gripper_manual(-1)
        elif gesture == "FIST":
            if is_new_gesture:
                self._arm.close_gripper_until_contact()
        elif gesture == "POINT":
            self._arm.rotate_base_manual(1)
        elif gesture == "PEACE":
            self._arm.rotate_base_manual(-1)
        elif gesture == "THREE_FINGERS":
            self._arm.move_middle_manual(1)
        elif gesture == "DEVIL_HORNS":
            self._arm.move_middle_manual(-1)

    #
    # Helper methods for state management and manual control
    #
    def get_state(self) -> State:
        return self._state

    def get_state_name(self) -> str:
        return self._state.name

    def get_mode_name(self) -> str:
        return "AUTOMATIC" if self._is_automatic_mode else "MANUAL"


    def _transition(self, new_state: State) -> None:
        if new_state != self._state:
            log.info("State: %s -> %s", self._state.name, new_state.name)
        self._state = new_state
        self._state_entry_time = time.time()
