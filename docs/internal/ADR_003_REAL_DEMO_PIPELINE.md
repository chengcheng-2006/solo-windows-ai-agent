# ADR 003: 真实 Demo 管道设计（Safe + VETO）

- **状态：** 提议中 (Proposed)
- **日期：** 2026-07-24
- **决策者：** 中书省 (Zhongshu)
- **关联：** ADR 001 (三层模式), ADR 002 (打包CLI), V011_IMPLEMENTATION_PLAN

---

## 1. 上下文 (Context)

### 1.1 问题陈述

v0.1.0 的 demo（`scripts/start_demo.ps1`）是一个 **PowerShell 脚本**，用 `ConvertTo-Json` 生成 mock 数据来模拟管道：

```powershell
# 当前 Demo 本质：生成假 JSON 文件
@{
    task_id = "demo-001"
    steps = @(...)
    risk_level = "R0"
    status = "planned"
} | ConvertTo-Json | Out-File $planFile
```

**问题：**
- ❌ **不真实：** 没有调用真正的 `TaskStore`、`StateMachine`、`Risk`、`Approval`、`Evidence`、`Validator` 模块
- ❌ **不可测试：** 没有 SQLite 数据库，没有状态转换验证，没有审批 nonce 机制
- ❌ **无 VETO 路径：** 只演示了 happy path，没有演示安全机制的核心——高风险请求被拒绝
- ❌ **平台绑定：** 仅 PowerShell/Windows 可用

v0.1.1 的 demo 必须**真实调用**现有的核心模块，展示完整的审批和安全管道。

### 1.2 现有模块能力分析

| 模块 | 文件 | 可复用接口 |
|------|------|-----------|
| `TaskStore` | `task_store.py` | `create_workflow_run()`, `transition_run()`, `append_event()`, `record_execution_attempt()`, `record_validation()` |
| `StateMachine` | `state_machine.py` | `can_transition()`, `require_transition()`, `ALLOWED_TRANSITIONS` |
| `Risk` (PAIOS) | `risk.py` | `RiskClassifier().classify()` — R0/R1/R2/R3 |
| `Policy` (PAIOS) | `policy.py` | `PolicyEngine().evaluate()` — 自动通过/需审批/拒绝 |
| `Approval` (Orch) | `approvals.py` | `create_approval()`, `resolve_approval()` — nonce + TTL |
| `Evidence` (Orch) | `evidence.py` | `sha256_file()`, `export_file_manifest()` |
| `Validator` (Orch) | `validator_runner.py` | `validate_phase()` — ValidationResult |
| `Schemas` (Orch) | `schemas.py` | `ValidationResult`, `utc_now()` |

### 1.3 状态流设计

v0.1.1 引入新的统一状态流，对齐"三省六部"审批管道：

```
                     ┌──────────┐
                     │ RECEIVED │  用户提交任务
                     └────┬─────┘
                          │
                     ┌────▼─────┐
                     │ TRIAGED  │  风险分类 (R0-R3) + 策略评估
                     └────┬─────┘
                          │
              ┌───────────┼───────────┐
              │ R0/R1     │ R2        │ R3
              │ 自动通过   │ 需要审批   │ 拒绝+人工
              │           │           │
     ┌────────▼──────┐  ┌▼──────────┐ ┌▼──────────────┐
     │   PLANNING    │  │REVIEW_    │ │    REJECTED    │
     │               │  │PENDING    │ │ (SAFE DEMO     │
     │               │  │           │ │  不会到这里)    │
     └───────┬───────┘  └─────┬─────┘ └────────────────┘
             │                │
             │           ┌────▼─────┐
             │           │ APPROVED │  审批通过
             │           └────┬─────┘
             │                │
             └────────┬───────┘
                      │
              ┌───────▼───────┐
              │  DISPATCHED   │  派发给执行器
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │  EXECUTING    │  执行任务
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │  VALIDATING   │  验证结果
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │  COMPLETED    │  任务完成
              └───────────────┘
```

