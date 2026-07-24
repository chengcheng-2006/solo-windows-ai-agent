# Public Module Ownership Table

**Generated:** 2026-07-24 03:54+08:00 (UTC+8)
**Auditor:** 吏部 (subagent, v0.1.1)
**Branch:** `release/v0.1.1-star-ready`
**Scope:** All 114 git-tracked files in the public repository

---

## Legend

| Column | Meaning |
|---|---|
| **Module** | Logical module / directory |
| **Visibility** | Public = in open-source release; Lite = subset/simplified; Private = deployment-specific code removed |
| **Owner** | Person/team or "Unclaimed" |
| **Maintenance** | Active | Beta | Stable | Stale | Orphan |
| **Test Coverage** | ✅ = has tests | ⚠️ = partial tests | ❌ = no tests | N/A = not code |

---

## 1. Root-Level Configuration & Governance

| Path | Type | Size | Visibility | Owner | Maintenance | Tests | Notes |
|---|---|---|---|---|---|---|---|
| `.env.example` | Config template | 1,977 B | Public | System Admin | Stable | N/A | Template for API keys; 10 env vars documented |
| `.gitignore` | Config | 811 B | Public | All devs | Stable | N/A | 50+ ignore patterns |
| `.gitattributes` | Config | 279 B | Public | All devs | Stable | N/A | Line ending normalization |
| `.gitleaks.toml` | Security config | 1,465 B | Public | Security | Stable | N/A | 36 deny rules for secrets scanning |
| `gitleaks-report.json` | Report | 3 B | Public | Security | Stale | N/A | Empty placeholder — **potentially orphan** |
| `LICENSE` | Legal | 11,344 B | Public | Legal | Stable | N/A | Apache 2.0 |
| `THIRD_PARTY_NOTICES.md` | Legal | 2,605 B | Public | Legal | Stable | N/A | MIT/Hermes attribution |
| `CHANGELOG.md` | Meta-doc | 1,066 B | Public | Release Manager | Active | N/A | Initial release section only |
| `ROADMAP.md` | Meta-doc | 1,982 B | Public | Product | Active | N/A | 15+ planned features |
| `README.md` | Entry doc | 6,156 B | Public | Documentation | Active | N/A | English; references all public modules |
| `README.zh-CN.md` | Entry doc | 3,484 B | Public | Documentation | Active | N/A | Chinese translation |
| `SECURITY.md` | Policy | 2,034 B | Public | Security | Stable | N/A | Disclosure policy |
| `CODE_OF_CONDUCT.md` | Policy | 1,752 B | Public | Community | Stable | N/A | Standard CoC |
| `CONTRIBUTING.md` | Guide | 2,012 B | Public | Community | Stable | N/A | Contribution workflow |

---

## 2. Community & CI (`/.github/`)

| Path | Type | Size | Visibility | Owner | Maintenance | Tests | Notes |
|---|---|---|---|---|---|---|---|
| `.github/dependabot.yml` | CI config | 466 B | Public | DevOps | Stable | N/A | Weekly security updates |
| `.github/workflows/ci.yml` | CI pipeline | 2,558 B | Public | DevOps | Active | N/A | Python 3.11 CI; lint + test |
| `.github/PULL_REQUEST_TEMPLATE.md` | Template | 928 B | Public | Community | Stable | N/A | Standard PR template |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Template | 2,552 B | Public | Community | Stable | N/A | Structured bug report |
| `.github/ISSUE_TEMPLATE/config.yml` | Template | 401 B | Public | Community | Stable | N/A | Issue config |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Template | 1,535 B | Public | Community | Stable | N/A | Feature request form |

---

## 3. Configuration Examples (`config/examples/`)

| Path | Type | Size | Visibility | Owner | Maintenance | Tests | Notes |
|---|---|---|---|---|---|---|---|
| `config/examples/agent_roles.yaml` | Config example | 506 B | Public | Agents | Active | N/A | Agent role definitions (sample) |
| `config/examples/solo_model_routing.yaml` | Config example | 684 B | Public | Models | Active | N/A | 4-level routing example |

**⚠️ Conflict:** `CONFIGURATION.md` references `config/agent_team/` (8 files) and `config/model-routing.json` and `config/runtime_ports.yaml` — none exist. Only `config/examples/` is present.

---

## 4. Orchestrator (`src/orchestrator/openclaw_night_workflow/`)

