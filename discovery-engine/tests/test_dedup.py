from __future__ import annotations

from discovery_engine.dedup import event_fingerprint, find_duplicates


def test_same_month_same_fingerprint() -> None:
    a = event_fingerprint("XYZ", "formal_agreement", "Major Co", "2026-07-01")
    b = event_fingerprint("xyz", "formal_agreement", "major co", "2026-07-28")
    assert a == b


def test_different_month_different_fingerprint() -> None:
    a = event_fingerprint("XYZ", "formal_agreement", "Major Co", "2026-07-01")
    b = event_fingerprint("XYZ", "formal_agreement", "Major Co", "2026-08-01")
    assert a != b


def test_different_counterparty_different_fingerprint() -> None:
    a = event_fingerprint("XYZ", "formal_agreement", "Major Co", "2026-07-01")
    b = event_fingerprint("XYZ", "formal_agreement", "Other Co", "2026-07-01")
    assert a != b


def test_find_duplicates() -> None:
    assert find_duplicates(["a", "b", "a", "c", "b"]) == {"a", "b"}
    assert find_duplicates(["a", "b"]) == set()
