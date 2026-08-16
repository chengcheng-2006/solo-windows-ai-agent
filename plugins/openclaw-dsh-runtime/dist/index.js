import path from "node:path";
import fs from "node:fs";
import { homedir } from "node:os";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { DshClient, BridgeLog, BridgeError, hashKey } from "./lib/dsh-client.js";
import { SessionMapStore } from "./lib/session-store.js";
import { DelegatedRun } from "./lib/bridge-run.js";

const BRIDGE_VERSION = "0.1.0";

const DEFAULT_CONFIG = {
  enabled: true,
  dshBaseUrl: "http://127.0.0.1:3081",
  contextTransferPolicy: "selected",
  fallbackOnRuntimeFailure: "fail",
  profiles: {
    flash: {
      harnessId: "dsh-flash-router",
      model: "deepseek-v4-flash",
      presetId: "router-standard",
      reasoningEffort: "max",
      status: "experimental",
    },
    pro: {
      harnessId: "dsh-pro-anchored",
      model: "deepseek-v4-pro",
      presetId: "anchored-standard",
      reasoningEffort: "max",
      status: "experimental",
    },
  },
  timeouts: {
    startupMs: 30000,
    executionMs: 1800000,
    idleMs: 300000,
    shutdownMs: 10000,
  },
};

function deepMergeDefaults(base, extra) {
  if (extra === undefined || extra === null) return structuredClone(base);
  if (Array.isArray(base) || typeof base !== "object" || typeof extra !== "object") return extra;
  const out = { ...base };
  for (const [key, value] of Object.entries(extra)) {
    out[key] = value && typeof value === "object" && !Array.isArray(value) && base[key] && typeof base[key] === "object"
      ? deepMergeDefaults(base[key], value)
      : value;
  }
  return out;
}

function resolveConfig(pluginConfig) {
  return deepMergeDefaults(DEFAULT_CONFIG, pluginConfig || {});
}

function resolveDir(raw, fallback) {
  if (typeof raw === "string" && raw.trim()) return path.resolve(raw.trim());
  return path.resolve(fallback);
}

function providerMatches(value) {
  return String(value || "").toLowerCase() === "deepseek";
}

const globalState = {
  config: null,
  client: null,
  store: null,
  logger: null,
  locks: new Map(),
};

async function withLock(key, fn) {
  const previous = globalState.locks.get(key) || Promise.resolve();
  let release;
  const tail = new Promise((resolve) => { release = resolve; });
  const next = previous.then(() => tail);
  globalState.locks.set(key, next);
  await previous;
  try {
    return await fn();
  } finally {
    release();
    if (globalState.locks.get(key) === next) globalState.locks.set(key, tail);
  }
}

function classifyUnexpected(error) {
  if (error && error.code) return error.code;
  const message = String((error && error.message) || error).toLowerCase();
  if (message.includes("credential") || message.includes("api key") || message.includes("unauthorized")) return "CREDENTIAL_ERROR";
  if (message.includes("preset")) return "PRESET_NOT_FOUND";
  if (message.includes("model")) return "MODEL_NOT_AVAILABLE";
  if (message.includes("timeout") || message.includes("abort")) return "RUNTIME_TIMEOUT";
  return "DSH_INTERNAL_ERROR";
}

function createHarness(profileName) {
  const id = profileName === "flash" ? "dsh-flash-router" : "dsh-pro-anchored";
  return {
    id,
    label: profileName === "flash"
      ? "DeepSeek Harness V4 Flash Router (experimental)"
      : "DeepSeek Harness V4 Pro Anchored Standard",
    supports(ctx) {
      const config = globalState.config || DEFAULT_CONFIG;
      if (!config.enabled) return { supported: false, reason: "openclaw-dsh-runtime bridge is disabled" };
      if (!providerMatches(ctx.provider)) return { supported: false, reason: `provider ${ctx.provider} is not deepseek` };
      const profile = config.profiles[profileName];
      if (!profile) return { supported: false, reason: `missing ${profileName} execution profile` };
      if (ctx.modelId && String(ctx.modelId).trim() !== profile.model) {
        return { supported: false, reason: `model ${ctx.modelId} is not ${profile.model}` };
      }
      return { supported: true, priority: 100, reason: `delegates to DSH preset ${profile.presetId} with reasoning ${profile.reasoningEffort}` };
    },
    async runAttempt(params) {
      const config = globalState.config || DEFAULT_CONFIG;
      if (!config.enabled) throw new BridgeError("DSH_NOT_FOUND", "openclaw-dsh-runtime bridge is disabled");
      const profile = config.profiles[profileName];
      if (!profile) throw new BridgeError("PRESET_NOT_FOUND", `missing ${profileName} execution profile`);
      if (params.modelId && params.modelId !== profile.model) {
        throw new BridgeError("MODEL_NOT_AVAILABLE", `runtime ${id} received ${params.provider}/${params.modelId}; expected ${profile.model}`);
      }
      const key = hashKey("run", params.sessionKey || params.sessionId || "unscoped", profileName);
      return withLock(key, async () => {
        const run = new DelegatedRun({
          config,
          profile,
          params,
          client: globalState.client,
          store: globalState.store,
          logger: globalState.logger,
        });
        const startedAt = Date.now();
        try {
          await run.log("turn.started", { status: "ok" });
          const result = await run.run();
          const final = await run.collectFinalUsage();
          if (final.usage) result.attemptUsage = final.usage;
          if (final.usage && result.lastAssistant) result.lastAssistant.usage = final.usage;
          if (final.usage && result.currentAttemptAssistant) result.currentAttemptAssistant.usage = final.usage;
          await run.log("turn.completed", {
            status: "ok",
            durationMs: Date.now() - startedAt,
            toolCallCount: run.accumulator.toolCallCount,
          });
          return result;
        } catch (error) {
          const code = error && error.code ? error.code : classifyUnexpected(error);
          const message = String((error && error.message) || error);
          await run.log("turn.failed", {
            status: "error",
            errorClass: code,
            durationMs: Date.now() - startedAt,
            toolCallCount: run.accumulator.toolCallCount,
          });
          if (config.fallbackOnRuntimeFailure === "native") {
            throw new BridgeError(code, `${message} (configured native fallback requires an operator policy switch to agentRuntime.id=openclaw; failing visibly instead of silently changing harness semantics)`);
          }
          throw new BridgeError(code, message);
        }
      });
    },
    classify(result) {
      if (result.promptError) return undefined;
      if (!result.assistantTexts || result.assistantTexts.length === 0 || !result.assistantTexts.some((t) => String(t).trim())) {
        return "empty";
      }
      return undefined;
    },
    async reset(params) {
      if (!globalState.store) return;
      const openclawSessionHash = hashKey(params.sessionKey || params.sessionId || "unscoped");
      await globalState.store.removeForOpenclaw(openclawSessionHash);
    },
    async dispose() {
      // No subprocesses or sockets owned by this harness.
    },
  };
}

