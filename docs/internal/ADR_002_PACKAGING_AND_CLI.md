# ADR 002: 打包方案与 CLI 入口设计

- **状态：** 提议中 (Proposed)
- **日期：** 2026-07-24
- **决策者：** 中书省 (Zhongshu)
- **关联：** ADR 001 (三层模式), ADR 003 (真实Demo管道), V011_IMPLEMENTATION_PLAN

---

## 1. 上下文 (Context)

### 1.1 问题陈述

Solo v0.1.0 没有统一的 Python 包入口或 CLI：

- **无 `pyproject.toml`：** 项目没有标准的 Python 包配置文件，无法通过 `pip install` 安装
- **无统一 CLI：** 现有入口分散在多个脚本中：
  - `scripts/doctor.ps1` — PowerShell 环境检查
  - `scripts/start_demo.ps1` — PowerShell Demo 脚本（mock 数据）
  - `scripts/stop_demo.ps1` — PowerShell 清理脚本
  - `src/orchestrator/openclaw_night_workflow/cli.py` — argparse 子命令（内部工具）
  - `src/orchestrator/openclaw_night_workflow/workflow_control_cli.py` — 另一个 argparse 入口
  - `src/orchestrator/openclaw_night_workflow/validator_cli.py` — 验证器 CLI
- **依赖声明散落：**
  - `requirements-demo.txt` — demo 依赖
  - 各模块内部 `import` — 隐式依赖

v0.1.1 需要统一的 **`solo`** 命令作为唯一入口，支持 `solo doctor`、`solo demo safe`、`solo demo veto`、`solo test`、`solo cleanup`。

### 1.2 现有 CLI 代码分析

审查现有 CLI 入口：

**`cli.py` (openclaw-night-workflow)：**
- 使用 `argparse`
- 子命令：`init-db`, `health`, `start-workflow`, `query-workflow`, `pause-workflow`, `resume-workflow`, `cancel-workflow`, `codex-health`, `export-file-manifest`, `create-rollback`
- 输出：JSON 到 stdout
- 设计风格：每次调用返回 JSON，通过 exit code 表示成功/失败（适合脚本集成）

**`workflow_control_cli.py`：**
- 使用 `argparse`
- 子命令：`status`, `start`, `pause`, `resume`, `cancel`, `approve`, `reject`, `export`
- 输出：JSON 到 stdout
- 特有的 `--owner-id` 授权检查

**`validator_cli.py`：**
- 使用 `argparse`
- 单功能：`--phase {bootstrap-entry,phase1,phase2,phase3}`
- 输出：JSON 到 stdout

**共同模式：** 所有 CLI 都使用 argparse + JSON 输出 + exit code 语义。适合自动化，但对人的可读性（human-readable output）不够友好。

### 1.3 利益相关者

- **终端用户：** 需要直觉式的命令和人类可读的输出
- **CI/CD 管道：** 需要 JSON 输出 + 明确的 exit code
- **PowerShell 用户：** 当前 demo 脚本为 PowerShell，但 Python CLI 应跨平台

---

## 2. 决策 (Decision)

### 2.1 CLI 框架选择：Click

经过 `argparse`、`Click`、`Typer` 三方比较：

| 维度 | argparse | Click | Typer |
|------|----------|-------|-------|
| 标准库内置 | ✅ 是 | ❌ 否 | ❌ 否 |
| 嵌套子命令 | ⚠️ 手动构建 | ✅ 原生 Group | ✅ 原生 Group |
| 类型提示 | ❌ 无 | ⚠️ 装饰器 | ✅ 原生 |
| 人类可读输出 | ⚠️ 需要自己写 | ✅ 彩色/进度条 | ✅ 继承 Click |
| 学习曲线 | 低 | 低 | 中 |
| 社区采用 | 广泛 | 极广泛 | 增长中 |
| JSON 输出支持 | ⚠️ 需要自己序列化 | ⚠️ 需要自己序列化 | ✅ 可通过 callback |

**选择 Click，理由：**

1. **成熟度：** Click 是 Python CLI 的事实标准（Flask CLI、pipenv、AWS CLI v2 等）
2. **嵌套命令：** `solo demo safe` 这种两级子命令在 Click 中通过 `@cli.group()` 自然表达
3. **轻量：** Click 是纯 Python，无额外 C 依赖，符合 Lite 模式"零门槛"要求
4. **Lite 依赖：** Click 已包含在 `requirements-demo.txt` 中（但只是 `typer>=0.9.0`）。我们改用 Click 直接依赖以简化依赖栈。
5. **避免 Typer 的额外依赖：** Typer 依赖 Click + typing-extensions + rich，在 Lite 模式下增加不必要依赖

### 2.2 CLI 命令树

