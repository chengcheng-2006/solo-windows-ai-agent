# Launch Posts and Promotion Materials

> Internal document — draft copy only, **do not auto-publish**.  
> All links use `https://github.com/chengcheng-2006/solo-windows-ai-agent` as placeholder.

---

## 1. GitHub Release

**Title**: Solo v0.1.0-alpha — Initial Public Release

**Body**:

Solo is a Windows-first personal AI system that processes your chat requests through a multi-agent pipeline: plan → review → approve → execute → verify.

This is the first public release. Here's what's included:

### Core Capabilities
- 🤖 Multi-agent orchestration (13 specialized agents with permission controls)
- 🖥️ Windows desktop automation (UIA, OCR, vision models)
- 🌐 Browser automation (CDP, Playwright)
- 💬 WeChat messaging gateway
- 🛡️ Approval-based safety controls
- 📋 Full audit trail
- 🐳 Docker infrastructure (PostgreSQL, NATS, Temporal, Grafana stack)
- 👁️ Computer Use (experimental, vision-based GUI control)

### Try It
```powershell
git clone https://github.com/chengcheng-2006/solo-windows-ai-agent.git
cd solo-windows-ai-agent
cp .env.example .env
# Edit .env with your API keys
.\scripts\doctor.ps1
.\scripts\start.ps1
```

### ⚠️ Alpha Notice
- Tested on author's Windows machine only
- Installation requires experience with dev tools
- Some features need API keys (network calls leave your machine)
- Computer Use (vision-based GUI) is experimental

### What's Next
See ROADMAP.md for planned features: better error handling, simpler setup, cross-machine testing, Telegram gateway, and more.

---

## 2. 中文技术社区发布

**平台**: 知乎、V2EX、少数派、掘金

**标题**: Solo：一个跑在 Windows 上的个人 AI 智能体系统，我把它开源了

**正文**:

一直以来，AI Agent 大多是为 Linux 设计的——Windows 用户要么装 WSL，要么上 Docker，体验总差一点。

所以我做了一个面向 Windows 的原生 AI 系统：Solo。

### 它能做什么？
- 通过微信发一条消息，Solo 就能规划、审核、执行一个任务
- 控制你的浏览器填表、截图
- 自动操作 Windows 桌面应用
- 运行代码脚本
- 所有高风险操作需要你的审批

### 它不是普通的聊天机器人
大多数 AI 助手只是生成文字。Solo 可以在你电脑上**干活**。

### 安全设计
- 三省六部制：规划智能体不能执行，执行智能体不能规划
- 所有高风险操作需要审批
- 完整审计链路：谁规划、谁审核、谁批准、谁执行

### 项目状态
🔶 Alpha 版，在作者机器上可以工作。欢迎尝鲜和贡献！

GitHub: https://github.com/chengcheng-2006/solo-windows-ai-agent

---

## 3. Reddit (r/LocalLLaMA, r/MachineLearning, r/Windows)

**Title**: [Project] Solo — Open-source Windows-first personal AI agent with multi-agent orchestration and approval-based safety

**Body**:

I built Solo, an open-source personal AI system designed to run on Windows. Unlike most AI agents that target Linux, Solo uses native Windows automation (UIA, COM, named pipes) alongside CDP-based browser control.

**Key differentiators:**
- Multi-agent orchestration with separation of powers (planning ≠ execution ≠ review)
- Every high-risk operation requires human approval
- Full audit trail from conversation to result
- Self-hosted, you bring your own API keys
- Local-first architecture with Docker infrastructure

It's early-stage (Alpha) but working on my Windows machine. Would love feedback and contributions.

https://github.com/chengcheng-2006/solo-windows-ai-agent

---

## 4. Hacker News

**Title**: Solo: A Windows-first personal AI agent with approval-based safety

**Body**:

I've been building a personal AI system for Windows — the kind that doesn't just chat but actually does things on your computer. Not another Linux-first agent that "works on WSL," but something that leverages Windows-native automation from the start.

**How it works:**
1. You send a message via WeChat or CLI
2. Planning agent breaks it down
3. Reviewer checks for safety and feasibility
4. Dispatcher sends tasks to specialized workers
5. Results are verified before returning

**The safety model is what I'm most interested in feedback on:**
- No single agent has unrestricted control
- Planners can't execute, executors can't plan
- High-risk operations need a human to approve
- Everything is logged in an audit trail

It's early but working. Apache 2.0 licensed.

https://github.com/chengcheng-2006/solo-windows-ai-agent

---

## 5. X / Twitter

**Thread**:

1/ I wanted a personal AI that could actually do things on my Windows PC without giving one model unrestricted control. So I built Solo — open-sourcing it today 🧵👇

2/ Solo is a Windows-first personal AI agent system. It processes chat requests through:
🧠 Planning → ✅ Review → 🏃 Execution → 📋 Verification

3/ Key design principle: separation of powers. The agent that plans can't execute. The agent that reviews can't plan. High-risk actions need your approval.

4/ What it can do:
• Control your browser (CDP)
• Automate Windows desktop (UIA/OCR)
• Run code (Python, PowerShell, Docker)
• Vision and voice input
• WeChat messaging

5/ Self-hosted, BYOK, Apache 2.0 license. Currently Alpha.

https://github.com/chengcheng-2006/solo-windows-ai-agent

---

## 6. LinkedIn

**Title**: Open-sourcing Solo — a Windows-first personal AI agent

**Body**:

I'm excited to share Solo, a personal AI system designed specifically for Windows. Unlike many AI agents that are Linux-first, Solo leverages native Windows automation (UIA, COM, CDP) from the ground up.

**Architecture highlights:**
- 13 specialized agents with role-based tool permissions
- Multi-stage approval pipeline
- Full audit trail for every action
- Browser and desktop automation
- Self-hosted with BYOK

This is an Alpha release and I'm looking for feedback and contributors.

https://github.com/chengcheng-2006/solo-windows-ai-agent

---

## 7. Project Demo Video Script

**Title**: Solo Windows AI Agent — 60-second demo

**Script**:
[0-10s] Show chat window → "Automate a task for me"
[10-25s] Show planning agent analyzing the request
[25-35s] Show browser automation in action
[35-45s] Show result being verified
[45-55s] Show approval request for high-risk operation
[55-60s] GitHub URL

---

## 8. Personal Resume / Portfolio Description

Built Solo, a Windows-first personal AI system with multi-agent orchestration, CDP-based browser automation, Windows UIA desktop automation, approval-based safety controls, and full audit trail. Open-source (Apache 2.0), self-hosted, BYOK.

---

## 9. GitHub Profile Pinned Repo Description

A Windows-first personal AI agent with multi-agent orchestration, browser and desktop automation, voice/vision workers, and approval-based safety controls.
