# Third-Party Notices

Solo uses the following third-party components and dependencies.

## Core Dependencies

### Hermes Agent
- **License**: MIT
- **Copyright**: (c) 2025 Nous Research
- **Source**: https://github.com/nousresearch/hermes
- **Used as**: Supervisor agent for task planning and orchestration
- **Modifications**: Configuration profiles and integration adapters

### OpenClaw
- **License**: MIT
- **Source**: https://github.com/openclaw/openclaw
- **Used as**: Message gateway and tool execution engine

## Python Dependencies

| Package | License | Purpose |
|---------|---------|---------|
| FastAPI | MIT | REST API server |
| uvicorn | BSD-3-Clause | ASGI server |
| SQLAlchemy | MIT | Database ORM |
| psycopg2-binary | LGPL-3.0 | PostgreSQL driver |
| pydantic | MIT | Data validation |
| httpx | BSD-3-Clause | HTTP client |
| websockets | BSD-3-Clause | WebSocket support |
| nats-py | Apache-2.0 | NATS client |
| temporalio | MIT | Workflow orchestration client |
| RapidOCR | Apache-2.0 | OCR engine |
| faster-whisper | MIT | Speech-to-text |
| playwright | Apache-2.0 | Browser automation |
| pywin32 | PSF | Windows COM/Win32 API |

## Node.js Dependencies

| Package | License | Purpose |
|---------|---------|---------|
| openclaw | (see OpenClaw) | AI Gateway |
| @tencent-weixin/openclaw-weixin | Proprietary | WeChat integration |

## Docker Images Used

| Image | License | Purpose |
|-------|---------|---------|
| pgvector/pgvector:0.8.0-pg16 | PostgreSQL License | Vector database |
| nats:2.14.0-alpine | Apache-2.0 | Event bus |
| temporalio/auto-setup:1.29.7 | MIT | Workflow engine |
| prom/prometheus:v3.5.0 | Apache-2.0 | Metrics |
| grafana/grafana:12.0.2 | AGPL-3.0 | Dashboards |
| grafana/loki:3.5.0 | AGPL-3.0 | Log aggregation |
| grafana/alloy:v1.16.1 | AGPL-3.0 | Log shipping |

## External Runtime Tools (not bundled)

The optional `openclaw-dsh-runtime` plugin calls these external tools over
DSH's loopback RPC interface. They are not vendored or copied into this
repository.

| Tool | License | Purpose | Source |
|------|---------|---------|--------|
| DeepSeek Harness (`@deepseek-ai/dsh`) | MIT | DeepSeek-native runtime | npm / DSH project |
| Anchored Standard preset | MIT | Experimental DSH preset for DeepSeek V4 Pro | https://github.com/xiaobright/dsh-anchored-standard |
| Router Standard preset | MIT | Experimental DSH preset for DeepSeek V4 Flash | https://github.com/yjh051108/dsh-router-standard |

## Icon / Logo / Font

- The Solo logo uses the Inter font (SIL Open Font License 1.1)
- No third-party icons or graphics are included in this repository

## License Compatibility

The core Solo/PAIOS codebase is licensed under Apache 2.0.
Docker images used at runtime are not redistributed in this repository.

All third-party components listed above are used as:
- **Dependencies** (declared in pyproject.toml / package.json)
- **Docker images** (referenced in docker-compose.yml, not bundled)
- **Runtime tools** (configured via environment variables, not bundled)

## Attribution

This product includes software developed by:
- Nous Research (Hermes)
- OpenClaw team (OpenClaw)
- Various open-source contributors (see individual package licenses)
