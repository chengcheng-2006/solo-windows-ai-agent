import { createHash } from "node:crypto";
import http from "node:http";
import https from "node:https";

export const DSH_PROVIDER = "deepseek-official";
export const DSH_VERSION_MIN = "0.1.0-rc.6";
export const HISTORY_PAGE_SIZE = 200;

export function hashKey(...parts) {
  return createHash("sha256").update(parts.join("\u0000")).digest("hex").slice(0, 32);
}

export function sanitizeText(value) {
  let text = String(value ?? "");
  text = text.replace(/\bsk-[A-Za-z0-9_-]{6,}/g, "sk-<redacted>");
  text = text.replace(/(bearer\s+)[A-Za-z0-9._~+/=-]+/gi, "$1<redacted>");
  text = text.replace(/(api[_-]?key|token|secret|password)(["']?\s*[:=]\s*["']?)[^,\s"']+/gi, "$1$2<redacted>");
  return text;
}

export class BridgeError extends Error {
  constructor(code, message, options = {}) {
    super(sanitizeText(message), options);
    this.name = "BridgeError";
    this.code = code;
    this.details = options.details;
  }
}

export function formatUsageZero() {
  return {
    input: 0,
    output: 0,
    cacheRead: 0,
    cacheWrite: 0,
    totalTokens: 0,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
  };
}

export function normalizeUsage(tokenUsage) {
  if (!tokenUsage || typeof tokenUsage !== "object") return undefined;
  const input = Number(tokenUsage.uncachedInputTokens ?? 0) || 0;
  const output = Number(tokenUsage.outputTokens ?? 0) || 0;
  const cacheRead = Number(tokenUsage.cacheReadTokens ?? 0) || 0;
  const cacheWrite = Number(tokenUsage.cacheWriteTokens ?? 0) || 0;
  return {
    input,
    output,
    cacheRead,
    cacheWrite,
    totalTokens: input + output + cacheRead + cacheWrite,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
  };
}

export class BridgeLog {
  constructor(dir) {
    this.dir = dir;
    this.file = dir ? `${String(dir).replace(/[\\/]+$/, "")}/bridge.log.jsonl` : null;
  }
  async write(record) {
    if (!this.file) return;
    const allowed = {
      ts: new Date().toISOString(),
      runId: record.runId,
      openclawSessionHash: record.openclawSessionHash,
      model: record.model,
      runtime: "dsh",
      profile: record.profile,
      reasoningEffort: record.reasoningEffort,
      dshVersion: record.dshVersion,
      presetVersion: record.presetVersion,
      event: record.event,
      status: record.status,
      errorClass: record.errorClass,
      durationMs: record.durationMs,
      toolCallCount: record.toolCallCount,
      dshSessionId: record.dshSessionId,
    };
    const line = JSON.stringify(Object.fromEntries(Object.entries(allowed).filter(([, v]) => v !== undefined))) + "\n";
    try {
      const { mkdir, appendFile } = await import("node:fs/promises");
      await mkdir(this.dir, { recursive: true });
      await appendFile(this.file, line, "utf8");
    } catch {
      // Logging must never break a delegated run.
    }
  }
}


function jsonRequest(url, init, signal) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(url);
    } catch (error) {
      reject(error);
      return;
    }
    const transport = parsed.protocol === "https:" ? https : http;
    const body = init.body || "";
    const headers = { ...(init.headers || {}), "content-length": Buffer.byteLength(body) };
    const req = transport.request({
      protocol: parsed.protocol,
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
      path: `${parsed.pathname}${parsed.search || ""}`,
      method: init.method || "GET",
      headers,
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        let text = Buffer.concat(chunks).toString("utf8");
        try {
          resolve({ status: res.statusCode || 0, json: JSON.parse(text) });
        } catch {
          resolve({ status: res.statusCode || 0, json: undefined, text });
        }
      });
      res.on("error", reject);
    });
    req.on("error", reject);
    const onAbort = () => req.destroy(signal && signal.reason ? signal.reason : new Error("aborted"));
    if (signal) {
      if (signal.aborted) {
        onAbort();
        return;
      }
      signal.addEventListener("abort", onAbort, { once: true });
    }
    req.end(body);
  });
}

