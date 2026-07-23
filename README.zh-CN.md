# Solo — 面向 Windows 的个人 AI 智能体系统

<p align="center">
  <a href="README.md">English</a> | <em>简体中文</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="许可证">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg" alt="平台">
  <img src="https://img.shields.io/badge/status-Alpha-orange.svg" alt="状态">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="欢迎 PR">
</p>

<p align="center">
  <b>把你的聊天请求转化为可审计的 Windows 任务——通过规划、审核、审批、浏览器自动化和结果验证。</b>
</p>

---

## 什么是 Solo？

Solo 是一个**面向 Windows 的个人 AI 系统**，通过多智能体流水线处理你的聊天请求：

1. **规划** — 理解你的需求并拆解步骤
2. **审核** — 检查安全性、可行性和资源需求
3. **执行** — 使用浏览器自动化、Windows UI 自动化、OCR、代码执行或视觉模型
4. **验证** — 验证结果后再返回给你

每一步都有审计追踪。高风险操作需要你的审批。

## 为什么用 Solo？

| 问题 | Solo 如何解决 |
|------|-------------|
| AI 智能体通常跑在 Linux 上，而不是 Windows | 原生 Windows 自动化，开箱即用 |
| 单个模型拥有不受限制的控制权 | 多智能体审批门将规划与执行分离 |
| 任务进入黑箱，无法追踪 | 完整审计链路：谁规划、谁审核、谁批准、谁执行 |
| 无法自动化桌面应用 | Windows UI 自动化 + OCR + 视觉模型降级链 |
| 纯云端意味着数据离开你的机器 | 自托管，BYOK（自带密钥），支持本地模型 |
| 浏览器自动化需要复杂配置 | Chrome DevTools Protocol + Playwright，自动配置 |

## 安全设计

- **审批门** — 规划智能体不能执行，审核智能体不能执行
- **工具级权限** — 每个智能体有允许使用的工具白名单
- **高风险操作** — 需要明确的人类审批（微信确认）
- **审计追踪** — 每个决策、批准和执行步骤都被记录
- **仅本机绑定** — Gateway 绑定到 localhost，不暴露到网络
- **自带密钥** — 你的 API 密钥保存在加密配置中

## 项目状态

> **Alpha 版** — Solo 处于活跃开发阶段，已在作者机器上测试通过。
> 它能工作，但可能有不完善之处。欢迎贡献！

## 快速开始（v0.1.1 Lite）

### 前置条件

- Python 3.11+
- pip

### 安装

```powershell
pip install solo-agent
```

### 运行 Demo（无需 API Key）

```powershell
solo demo safe    # R0 端到端管道：8 步
solo demo veto    # R3 高风险请求被拒绝
solo doctor       # 环境健康检查
solo version      # 版本和模式信息
```

所有 Demo 在 **Lite 模式**下运行——零 API Key、零 Docker、零 Node.js、零 GPU。

---

### 前置条件（v0.1.0 Legacy）

- Windows 10/11（64 位）
- PowerShell 5.1+
- Node.js 18+
- Python 3.11+
- Git
- （可选）Docker Desktop 用于基础设施服务

### 1. 克隆并安装（v0.1.0 Legacy）

```powershell
git clone https://github.com/chengcheng-2006/solo-windows-ai-agent.git
cd solo-windows-ai-agent
```

### 2. 配置 API 密钥（v0.1.0 Legacy）

```powershell
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

### 3. 运行健康检查

```powershell
.\scripts\doctor.ps1
```

### 4. 启动 Solo

```powershell
.\scripts\start.ps1
```

### 5. 和 Solo 对话

通过配置的消息网关发送消息，或本地测试：

```powershell
.\scripts\test_smoke.ps1
```

### 6. 停止

```powershell
.\scripts\stop.ps1
```

## 许可证

Solo/PAIOS 核心基于 **Apache 2.0** 开源。
Hermes 基于 MIT 许可证使用（详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。

---

<p align="center">
  如果 Solo 对你的 Windows 个人 AI 系统有所帮助，欢迎点一个 Star ⭐，让更多开发者看到它。
</p>
