from __future__ import annotations

import copy

from discovery_engine.models import CandidateRecord
from discovery_engine.scoring import assign_band, score_band
from tests.test_models import VALID_RECORD


def make_record(**overrides) -> CandidateRecord:
    data = copy.deepcopy(VALID_RECORD)
    data.update(overrides)
    return CandidateRecord.from_dict(data)


def test_score_band_thresholds() -> None:
    assert score_band(20) == "priority"
    assert score_band(16) == "priority"
    assert score_band(15) == "candidate_pool"
    assert score_band(13) == "candidate_pool"
    assert score_band(12) == "watchlist"
    assert score_band(9) == "watchlist"
    assert score_band(8) == "noise"
    assert score_band(0) == "noise"


def test_clean_record_keeps_score_band() -> None:
    assert assign_band(make_record()) == "candidate_pool"


def test_gate_g1_caps_at_watchlist() -> None:
    record = make_record(
        scores={
            "change_score": 5,
            "evidence_score": 2,
            "economic_impact_score": 4,
            "recognition_gap_score": 4,
        },
        discovery_score=15,
        status="watchlist",
    )
    assert assign_band(record) == "watchlist"


def test_gate_g2_caps_level_e_at_watchlist() -> None:
    record = make_record(relationship_level="E", status="watchlist")
    assert assign_band(record) == "watchlist"


def test_gate_g4_price_moved_demotes_one_band() -> None:
    record = make_record(red_flags=["price_already_moved"])
    assert assign_band(record) == "watchlist"


def test_gate_g5_dilution_demotes_one_band() -> None:
    record = make_record(red_flags=["dilution_or_insider_selling"])
    assert assign_band(record) == "watchlist"


def test_stacked_gates_demote_twice() -> None:
    record = make_record(red_flags=["price_already_moved", "dilution_or_insider_selling"])
    assert assign_band(record) == "noise"
