# OpenClaw DeepSeek Harness Runtime Bridge

**Status: experimental integration**

This plugin adds optional native DeepSeek Harness execution profiles for
DeepSeek V4 Flash and V4 Pro. It does **not** replace OpenClaw's native
runtime for other models, and it does **not** modify OpenClaw core.

```
OpenClaw
   │
   ├─ DeepSeek V4 Flash
   │      ↓
   │   DSH Runtime
   │      ↓
   │   Router Standard (experimental)
   │
   ├─ DeepSeek V4 Pro
   │      ↓
   │   DSH Runtime
   │      ↓
   │   Anchored Standard (experimental)
   │
   └─ Other Models
          ↓
       OpenClaw Native Runtime
```

## What it does

- Registers two OpenClaw native Agent Harness entries:
  - `dsh-flash-router` → DeepSeek Harness preset `router-standard`
  - `dsh-pro-anchored` → DeepSeek Harness preset `anchored-standard`
- When OpenClaw resolves `deepseek/deepseek-v4-flash` or
  `deepseek/deepseek-v4-pro`, the turn is delegated to a real DSH runtime over
  loopback HTTP RPC.
- DSH owns DeepSeek prompt assembly, tool schemas, tool execution, and the
  tool loop. OpenClaw owns model selection, sessions, channels, and delivery.
- DSH session mappings are persisted locally and resumed across OpenClaw turns
  (`/new` or reset detaches the mapping).
- Cancellation, timeout handling, runtime status (`/runtime-status`), a
  disable switch, and rollback are supported.

## Requirements

- OpenClaw `>= 2026.7.1`
- Node.js 20+ (the plugin is an ES module)
- DeepSeek Harness (`@deepseek-ai/dsh`) `0.1.0-rc.6` or a compatible release
- The DSH presets installed:
  - `router-standard` (experimental)
  - `anchored-standard` (experimental)
- DeepSeek credentials configured inside the DSH credential store (the bridge
  never reads or stores API keys)

The DSH transport is plain HTTP on loopback (`127.0.0.1`). Do not expose DSH
`/api` beyond loopback without an authenticated proxy.

## Install

From the repository root:

```powershell
# Add the plugin directory to OpenClaw's plugin load path, enable it, and
# apply the model-scoped runtime mapping.
python plugins/openclaw-dsh-runtime/scripts/apply_bridge_config.py

# Restart OpenClaw Gateway so the plugin loads.
openclaw gateway restart --force
```

To inspect the live status:

```
/runtime-status
```

The command shows bridge version, enabled state, DSH health, profile mappings,
and persisted DSH session mappings.

## Configuration

The plugin is optional. If DSH is not installed, or if you do not enable the
plugin, DeepSeek models keep OpenClaw's native behavior.

Example plugin configuration (JSON):

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

The model-scoped OpenClaw routing entries applied by the helper are:

```json
{
  "agents": {
    "defaults": {
      "models": {
        "deepseek/deepseek-v4-flash": {
          "agentRuntime": { "id": "dsh-flash-router" }
        },
        "deepseek/deepseek-v4-pro": {
          "agentRuntime": { "id": "dsh-pro-anchored" }
        }
      }
    }
  }
}
```

All other models continue to use OpenClaw's native runtime.

## Disable / rollback

Disable the bridge while keeping the plugin installed:

```powershell
python plugins/openclaw-dsh-runtime/scripts/disable_bridge.py
openclaw gateway restart --force
```

This restores DeepSeek V4 Flash/Pro to `agentRuntime.id=openclaw` and disables
the plugin entry.

Roll back to a pre-bridge OpenClaw config backup:

```powershell
python plugins/openclaw-dsh-runtime/scripts/rollback_bridge.py --backup C:\path\to\backup.json
openclaw gateway restart --force
```

## Tests

Offline unit tests (no DSH required):

```powershell
node --test plugins/openclaw-dsh-runtime/tests/unit
```

Optional live integration tests (requires a running DSH instance):

```powershell
$env:OCDSH_TEST_DSH_URL="http://127.0.0.1:3081"
node --test plugins/openclaw-dsh-runtime/tests/integration
```

## Known limitations

- Image attachment bridge is currently unsupported; image input fails visibly
  and instructs the caller to use a native OpenClaw turn.
- Event mapping is currently polling-based (bounded `session.history` reads),
  not a WebSocket token stream.
- DSH 0.1.0-rc.6 has cancel/archive but no safe hard-delete RPC. OpenClaw
  `/new` detaches the bridge mapping; DSH JSONL remains on disk until DSH
  workspace cleanup.
- DSH rc APIs and experimental presets may change; versions are pinned in the
  compatibility matrix and upgrades should be staged.
- The bridge fails closed. `fallbackOnRuntimeFailure=native` does not silently
  replay the same turn through OpenClaw native runtime; it returns a visible
  error with instructions to disable the bridge.