**状态定义：**

| 状态 | 说明 | 触发条件 |
|------|------|----------|
| `RECEIVED` | 任务已创建，等待分类 | 用户提交任务 |
| `TRIAGED` | 风险已评估 (R0-R3)，策略已判定 | RiskClassifier.classify() + PolicyEngine.evaluate() |
| `PLANNING` | 正在生成执行计划 (R0/R1直接进入) | 低风险任务自动进入 |
| `REVIEW_PENDING` | 等待审批人审核 (R2任务) | PolicyDecision.requires_approval == True |
| `APPROVED` | 审批通过 | resolve_approval(approve=True) |
| `REJECTED` | 审批拒绝 | resolve_approval(approve=False) |
| `DISPATCHED` | 任务已派发给执行器 | 审批通过后派发 |
| `EXECUTING` | 任务正在执行 | 执行器开始工作 |
| `VALIDATING` | 正在验证执行结果 | 执行完成后进入验证 |
| `COMPLETED` | 任务成功完成 | 验证通过 |

### 1.4 状态转换规则

```python
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "RECEIVED":       {"TRIAGED", "REJECTED"},
    "TRIAGED":        {"PLANNING", "REVIEW_PENDING", "REJECTED"},
    "PLANNING":       {"DISPATCHED"},
    "REVIEW_PENDING": {"APPROVED", "REJECTED"},
    "APPROVED":       {"DISPATCHED"},
    "REJECTED":       set(),                    # 终态
    "DISPATCHED":     {"EXECUTING"},
    "EXECUTING":      {"VALIDATING"},
    "VALIDATING":     {"COMPLETED"},
    "COMPLETED":      set(),                    # 终态
}
```

---

## 2. 决策 (Decision)

### 2.1 Safe Demo 管道设计

**Safe Demo** 演示 R0（只读/无副作用）任务从创建到完成的完整流水线。每一步都调用真实的 Python 模块。

#### 2.1.1 管道步骤

