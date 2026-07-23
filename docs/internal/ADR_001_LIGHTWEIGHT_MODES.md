# ADR 001: Lite / Core / Full 三层部署模式

- **状态：** 提议中 (Proposed)
- **日期：** 2026-07-24
- **决策者：** 中书省 (Zhongshu)
- **关联：** ADR 002 (打包与CLI), ADR 003 (真实Demo管道), V011_IMPLEMENTATION_PLAN

---

## 1. 上下文 (Context)

### 1.1 问题陈述

Solo v0.1.0 的架构（见 `docs/ARCHITECTURE.md`）预设了一个完整的基础设施栈：

- **Docker 容器：** PostgreSQL + pgvector, NATS JetStream, Temporal, Prometheus, Grafana, Loki, Alloy (7 个容器)
- **外部运行时：** Node.js (OpenClaw Gateway), Python 3.11+, Codex CLI
- **GPU/驱动依赖：** Computer Use worker 依赖视觉模型推理
- **API Key 依赖：** DeepSeek API Key, Gemini API Key, Zhipu API Key

对于新用户或 demo 场景，这个门槛过高——一个想先"跑起来看看"的用户需要先配置 Docker、装 Node.js、申请至少 1 个 API Key，才能看到任何可运行的东西。这违反了"轻量、易部署、真实 Demo"的设计目标。

### 1.2 现有代码约束

审查代码库后发现：

| 模块 | 依赖级别 | 可剥离性 |
|------|----------|----------|
| `src/orchestrator/openclaw_night_workflow/` | 纯 Python + SQLite | ✅ 完全可独立运行 |
| `src/paios/paios/` | Python + SQLite (+ Pydantic) | ✅ 核心可独立，路由需要 API Key |
| `workers/browser_worker/` | Playwright + CDP | ⚠️ 需要浏览器/Docker |
| `workers/computer_use/` | Vision + 键盘/鼠标控制 | ❌ 需要 GPU/视觉模型 |
| `workers/windows_bridge/` | UIA + NamedPipe | ⚠️ 仅 Windows |
| `workers/watchdog/` | PowerShell | ⚠️ 仅 Windows |
| OpenClaw Gateway | Node.js | ❌ 需要 npm/Node |

关键洞察：**状态机、任务存储、风险评估、审批引擎、证据验证**这些核心逻辑全部在纯 Python 模块中，只依赖 SQLite 和标准库。

### 1.3 利益相关者

- **新用户：** 想要 5 分钟内跑通 demo，不需要配 Docker/Node/API Key
- **开发者：** 需要浏览器自动化、HTTP 能力来测试扩展
- **生产用户：** 需要完整的基础设施栈保障可靠性和可观测性

---

## 2. 决策 (Decision)

### 2.1 三层模式定义

我们引入 **Lite → Core → Full** 三层渐进式部署模式：

```
┌─────────────────────────────────────────────────────────┐
│                      FULL (生产)                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │                  CORE (扩展)                       │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │              LITE (零门槛)                   │  │  │
│  │  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌────────┐  │  │  │
│  │  │  │State  │ │ Risk  │ │Approval│ │Evidence│  │  │  │
│  │  │  │Machine│ │Engine │ │Engine │ │Validator│  │  │  │
│  │  │  └───────┘ └───────┘ └───────┘ └────────┘  │  │  │
│  │  │  ┌───────────────────────────────────────┐  │  │  │
│  │  │  │        SQLite TaskStore               │  │  │  │
│  │  │  └───────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │  + HTTP/浏览器 Workers + 可选模型 Provider          │  │
│  └───────────────────────────────────────────────────┘  │
│  + Docker 基础设施 + GPU Workers + 生产监控              │
└─────────────────────────────────────────────────────────┘
```

#### 2.1.1 Lite 模式（零门槛）

**定义：** 纯 Python，无 Docker/Node/GPU/API Key，纯本地文件操作。

**运行条件：**
- Python >= 3.11
- `pip install solo-agent`（仅 `dependencies`）
- 零外部服务、零 API Key

**包含模块：**

| 模块 | 来源 | 说明 |
|------|------|------|
| `solo.core.state_machine` | `src/paios/paios/state_machine.py` | 任务状态机 (RECEIVED→...→COMPLETED) |
| `solo.core.risk` | `src/paios/paios/risk.py` | RiskClassifier (R0-R3 关键词匹配) |
| `solo.core.policy` | `src/paios/paios/policy.py` | PolicyEngine (R0/R1 自动通过) |
| `solo.core.task_store` | `src/orchestrator/.../task_store.py` | SQLite TaskStore (完整 DDL) |
| `solo.core.approvals` | `src/orchestrator/.../approvals.py` | 审批创建/决议 (nonce + TTL) |
| `solo.core.evidence` | `src/orchestrator/.../evidence.py` | 文件清单导出 + SHA256 |
| `solo.core.schemas` | `src/orchestrator/.../schemas.py` | ValidationResult 数据类 |
| `solo.core.validator` | `src/orchestrator/.../validator_runner.py` | Phase 验证引擎 |
| `solo.demo.safe_demo` | *新建* | Safe Demo 管道 (见 ADR 003) |
| `solo.demo.veto_demo` | *新建* | VETO Demo (R3 拒绝) |

