from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schemas import utc_now


GEMINI_DPAPI_STORE_PATH = Path(
    os.environ.get("PAIOS_GEMINI_DPAPI_STORE")
    or r"C:\Users\35331\.openclaw\secrets\gemini-dpapi-store.json"
)
GEMINI_PROVIDER_STATUS_PATH = Path(
    os.environ.get("PAIOS_GEMINI_PROVIDER_STATUS")
    or r"D:\OpenClaw-Hermes-Integration\state\gemini_provider_status.json"
)


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS paios_tasks (
  task_id TEXT PRIMARY KEY,
  correlation_id TEXT NOT NULL,
  source_channel TEXT NOT NULL,
  user_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  risk TEXT NOT NULL,
  selected_model TEXT NOT NULL,
  executor TEXT NOT NULL,
  status TEXT NOT NULL,
  phase TEXT NOT NULL,
  completed_steps_json TEXT NOT NULL,
  pending_steps_json TEXT NOT NULL,
  approval_state TEXT NOT NULL,
  artifacts_json TEXT NOT NULL,
  error_json TEXT NOT NULL,
  retry_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  heartbeat_at TEXT,
  checkpoint_json TEXT NOT NULL,
  final_result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paios_tasks_status ON paios_tasks(status);
CREATE INDEX IF NOT EXISTS idx_paios_tasks_correlation ON paios_tasks(correlation_id);

CREATE TABLE IF NOT EXISTS paios_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  task_id TEXT,
  correlation_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  delivered_at TEXT,
  dead_letter_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_paios_events_task ON paios_events(task_id);
CREATE INDEX IF NOT EXISTS idx_paios_events_type ON paios_events(event_type);

CREATE TABLE IF NOT EXISTS paios_memories (
  memory_id TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  channel TEXT NOT NULL,
  project TEXT NOT NULL,
  memory_key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  source TEXT NOT NULL,
  version INTEGER NOT NULL,
  permissions_json TEXT NOT NULL,
  expires_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  UNIQUE(scope, channel, project, memory_key, version)
);
CREATE INDEX IF NOT EXISTS idx_paios_memories_lookup
  ON paios_memories(scope, channel, project, memory_key, deleted_at);

CREATE TABLE IF NOT EXISTS paios_routing_decisions (
  decision_id TEXT PRIMARY KEY,
  task_id TEXT,
  message_hash TEXT NOT NULL,
  risk TEXT NOT NULL,
  reasoning_class TEXT NOT NULL,
  workload_class TEXT NOT NULL,
  selected_layer TEXT NOT NULL,
  selected_model TEXT NOT NULL,
  executor TEXT NOT NULL,
  requires_approval INTEGER NOT NULL,
  fallback_executor TEXT,
  decision_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paios_policy_decisions (
  decision_id TEXT PRIMARY KEY,
  task_id TEXT,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  result TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paios_audit_records (
  audit_id TEXT PRIMARY KEY,
  task_id TEXT,
  actor TEXT NOT NULL,
  channel TEXT NOT NULL,
  action TEXT NOT NULL,
  tool TEXT,
  model TEXT,
  files_json TEXT NOT NULL,
  command_summary TEXT,
  approved INTEGER NOT NULL,
  result TEXT NOT NULL,
  redacted INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paios_agent_leases (
  lease_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  worker_id TEXT NOT NULL,
  role TEXT NOT NULL,
  batch_json TEXT NOT NULL,
  status TEXT NOT NULL,
  lease_until TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paios_health_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  component TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  checked_at TEXT NOT NULL
);
"""


SECRET_MARKERS = ("sk-", "api_key", "token=", "authorization:", "bearer ")


@dataclass(frozen=True)
class RoutingDecision:
    risk: str
    reasoning_class: str
    workload_class: str
    selected_layer: str
    selected_model: str
    executor: str
    symbolic_model: str
    selected_provider: str | None
    auth_mode: str
    credential_ref: str | None
    configured: bool
    runtime_available: bool
    routing_enabled: bool
    requires_approval: bool
    fallback_executor: str | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk": self.risk,
            "reasoning_class": self.reasoning_class,
            "workload_class": self.workload_class,
            "selected_layer": self.selected_layer,
            "selected_model": self.selected_model,
            "executor": self.executor,
            "symbolic_model": self.symbolic_model,
            "selected_provider": self.selected_provider,
            "auth_mode": self.auth_mode,
            "credential_ref": self.credential_ref,
            "configured": self.configured,
            "runtime_available": self.runtime_available,
            "routing_enabled": self.routing_enabled,
            "requires_approval": self.requires_approval,
            "fallback_executor": self.fallback_executor,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    executor: str
    model: str | None
    configured: bool
    runtime_available: bool
    routing_enabled: bool
    auth_mode: str
    credential_ref: str | None
    real_call_verified: bool
    fallback_route: str | None
    intended_task_class: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "executor": self.executor,
            "model": self.model,
            "configured": self.configured,
            "runtime_available": self.runtime_available,
            "routing_enabled": self.routing_enabled,
            "auth_mode": self.auth_mode,
            "credential_ref": self.credential_ref,
            "real_call_verified": self.real_call_verified,
            "fallback_route": self.fallback_route,
            "intended_task_class": self.intended_task_class,
        }


class RouteResolutionError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


SYMBOLIC_ALIASES = {
    "free_multimodal": {
        "executor": "gemini_adapter",
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "auth_mode": "env",
        "credential_ref": "GEMINI_API_KEY",
        "selected_layer": "free_multimodal_adapter",
        "fallback_executor": "openclaw_gateway",
    },
    "paid_fast_reasoning": {
        "executor": "hermes",
        "provider": "deepseek",
        "model": "deepseek/deepseek-v4-flash",
        "auth_mode": "gateway_env",
        "credential_ref": "DEEPSEEK_API_KEY",
        "selected_layer": "hermes_supervisor",
        "fallback_executor": "codex_cli",
    },
    "paid_strong_reasoning": {
        "executor": "hermes",
        "provider": "deepseek",
        "model": "deepseek/deepseek-v4-pro",
        "auth_mode": "gateway_env",
        "credential_ref": "DEEPSEEK_API_KEY",
        "selected_layer": "hermes_supervisor",
        "fallback_executor": "codex_cli",
    },
    "engineering_executor": {
        "executor": "codex_cli",
        "provider": None,
        "model": "codex-native",
        "auth_mode": "codex_oauth",
        "credential_ref": None,
        "selected_layer": "codex_execution",
        "fallback_executor": "claude_cli",
    },
    "engineering_fallback": {
        "executor": "claude_cli",
        "provider": None,
        "model": "claude-code",
        "auth_mode": "claude_cli_auth",
        "credential_ref": None,
        "selected_layer": "claude_code_fallback",
        "fallback_executor": None,
    },
    "free-router-model": {
        "executor": "openclaw_gateway",
        "provider": "deepseek",
        "model": "deepseek/deepseek-v4-flash",
        "auth_mode": "gateway_env",
        "credential_ref": "DEEPSEEK_API_KEY",
        "selected_layer": "openclaw_direct",
        "fallback_executor": "hermes",
    },
    "vision-router-model": {
        "executor": "openclaw_gateway",
        "provider": "zhipu",
        "model": "glm-4.7-flash",
        "auth_mode": "gateway_env",
        "credential_ref": "ZHIPU_API_KEY",
        "selected_layer": "vision_router",
        "fallback_executor": "legion_worker_local_ocr",
        "capabilities": ["image_understanding", "ocr"],
        "sensitive_image_policy": "confirm_or_local_redact_before_cloud",
        "quota_failure_status": "VISION_PROVIDER_QUOTA_EXHAUSTED",
    },
    "strong-reasoning-model": {
        "executor": "hermes",
        "provider": "deepseek",
        "model": "deepseek/deepseek-v4-flash",
        "auth_mode": "gateway_env",
        "credential_ref": "DEEPSEEK_API_KEY",
        "selected_layer": "hermes_supervisor",
        "fallback_executor": "codex_cli",
    },
    "engineering-model": {
        "executor": "codex_cli",
        "provider": None,
        "model": "codex-native",
        "auth_mode": "codex_oauth",
        "credential_ref": None,
        "selected_layer": "codex_execution",
        "fallback_executor": "claude_cli",
    },
    "claude-fallback-model": {
        "executor": "claude_cli",
        "provider": None,
        "model": "claude-code",
        "auth_mode": "claude_cli_auth",
        "credential_ref": None,
        "selected_layer": "claude_code_fallback",
        "fallback_executor": None,
    },
    "agent-team-model": {
        "executor": "agent_team",
        "provider": "deepseek",
        "model": "deepseek/deepseek-v4-flash",
        "auth_mode": "gateway_env",
        "credential_ref": "DEEPSEEK_API_KEY",
        "selected_layer": "planner_workers_validator",
        "fallback_executor": "hermes",
    },
}


UNCONFIGURED_GATEWAY_PROVIDERS = (
    "openai",
    "anthropic",
    "byteplus",
    "byteplus-plan",
    "volcengine",
    "mistral",
    "cohere",
    "novita",
    "nvidia",
    "together",
    "ollama-cloud",
    "xiaomi",
)


LEGACY_SYMBOLIC_TO_ALIAS = {
    "free-router-model": "free-router-model",
    "strong-reasoning-model": "strong-reasoning-model",
    "codex_oauth_native": "engineering-model",
    "free-workers-with-validator": "agent-team-model",
}


class PAIOSCore:
    def __init__(self, root: Path):
        self.root = root
        self.db_path = root / "database" / "paios_v1.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.conn.close()

    def migrate(self) -> None:
        self.conn.executescript(SCHEMA)
        self._apply_schema_upgrades()
        self.conn.commit()

    def _apply_schema_upgrades(self) -> None:
        task_columns = {
            "selected_provider": "TEXT",
            "symbolic_model": "TEXT",
            "auth_mode": "TEXT",
            "credential_ref": "TEXT",
            "routing_enabled": "INTEGER",
            "runtime_available": "INTEGER",
            "legacy_symbolic_alias": "INTEGER NOT NULL DEFAULT 0",
        }
        routing_columns = {
            "selected_provider": "TEXT",
            "symbolic_model": "TEXT",
            "auth_mode": "TEXT",
            "credential_ref": "TEXT",
            "routing_enabled": "INTEGER",
            "runtime_available": "INTEGER",
            "error_code": "TEXT",
        }
        self._ensure_columns("paios_tasks", task_columns)
        self._ensure_columns("paios_routing_decisions", routing_columns)

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, definition in columns.items():
            if name not in existing:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def status(self) -> dict[str, Any]:
        self.migrate()
        tables = {
            row["name"]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if str(row["name"]).startswith("paios_")
        }
        counts = {
            table: int(self.conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"])
            for table in sorted(tables)
        }
        return {
            "status": "PASS",
            "database": str(self.db_path),
            "tables": sorted(tables),
            "counts": counts,
        }

    def create_task(
        self,
        *,
        source_channel: str,
        user_id: str,
        message: str,
        task_type: str = "general",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        self.migrate()
        decision = self.route(message, task_type=task_type)
        task_id = f"task-{uuid.uuid4().hex[:16]}"
        corr = correlation_id or f"corr-{uuid.uuid4().hex[:12]}"
        now = utc_now()
        self.conn.execute(
            """
            INSERT INTO paios_tasks(
              task_id, correlation_id, source_channel, user_id, task_type, risk,
              selected_model, executor, selected_provider, symbolic_model, auth_mode,
              credential_ref, routing_enabled, runtime_available, status, phase, completed_steps_json,
              pending_steps_json, approval_state, artifacts_json, error_json,
              retry_count, created_at, updated_at, heartbeat_at, checkpoint_json,
              final_result_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id,
                corr,
                source_channel,
                user_id,
                task_type,
                decision.risk,
                decision.selected_model,
                decision.executor,
                decision.selected_provider,
                decision.symbolic_model,
                decision.auth_mode,
                decision.credential_ref,
                int(decision.routing_enabled),
                int(decision.runtime_available),
                "WAITING_APPROVAL" if decision.requires_approval else "CREATED",
                "intake",
                "[]",
                json.dumps(["route", "execute", "validate", "reply"], ensure_ascii=False),
                "required" if decision.requires_approval else "not_required",
                "[]",
                "{}",
                0,
                now,
                now,
                now,
                json.dumps({"message_hash": _hash_text(message)}, ensure_ascii=False),
                "{}",
            ),
        )
        self.record_routing_decision(task_id, message, decision)
        self.emit_event("task.created", task_id, corr, {"task_type": task_type, "executor": decision.executor})
        self.audit(task_id=task_id, actor=user_id, channel=source_channel, action="task.created", result="created")
        self.conn.commit()
        return {"task_id": task_id, "correlation_id": corr, "routing": decision.to_dict()}

    def route(self, message: str, *, task_type: str = "general", codex_available: bool = True) -> RoutingDecision:
        text = message.lower()
        reasons: list[str] = []
        high_risk_terms = ("delete", "remove", "admin", "群", "转发", "发微信", "付款", "支付", "secret", "password")
        engineering_terms = ("code", "repo", "github", "test", "bug", "deploy", "脚本", "代码", "修复", "工程")
        batch_terms = ("批量", "repeat", "many", "大量", "清单", "列表")
        hard_terms = ("plan", "architecture", "reason", "complex", "架构", "规划", "复杂", "推理")

        risk = "high" if any(term in text for term in high_risk_terms) else "low"
        if risk == "high":
            reasons.append("high_risk_action_detected")
        reasoning = "high" if any(term in text for term in hard_terms) or len(message) > 400 else "low"
        workload = "high" if any(term in text for term in batch_terms) or len(message.splitlines()) > 20 else "low"

        if any(term in text for term in engineering_terms) or task_type == "engineering":
            alias = "engineering-model" if codex_available else "claude-fallback-model"
            reasons.append("engineering_task")
        elif workload == "high" and reasoning == "low":
            alias = "agent-team-model"
            reasons.append("high_repetition_low_reasoning")
        elif reasoning == "high":
            alias = "paid_strong_reasoning"
            reasons.append("high_reasoning")
        else:
            alias = "free_multimodal" if gemini_live_verified() else "free-router-model"
            reasons.append("simple_low_risk")

        return self.resolve_alias(
            alias,
            risk=risk,
            reasoning_class=reasoning,
            workload_class=workload,
            requires_approval=risk == "high",
            reasons=reasons,
        )

    def route(self, message: str, *, task_type: str = "general", codex_available: bool = True) -> RoutingDecision:
        text = message.lower()
        reasons: list[str] = []
        high_risk_terms = (
            "delete",
            "remove",
            "admin",
            "send message",
            "group message",
            "wechat group",
            "forward",
            "payment",
            "secret",
            "password",
            "群",
            "群聊",
            "转发",
            "发微信",
            "付款",
            "支付",
        )
        engineering_terms = ("code", "repo", "github", "test", "bug", "deploy", "script", "代码", "修复", "工程")
        batch_terms = ("批量", "repeat", "many", "大量", "清单", "列表")
        hard_terms = ("plan", "architecture", "reason", "complex", "analysis", "analyze", "risk", "架构", "规划", "复杂", "推理", "分析", "风险")
        engineering_negations = ("no engineering", "do not call engineering", "不调用工程", "不要调用工程", "不使用工程")

        risk = "high" if any(term in text for term in high_risk_terms) else "low"
        if risk == "high":
            reasons.append("high_risk_action_detected")
        reasoning = "high" if any(term in text for term in hard_terms) or len(message) > 400 else "low"
        workload = "high" if any(term in text for term in batch_terms) or len(message.splitlines()) > 20 else "low"
        wants_engineering = (any(term in text for term in engineering_terms) or task_type == "engineering") and not any(term in text for term in engineering_negations)

        if wants_engineering:
            alias = "engineering_executor" if codex_available else "engineering_fallback"
            reasons.append("engineering_task")
        elif workload == "high" and reasoning == "low":
            alias = "agent-team-model"
            reasons.append("high_repetition_low_reasoning")
        elif reasoning == "high":
            alias = "paid_strong_reasoning"
            reasons.append("high_reasoning")
        else:
            alias = "free_multimodal" if gemini_live_verified() else "free-router-model"
            reasons.append("simple_low_risk")

        return self.resolve_alias(
            alias,
            risk=risk,
            reasoning_class=reasoning,
            workload_class=workload,
            requires_approval=risk == "high",
            reasons=reasons,
        )

    def resolve_alias(
        self,
        alias: str,
        *,
        risk: str = "low",
        reasoning_class: str = "low",
        workload_class: str = "low",
        requires_approval: bool = False,
        reasons: list[str] | None = None,
    ) -> RoutingDecision:
        if alias not in SYMBOLIC_ALIASES:
            raise RouteResolutionError("UNRESOLVED_SYMBOLIC_MODEL_ALIAS", alias)
        route = SYMBOLIC_ALIASES[alias]
        provider = route["provider"]
        executor = str(route["executor"])
        model = route["model"]
        auth_mode = str(route["auth_mode"])
        credential_ref = route["credential_ref"]
        self._assert_auth_class_separation(executor, provider)
        capability = self._capability_for_route(executor, provider)
        if executor == "openclaw_gateway":
            if not provider or not model or not auth_mode or not credential_ref:
                raise RouteResolutionError("GATEWAY_ROUTE_AUTH_UNAVAILABLE", alias)
            if not capability.configured or not capability.runtime_available or not capability.routing_enabled:
                raise RouteResolutionError("GATEWAY_ROUTE_AUTH_UNAVAILABLE", str(provider))
        if model in SYMBOLIC_ALIASES:
            raise RouteResolutionError("UNRESOLVED_SYMBOLIC_MODEL_ALIAS", str(model))
        return RoutingDecision(
            risk=risk,
            reasoning_class=reasoning_class,
            workload_class=workload_class,
            selected_layer=str(route["selected_layer"]),
            selected_model=str(model),
            executor=executor,
            symbolic_model=alias,
            selected_provider=str(provider) if provider else None,
            auth_mode=auth_mode,
            credential_ref=str(credential_ref) if credential_ref else None,
            configured=capability.configured,
            runtime_available=capability.runtime_available,
            routing_enabled=capability.routing_enabled,
            requires_approval=requires_approval,
            fallback_executor=str(route["fallback_executor"]) if route["fallback_executor"] else None,
            reasons=reasons or [],
        )

    def provider_capability_registry(self) -> dict[str, ProviderCapability]:
        codex_available = shutil.which("codex") is not None
        claude_available = shutil.which("claude") is not None
        gemini_configured = gemini_credential_available()
        gemini_available = gemini_live_verified()
        registry: dict[str, ProviderCapability] = {
            "gemini": ProviderCapability(
                provider="gemini",
                executor="gemini_adapter",
                model=os.environ.get("PAIOS_GEMINI_MODEL") or "gemini-3-flash-preview",
                configured=gemini_configured,
                runtime_available=gemini_available,
                routing_enabled=gemini_available,
                auth_mode="env_or_dpapi_child_env",
                credential_ref="GEMINI_API_KEY",
                real_call_verified=False,
                fallback_route="deepseek",
                intended_task_class="free_low_risk_text_and_multimodal",
            ),
            "deepseek": ProviderCapability(
                provider="deepseek",
                executor="openclaw_gateway",
                model="deepseek/deepseek-v4-flash",
                configured=True,
                runtime_available=True,
                routing_enabled=True,
                auth_mode="env_discovery",
                credential_ref="DEEPSEEK_API_KEY",
                real_call_verified=True,
                fallback_route="hermes",
                intended_task_class="simple_low_risk_and_supervised_reasoning",
            ),
            "zhipu": ProviderCapability(
                provider="zhipu",
                executor="openclaw_gateway",
                model="glm-4.7-flash",
                configured=True,
                runtime_available=True,
                routing_enabled=True,
                auth_mode="gateway_env",
                credential_ref="ZHIPU_API_KEY",
                real_call_verified=False,
                fallback_route="legion_worker_local_ocr",
                intended_task_class="image_understanding_and_ocr_limited",
            ),
            "codex_cli": ProviderCapability(
                provider="codex_cli",
                executor="codex_cli",
                model="codex-native",
                configured=codex_available,
                runtime_available=codex_available,
                routing_enabled=codex_available,
                auth_mode="codex_oauth",
                credential_ref=None,
                real_call_verified=codex_available,
                fallback_route="claude_cli",
                intended_task_class="engineering",
            ),
            "claude_cli": ProviderCapability(
                provider="claude_cli",
                executor="claude_cli",
                model="claude-code",
                configured=claude_available,
                runtime_available=claude_available,
                routing_enabled=claude_available,
                auth_mode="claude_cli_auth",
                credential_ref=None,
                real_call_verified=claude_available,
                fallback_route=None,
                intended_task_class="engineering_fallback",
            ),
        }
        for provider in UNCONFIGURED_GATEWAY_PROVIDERS:
            registry[provider] = ProviderCapability(
                provider=provider,
                executor="openclaw_gateway",
                model=None,
                configured=False,
                runtime_available=False,
                routing_enabled=False,
                auth_mode="gateway_api_key",
                credential_ref="OPENAI_API_KEY" if provider == "openai" else ("ANTHROPIC_API_KEY" if provider == "anthropic" else None),
                real_call_verified=False,
                fallback_route="deepseek",
                intended_task_class="disabled_unconfigured_gateway_provider",
            )
        return registry

    def _capability_for_route(self, executor: str, provider: str | None) -> ProviderCapability:
        registry = self.provider_capability_registry()
        if executor in ("codex_cli", "claude_cli"):
            return registry[executor]
        if executor == "gemini_adapter":
            return registry["gemini"]
        if provider and provider in registry:
            return registry[provider]
        if executor == "agent_team":
            return registry["deepseek"]
        raise RouteResolutionError("PROVIDER_AUTH_UNAVAILABLE", provider or executor)

    def validate_gateway_provider(self, provider: str, model: str | None) -> ProviderCapability:
        capability = self.provider_capability_registry().get(provider)
        if not capability or not capability.configured or not capability.runtime_available or not capability.routing_enabled or not model:
            raise RouteResolutionError("PROVIDER_AUTH_UNAVAILABLE", provider)
        return capability

    @staticmethod
    def _assert_auth_class_separation(executor: str, provider: str | None) -> None:
        if executor == "codex_cli" and provider == "openai":
            raise RouteResolutionError("AUTH_CLASS_MISMATCH", "codex_oauth_is_not_openai_gateway_api_key")
        if executor == "claude_cli" and provider == "anthropic":
            raise RouteResolutionError("AUTH_CLASS_MISMATCH", "claude_cli_auth_is_not_anthropic_gateway_api_key")

    def record_routing_decision(self, task_id: str, message: str, decision: RoutingDecision) -> str:
        decision_id = f"route-{uuid.uuid4().hex[:16]}"
        self.conn.execute(
            """
            INSERT INTO paios_routing_decisions(
              decision_id, task_id, message_hash, risk, reasoning_class, workload_class,
              selected_layer, selected_model, executor, selected_provider, symbolic_model,
              auth_mode, credential_ref, routing_enabled, runtime_available, requires_approval,
              fallback_executor, decision_json, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                decision_id,
                task_id,
                _hash_text(message),
                decision.risk,
                decision.reasoning_class,
                decision.workload_class,
                decision.selected_layer,
                decision.selected_model,
                decision.executor,
                decision.selected_provider,
                decision.symbolic_model,
                decision.auth_mode,
                decision.credential_ref,
                int(decision.routing_enabled),
                int(decision.runtime_available),
                int(decision.requires_approval),
                decision.fallback_executor,
                json.dumps(decision.to_dict(), ensure_ascii=False),
                utc_now(),
            ),
        )
        return decision_id

    def repair_legacy_symbolic_routes(self, *, execute: bool = False) -> dict[str, Any]:
        self.migrate()
        target_statuses = ("CREATED", "WAITING_APPROVAL", "QUEUED", "PENDING", "RETRY_PENDING")
        placeholders = ",".join("?" for _ in LEGACY_SYMBOLIC_TO_ALIAS)
        status_placeholders = ",".join("?" for _ in target_statuses)
        rows = self.conn.execute(
            f"""
            SELECT task_id, selected_model, executor, risk, status
            FROM paios_tasks
            WHERE selected_model IN ({placeholders})
              AND status IN ({status_placeholders})
            ORDER BY created_at
            """,
            (*LEGACY_SYMBOLIC_TO_ALIAS.keys(), *target_statuses),
        ).fetchall()
        planned: list[dict[str, Any]] = []
        for row in rows:
            alias = LEGACY_SYMBOLIC_TO_ALIAS[str(row["selected_model"])]
            decision = self.resolve_alias(alias, risk=str(row["risk"] or "low"), reasons=["legacy_symbolic_route_repaired"])
            planned.append(
                {
                    "task_id": row["task_id"],
                    "old_model": row["selected_model"],
                    "old_executor": row["executor"],
                    "old_status": row["status"],
                    "new_model": decision.selected_model,
                    "new_executor": decision.executor,
                    "selected_provider": decision.selected_provider,
                    "new_status": "ROUTE_REPAIRED_AWAITING_REVIEW",
                }
            )
        if not execute:
            return {"status": "DRY_RUN", "planned_count": len(planned), "planned": planned}

        now = utc_now()
        with self.conn:
            for item in planned:
                alias = LEGACY_SYMBOLIC_TO_ALIAS[str(item["old_model"])]
                decision = self.resolve_alias(alias, risk="low", reasons=["legacy_symbolic_route_repaired"])
                self.conn.execute(
                    """
                    UPDATE paios_tasks
                    SET selected_model=?, executor=?, selected_provider=?, symbolic_model=?,
                        auth_mode=?, credential_ref=?, routing_enabled=?, runtime_available=?,
                        legacy_symbolic_alias=1, status=?, phase=?, updated_at=?,
                        error_json=json_set(COALESCE(NULLIF(error_json,''),'{}'), '$.route_repair', json(?))
                    WHERE task_id=? AND selected_model=? AND status IN ('CREATED','WAITING_APPROVAL','QUEUED','PENDING','RETRY_PENDING')
                    """,
                    (
                        decision.selected_model,
                        decision.executor,
                        decision.selected_provider,
                        decision.symbolic_model,
                        decision.auth_mode,
                        decision.credential_ref,
                        int(decision.routing_enabled),
                        int(decision.runtime_available),
                        "ROUTE_REPAIRED_AWAITING_REVIEW",
                        "route_repaired_no_auto_retry",
                        now,
                        json.dumps({"at": now, "old_model": item["old_model"], "old_executor": item["old_executor"]}, ensure_ascii=False),
                        item["task_id"],
                        item["old_model"],
                    ),
                )
                self.conn.execute(
                    """
                    UPDATE paios_routing_decisions
                    SET selected_model=?, executor=?, selected_provider=?, symbolic_model=?,
                        auth_mode=?, credential_ref=?, routing_enabled=?, runtime_available=?,
                        decision_json=?, error_code=NULL
                    WHERE task_id=? AND selected_model=?
                    """,
                    (
                        decision.selected_model,
                        decision.executor,
                        decision.selected_provider,
                        decision.symbolic_model,
                        decision.auth_mode,
                        decision.credential_ref,
                        int(decision.routing_enabled),
                        int(decision.runtime_available),
                        json.dumps(decision.to_dict(), ensure_ascii=False),
                        item["task_id"],
                        item["old_model"],
                    ),
                )
        return {"status": "APPLIED", "updated_count": len(planned), "updated": planned}

    def emit_event(
        self,
        event_type: str,
        task_id: str | None,
        correlation_id: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> str:
        self.migrate()
        key = idempotency_key or _hash_json({"type": event_type, "task_id": task_id, "correlation_id": correlation_id, "payload": payload})
        row = self.conn.execute("SELECT event_id FROM paios_events WHERE idempotency_key=?", (key,)).fetchone()
        if row:
            return str(row["event_id"])
        event_id = f"evt-{uuid.uuid4().hex[:16]}"
        self.conn.execute(
            "INSERT INTO paios_events(event_id,event_type,task_id,correlation_id,idempotency_key,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (event_id, event_type, task_id, correlation_id, key, json.dumps(payload, ensure_ascii=False), utc_now()),
        )
        self.conn.commit()
        return event_id

    def put_memory(
        self,
        *,
        scope: str,
        channel: str,
        project: str,
        key: str,
        value: dict[str, Any],
        source: str,
        permissions: dict[str, Any] | None = None,
        expires_at: str | None = None,
    ) -> str:
        self.migrate()
        current = self.conn.execute(
            """
            SELECT max(version) AS version FROM paios_memories
            WHERE scope=? AND channel=? AND project=? AND memory_key=? AND deleted_at IS NULL
            """,
            (scope, channel, project, key),
        ).fetchone()
        version = int(current["version"] or 0) + 1
        memory_id = f"mem-{uuid.uuid4().hex[:16]}"
        now = utc_now()
        self.conn.execute(
            """
            INSERT INTO paios_memories(
              memory_id, scope, channel, project, memory_key, value_json, source,
              version, permissions_json, expires_at, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                memory_id,
                scope,
                channel,
                project,
                key,
                json.dumps(value, ensure_ascii=False),
                source,
                version,
                json.dumps(permissions or {"recall": [scope]}, ensure_ascii=False),
                expires_at,
                now,
                now,
            ),
        )
        self.conn.commit()
        return memory_id

    def recall_memory(self, *, scope: str, channel: str, project: str, key: str | None = None) -> list[dict[str, Any]]:
        self.migrate()
        params: list[Any] = []
        where = ["deleted_at IS NULL"]
        if key:
            where.append("memory_key=?")
            params.append(key)
        allowed = [
            ("shared", "shared", "shared"),
            (scope, channel, project),
            (scope, channel, "shared"),
            (scope, "shared", project),
        ]
        scope_filters = []
        for item in allowed:
            scope_filters.append("(scope=? AND channel=? AND project=?)")
            params.extend(item)
        where.append("(" + " OR ".join(scope_filters) + ")")
        rows = self.conn.execute(
            f"""
            SELECT * FROM paios_memories
            WHERE {' AND '.join(where)}
            ORDER BY updated_at DESC
            """,
            params,
        ).fetchall()
        return [
            {
                "memory_id": row["memory_id"],
                "scope": row["scope"],
                "channel": row["channel"],
                "project": row["project"],
                "key": row["memory_key"],
                "value": json.loads(row["value_json"]),
                "source": row["source"],
                "version": row["version"],
            }
            for row in rows
        ]

    def policy_check(self, *, action: str, target: str, task_id: str | None = None) -> dict[str, Any]:
        risky = ("send_message", "group_post", "forward", "bulk_delete", "admin", "device_scope", "payment")
        result = "REQUIRES_CONFIRMATION" if action in risky else "ALLOW"
        reason = "explicit_confirmation_required" if result != "ALLOW" else "low_risk_action"
        decision_id = f"policy-{uuid.uuid4().hex[:16]}"
        self.conn.execute(
            "INSERT INTO paios_policy_decisions(decision_id,task_id,action,target,result,reason,created_at) VALUES(?,?,?,?,?,?,?)",
            (decision_id, task_id, action, target, result, reason, utc_now()),
        )
        self.conn.commit()
        return {"decision_id": decision_id, "result": result, "reason": reason}

    def audit(
        self,
        *,
        task_id: str | None,
        actor: str,
        channel: str,
        action: str,
        result: str,
        tool: str | None = None,
        model: str | None = None,
        files: list[str] | None = None,
        command_summary: str | None = None,
        approved: bool = False,
    ) -> str:
        if command_summary and _looks_secret_bearing(command_summary):
            command_summary = "[REDACTED]"
        audit_id = f"audit-{uuid.uuid4().hex[:16]}"
        self.conn.execute(
            """
            INSERT INTO paios_audit_records(
              audit_id, task_id, actor, channel, action, tool, model, files_json,
              command_summary, approved, result, redacted, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                audit_id,
                task_id,
                actor,
                channel,
                action,
                tool,
                model,
                json.dumps(files or [], ensure_ascii=False),
                command_summary,
                int(approved),
                result,
                int(command_summary == "[REDACTED]"),
                utc_now(),
            ),
        )
        self.conn.commit()
        return audit_id

    def plan_agent_team(self, task_id: str, items: list[str], *, max_workers: int = 5) -> dict[str, Any]:
        self.migrate()
        worker_count = max(1, min(max_workers, 5, len(items)))
        batches = [items[i::worker_count] for i in range(worker_count)]
        leases = []
        now = utc_now()
        for idx, batch in enumerate(batches):
            lease_id = f"lease-{uuid.uuid4().hex[:16]}"
            self.conn.execute(
                """
                INSERT INTO paios_agent_leases(
                  lease_id, task_id, worker_id, role, batch_json, status,
                  lease_until, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    lease_id,
                    task_id,
                    f"worker-{idx + 1}",
                    "worker",
                    json.dumps(batch, ensure_ascii=False),
                    "leased",
                    now,
                    now,
                    now,
                ),
            )
            leases.append({"lease_id": lease_id, "worker_id": f"worker-{idx + 1}", "items": batch})
        self.conn.commit()
        return {"planner": "hermes", "validator": "deterministic", "reviewer": "hermes_reviewer", "leases": leases}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def gemini_credential_available() -> bool:
    if os.environ.get("GEMINI_API_KEY"):
        return True
    try:
        resolved = GEMINI_DPAPI_STORE_PATH.resolve()
        if str(resolved).upper().startswith("E:\\") or not resolved.is_file():
            return False
        store = json.loads(resolved.read_text(encoding="utf-8-sig"))
        values = store.get("values") if isinstance(store, dict) else None
        ciphertext = values.get("gemini/api/key") if isinstance(values, dict) else None
        return bool(ciphertext and store.get("schema") == "paios.gemini.dpapi_store.v1")
    except Exception:
        return False


def gemini_live_verified() -> bool:
    try:
        resolved = GEMINI_PROVIDER_STATUS_PATH.resolve()
        if str(resolved).upper().startswith("E:\\") or not resolved.is_file():
            return False
        status = json.loads(resolved.read_text(encoding="utf-8-sig"))
        return bool(status.get("status") == "PASS" and status.get("text_test") == "PASS" and status.get("multimodal_test") == "PASS")
    except Exception:
        return False


def _hash_json(value: Any) -> str:
    return _hash_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _looks_secret_bearing(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in SECRET_MARKERS)