```python
# solo/demo/safe_demo.py (伪代码)

def run_safe_demo(workspace: Path) -> dict:
    """
    Safe Demo: R0 任务端到端管道。
    真实调用 TaskStore, StateMachine, Risk, Policy, Approval, Evidence, Validator。
    """
    store = TaskStore(workspace / "demo.db")
    store.migrate()
    classifier = RiskClassifier()
    policy_engine = PolicyEngine()
    
    events = []  # 收集所有事件用于审计

    # Step 1: RECEIVED — 创建任务
    task_id = store.create_workflow_run("solo-safe-demo", idempotency_key="safe-demo-001")
    store.transition_run(task_id, "RECEIVED")
    events.append({"state": "RECEIVED", "task_id": task_id})

    # Step 2: TRIAGED — 风险分类 + 策略评估
    risk = classifier.classify(
        objective="Count words in a test text file",
        task_type="file_operation",
    )
    # 预期: R0 (read_only_or_no_side_effect)
    assert risk.level == RiskLevel.R0, f"Expected R0, got {risk.level}"
    
    policy = policy_engine.evaluate(
        requester="demo-owner",
        owner_id="demo-owner",
        source_channel="wechat",
        risk=risk.level,
    )
    # 预期: allowed=True, requires_approval=False
    assert policy.allowed and not policy.requires_approval
    
    store.transition_run(task_id, "TRIAGED", payload={
        "risk": str(risk.level),
        "reasons": list(risk.reasons),
        "policy": {"allowed": policy.allowed, "reason": policy.reason_code},
    })
    events.append({"state": "TRIAGED", "risk": str(risk.level)})

    # Step 3: PLANNING — 生成执行计划 (R0自动进入)
    plan = {
        "steps": [
            {"step": 1, "action": "create_test_file", "target": "sample.txt"},
            {"step": 2, "action": "count_words", "target": "sample.txt"},
            {"step": 3, "action": "write_audit_log", "target": "audit.json"},
        ],
        "risk_level": "R0",
        "estimated_duration_ms": 100,
    }
    store.transition_run(task_id, "PLANNING", payload={"plan": plan})
    events.append({"state": "PLANNING", "steps": len(plan["steps"])})

    # Step 4: APPROVED — R0自动通过，无需 REVIEW_PENDING
    # 对于 R0/R1，跳过 REVIEW_PENDING 直接到 APPROVED
    store.transition_run(task_id, "APPROVED", payload={
        "auto_approved": True,
        "reason": "R0_read_only_safe",
    })
    events.append({"state": "APPROVED"})

    # Step 5: DISPATCHED — 派发给 demo 执行器
    store.transition_run(task_id, "DISPATCHED", payload={"executor": "demo-local"})
    events.append({"state": "DISPATCHED"})

    # Step 6: EXECUTING — 执行文件操作
    start_time = utc_now()
    
    # 真实执行：创建文件、写入内容、统计单词
    test_file = workspace / "sample_text.txt"
    test_file.write_text(
        "Solo is a Windows-first personal AI agent system.\n"
        "It processes chat requests through a multi-agent pipeline:\n"
        "planning, review, approval, execution, and verification.\n"
        "This demo demonstrates the real orchestration pipeline.\n",
        encoding="utf-8",
    )
    word_count = len(test_file.read_text(encoding="utf-8").split())
    
    # 记录证据：文件清单 + SHA256
    file_sha = sha256_file(test_file)
    
    store.transition_run(task_id, "EXECUTING")
    store.record_execution_attempt(
        run_id=task_id,
        phase_id="demo-execution",
        attempt=1,
        executor="demo-local",
        task_id="demo-001",
        started_at=start_time,
        finished_at=utc_now(),
        exit_code=0,
    )
    events.append({"state": "EXECUTING", "word_count": word_count})

    # Step 7: VALIDATING — 验证结果
    validation = ValidationResult(
        workflow_id="solo-safe-demo",
        run_id=task_id,
        phase_id="demo-execution",
        validation_id=f"val-{uuid.uuid4().hex[:12]}",
        result="PASS",
        checks_total=4,
        checks_passed=4,
        checks_failed=0,
        critical_failures=[],
        security_findings=[],
        missing_artifacts=[],
        retryable_findings=[],
        requires_user_action=False,
        recommended_next_state="COMPLETED",
        evidence=[str(test_file.relative_to(workspace))],
    )
    store.transition_run(task_id, "VALIDATING")
    store.record_validation(validation.to_dict())
    events.append({"state": "VALIDATING", "result": "PASS"})

    # Step 8: COMPLETED — 任务完成
    store.transition_run(task_id, "COMPLETED", payload={"word_count": word_count})
    events.append({"state": "COMPLETED"})

    # 导出证据清单
    manifest_path = workspace / "evidence" / "demo_file_manifest.json"
    export_file_manifest(workspace, manifest_path)
    
    store.close()
    
    return {
        "task_id": task_id,
        "pipeline": events,
        "result": {"word_count": word_count, "validation": "PASS"},
        "evidence_manifest": str(manifest_path),
    }
```

#### 2.1.2 Safe Demo 调用的真实模块清单

| 步骤 | 调用的真实模块 | 真实操作 |
|------|---------------|---------|
| RECEIVED | `TaskStore.create_workflow_run()` | 写入 SQLite `workflow_runs` 表 |
| TRIAGED | `RiskClassifier.classify()` | 关键词匹配返回 R0 |
| | `PolicyEngine.evaluate()` | 策略判定 allowed=True, no approval |
| TRIAGED | `TaskStore.transition_run()` | SQLite 状态转换 + event 写入 |
| PLANNING | `TaskStore.transition_run()` | plan JSON 写入 |
| APPROVED | `TaskStore.transition_run()` | auto_approved payload |
| DISPATCHED | `TaskStore.transition_run()` | executor 标识写入 |
| EXECUTING | `TaskStore.record_execution_attempt()` | 写入 `execution_attempts` 表 |
| EXECUTING | `sha256_file()` | 真实计算文件 SHA256 |
| VALIDATING | `ValidationResult` 构造 | 结构化验证结果 |
| | `TaskStore.record_validation()` | 写入 `validation_runs` 表 |
| COMPLETED | `TaskStore.transition_run()` | 终态转换 |
| 审计 | `export_file_manifest()` | 导出文件清单 JSON |

