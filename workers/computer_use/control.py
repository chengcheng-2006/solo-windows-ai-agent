from __future__ import annotations

import math
import threading
from enum import Enum

from pydantic import Field

from .models import Point, StrictModel, utc_now


class ControlStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED_BY_USER = "PAUSED_BY_USER"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class ControlSnapshot(StrictModel):
    status: ControlStatus
    generation: int = Field(ge=0)
    reason_code: str
    changed_at: str
    emergency_hotkey: str


class UserControlState:
    """Thread-safe takeover and emergency-stop state shared with native adapters.

    Native keyboard/mouse hooks remain adapter responsibilities. They must call
    ``signal_hotkey`` and ``notify_pointer_position``; the controller checks this
    state immediately before every side effect and supplies it as a cancellation
    callback while an action is running.
    """

    def __init__(self, emergency_hotkey: str = "CTRL+ALT+ESC", pointer_tolerance_px: float = 8.0) -> None:
        normalized = self._normalize_hotkey(emergency_hotkey)
        if normalized != "CTRL+ALT+ESC":
            raise ValueError("the supported emergency hotkey is Ctrl+Alt+Esc")
        if pointer_tolerance_px < 1 or pointer_tolerance_px > 100:
            raise ValueError("pointer tolerance outside supported range")
        self._hotkey = normalized
        self._pointer_tolerance = pointer_tolerance_px
        self._status = ControlStatus.ACTIVE
        self._reason = "READY"
        self._generation = 0
        self._changed_at = utc_now()
        self._expected_pointer: Point | None = None
        self._lock = threading.RLock()
        self._cancel = threading.Event()

    @staticmethod
    def _normalize_hotkey(value: str) -> str:
        aliases = {"CONTROL": "CTRL", "ESCAPE": "ESC"}
        parts = [aliases.get(part.strip().upper(), part.strip().upper()) for part in value.replace("-", "+").split("+")]
        order = {"CTRL": 0, "ALT": 1, "SHIFT": 2, "ESC": 3}
        return "+".join(sorted((part for part in parts if part), key=lambda part: order.get(part, 10)))

    def snapshot(self) -> ControlSnapshot:
        with self._lock:
            return ControlSnapshot(
                status=self._status,
                generation=self._generation,
                reason_code=self._reason,
                changed_at=self._changed_at.isoformat(),
                emergency_hotkey=self._hotkey,
            )

    def _transition(self, status: ControlStatus, reason_code: str) -> ControlSnapshot:
        with self._lock:
            if self._status == ControlStatus.EMERGENCY_STOPPED and status != ControlStatus.ACTIVE:
                return self.snapshot()
            self._status = status
            self._reason = reason_code
            self._generation += 1
            self._changed_at = utc_now()
            self._expected_pointer = None
            if status == ControlStatus.ACTIVE:
                self._cancel.clear()
            else:
                self._cancel.set()
            return self.snapshot()

    def request_takeover(self, reason_code: str = "USER_TAKEOVER") -> ControlSnapshot:
        return self._transition(ControlStatus.PAUSED_BY_USER, reason_code)

    def signal_protected_window(self) -> ControlSnapshot:
        return self._transition(ControlStatus.PAUSED_BY_USER, "PROTECTED_WINDOW_ACTIVATED")

    def signal_hotkey(self, chord: str) -> ControlSnapshot:
        if self._normalize_hotkey(chord) != self._hotkey:
            return self.snapshot()
        return self._transition(ControlStatus.EMERGENCY_STOPPED, "CTRL_ALT_ESC")

    def arm_pointer_guard(self, expected: Point) -> None:
        with self._lock:
            if self._status == ControlStatus.ACTIVE:
                self._expected_pointer = expected.model_copy(deep=True)

    def record_executor_pointer(self, expected: Point) -> None:
        """Update the expected cursor location after an authorized executor move."""
        self.arm_pointer_guard(expected)

    def notify_pointer_position(self, actual: Point) -> ControlSnapshot:
        with self._lock:
            expected = self._expected_pointer
            if self._status != ControlStatus.ACTIVE or expected is None:
                return self.snapshot()
            if expected.coordinate_space != actual.coordinate_space:
                return self._transition(ControlStatus.PAUSED_BY_USER, "POINTER_COORDINATE_SPACE_CHANGED")
            distance = math.hypot(actual.x - expected.x, actual.y - expected.y)
            if distance > self._pointer_tolerance:
                return self._transition(ControlStatus.PAUSED_BY_USER, "USER_MOVED_POINTER")
            return self.snapshot()

    def resume_by_owner(self) -> ControlSnapshot:
        return self._transition(ControlStatus.ACTIVE, "OWNER_RESUMED")

    def cancellation_requested(self) -> bool:
        return self._cancel.is_set()

    def is_unchanged_and_active(self, snapshot: ControlSnapshot) -> bool:
        with self._lock:
            return self._status == ControlStatus.ACTIVE and self._generation == snapshot.generation
