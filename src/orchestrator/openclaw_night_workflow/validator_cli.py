from __future__ import annotations

import argparse
import json
import sys

from .config import get_settings
from .validator_runner import validate_phase


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--workflow-id", default="openclaw-hermes-v1")
    parser.add_argument("--run-id", default="dry-run")
    parser.add_argument("--phase", required=True, choices=["bootstrap-entry", "phase1", "phase2", "phase3"])
    args = parser.parse_args(argv)
    settings = get_settings(args.root)
    result = validate_phase(settings.root, args.workflow_id, args.run_id, args.phase).to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
