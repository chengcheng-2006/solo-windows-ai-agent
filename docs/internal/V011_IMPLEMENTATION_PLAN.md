# Solo v0.1.1 实施计划

- **版本：** v0.1.1-alpha
- **日期：** 2026-07-24
- **制定者：** 中书省 (Zhongshu)
- **关联 ADR：** [ADR 001](ADR_001_LIGHTWEIGHT_MODES.md) · [ADR 002](ADR_002_PACKAGING_AND_CLI.md) · [ADR 003](ADR_003_REAL_DEMO_PIPELINE.md)
- **总预估时间：** ~12 个工程小时（不含审查/测试等待时间）

---

## 1. 概述

### 1.1 目标

将 Solo 从 v0.1.0 修复/升级到 v0.1.1-alpha，实现：

1. **三层部署模式 (Lite/Core/Full)** — 渐进式能力梯度，Lite 零门槛
2. **统一 CLI** (`solo doctor|demo safe|demo veto|test|cleanup`) — Click 框架
3. **真实 Demo 管道** — 调用 TaskStore、StateMachine、Risk、Policy、Approval、Evidence、Validator
4. **标准打包 (pyproject.toml)** — pip install 就绪，分层依赖
5. **严格测试** — 单元测试 (Lite) + 冒烟测试 (Demo) + 集成测试

### 1.2 不修改的代码

| 目录/文件 | 说明 |
|----------|------|
| `src/orchestrator/**` | 现有编排器代码保持不变 |
| `src/paios/**` | 现有 PAIOS 代码保持不变 |
| `workers/**` | 现有 Worker 代码保持不变 |
| `scripts/*.ps1` | 现有 PowerShell 脚本保留（添加 deprecation notice） |
| `config/**`, `assets/**` | 现有配置文件保持不变 |

### 1.3 新增目录结构

```
solo-windows-ai-agent/
├── pyproject.toml                 # [新增] 包配置
├── src/
│   ├── solo/                      # [新增] v0.1.1 主包
│   │   ├── __init__.py
│   │   ├── core/                  # Lite 核心
│   │   │   ├── __init__.py
│   │   │   ├── mode.py
│   │   │   ├── enums.py
│   │   │   ├── state_machine.py
│   │   │   ├── risk.py
│   │   │   ├── policy.py
│   │   │   ├── task_store.py
│   │   │   ├── approvals.py
│   │   │   ├── evidence.py
│   │   │   ├── schemas.py
│   │   │   └── validator.py
│   │   ├── demo/                  # Demo 管道
│   │   │   ├── __init__.py
│   │   │   ├── safe_demo.py
│   │   │   └── veto_demo.py
│   │   └── cli/                   # CLI 入口
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── doctor.py
│   │       ├── demo.py
│   │       ├── test_cmd.py
│   │       └── cleanup.py
│   ├── orchestrator/              # [不变] 现有编排器
│   └── paios/                     # [不变] 现有 PAIOS
├── tests/                         # [扩展] 测试
│   ├── test_core_state_machine.py
│   ├── test_core_risk.py
│   ├── test_core_policy.py
│   ├── test_core_task_store.py
│   ├── test_core_approvals.py
│   ├── test_demo_safe.py
│   ├── test_demo_veto.py
│   └── test_cli.py
└── docs/
    └── internal/                  # [新增] ADR 文档
        ├── ADR_001_LIGHTWEIGHT_MODES.md
        ├── ADR_002_PACKAGING_AND_CLI.md
        ├── ADR_003_REAL_DEMO_PIPELINE.md
        └── V011_IMPLEMENTATION_PLAN.md
```

---

## 2. 实施步骤

### Phase 1: 基础设施 (预估 2 小时)