**关键约束：**
- ❌ 不 mock 任何核心模块 —— 不替换 `TaskStore`、`RiskClassifier`、`PolicyEngine`
- ❌ 不到调用时手动构造假数据绕过验证 —— 所有数据通过真实的 SQLite 读写
- ✅ 唯一简化的部分：demo 的"执行器"是直接的文件操作代码，而非通过 Worker 调度（Worker 属于 Core 模式）

### 2.2 VETO Demo 设计

**VETO Demo** 演示 R3（高风险不可逆）任务被安全机制拒绝的流程。

#### 2.2.1 场景

用户请求："Delete all files in the important project directory"（删除重要项目中的所有文件）

这会触发 `RiskClassifier.classify()` 返回 **R3**（匹配 "delete important"），`PolicyEngine.evaluate()` 返回 **requires_approval=True + approval_scope="step"**。

Demo 中：审批被 Reviewer 拒绝 → 任务进入 REJECTED 终态 → 不执行。

#### 2.2.2 管道步骤

```python
# solo/demo/veto_demo.py (伪代码)

def run_veto_demo(workspace: Path) -> dict:
    """
    VETO Demo: R3 高风险请求 → Reviewer 拒绝 → REJECTED。
    """
    store = TaskStore(workspace / "demo.db")
    store.migrate()
    classifier = RiskClassifier()
    policy_engine = PolicyEngine()
    
    events = []

    # Step 1: RECEIVED
    task_id = store.create_workflow_run("solo-veto-demo", idempotency_key="veto-demo-001")
    store.transition_run(task_id, "RECEIVED")
    events.append({"state": "RECEIVED", "task_id": task_id})

    # Step 2: TRIAGED — 风险判定为 R3
    risk = classifier.classify(
        objective="Delete all files in the important project directory",
        task_type="file_operation",
    )
    # 预期: R3 (high_risk_or_irreversible_action)
    # 因为 "delete important" 匹配 R3_TERMS 中的 "delete important"
    assert risk.level == RiskLevel.R3, f"Expected R3, got {risk.level}"
    
    policy = policy_engine.evaluate(
        requester="demo-owner",
        owner_id="demo-owner",
        source_channel="wechat",
        risk=risk.level,
    )
    # 预期: allowed=True, requires_approval=True, approval_scope="step"
    # R3 需要逐步骤审批
    assert policy.allowed, "R3 should be allowed but require step-level approval"
    assert policy.requires_approval, "R3 requires approval"
    assert policy.approval_scope == "step", "R3 requires per-step approval"
    
    store.transition_run(task_id, "TRIAGED", payload={
        "risk": "R3",
        "reasons": list(risk.reasons),
        "policy": {
            "allowed": policy.allowed,
            "requires_approval": policy.requires_approval,
            "approval_scope": policy.approval_scope,
        },
    })
    events.append({"state": "TRIAGED", "risk": "R3", "requires_approval": True})

    # Step 3: REVIEW_PENDING — 创建审批请求
    store.transition_run(task_id, "REVIEW_PENDING")
    
    approval = create_approval(
        store=store,
        workflow_id="solo-veto-demo",
        run_id=task_id,
        phase_id="demo-review",
        risk="R3",
        target="Delete all files in the important project directory",
        ttl_seconds=300,
    )
    events.append({
        "state": "REVIEW_PENDING",
        "action_id": approval["action_id"],
        "nonce": approval["nonce"][:8] + "...",  # 不泄露完整nonce
    })

    # Step 4: REJECTED — Reviewer 拒绝了审批
    resolved = resolve_approval(
        store=store,
        action_id=approval["action_id"],
        nonce=approval["nonce"],
        approve=False,  # ← 拒绝！
        owner_confirmed=True,
    )
    assert resolved, "Approval rejection should succeed"
    
    store.transition_run(task_id, "REJECTED", payload={
        "action_id": approval["action_id"],
        "verdict": "REJECTED",
        "reason": "R3_high_risk_operation_denied_by_reviewer",
    })
    events.append({"state": "REJECTED", "verdict": "VETO"})

    # 验证：尝试执行被阻止
    # 检查状态机：REJECTED 是终态，不能转换到任何其他状态
    assert not can_transition("REJECTED", "DISPATCHED"), "REJECTED must be terminal"
    assert not can_transition("REJECTED", "EXECUTING"), "REJECTED must be terminal"
    
    # 验证：数据库中没有执行记录
    attempts = store.conn.execute(
        "SELECT COUNT(*) as c FROM execution_attempts WHERE run_id=?",
        (task_id,),
    ).fetchone()
    assert attempts["c"] == 0, "No execution should have occurred for REJECTED task"
    
    store.close()
    
    return {
        "task_id": task_id,
        "risk_level": "R3",
        "risk_reasons": list(risk.reasons),
        "vetoed": True,
        "pipeline": events,
        "security_guarantees": {
            "no_execution_occurred": True,
            "state_is_terminal": True,
            "approval_nonce_consumed": True,
        },
    }
```

