from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from discovery_engine.dedup import event_fingerprint, find_duplicates
from discovery_engine.models import CandidateRecord
from discovery_engine.scoring import assign_band


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discovery-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    template_parser = subparsers.add_parser("template", help="Print a candidate record template")
    template_parser.add_argument("--ticker", required=True)

    validate_parser = subparsers.add_parser(
        "validate-candidates",
        help="Validate a JSONL file of candidate records (schema, gates, dedup)",
    )
    validate_parser.add_argument("path", type=Path)

    score_parser = subparsers.add_parser(
        "score",
        help="Print band assignment for each record in a JSONL file",
    )
    score_parser.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    if args.command == "template":
        print(json.dumps(build_template(args.ticker), ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate-candidates":
        return validate_candidates(args.path)
    if args.command == "score":
        return score_candidates(args.path)
    parser.error("unknown command")
    return 2


def build_template(ticker: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "company": "",
        "exchange": "",
        "country": "",
        "event_date": "YYYY-MM-DD",
        "event_type": "customer_or_supplier_mention",
        "relationship_level": "E",
        "counterparty": "",
        "summary": "",
        "why_mentioned": "",
        "unilateral": True,
        "economic_impact_note": "[unverified]",
        "price_reaction_note": "[unverified]",
        "sources": [
            {
                "url": "",
                "publisher": "",
                "published_date": "YYYY-MM-DD",
                "captured_at": "YYYY-MM-DD",
                "tier": 3,
                "excerpt": "verbatim quote here",
            }
        ],
        "scores": {
            "change_score": 0,
            "evidence_score": 0,
            "economic_impact_score": 0,
            "recognition_gap_score": 0,
        },
        "discovery_score": 0,
        "status": "lead",
        "review_by": "YYYY-MM-DD",
        "fingerprint": event_fingerprint(ticker, "customer_or_supplier_mention", "", "0000-00"),
        "captured_at": "YYYY-MM-DD",
        "score_rationale": "[unverified]",
        "supersedes": "",
        "red_flags": ["unilateral_claim_only"],
        "mispricing_hypothesis": "",
        "falsification_signals": [],
        "kill_rules_triggered": [],
        "next_questions": [],
        "outcome_note": "",
    }


def _load_records(path: Path) -> tuple[list[CandidateRecord], list[str]]:
    records: list[CandidateRecord] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(CandidateRecord.from_dict(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path}:{line_number}: {exc}")
    return records, errors


def validate_candidates(path: Path) -> int:
    records, errors = _load_records(path)
    duplicates = find_duplicates([record.fingerprint for record in records])
    for fingerprint in sorted(duplicates):
        errors.append(f"{path}: duplicate fingerprint {fingerprint}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {path} ({len(records)} records)")
    return 0


def score_candidates(path: Path) -> int:
    records, errors = _load_records(path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    for record in records:
        print(f"{record.ticker}\t{record.discovery_score}\t{assign_band(record)}\t{record.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