```
solo
├── doctor                        # 环境检查 (Lite)
│   └── --json                    # JSON 输出模式
├── demo                          # Demo 子命令组
│   ├── safe                      # Safe Demo: R0 任务端到端管道
│   │   └── --workspace PATH      # 指定工作目录
│   │   └── --json                # JSON 输出模式
│   └── veto                      # VETO Demo: R3 任务被拒绝
│       └── --workspace PATH
│       └── --json
├── test                          # 运行测试套件 (Lite)
│   ├── --unit                    # 仅单元测试
│   ├── --integration             # 集成测试 (需要 Core)
│   └── --coverage                # 生成覆盖率报告
├── cleanup                       # 清理 demo/测试产物 (Lite)
│   └── --all                     # 清理所有 (含数据库)
└── version                       # 显示版本和模式信息 (Lite)
```

### 2.3 输出模式设计

每个命令支持两种输出模式，通过 `--json` flag 切换：

**人类可读模式（默认）：**
```
$ solo demo safe

===== Solo Safe Demo v0.1.1 =====
Mode: Lite
Workspace: C:\Users\xxx\AppData\Local\Temp\solo-demo-a1b2c3d4

[1/8] RECEIVED        Creating task .............. ✅
[2/8] TRIAGED         Risk assessment ............ ✅ R0 (read_only_or_no_side_effect)
[3/8] PLANNING        Generating plan ............ ✅ 3 steps
[4/8] REVIEW_PENDING  Policy evaluation .......... ✅ auto-approved
[5/8] APPROVED        Review passed .............. ✅
[6/8] DISPATCHED      Dispatching to executor .... ✅
[7/8] EXECUTING       Running task ............... ✅ word_count=29
[8/8] VALIDATING      Verifying result ........... ✅ PASS
                      COMPLETED .................. 🎉

===== Demo SUCCESS =====
Pipeline: RECEIVED → TRIAGED → PLANNING → REVIEW_PENDING → APPROVED → DISPATCHED → EXECUTING → VALIDATING → COMPLETED
Duration: 0.3s
```

**JSON 模式（`--json`）：**
```json
{
  "status": "PASS",
  "mode": "lite",
  "pipeline": {
    "task_id": "task-a1b2c3d4e5f6g7h8",
    "states": [
      {"state": "RECEIVED", "timestamp": "2026-07-24T03:54:00Z", "ok": true},
      {"state": "TRIAGED", "timestamp": "2026-07-24T03:54:00Z", "ok": true, "risk": "R0"},
      ...
    ],
    "result": {"word_count": 29, "validation": "PASS"}
  },
  "duration_ms": 312
}
```

### 2.4 pyproject.toml 依赖分层

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "solo-agent"
version = "0.1.1a0"
description = "Solo: Personal AI agent system for Windows — lightweight, safe, extensible"
readme = "README.md"
license = {file = "LICENSE"}
requires-python = ">=3.11"
authors = [
    {name = "chengcheng-2006", email = "chengcheng-2006@users.noreply.github.com"},
]
keywords = ["ai-agent", "windows", "orchestration", "approval", "safety"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

# ============================================================
# Lite 模式依赖 (pip install solo-agent)
# 零外部服务、零 API Key、纯本地文件操作
# ============================================================
dependencies = [
    "click>=8.1.0",       # CLI 框架
    "pydantic>=2.0.0",    # 数据验证 (schemas)
]

# ============================================================
# Core 模式依赖 (pip install solo-agent[core])
# HTTP/浏览器/可选模型 Provider
# ============================================================
[project.optional-dependencies]
core = [
    "httpx>=0.27.0",            # HTTP 客户端 (API 调用)
    "playwright>=1.45.0",       # 浏览器自动化
    "python-dateutil>=2.8.0",   # 日期工具
    "rich>=13.0.0",             # 终端美化 (表格/进度条)
]

# ============================================================
# 开发/测试依赖 (pip install solo-agent[dev])
# ============================================================
dev = [
    "pytest>=8.0.0",            # 测试框架
    "pytest-cov>=5.0.0",        # 覆盖率
    "pytest-timeout>=2.0.0",    # 测试超时
    "pytest-xdist>=3.0.0",      # 并行测试
    "ruff>=0.4.0",              # Linter + Formatter
    "mypy>=1.10.0",             # 类型检查
    "build>=1.0.0",             # 打包工具
    "twine>=5.0.0",             # PyPI 上传
]

# ============================================================
# Full 模式标记 (pip install solo-agent[full])
# Full 通过 docker compose 管理，Python 包层面不需要额外依赖
# 仅作为便利别名
# ============================================================
full = [
    "solo-agent[core]",
]

[project.scripts]
solo = "solo.cli.main:cli"

[project.urls]
Homepage = "https://github.com/chengcheng-2006/solo-windows-ai-agent"
Documentation = "https://github.com/chengcheng-2006/solo-windows-ai-agent/tree/main/docs"
Repository = "https://github.com/chengcheng-2006/solo-windows-ai-agent.git"
Issues = "https://github.com/chengcheng-2006/solo-windows-ai-agent/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/solo"]