#### Step 1.1: pyproject.toml 和包骨架

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** 无 |
| **输入：** ADR 002 中的 pyproject.toml 模板 |
| **动作：** |
| 1. 创建 `pyproject.toml`，配置 `hatchling` 构建系统 |
| 2. 定义 `dependencies`（click, pydantic） |
| 3. 定义 `[project.optional-dependencies]` 分层（core, dev） |
| 4. 注册 `[project.scripts]` 入口点 `solo = solo.cli.main:cli` |
| 5. 配置 `[tool.pytest]`, `[tool.ruff]`, `[tool.mypy]` |
| 6. 创建 `src/solo/__init__.py` 含版本号 `__version__ = "0.1.1a0"` |
| **预期输出：** `pyproject.toml`, `src/solo/__init__.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `python -c "import solo; print(solo.__version__)"` 输出 `0.1.1a0` |

#### Step 1.2: 核心枚举和模式检测

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 1.1 |
| **输入：** `src/paios/paios/enums.py` (已存在), ADR 001 模式定义 |
| **动作：** |
| 1. 创建 `src/solo/core/enums.py` — 从现有 `enums.py` 提取 `TaskState`, `RiskLevel`, `ApprovalState`, `ApprovalDecision`, `ValidationStatus` |
| 2. 新增 `PipelineState` 枚举（RECEIVED→...→COMPLETED，见 ADR 003） |
| 3. 创建 `src/solo/core/mode.py` — `DeploymentMode` 枚举 + `detect_mode()` 函数 |
| 4. 实现模式降级逻辑：Core→Lite 自动降级 |
| **预期输出：** `src/solo/core/enums.py`, `src/solo/core/mode.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `from solo.core.enums import TaskState, RiskLevel` 无报错；`from solo.core.mode import detect_mode; print(detect_mode())` 输出 `lite` |

### Phase 2: 核心模块迁移/桥接 (预估 3 小时)

#### Step 2.1: 状态机

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 1.2 |
| **输入：** `src/paios/paios/state_machine.py` (已存在), ADR 003 状态转换规则 |
| **动作：** |
| 1. 创建 `src/solo/core/state_machine.py` |
| 2. 实现 ADR 003 定义的 `ALLOWED_TRANSITIONS`（RECEIVED→TRIAGED→PLANNING→APPROVED→DISPATCHED→EXECUTING→VALIDATING→COMPLETED） |
| 3. 实现 `can_transition()`, `require_transition()`, `InvalidTransition` 异常 |
| 4. 注意：这与现有 `state_machine.py` 的转换集不同（旧版是 CREATED→PREFLIGHT→...），需完全按 ADR 003 设计实现 |
| **预期输出：** `src/solo/core/state_machine.py` |
| **预估时间：** 20 分钟 |
| **完成标准：** `can_transition("RECEIVED", "TRIAGED") == True`, `can_transition("REJECTED", "DISPATCHED") == False` |

