# Changelog

## [Unreleased]

### Internal Development (pre-open-source)
- PAIOS architecture design and implementation
- 三省六部 multi-agent system (13 agents)
- OpenClaw + Hermes integration
- WeChat gateway messaging
- Browser automation via CDP/Playwright
- Windows UIA/OCR desktop automation
- Computer Use vision-based GUI control (experimental)
- Local STT (Faster-Whisper)
- Docker infrastructure (PostgreSQL, NATS, Temporal, Grafana stack)
- Watchdog monitoring and alerting
- Secret management with DPAPI
- Privacy broker and audit trail
- Multi-agent approval gates
- 4-level model routing
- Memory bridge (OpenClaw ↔ Hermes sync)

## [0.2.0-alpha] - 2026-08-16

### Added
- Native DeepSeek Harness runtime integration via an optional OpenClaw plugin.
- Model-scoped runtime profiles for DeepSeek V4 Flash (`dsh-flash-router`) and
  DeepSeek V4 Pro (`dsh-pro-anchored`).
- DSH session persistence and resume.
- Runtime status diagnostics (`/runtime-status`).
- Cancellation and timeout handling.
- Disable and rollback controls.
- Offline unit tests for the plugin, plus optional live DSH integration tests.

### Changed
- DeepSeek V4 execution can now delegate to experimental DSH profiles when the
  bridge is enabled. All other models keep OpenClaw's native runtime.

### Security
- Runtime credentials remain outside public configuration.
- Added secret sanitization in bridge errors/logs and repo-level secret scan
  coverage.

### Known limitations
- Image attachment bridge is currently unsupported.
- Event mapping is currently polling-based.
- DSH rc API and experimental presets may change.
- Session hard deletion may be unavailable in DSH 0.1.0-rc.6.

## [0.1.0-alpha] - YYYY-MM-DD

### Added
- Initial open-source release
- Public README (English and Chinese)
- Security policy and contributing guidelines
- Issue templates and CI workflow
- Public documentation (architecture, installation, configuration)

### Notes
- This is an Alpha release
- Tested on author's Windows machine only
- WeChat gateway requires Chinese WeChat account
- Computer Use is experimental
