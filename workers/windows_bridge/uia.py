from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path

# Suppress console window for subprocess calls on Windows; no-op on other platforms
_CW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


RESPONSE_ROOT = Path(r"D:\OpenClaw-Hermes-Integration\state\windows-bridge\uia")


class UIAWorker:
    @staticmethod
    def _invoke(pid: int, operation: str, text: str = "", timeout: int = 25) -> dict:
        RESPONSE_ROOT.mkdir(parents=True, exist_ok=True)
        response_path = RESPONSE_ROOT / f"{pid}-{operation}.json"
        script_path = RESPONSE_ROOT / f"{pid}-{operation}.ps1"
        response_path.unlink(missing_ok=True)
        script_path.unlink(missing_ok=True)
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        script = rf"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
$targetPid = {int(pid)}
$responsePath = '{str(response_path)}'
$condition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $targetPid)
$window = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
    [System.Windows.Automation.TreeScope]::Children, $condition)
if ($null -eq $window) {{ throw 'UIA window not found' }}
$operation = '{operation}'
if ($operation -eq 'inspect') {{
    $all = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)
    $controls = @()
    for ($index = 0; $index -lt [Math]::Min($all.Count, 200); $index++) {{
        $element = $all.Item($index)
        $controls += [ordered]@{{
            name = $element.Current.Name
            automation_id = $element.Current.AutomationId
            control_type = $element.Current.ControlType.ProgrammaticName
        }}
    }}
    $json = [ordered]@{{status=$(if($controls.Count -gt 0){{'PASS'}}else{{'EMPTY'}});title=$window.Current.Name;controls=$controls}} |
        ConvertTo-Json -Depth 6 -Compress
    [IO.File]::WriteAllText($responsePath, $json, (New-Object Text.UTF8Encoding($false)))
    exit 0
}}
$documentCondition = New-Object System.Windows.Automation.OrCondition(
    (New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Document)),
    (New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit)))
$target = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $documentCondition)
if ($null -eq $target) {{ throw 'editable UIA control not found' }}
$valuePattern = $null
$inputText = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}'))
if ($target.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$valuePattern)) {{
    $valuePattern.SetValue($inputText)
    $value = $valuePattern.Current.Value
    $method = 'ValuePattern'
}} else {{
    $target.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait($inputText)
    Start-Sleep -Milliseconds 300
    $value = $target.Current.Name
    $method = 'UIAFocus+SendKeys'
}}
$json = [ordered]@{{status='PASS';method=$method;control_type=$target.Current.ControlType.ProgrammaticName;value_length=$inputText.Length}} |
    ConvertTo-Json -Compress
[IO.File]::WriteAllText($responsePath, $json, (New-Object Text.UTF8Encoding($false)))
"""
        try:
            script_path.write_text(script, encoding="utf-8-sig")
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=_CW,
            )
            if completed.returncode != 0:
                detail = " ".join(completed.stderr.split())[-400:]
                raise RuntimeError(f"native UIA operation failed: {detail or 'no diagnostic'}")
            if not response_path.is_file():
                raise RuntimeError("native UIA did not return structured output")
            return json.loads(response_path.read_text(encoding="utf-8"))
        finally:
            response_path.unlink(missing_ok=True)
            script_path.unlink(missing_ok=True)

    @classmethod
    def inspect(cls, pid: int, limit: int = 200) -> dict:
        result = cls._invoke(pid, "inspect")
        result["controls"] = result.get("controls", [])[:limit]
        return result

    @classmethod
    def type_text(cls, pid: int, text: str) -> dict:
        if not text or len(text) > 8000:
            raise ValueError("UIA text length outside allowed range")
        return cls._invoke(pid, "type", text=text)
