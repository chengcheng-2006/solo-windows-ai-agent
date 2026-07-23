from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANONICAL_ROLES = {
    "main": "Compatibility entrypoint; must not bypass Menxia for governed work.",
    "taizi": "Message triage, chat detection, requirement shaping, task creation.",
    "zhongshu": "Planning, decomposition, option generation.",
    "menxia": "Independent review, approve/reject, force rework.",
    "shangshu": "Dispatch, coordinate departments, consolidate results.",
    "hubu": "Data, resource, cost, statistics.",
    "libu": "Documentation, standards, reports.",
    "bingbu": "Code, algorithms, engineering work classification.",
    "xingbu": "Security, compliance, audit.",
    "gongbu": "Deployment, CI/CD, infrastructure, automation.",
    "libu_hr": "Agent registry, permissions, capabilities.",
    "zaochao": "Daily briefings, news and scheduled summaries.",
    "zhipu_multimodal_free": "Free multimodal vision analysis using GLM-4.6V-Flash from Zhipu AI (BigModel).",
}


PERMISSION_MATRIX = {
    "main": {"taizi"},
    "taizi": {"zhongshu"},
    "zhongshu": {"menxia", "shangshu"},
    "menxia": {"zhongshu", "shangshu"},
    "shangshu": {"menxia", "zhongshu", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr", "zhipu_multimodal_free"},
    "hubu": {"shangshu"},
    "libu": {"shangshu"},
    "bingbu": {"shangshu"},
    "xingbu": {"shangshu"},
    "gongbu": {"shangshu"},
    "libu_hr": {"shangshu"},
    "zaochao": set(),
}


EDICT_STATES = {
    "INTAKE": {"TRIAGED", "CANCELLED"},
    "TRIAGED": {"PLANNING", "DIRECT_REPLY", "CANCELLED"},
    "PLANNING": {"MENXIA_REVIEW", "CANCELLED"},
    "MENXIA_REVIEW": {"REWORK_REQUIRED", "APPROVED_FOR_DISPATCH", "REJECTED", "CANCELLED"},
    "REWORK_REQUIRED": {"PLANNING", "CANCELLED"},
    "APPROVED_FOR_DISPATCH": {"DISPATCHED", "CANCELLED"},
    "DISPATCHED": {"EXECUTING", "BLOCKED", "CANCELLED"},
    "EXECUTING": {"VALIDATING", "BLOCKED", "CANCELLED"},
    "VALIDATING": {"MENXIA_FINAL_REVIEW", "REWORK_REQUIRED", "FAILED"},
    "MENXIA_FINAL_REVIEW": {"DONE", "REWORK_REQUIRED", "FAILED"},
    "DIRECT_REPLY": {"DONE"},
    "BLOCKED": {"REWORK_REQUIRED", "CANCELLED"},
    "DONE": set(),
    "FAILED": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
}


ROLE_MODEL_POLICY = {
    "main": "free_multimodal",
    "taizi": "free_multimodal",
    "hubu": "free_multimodal",
    "libu": "free_multimodal",
    "libu_hr": "free_multimodal",
    "zaochao": "free_multimodal",
    "shangshu": "free_multimodal",
    "zhongshu": "dynamic_free_or_paid_strong",
    "menxia": "deterministic_plus_free_or_paid_strong",
    "bingbu": "gemini_for_triage_codex_for_execution",
    "gongbu": "gemini_for_triage_codex_for_execution",
    "xingbu": "deterministic_plus_gemini_or_paid_strong",
    "zhipu_multimodal_free": "zhipu_multimodal_free",
}


@dataclass(frozen=True)
class EdictDecision:
    allowed: bool
    code: str
    detail: str


def can_agent_call(caller: str, callee: str) -> bool:
    return callee in PERMISSION_MATRIX.get(caller, set())


def validate_agent_call(caller: str, callee: str) -> EdictDecision:
    if can_agent_call(caller, callee):
        return EdictDecision(True, "AGENT_CALL_ALLOWED", f"{caller}->{callee}")
    return EdictDecision(False, "EDICT_PERMISSION_DENIED", f"{caller}->{callee}")


def can_transition(current: str, desired: str) -> bool:
    return desired in EDICT_STATES.get(current, set())


def validate_transition(current: str, desired: str) -> EdictDecision:
    if can_transition(current, desired):
        return EdictDecision(True, "STATE_TRANSITION_ALLOWED", f"{current}->{desired}")
    return EdictDecision(False, "ILLEGAL_STATE_TRANSITION", f"{current}->{desired}")


def conformance_baseline() -> dict[str, Any]:
    return {
        "canonical_role_count": len(CANONICAL_ROLES),
        "roles": CANONICAL_ROLES,
        "permission_matrix": {k: sorted(v) for k, v in PERMISSION_MATRIX.items()},
        "state_machine": {k: sorted(v) for k, v in EDICT_STATES.items()},
        "role_model_policy": ROLE_MODEL_POLICY,
    }
