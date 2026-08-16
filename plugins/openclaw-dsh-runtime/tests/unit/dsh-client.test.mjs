import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { DshClient, BridgeError, sanitizeText } from "../../dist/lib/dsh-client.js";

function startServer(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

test("sanitizeText removes api key shapes", () => {
  const out = sanitizeText("fail with sk-TESTNOTAKEY and Bearer abc.def and api_key=deadbeef");
  assert.match(out, /sk-<redacted>/);
  assert.match(out, /Bearer <redacted>/i);
  assert.match(out, /api_key=<redacted>/i);
  assert.doesNotMatch(out, /sk-abcdef/);
});

test("rpc happy path parses server-response envelope", async (t) => {
  const server = await startServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const msg = JSON.parse(body);
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ type: "server-response", rpcId: msg.rpcId, result: { ok: true, value: { hello: 1 } } }));
    });
  });
  t.after(() => server.close());
  const client = new DshClient(`http://127.0.0.1:${server.address().port}`);
  assert.deepEqual(await client.rpc("host.describe", {}), { hello: 1 });
});

test("rpc classifies preset and credential errors", async (t) => {
  const server = await startServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const msg = JSON.parse(body);
      const code = msg.method === "agentPreset.list" ? "preset-not-found" : "credential";
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ type: "server-response", rpcId: msg.rpcId, result: { ok: false, error: { code, message: "bad thing" } } }));
    });
  });
  t.after(() => server.close());
  const client = new DshClient(`http://127.0.0.1:${server.address().port}`);
  await assert.rejects(() => client.listPresets(), (e) => e instanceof BridgeError && e.code === "PRESET_NOT_FOUND");
  await assert.rejects(() => client.hostDescribe(), (e) => e instanceof BridgeError && e.code === "CREDENTIAL_ERROR");
});

test("transport failure maps to DSH_NOT_FOUND", async () => {
  const client = new DshClient("http://127.0.0.1:1");
  await assert.rejects(() => client.hostDescribe(), (e) => e instanceof BridgeError && e.code === "DSH_NOT_FOUND");
});
