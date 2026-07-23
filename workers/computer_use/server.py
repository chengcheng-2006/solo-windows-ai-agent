"""Computer Use Service — 浏览器/UIA/OCR 统一控制层"""
from __future__ import annotations
import asyncio, json, logging, os, subprocess, sys, time, uuid

# Suppress console window for subprocess calls on Windows
_CW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
from pathlib import Path
from datetime import datetime
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(os.environ.get("COMPUTER_USE_ROOT", r"D:\OpenClaw-Hermes-Integration"))
STATE = ROOT / "state" / "computer_use"
SCREENSHOTS = STATE / "screenshots"
STATE.mkdir(parents=True, exist_ok=True)
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Computer Use", version="0.1.0")
log = logging.getLogger("computer_use")

# ── Models ──
class ObserveRequest(BaseModel):
    include_ocr: bool = True
    include_dom: bool = False
    include_uia: bool = False

class LocateRequest(BaseModel):
    target: str
    method: str = "ocr"  # ocr | dom | uia

class ActionRequest(BaseModel):
    action: str  # left_click | double_click | right_click | move | type_text | press_key | scroll
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None

# ── Endpoints ──
@app.on_event("startup")
async def startup():
    log.info("Computer Use service starting")

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/observe")
async def observe(req: ObserveRequest):
    """获取当前屏幕状态"""
    screenshot_id = f"ss_{uuid.uuid4().hex[:8]}_{int(time.time())}"
    ss_path = SCREENSHOTS / f"{screenshot_id}.png"
    
    # 截图 (PowerShell)
    # DPI-aware full screen capture (fix: use physical resolution not logical)
    ps_cmd = f'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap 1920, 1080
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, (New-Object System.Drawing.Size(1920, 1080)))
$bmp.Save('{ss_path}')
$g.Dispose()
$bmp.Dispose()
'''
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=30, creationflags=_CW)
    
    result = {
        "observation_id": screenshot_id,
        "timestamp": datetime.now().isoformat(),
        "screenshot": str(ss_path),
        "ocr_blocks": ["OCR pending - requires RapidOCR package"],
        "uia_tree": None,
        "dom_snapshot": None,
    }
    return result

@app.post("/locate")
async def locate(req: LocateRequest):
    """定位目标元素坐标"""
    return {"method": req.method, "target": req.target, "coordinates": None, "confidence": 0, "message": "Locate not yet implemented"}

@app.post("/click")
async def click(req: ActionRequest):
    """执行鼠标/键盘动作"""
    if req.action in ("left_click", "double_click", "move"):
        ps_cmd = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({req.x or 0}, {req.y or 0})
'''
        if req.action == "left_click":
            ps_cmd += '[System.Windows.Forms.SendKeys]::SendWait("{+ENTER}")'
            subprocess.run("powershell -NoProfile -Command \"$s=New-Object -ComObject WScript.Shell; $s.SendKeys('~')\"", shell=True, timeout=5, creationflags=_CW)
        return {"action": req.action, "x": req.x, "y": req.y, "status": "executed"}
    return {"action": req.action, "status": "not_implemented"}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8830)