#### Step 2.2: 风险评估和策略引擎

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 1.2 |
| **输入：** `src/paios/paios/risk.py` (已存在), `src/paios/paios/policy.py` (已存在) |
| **动作：** |
| 1. 创建 `src/solo/core/risk.py`，包含 `RiskClassifier` 类，复用现有 R3_TERMS / R2_TERMS / R1_TERMS 关键词表 |
| 2. 创建 `src/solo/core/policy.py`，包含 `PolicyEngine` 类，复用 R0/R1 auto-pass, R2 task-approval, R3 step-approval 策略 |
| 3. 修复现有 `PolicyEngine.evaluate()` 中的 `requester` vs `owner_id` 比较（当前代码 `requester != owner_id` → 直接拒绝，这在单用户场景下不适用） |
| 4. 添加类型注解 |
| **预期输出：** `src/solo/core/risk.py`, `src/solo/core/policy.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `RiskClassifier().classify("delete important file", "file_operation").level == RiskLevel.R3` |

#### Step 2.3: TaskStore (SQLite)

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 2.1 |
| **输入：** `src/orchestrator/openclaw_night_workflow/task_store.py` (已存在) |
| **动作：** |
| 1. 创建 `src/solo/core/task_store.py`，基于现有 `TaskStore` |
| 2. 精简 DDL：Lite 模式只需要核心表 — `workflow_runs`, `workflow_events`, `execution_attempts`, `validation_runs`, `approvals` |
| 3. 去掉 Lite 不需要的表：`phase_runs`, `artifacts`, `notifications`, `locks`, `health_snapshots`, `rollback_events` |
| 4. 保持 `create_workflow_run()`, `get_run()`, `transition_run()`, `append_event()`, `record_execution_attempt()`, `record_validation()` |
| 5. 添加 `close()` 上下文管理器支持 (`__enter__` / `__exit__`) |
| **预期输出：** `src/solo/core/task_store.py` |
| **预估时间：** 45 分钟 |
| **完成标准：** 创建 TaskStore、调用 `migrate()`、`create_workflow_run()` 返回有效 `run_id` |

#### Step 2.4: 审批引擎和证据模块

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 2.3 |
| **输入：** `src/orchestrator/openclaw_night_workflow/approvals.py`, `src/orchestrator/openclaw_night_workflow/evidence.py` (已存在) |
| **动作：** |
| 1. 创建 `src/solo/core/approvals.py` — 复用 `create_approval()` 和 `resolve_approval()` |
| 2. 创建 `src/solo/core/evidence.py` — 复用 `sha256_file()` 和 `export_file_manifest()` |
| 3. 创建 `src/solo/core/schemas.py` — `ValidationResult` 数据类 + `utc_now()` |
| 4. 创建 `src/solo/core/validator.py` — 暴露 `validate_phase()` 接口（精简版，Lite 模式验证） |
| **预期输出：** `src/solo/core/approvals.py`, `src/solo/core/evidence.py`, `src/solo/core/schemas.py`, `src/solo/core/validator.py` |
| **预估时间：** 45 分钟 |
| **完成标准：** `create_approval()` 返回 `{action_id, nonce, expires_at}`; `resolve_approval(action_id, nonce, approve=False)` 返回 `True` |

### Phase 3: Demo 管道 (预估 3 小时)

#### Step 3.1: Safe Demo

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 2.1, 2.2, 2.3, 2.4 |
| **输入：** ADR 003 Safe Demo 设计 |
| **动作：** |
| 1. 创建 `src/solo/demo/__init__.py` |
| 2. 创建 `src/solo/demo/safe_demo.py` |
| 3. 实现 `run_safe_demo(workspace: Path) -> SafeDemoResult` |
| 4. 8 步管道：RECEIVED → TRIAGED (R0) → PLANNING → APPROVED → DISPATCHED → EXECUTING → VALIDATING → COMPLETED |
| 5. 每步调用真实核心模块（TaskStore, RiskClassifier, PolicyEngine, Approval, Evidence, Validator） |
| 6. 真实文件操作：创建 sample_text.txt、统计单词、计算 SHA256、写入审计记录 |
| 7. 返回结构化结果 `SafeDemoResult` 包含 pipeline 事件列表 |
| **预期输出：** `src/solo/demo/__init__.py`, `src/solo/demo/safe_demo.py` |
| **预估时间：** 1.5 小时 |
| **完成标准：** `run_safe_demo(tmp_path)` 返回的 `SafeDemoResult.pipeline[-1].state == "COMPLETED"` |

#### Step 3.2: VETO Demo

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 3.1 |
| **输入：** ADR 003 VETO Demo 设计 |
| **动作：** |
| 1. 创建 `src/solo/demo/veto_demo.py` |
| 2. 实现 `run_veto_demo(workspace: Path) -> VetoDemoResult` |
| 3. 4 步管道：RECEIVED → TRIAGED (R3) → REVIEW_PENDING → REJECTED |
| 4. 触发 R3 分类：请求 "Delete all files in the important project directory" |
| 5. 调用 `create_approval()` → `resolve_approval(approve=False)` |
| 6. 验证 6 项安全保证：R3 分类正确、需要审批、审批被拒绝、终态不可逃逸、无执行记录、nonce 已消费 |
| 7. 返回 `VetoDemoResult` 包含 `security_guarantees` 字典 |
| **预期输出：** `src/solo/demo/veto_demo.py` |
| **预估时间：** 1 小时 |
| **完成标准：** `run_veto_demo(tmp_path).vetoed == True`, 所有 `security_guarantees` 值均为 `True` |

#### Step 3.3: Demo 输出格式化

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 3.1, 3.2 |
| **输入：** ADR 002 输出模式设计 |
| **动作：** |
| 1. 在 `src/solo/demo/` 下创建或添加 `formatter.py` |
| 2. 实现 `format_demo_human(result: DemoResult) -> str` — 彩色终端输出 (使用 ANSI 转义码, 不依赖 rich) |
| 3. 实现 `format_demo_json(result: DemoResult) -> str` — JSON 序列化 |
| 4. Safe Demo 格式：8 步带 ✅/🚨 图标 |
| 5. VETO Demo 格式：4 步 + 安全保证验证表格 |
| **预期输出：** `src/solo/demo/formatter.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** 终端输出与 ADR 002/003 规范一致 |

