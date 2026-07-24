# Repository Structure Audit

**Generated:** 2026-07-24 03:54+08:00 (UTC+8)
**Auditor:** 吏部 (subagent, v0.1.1)
**Branch:** `release/v0.1.1-star-ready`
**Commit:** `dc4cd28`
**Git-tracked files:** 114
**On-disk files (excluding __pycache__):** 114 tracked, 0 untracked (excluding gitignored bytecache)
**Total size (tracked):** ~478 KB

---

## 1. Complete File Tree

```
solo-windows-ai-agent/                              477.6 KB  (114 tracked files)
│
├── .env.example                                      1,977 B   Config template
├── .gitattributes                                      279 B   Git attributes
├── .gitignore                                          811 B   Git ignore rules
├── .gitleaks.toml                                    1,465 B   Gitleaks config
├── CHANGELOG.md                                      1,066 B   Release changelog
├── CODE_OF_CONDUCT.md                                1,752 B   Code of conduct
├── CONTRIBUTING.md                                   2,012 B   Contributing guide
├── LICENSE                                           11,344 B  Apache 2.0
├── README.md                                         6,156 B   English README
├── README.zh-CN.md                                   3,484 B   Chinese README
├── ROADMAP.md                                        1,982 B   Roadmap
├── REQUIREMENTS-demo.txt                               204 B   Demo dependencies
├── SECURITY.md                                       2,034 B   Security policy
├── THIRD_PARTY_NOTICES.md                            2,605 B   Third-party licenses
├── gitleaks-report.json                                  3 B   Empty gitleaks report
│
├── .github/                                            (4 items)
│   ├── dependabot.yml                                  466 B
│   ├── PULL_REQUEST_TEMPLATE.md                        928 B
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml                            2,552 B
│   │   ├── config.yml                                  401 B
│   │   └── feature_request.yml                       1,535 B
│   └── workflows/
│       └── ci.yml                                    2,558 B
│
├── config/
│   └── examples/
│       ├── agent_roles.yaml                            506 B
│       └── solo_model_routing.yaml                     684 B
│
├── docs/                                              (14 items)
│   ├── ARCHITECTURE.md                               5,270 B
│   ├── CONFIGURATION.md                              2,155 B
│   ├── DEVELOPMENT.md                                2,774 B
│   ├── FAQ.md                                        3,321 B
│   ├── GITHUB_PUBLISH_FINAL_REPORT.md                  716 B  (JSON report)
│   ├── INSTALLATION.md                               3,332 B
│   ├── LAUNCH_CHECKLIST.md                           3,593 B
│   ├── LAUNCH_POSTS.md                               6,839 B
│   ├── PUBLIC_PACKAGE_COMPLETENESS_AUDIT.md          1,829 B
│   ├── SECURITY_MODEL.md                             3,017 B
│   ├── TROUBLESHOOTING.md                            2,652 B
│   └── internal/
│       └── (empty — output directory for this audit)
│
├── scripts/                                           (4 items)
│   ├── doctor.ps1                                    2,217 B
│   ├── setup.ps1                                     1,720 B
│   ├── start_demo.ps1                                4,157 B
│   └── stop_demo.ps1                                   456 B
│
├── src/                                               (78 files total)
│   ├── __init__.py                                      36 B
│   │
│   ├── orchestrator/                                  (30 files)
│   │   ├── __init__.py                                  31 B
│   │   └── openclaw_night_workflow/                   (29 .py files)
│   │       ├── __init__.py                              81 B
│   │       ├── app.py                                3,493 B   FastAPI application
│   │       ├── approvals.py                          1,759 B   Approval gate logic
│   │       ├── cli.py                                3,086 B   CLI entry point
│   │       ├── codex_adapter.py                      2,969 B   Codex agent adapter
│   │       ├── config.py                             1,340 B   Local configuration
│   │       ├── dispatcher.py                         1,114 B   Task dispatcher
│   │       ├── edict_adapter.py                      4,070 B   Edict/command adapter
│   │       ├── evidence.py                             778 B   Audit evidence
│   │       ├── gemini_adapter.py                     6,384 B   Gemini model adapter
│   │       ├── locks.py                              1,020 B   Concurrent access locks
│   │       ├── manifest.py                           1,654 B   File manifest
│   │       ├── notifications.py                        540 B   Notification handlers
│   │       ├── paios_acceptance.py                  10,576 B   PAIOS acceptance tests
│   │       ├── paios_bridges.py                     12,714 B   PAIOS bridge utilities
│   │       ├── paios_cli.py                         16,538 B   PAIOS CLI interface
│   │       ├── paios_core.py                        42,014 B   PAIOS core logic
│   │       ├── process_watcher.py                    1,056 B   Process monitoring
│   │       ├── redaction.py                            781 B   Data redaction
│   │       ├── retry_controller.py                     772 B   Retry logic
│   │       ├── rollback.py                           1,320 B   Rollback support
│   │       ├── schemas.py                            2,220 B   Data schemas
│   │       ├── security.py                             851 B   Security utilities
│   │       ├── state_machine.py                      1,294 B   Task state machine
│   │       ├── task_store.py                         7,183 B   SQLite task persistence
│   │       ├── validator_cli.py                        856 B   Validator CLI
│   │       ├── validator_runner.py                   7,340 B   Validator runner
│   │       ├── workflow_control.py                   7,274 B   Workflow control
│   │       └── workflow_control_cli.py               2,097 B   Workflow control CLI
│   │
│   └── paios/                                        (17 files)
│       ├── __init__.py                                  13 B
│       └── paios/                                    (16 files)
│           ├── __init__.py                              71 B
│           ├── config.py                             3,580 B   PAIOS config
│           ├── control_plane.py                     23,900 B   FastAPI control plane
│           ├── database.py                          11,263 B   DB persistence (SQLite)
│           ├── enums.py                             1,184 B   Enumerations
│           ├── input_vault.py                        5,519 B   Secure input handling
│           ├── main.py                              8,105 B   PAIOS entry point
│           ├── migrations.py                        2,621 B   DB migrations
│           ├── policy.py                              939 B   Policy engine
│           ├── privacy_broker.py                    11,033 B   Privacy redaction
│           ├── risk.py                              2,663 B   Risk assessment
│           ├── schemas.py                           8,393 B   Pydantic schemas
│           ├── security.py                          3,467 B   Security utilities
│           ├── state_machine.py                     1,834 B   Workflow state machine
│           └── agent_team/                          (10 files)
│               ├── audit.py                         1,427 B
│               ├── capabilities.py                  4,390 B
│               ├── errors.py                          513 B
│               ├── heartbeat.py                     3,282 B
│               ├── middleware.py                     5,250 B
│               ├── models.py                       14,572 B
│               ├── policy.py                       10,247 B
│               ├── registry.py                      2,520 B
│               ├── review.py                        3,808 B
│               ├── state_machine.py                12,021 B
│               └── tokens.py                       10,610 B
│
├── tests/
│   ├── test_core.py                                 5,619 B   14 test cases
│   └── (only 1 test file — smoke/core tests)
│
└── workers/                                          (16 files)
    ├── browser_worker/                               (2 files)
    │   ├── __init__.py                                  63 B
    │   └── worker.py                                5,406 B   CDP/Playwright worker
    ├── computer_use/                                 (7 files)
    │   ├── __init__.py                                 417 B
    │   ├── control.py                               5,071 B   Input control
    │   ├── controller.py                            6,882 B   GUI controller
    │   ├── coordinates.py                           2,005 B   Coordinate math
    │   ├── gpu_resource_manager.py                 12,755 B   GPU management
    │   ├── models.py                               23,291 B   ML models
    │   ├── policy.py                               15,010 B   Safety policy
    │   └── server.py                                3,703 B   Server entry
    ├── vision_worker/                                (2 files)
    │   ├── __init__.py                                 123 B
    │   └── worker.py                                5,164 B   OCR worker
    ├── watchdog/                                     (2 files)
    │   ├── __init__.py                                  24 B
    │   └── watchdog.py                              9,141 B   Health monitoring
    └── windows_bridge/                               (6 files)
        ├── __init__.py                                  97 B
        ├── client.py                                1,305 B   UIA client
        ├── dispatcher.py                            5,581 B   Task dispatch
        ├── registry.py                              4,951 B   UIA registry
        ├── security.py                              3,243 B   Security layer
        ├── server.py                                  998 B   NamedPipe server
        └── uia.py                                   5,054 B   UIA automation core
```

