from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CoordinateSpace(str, Enum):
    LOGICAL = "LOGICAL"
    PHYSICAL = "PHYSICAL"


class LocateSource(str, Enum):
    DOM = "DOM"
    UIA = "UIA"
    OCR = "OCR"
    VISION = "VISION"
    FUSED = "FUSED"


class RiskLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class ActionKind(str, Enum):
    FOCUS_WINDOW = "focus_window"
    MOVE_MOUSE = "move_mouse"
    LEFT_CLICK = "left_click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    SCROLL = "scroll"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"
    SELECT_TEXT = "select_text"
    DRAG = "drag"
    WAIT = "wait"
    UIA_INVOKE = "uia_invoke"
    UIA_SET_VALUE = "uia_set_value"
    BROWSER_CLICK = "browser_click"
    BROWSER_FILL = "browser_fill"
    BROWSER_SELECT = "browser_select"
    CAPTURE_SCREENSHOT = "capture_screenshot"
    ABORT = "abort"


class ActionEffect(str, Enum):
    NONE = "NONE"
    NAVIGATE = "NAVIGATE"
    EDIT_LOCAL = "EDIT_LOCAL"
    SUBMIT = "SUBMIT"
    SEND_EXTERNAL = "SEND_EXTERNAL"
    DELETE = "DELETE"
    INSTALL = "INSTALL"
    UPLOAD = "UPLOAD"
    PAYMENT = "PAYMENT"


class SensitiveKind(str, Enum):
    PASSWORD = "PASSWORD"
    API_KEY = "API_KEY"
    IDENTITY = "IDENTITY"
    PAYMENT = "PAYMENT"
    PERSONAL_DATA = "PERSONAL_DATA"
    PRIVATE_MESSAGE = "PRIVATE_MESSAGE"
    OTHER = "OTHER"


class Point(StrictModel):
    x: float
    y: float
    coordinate_space: CoordinateSpace = CoordinateSpace.PHYSICAL

    @field_validator("x", "y")
    @classmethod
    def finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("coordinate must be finite")
        return value


class Size(StrictModel):
    width: int = Field(gt=0, le=100_000)
    height: int = Field(gt=0, le=100_000)


class Bounds(StrictModel):
    left: float
    top: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    coordinate_space: CoordinateSpace = CoordinateSpace.PHYSICAL

    @field_validator("left", "top", "width", "height")
    @classmethod
    def finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("bounds must be finite")
        return value

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center(self) -> Point:
        return Point(
            x=self.left + (self.width / 2),
            y=self.top + (self.height / 2),
            coordinate_space=self.coordinate_space,
        )

    def contains(self, point: Point, tolerance: float = 0.0) -> bool:
        if self.coordinate_space != point.coordinate_space:
            return False
        return (
            self.left - tolerance <= point.x <= self.right + tolerance
            and self.top - tolerance <= point.y <= self.bottom + tolerance
        )

    def intersects(self, other: "Bounds") -> bool:
        if self.coordinate_space != other.coordinate_space:
            return False
        return not (
            self.right < other.left
            or other.right < self.left
            or self.bottom < other.top
            or other.bottom < self.top
        )


class MonitorState(StrictModel):
    monitor_id: str = Field(min_length=1, max_length=200)
    bounds: Bounds
    resolution: Size
    dpi_scale: float = Field(ge=0.5, le=5.0)
    primary: bool = False

    @model_validator(mode="after")
    def physical_bounds(self) -> "MonitorState":
        if self.bounds.coordinate_space != CoordinateSpace.PHYSICAL:
            raise ValueError("monitor bounds must use PHYSICAL coordinates")
        return self


class ActiveWindow(StrictModel):
    process_name: str = Field(min_length=1, max_length=260)
    process_id: int = Field(ge=0)
    window_title: str = Field(max_length=2_000)
    window_handle: int | None = Field(default=None, ge=0)
    bounds: Bounds
    monitor_id: str = Field(min_length=1, max_length=200)
    executable_path_redacted: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def physical_bounds(self) -> "ActiveWindow":
        if self.bounds.coordinate_space != CoordinateSpace.PHYSICAL:
            raise ValueError("active window bounds must use PHYSICAL coordinates")
        return self


