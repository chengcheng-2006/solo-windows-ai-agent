import path from "node:path";
import { BridgeError, sanitizeText, formatUsageZero, normalizeUsage, hashKey, DSH_VERSION_MIN } from "./dsh-client.js";

export const POLL_INTERVAL_MS = 1000;
export const MAX_HISTORY_PAGES = 25;

function nowIso() {
  return new Date().toISOString();
}

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) {
      reject(new BridgeError("CANCELLED", "aborted"));
      return;
    }
    const timer = setTimeout(() => {
      if (signal) signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new BridgeError("CANCELLED", "aborted"));
    };
    if (signal) signal.addEventListener("abort", onAbort, { once: true });
  });
}

function extractMessageText(data) {
  if (!data || typeof data !== "object") return "";
  const message = data.message && typeof data.message === "object" ? data.message : data;
  if (Array.isArray(message.content)) {
    return message.content
      .filter((block) => block && block.type === "text" && typeof block.text === "string")
      .map((block) => block.text)
      .join("");
  }
  if (typeof message.content === "string") return message.content;
  if (typeof message.text === "string") return message.text;
  return "";
}

function eventToolName(data) {
  if (!data || typeof data !== "object") return "unknown";
  return data.name || data.toolName || data.tool || "unknown";
}

function safeToolEventData(data) {
  return {
    toolName: eventToolName(data),
    callId: typeof data.id === "string" ? data.id : typeof data.callId === "string" ? data.callId : undefined,
  };
}

export class EventAccumulator {
  constructor() {
    this.seenSeqs = new Set();
    this.assistantTexts = [];
    this.lastAssistantText = "";
    this.toolEvents = [];
    this.toolCallCount = 0;
    this.toolResultCount = 0;
    this.reasoningChunkCount = 0;
    this.requestHeaders = [];
    this.turnEnd = null;
    this.lastSeq = -1;
    this.callNames = new Map();
  }
  process(event, { onPartialReply, onAgentEvent } = {}) {
    if (!event || typeof event !== "object") return;
    const seq = Number(event.seq);
    if (Number.isFinite(seq)) {
      if (this.seenSeqs.has(seq)) return;
      this.seenSeqs.add(seq);
      if (seq > this.lastSeq) this.lastSeq = seq;
    }
    const data = event.data && typeof event.data === "object" ? event.data : {};
    switch (event.type) {
      case "assistant/message": {
        const text = extractMessageText(data);
        if (text && text !== this.lastAssistantText) {
          this.lastAssistantText = text;
          this.assistantTexts.push(text);
          if (onPartialReply) {
            try {
              const out = onPartialReply({ text, replace: true });
              if (out && typeof out.catch === "function") out.catch(() => {});
            } catch {}
          }
        }
        break;
      }
      case "tool/call": {
        this.toolCallCount += 1;
        const info = safeToolEventData(data);
        if (info.callId && info.toolName !== "unknown") this.callNames.set(info.callId, info.toolName);
        this.toolEvents.push({ seq, type: "call", ...info });
        if (onAgentEvent) {
          try {
            const out = onAgentEvent({
              stream: "tool",
              data: { toolName: info.toolName, status: "started", callId: info.callId },
            });
            if (out && typeof out.catch === "function") out.catch(() => {});
          } catch {}
        }
        break;
      }
      case "tool/result": {
        this.toolResultCount += 1;
        const info = safeToolEventData(data);
        if (info.toolName === "unknown" && info.callId && this.callNames.has(info.callId)) {
          info.toolName = this.callNames.get(info.callId);
        }
        this.toolEvents.push({ seq, type: "result", ...info });
        if (onAgentEvent) {
          try {
            const out = onAgentEvent({
              stream: "tool",
              data: { toolName: info.toolName, status: "completed", callId: info.callId },
            });
            if (out && typeof out.catch === "function") out.catch(() => {});
          } catch {}
        }
        break;
      }
      case "request/header": {
        const header = data.header && typeof data.header === "object" ? data.header : data;
        this.requestHeaders.push({
          reason: typeof data.reason === "string" ? data.reason : undefined,
          model: header.config?.model,
          provider: header.config?.provider,
          reasoningEffort: header.config?.reasoningEffort,
          tools: Array.isArray(header.tools) ? header.tools.map((tool) => (typeof tool === "string" ? tool : tool?.name)).filter(Boolean) : [],
        });
        break;
      }
      case "reasoning-chunks": {
        this.reasoningChunkCount += 1;
        break;
      }
      case "turn/end": {
        this.turnEnd = { seq, data: data.reason || data };
        break;
      }
      default:
        break;
    }
  }
}

