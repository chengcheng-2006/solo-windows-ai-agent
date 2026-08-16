import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { DshClient } from "../../dist/lib/dsh-client.js";

const DSH_URL = process.env.OCDSH_TEST_DSH_URL || "http://127.0.0.1:3081";
const TEST_CWD = process.env.OCDSH_TEST_CWD || path.join(os.tmpdir(), "ocdsh-integration");
const client = new DshClient(DSH_URL);

test("DSH health is HEALTHY with both bridge presets", async () => {
  const health = await client.health();
  assert.equal(health.dshAvailable, true);
  assert.equal(health.providerAvailable, true);
  assert.equal(health.modelAvailable, true);
  assert.equal(health.sessionBackendAvailable, true);
  assert.equal(health.status, "HEALTHY");
  const presetIds = new Set((health.details.presets || []).map((p) => p.id));
  assert.ok(presetIds.has("anchored-standard"));
  assert.ok(presetIds.has("router-standard"));
});

test("DSH model registry exposes off/high/max for both V4 models", async () => {
  const models = await client.listModels();
  const groups = models.groups || [];
  const deepseek = groups.find((g) => g.id === "deepseek-official");
  assert.ok(deepseek);
  const byId = Object.fromEntries(deepseek.models.map((m) => [m.id, m]));
  for (const id of ["deepseek-v4-flash", "deepseek-v4-pro"]) {
    assert.ok(byId[id], `missing ${id}`);
    const efforts = byId[id].reasoning?.efforts?.map((e) => e.id) || [];
    assert.deepEqual([...efforts].sort(), ["high", "max", "off"].sort());
  }
});

test("session create/selectModel works without sending a prompt", async () => {
  const created = await client.createSession({
    cwd: TEST_CWD,
    agentPreset: "minimal",
  });
  assert.match(created.sessionId, /^session-/);
  const selected = await client.selectModel({
    sessionId: created.sessionId,
    model: "deepseek-v4-flash",
    reasoningEffort: "max",
  });
  assert.equal(selected.selected.model, "deepseek-v4-flash");
  assert.equal(selected.selected.reasoningEffort, "max");
});