async function runtimeStatusText() {
  const config = globalState.config || DEFAULT_CONFIG;
  const lines = [];
  lines.push("OpenClaw DSH Runtime Bridge");
  lines.push(`Bridge version: ${BRIDGE_VERSION}`);
  lines.push(`Bridge enabled: ${config.enabled ? "yes" : "no"}`);
  lines.push(`DSH URL: ${config.dshBaseUrl}`);
  lines.push(`Context transfer policy: ${config.contextTransferPolicy}`);
  lines.push(`Runtime failure policy: ${config.fallbackOnRuntimeFailure}`);
  lines.push(`Flash profile: ${config.profiles.flash.model} -> runtime DSH, preset ${config.profiles.flash.presetId}, reasoning ${config.profiles.flash.reasoningEffort} (${config.profiles.flash.status})`);
  lines.push(`Pro profile: ${config.profiles.pro.model} -> runtime DSH, preset ${config.profiles.pro.presetId}, reasoning ${config.profiles.pro.reasoningEffort} (${config.profiles.pro.status})`);
  if (globalState.store) {
    const data = await globalState.store.load();
    const entries = data.listEntries ? data.listEntries() : Object.values(data.sessions || {});
    lines.push(`DSH session mappings: ${entries.length} persisted`);
    for (const entry of entries) {
      lines.push(`- ${entry.profileId}: dsh session ${entry.dshSessionId}, cwd ${entry.dshCwd}, lastUsed ${entry.lastUsedAt || entry.createdAt || "unknown"}`);
    }
  }
  if (globalState.client) {
    const health = await globalState.client.health();
    lines.push(`Health: ${health.status}`);
    lines.push(`DSH available: ${health.dshAvailable}`);
    lines.push(`Provider available: ${health.providerAvailable}`);
    lines.push(`Models available: ${health.modelAvailable}`);
    lines.push(`Presets available: ${health.presetAvailable}`);
    lines.push(`Session backend available: ${health.sessionBackendAvailable}`);
    if (health.details?.host?.version) lines.push(`DSH version: ${health.details.host.version}`);
    if (health.details?.host?.attachedSessions !== undefined) lines.push(`DSH attached sessions: ${health.details.host.attachedSessions}`);
  }
  return lines.join("\n");
}

const pluginEntry = definePluginEntry({
  id: "openclaw-dsh-runtime",
  name: "DeepSeek Harness Runtime Bridge",
  description: "Delegates DeepSeek V4 Flash/Pro agent turns to the real DeepSeek Harness runtime. DSH owns DeepSeek-native prompt assembly and tool loop.",
  register(api) {
    const config = resolveConfig(api.pluginConfig);
    globalState.config = config;
    const stateDir = resolveDir(config.stateDir, path.join(homedir(), ".openclaw", "openclaw-dsh-runtime"));
    const logDir = resolveDir(config.logDir, stateDir);
    fs.mkdirSync(stateDir, { recursive: true });
    fs.mkdirSync(logDir, { recursive: true });
    globalState.logger = new BridgeLog(logDir);
    globalState.store = new SessionMapStore(path.join(stateDir, "session-map.json"));
    globalState.client = new DshClient(config.dshBaseUrl, globalState.logger);
    api.registerAgentHarness(createHarness("flash"));
    api.registerAgentHarness(createHarness("pro"));
    api.registerCommand({
      name: "runtime-status",
      description: "Show DeepSeek Harness runtime bridge status, health, profiles, and DSH session mappings.",
      acceptsArgs: false,
      requireAuth: true,
      handler: async () => ({ text: await runtimeStatusText() }),
    });
  },
});

export default pluginEntry;