**Overall status:** Active | 29 source files | ~145 KB | **Public**

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 81 B | Framework | Stable | N/A | Package init |
| `app.py` | 3,493 B | Orchestrator | Active | ✅ | FastAPI app entry point |
| `approvals.py` | 1,759 B | Orchestrator | Stable | ⚠️ | Approval gate logic |
| `cli.py` | 3,086 B | Orchestrator | Active | ❌ | CLI entry point |
| `codex_adapter.py` | 2,969 B | Codex | Beta | ❌ | Codex agent adapter |
| `config.py` | 1,340 B | Orchestrator | Stable | ❌ | Module config |
| `dispatcher.py` | 1,114 B | Dispatcher | Active | ❌ | Task routing/dispatch |
| `edict_adapter.py` | 4,070 B | Orchestrator | Beta | ❌ | Edict command processing |
| `evidence.py` | 778 B | Audit | Stable | ❌ | Evidence/audit trail |
| `gemini_adapter.py` | 6,384 B | Models | Beta | ❌ | Gemini model adapter |
| `locks.py` | 1,020 B | Orchestrator | Stable | ❌ | Concurrency locks |
| `manifest.py` | 1,654 B | Orchestrator | Active | ❌ | File manifest generation |
| `notifications.py` | 540 B | Orchestrator | Beta | ❌ | Notification handlers |
| `paios_acceptance.py` | 10,576 B | PAIOS | Beta | ❌ | PAIOS acceptance testing |
| `paios_bridges.py` | 12,714 B | PAIOS | Beta | ❌ | Bridge utilities between PAIOS and orchestrator |
| `paios_cli.py` | 16,538 B | PAIOS | Beta | ❌ | CLI for PAIOS interaction |
| `paios_core.py` | 42,014 B | PAIOS | Active | ❌ | **Largest file** — PAIOS core orchestration logic |
| `process_watcher.py` | 1,056 B | Orchestrator | Active | ❌ | Process monitoring |
| `redaction.py` | 781 B | Privacy | Stable | ❌ | Data redaction |
| `retry_controller.py` | 772 B | Orchestrator | Stable | ⚠️ | Retry logic |
| `rollback.py` | 1,320 B | Orchestrator | Beta | ❌ | Rollback support |
| `schemas.py` | 2,220 B | Orchestrator | Stable | ❌ | Pydantic/JSON schemas |
| `security.py` | 851 B | Security | Stable | ❌ | Security utilities |
| `state_machine.py` | 1,294 B | Orchestrator | Stable | ⚠️ | Task lifecycle state machine |
| `task_store.py` | 7,183 B | Storage | Active | ⚠️ | SQLite task persistence |
| `validator_cli.py` | 856 B | Validator | Beta | ❌ | Validator CLI |
| `validator_runner.py` | 7,340 B | Validator | Active | ❌ | Validation runner |
| `workflow_control.py` | 7,274 B | Workflow | Active | ❌ | Workflow orchestration control |
| `workflow_control_cli.py` | 2,097 B | Workflow | Beta | ❌ | Workflow control CLI |

---

## 5. PAIOS Core (`src/paios/paios/`)

**Overall status:** Active | 16 source files | ~94 KB | **Public** (simplified lite version)

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 71 B | Framework | Stable | N/A | Package init |
| `config.py` | 3,580 B | PAIOS | Active | ❌ | Configuration management |
| `control_plane.py` | 23,900 B | PAIOS | Active | ❌ | FastAPI control plane server |
| `database.py` | 11,263 B | PAIOS | Active | ⚠️ | SQLite persistence |
| `enums.py` | 1,184 B | PAIOS | Stable | ❌ | Enumerations |
| `input_vault.py` | 5,519 B | PAIOS | Active | ❌ | Secure input handling |
| `main.py` | 8,105 B | PAIOS | Active | ❌ | Entry point |
| `migrations.py` | 2,621 B | PAIOS | Active | ❌ | DB migration support |
| `policy.py` | 939 B | PAIOS | Stable | ❌ | Policy engine (system-level) |
| `privacy_broker.py` | 11,033 B | Privacy | Active | ❌ | Privacy filtering/redaction |
| `risk.py` | 2,663 B | Security | Stable | ❌ | Risk assessment |
| `schemas.py` | 8,393 B | PAIOS | Stable | ❌ | Core Pydantic schemas |
| `security.py` | 3,467 B | Security | Stable | ❌ | Security utilities |
| `state_machine.py` | 1,834 B | PAIOS | Stable | ❌ | Workflow state machine |
| `src/paios/__init__.py` (parent) | 13 B | Framework | Stable | N/A | Redundant? Parent package init |

