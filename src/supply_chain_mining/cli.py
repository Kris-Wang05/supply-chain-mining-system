from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from supply_chain_mining.models import Candidate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="supply-chain-mining")
    subparsers = parser.add_subparsers(dest="command", required=True)

    template_parser = subparsers.add_parser("template", help="Print a Stage 0-5 run template")
    template_parser.add_argument("--mainline", required=True, help="Mainline or anchor fact to research")

    validate_parser = subparsers.add_parser(
        "validate-candidates",
        help="Validate a JSONL file of candidate records",
    )
    validate_parser.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    if args.command == "template":
        print(json.dumps(build_template(args.mainline), ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate-candidates":
        return validate_candidates(args.path)
    parser.error("unknown command")
    return 2


def build_template(mainline: str) -> dict[str, object]:
    return {
        "input": mainline,
        "stage_0_mainline_registry": {
            "name": mainline,
            "anchor_facts": [],
            "lifecycle": "unknown",
            "falsification_signals": [],
            "junk_graft_density": "unknown",
        },
        "stage_1_anchor_facts": [],
        "stage_2_process_nodes": [],
        "stage_3_candidates": [],
        "stage_4_pricing_tests": [],
        "stage_5_kill_rules": [],
        "stage_6_manual_questions": [
            "我的变量是什么?",
            "下行有界吗?",
            "兑现有日历吗?",
            "谁在对面?",
        ],
    }


def validate_candidates(path: Path) -> int:
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            Candidate.from_dict(json.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path}:{line_number}: {exc}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

