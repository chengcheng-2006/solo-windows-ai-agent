# Solo Security Model

## Overview

Solo is designed with a defense-in-depth approach to security. The system separates planning, review, approval, and execution into distinct roles, ensuring no single agent has unrestricted control.

## Core Principles

1. **Separation of powers** — Planning, review, and execution are handled by different agents
2. **Least privilege** — Each agent has only the tools it needs
3. **Human-in-the-loop** — High-risk operations require explicit approval
4. **Full audit trail** — Every action is logged and traceable
5. **Loopback-only** — Network services bind to localhost only
6. **BYOK** — You bring and manage your own API keys

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Malicious prompt injection | Multi-agent review; reviewer can VETO unsafe plans |
| Agent goes rogue | Each agent is tool-restricted; executor can't plan, planner can't execute |
| API key leakage | DPAPI-encrypted local store; no plaintext in config |
| Network attack | Loopback-only binding; no external ports exposed |
| Unauthorized access | WeChat DM policy requires pairing; owner-only commands |
| Data exfiltration | Approval gate for external operations; audit trail for all actions |
| Privilege escalation | Tool whitelist per agent; 27 global deny rules |

## Approval Gates

| Risk Level | Description | Approval Required |
|------------|-------------|------------------|
| R0 | Read-only, no side effects | None |
| R1 | Read+write within sandbox | Auto-review (menxia) |
| R2 | System modification, external API calls | Auto-review + optional human approval |
| R3 | File deletion, payment, sensitive data | Always human approval |

## Secret Management

- Secrets are stored in DPAPI-encrypted files (`C:\Users\<USER>\.openclaw\secrets\`)
- Environment variables are injected at runtime, never in config files
- API keys use `SecretRef` pattern: `secret://provider/key-name`
- `.env.example` contains only placeholder values (`YOUR_API_KEY`)
- No secrets in Git history

## Network Security

| Service | Bind | Accessible From |
|---------|------|----------------|
| Gateway (OpenClaw) | 127.0.0.1:18789 | Localhost only |
| PAIOS API | 127.0.0.1:8810 | Localhost only |
| PostgreSQL | 127.0.0.1:5432 | Localhost only |
| NATS | 127.0.0.1:4222 | Localhost only |
| Temporal | 127.0.0.1:7233 | Localhost only |
| Grafana | 127.0.0.1:3000 | Localhost only |
| Prometheus | 127.0.0.1:9090 | Localhost only |

## Reporting Vulnerabilities

See [SECURITY.md](../SECURITY.md) for the responsible disclosure process.

## Limitations

- Solo is **not** a hardened security sandbox — it's a personal productivity tool
- Computer Use (vision-based GUI control) is experimental and may behave unexpectedly
- Docker containers running on the same host share the kernel
- Third-party API calls (LLM providers) send data to external servers
- You are responsible for:
  - Protecting your API keys
  - Keeping your system updated
  - Reviewing audit logs periodically