---

## 6. Agent Team (`src/paios/paios/agent_team/`)

**Overall status:** Active | 10 source files | ~69 KB | **Public** (simplified)

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `audit.py` | 1,427 B | Audit/Security | Active | ❌ | Agent audit logging |
| `capabilities.py` | 4,390 B | Agents | Active | ❌ | Agent capability definitions |
| `errors.py` | 513 B | Agents | Stable | ❌ | Agent error types |
| `heartbeat.py` | 3,282 B | Monitoring | Active | ❌ | Agent heartbeat/liveness |
| `middleware.py` | 5,250 B | Agents | Active | ❌ | Agent middleware (logging, auth) |
| `models.py` | 14,572 B | Agents | Active | ❌ | Agent data models |
| `policy.py` | 10,247 B | Security | Active | ❌ | Agent-level policy engine |
| `registry.py` | 2,520 B | Agents | Active | ❌ | Agent registry |
| `review.py` | 3,808 B | Review | Active | ❌ | Agent review/approval |
| `state_machine.py` | 12,021 B | Agents | Active | ❌ | Agent workflow state machine |
| `tokens.py` | 10,610 B | Security | Active | ❌ | Token/rate limiting |

---

## 7. Workers

### Browser Worker (`workers/browser_worker/`)

**Status:** Beta | 2 files | ~5.5 KB

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 63 B | Workers | Stable | N/A | Package init |
| `worker.py` | 5,406 B | Browser Worker | Beta | ❌ | CDP/Playwright browser automation |

### Computer Use Worker (`workers/computer_use/`)

**Status:** Experimental | 7 files | ~69 KB

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 417 B | Workers | Stable | N/A | Package init |
| `control.py` | 5,071 B | Computer Use | Experimental | ❌ | Input control abstraction |
| `controller.py` | 6,882 B | Computer Use | Experimental | ❌ | Vision-based GUI controller |
| `coordinates.py` | 2,005 B | Computer Use | Experimental | ❌ | Coordinate math for GUI targets |
| `gpu_resource_manager.py` | 12,755 B | Computer Use | Experimental | ❌ | GPU memory management |
| `models.py` | 23,291 B | Computer Use | Experimental | ❌ | **Largest worker file** — ML models for vision |
| `policy.py` | 15,010 B | Computer Use | Experimental | ❌ | Safety policy for GUI control |
| `server.py` | 3,703 B | Computer Use | Experimental | ❌ | Server entry point |

### Vision Worker (`workers/vision_worker/`)

**Status:** Beta | 2 files | ~5.3 KB

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 123 B | Workers | Stable | N/A | Package init |
| `worker.py` | 5,164 B | Vision Worker | Beta | ❌ | OCR/Vision (RapidOCR, GLM Vision) |

### Watchdog (`workers/watchdog/`)

**Status:** Stable | 2 files | ~9.2 KB

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 24 B | Workers | Stable | N/A | Package init |
| `watchdog.py` | 9,141 B | Watchdog | Stable | ❌ | Health monitoring, alerts |

### Windows Bridge (`workers/windows_bridge/`)

**Status:** Beta | 6 files | ~20 KB

| Path | Size | Owner | Status | Tests | Notes |
|---|---|---|---|---|---|
| `__init__.py` | 97 B | Workers | Stable | N/A | Package init |
| `client.py` | 1,305 B | Windows Bridge | Beta | ❌ | UIA named-pipe client |
| `dispatcher.py` | 5,581 B | Windows Bridge | Beta | ❌ | Task dispatcher for UIA |
| `registry.py` | 4,951 B | Windows Bridge | Beta | ❌ | Window registry / element tracking |
| `security.py` | 3,243 B | Windows Bridge | Beta | ❌ | Security layer for UIA |
| `server.py` | 998 B | Windows Bridge | Beta | ❌ | Named-pipe server |
| `uia.py` | 5,054 B | Windows Bridge | Beta | ❌ | Windows UIA automation core |

---

## 8. Tests

| Path | Size | Owner | Status | Notes |
|---|---|---|---|---|
| `tests/test_core.py` | 5,619 B | QA / All devs | Active | 14 test cases; 2 known Windows file lock failures |

