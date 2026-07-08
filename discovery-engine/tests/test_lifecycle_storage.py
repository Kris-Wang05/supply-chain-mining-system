from __future__ import annotations

import copy
from datetime import date

import pytest

from discovery_engine.lifecycle import expire_overdue, is_valid_transition
from discovery_engine.models import CandidateRecord
from discovery_engine.storage import append_raw, load_pool, upsert, write_pool
from tests.test_models import VALID_RECORD


def make_record(**overrides) -> CandidateRecord:
    data = copy.deepcopy(VALID_RECORD)
    data.update(overrides)
    return CandidateRecord.from_dict(data)


def test_valid_transitions() -> None:
    assert is_valid_transition("lead", "contextualized")
    assert is_valid_transition("candidate", "promoted")
    assert is_valid_transition("expired", "lead")
    assert is_valid_transition("watchlist", "candidate")
    assert is_valid_transition("lead", "lead")


def test_invalid_transitions() -> None:
    assert not is_valid_transition("lead", "promoted")
    assert not is_valid_transition("rejected", "lead")
    assert not is_valid_transition("promoted", "candidate")


def test_expire_overdue_only_past_review_by() -> None:
    overdue = make_record(review_by="2026-01-01")
    fresh = make_record(review_by="2027-01-01", fingerprint="other0000000000f")
    expired = expire_overdue([overdue, fresh], today=date(2026, 7, 8))
    assert len(expired) == 1
    assert expired[0]["status"] == "expired"
    assert "auto-expired" in expired[0]["outcome_note"]


def test_expire_skips_terminal_statuses() -> None:
    rejected = make_record(status="rejected", kill_rules_triggered=["dilution"], review_by="2026-01-01")
    assert expire_overdue([rejected], today=date(2026, 7, 8)) == []


def test_pool_roundtrip_and_upsert(tmp_path) -> None:
    pool_path = tmp_path / "pool.jsonl"
    history_path = tmp_path / "history.jsonl"
    record = make_record()
    pool = upsert({}, record)
    write_pool(pool_path, pool, history_path=history_path)

    loaded = load_pool(pool_path)
    assert loaded[record.fingerprint] == record

    # 合法状态推进：candidate -> promoted
    promoted = make_record(
        status="promoted",
        mispricing_hypothesis="No coverage",
        falsification_signals=["Q3 shows no revenue"],
    )
    pool = upsert(loaded, promoted)
    write_pool(pool_path, pool, history_path=history_path)
    assert load_pool(pool_path)[record.fingerprint].status == "promoted"
    # 审计日志有两条（初始 + 更新）
    assert len(history_path.read_text(encoding="utf-8").splitlines()) == 2


def test_upsert_rejects_illegal_transition() -> None:
    pool = upsert({}, make_record(status="lead"))
    with pytest.raises(ValueError, match="invalid status transition"):
        upsert(pool, make_record(status="promoted",
                                 mispricing_hypothesis="x", falsification_signals=["y"]))


def test_append_raw_dedups_by_key(tmp_path) -> None:
    path = tmp_path / "raw.jsonl"
    entries = [{"accession": "A-1", "x": 1}, {"accession": "A-2", "x": 2}]
    assert append_raw(path, entries, key="accession") == 2
    assert append_raw(path, entries + [{"accession": "A-3", "x": 3}], key="accession") == 1
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
