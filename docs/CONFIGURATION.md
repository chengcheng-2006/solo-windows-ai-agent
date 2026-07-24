# Configuration Guide

## Configuration Files

Solo uses a layered configuration system:

```
.env                              # Environment variables (API keys)
config/examples/                  # Example configuration files
```

> ⚠️ **v0.1.1 Note:** The legacy `config/agent_team/` and `config/model-routing.json`
> files referenced in previous documentation are not part of the public release.
> See `docs/internal/ADR_002_PACKAGING_AND_CLI.md` for the CLI-based configuration.

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

## v0.1.1 Configuration (New)

For v0.1.1, the recommended configuration is:

1. **Lite mode (default):** No configuration needed. `pip install solo-agent` and run.
2. **Demo:** `solo demo safe` or `solo demo veto` — no API keys required.
3. **Environment check:** `solo doctor` detects available capabilities.
4. **Model routing:** Managed by PAIOS orchestrator; default model is `deepseek-v4-flash`.

For deployment mode override:
```bash
export SOLO_MODE=lite    # Force Lite mode
export SOLO_MODE=core    # Force Core mode (requires httpx + playwright)
```