**不包含：**
- ❌ PAIOS 路由引擎 (`paios_core.py` route/resolve)
- ❌ Codex 适配器
- ❌ Gemini 适配器
- ❌ 浏览器/Windows/Computer Use workers
- ❌ 任何 HTTP 客户端

**Lite 模式的能力边界：**
- ✅ 创建任务 → 分类风险 → 生成计划 → 审批流程 → 执行动作 → 验证结果 → 审计记录
- ✅ 所有状态转换通过 SQLite 持久化
- ✅ 完整的 demo 管道可以在 30 秒内跑完
- ❌ 无外部 API 调用（无模型推理、无浏览器、无消息推送）
- ❌ 执行动作仅限本地文件操作

#### 2.1.2 Core 模式（扩展）

**定义：** Lite + HTTP/浏览器 Workers + 可选模型 Provider。

**额外依赖：** `pip install solo-agent[core]`

**新增模块：**

| 模块 | 说明 |
|------|------|
| `solo.routing.router` | PAIOS 路由引擎 (需要 API Key) |
| `solo.workers.browser` | Playwright/CDP 浏览器自动化 |
| `solo.workers.windows` | Windows UIA 桥接 |
| `solo.gateway.client` | OpenClaw Gateway HTTP 客户端 |
| `solo.providers.deepseek` | DeepSeek API 适配器 |
| `solo.providers.gemini` | Gemini API 适配器 |

**Core 模式的能力边界：**
- ✅ Lite 全部能力
- ✅ 模型推理（需要 API Key）
- ✅ 浏览器自动化
- ✅ Windows 桌面自动化
- ❌ Docker 基础设施（无 NATS/Temporal/PostgreSQL/Prometheus）
- ❌ GPU Workers (Computer Use)

#### 2.1.3 Full 模式（私有生产）

**定义：** Core + Docker 基础设施 + GPU Workers + 生产监控。

**部署方式：** `docker compose up` + 完整环境变量配置。

**新增模块：**

| 模块 | 说明 |
|------|------|
| `solo.infra.nats` | NATS JetStream 集成 |
| `solo.infra.temporal` | Temporal 工作流引擎 |
| `solo.infra.postgres` | PostgreSQL + pgvector |
| `solo.workers.computer_use` | 视觉+键鼠 GUI 控制 |
| `solo.observability` | Prometheus + Grafana + Loki |

---

### 2.2 模式检测与切换

```python
# solo/core/mode.py (伪代码)
import os
import importlib.util

class DeploymentMode(StrEnum):
    LITE = "lite"
    CORE = "core"
    FULL = "full"

def detect_mode() -> DeploymentMode:
    """自动检测当前部署模式。"""
    # 检查 Docker 基础设施
    docker_running = _check_docker_services()
    if docker_running:
        return DeploymentMode.FULL

    # 检查可选依赖
    has_httpx = importlib.util.find_spec("httpx") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    has_api_key = bool(os.environ.get("DEEPSEEK_API_KEY"))

    if has_httpx and (has_playwright or has_api_key):
        return DeploymentMode.CORE

    return DeploymentMode.LITE


# 模式可通过环境变量显式覆盖
# SOLO_MODE=lite|core|full
```

**降级策略：** 如果用户以 Core 模式启动但检测到缺少必需依赖，自动降级到 Lite 并发出警告，而非崩溃。

---

### 2.3 代码组织