**⚠️ Only 1 test file** for 78 Python source files. Test coverage is extremely low (<2%).

---

## 9. Scripts

| Path | Size | Owner | Status | Notes |
|---|---|---|---|---|
| `scripts/doctor.ps1` | 2,217 B | DevOps | Active | Health check |
| `scripts/setup.ps1` | 1,720 B | DevOps | Active | Initial setup |
| `scripts/start_demo.ps1` | 4,157 B | DevOps | Active | Safe demo launcher |
| `scripts/stop_demo.ps1` | 456 B | DevOps | Active | Demo cleanup |

---

## 10. Documentation

| Path | Size | Owner | Status | Notes |
|---|---|---|---|---|
| `docs/ARCHITECTURE.md` | 5,270 B | Documentation | Active | System topology + 3 diagrams |
| `docs/CONFIGURATION.md` | 2,155 B | Documentation | **Stale** | Mentions non-existent config files |
| `docs/DEVELOPMENT.md` | 2,774 B | Documentation | **Stale** | Mentions non-existent directories |
| `docs/FAQ.md` | 3,321 B | Documentation | Active | Common questions |
| `docs/GITHUB_PUBLISH_FINAL_REPORT.md` | 716 B | Release | Published | Post-publish report (JSON) |
| `docs/INSTALLATION.md` | 3,332 B | Documentation | **Stale** | References missing scripts |
| `docs/LAUNCH_CHECKLIST.md` | 3,593 B | Documentation | Active | Pre-launch checklist |
| `docs/LAUNCH_POSTS.md` | 6,839 B | Documentation | Active | Launch announcement drafts |
| `docs/PUBLIC_PACKAGE_COMPLETENESS_AUDIT.md` | 1,829 B | Audit | **Stale/Incorrect** | Claims zero source code — false |
| `docs/SECURITY_MODEL.md` | 3,017 B | Documentation | Active | Security architecture |
| `docs/TROUBLESHOOTING.md` | 2,652 B | Documentation | Active | Common issues |
| `docs/internal/` (dir) | 0 B | (This audit) | Created | **New** |

---

## 11. Summary: Module Ownership & Status Matrix

| Module | Files | Size | Public/Lite/Private | Overall Status | Has Tests | Owner |
|---|---|---|---|---|---|---|
| Root governance | 13 | ~33 KB | Public | ✅ Stable | N/A | DevOps / Legal |
| Community/CI | 6 | ~8.4 KB | Public | ✅ Stable | ✅ CI | DevOps |
| Config examples | 2 | ~1.2 KB | Public | ✅ Stable | N/A | Documentation |
| **Orchestrator** | **30** | **~145 KB** | Public | 🟡 Active | ⚠️ Partial | Orchestration Team |
| **PAIOS Core** | **16** | **~94 KB** | Public (Lite) | 🟡 Active | ❌ None | PAIOS Team |
| **Agent Team** | **11** | **~69 KB** | Public (Lite) | 🟡 Active | ❌ None | Agent Team |
| **Workers (all)** | **19** | **~109 KB** | Public | 🟡 Beta/Exp | ❌ None | Worker Team |
| Tests | 1 | ~5.6 KB | Public | 🟡 Active | — | QA |
| Scripts | 4 | ~8.6 KB | Public | ✅ Stable | N/A | DevOps |
| Docs | 13 (+1) | ~43 KB | Public | ⚠️ 3 stale | N/A | Documentation |

---

## Key Findings

1. **Test coverage is critically low** — 1 test file for 78 Python source files (~1.3%)
2. **3 documentation files are stale**: `DEVELOPMENT.md`, `CONFIGURATION.md`, `INSTALLATION.md` all reference non-existent paths
3. **PUBLIC_PACKAGE_COMPLETENESS_AUDIT.md is factually incorrect** — claims zero source code when 78 files exist
4. **All workers lack tests** despite being marked "Beta" or "Stable"
5. **No single module has an explicitly assigned owner** — ownership is implicit by code author
6. **`paios_core.py` (42 KB)** is the largest single file and a prime candidate for refactoring/splitting
7. **`config/agent_team/` directory is entirely missing** despite being documented as the primary config location
8. **9 files referenced in documentation are missing** (see section 3 of REPOSITORY_STRUCTURE_AUDIT.md)