---

## 2. Files That Exist But Documentation Claims Don't Exist

The **`PUBLIC_PACKAGE_COMPLETENESS_AUDIT.md`** (generated at 2026-07-24 03:14, before code was committed to this branch) declares:

> *"The current release package contains zero lines of actual source code, zero executable scripts, zero tests, and zero demo."*

This is **incorrect for the current state of `release/v0.1.1-star-ready`**. The following exist:

| Missing-Audit Claim | Reality | Count |
|---|---|---|
| "Source code (.py) = 0" | **78 Python source files exist** | 78 |
| "Scripts/ is empty" | **4 .ps1 scripts exist** | 4 |
| "Tests/ is empty" | **1 test file exists (14 test cases)** | 1 |
| "Executable scripts = 0" | **4 PowerShell scripts exist** | 4 |
| "Demo = 0" | **start_demo.ps1 + stop_demo.ps1 + requirements-demo.txt exist** | 3 |

**Explanation**: The `PUBLIC_PACKAGE_COMPLETENESS_AUDIT.md` was generated before code files were committed to this branch. The branch now contains the full public source tree.

---

## 3. Files Documented As Existing But Actually Missing

The following files are **referenced in documentation but do not exist** in the repository:

### From `DEVELOPMENT.md` (Code Structure section)

