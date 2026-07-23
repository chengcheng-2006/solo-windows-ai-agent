from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    parameter_schema: dict
    return_schema: dict
    risk_level: str
    approval_required: bool
    timeout_seconds: int
    path_policy: str
    redaction: str
    validation: str

    def document(self) -> dict:
        return asdict(self)


def _spec(name: str, risk: str, approval: bool, timeout: int, parameters: dict, returns: dict, path: str, validation: str) -> CapabilitySpec:
    return CapabilitySpec(name, parameters, returns, risk, approval, timeout, path, "recursive secret and PII redaction", validation)


CAPABILITIES = {
    item.name: item for item in (
        _spec("health", "R0", False, 5, {"nonce": "optional string"}, {"status": "string"}, "named pipe only", "status is PASS"),
        _spec("powershell.execute", "R2", True, 300, {"script": "string", "cwd": "path"}, {"exit_code": "int", "stdout": "string", "stderr": "string"}, "project cwd only; script via stdin", "exit code and optional validator"),
        _spec("process.start", "R2", True, 60, {"executable": "allowlisted path", "args": "array"}, {"pid": "int"}, "allowlisted executable", "process exists"),
        _spec("process.stop", "R2", True, 60, {"pid": "int"}, {"stopped": "bool"}, "n/a", "process absent"),
        _spec("filesystem.read", "R0", False, 30, {"path": "path"}, {"content": "string", "sha256": "hex"}, "project root", "hash reread"),
        _spec("filesystem.write", "R1", False, 30, {"path": "path", "content": "string"}, {"sha256": "hex"}, "runtime sandbox/workspaces/artifacts", "hash and exact reread"),
        _spec("filesystem.copy", "R1", False, 60, {"source": "path", "destination": "path"}, {"sha256": "hex"}, "project read; approved write roots", "source/destination hashes equal"),
        _spec("filesystem.move", "R2", True, 60, {"source": "path", "destination": "path"}, {"sha256": "hex"}, "project read; approved write roots", "source absent and destination hash"),
        _spec("filesystem.delete", "R3", True, 30, {"path": "path"}, {"deleted": "bool", "sha256": "hex"}, "runtime sandbox/workspaces/artifacts only", "original hash recorded and path absent"),
        _spec("archive.extract", "R2", True, 120, {"archive": "zip path", "destination": "path"}, {"files": "array"}, "zip-slip safe approved write root", "every output remains below destination"),
        _spec("browser.navigate", "R0", False, 60, {"url": "allowlisted URL"}, {"title": "string", "url": "string"}, "loopback/file sandbox/example.com", "DOM loaded"),
        _spec("browser.click", "R1", False, 60, {"selector": "string"}, {"status": "string"}, "active isolated browser", "target state changed"),
        _spec("browser.type", "R1", False, 60, {"selector": "string", "text": "string"}, {"status": "string"}, "active isolated browser", "DOM value equals input"),
        _spec("browser.download", "R2", True, 180, {"selector": "string", "destination": "path"}, {"sha256": "hex"}, "approved write root", "download hash"),
        _spec("browser.screenshot", "R0", False, 60, {"path": "path"}, {"sha256": "hex"}, "artifacts/runtime sandbox", "PNG dimensions and hash"),
        _spec("windows.uia.inspect", "R0", False, 30, {"pid": "int"}, {"controls": "array"}, "interactive user session", "UIA tree nonempty"),
        _spec("windows.uia.click", "R2", True, 30, {"pid": "int", "automation_id": "string"}, {"status": "string"}, "interactive user session", "UIA state change"),
        _spec("windows.uia.type", "R2", True, 30, {"pid": "int", "automation_id": "string", "text": "string"}, {"status": "string"}, "interactive user session", "ValuePattern reread"),
        _spec("ocr.read", "R0", False, 120, {"path": "image path"}, {"text": "string", "lines": "array"}, "project root", "confidence and expected-text validator"),
        _spec("screenshot.capture", "R0", False, 30, {"path": "path", "monitor": "int"}, {"sha256": "hex", "width": "int", "height": "int"}, "artifacts/runtime sandbox", "PNG dimensions and hash"),
        _spec("document.read", "R0", False, 30, {"path": "txt/md/json path"}, {"content": "string", "sha256": "hex"}, "project root", "hash reread"),
        _spec("document.write", "R1", False, 30, {"path": "txt/md/json path", "content": "string"}, {"sha256": "hex"}, "approved write roots", "hash and exact reread"),
        _spec("gpu.inference", "R1", False, 300, {"model": "registered local model", "prompt": "string"}, {"response": "string"}, "localhost Ollama only", "model health and nonempty response"),
        _spec("codex.run", "R2", True, 1800, {"task_id": "string", "repo": "path", "prompt": "string"}, {"state": "string", "diff": "string"}, "isolated Git worktree", "validator exit code"),
        _spec("hermes.plan", "R0", False, 300, {"goal": "paios.hermes.goal.v1"}, {"plan": "paios.hermes.plan.v1"}, "no-tool ACP", "Pydantic schema and policy validation"),
    )
}
