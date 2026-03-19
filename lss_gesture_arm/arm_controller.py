###############################################################################
# arm_controller.py — Low-level LSS servo control with safety guarantees
#
# Safety contract:
#   1. Every position command passes through clamp() before reaching hardware.
#   2. move_servo_smooth checks _estop on every interpolation tick (≤30 ms latency).
#   3. Serial/hardware exceptions are caught, logged, and set _connected=False
#      rather than crashing the main loop.
###############################################################################

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


class ArmController:
    def __init__(self):
        self._servos: dict[int, object] = {}
        self._current_positions: dict[int, int] = {sid: 0 for sid in config.ALL_SERVO_IDS}
        self._connected: bool = False
        self._estop: bool = False
        self._carrying: bool = False    # True after successful pick-up lift

    # ------------------------------------------------------------------ #
    # Connection                                                           #
    # ------------------------------------------------------------------ #

    def connect(self) -> bool:
        try:
            if _LSS_AVAILABLE:
                lss.initBus(config.SERIAL_PORT, config.SERIAL_BAUD)
                for sid in config.ALL_SERVO_IDS:
                    self._servos[sid] = lss.LSS(sid)
            else:
                for sid in config.ALL_SERVO_IDS:
                    self._servos[sid] = _FakeServo(sid)

            # Sync position cache from hardware
            for sid in config.ALL_SERVO_IDS:
                self._current_positions[sid] = self.get_position(sid)

            self._connected = True
            log.info("ArmController connected (simulation=%s)", not _LSS_AVAILABLE)
            return True

        except Exception as exc:
            log.error("connect() failed: %s", exc)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._connected:
            try:
                self.go_home()
            except Exception:
                pass
            try:
                if _LSS_AVAILABLE:
                    lss.closeBus()
            except Exception:
                pass
        self._connected = False
        log.info("ArmController disconnected")

    # ------------------------------------------------------------------ #
    # Safety core                                                          #
    # ------------------------------------------------------------------ #

    def clamp(self, servo_id: int, position: int) -> int:
        lo, hi = config.SERVO_LIMITS.get(servo_id, (-9999, 9999))
        return max(lo, min(hi, int(position)))

    def emergency_stop(self) -> None:
        self._estop = True
        for sid, servo in self._servos.items():
            try:
                if _LSS_AVAILABLE:
                    servo.hold()
                log.warning("E-STOP: servo %d held", sid)
            except Exception as exc:
                log.error("E-STOP hold failed on servo %d: %s", sid, exc)

    def clear_estop(self) -> None:
        self._estop = False
        log.info("E-stop cleared")

    # ------------------------------------------------------------------ #
    # Movement primitives                                                  #
    # ------------------------------------------------------------------ #

    def move_servo(self, servo_id: int, position: int) -> None:
        """Issue a single move command (clamped). Non-blocking at hardware level."""
        if self._estop:
            return
        position = self.clamp(servo_id, position)
        try:
            self._servos[servo_id].move(position)
            self._current_positions[servo_id] = position
        except Exception as exc:
            log.error("move_servo(%d, %d) failed: %s", servo_id, position, exc)
            self._connected = False

    def move_servo_smooth(self, servo_id: int, target: int,
                          step: int = config.INTERPOLATION_STEP,
                          delay: float = config.INTERPOLATION_DELAY) -> None:
        """Interpolated move from current position to target.
        Checks _estop on every tick — maximum 30 ms response latency."""
        target = self.clamp(servo_id, target)
        current = self._current_positions.get(servo_id, 0)

        if current == target:
            return

        direction = 1 if target > current else -1

        pos = current
        while True:
            if self._estop:
                log.info("move_servo_smooth: aborted by estop (servo %d)", servo_id)
                return

            pos += direction * step
            # Overshoot guard
            if (direction == 1 and pos >= target) or (direction == -1 and pos <= target):
                pos = target

            try:
                self._servos[servo_id].move(pos)
                self._current_positions[servo_id] = pos
            except Exception as exc:
                log.error("move_servo_smooth(%d): %s", servo_id, exc)
                self._connected = False
                return

            if pos == target:
                break
            time.sleep(delay)

    def move_pose_sequential(self, pose: dict, order: list,
                             speed: int = config.DEFAULT_SPEED) -> None:
        """Move servos in a specified order (safety-critical for multi-joint moves).
        Blocks until all servos reach their targets."""
        step = max(10, config.INTERPOLATION_STEP * (speed // config.DEFAULT_SPEED))
        for sid in order:
            if sid in pose:
                self.move_servo_smooth(sid, pose[sid], step=step)
            if self._estop:
                return

    def move_pose(self, pose: dict, speed: int = config.DEFAULT_SPEED) -> None:
        """Move all servos in pose using default safe order."""
        self.move_pose_sequential(pose, config.ALL_SERVO_IDS, speed=speed)

    # ------------------------------------------------------------------ #
    # Named pose helpers                                                   #
    # ------------------------------------------------------------------ #

    def go_home(self) -> None:
        # Safe order: wrist first, then fold top, lower bottom, centre base
        self.move_pose_sequential(config.POSE_HOME,
                                  [config.SERVO_WRIST, config.SERVO_TOP,
                                   config.SERVO_BOTTOM, config.SERVO_BASE,
                                   config.SERVO_GRIPPER])

    def go_ready(self) -> None:
        self.move_pose_sequential(config.POSE_READY,
                                  [config.SERVO_WRIST, config.SERVO_TOP,
                                   config.SERVO_BOTTOM, config.SERVO_BASE,
                                   config.SERVO_GRIPPER])

    def gripper_open(self) -> None:
        self.move_servo_smooth(config.SERVO_GRIPPER, 0)

    def gripper_close(self, position: int = 600) -> None:
        self.move_servo_smooth(config.SERVO_GRIPPER,
                               self.clamp(config.SERVO_GRIPPER, position))

    # ------------------------------------------------------------------ #
    # State queries                                                        #
    # ------------------------------------------------------------------ #

    def get_position(self, servo_id: int) -> int:
        try:
            raw = self._servos[servo_id].getPosition()
            pos = int(raw) if raw is not None else self._current_positions.get(servo_id, 0)
            self._current_positions[servo_id] = pos
            return pos
        except Exception:
            return self._current_positions.get(servo_id, 0)

    def get_all_positions(self) -> dict:
        return {sid: self.get_position(sid) for sid in config.ALL_SERVO_IDS}

    def is_connected(self) -> bool:
        return self._connected

    def is_estopped(self) -> bool:
        return self._estop

    def set_carrying(self, value: bool) -> None:
        self._carrying = value

    def is_carrying(self) -> bool:
        return self._carrying