| Documented Path | Docs Claim | Status |
|---|---|---|
| `apps/paios/` | PAIOS orchestration core | ❌ **Missing** — Actual location: `src/paios/paios/` |
| `agents/` | Agent definitions (三省六部) | ❌ **Missing** — Agent code is in `src/paios/paios/agent_team/` |
| `infra/` | Docker infrastructure | ❌ **Missing** |
| `tools/` | Diagnostic tools | ❌ **Missing** |

### From `INSTALLATION.md`

| Documented Path | Docs Claim | Status |
|---|---|---|
| `requirements.txt` | Python dependencies | ❌ **Missing** — `requirements-demo.txt` exists instead |
| `infra/docker-compose.yml` | Docker Compose file | ❌ **Missing** |
| `scripts/start.ps1` | Start script | ❌ **Missing** — Only `start_demo.ps1` exists |
| `scripts/stop.ps1` | Stop script | ❌ **Missing** — Only `stop_demo.ps1` exists |
| `scripts/uninstall.ps1` | Uninstall script | ❌ **Missing** |
| `scripts/test_smoke.ps1` | Smoke test script | ❌ **Missing** |
| `scripts/quick_ports.ps1` | Port status script | ❌ **Missing** |

### From `CONFIGURATION.md`

| Documented Path | Docs Claim | Status |
|---|---|---|
| `config/agent_team/agent_role_mapping.yaml` | Role definitions | ❌ **Missing** — Entire `config/agent_team/` dir doesn't exist |
| `config/agent_team/permission_matrix.yaml` | Tool access matrix | ❌ **Missing** |
| `config/agent_team/state_machine.yaml` | State machine config | ❌ **Missing** |
| `config/agent_team/review.schema.json` | Review schema | ❌ **Missing** |
| `config/agent_team/memorial.schema.json` | Report schema | ❌ **Missing** |
| `config/agent_team/agents.schema.json` | Agent schema | ❌ **Missing** |
| `config/model-routing.json` | Model routing config | ❌ **Missing** |
| `config/runtime_ports.yaml` | Port configuration | ❌ **Missing** |

### From `ARCHITECTURE.md`

| Documented Path | Docs Claim | Status |
|---|---|---|
| `apps/paios/` | PAIOS core | ❌ **Missing** — Uses `src/paios/paios/` instead |

### From `.gitignore` (Referenced Files That Are Listed To Be Ignored)

| Path | Purpose | Status |
|---|---|---|
| `hermes-agent/` | Hermes Agent directory | ❌ **Missing** (gitignored/excluded from public release) |
| `state/` | State directory | ❌ **Missing** |
| `data/` | Data directory | ❌ **Missing** |
| `models/` | Models directory | ❌ **Missing** |
| `evidence/` | Evidence directory | ❌ **Missing** |

### Missing Empty Directories Referenced in README

