from __future__ import annotations

from datetime import date

from discovery_engine.models import CandidateRecord, Status

# 状态机：lead → contextualized → verified → candidate → promoted
# 任何非终态可转 rejected / watchlist / expired；expired 可被新证据复活回 lead。
ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    "lead": {"contextualized", "watchlist", "rejected", "expired"},
    "contextualized": {"verified", "watchlist", "rejected", "expired"},
    "verified": {"candidate", "watchlist", "rejected", "expired"},
    "candidate": {"promoted", "watchlist", "rejected", "expired"},
    "watchlist": {"contextualized", "verified", "candidate", "rejected", "expired"},
    "promoted": {"rejected"},
    "rejected": set(),
    "expired": {"lead"},
}

TERMINAL_STATUSES: set[Status] = {"promoted", "rejected", "expired"}


def is_valid_transition(old: Status, new: Status) -> bool:
    if old == new:
        return True
    return new in ALLOWED_TRANSITIONS[old]


def check_transition(old: Status, new: Status) -> None:
    if not is_valid_transition(old, new):
        raise ValueError(f"invalid status transition: {old} -> {new}")


def is_overdue(record: CandidateRecord, today: date) -> bool:
    """过了 review_by 且不在终态的记录应转 expired。"""
    if record.status in TERMINAL_STATUSES:
        return False
    return date.fromisoformat(record.review_by) < today


def expire_overdue(records: list[CandidateRecord], today: date) -> list[dict]:
    """返回过期记录的字典副本（status 改为 expired），供 storage 层落盘。

    不修改原记录（frozen dataclass）；outcome_note 记录过期原因。
    """
    from dataclasses import asdict

    expired: list[dict] = []
    for record in records:
        if is_overdue(record, today):
            data = asdict(record)
            data["status"] = "expired"
            note = f"auto-expired on {today.isoformat()}: review_by {record.review_by} passed"
            data["outcome_note"] = (
                f"{record.outcome_note}; {note}" if record.outcome_note else note
            )
            expired.append(data)
    return expired