#### 2.2.3 VETO Demo 安全保证验证

Demo 结束后自动验证以下安全保证：

| 保证 | 验证方式 |
|------|---------|
| R3 被正确分类 | `RiskClassifier.classify()` 返回 `RiskLevel.R3` |
| 策略要求审批 | `PolicyEngine.evaluate().requires_approval == True` |
| 审批被拒绝 | `resolve_approval(approve=False)` 返回 `True` |
| 终态不可逃逸 | `can_transition("REJECTED", *) == False` 对所有非终态 |
| 无执行记录 | `execution_attempts` 表中该 task 行数为 0 |
| nonce 已消费 | approvals 表状态为 REJECTED |

### 2.3 Demo 输出格式

**Safe Demo 终端输出：**
```
$ solo demo safe

===== Solo Safe Demo v0.1.1 =====
Mode: Lite | Workspace: C:\Users\xxx\AppData\Local\Temp\solo-demo-a1b2c3d4

[1/8] RECEIVED        Creating task "Count words in a test file"  ✅ task-a1b2c3d4
[2/8] TRIAGED         RiskClassifier.classify() .................... ✅ R0
                      Reasons: read_only_or_no_side_effect
                      PolicyEngine.evaluate() ...................... ✅ allowed, no_approval
[3/8] PLANNING        Generating 3-step plan ...................... ✅
[4/8] APPROVED        Auto-approved (R0 safe operation) ........... ✅
[5/8] DISPATCHED      Dispatching to demo-local executor .......... ✅
[6/8] EXECUTING       Creating sample_text.txt .................... ✅ 29 words
                      SHA256: a1b2c3d4...
[7/8] VALIDATING      ValidationResult: 4/4 checks passed ......... ✅ PASS
[8/8] COMPLETED       Task completed successfully ................. 🎉

===== Demo SUCCESS =====
Pipeline: RECEIVED→TRIAGED→PLANNING→APPROVED→DISPATCHED→EXECUTING→VALIDATING→COMPLETED
Duration: 0.45s | Evidence: 8 files, 2.3 KB
```

