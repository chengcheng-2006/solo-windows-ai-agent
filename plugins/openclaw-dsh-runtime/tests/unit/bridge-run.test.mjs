import test from "node:test";
import assert from "node:assert/strict";
import { EventAccumulator, DelegatedRun } from "../../dist/lib/bridge-run.js";

function makeRun(overrides = {}) {
  return new DelegatedRun({
    config: {
      contextTransferPolicy: "selected",
      fallbackOnRuntimeFailure: "fail",
      timeouts: { startupMs: 1000, executionMs: 1000, idleMs: 1000 },
      profiles: {},
    },
    profile: {
      harnessId: "dsh-pro-anchored",
      model: "deepseek-v4-pro",
      presetId: "anchored-standard",
      reasoningEffort: "max",
    },
    params: {
      runId: "r1",
      sessionId: "s1",
      sessionKey: "agent:main:test",
      workspaceDir: process.cwd(),
      cwd: process.cwd(),
      prompt: "raw task",
      timeoutMs: 1000,
    },
    client: {},
    store: { load: async () => ({ sessions: {} }), entry: () => undefined, setEntry: async () => {} },
    logger: { write: async () => {} },
    ...overrides,
  });
}

test("request/header parses DSH durable header shape and omits CoT", () => {
  const acc = new EventAccumulator();
  acc.process({
    type: "request/header",
    seq: 9,
    data: {
      reason: "initial",
      header: {
        config: { provider: "deepseek-official", model: "deepseek-v4-pro", reasoningEffort: "max" },
        tools: [{ name: "bash" }, { name: "str_replace_editor" }],
      },
    },
  });
  assert.deepEqual(acc.requestHeaders[0].tools, ["bash", "str_replace_editor"]);
  assert.equal(acc.requestHeaders[0].reasoningEffort, "max");
});

test("assistant message extracts text blocks only; reasoning chunks are counted not kept", () => {
  const acc = new EventAccumulator();
  acc.process({ type: "assistant/message", seq: 1, data: { message: { content: [{ type: "reasoning", text: "secret-cot" }, { type: "text", text: "PASS" }] } } });
  acc.process({ type: "reasoning-chunks", seq: 2, data: { chunks: ["do-not-keep"] } });
  assert.deepEqual(acc.assistantTexts, ["PASS"]);
  assert.equal(acc.reasoningChunkCount, 1);
  assert.doesNotMatch(JSON.stringify(acc), /secret-cot|do-not-keep/);
});

test("tool result inherits tool name from call id without forwarding arguments", () => {
  const acc = new EventAccumulator();
  acc.process({ type: "tool/call", seq: 3, data: { callId: "c1", name: "bash", arguments: { command: "echo secret" } } });
  acc.process({ type: "tool/result", seq: 4, data: { callId: "c1", message: {} } });
  assert.equal(acc.toolEvents[1].toolName, "bash");
  assert.doesNotMatch(JSON.stringify(acc.toolEvents), /echo secret/);
});

test("context transfer policies keep DSH input boundary", () => {
  const minimal = makeRun({ config: { ...makeRun().config, contextTransferPolicy: "minimal" } });
  assert.equal(minimal.buildPrompt(), "raw task");
  const selected = makeRun({ config: { ...makeRun().config, contextTransferPolicy: "selected" } });
  assert.match(selected.buildPrompt(), /Workspace:/);
  assert.match(selected.buildPrompt(), /raw task/);
  assert.doesNotMatch(selected.buildPrompt(), /SOUL\.md|TOOLS\.md|system prompt/i);
  const full = makeRun({
    config: { ...makeRun().config, contextTransferPolicy: "full" },
    params: { ...makeRun().params, transcriptPrompt: "owner-selected transcript" },
  });
  assert.match(full.buildPrompt(), /owner-selected transcript/);
});

test("abort signal propagates to DSH session.cancel", async () => {
  const cancelled = [];
  const controller = new AbortController();
  const run = makeRun({
    params: { ...makeRun().params, abortSignal: controller.signal, timeoutMs: 60000 },
    client: {
      history: async () => ({ events: [], hasMore: false }),
      listSessions: async () => ({ items: [{ sessionId: "s", running: true }] }),
      cancel: async (id) => { cancelled.push(id); return null; },
    },
  });
  run.dshSessionId = "session-cancel-test";
  setTimeout(() => controller.abort(new Error("owner cancel")), 20);
  const result = await run.waitForTurnEnd({ signal: controller.signal });
  assert.equal(result, null);
  assert.equal(run.cancelledByUser, true);
  assert.deepEqual(cancelled, ["session-cancel-test"]);
});
