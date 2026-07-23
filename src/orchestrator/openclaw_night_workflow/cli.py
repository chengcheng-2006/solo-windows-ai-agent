from __future__ import annotations

import argparse
import json
import sys

from .app import NightWorkflowOrchestrator
from .codex_adapter import CodexAdapter
from .config import get_settings
from .evidence import export_file_manifest
from .rollback import create_bootstrap_rollback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openclaw-night-workflow")
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("health")
    start = sub.add_parser("start-workflow")
    start.add_argument("--idempotency-key", required=True)
    start.add_argument("--allow-real-phase-start", action="store_true")
    query = sub.add_parser("query-workflow")
    query.add_argument("--run-id", required=True)
    pause = sub.add_parser("pause-workflow")
    pause.add_argument("--run-id", required=True)
    resume = sub.add_parser("resume-workflow")
    resume.add_argument("--run-id", required=True)
    cancel = sub.add_parser("cancel-workflow")
    cancel.add_argument("--run-id", required=True)
    sub.add_parser("codex-health")
    sub.add_parser("export-file-manifest")
    sub.add_parser("create-rollback")
    args = parser.parse_args(argv)
    settings = get_settings(args.root)

    if args.command == "codex-health":
        print(json.dumps(CodexAdapter().health(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "export-file-manifest":
        export_file_manifest(settings.root, settings.evidence_dir / "00_file_manifest.json")
        return 0
    if args.command == "create-rollback":
        print(str(create_bootstrap_rollback(settings.root)))
        return 0

    orch = NightWorkflowOrchestrator(settings)
    try:
        if args.command == "init-db":
            print(json.dumps(orch.health(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "health":
            result = orch.health()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "start-workflow":
            result = orch.start_registered_workflow(args.idempotency_key, args.allow_real_phase_start)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "query-workflow":
            print(json.dumps(orch.query_run(args.run_id), ensure_ascii=False, indent=2))
            return 0
        if args.command == "pause-workflow":
            print(json.dumps(orch.pause_run(args.run_id), ensure_ascii=False, indent=2))
            return 0
        if args.command == "resume-workflow":
            print(json.dumps(orch.resume_run(args.run_id), ensure_ascii=False, indent=2))
            return 0
        if args.command == "cancel-workflow":
            print(json.dumps(orch.cancel_run(args.run_id), ensure_ascii=False, indent=2))
            return 0
    finally:
        orch.close()
    return 2


if __name__ == "__main__":
    sys.exit(main())
