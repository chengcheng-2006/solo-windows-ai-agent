# Configuration Guide

## Configuration Files

Solo uses a layered configuration system:

```
.env                              # Environment variables (API keys)
config/examples/                  # Example configuration files
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key (planning/review agents) |
| `OPENAI_API_KEY` | No | OpenAI API key (Codex worker) |
| `ZHIPU_API_KEY` | No | ZHIPU API key (vision agent) |
| `PAIOS_POSTGRES_PASSWORD` | No | PostgreSQL password (Docker) |
| `PAIOS_NATS_PASSWORD` | No | NATS password (Docker) |
| `PAIOS_GRAFANA_PASSWORD` | No | Grafana admin password (Docker) |
| `OLLAMA_HOST` | No | Ollama server URL (default: http://127.0.0.1:11434) |

## Example .env

```bash
# --- Required ---
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY

# --- Optional LLM Providers ---
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
ZHIPU_API_KEY=YOUR_ZHIPU_API_KEY

# --- Infrastructure ---
PAIOS_POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD
PAIOS_NATS_PASSWORD=YOUR_NATS_PASSWORD
PAIOS_GRAFANA_PASSWORD=YOUR_GRAFANA_PASSWORD
```

## Model Configuration

Model routing is defined in `config/model-routing.json`. See [ARCHITECTURE.md](ARCHITECTURE.md) for the routing topology.

The 4-level routing system:
- **Level 1** (Local): Ollama Qwen 2.5 7B — free, fast, simple queries
- **Level 2** (Free Cloud): DeepSeek Chat — knowledge, explanation
- **Level 3** (Paid Fast): DeepSeek Flash — reasoning, code
- **Level 4** (Paid Pro): DeepSeek Pro — complex decisions

## Agent Team Configuration

Agent roles and permissions are defined in `config/agent_team/`:

| File | Purpose |
|------|---------|
| `agent_role_mapping.yaml` | Role definitions and tool permissions |
| `permission_matrix.yaml` | Tool access matrix per agent |
| `state_machine.yaml` | Agent workflow state machine |
| `review.schema.json` | Review output format |
| `memorial.schema.json` | Report output format |
| `agents.schema.json` | Unified agent schema |

## Native DeepSeek Harness Runtime (Optional)

The `openclaw-dsh-runtime` plugin is optional. When enabled, it maps:

- `deepseek/deepseek-v4-flash` → `dsh-flash-router` → DSH preset `router-standard`
- `deepseek/deepseek-v4-pro` → `dsh-pro-anchored` → DSH preset `anchored-standard`

Both profiles are **experimental**. All other models keep OpenClaw's native
runtime.

The helper script applies the OpenClaw-side model policy:

```powershell
python plugins/openclaw-dsh-runtime/scripts/apply_bridge_config.py
```

Plugin configuration example:

```json
{
  "enabled": true,
  "dshBaseUrl": "http://127.0.0.1:3081",
  "contextTransferPolicy": "selected",
  "fallbackOnRuntimeFailure": "fail",
  "profiles": {
    "flash": {
      "harnessId": "dsh-flash-router",
      "model": "deepseek-v4-flash",
      "presetId": "router-standard",
      "reasoningEffort": "max",
      "status": "experimental"
    },
    "pro": {
      "harnessId": "dsh-pro-anchored",
      "model": "deepseek-v4-pro",
      "presetId": "anchored-standard",
      "reasoningEffort": "max",
      "status": "experimental"
    }
  },
  "timeouts": {
    "startupMs": 30000,
    "executionMs": 1800000,
    "idleMs": 300000,
    "shutdownMs": 10000
  }
}
```

To disable:

```powershell
python plugins/openclaw-dsh-runtime/scripts/disable_bridge.py
```

See [plugins/openclaw-dsh-runtime/README.md](../plugins/openclaw-dsh-runtime/README.md)
for full details.

## Port Configuration

All service ports are defined in `config/runtime_ports.yaml` and bind to 127.0.0.1 only.
