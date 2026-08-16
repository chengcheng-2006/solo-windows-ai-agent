import path from "node:path";
import fs from "node:fs/promises";

export class SessionMapStore {
  constructor(file) {
    this.file = file;
    this.data = { version: 1, sessions: {} };
    this.loadPromise = null;
  }
  async load() {
    if (this.loadPromise) return this.loadPromise;
    this.loadPromise = (async () => {
      try {
        const raw = await fs.readFile(this.file, "utf8");
        const parsed = JSON.parse(raw);
        if (parsed && parsed.version === 1 && parsed.sessions && typeof parsed.sessions === "object") {
          this.data = parsed;
        }
      } catch (error) {
        if (!error || error.code !== "ENOENT") {
          this.data = { version: 1, sessions: {} };
          await this.persist();
        }
      }
      return this.data;
    })();
    return this.loadPromise;
  }
  async persist() {
    await fs.mkdir(path.dirname(this.file), { recursive: true });
    const tmp = `${this.file}.${process.pid}.${Date.now()}.tmp`;
    await fs.writeFile(tmp, JSON.stringify(this.data, null, 2), "utf8");
    try {
      await fs.rename(tmp, this.file);
    } catch {
      await fs.rm(this.file, { force: true });
      await fs.rename(tmp, this.file);
    }
  }
  entry(key) {
    return this.data.sessions[key];
  }
  async setEntry(key, entry) {
    this.data.sessions[key] = entry;
    await this.persist();
  }
  async removeForOpenclaw(openclawSessionHash, profileId) {
    let changed = false;
    for (const [key, entry] of Object.entries(this.data.sessions)) {
      if (entry && entry.openclawSessionHash === openclawSessionHash) {
        if (!profileId || entry.profileId === profileId) {
          delete this.data.sessions[key];
          changed = true;
        }
      }
    }
    if (changed) await this.persist();
  }
  listEntries() {
    return Object.values(this.data.sessions || {});
  }
}