export class DelegatedRun {
  constructor({ config, profile, params, client, store, logger }) {
    this.config = config;
    this.profile = profile;
    this.params = params;
    this.client = client;
    this.store = store;
    this.logger = logger;
    this.runId = params.runId || `run-${hashKey(nowIso(), Math.random().toString())}`;
    this.openclawSessionHash = hashKey(params.sessionKey || params.sessionId || "unscoped");
    this.startedAt = Date.now();
    this.dshSessionId = null;
    this.baselineSeq = -1;
    this.accumulator = new EventAccumulator();
    this.cancelledByUser = false;
    this.cancelledByTimeout = false;
  }
  async log(event, extra = {}) {
    await this.logger.write({
      runId: this.runId,
      openclawSessionHash: this.openclawSessionHash,
      model: this.profile.model,
      profile: this.profile.harnessId,
      reasoningEffort: this.profile.reasoningEffort,
      dshVersion: DSH_VERSION_MIN,
      presetVersion: this.profile.presetId,
      dshSessionId: this.dshSessionId,
      event,
      ...extra,
    });
  }
  mappingKey() {
    return hashKey("openclaw-session", this.openclawSessionHash, this.profile.harnessId);
  }
  async ensureSession(cwd) {
    const key = this.mappingKey();
    await this.store.load();
    let entry = this.store.entry(key);
    const wantedCwd = path.resolve(cwd || this.params.workspaceDir || process.cwd());
    if (entry && entry.dshCwd !== wantedCwd) entry = null;
    if (entry) {
      try {
        const list = await this.client.listSessions();
        const exists = (list.items || []).some((s) => s.sessionId === entry.dshSessionId);
        if (!exists) entry = null;
      } catch (error) {
        throw new BridgeError("SESSION_RESUME_ERROR", `Cannot verify DSH session mapping: ${error.message}`, { cause: error });
      }
    }
    if (!entry) {
      const created = await this.client.createSession({ cwd: wantedCwd, agentPreset: this.profile.presetId });
      entry = {
        profileId: this.profile.harnessId,
        openclawSessionHash: this.openclawSessionHash,
        dshSessionId: created.sessionId,
        dshCwd: wantedCwd,
        dshPreset: created.agentPreset || this.profile.presetId,
        dshModel: this.profile.model,
        createdAt: nowIso(),
        lastUsedAt: nowIso(),
      };
      await this.store.setEntry(key, entry);
      await this.log("session.created", { dshSessionId: created.sessionId, status: "ok" });
    } else {
      entry.lastUsedAt = nowIso();
      entry.dshModel = this.profile.model;
      entry.dshPreset = this.profile.presetId;
      await this.store.setEntry(key, entry);
      await this.log("session.resumed", { dshSessionId: entry.dshSessionId, status: "ok" });
    }
    this.dshSessionId = entry.dshSessionId;
    const selected = await this.client.selectModel({
      sessionId: this.dshSessionId,
      model: this.profile.model,
      reasoningEffort: this.profile.reasoningEffort,
    });
    if (!selected || !selected.selected) {
      throw new BridgeError("MODEL_NOT_AVAILABLE", `DSH did not confirm model selection for ${this.profile.model}`);
    }
    await this.log("model.selected", {
      dshSessionId: this.dshSessionId,
      model: selected.selected.model,
      provider: selected.selected.provider,
      reasoningEffort: selected.selected.reasoningEffort,
      status: "ok",
    });
    return entry;
  }
  async captureBaseline() {
    try {
      const page = await this.client.history(this.dshSessionId, { maxMessages: 200 });
      for (const item of page.events || []) {
        const seq = Number(item?.event?.seq);
        if (Number.isFinite(seq) && seq > this.baselineSeq) this.baselineSeq = seq;
      }
    } catch {
      // Fresh sessions can have no history yet; baseline stays -1.
    }
  }
  async fetchEvents({ pages = MAX_HISTORY_PAGES, signal } = {}) {
    const collected = [];
    let beforeSeq;
    let hasMore = true;
    for (let i = 0; i < pages && hasMore; i += 1) {
      const page = await this.client.history(this.dshSessionId, {
        beforeSeq,
        maxMessages: 200,
        signal,
      });
      const events = (page.events || []).map((item) => item.event).filter(Boolean);
      if (events.length === 0) break;
      collected.push(...events);
      const seqs = events.map((e) => Number(e.seq)).filter(Number.isFinite);
      if (seqs.length === 0) break;
      const oldest = Math.min(...seqs);
      hasMore = page.hasMore === true;
      beforeSeq = oldest;
      if (oldest <= this.baselineSeq) break;
    }
    return collected
      .filter((event) => Number(event.seq) > this.baselineSeq)
      .sort((a, b) => Number(a.seq) - Number(b.seq));
  }
  async waitForTurnEnd({ signal }) {
    const executionBudget = Math.min(
      Number(this.params.timeoutMs) || this.config.timeouts.executionMs,
      this.config.timeouts.executionMs,
    );
    const deadline = Date.now() + executionBudget;
    let lastActivity = Date.now();
    while (Date.now() < deadline) {
      if (signal && signal.aborted) {
        this.cancelledByUser = true;
        await this.client.cancel(this.dshSessionId);
        return null;
      }
      let events = [];
      try {
        events = await this.fetchEvents({ pages: 1, signal });
      } catch (error) {
        if (error && error.code === "CANCELLED") throw error;
        // Transient history read; keep polling.
      }
      for (const event of events) {
        this.accumulator.process(event, {
          onPartialReply: this.params.onPartialReply,
          onAgentEvent: this.params.onAgentEvent,
        });
        if (event.type === "turn/end") return event;
      }
      if (events.length > 0) lastActivity = Date.now();
      if (Date.now() - lastActivity > this.config.timeouts.idleMs) {
        this.cancelledByTimeout = true;
        await this.client.cancel(this.dshSessionId);
        throw new BridgeError("RUNTIME_TIMEOUT", `DSH turn exceeded idle timeout ${this.config.timeouts.idleMs}ms`);
      }
      try {
        const list = await this.client.listSessions();
        const row = (list.items || []).find((s) => s.sessionId === this.dshSessionId);
        if (row && row.running === false) {
          const finalEvents = await this.fetchEvents({ signal });
          for (const event of finalEvents) {
            this.accumulator.process(event, {
              onPartialReply: this.params.onPartialReply,
              onAgentEvent: this.params.onAgentEvent,
            });
            if (event.type === "turn/end") return event;
          }
          return this.accumulator.turnEnd ? { type: "turn/end", data: this.accumulator.turnEnd.data } : null;
        }
      } catch {
        // Keep polling.
      }
      try {
        await sleep(POLL_INTERVAL_MS, signal);
      } catch (error) {
        if (error && error.code === "CANCELLED") break;
        throw error;
      }
    }
    if (signal && signal.aborted) {
      this.cancelledByUser = true;
      await this.client.cancel(this.dshSessionId);
      return null;
    }
    this.cancelledByTimeout = true;
    await this.client.cancel(this.dshSessionId);
    throw new BridgeError("RUNTIME_TIMEOUT", `DSH turn exceeded execution timeout ${executionBudget}ms`);
  }
  async collectFinalUsage() {
    try {
      const list = await this.client.listSessions();
      const row = (list.items || []).find((s) => s.sessionId === this.dshSessionId);
      const projections = row?.projections?.values || {};
      return {
        usage: normalizeUsage(projections.tokenUsage),
        stats: projections.sessionStats,
      };
    } catch {
      return { usage: undefined, stats: undefined };
    }
  }
  buildPrompt() {
    const policy = this.config.contextTransferPolicy;
    const cwd = path.resolve(this.params.cwd || this.params.workspaceDir || process.cwd());
    const task = String(this.params.prompt || "").trim();
    if (policy === "minimal") return task;
    if (policy === "full") {
      const parts = [];
      if (this.params.transcriptPrompt && String(this.params.transcriptPrompt).trim()) {
        parts.push(String(this.params.transcriptPrompt).trim());
      }
      parts.push(`Workspace: ${cwd}`);
      if (task) parts.push(task);
      return parts.join("\n\n");
    }
    return `Workspace: ${cwd}\n\nTask:\n${task}`;
  }
  async run() {
    const startupDeadline = Date.now() + this.config.timeouts.startupMs;
    const guardStartup = async (fn) => {
      if (Date.now() > startupDeadline) throw new BridgeError("RUNTIME_TIMEOUT", "DSH startup timeout exceeded");
      return fn();
    };
    const cwd = path.resolve(this.params.cwd || this.params.workspaceDir || process.cwd());
    await guardStartup(() => this.ensureSession(cwd));
    await guardStartup(() => this.captureBaseline());
    if (this.params.images && this.params.images.length > 0) {
      throw new BridgeError("BRIDGE_PROTOCOL_ERROR", "Image attachments are not supported by this DSH bridge version; send text tasks or use a native OpenClaw turn.");
    }
    const promptText = this.buildPrompt();
    await this.log("turn.prompted", { status: "ok" });
    const accepted = await this.client.prompt(this.dshSessionId, promptText, this.params.abortSignal);
    if (!accepted || accepted.accepted !== true) {
      throw new BridgeError("BRIDGE_PROTOCOL_ERROR", "DSH did not accept session.prompt");
    }
    const turnEndEvent = await this.waitForTurnEnd({ signal: this.params.abortSignal });
    if (this.cancelledByUser || (this.params.abortSignal && this.params.abortSignal.aborted)) {
      return this.buildAbortedResult("user");
    }
    if (!turnEndEvent) {
      const finalEvents = await this.fetchEvents({});
      for (const event of finalEvents) {
        this.accumulator.process(event, {
          onPartialReply: this.params.onPartialReply,
          onAgentEvent: this.params.onAgentEvent,
        });
      }
      if (this.accumulator.turnEnd) {
        return this.buildCompletedResult();
      }
      throw new BridgeError("BRIDGE_PROTOCOL_ERROR", "DSH turn finished without a durable turn/end event");
    }
    const data = turnEndEvent.data && typeof turnEndEvent.data === "object" ? turnEndEvent.data : {};
    const reason = data.reason && typeof data.reason === "object" ? data.reason : data;
    const reasonKind = reason?.kind;
    if (reasonKind && reasonKind !== "completed") {
      const message = sanitizeText(reason?.error?.message || reason?.message || `DSH turn ended with ${reasonKind}`);
      throw new BridgeError("DSH_INTERNAL_ERROR", message, { details: { reasonKind } });
    }
    return this.buildCompletedResult();
  }
  buildCompletedResult() {
    const lastText = this.accumulator.lastAssistantText;
    const usage = formatUsageZero();
    const assistantMessage = lastText ? {
      role: "assistant",
      content: [{ type: "text", text: lastText }],
      api: "openai-completions",
      provider: "deepseek",
      model: this.profile.model,
      responseModel: this.profile.model,
      usage,
      stopReason: "stop",
      timestamp: Date.now(),
    } : undefined;
    const toolMessages = this.accumulator.toolEvents.map((event) => ({
      role: "custom",
      customType: "dsh-tool",
      content: `[DSH ${event.type}] ${event.toolName}`,
      display: false,
      details: { dshEventType: event.type, toolName: event.toolName },
      timestamp: Date.now(),
    }));
    const messagesSnapshot = [
      {
        role: "user",
        content: this.buildPrompt(),
        timestamp: Date.now(),
      },
      ...toolMessages,
      ...(assistantMessage ? [assistantMessage] : []),
    ];
    const startedCount = this.accumulator.toolCallCount;
    const completedCount = this.accumulator.toolResultCount;
    const hadPotentialSideEffects = startedCount > 0;
    return {
      aborted: false,
      externalAbort: false,
      timedOut: false,
      idleTimedOut: false,
      timedOutDuringCompaction: false,
      timedOutDuringToolExecution: false,
      timedOutByRunBudget: false,
      promptError: null,
      promptErrorSource: null,
      sessionIdUsed: this.params.sessionId,
      sessionFileUsed: this.params.sessionFile,
      agentHarnessId: this.profile.harnessId,
      messagesSnapshot,
      assistantTexts: [...this.accumulator.assistantTexts],
      lastAssistant: assistantMessage,
      currentAttemptAssistant: assistantMessage,
      toolMetas: this.accumulator.toolEvents.filter((event) => event.type === "call").map((event) => ({ toolName: event.toolName, meta: "dsh:tool-call" })),
      didSendViaMessagingTool: false,
      didDeliverSourceReplyViaMessageTool: false,
      messagingToolSentTexts: [],
      messagingToolSentMediaUrls: [],
      messagingToolSentTargets: [],
      messagingToolSourceReplyPayloads: [],
      toolMediaUrls: [],
      toolAudioAsVoice: false,
      successfulCronAdds: 0,
      cloudCodeAssistFormatError: false,
      attemptUsage: usage,
      replayMetadata: { hadPotentialSideEffects, replaySafe: !hadPotentialSideEffects },
      itemLifecycle: { startedCount, completedCount, activeCount: Math.max(0, startedCount - completedCount) },
      yieldDetected: false,
    };
  }
  buildAbortedResult(source) {
    const timedOut = source === "timeout";
    return {
      aborted: true,
      externalAbort: source === "user",
      timedOut,
      idleTimedOut: timedOut,
      timedOutDuringCompaction: false,
      timedOutDuringToolExecution: false,
      timedOutByRunBudget: false,
      promptError: timedOut ? new BridgeError("RUNTIME_TIMEOUT", "DSH run timed out") : null,
      promptErrorSource: timedOut ? "prompt" : null,
      sessionIdUsed: this.params.sessionId,
      sessionFileUsed: this.params.sessionFile,
      agentHarnessId: this.profile.harnessId,
      messagesSnapshot: [],
      assistantTexts: [],
      lastAssistant: undefined,
      currentAttemptAssistant: undefined,
      toolMetas: [],
      didSendViaMessagingTool: false,
      didDeliverSourceReplyViaMessageTool: false,
      messagingToolSentTexts: [],
      messagingToolSentMediaUrls: [],
      messagingToolSentTargets: [],
      messagingToolSourceReplyPayloads: [],
      cloudCodeAssistFormatError: false,
      attemptUsage: formatUsageZero(),
      replayMetadata: { hadPotentialSideEffects: true, replaySafe: false },
      itemLifecycle: { startedCount: 0, completedCount: 0, activeCount: 0 },
    };
  }
}