### Phase 4: CLI 入口 (预估 2 小时)

#### Step 4.1: CLI 主入口

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 1.1 |
| **输入：** ADR 002 CLI 命令树 |
| **动作：** |
| 1. 创建 `src/solo/cli/__init__.py`, `src/solo/cli/main.py` |
| 2. 使用 `click` 创建 `@click.group()` 主入口 `cli` |
| 3. 添加 `--json` 全局 flag（切换输出模式） |
| 4. 添加 `--workspace` 全局选项（自定义工作目录） |
| 5. 注册子命令组：`doctor`, `demo`, `test`, `cleanup` |
| 6. 添加 `version` 命令（输出版本 + 模式） |
| **预期输出：** `src/solo/cli/__init__.py`, `src/solo/cli/main.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `solo --help` 显示完整命令树；`solo version` 输出 `0.1.1a0 (lite)` |

#### Step 4.2: doctor 命令

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 4.1 |
| **输入：** ADR 002 doctor 规范 + 现有 `scripts/doctor.ps1` |
| **动作：** |
| 1. 创建 `src/solo/cli/doctor.py` |
| 2. 实现检查：Python 版本、磁盘空间、文件系统权限、Git、Node.js、Docker、API Key |
| 3. 人类输出模式：✅/⚠️ 图标 + 彩色输出 |
| 4. JSON 模式：`{"checks": [...], "summary": {"pass": N, "fail": N, "warn": N}}` |
| 5. 自动检测运行模式 (Lite/Core/Full) |
| **预期输出：** `src/solo/cli/doctor.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `solo doctor` 在 Lite 环境输出 >= 4 pass 且 node/docker 为 warn |

#### Step 4.3: demo 命令组

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 3.1, 3.2, 4.1 |
| **输入：** ADR 002 demo 命令规范 |
| **动作：** |
| 1. 创建 `src/solo/cli/demo.py` |
| 2. 使用 `@cli.group()` 创建 `demo` 子命令组 |
| 3. 实现 `demo safe` 命令 — 调用 `run_safe_demo()` + 格式化输出 |
| 4. 实现 `demo veto` 命令 — 调用 `run_veto_demo()` + 格式化输出 |
| 5. `--workspace` 选项覆盖默认临时目录 |
| 6. `--json` flag 切换 JSON 输出 |
| 7. 临时工作空间自动创建，全路径打印 |
| **预期输出：** `src/solo/cli/demo.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `solo demo safe` 成功运行并打印管道步骤 |

#### Step 4.4: test 和 cleanup 命令

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 4.1 |
| **输入：** ADR 002 test/cleanup 规范 |
| **动作：** |
| 1. 创建 `src/solo/cli/test_cmd.py` — `solo test` 调用 pytest |
| 2. `--unit` / `--integration` / `--coverage` 选项 |
| 3. 创建 `src/solo/cli/cleanup.py` — `solo cleanup` |
| 4. 扫描 `$TEMP/solo-demo-*` 目录 |
| 5. `--all` flag 清理所有包括测试数据库 |
| 6. `--yes` / `--force` flag 跳过确认提示 |
| **预期输出：** `src/solo/cli/test_cmd.py`, `src/solo/cli/cleanup.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `solo cleanup` 清理临时目录；`solo test --unit` 运行单元测试 |

### Phase 5: 测试 (预估 2 小时)