class ScreenshotReference(StrictModel):
    reference: str = Field(min_length=1, max_length=4_000)
    captured_at: datetime
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    redacted: bool = True
    delete_after: datetime | None = None

    @field_validator("captured_at", "delete_after")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("screenshot timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def cleanup_window(self) -> "ScreenshotReference":
        if self.delete_after is not None:
            if self.delete_after <= self.captured_at:
                raise ValueError("screenshot cleanup must occur after capture")
            if self.delete_after - self.captured_at > timedelta(hours=24):
                raise ValueError("screenshot cleanup exceeds the 24 hour safety ceiling")
        return self

    @field_validator("reference")
    @classmethod
    def d_drive_or_opaque_reference(cls, value: str) -> str:
        allowed_opaque = ("artifact://", "memory://", "redacted://")
        if value.startswith(allowed_opaque):
            return value
        if "://" in value:
            raise ValueError("unsupported screenshot reference scheme")
        normalized = value.replace("/", "\\")
        if normalized.upper().startswith("E:\\"):
            raise ValueError("E drive is forbidden")
        if not normalized.upper().startswith("D:\\"):
            raise ValueError("local screenshot files must be stored on D drive")
        return value


class UIAElement(StrictModel):
    element_id: str = Field(min_length=1, max_length=500)
    automation_id: str = Field(max_length=500)
    name: str = Field(max_length=2_000)
    control_type: str = Field(min_length=1, max_length=200)
    bounds: Bounds
    enabled: bool
    visible: bool
    focused: bool
    value: str | None = Field(default=None, max_length=20_000)
    supported_patterns: list[str] = Field(default_factory=list, max_length=100)


class OCRBlock(StrictModel):
    block_id: str = Field(min_length=1, max_length=500)
    text: str = Field(max_length=20_000)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: Bounds
    language: str = Field(min_length=2, max_length=50)
    source_image: str = Field(min_length=1, max_length=4_000)

    @field_validator("source_image")
    @classmethod
    def no_e_drive(cls, value: str) -> str:
        allowed_opaque = ("artifact://", "memory://", "redacted://")
        if value.startswith(allowed_opaque):
            return value
        if "://" in value:
            raise ValueError("unsupported OCR image reference scheme")
        normalized = value.replace("/", "\\")
        if not normalized.upper().startswith("D:\\"):
            raise ValueError("local OCR images must be stored on D drive")
        return value


class DOMNode(StrictModel):
    node_id: str = Field(min_length=1, max_length=500)
    selector: str = Field(min_length=1, max_length=2_000)
    role: str | None = Field(default=None, max_length=200)
    name: str = Field(default="", max_length=2_000)
    bounds: Bounds | None = None
    enabled: bool = True
    visible: bool = True
    focused: bool = False
    value_redacted: str | None = Field(default=None, max_length=2_000)
    attributes: dict[str, str] = Field(default_factory=dict)


class DOMSnapshot(StrictModel):
    document_id: str = Field(min_length=1, max_length=500)
    origin: str | None = Field(default=None, max_length=2_000)
    title: str = Field(default="", max_length=2_000)
    captured_at: datetime
    nodes: list[DOMNode] = Field(default_factory=list, max_length=20_000)

    @field_validator("captured_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("DOM timestamp must be timezone-aware")
        return value


class LocateCandidate(StrictModel):
    target_description: str = Field(min_length=1, max_length=2_000)
    element_type: str = Field(min_length=1, max_length=200)
    bounding_box: Bounds
    center_point: Point
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=50)
    source: LocateSource
    candidate_id: str = Field(min_length=1, max_length=500)
    enabled: bool = True
    visible: bool = True

    @model_validator(mode="after")
    def center_inside_bounds(self) -> "LocateCandidate":
        if not self.bounding_box.contains(self.center_point, tolerance=1.0):
            raise ValueError("candidate center must be inside its bounding box")
        return self


class VisualModelAnalysis(StrictModel):
    model_id: str = Field(min_length=1, max_length=500)
    summary: str = Field(max_length=10_000)
    confidence: float = Field(ge=0.0, le=1.0)
    candidates: list[LocateCandidate] = Field(default_factory=list, max_length=500)
    latency_ms: int | None = Field(default=None, ge=0)


class SensitiveRegion(StrictModel):
    region_id: str = Field(min_length=1, max_length=500)
    kind: SensitiveKind
    bounding_box: Bounds
    reason_code: str = Field(min_length=1, max_length=500)
    redacted: bool = True


class AvailableAction(StrictModel):
    kind: ActionKind
    target_id: str | None = Field(default=None, max_length=500)
    risk_hint: RiskLevel = RiskLevel.R1
    reason_code: str = Field(default="OBSERVED", max_length=500)


def compute_window_fingerprint(
    active_window: ActiveWindow,
    resolution: Size,
    dpi_scale: float,
) -> str:
    document = {
        "process_name": active_window.process_name.lower(),
        "process_id": active_window.process_id,
        "window_title": active_window.window_title,
        "window_handle": active_window.window_handle,
        "bounds": active_window.bounds.model_dump(mode="json"),
        "monitor_id": active_window.monitor_id,
        "resolution": resolution.model_dump(mode="json"),
        "dpi_scale": dpi_scale,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class Observation(StrictModel):
    observation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(default_factory=lambda: utc_now() + timedelta(seconds=30))
    active_window: ActiveWindow
    process_name: str | None = Field(default=None, max_length=260)
    window_title: str | None = Field(default=None, max_length=2_000)
    window_bounds: Bounds | None = None
    monitor_id: str
    resolution: Size
    dpi_scale: float = Field(ge=0.5, le=5.0)
    screenshot_reference: ScreenshotReference | None = None
    uia_tree: list[UIAElement] = Field(default_factory=list, max_length=20_000)
    ocr_blocks: list[OCRBlock] = Field(default_factory=list, max_length=20_000)
    dom_snapshot: DOMSnapshot | None = None
    visual_model_analysis: VisualModelAnalysis | None = None
    detected_sensitive_regions: list[SensitiveRegion] = Field(default_factory=list, max_length=2_000)
    available_actions: list[AvailableAction] = Field(default_factory=list, max_length=2_000)
    monitors: list[MonitorState] = Field(default_factory=list, max_length=32)
    window_fingerprint: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("timestamp", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observation timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "Observation":
        if self.expires_at <= self.timestamp:
            raise ValueError("observation must expire after it is captured")
        if self.expires_at - self.timestamp > timedelta(minutes=5):
            raise ValueError("observation TTL exceeds the five minute safety ceiling")
        if self.monitor_id != self.active_window.monitor_id:
            raise ValueError("active window monitor does not match observation monitor")
        monitor_ids = {monitor.monitor_id for monitor in self.monitors}
        if monitor_ids and self.monitor_id not in monitor_ids:
            raise ValueError("observation monitor is absent from monitor inventory")
        if self.process_name is not None and self.process_name != self.active_window.process_name:
            raise ValueError("process_name does not match active_window")
        if self.window_title is not None and self.window_title != self.active_window.window_title:
            raise ValueError("window_title does not match active_window")
        if self.window_bounds is not None and self.window_bounds != self.active_window.bounds:
            raise ValueError("window_bounds does not match active_window")
        self.process_name = self.active_window.process_name
        self.window_title = self.active_window.window_title
        self.window_bounds = self.active_window.bounds
        expected = compute_window_fingerprint(self.active_window, self.resolution, self.dpi_scale)
        if self.window_fingerprint is not None and self.window_fingerprint.lower() != expected:
            raise ValueError("window fingerprint does not match observation")
        self.window_fingerprint = expected
        if self.detected_sensitive_regions and self.screenshot_reference is not None:
            if not self.screenshot_reference.redacted:
                raise ValueError("screenshots containing sensitive regions must be redacted")
            if self.screenshot_reference.delete_after is None:
                raise ValueError("sensitive screenshots require automatic cleanup")
            if self.screenshot_reference.delete_after > self.timestamp + timedelta(minutes=10):
                raise ValueError("sensitive screenshot cleanup exceeds ten minutes")
        return self

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or utc_now()) >= self.expires_at


class ActionTarget(StrictModel):
    target_id: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=2_000)
    element_type: str = Field(min_length=1, max_length=200)
    source: LocateSource
    bounding_box: Bounds
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=50)
    enabled: bool = True
    visible: bool = True


