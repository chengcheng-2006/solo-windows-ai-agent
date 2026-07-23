# Installation Guide (v0.1.1 Lite)

> 🚀 **Lite mode install — zero API keys, zero Docker, zero Node.js, zero GPU required.**

## System Requirements

- **OS**: Windows 10/11, Linux, macOS
- **Python**: 3.11+
- **pip**: Latest (or use `pipx` for isolated install)

## Quick Install

```powershell
pip install solo-agent
```

That's it. The `solo` CLI is immediately available:

```powershell
solo doctor          # Environment health check
solo demo safe       # Safe Demo: R0 end-to-end pipeline
solo demo veto       # VETO Demo: R3 rejection demo
solo version         # Show version
solo cleanup         # Cleanup demo artifacts
```

## Verify Installation

```powershell
solo doctor
```

Expected output (Lite mode):
```
  ✅ Python          3.11.9
  ✅ Disk Space      45.2 GB free
  ✅ Write Access    Temp directory writable
  ⚠️  Node.js         Not found (optional)
  ⚠️  API Key         Not set (optional)
```

## Run the Demos

```powershell
solo demo safe       # 8-step pipeline, real TaskStore + Risk + Policy + Approval + Validator
solo demo veto       # R3 request → rejected by safety system, 6 security guarantees verified
```

Both demos run in **Lite mode** with no API keys required.

## Optional: Core Mode (add HTTP + browser)

```powershell
pip install solo-agent[core]
```

Enables:
- HTTP client (httpx) for API calls
- Playwright browser automation

## Optional: Full Mode (Docker infrastructure)

Full mode requires:
- Docker Desktop 4.30+
- `docker compose` infrastructure (see `infra/`)

## Lite vs Core vs Full

| Feature | Lite | Core | Full |
|---------|------|------|------|
| pip install | `solo-agent` | `solo-agent[core]` | `solo-agent[full]` |
| Demo pipelines | ✅ | ✅ | ✅ |
| CLI (doctor/cleanup) | ✅ | ✅ | ✅ |
| SQLite persistence | ✅ | ✅ | ✅ |
| HTTP/API calls | ❌ | ✅ | ✅ |
| Browser automation | ❌ | ✅ | ✅ |
| Docker services | ❌ | ❌ | ✅ |
| GPU Workers | ❌ | ❌ | ✅ |
| API keys required | ❌ | ✅ (some features) | ✅ |

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues.

---

## Legacy Installation (v0.1.0)

> ⚠️ The following instructions are for the v0.1.0 production deployment and are **DEPRECATED** in favor of the v0.1.1 Lite install above.

### Old Requirements
- Windows 10/11 (64-bit)
- Python 3.11+
- Node.js 18+
- Git
- PowerShell 5.1+
- Docker Desktop 4.30+ (for infrastructure services)

### Old Setup Steps

1. Clone:
   ```powershell
   git clone https://github.com/chengcheng-2006/solo-windows-ai-agent.git
   cd solo-windows-ai-agent
   ```

2. Set up Python environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Set up Node.js:
   ```powershell
   npm install
   ```

4. Configure API keys:
   ```powershell
   cp .env.example .env
   ```
