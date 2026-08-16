# Compatibility Matrix

The bridge is tested against a specific, pinned toolchain. Upstream DSH and
the experimental presets can change quickly; treat these as the known-good
versions and stage upgrades.

| Component | Version / commit | Notes |
|---|---|---|
| OpenClaw | `>= 2026.7.1` | Agent Harness plugin API used: `api.registerAgentHarness` |
| Bridge | `0.1.0` | This repository |
| DeepSeek Harness (DSH) | `@deepseek-ai/dsh@0.1.0-rc.6` | Loopback HTTP RPC; package is not vendored |
| Anchored Standard preset | commit `db4527a2a70a9032d3a8525ce3c0ea6ef528d6fc` | Upstream: `xiaobright/dsh-anchored-standard` (MIT), experimental |
| Router Standard preset | commit `eff787e95132d6c7104214542104a84d656b497e`, tag `v0.2.0` | Upstream: `yjh051108/dsh-router-standard` / `dsh-routing-suite` (MIT), experimental |
| Transport | DSH HTTP RPC `/api/*` + `session.history` polling | Loopback only |
| Session persistence | JSON file with atomic replace | Path defaults to `~/.openclaw/openclaw-dsh-runtime/` |

## Upstream license note

The bridge **calls** DSH and its presets over DSH's RPC interface. It does not
vendor or copy DSH, Anchored Standard, Router Standard, or OpenClaw source
code into this repository. Runtime presets remain installed by the user in
their DSH home; the bridge only sends RPC requests and observes metadata.