| Directory | Referenced In | Status |
|---|---|---|
| `assets/demo/` | README (implied by asset structure) | Empty directory exists |
| `assets/logo/` | README (implied by asset structure) | Empty directory exists |
| `assets/screenshots/` | README (implied by asset structure) | Empty directory exists |
| `assets/social-preview/` | README (implied by asset structure) | Empty directory exists |
| `docs/internal/` | (This audit output) | Empty directory exists |

---

## 4. Redundant / Orphaned / Orphan Files

### Redundant Duplicates

| Files | Notes |
|---|---|
| `src/paios/__init__.py` (13 B) + `src/paios/paios/__init__.py` (71 B) + `src/paios/paios/agent_team/__init__.py` (implicit) | Standard Python package init; no redundancy |
| `src/orchestrator/__init__.py` (31 B) + `src/orchestrator/openclaw_night_workflow/__init__.py` (81 B) | Standard Python package init |
| `src/paios/paios/state_machine.py` (1,834 B) vs `src/orchestrator/openclaw_night_workflow/state_machine.py` (1,294 B) | **Separate code**, different modules — PAIOS vs orchestrator state machines. Likely intentional split but bears auditing. |
| `src/paios/paios/security.py` (3,467 B) vs `src/orchestrator/openclaw_night_workflow/security.py` (851 B) | **Separate code**, same concern — PAIOS layer vs orchestrator layer. Potential functional overlap. |
| `src/paios/paios/policy.py` (939 B) vs `src/paios/paios/agent_team/policy.py` (10,247 B) | Possibly different levels (system policy vs agent policy). Review needed. |
| `src/paios/paios/risk.py` (2,663 B) vs `src/paios/paios/agent_team/tokens.py` (10,610 B) (risk-related) | Separate domains. |

### Stale/Untracked Files on Disk

| File | Size | Status |
|---|---|---|
| `__pycache__/` directories (multiple) | ~87 KB total | Generated bytecode; properly gitignored. Not a problem. |
| `gitleaks-report.json` | 3 B | Empty JSON — placeholder or leftover artifact. |

### Files That Exist But Have No Clear Module Owner

| File | Module | Concern |
|---|---|---|
| `gitleaks-report.json` | Root | Empty placeholder; no clear owner |
| `src/__init__.py` (36 B) | Root src | Empty init; could be removed since `src/orchestrator/` and `src/paios/` each have their own `__init__.py` |
| `docs/LAUNCH_POSTS.md` | Docs | Marketing content — outside normal documentation scope |
| `docs/LAUNCH_CHECKLIST.md` | Docs | Release checklist — belongs in release tooling |

---

## 5. Summary Statistics

| Category | Count | Size (approx) |
|---|---|---|
| Python source files (.py) | 78 | 410 KB |
| PowerShell scripts (.ps1) | 4 | 8.6 KB |
| Markdown docs (.md) | 19 | 54 KB |
| YAML config (.yml/.yaml) | 7 | 10.3 KB |
| Config/tooling (.example, .toml, .json, .git*) | 5 | 5.3 KB |
| License files | 2 | 13.9 KB |
| **Total tracked** | **114** | **~478 KB** |
| __pycache__ (gitignored) | ~23 files | ~87 KB |
| Empty asset directories | 4 directories | 0 KB |

---

## Audit Gaps / Risks

1. **DEVELOPMENT.md structure is stale** — References `apps/paios/`, `agents/`, `infra/`, `tools/` which don't exist; actual structure uses `src/` namespacing
2. **CONFIGURATION.md over-promises** — Claims 8 configuration files under `config/agent_team/` and `config/` that don't exist
3. **INSTALLATION.md references missing scripts** — `start.ps1`, `stop.ps1`, `uninstall.ps1`, `test_smoke.ps1` are referenced but don't exist
4. **PUBLIC_PACKAGE_COMPLETENESS_AUDIT.md is stale/incorrect** — Claims zero source code, which is now false
5. **No `requirements.txt`** — Only `requirements-demo.txt` exists; full dependencies not declared
6. **No `requirements-dev.txt`** — Referenced in DEVELOPMENT.md but missing
7. **Naming inconsistency** — Documentation says `apps/paios/` but actual is `src/paios/paios/` (double nested)
8. **Empty asset directories** — `assets/demo/`, `assets/logo/`, `assets/screenshots/`, `assets/social-preview/` are all empty