#### Step 5.1: 核心模块单元测试

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Phase 2 全部 |
| **输入：** `tests/test_core.py` (已存在但需扩展) |
| **动作：** |
| 1. `test_core_state_machine.py` — 测试所有合法/非法转换 |
| 2. `test_core_risk.py` — 测试 R0/R1/R2/R3 分类 + `requested` 覆盖 |
| 3. `test_core_policy.py` — 测试 R0 auto-pass, R2 approval, R3 step-approval |
| 4. `test_core_task_store.py` — 测试 CRUD + 状态转换持久化 + idempotency |
| 5. `test_core_approvals.py` — 测试 create → approve → reject → expire → nonce 验证 |
| **预期输出：** `tests/test_core_*.py` (5 个测试文件) |
| **预估时间：** 1 小时 |
| **完成标准：** `pytest tests/test_core_*.py -v` 全部通过 (> 40 个测试用例) |

#### Step 5.2: Demo 集成测试

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 3.1, 3.2 |
| **输入：** ADR 003 demo 设计 |
| **动作：** |
| 1. `test_demo_safe.py` — 验证 Safe Demo 完整管道：8 步全部通过、word_count 正确、文件存在 |
| 2. `test_demo_veto.py` — 验证 VETO Demo：R3 拒绝、6 项安全保证、无执行记录 |
| 3. 每个测试使用 `tmp_path` fixture 隔离工作空间 |
| 4. `solo demo safe` + `solo demo veto` 作为冒烟测试 |
| **预期输出：** `tests/test_demo_safe.py`, `tests/test_demo_veto.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `pytest tests/test_demo_*.py -v` 全部通过 |

#### Step 5.3: CLI 测试

| 字段 | 值 |
|------|-----|
| **执行部门：** 工部 |
| **依赖步骤：** Step 4.1-4.4 |
| **输入：** Click 的 `CliRunner` 测试工具 |
| **动作：** |
| 1. `test_cli.py` — 使用 `click.testing.CliRunner` 测试所有命令 |
| 2. 测试 `solo --help` 返回 0 |
| 3. 测试 `solo doctor --json` 输出有效 JSON |
| 4. 测试 `solo demo safe --json` 返回 COMPLETED |
| 5. 测试 `solo demo veto --json` 返回 REJECTED |
| 6. 测试 `solo version` 输出版本字符串 |
| **预期输出：** `tests/test_cli.py` |
| **预估时间：** 30 分钟 |
| **完成标准：** `pytest tests/test_cli.py -v` 全部通过 |

---

## 3. 依赖关系图

```
Phase 1: 基础设施
  Step 1.1 (pyproject.toml)
    └→ Step 1.2 (enums + mode)
          ├→ Step 2.1 (state_machine)
          │     └→ Step 2.3 (task_store)
          │           └→ Step 2.4 (approvals + evidence)
          ├→ Step 2.2 (risk + policy)
          └→ Step 4.1 (CLI main)
                ├→ Step 4.2 (doctor)
                ├→ Step 4.3 (demo commands)
                │     ↑ (need Phase 3 complete)
                ├→ Step 4.4 (test + cleanup)
                      ↑
Phase 3: Demo 管道
  Step 3.1 (safe_demo)
    └→ Step 3.2 (veto_demo)
          └→ Step 3.3 (formatter)
                ↑ (depends on Phase 2 complete)

Phase 5: 测试 (依赖 Phase 2-4 完成)
  Step 5.1 (core unit tests)
  Step 5.2 (demo integration tests)
  Step 5.3 (CLI tests)
  → 可并行执行