[tool.hatch.build.targets.wheel.force-include]
"src/orchestrator" = "solo/_vendor/orchestrator"
"src/paios" = "solo/_vendor/paios"

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = ["-v", "--strict-markers", "--tb=short"]
markers = [
    "lite: tests that run in Lite mode (no external deps)",
    "core: tests that require Core mode (HTTP/browser)",
    "full: tests that require Full mode (Docker infrastructure)",
    "slow: tests that take >10 seconds",
]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
```

### 2.5 doctor 命令规范

`solo doctor` 检查 Lite 模式所需的全部前提条件：

| 检查项 | 必要 | 说明 |
|--------|------|------|
| OS 信息 | ✅ | Windows/Linux/macOS 检测 |
| Python 版本 | ✅ | >= 3.11 |
| 磁盘空间 | ✅ | 工作目录 >= 100 MB 可用 |
| 文件系统权限 | ✅ | 可读写临时目录 |
| Git | ⚠️ 建议 | 用于版本追踪 |
| Node.js | ❌ 可选 | Core 模式需要 |
| Docker | ❌ 可选 | Full 模式需要 |
| API Key | ❌ 可选 | Core 模式需要 (DEEPSEEK_API_KEY) |
| Playwright | ❌ 可选 | Core 模式浏览器 |workers 需要 |

**输出示例：**
```
$ solo doctor

===== Solo Doctor v0.1.1 =====

✅ Windows         Windows 10.0.26200
✅ Python          3.11.9
✅ Disk Space      45.2 GB free (C:\)
✅ Write Access    Temp directory writable
✅ Git             2.45.0
⚠️  Node.js         Not found (Core mode needs this)
⚠️  Docker          Not found (Full mode needs this)
⚠️  API Key         DEEPSEEK_API_KEY not set (Core mode needs this)

===== Result: 5 pass, 0 fail, 3 warn =====
Mode: Lite (ready)
Run `solo demo safe` to try the pipeline.
```

### 2.6 cleanup 命令规范

```
$ solo cleanup
Cleaning up 3 demo workspaces ............. ✅ 12 MB freed

$ solo cleanup --all
⚠️  This will delete all demo data and test databases.
Are you sure? [y/N]: y
Cleaning up all workspaces ................ ✅ 45 MB freed
Cleaning up test databases ................ ✅ night_workflows.db deleted
```

---

## 3. 后果 (Consequences)

### 3.1 正面影响

1. **单一入口：** `solo` 命令覆盖所有用户操作，无需记住多个脚本路径
2. **渐进式复杂度：** `solo doctor` → `solo demo safe` → `solo test` 自然的学习路径
3. **人类+机器双模式：** 默认输出人类友好，`--json` 适合 CI/CD
4. **标准打包：** `pip install solo-agent` 符合 Python 生态标准
5. **依赖分层清晰：** `[core]` 和 `[dev]` extras 让用户按需安装

### 3.2 负面权衡

1. **向后兼容：** 现有 PowerShell 脚本 (`scripts/*.ps1`) 需要迁移或标记为 deprecated
2. **Click 额外依赖：** 虽然轻量（~200KB），但为 Lite 模式增加了唯一一个外部依赖
3. **Windows 路径：** CLI 在 Windows 上可能遇到路径编码问题（UTF-8 vs GBK），需要处理

### 3.3 缓解措施

- **PowerShell 脚本保留：** 现有 `scripts/` 下的 PS1 脚本保留但添加 deprecation notice，指向 `solo` 命令
- **Click 依赖最小化：** 使用 `click>=8.1.0`（8.1 是当前稳定版，纯 Python，无 C 扩展）
- **编码处理：** 在 CLI 入口处设置 `PYTHONUTF8=1` 或使用 `sys.stdout.reconfigure(encoding='utf-8')`

---

## 4. 备选方案

### 方案 A：纯 argparse + 手动子命令（未采用）
优点：零外部依赖。缺点：嵌套子命令需要大量样板代码，输出格式化需要自己实现，维护成本高。

### 方案 B：Typer（未采用）
优点：类型提示驱动，自动生成 `--help`，与 FastAPI 风格一致。缺点：依赖 `rich` + `typing-extensions`，增加 2 个额外依赖。对于 Lite 模式来说太重。

### 方案 C：Click（采用）
优点：成熟、轻量、嵌套命令自然、社区广泛采用。缺点：增加一个外部依赖。但权衡后认为这是最合理的。

---

## 5. 参考

- `scripts/doctor.ps1` — 现有 doctor 检查脚本
- `scripts/start_demo.ps1` — 现有 demo 脚本
- `requirements-demo.txt` — 现有 demo 依赖
- `src/orchestrator/openclaw_night_workflow/cli.py` — 现有内部 CLI
- `src/orchestrator/openclaw_night_workflow/workflow_control_cli.py` — 现有 workflow 控制 CLI
- `src/orchestrator/openclaw_night_workflow/validator_cli.py` — 现有验证器 CLI
- ADR 001 — 三层部署模式
- ADR 003 — 真实 Demo 管道设计
