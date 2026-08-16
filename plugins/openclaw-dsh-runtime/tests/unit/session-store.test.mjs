import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import fs from "node:fs/promises";
import { SessionMapStore } from "../../dist/lib/session-store.js";

test("session map persists, resumes, and resets without raw openclaw session keys", async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "ocdsh-store-"));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const file = path.join(dir, "session-map.json");
  const store = new SessionMapStore(file);
  await store.load();
  await store.setEntry("k1", {
    profileId: "dsh-pro-anchored",
    openclawSessionHash: "h1",
    dshSessionId: "session-1",
    dshCwd: path.join(os.tmpdir(), "ocdsh-cwd"),
    dshPreset: "anchored-standard",
    dshModel: "deepseek-v4-pro",
    createdAt: "t",
    lastUsedAt: "t",
  });
  const store2 = new SessionMapStore(file);
  const data = await store2.load();
  assert.equal(data.sessions.k1.dshSessionId, "session-1");
  assert.equal(Object.keys(data.sessions).length, 1);
  await store2.removeForOpenclaw("h1");
  assert.equal(Object.keys(store2.data.sessions).length, 0);
  const raw = await fs.readFile(file, "utf8");
  assert.doesNotMatch(raw, /sessionKey/);
});
