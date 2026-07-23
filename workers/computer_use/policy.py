from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import Field, field_validator

from .coordinates import CoordinateMapper
from .models import (
    ActionEffect,
    ActionKind,
    ApprovalGrant,
    Bounds,
    ComputerAction,
    CoordinateSpace,
    LocateSource,
    Observation,
    Point,
    PolicyDecision,
    RiskLevel,
    SensitiveKind,
    StrictModel,
    utc_now,
)


_RISK_ORDER = {RiskLevel.R0: 0, RiskLevel.R1: 1, RiskLevel.R2: 2, RiskLevel.R3: 3}


class PolicyConfig(StrictModel):
    max_attempts: int = Field(default=3, ge=1, le=3)
    max_clock_skew_seconds: int = Field(default=5, ge=0, le=30)
    owner_approver: str = Field(default="owner", min_length=1, max_length=200)
    confidence_thresholds: dict[LocateSource, float] = Field(
        default_factory=lambda: {
            LocateSource.DOM: 0.75,
            LocateSource.UIA: 0.80,
            LocateSource.OCR: 0.88,
            LocateSource.VISION: 0.92,
            LocateSource.FUSED: 0.88,
        }
    )
    protected_processes: list[str] = Field(
        default_factory=lambda: [
            "credentialuibroker.exe",
            "consent.exe",
            "logonui.exe",
            "keepass.exe",
            "1password.exe",
            "bitwarden.exe",
        ]
    )
    protected_title_fragments: list[str] = Field(
        default_factory=lambda: [
            "windows security",
            "user account control",
            "credential",
            "password manager",
            "windows 安全中心",
            "用户帐户控制",
            "凭据",
            "密码管理器",
        ]
    )

    @field_validator("confidence_thresholds")
    @classmethod
    def complete_thresholds(cls, values: dict[LocateSource, float]) -> dict[LocateSource, float]:
        if set(values) != set(LocateSource):
            raise ValueError("confidence thresholds must cover every locate source")
        if any(value < 0 or value > 1 for value in values.values()):
            raise ValueError("confidence threshold outside 0..1")
        return values

    @classmethod
    def from_json(cls, path: Path) -> "PolicyConfig":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


