from __future__ import annotations

import argparse
import json
import sys

from .config import get_settings
from .workflow_control import WorkflowControlError, dry_run_start, export_evidence, resolve_action, status, transition


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openclaw-night-workflow-control")
    parser.add_argument("--root", default=None)
    parser.add_argument("--action", required=True, choices=["status", "start", "pause", "resume", "cancel", "approve", "reject", "export"])
    parser.add_argument("--workflow-id", default="openclaw-hermes-v1")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--action-id", default=None)
    parser.add_argument("--owner-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = get_settings(args.root).root
    try:
        if args.action == "status":
            result = status(root, args.workflow_id, args.owner_id)
        elif args.action == "start":
            if not args.dry_run:
                raise WorkflowControlError("real start is disabled in phase 0.5; pass --dry-run")
            result = dry_run_start(root, args.workflow_id, args.owner_id)
        elif args.action in {"pause", "resume", "cancel"}:
            result = transition(root, args.workflow_id, args.owner_id, args.action, args.run_id)
        elif args.action in {"approve", "reject"}:
            result = resolve_action(root, args.workflow_id, args.owner_id, args.action, args.action_id)
        elif args.action == "export":
            result = export_evidence(root, args.workflow_id, args.owner_id)
        else:
            raise WorkflowControlError(f"unsupported action: {args.action}")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "error_type": exc.__class__.__name__}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