COORDINATE_ACTIONS = frozenset(
    {
        ActionKind.MOVE_MOUSE,
        ActionKind.LEFT_CLICK,
        ActionKind.DOUBLE_CLICK,
        ActionKind.RIGHT_CLICK,
        ActionKind.SCROLL,
        ActionKind.DRAG,
    }
)


class ComputerAction(StrictModel):
    task_id: UUID
    action_id: UUID = Field(default_factory=uuid4)
    kind: ActionKind
    observation_id: UUID | None = None
    window_fingerprint: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    target: ActionTarget | None = None
    point: Point | None = None
    end_point: Point | None = None
    scroll_amount: int | None = Field(default=None, ge=-100_000, le=100_000)
    text: str | None = Field(default=None, max_length=50_000)
    key: str | None = Field(default=None, max_length=100)
    keys: list[str] = Field(default_factory=list, max_length=16)
    selector: str | None = Field(default=None, max_length=2_000)
    value: str | None = Field(default=None, max_length=50_000)
    duration_ms: int | None = Field(default=None, ge=0, le=60_000)
    effect: ActionEffect = ActionEffect.NONE
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("action timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def action_contract(self) -> "ComputerAction":
        if self.kind in COORDINATE_ACTIONS:
            if self.observation_id is None or self.window_fingerprint is None:
                raise ValueError("coordinate actions require an observation and window fingerprint")
        if self.kind in {
            ActionKind.MOVE_MOUSE,
            ActionKind.LEFT_CLICK,
            ActionKind.DOUBLE_CLICK,
            ActionKind.RIGHT_CLICK,
        } and self.point is None and self.target is None:
            raise ValueError("pointer action requires a point or located target")
        if self.kind == ActionKind.DRAG and (self.point is None or self.end_point is None):
            raise ValueError("drag requires start and end points")
        if self.kind == ActionKind.SCROLL and self.scroll_amount in (None, 0):
            raise ValueError("scroll requires a non-zero amount")
        if self.kind == ActionKind.TYPE_TEXT and not self.text:
            raise ValueError("type_text requires text")
        if self.kind == ActionKind.PRESS_KEY and not self.key:
            raise ValueError("press_key requires key")
        if self.kind == ActionKind.HOTKEY and len(self.keys) < 2:
            raise ValueError("hotkey requires at least two keys")
        if self.kind == ActionKind.WAIT and self.duration_ms is None:
            raise ValueError("wait requires duration_ms")
        if self.kind in {ActionKind.UIA_INVOKE, ActionKind.UIA_SET_VALUE} and self.target is None:
            raise ValueError("UIA action requires a located target")
        if self.kind == ActionKind.UIA_SET_VALUE and self.value is None:
            raise ValueError("uia_set_value requires value")
        if self.kind in {ActionKind.BROWSER_CLICK, ActionKind.BROWSER_FILL, ActionKind.BROWSER_SELECT}:
            if self.target is None and not self.selector:
                raise ValueError("browser action requires a DOM target or selector")
        if self.kind in {ActionKind.BROWSER_FILL, ActionKind.BROWSER_SELECT} and self.value is None:
            raise ValueError("browser fill/select requires value")
        return self

    @property
    def binding_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ApprovalGrant(StrictModel):
    token_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    action_binding_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    risk_level: RiskLevel
    decision: str = Field(pattern=r"^APPROVED$")
    approved_by: str = Field(min_length=1, max_length=200)
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("approval timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def valid_interval(self) -> "ApprovalGrant":
        if self.expires_at <= self.issued_at:
            raise ValueError("approval must expire after it is issued")
        if self.expires_at - self.issued_at > timedelta(hours=1):
            raise ValueError("approval lifetime exceeds one hour")
        return self

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or utc_now()) >= self.expires_at


class ActionPlan(StrictModel):
    action: ComputerAction
    approval: ApprovalGrant | None = None


class ObservationScope(StrictModel):
    mode: str = Field(pattern=r"^(ACTIVE_WINDOW|WINDOW|MONITOR|FULL_SCREEN|REGION)$")
    window_handle: int | None = Field(default=None, ge=0)
    monitor_id: str | None = Field(default=None, max_length=200)
    region: Bounds | None = None
    include_dom: bool = True
    include_uia: bool = True
    include_ocr: bool = True
    include_vision: bool = False

    @model_validator(mode="after")
    def required_target(self) -> "ObservationScope":
        if self.mode == "WINDOW" and self.window_handle is None:
            raise ValueError("WINDOW scope requires window_handle")
        if self.mode == "MONITOR" and not self.monitor_id:
            raise ValueError("MONITOR scope requires monitor_id")
        if self.mode == "REGION" and self.region is None:
            raise ValueError("REGION scope requires region")
        return self


class PolicyDecision(StrictModel):
    allowed: bool
    risk_level: RiskLevel
    code: str = Field(min_length=1, max_length=200)
    reasons: list[str] = Field(default_factory=list, max_length=100)
    requires_approval: bool = False
    should_pause: bool = False
    checks: list[str] = Field(default_factory=list, max_length=100)


class ActionExecution(StrictModel):
    action_id: UUID
    status: str = Field(pattern=r"^(PASS|FAIL|ABORTED|PAUSED)$")
    started_at: datetime
    finished_at: datetime
    result_code: str = Field(min_length=1, max_length=500)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "finished_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("execution timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def ordered_timestamps(self) -> "ActionExecution":
        if self.finished_at < self.started_at:
            raise ValueError("execution cannot finish before it starts")
        return self


class ActionValidation(StrictModel):
    passed: bool
    code: str = Field(min_length=1, max_length=500)
    checks: list[str] = Field(default_factory=list, max_length=100)
    details: dict[str, Any] = Field(default_factory=dict)


class ControllerResult(StrictModel):
    status: str = Field(
        pattern=r"^(PASS|POLICY_DENIED|OBSERVATION_FAILED|PLANNING_FAILED|VALIDATION_FAILED|EXECUTION_FAILED|PAUSED_BY_USER|EMERGENCY_STOPPED)$"
    )
    task_id: UUID
    attempts: int = Field(ge=0, le=10)
    observation_ids: list[UUID] = Field(default_factory=list, max_length=20)
    action_ids: list[UUID] = Field(default_factory=list, max_length=10)
    policy_decision: PolicyDecision | None = None
    execution: ActionExecution | None = None
    validation: ActionValidation | None = None
    reason_code: str = Field(min_length=1, max_length=500)