```
src/solo/
├── __init__.py                  # 版本号, 模式检测
├── core/                        # Lite 核心 (零依赖)
│   ├── __init__.py
│   ├── mode.py                  # DeploymentMode 枚举 + detect_mode()
│   ├── state_machine.py         # 从 paios/state_machine.py 迁移
│   ├── enums.py                 # TaskState, RiskLevel, ApprovalState, etc.
│   ├── risk.py                  # RiskClassifier
│   ├── policy.py                # PolicyEngine
│   ├── task_store.py            # SQLite TaskStore
│   ├── approvals.py             # 审批引擎
│   ├── evidence.py              # 证据/清单
│   ├── schemas.py               # ValidationResult 等
│   └── validator.py             # Phase 验证
├── demo/                        # Demo 管道 (Lite 可用)
│   ├── __init__.py
│   ├── safe_demo.py             # Safe Demo (见 ADR 003)
│   └── veto_demo.py             # VETO Demo (见 ADR 003)
├── routing/                     # Core: 模型路由
│   ├── __init__.py
│   └── router.py                # PAIOS 路由引擎
├── workers/                     # Core: 浏览器/桌面 Workers
│   ├── __init__.py
│   ├── browser.py
│   └── windows.py
├── providers/                   # Core: 模型 Provider 适配器
│   ├── __init__.py
│   ├── deepseek.py
│   └── gemini.py
├── infra/                       # Full: Docker 基础设施
│   ├── __init__.py
│   ├── nats.py
│   ├── temporal.py
│   └── postgres.py
├── observability/               # Full: 监控
│   ├── __init__.py
│   ├── metrics.py
│   └── logging.py
└── cli/                         # CLI 入口
    ├── __init__.py
    ├── main.py                  # click 主入口
    ├── doctor.py
    ├── demo.py
    ├── test.py
    └── cleanup.py
```

**迁移策略：** 不修改现有 `src/orchestrator/` 和 `src/paios/` 下的任何源码文件。Lite 核心通过符号链接或导入桥接使用现有模块，或在新 `src/solo/core/` 下创建精简副本。

---

## 3. 后果 (Consequences)

### 3.1 正面影响

1. **零门槛体验：** 新用户 `pip install solo-agent && solo demo safe` 即可在 30 秒内看到完整的编排管道运行
2. **渐进式采用：** 从 Lite 开始，逐步添加 Core/Full 功能，无需重装
3. **清晰的边界：** 每个模式的能力边界明确，用户不会被"需要装 Docker 才能跑 Demo"的挫败感劝退
4. **测试友好：** Lite 模式可用于 CI/CD 快速测试核心逻辑，无需启动 Docker
5. **向后兼容：** 现有 `src/orchestrator/` 和 `src/paios/` 代码不变

### 3.2 负面权衡

1. **代码维护成本：** Lite/Core/Full 共享一些模块但聚合方式不同，需要确保核心模块在不同模式下行为一致
2. **模式边界模糊风险：** 如果 Core 模块被 Lite 代码引入，可能导致隐式依赖。需通过 `importlib` 守卫和 CI 检查来防范
3. **文档复杂度：** 需要三套文档说明不同模式的能力和限制
4. **测试矩阵扩大：** 需要在三种模式下分别运行测试套件

### 3.3 缓解措施

- **Lite CI 流水线：** 在纯净 Python 3.11 环境中运行，验证零依赖导入
- **依赖守卫：** 所有可选依赖通过 `try/except ImportError` 包装，在导入时给出明确的错误信息而非 traceback
- **`solo doctor` 命令：** 自动检测当前模式、可用能力和缺失依赖（见 ADR 002）
- **模式标记：** 每个公共 API 模块用 `__solo_mode__` 属性标记其所需最低模式

---

## 4. 备选方案

### 方案 A：保持单体，通过配置开关控制（未采用）
将所有代码打包在一起，通过 `solo.toml` 配置文件的 `[mode]` 段控制。不采用原因：配置驱动无法阻止用户在 Lite 模式下 import 需要 Docker 的模块——会在运行时才崩溃，不如在 import 时就明确失败。

### 方案 B：独立三个包 solo-lite / solo-core / solo-full（未采用）
拆分为三个 PyPI 包。不采用原因：维护三个独立包的版本同步、依赖管理和发布流水线成本过高。

### 方案 C：单包 + extras（采用）
一个 `solo-agent` PyPI 包，通过 `[core]` 和 `[full]` extras 控制可选依赖安装。Lite 是默认安装。这是 Python 生态的标准实践，维护成本最低。

---

## 5. 参考

- `docs/ARCHITECTURE.md` — 现有系统架构
- `src/paios/paios/state_machine.py` — 现有任务状态机
- `src/paios/paios/risk.py` — 风险评估引擎
- `src/paios/paios/policy.py` — 策略引擎
- `src/orchestrator/openclaw_night_workflow/task_store.py` — SQLite TaskStore
- `src/orchestrator/openclaw_night_workflow/approvals.py` — 审批引擎
- `src/orchestrator/openclaw_night_workflow/evidence.py` — 证据/清单
- `src/orchestrator/openclaw_night_workflow/validator_runner.py` — 验证引擎
- `requirements-demo.txt` — 当前 demo 最小依赖
- ADR 002 — 打包与 CLI 设计
- ADR 003 — 真实 Demo 管道设计
