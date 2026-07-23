# Installation Guide

> **⚠️ Alpha Status**: Solo is currently in active development. Installation requires familiarity with Windows development tools. Expect rough edges.

## System Requirements

### Minimum
- **OS**: Windows 10 22H2+ or Windows 11 (64-bit)
- **CPU**: 4+ cores (x86-64)
- **RAM**: 16 GB
- **Storage**: 10 GB free on C: drive, 50 GB free on D: (or data drive)
- **PowerShell**: 5.1+ (Windows built-in)
- **Git**: 2.40+
- **Node.js**: 18+ (LTS recommended)
- **Python**: 3.11+

### Recommended
- **GPU**: NVIDIA with 4+ GB VRAM (for local LLM and vision models)
- **RAM**: 32 GB
- **Docker Desktop**: 4.30+ (for infrastructure services)
- **Disc space**: 100+ GB free on data drive

## Installation Steps

### 1. Clone the Repository

```powershell
git clone https://github.com/chengcheng-2006/solo-windows-ai-agent.git
cd solo-windows-ai-agent
```

### 2. Set Up Python Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Set Up Node.js Dependencies

```powershell
npm install
# or
pnpm install
```

### 4. Configure API Keys

```powershell
cp .env.example .env
notepad .env
```

You need at least one LLM API key:
- **DeepSeek API key** — For planning and review agents (recommended)
- Or **OpenAI API key** — For Codex worker
- Or set up **Ollama** for fully local operation (limited capability)

### 5. Run Health Check

```powershell
.\scripts\doctor.ps1
```

The doctor script checks:
- PowerShell version
- Git availability
- Python environment
- Node.js environment
- API key configuration
- Disk space
- Docker Desktop (optional)
- Port availability

### 6. Start Solo

```powershell
.\scripts\start.ps1
```

### 7. Verify Operation

```powershell
.\scripts\test_smoke.ps1
```

This runs a basic smoke test:
- Gateway connectivity
- Model routing
- Agent availability

## Optional: Infrastructure Services

For full functionality (audit trail, event bus, dashboards), start Docker services:

```powershell
cd infra
docker compose up -d
```

This starts:
- PostgreSQL (task persistence)
- NATS (event bus)
- Temporal (workflow orchestration)
- Prometheus + Grafana (monitoring)
- Loki + Alloy (log aggregation)

## Optional: Local Models

### Ollama (for local text inference)

```powershell
# Install Ollama
winget install Ollama.Ollama

# Pull a model
ollama pull qwen2.5:7b
```

### Faster-Whisper (for voice input)

```powershell
pip install faster-whisper
# Download model: base or small for best speed/accuracy balance
```

## Stopping Solo

```powershell
.\scripts\stop.ps1
```

## Uninstalling

```powershell
.\scripts\uninstall.ps1
```

This stops services and removes the configuration directory.

## Verification Checklist

After installation:

- [ ] `.\scripts\doctor.ps1` passes all checks
- [ ] `.\scripts\start.ps1` starts without errors
- [ ] `.\scripts\test_smoke.ps1` returns success
- [ ] Gateway responds on 127.0.0.1:18789
- [ ] Agent team responds to test messages

## Supported Windows Versions

| Version | Status |
|---------|--------|
| Windows 11 23H2+ | ✅ Tested |
| Windows 10 22H2+ | ✅ Tested |
| Windows Server 2022 | ❌ Not tested |
| Windows on ARM | ❌ Not tested |
| Wine / Linux | ❌ Not supported |

## Common Issues

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions.
