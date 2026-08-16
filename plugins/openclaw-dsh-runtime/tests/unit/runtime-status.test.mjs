import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import pluginEntry from "../../dist/index.js";

test("plugin registers two DSH harnesses and runtime-status command", async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "ocdsh-status-"));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));

  const harnesses = [];
  const commands = [];
  const api = {
    id: pluginEntry.id,
    name: pluginEntry.name,
    config: {},
    pluginConfig: {
      enabled: true,
      dshBaseUrl: process.env.OCDSH_TEST_DSH_URL || "http://127.0.0.1:3081",
      stateDir: path.join(dir, "state"),
      logDir: path.join(dir, "logs"),
    },
    logger: { warn() {}, info() {} },
    registerAgentHarness(harness) { harnesses.push(harness); },
    registerCommand(command) { commands.push(command); },
  };
  pluginEntry.register(api);
  assert.deepEqual(harnesses.map((h) => h.id).sort(), ["dsh-flash-router", "dsh-pro-anchored"]);
  assert.deepEqual(commands.map((c) => c.name), ["runtime-status"]);
  const flash = harnesses.find((h) => h.id === "dsh-flash-router");
  const pro = harnesses.find((h) => h.id === "dsh-pro-anchored");
  assert.equal(flash.supports({ provider: "deepseek", modelId: "deepseek-v4-flash" }).supported, true);
  assert.equal(flash.supports({ provider: "deepseek", modelId: "deepseek-v4-pro" }).supported, false);
  assert.equal(pro.supports({ provider: "deepseek", modelId: "deepseek-v4-pro" }).supported, true);
  assert.equal(pro.supports({ provider: "anthropic", modelId: "claude-x" }).supported, false);
  const reply = await commands[0].handler({});
  const text = reply.text;
  assert.match(text, /Pro profile: deepseek-v4-pro/);
  assert.match(text, /Flash profile: deepseek-v4-flash/);
  assert.match(text, /Health:/);
});
