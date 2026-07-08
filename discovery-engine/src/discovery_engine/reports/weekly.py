from __future__ import annotations

from datetime import date, timedelta

from discovery_engine.models import CandidateRecord
from discovery_engine.scoring import assign_band


def build_weekly_report(
    records: list[CandidateRecord], report_date: date, window_days: int = 7
) -> str:
    """按框架 v0.2 第 9 节生成周报 markdown。纯函数，不做 IO。"""
    since = (report_date - timedelta(days=window_days)).isoformat()
    new_records = [r for r in records if r.captured_at >= since]
    expired = [r for r in records if r.status == "expired"]
    dilution = [r for r in records if "dilution_or_insider_selling" in r.red_flags]
    priced_in = [r for r in records if "price_already_moved" in r.red_flags]
    rejected = [r for r in records if r.status == "rejected"]
    promotable = sorted(
        (r for r in records if r.status == "candidate" and assign_band(r) in {"priority", "candidate_pool"}),
        key=lambda r: -r.discovery_score,
    )[:10]

    lines = [
        f"# Discovery Engine 周报 {report_date.isoformat()}",
        "",
        "## 本周新发现",
        _table(new_records),
        "## 推荐进入 3+1 完整分析（按分数排序，最多 10 家）",
        _table(promotable),
        "## G5 稀释门槛触发清单（必须单独复核）",
        _table(dilution),
        "## 可能已被市场定价的事件",
        _table(priced_in),
        "## 当前处于 expired 的记录",
        _table(expired),
        "## 因 kill rule 被排除的记录",
        _table(rejected),
    ]
    return "\n".join(lines) + "\n"


def _table(records: list[CandidateRecord]) -> str:
    if not records:
        return "（无）\n"
    rows = [
        "| ticker | company | event_type | score | band | status | review_by |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: (-r.discovery_score, r.ticker)):
        rows.append(
            f"| {r.ticker} | {r.company} | {r.event_type} | {r.discovery_score} "
            f"| {assign_band(r)} | {r.status} | {r.review_by} |"
        )
    return "\n".join(rows) + "\n"
