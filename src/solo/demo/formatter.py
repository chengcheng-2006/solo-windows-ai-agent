"""Demo output formatter — human-readable terminal output and JSON mode."""
from __future__ import annotations

import json
from typing import Any


def format_demo_human(result: dict[str, Any], title: str = "Solo Demo") -> str:
    """Format demo result as human-readable terminal output with ANSI colors."""
    lines: list[str] = []
    mode = result.get("mode", "lite")

    lines.append(f"\n===== {title} v0.1.1 =====")
    lines.append(f"Mode: {mode}")
    if "task_id" in result:
        lines.append(f"Task: {result['task_id']}")
    lines.append("")

    pipeline = result.get("pipeline", [])
    for i, event in enumerate(pipeline, 1):
        state = event.get("state", "?")
        ok = event.get("ok", True)
        icon = "✅" if ok else "🚨"
        detail = event.get("detail", event.get("risk", event.get("verdict", "")))
        if detail:
            lines.append(f"  [{i}/{len(pipeline)}] {state:<16} {detail:<40} {icon}")
        else:
            lines.append(f"  [{i}/{len(pipeline)}] {state:<16} {' '.ljust(40)} {icon}")

    # Security guarantees for VETO demo
    if "security_guarantees" in result:
        lines.append("")
        lines.append("===== Security Guarantees Verified =====")
        for key, val in result["security_guarantees"].items():
            icon = "✅" if val else "❌"
            label = key.replace("_", " ").title()
            lines.append(f"  {icon} {label}")

    lines.append("")
    status = result.get("status", "?")
    if status == "PASS":
        lines.append("===== Demo SUCCESS =====")
    else:
        lines.append(f"===== Demo {status} =====")

    if "vetoed" in result and result["vetoed"]:
        lines.append("The safety system correctly prevented a high-risk operation.")

    lines.append("")
    return "\n".join(lines)


def format_demo_json(result: dict[str, Any]) -> str:
    """Format demo result as JSON."""
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)
