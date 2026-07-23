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

## Port Configuration

All service ports are defined in `config/runtime_ports.yaml` and bind to 127.0.0.1 only.
