from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from discovery_engine.dedup import event_fingerprint, find_duplicates
from discovery_engine.models import CandidateRecord
from discovery_engine.scoring import assign_band

DEFAULT_POOL = Path("state/candidate_pool.jsonl")
DEFAULT_HISTORY = Path("state/history.jsonl")


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

    collect_8k_parser = subparsers.add_parser("collect-8k", help="Fetch one day of 8-K filings into raw/")
    collect_8k_parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    collect_8k_parser.add_argument("--raw-dir", type=Path, default=Path("raw/edgar_8k"))

    collect_f4_parser = subparsers.add_parser(
        "collect-form4", help="Fetch one day of Form 4 open-market purchases into raw/"
    )
    collect_f4_parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    collect_f4_parser.add_argument("--raw-dir", type=Path, default=Path("raw/edgar_form4"))

    ingest_parser = subparsers.add_parser(
        "ingest", help="Convert raw JSONL into status=lead records in the candidate pool"
    )
    ingest_parser.add_argument("raw_path", type=Path)
    ingest_parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    ingest_parser.add_argument("--queue", type=Path, default=Path("state/classification_queue.jsonl"))

    expire_parser = subparsers.add_parser("expire", help="Mark overdue records as expired")
    expire_parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    expire_parser.add_argument("--today", default=date.today().isoformat())

    classify_parser = subparsers.add_parser(
        "classify", help="List or resolve the manual classification queue"
    )
    classify_parser.add_argument("--queue", type=Path, default=Path("state/classification_queue.jsonl"))
    classify_parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    classify_parser.add_argument("--limit", type=int, default=20, help="entries to list")
    classify_parser.add_argument(
        "--apply", type=Path, default=None,
        help="JSONL of decisions: {accession, action: <event_type>|discard}",
    )

    report_parser = subparsers.add_parser("report", help="Write the weekly markdown report")
    report_parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    report_parser.add_argument("--out-dir", type=Path, default=Path("output/weekly"))
    report_parser.add_argument("--date", default=date.today().isoformat())

    args = parser.parse_args(argv)
    if args.command == "template":
        print(json.dumps(build_template(args.ticker), ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate-candidates":
        return validate_candidates(args.path)
    if args.command == "score":
        return score_candidates(args.path)
    if args.command == "collect-8k":
        return run_collect(args.date, args.raw_dir, kind="8k")
    if args.command == "collect-form4":
        return run_collect(args.date, args.raw_dir, kind="form4")
    if args.command == "ingest":
        return run_ingest(args.raw_path, args.pool, args.queue)
    if args.command == "expire":
        return run_expire(args.pool, date.fromisoformat(args.today))
    if args.command == "classify":
        return run_classify(args.queue, args.pool, args.limit, args.apply)
    if args.command == "report":
        return run_report(args.pool, args.out_dir, date.fromisoformat(args.date))
    parser.error("unknown command")
    return 2


def run_collect(day_str: str, raw_dir: Path, kind: str) -> int:
    from discovery_engine.collectors.edgar_8k import collect_8k
    from discovery_engine.collectors.edgar_form4 import collect_form4
    from discovery_engine.storage import append_raw

    day = date.fromisoformat(day_str)
    filings = collect_8k(day) if kind == "8k" else collect_form4(day)
    path = raw_dir / f"{day.isoformat()}.jsonl"
    added = append_raw(path, [f.to_dict() for f in filings], key="accession")
    print(f"collected {len(filings)} filings, {added} new -> {path}")
    return 0


def run_ingest(raw_path: Path, pool_path: Path, queue_path: Path) -> int:
    from discovery_engine.extractors.to_candidate import convert_batch
    from discovery_engine.resolvers.cik_ticker import load_map
    from discovery_engine.storage import append_raw, load_pool, upsert, write_pool

    raws = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ticker_map = load_map(Path("state/cik_ticker_map.json"))
    leads, queue = convert_batch(raws, ticker_map)
    pool = load_pool(pool_path)
    added = 0
    for record in leads:
        if record.fingerprint not in pool:  # ingest 只新增，不改已有记录的状态
            pool = upsert(pool, record)
            added += 1
    write_pool(pool_path, pool, history_path=DEFAULT_HISTORY)
    queued = append_raw(queue_path, queue, key="accession") if queue else 0
    print(f"ingested {added} new leads -> {pool_path}; {queued} queued for classification")
    return 0


def run_expire(pool_path: Path, today: date) -> int:
    from discovery_engine.lifecycle import expire_overdue
    from discovery_engine.storage import load_pool, upsert, write_pool

    pool = load_pool(pool_path)
    expired = expire_overdue(list(pool.values()), today)
    for data in expired:
        pool = upsert(pool, CandidateRecord.from_dict(data))
    write_pool(pool_path, pool, history_path=DEFAULT_HISTORY)
    print(f"expired {len(expired)} records")
    return 0


def run_classify(queue_path: Path, pool_path: Path, limit: int, apply_path: Path | None) -> int:
    from discovery_engine.extractors.classify import apply_decisions, format_queue_listing, load_queue
    from discovery_engine.extractors.to_candidate import convert_batch
    from discovery_engine.resolvers.cik_ticker import load_map
    from discovery_engine.storage import load_pool, upsert, write_pool

    queue = load_queue(queue_path)
    if apply_path is None:
        print(format_queue_listing(queue, limit))
        return 0

    decisions = [
        json.loads(line)
        for line in apply_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    classified, remaining = apply_decisions(queue, decisions)
    ticker_map = load_map(Path("state/cik_ticker_map.json"))
    leads, requeued = convert_batch(classified, ticker_map)
    if requeued:
        raise ValueError(f"{len(requeued)} classified entries failed conversion")

    pool = load_pool(pool_path)
    added = 0
    for record in leads:
        if record.fingerprint not in pool:
            pool = upsert(pool, record)
            added += 1
    write_pool(pool_path, pool, history_path=DEFAULT_HISTORY)
    # 队列重写（原始 raw 不动，符合"raw append-only"不变量）
    queue_path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in remaining),
        encoding="utf-8",
    )
    print(f"classified {len(decisions)} decisions: {added} new leads, "
          f"{len(decisions) - len(classified)} discarded, {len(remaining)} left in queue")
    return 0


def run_report(pool_path: Path, out_dir: Path, report_date: date) -> int:
    from discovery_engine.reports.weekly import build_weekly_report
    from discovery_engine.storage import load_pool

    records = list(load_pool(pool_path).values())
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{report_date.isoformat()}.md"
    out_path.write_text(build_weekly_report(records, report_date), encoding="utf-8")
    print(f"report written -> {out_path}")
    return 0


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