class ComputerUsePolicy:
    _RISK_BY_ACTION = {
        ActionKind.ABORT: RiskLevel.R0,
        ActionKind.WAIT: RiskLevel.R0,
        ActionKind.CAPTURE_SCREENSHOT: RiskLevel.R0,
        ActionKind.MOVE_MOUSE: RiskLevel.R0,
        ActionKind.FOCUS_WINDOW: RiskLevel.R1,
        ActionKind.LEFT_CLICK: RiskLevel.R1,
        ActionKind.DOUBLE_CLICK: RiskLevel.R1,
        ActionKind.RIGHT_CLICK: RiskLevel.R1,
        ActionKind.SCROLL: RiskLevel.R1,
        ActionKind.SELECT_TEXT: RiskLevel.R1,
        ActionKind.DRAG: RiskLevel.R2,
        ActionKind.TYPE_TEXT: RiskLevel.R2,
        ActionKind.PRESS_KEY: RiskLevel.R2,
        ActionKind.HOTKEY: RiskLevel.R2,
        ActionKind.UIA_INVOKE: RiskLevel.R2,
        ActionKind.UIA_SET_VALUE: RiskLevel.R2,
        ActionKind.BROWSER_CLICK: RiskLevel.R2,
        ActionKind.BROWSER_FILL: RiskLevel.R2,
        ActionKind.BROWSER_SELECT: RiskLevel.R2,
    }
    _R3_EFFECTS = {
        ActionEffect.SUBMIT,
        ActionEffect.SEND_EXTERNAL,
        ActionEffect.DELETE,
        ActionEffect.INSTALL,
        ActionEffect.UPLOAD,
        ActionEffect.PAYMENT,
    }
    _R3_TARGET_TERMS = (
        "send",
        "submit",
        "delete",
        "install",
        "upload",
        "pay",
        "purchase",
        "publish",
        "发送",
        "提交",
        "删除",
        "安装",
        "上传",
        "付款",
        "支付",
        "购买",
        "发布",
    )
    _SECRET_PATTERNS = (
        re.compile(r"(?i)\b(?:password|passwd|api[_ -]?key|access[_ -]?token|secret)\s*[:=]"),
        re.compile(r"(?i)\bsk-[a-z0-9_-]{12,}"),
        re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
        re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)"),
    )
    _INTERACTIVE = frozenset(ActionKind) - {
        ActionKind.ABORT,
        ActionKind.WAIT,
        ActionKind.CAPTURE_SCREENSHOT,
    }

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()

    def is_protected_window(self, observation: Observation) -> bool:
        process = observation.process_name.lower()
        title = observation.window_title.lower()
        return any(item.lower() in process for item in self.config.protected_processes) or any(
            item.lower() in title for item in self.config.protected_title_fragments
        )

    def classify_risk(self, action: ComputerAction, observation: Observation) -> RiskLevel:
        risk = self._RISK_BY_ACTION[action.kind]
        description = action.target.description.lower() if action.target else ""
        if action.effect in self._R3_EFFECTS or any(term in description for term in self._R3_TARGET_TERMS):
            risk = RiskLevel.R3
        if action.effect == ActionEffect.EDIT_LOCAL and _RISK_ORDER[risk] < _RISK_ORDER[RiskLevel.R2]:
            risk = RiskLevel.R2
        impacted = self._impacted_sensitive_regions(action, observation)
        if any(region.kind in {SensitiveKind.PAYMENT, SensitiveKind.IDENTITY, SensitiveKind.PERSONAL_DATA} for region in impacted):
            risk = RiskLevel.R3
        return risk

    @staticmethod
    def _monitor_bounds(observation: Observation) -> Bounds:
        for monitor in observation.monitors:
            if monitor.monitor_id == observation.monitor_id:
                return monitor.bounds
        return Bounds(
            left=0,
            top=0,
            width=observation.resolution.width,
            height=observation.resolution.height,
            coordinate_space=CoordinateSpace.PHYSICAL,
        )

    def _physical_point(self, point: Point, observation: Observation) -> Point:
        mapper = CoordinateMapper(observation.dpi_scale, self._monitor_bounds(observation))
        return mapper.point(point, CoordinateSpace.PHYSICAL)

    def _physical_bounds(self, bounds: Bounds, observation: Observation) -> Bounds:
        mapper = CoordinateMapper(observation.dpi_scale, self._monitor_bounds(observation))
        return mapper.bounds(bounds, CoordinateSpace.PHYSICAL)

    def _action_points(self, action: ComputerAction, observation: Observation) -> list[Point]:
        points: list[Point] = []
        if action.point is not None:
            points.append(self._physical_point(action.point, observation))
        elif action.target is not None:
            points.append(self._physical_point(action.target.bounding_box.center, observation))
        if action.end_point is not None:
            points.append(self._physical_point(action.end_point, observation))
        return points

    def _impacted_sensitive_regions(self, action: ComputerAction, observation: Observation):
        if not observation.detected_sensitive_regions:
            return []
        if action.kind in {ActionKind.TYPE_TEXT, ActionKind.UIA_SET_VALUE, ActionKind.BROWSER_FILL} and action.target is None:
            return list(observation.detected_sensitive_regions)
        target_bounds = self._physical_bounds(action.target.bounding_box, observation) if action.target else None
        points = self._action_points(action, observation)
        impacted = []
        for region in observation.detected_sensitive_regions:
            physical = self._physical_bounds(region.bounding_box, observation)
            if (target_bounds and physical.intersects(target_bounds)) or any(physical.contains(point) for point in points):
                impacted.append(region)
        return impacted

    @classmethod
    def _contains_secret_material(cls, action: ComputerAction) -> bool:
        values = [value for value in (action.text, action.value) if value]
        return any(pattern.search(value) for value in values for pattern in cls._SECRET_PATTERNS)

    def _approval_valid(
        self,
        action: ComputerAction,
        approval: ApprovalGrant | None,
        risk: RiskLevel,
        now: datetime,
    ) -> tuple[bool, str]:
        if approval is None:
            return False, "APPROVAL_REQUIRED"
        if approval.task_id != action.task_id:
            return False, "APPROVAL_TASK_MISMATCH"
        if approval.action_binding_sha256.lower() != action.binding_hash:
            return False, "APPROVAL_ACTION_MISMATCH"
        if approval.is_expired(now):
            return False, "APPROVAL_EXPIRED"
        if approval.issued_at > now + timedelta(seconds=self.config.max_clock_skew_seconds):
            return False, "APPROVAL_FROM_FUTURE"
        if _RISK_ORDER[approval.risk_level] < _RISK_ORDER[risk]:
            return False, "APPROVAL_RISK_MISMATCH"
        if risk == RiskLevel.R3 and approval.approved_by != self.config.owner_approver:
            return False, "R3_OWNER_APPROVAL_REQUIRED"
        return True, "APPROVAL_BOUND"

    def evaluate(
        self,
        action: ComputerAction,
        observation: Observation,
        approval: ApprovalGrant | None = None,
        *,
        attempt: int = 1,
        now: datetime | None = None,
    ) -> PolicyDecision:
        checked_at = now or utc_now()
        risk = self.classify_risk(action, observation)
        checks: list[str] = ["SCHEMA_VALID", "TASK_ID_PRESENT"]

        def deny(code: str, reason: str, *, pause: bool = False, approval_required: bool = False) -> PolicyDecision:
            return PolicyDecision(
                allowed=False,
                risk_level=risk,
                code=code,
                reasons=[reason],
                requires_approval=approval_required,
                should_pause=pause,
                checks=checks,
            )

        if attempt < 1 or attempt > self.config.max_attempts:
            return deny("RETRY_BUDGET_EXHAUSTED", "action attempt exceeds the finite retry budget")
        checks.append("RETRY_BUDGET_VALID")
        if observation.timestamp > checked_at + timedelta(seconds=self.config.max_clock_skew_seconds):
            return deny("OBSERVATION_FROM_FUTURE", "observation timestamp exceeds allowed clock skew")
        if observation.is_expired(checked_at):
            return deny("OBSERVATION_EXPIRED", "observation TTL has expired")
        checks.append("OBSERVATION_FRESH")
        if self.is_protected_window(observation):
            return deny("PROTECTED_WINDOW", "active window is protected", pause=True)
        checks.append("WINDOW_NOT_PROTECTED")
        if action.kind in self._INTERACTIVE:
            if action.observation_id != observation.observation_id:
                return deny("STALE_OBSERVATION_BINDING", "action is not bound to the current observation")
            if action.window_fingerprint != observation.window_fingerprint:
                return deny("WINDOW_CHANGED", "window position, DPI, title, or identity changed")
        checks.append("WINDOW_BINDING_VALID")
        if action.kind == ActionKind.HOTKEY and {key.upper() for key in action.keys} == {"CTRL", "ALT", "ESC"}:
            return deny("EMERGENCY_HOTKEY_RESERVED", "Ctrl+Alt+Esc is reserved for emergency stop")
        if self._contains_secret_material(action):
            return deny("SENSITIVE_TEXT_FORBIDDEN", "password, API key, identity, or payment-like text is forbidden")
        checks.append("PAYLOAD_SECRET_SAFE")

        monitor_bounds = self._monitor_bounds(observation)
        for point in self._action_points(action, observation):
            if not monitor_bounds.contains(point) or not observation.active_window.bounds.contains(point):
                return deny("COORDINATE_OUT_OF_BOUNDS", "action coordinate is outside the current window or monitor")
        if action.target is not None:
            if not action.target.visible:
                return deny("TARGET_NOT_VISIBLE", "located target is not visible")
            if not action.target.enabled:
                return deny("TARGET_DISABLED", "located target is disabled")
            threshold = self.config.confidence_thresholds[action.target.source]
            if action.target.confidence < threshold:
                return deny("LOW_LOCATION_CONFIDENCE", "located target is below the execution confidence threshold")
            target_bounds = self._physical_bounds(action.target.bounding_box, observation)
            if not target_bounds.intersects(observation.active_window.bounds):
                return deny("TARGET_OUT_OF_WINDOW", "located target is outside the active window")
            if action.kind in {ActionKind.BROWSER_CLICK, ActionKind.BROWSER_FILL, ActionKind.BROWSER_SELECT} and action.target.source not in {
                LocateSource.DOM,
                LocateSource.FUSED,
            }:
                return deny("BROWSER_SOURCE_INVALID", "browser actions require DOM or fused evidence")
            if action.kind in {ActionKind.UIA_INVOKE, ActionKind.UIA_SET_VALUE} and action.target.source not in {
                LocateSource.UIA,
                LocateSource.FUSED,
            }:
                return deny("UIA_SOURCE_INVALID", "UIA actions require UIA or fused evidence")
        if action.kind in {ActionKind.BROWSER_CLICK, ActionKind.BROWSER_FILL, ActionKind.BROWSER_SELECT} and action.target is None:
            nodes = observation.dom_snapshot.nodes if observation.dom_snapshot is not None else []
            node = next((item for item in nodes if item.selector == action.selector), None)
            if node is None:
                return deny("DOM_SELECTOR_NOT_OBSERVED", "browser selector is absent from the current DOM snapshot")
            if not node.visible:
                return deny("TARGET_NOT_VISIBLE", "DOM selector is not visible")
            if not node.enabled:
                return deny("TARGET_DISABLED", "DOM selector is disabled")
        checks.extend(["BOUNDS_VALID", "LOCATION_CONFIDENCE_VALID"])

        impacted = self._impacted_sensitive_regions(action, observation)
        if any(region.kind in {SensitiveKind.PASSWORD, SensitiveKind.API_KEY} for region in impacted):
            return deny("PROTECTED_SECRET_REGION", "actions on password or API key regions are forbidden", pause=True)
        checks.append("SENSITIVE_REGION_POLICY_VALID")
        requires_approval = risk in {RiskLevel.R2, RiskLevel.R3}
        if requires_approval:
            valid, code = self._approval_valid(action, approval, risk, checked_at)
            if not valid:
                return deny(code, "a current approval bound to task, action, parameters, and risk is required", approval_required=True)
            checks.append(code)
        return PolicyDecision(
            allowed=True,
            risk_level=risk,
            code="ALLOWED",
            reasons=["all deterministic policy checks passed"],
            requires_approval=requires_approval,
            should_pause=False,
            checks=checks,
        )
