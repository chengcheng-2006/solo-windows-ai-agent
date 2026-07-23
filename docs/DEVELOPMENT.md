# Development Guide

## Development Environment

### Prerequisites
- Windows 10/11
- Git 2.40+
- PowerShell 5.1+
- Python 3.11+
- Node.js 18+
- Visual Studio Code (recommended)
- Docker Desktop (optional, for infrastructure)

### Setup

```powershell
# Clone the repository
git clone https://github.com/chengcheng-2006/solo-windows-ai-agent.git
cd solo-windows-ai-agent

# Set up Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

## Code Structure

```
solo-windows-ai-agent/
├── apps/paios/            # PAIOS orchestration core
├── agents/                # Agent definitions (三省六部)
├── workers/               # Task workers
├── orchestrator/          # Workflow engine
├── config/                # Configuration files
├── scripts/               # Automation scripts
├── tests/                 # Test suites
├── docs/                  # Documentation
├── infra/                 # Docker infrastructure
└── tools/                 # Diagnostic tools
```

## Development Workflow

### Branch Strategy
- `main` — Stable release branch
- `develop` — Development branch
- `feature/*` — Feature branches
- `fix/*` — Bug fix branches

### Commit Messages
Follow conventional commits:
```
feat: add new browser worker capability
fix: correct OCR fallback when vision API unavailable
docs: update installation guide
test: add smoke test for WeChat gateway
```

### Testing
```powershell
# Run all tests
.\tests\run_all.ps1

# Run specific test suite
.\tests\run.ps1 -Suite smoke

# Run Python tests
pytest apps/paios/tests/
```

## Adding a New Worker

1. Create your worker in `workers/<name>/`
2. Implement the worker interface (NATS subscription or PAIOS API)
3. Add configuration in `config/agent_team/`
4. Add tests in `tests/`
5. Update architecture docs
6. Submit a PR

## Code Style

- **Python**: Follow PEP 8, use type hints, max line length 100
- **PowerShell**: Follow PSScriptAnalyzer rules
- **Documentation**: Use Markdown, keep lines under 80 chars

## Security Requirements

- **No secrets in code** — Use environment variables or DPAPI store
- **No real user paths** — Use relative paths, environment variables, or config
- **New Computer Use capabilities** must include safety tests
- **New high-risk actions** must have approval gates

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a PR with a clear description
6. Wait for review

## Running Diagnostics

```powershell
# Health check
.\scripts\doctor.ps1

# Port status
.\scripts\quick_ports.ps1
```
