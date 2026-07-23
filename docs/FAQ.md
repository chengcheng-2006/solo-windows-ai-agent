# FAQ

## General

### What is Solo?
Solo is a Windows-first personal AI system. It processes your chat requests through multiple AI agents that plan, review, approve, execute, and verify tasks on your Windows computer.

### How is Solo different from ChatGPT or Claude?
ChatGPT and Claude are chatbots that respond with text. Solo can **do things on your computer** — control your browser, automate desktop applications, run code, and manage files — all while keeping an audit trail of what happened.

### Does Solo work on Mac or Linux?
Solo is designed specifically for Windows. It uses Windows-native technologies (UIA, COM, named pipes) that don't exist on other platforms. Some components could theoretically run on Linux, but the desktop automation features won't work.

### Is Solo ready for production use?
Solo is **Alpha** software. It works on the author's machine but has not been tested across different hardware configurations. Use it for experimentation and development.

## Safety

### Can Solo delete my files?
Only if you approve. High-risk operations (file deletion, system modification, external payments) require explicit human approval through the WeChat gateway.

### Can Solo access my API keys?
Solo uses your API keys to call LLM providers. They are stored encrypted (DPAPI) on your local machine. No data is sent to third parties except the LLM API calls you configure.

### Is my data private?
Solo is self-hosted — your data stays on your machine. However, LLM API calls send your prompts to external providers (DeepSeek, OpenAI, etc.). You control which providers to use.

### Can Solo be hacked?
Like any software, vulnerabilities are possible. Solo's multi-agent review system provides defense-in-depth, but it's not a hardened security product. Keep your system updated and review audit logs periodically.

## Technical

### What hardware do I need?
Minimum: Windows 64-bit, 4-core CPU, 16 GB RAM, 10 GB free disk.
Recommended: NVIDIA GPU with 4+ GB VRAM, 32 GB RAM, 100 GB free disk.

### Do I need Docker?
Docker is optional but recommended. It provides infrastructure services (PostgreSQL, NATS, monitoring) that enhance Solo's capabilities. Basic chat-and-automate features work without Docker.

### What API keys do I need?
At minimum, a DeepSeek API key. Optional: OpenAI (for Codex), ZHIPU (for vision), Ollama (for fully local operation).

### Can I use OpenAI instead of DeepSeek?
Currently, DeepSeek is the primary model for planning/review agents. OpenAI is used for the Codex worker. The system is designed to be model-agnostic — custom providers can be added.

### How do I add a new worker?
Create a Python script/process that communicates via NATS or the PAIOS API, then register it in `config/agent_team/`.

## Contributing

### How can I contribute?
See CONTRIBUTING.md. We welcome PRs for bug fixes, documentation, and new workers. Please start with an Issue discussion for significant changes.

### Can I use Solo in my commercial product?
The core Solo/PAIOS code is Apache 2.0 licensed, which allows commercial use with attribution. Third-party components have their own licenses (see THIRD_PARTY_NOTICES.md).

### I found a bug. Where do I report it?
Open a GitHub Issue, or for security vulnerabilities, follow the process in SECURITY.md (private report).