export class DshClient {
  constructor(baseUrl, log) {
    this.baseUrl = String(baseUrl || "http://127.0.0.1:3081").replace(/\/+$/, "");
    this.log = log;
  }
  async rpc(method, payload = {}, { signal, timeoutMs = 30000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error("dsh rpc timeout")), timeoutMs);
    const abort = () => controller.abort(signal && signal.reason ? signal.reason : new Error("aborted"));
    if (signal) {
      if (signal.aborted) abort();
      else signal.addEventListener("abort", abort, { once: true });
    }
    const rpcId = `ocdsh-${hashKey(new Date().toISOString(), Math.random().toString(), method)}`;
    let response;
    try {
      response = await jsonRequest(`${this.baseUrl}/api/${method}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ type: "client-request", rpcId, method, payload }),
      }, controller.signal);
    } catch (error) {
      throw this.classifyTransportError(error);
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener("abort", abort);
    }
    const body = response.json;
    if (response.status < 200 || response.status >= 300) {
      throw new BridgeError("DSH_START_FAILED", `DSH HTTP ${response.status} for ${method}: ${sanitizeText((body && body.message) || body)}`);
    }
    if (body?.type !== "server-response" || body?.rpcId !== rpcId) {
      throw new BridgeError("BRIDGE_PROTOCOL_ERROR", `DSH response envelope mismatch for ${method}`);
    }
    if (body.result?.ok !== true) {
      throw this.classifyRpcError(method, body.result?.error || {});
    }
    return body.result.value;
  }
  classifyTransportError(error) {
    const message = sanitizeText((error && error.message) || error);
    if (error && (error.name === "AbortError" || message.includes("abort"))) {
      return new BridgeError("CANCELLED", "DSH RPC aborted", { cause: error });
    }
    const lower = message.toLowerCase();
    if (lower.includes("fetch failed") || lower.includes("econnrefused") || lower.includes("enotfound") || lower.includes("network")) {
      return new BridgeError("DSH_NOT_FOUND", `DSH unavailable at ${this.baseUrl}: ${message}`, { cause: error });
    }
    return new BridgeError("DSH_START_FAILED", `DSH request failed: ${message}`, { cause: error });
  }
  classifyRpcError(method, err) {
    const code = String(err.code || "").toLowerCase();
    const message = sanitizeText(err.message || `DSH RPC ${method} failed`);
    if (code.includes("credential") || /credential|unauthorized|forbidden|api[ _-]?key|authentication/i.test(message)) {
      return new BridgeError("CREDENTIAL_ERROR", message);
    }
    if (code.includes("preset") || /preset/i.test(message)) {
      return new BridgeError("PRESET_NOT_FOUND", message);
    }
    if (code.includes("model") || /model/i.test(message)) {
      return new BridgeError("MODEL_NOT_AVAILABLE", message);
    }
    if (code.includes("session") && /not found|missing|unavailable/i.test(message)) {
      return new BridgeError("SESSION_RESUME_ERROR", message);
    }
    return new BridgeError("DSH_INTERNAL_ERROR", message);
  }
  async hostDescribe() { return this.rpc("host.describe", {}, { timeoutMs: 10000 }); }
  async listPresets() { return this.rpc("agentPreset.list", {}, { timeoutMs: 15000 }); }
  async listModels() { return this.rpc("llm.models", {}, { timeoutMs: 15000 }); }
  async listSessions() { return this.rpc("session.list", {}, { timeoutMs: 15000 }); }
  async createSession({ cwd, agentPreset }) { return this.rpc("session.create", { cwd, agentPreset }, { timeoutMs: 30000 }); }
  async selectModel({ sessionId, model, reasoningEffort }) {
    return this.rpc("session.selectModel", {
      sessionId,
      provider: DSH_PROVIDER,
      model,
      reasoningEffort,
    }, { timeoutMs: 30000 });
  }
  async prompt(sessionId, text, signal) {
    return this.rpc("session.prompt", {
      sessionId,
      mode: "queue",
      content: [{ type: "text", text }],
    }, { signal, timeoutMs: 30000 });
  }
  async cancel(sessionId, signal) {
    try {
      return await this.rpc("session.cancel", { sessionId }, { signal, timeoutMs: 10000 });
    } catch {
      return null;
    }
  }
  async history(sessionId, { beforeSeq, maxMessages = HISTORY_PAGE_SIZE, signal } = {}) {
    const payload = { sessionId, maxMessages };
    if (beforeSeq !== undefined) payload.beforeSeq = beforeSeq;
    return this.rpc("session.history", payload, { signal, timeoutMs: 20000 });
  }
  async health() {
    const out = {
      status: "HEALTHY",
      dshAvailable: false,
      providerAvailable: false,
      modelAvailable: false,
      presetAvailable: false,
      sessionBackendAvailable: false,
      details: {},
    };
    try {
      const host = await this.hostDescribe();
      out.dshAvailable = true;
      out.details.host = {
        version: host.version,
        provider: host.provider,
        model: host.model,
        attachedSessions: host.attachedSessions,
        canOpenPath: Boolean(host.canOpenPath),
      };
      const sessions = await this.listSessions();
      out.sessionBackendAvailable = Array.isArray(sessions.items);
      out.details.sessionCount = sessions.items?.length;
    } catch (error) {
      out.status = "UNAVAILABLE";
      out.details.hostError = error.code || "DSH_NOT_FOUND";
      out.details.hostMessage = error.message;
      return out;
    }
    try {
      const models = await this.listModels();
      const groups = models.groups || [];
      out.providerAvailable = groups.some((g) => g.id === DSH_PROVIDER);
      const flashOk = groups.some((g) => g.id === DSH_PROVIDER && (g.models || []).some((m) => m.id === "deepseek-v4-flash"));
      const proOk = groups.some((g) => g.id === DSH_PROVIDER && (g.models || []).some((m) => m.id === "deepseek-v4-pro"));
      out.modelAvailable = flashOk && proOk;
      out.details.models = groups.map((g) => ({ id: g.id, models: (g.models || []).map((m) => ({ id: m.id, efforts: m.reasoning?.efforts?.map((e) => e.id) })) }));
      if (!out.providerAvailable || !out.modelAvailable) out.status = "DEGRADED";
    } catch (error) {
      out.status = "DEGRADED";
      out.details.modelError = error.code || "MODEL_NOT_AVAILABLE";
    }
    try {
      const presets = await this.listPresets();
      const items = presets.presets || [];
      out.details.presets = items.map((p) => ({ id: p.id, broken: p.broken || null }));
      const anchored = items.some((p) => p.id === "anchored-standard" && !p.broken);
      const router = items.some((p) => p.id === "router-standard" && !p.broken);
      out.presetAvailable = anchored && router;
      if (!out.presetAvailable) out.status = "DEGRADED";
    } catch (error) {
      out.status = "DEGRADED";
      out.details.presetError = error.code || "PRESET_NOT_FOUND";
    }
    return out;
  }
}