```

**并行机会：**
- Phase 2.1 + 2.2 可并行（各自独立）
- Phase 5.1, 5.2, 5.3 可并行
- Phase 4.2 和 Phase 4.4 可并行

---

## 4. 风险与注意事项

| 风险 | 影响 | 概率 | 应对方案 |
|------|------|------|---------|
| `RiskClassifier` 关键词变化导致 VETO Demo 失效 | 中 | 低 | 在测试中锁定预期的关键词；VETO Demo 注释标记预期 R3 触发词 |
| 状态机新旧两套转换规则混淆 | 高 | 中 | 新状态机放在 `solo.core.state_machine`，与旧 `paios/state_machine.py` 完全隔离 |
| SQLite 线程安全 (多测试并发) | 中 | 中 | 每个测试使用独立 `tmp_path/demo.db`；设置 `check_same_thread=False` |
| Windows 路径编码问题 (GBK vs UTF-8) | 中 | 高 | CLI 入口强制 `sys.stdout.reconfigure(encoding='utf-8')` |
| 现有代码导入冲突 | 低 | 低 | v0.1.1 新代码完全在 `src/solo/` 下，不修改 `src/orchestrator/` 和 `src/paios/` |
| `pip install` 在 Windows 上权限问题 | 低 | 中 | 文档中推荐 `pip install --user solo-agent` |
| Demo 执行速度慢 | 低 | 低 | Safe Demo 目标 < 1 秒，VETO Demo < 0.5 秒 |

---

## 5. 完成标准

### 5.1 必须达成 (P0)

- [ ] `pyproject.toml` 存在且 `pip install -e .` 成功
- [ ] `solo --help` 显示完整命令树
- [ ] `solo doctor` 检测环境并返回模式
- [ ] `solo demo safe` 成功运行 8 步管道，调用真实核心模块
- [ ] `solo demo veto` 成功运行 4 步管道，验证 6 项安全保证
- [ ] `solo demo safe --json` 输出有效 JSON
- [ ] `solo cleanup` 清理临时工作空间
- [ ] 所有单元测试通过 (`pytest tests/ -v -m "lite"`)
- [ ] Lite 模式下 `python -c "import solo.core"` 不触发任何外部导入

### 5.2 应该达成 (P1)

- [ ] `solo test --unit` 运行单元测试套件
- [ ] `solo version` 显示版本号和部署模式
- [ ] Demo 管道时长 < 1 秒
- [ ] 所有测试通过率 100%
- [ ] 代码覆盖率 > 85% (核心模块)

### 5.3 最好达成 (P2)

- [ ] Core 模式 `solo doctor` 检测 Playwright/Node.js
- [ ] 彩色终端输出正确渲染（不依赖 rich）
- [ ] `README.md` 添加 Quick Start 章节 (`pip install` + `solo demo safe`)

---

## 6. 验收测试

```bash
# 1. 安装
pip install -e .

# 2. 版本检查
solo version
# 预期: solo-agent v0.1.1a0 (lite)

# 3. 环境检查
solo doctor
# 预期: >= 4 pass, 0 fail

# 4. Safe Demo
solo demo safe
# 预期: RECEIVED→TRIAGED→PLANNING→APPROVED→DISPATCHED→EXECUTING→VALIDATING→COMPLETED
#       exit code 0

# 5. VETO Demo
solo demo veto
# 预期: RECEIVED→TRIAGED(R3)→REVIEW_PENDING→REJECTED
#       6 security guarantees all ✅
#       exit code 0

# 6. JSON 输出
solo demo safe --json | python -m json.tool
# 预期: 有效 JSON, status=PASS

# 7. 清理
solo cleanup --all --yes
# 预期: exit code 0

# 8. 单元测试
solo test --unit
# 预期: 全部通过

# 9. Lite 模式验证
python -c "
import solo.core.mode as m
assert m.detect_mode() == m.DeploymentMode.LITE
print('Lite mode OK')
"
```

---

## 7. 参考

- [ADR 001: Lite/Core/Full 三层模式](ADR_001_LIGHTWEIGHT_MODES.md)
- [ADR 002: 打包与 CLI 设计](ADR_002_PACKAGING_AND_CLI.md)
- [ADR 003: 真实 Demo 管道设计](ADR_003_REAL_DEMO_PIPELINE.md)
- `docs/ARCHITECTURE.md` — 现有系统架构
- `docs/DEVELOPMENT.md` — 开发指南
- `scripts/start_demo.ps1` — 现有 demo 脚本
- `scripts/doctor.ps1` — 现有 doctor 脚本