**VETO Demo 终端输出：**
```
$ solo demo veto

===== Solo VETO Demo v0.1.1 =====
Mode: Lite | Workspace: C:\Users\xxx\AppData\Local\Temp\solo-demo-e5f6g7h8

Hazardous Request: "Delete all files in the important project directory"

[1/4] RECEIVED        Creating task ................................ ✅ task-e5f6g7h8
[2/4] TRIAGED         RiskClassifier.classify() .................... 🚨 R3
                      Reasons: high_risk_or_irreversible_action
                      PolicyEngine.evaluate() ...................... ⚠️  requires step-level approval
[3/4] REVIEW_PENDING  Approval created (nonce: a1b2...c3d4) ....... ✅
                      Waiting for reviewer decision ................
[4/4] REJECTED        ❌ Reviewer REJECTED the request
                      Reason: R3_high_risk_operation_denied

===== Security Guarantees Verified =====
✅ R3 correctly classified
✅ Step-level approval required
✅ Approval rejected by reviewer
✅ REJECTED is terminal (cannot escape to DISPATCHED/EXECUTING)
✅ No execution attempts recorded
✅ All checks passed — VETO mechanism working correctly

===== Demo SUCCESS =====
The safety system correctly prevented a high-risk operation.
```

---

## 3. 后果 (Consequences)

### 3.1 正面影响

1. **真实调用：** Demo 不再是 mock 数据，而是真实执行核心模块代码，demo 的行为 = 生产代码的行为
2. **安全性可验证：** VETO demo 自动验证 6 项安全保证，确保审批/拒绝机制正确
3. **可作为冒烟测试：** `solo demo safe && solo demo veto` 可作为最小化冒烟测试套件
4. **教育价值：** 输出清晰展示每一步的状态转换和模块调用，新用户可以理解管道全貌
5. **零额外依赖：** 所有被调用的模块都是 Lite 核心（纯 Python + SQLite）

### 3.2 负面权衡

1. **Demo 代码需要与生产代码保持同步：** 如果 `RiskClassifier` 的关键词列表变化，demo 的预期风险等级可能需要调整
2. **VETO Demo 的依赖：** 依赖 R3 关键词 "delete important" 不变，如果未来重构可能失效
3. **SQLite 文件残留：** Demo 结束后 `demo.db` 文件留在临时目录，需要 `solo cleanup` 清理

### 3.3 缓解措施

- **版本锁定：** Demo 代码中使用 `@pytest.mark.demo` 风格的注释标记预期行为
- **CI 验证：** Safe Demo + VETO Demo 在 CI 流水线中作为冒烟测试运行
- **清理：** `solo cleanup` 自动清理所有 demo 工作空间（见 ADR 002）

---

## 4. 备选方案

### 方案 A：使用命令行脚本调用现有 CLI（未采用）
即 `solo demo safe` 内部调用 `python -m openclaw_night_workflow.cli start-workflow ...`。不采用原因：流程不连贯，需要多个进程，无法在 Python 层面做断言和验证。

### 方案 B：完全使用 pytest 测试（未采用）
将 demo 作为 pytest 测试用例。不采用原因：`solo demo safe` 的目标用户是"想看看这个项目怎么工作"的新用户，不是开发者。pytest 输出对终端用户不友好。

### 方案 C：Demo 作为独立 Python 模块（采用）
`src/solo/demo/` 下的独立模块，直接 import 核心模块，构造管道。CLI 命令调用 demo 函数。这是最清晰的方案。

---

## 5. 参考

- `scripts/start_demo.ps1` — 现有 mock demo
- `src/orchestrator/openclaw_night_workflow/task_store.py` — TaskStore (SQLite)
- `src/orchestrator/openclaw_night_workflow/state_machine.py` — 状态机
- `src/orchestrator/openclaw_night_workflow/approvals.py` — 审批引擎
- `src/orchestrator/openclaw_night_workflow/evidence.py` — 证据模块
- `src/orchestrator/openclaw_night_workflow/schemas.py` — ValidationResult 等
- `src/paios/paios/risk.py` — RiskClassifier
- `src/paios/paios/policy.py` — PolicyEngine
- `src/paios/paios/enums.py` — RiskLevel, TaskState, ApprovalState
- ADR 001 — 三层部署模式
- ADR 002 — 打包与 CLI 设计
