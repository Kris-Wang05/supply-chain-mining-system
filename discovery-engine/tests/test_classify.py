from __future__ import annotations

import pytest

from discovery_engine.extractors.classify import apply_decisions, format_queue_listing

QUEUE = [
    {
        "accession": "0000999999-26-000007",
        "form_type": "8-K",
        "cik": "999999",
        "company": "AMENDED INC",
        "filed_date": "2026-07-07",
        "source_url": "https://www.sec.gov/example-index.htm",
        "captured_at": "2026-07-08",
        "extra": {"items": ["8.01"], "event_type": "", "needs_classification": True},
    },
    {
        "accession": "0000888888-26-000001",
        "form_type": "8-K",
        "cik": "888888",
        "company": "OTHER CORP",
        "filed_date": "2026-07-07",
        "source_url": "https://www.sec.gov/other-index.htm",
        "captured_at": "2026-07-08",
        "extra": {"items": ["5.02"], "event_type": "", "needs_classification": True},
    },
]


def test_apply_classifies_and_removes_from_queue() -> None:
    decisions = [{"accession": "0000999999-26-000007", "action": "government_contract"}]
    classified, remaining = apply_decisions(QUEUE, decisions)
    assert len(classified) == 1
    assert classified[0]["extra"]["event_type"] == "government_contract"
    assert not classified[0]["extra"]["needs_classification"]
    assert len(remaining) == 1
    assert remaining[0]["accession"] == "0000888888-26-000001"


def test_apply_discard_removes_without_classifying() -> None:
    decisions = [{"accession": "0000999999-26-000007", "action": "discard"}]
    classified, remaining = apply_decisions(QUEUE, decisions)
    assert classified == []
    assert len(remaining) == 1


def test_apply_rejects_unknown_accession() -> None:
    with pytest.raises(ValueError, match="unknown accession"):
        apply_decisions(QUEUE, [{"accession": "nope", "action": "discard"}])


def test_apply_rejects_invalid_action() -> None:
    with pytest.raises(ValueError, match="invalid action"):
        apply_decisions(QUEUE, [{"accession": "0000999999-26-000007", "action": "made_up_type"}])


def test_apply_rejects_duplicate_decisions() -> None:
    decisions = [
        {"accession": "0000999999-26-000007", "action": "discard"},
        {"accession": "0000999999-26-000007", "action": "government_contract"},
    ]
    with pytest.raises(ValueError, match="duplicate decision"):
        apply_decisions(QUEUE, decisions)


def test_format_queue_listing() -> None:
    listing = format_queue_listing(QUEUE, limit=1)
    assert "2 entries" in listing
    assert "AMENDED INC" in listing
    assert "OTHER CORP" not in listing  # limit=1
