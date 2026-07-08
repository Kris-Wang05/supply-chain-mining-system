from __future__ import annotations

import copy

import pytest

from discovery_engine.models import CandidateRecord

VALID_RECORD: dict = {
    "ticker": "XYZ",
    "company": "Example Corp",
    "exchange": "NASDAQ",
    "country": "US",
    "event_date": "2026-07-01",
    "event_type": "design_win_or_qualification",
    "relationship_level": "C",
    "counterparty": "Major Company",
    "summary": "Customer validation announced by both parties",
    "why_mentioned": "Testing a specific component for volume production",
    "unilateral": False,
    "economic_impact_note": "Contract value not disclosed; estimated single-digit % of revenue",
    "price_reaction_note": "+4% on announcement day, volume 1.5x average",
    "sources": [
        {
            "url": "https://www.sec.gov/example-8k",
            "publisher": "SEC EDGAR",
            "published_date": "2026-07-01",
            "captured_at": "2026-07-05",
            "tier": 1,
            "excerpt": "The company entered into a qualification agreement...",
        }
    ],
    "scores": {
        "change_score": 4,
        "evidence_score": 3,
        "economic_impact_score": 2,
        "recognition_gap_score": 4,
    },
    "discovery_score": 13,
    "status": "candidate",
    "review_by": "2026-09-29",
    "fingerprint": "abc123def4567890",
    "captured_at": "2026-07-05",
    "score_rationale": "Tier 1 filing confirms qualification; no analyst coverage found",
    "red_flags": [],
    "next_questions": ["Does Q3 10-Q show related revenue?"],
}


def record_with(**overrides) -> dict:
    data = copy.deepcopy(VALID_RECORD)
    data.update(overrides)
    return data


def test_valid_record_parses() -> None:
    record = CandidateRecord.from_dict(VALID_RECORD)
    assert record.ticker == "XYZ"
    assert record.scores.total == 13


def test_discovery_score_must_match_components() -> None:
    with pytest.raises(ValueError, match="discovery_score"):
        CandidateRecord.from_dict(record_with(discovery_score=15))


def test_gate_g1_low_evidence_cannot_be_candidate() -> None:
    data = record_with(
        scores={
            "change_score": 5,
            "evidence_score": 2,
            "economic_impact_score": 4,
            "recognition_gap_score": 4,
        },
        discovery_score=15,
    )
    with pytest.raises(ValueError, match="gate G1"):
        CandidateRecord.from_dict(data)


def test_gate_g2_level_e_cannot_be_candidate() -> None:
    with pytest.raises(ValueError, match="gate G2"):
        CandidateRecord.from_dict(record_with(relationship_level="E"))


def test_verified_requires_primary_or_secondary_source() -> None:
    tier3_source = dict(VALID_RECORD["sources"][0], tier=3)
    with pytest.raises(ValueError, match="tier 1 or 2"):
        CandidateRecord.from_dict(record_with(sources=[tier3_source]))


def test_tier3_only_is_fine_for_lead() -> None:
    tier3_source = dict(VALID_RECORD["sources"][0], tier=3)
    record = CandidateRecord.from_dict(record_with(sources=[tier3_source], status="lead"))
    assert record.status == "lead"


def test_promoted_requires_hypothesis_and_falsification() -> None:
    with pytest.raises(ValueError, match="mispricing_hypothesis"):
        CandidateRecord.from_dict(record_with(status="promoted"))
    with pytest.raises(ValueError, match="falsification_signals"):
        CandidateRecord.from_dict(
            record_with(status="promoted", mispricing_hypothesis="No coverage yet")
        )
    record = CandidateRecord.from_dict(
        record_with(
            status="promoted",
            mispricing_hypothesis="No coverage yet",
            falsification_signals=["Q3 10-Q shows no related revenue"],
        )
    )
    assert record.status == "promoted"


def test_rejected_requires_kill_rules() -> None:
    with pytest.raises(ValueError, match="kill_rules_triggered"):
        CandidateRecord.from_dict(record_with(status="rejected"))


def test_unilateral_requires_red_flag() -> None:
    with pytest.raises(ValueError, match="unilateral_claim_only"):
        CandidateRecord.from_dict(record_with(unilateral=True))


def test_level_a_requires_tier1_source() -> None:
    tier2_source = dict(VALID_RECORD["sources"][0], tier=2)
    with pytest.raises(ValueError, match="tier 1 source"):
        CandidateRecord.from_dict(record_with(relationship_level="A", sources=[tier2_source]))


def test_pending_marker_forces_lead() -> None:
    with pytest.raises(ValueError, match="status=lead"):
        CandidateRecord.from_dict(record_with(economic_impact_note="[unverified]"))
