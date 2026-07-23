from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
CHROMIUM = ROOT / "models" / "playwright" / "chromium-1208" / "chrome-win64" / "chrome.exe"
SANDBOX = ROOT / "tests" / "runtime-sandbox"
ARTIFACTS = ROOT / "artifacts" / "browser"
HIGH_RISK_ACTIONS = {"login", "payment", "publish", "delete", "send", "submit", "account_change", "sensitive_upload"}


class BrowserWorker:
    def __init__(self, executable: Path = CHROMIUM) -> None:
        self.executable = executable.resolve(strict=True)

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme == "file":
            path = Path(unquote(parsed.path.lstrip("/") if parsed.path[2:3] == ":" else parsed.path)).resolve(strict=True)
            if str(path).upper().startswith("E:\\") or not path.is_relative_to(SANDBOX.resolve()):
                raise ValueError("file URL is outside the runtime sandbox")
            return
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("unsupported browser URL scheme")
        if parsed.hostname not in {"127.0.0.1", "localhost", "example.com"}:
            raise ValueError("browser destination is not allowlisted")

    def run(self, task_id: str, url: str, actions: list[dict], timeout_ms: int = 30_000) -> dict:
        self._validate_url(url)
        if not 1_000 <= timeout_ms <= 120_000:
            raise ValueError("browser timeout outside allowed range")
        artifact_dir = ARTIFACTS / task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        profile_dir = ROOT / "state" / "browser" / task_id
        temporary_dir = ROOT / "state" / "browser" / "temp"
        profile_dir.mkdir(parents=True, exist_ok=True)
        temporary_dir.mkdir(parents=True, exist_ok=True)
        screenshot = artifact_dir / "screenshot.png"
        extracted: dict[str, object] = {}
        action_results: list[dict] = []
        original_temp = os.environ.get("TEMP")
        original_tmp = os.environ.get("TMP")
        os.environ["TEMP"] = str(temporary_dir)
        os.environ["TMP"] = str(temporary_dir)
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir), headless=True, executable_path=str(self.executable), accept_downloads=True,
                    env={**os.environ, "TEMP": str(temporary_dir), "TMP": str(temporary_dir)},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(timeout_ms)
                response = page.goto(url, wait_until="domcontentloaded")
                for index, action in enumerate(actions):
                    kind = action.get("action")
                    risk_reason = action.get("risk_reason")
                    if risk_reason in HIGH_RISK_ACTIONS and not action.get("approval_bound"):
                        raise PermissionError("high-risk browser action requires bound approval")
                    if kind == "click":
                        page.locator(action["selector"]).click()
                    elif kind == "type":
                        page.locator(action["selector"]).fill(action["text"])
                    elif kind == "extract_text":
                        value = page.locator(action["selector"]).inner_text()
                        extracted[action.get("name", f"text_{index}")] = value
                    elif kind == "extract_attribute":
                        value = page.locator(action["selector"]).get_attribute(action["attribute"])
                        extracted[action.get("name", f"attribute_{index}")] = value
                    elif kind == "screenshot":
                        page.screenshot(path=str(screenshot), full_page=True)
                    else:
                        raise ValueError("unsupported browser action")
                    action_results.append({"index": index, "action": kind, "status": "PASS"})
                if not screenshot.exists():
                    page.screenshot(path=str(screenshot), full_page=True)
                title = page.title()
                final_url = page.url
                context.close()
        finally:
            if original_temp is None:
                os.environ.pop("TEMP", None)
            else:
                os.environ["TEMP"] = original_temp
            if original_tmp is None:
                os.environ.pop("TMP", None)
            else:
                os.environ["TMP"] = original_tmp
        screenshot_hash = hashlib.sha256(screenshot.read_bytes()).hexdigest()
        result = {
            "schema": "paios.browser.result.v1",
            "task_id": task_id,
            "status": "PASS",
            "http_status": response.status if response else None,
            "title": title,
            "final_url": final_url,
            "extracted": extracted,
            "actions": action_results,
            "screenshot": str(screenshot),
            "screenshot_sha256": screenshot_hash,
        }
        (artifact_dir / "result.json").write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
        return result
