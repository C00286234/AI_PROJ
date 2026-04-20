import time
import logging

import config

log = logging.getLogger(__name__)

try:
    import lss
    import lss_const as lssc
    _LSS_AVAILABLE = True
except ImportError:
    log.warning("LSS library not installed — arm_controller running in SIMULATION mode")
    _LSS_AVAILABLE = False


class _FakeServo:
    """Simulated servo for offline development/testing."""
    def __init__(self, servo_id):
        self.servoID = servo_id
        self._pos = 0

    def move(self, pos):
        self._pos = pos

    def getPosition(self):
        return str(self._pos)

    def setColorLED(self, color):
        pass

    def hold(self):
        pass

    def setMaxSpeed(self, speed):
        pass


class ArmController:
    def __init__(self):
        self._servos = {}
        self._current_positions = {sid: 0 for sid in config.ALL_SERVO_IDS}
        self._connected = False
        self._estop = False

    def connect(self) -> bool:
        try:
            if _LSS_AVAILABLE:
                lss.initBus(config.SERIAL_PORT, config.SERIAL_BAUD)
                for sid in config.ALL_SERVO_IDS:
                    self._servos[sid] = lss.LSS(sid)
            else:
                for sid in config.ALL_SERVO_IDS:
                    self._servos[sid] = _FakeServo(sid)

            for sid in config.ALL_SERVO_IDS:
                try:
                    self._servos[sid].setMaxSpeed(config.SERVO_MAX_SPEED)
                except Exception:
                    pass

            for sid in config.ALL_SERVO_IDS:
                self._current_positions[sid] = self.get_position(sid)

            self._connected = True
            log.info("Arm connected")
            return True

        except Exception as exc:
            log.error("connect() failed: %s", exc)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._connected:
            try:
                self.go_home()
                time.sleep(0.3)
            except Exception:
                pass
            try:
                if _LSS_AVAILABLE:
                    lss.closeBus()
            except Exception:
                pass
        self._connected = False
        log.info("Arm disconnected")

    def clamp(self, servo_id, position):
        lo, hi = config.SERVO_LIMITS.get(servo_id, (-9999, 9999))
        return max(lo, min(hi, int(position)))

    #
    # Low level control methods
    #
    def emergency_stop(self) -> None:
        self._estop = True
        for sid, servo in self._servos.items():
            try:
                servo.hold()
            except Exception:
                pass
        log.warning("Emergency stop")

    def clear_estop(self) -> None:
        self._estop = False
        log.info("E-stop cleared")

    def move_servo(self, servo_id, position):
        if self._estop:
            return
        position = self.clamp(servo_id, position)
        try:
            self._servos[servo_id].move(position)
            self._current_positions[servo_id] = position
        except Exception:
            self._connected = False

    def move_servo_smooth(self, servo_id, target):
        if self._estop:
            return

        target = self.clamp(servo_id, target)
        self.move_servo(servo_id, target)
        time.sleep(0.2)

    def move_pose_sequential(self, pose, order):
        for sid in order:
            if sid in pose:
                self.move_servo_smooth(sid, pose[sid])
            if self._estop:
                return

    def move_pose(self, pose):
        self.move_pose_sequential(pose, config.ALL_SERVO_IDS)

    #
    # Manual control methods (for manual mode)
    #
    def nudge_servo(self, servo_id, delta):
        current = self._current_positions.get(servo_id, self.get_position(servo_id))
        self.move_servo(servo_id, current + int(delta))

    def rotate_base_manual(self, direction, step=18):
        if direction == 0:
            return
        self.nudge_servo(config.SERVO_BASE, step if direction > 0 else -step)
        time.sleep(0.05)

    def move_middle_manual(self, direction, step=18):
        if direction == 0:
            return
        self.nudge_servo(config.SERVO_MIDDLE, step if direction > 0 else -step)
        time.sleep(0.05)

    def move_gripper_manual(self, direction, step=18):
        if direction == 0:
            return
        self.nudge_servo(config.SERVO_GRIPPER, step if direction > 0 else -step)
        time.sleep(0.05)

    #
    # Convenience methods for common poses and actions
    #
    def go_home(self) -> None:
        self.move_pose_sequential(config.POSE_HOME,
                                  [config.SERVO_WRIST, config.SERVO_TOP,
                                   config.SERVO_MIDDLE, config.SERVO_BASE,
                                   config.SERVO_GRIPPER])

    def go_ready(self) -> None:
        self.move_pose_sequential(config.POSE_READY,
                                  [config.SERVO_WRIST, config.SERVO_TOP,
                                   config.SERVO_MIDDLE, config.SERVO_BASE,
                                   config.SERVO_GRIPPER])

    def gripper_open(self) -> None:
        self.move_servo_smooth(config.SERVO_GRIPPER, 0)

    def gripper_close(self, position: int = 600) -> None:
        self.move_servo_smooth(config.SERVO_GRIPPER,
                               self.clamp(config.SERVO_GRIPPER, position))

    def get_position(self, servo_id):
        try:
            raw = self._servos[servo_id].getPosition()
            pos = int(raw) if raw is not None else self._current_positions.get(servo_id, 0)
            self._current_positions[servo_id] = pos
            return pos
        except Exception:
            return self._current_positions.get(servo_id, 0)

    def get_all_positions(self):
        return {sid: self.get_position(sid) for sid in config.ALL_SERVO_IDS}

    def is_connected(self) -> bool:
        return self._connected

    def is_estopped(self) -> bool:
        return self._estop
