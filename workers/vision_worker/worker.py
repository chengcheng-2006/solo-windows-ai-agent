from __future__ import annotations

import hashlib
import json
import ctypes
import urllib.request
from pathlib import Path

import mss
import mss.tools
import win32con
import win32gui
import win32process
import win32ui
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
WRITE_ROOTS = (ROOT / "artifacts", ROOT / "tests" / "runtime-sandbox", ROOT / "evidence")


def _project_path(path: Path, *, write: bool = False) -> Path:
    resolved = path.resolve(strict=not write)
    if str(resolved).upper().startswith("E:\\") or not resolved.is_relative_to(ROOT):
        raise ValueError("path is outside the project root")
    if write and not any(resolved.is_relative_to(root.resolve()) for root in WRITE_ROOTS):
        raise ValueError("write path is outside approved output roots")
    return resolved


class OCRWorker:
    def __init__(self) -> None:
        self.engine = RapidOCR()

    def read(self, image_path: Path) -> dict:
        image = _project_path(image_path)
        result, elapsed = self.engine(str(image))
        lines = []
        for box, text, score in result or []:
            lines.append({"text": text, "score": float(score), "box": box})
        return {
            "schema": "paios.ocr.result.v1",
            "status": "PASS" if lines else "NO_TEXT",
            "engine": "rapidocr_onnxruntime",
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "text": "\n".join(line["text"] for line in lines),
            "lines": lines,
            "elapsed": elapsed,
        }


class ScreenshotWorker:
    def capture(self, output_path: Path, monitor: int = 1) -> dict:
        output = _project_path(output_path, write=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as capture:
            if monitor < 0 or monitor >= len(capture.monitors):
                raise ValueError("invalid monitor index")
            raw = capture.grab(capture.monitors[monitor])
            mss.tools.to_png(raw.rgb, raw.size, output=str(output))
        return {
            "schema": "paios.screenshot.result.v1",
            "status": "PASS",
            "path": str(output),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "width": raw.width,
            "height": raw.height,
        }

    def capture_window(self, pid: int, output_path: Path) -> dict:
        output = _project_path(output_path, write=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        handles: list[int] = []
        def collect(hwnd: int, _context: object) -> None:
            if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
                handles.append(hwnd)
        win32gui.EnumWindows(collect, None)
        if not handles:
            raise RuntimeError("no visible window found for screenshot")
        hwnd = handles[0]
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        window_dc = win32gui.GetWindowDC(hwnd)
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)
        try:
            rendered = ctypes.windll.user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), 2)
            if not rendered:
                raise RuntimeError("PrintWindow failed")
            info = bitmap.GetInfo()
            bits = bitmap.GetBitmapBits(True)
            image = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1)
            image.save(output)
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            memory_dc.DeleteDC()
            source_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, window_dc)
        return {
            "schema": "paios.screenshot.result.v1",
            "status": "PASS",
            "capture_mode": "PrintWindow",
            "path": str(output),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "width": width,
            "height": height,
        }


class VisionHealth:
    @staticmethod
    def local() -> dict:
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open("http://127.0.0.1:11434/api/tags", timeout=5) as response:
                payload = json.load(response)
            models = [model.get("name", "") for model in payload.get("models", [])]
        except Exception as exc:
            return {"status": "FAIL", "provider": "ollama", "reason": type(exc).__name__}
        vision_models = [name for name in models if any(marker in name.lower() for marker in ("llava", "vision", "vl"))]
        return {
            "status": "PASS" if vision_models else "DEGRADED",
            "provider": "ollama",
            "models": models,
            "vision_models": vision_models,
            "reason": None if vision_models else "no_local_vision_model",
        }
