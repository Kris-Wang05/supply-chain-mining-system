from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal[
    # 企业关系
    "customer_or_supplier_mention",
    "formal_agreement",
    "design_win_or_qualification",
    "second_source_adoption",
    "ma_or_strategic_investment",
    # 政府与监管
    "government_contract",
    "subsidy_or_policy",
    "regulatory_approval",
    "export_restriction_or_localization",
    # 经营变化
    "financial_inflection",
    "backlog_or_order_growth",
    "guidance_raise",
    "capacity_addition",
    "new_product_revenue",
    # 资本与资产变化
    "asset_event",
    "insider_buying",
    "buyback_or_capital_allocation",
    "debt_restructuring",
    # 行业变化
    "industry_structure_change",
]

RelationshipLevel = Literal["A", "B", "C", "D", "E"]
SourceTier = Literal[1, 2, 3]
RedFlag = Literal[
    "unilateral_claim_only",
    "no_contract_value",
    "many_similar_partners",
    "recycled_news",
    "conflicts_with_filings",
    "promo_name_dropping",
    "price_already_moved",
    "dilution_or_insider_selling",
    "governance_risk",
    "low_liquidity",
]
Status = Literal[
    "lead",
    "contextualized",
    "verified",
    "candidate",
    "promoted",
    "watchlist",
    "rejected",
    "expired",
]
Band = Literal["priority", "candidate_pool", "watchlist", "noise"]

PENDING_MARKERS = ("unknown", "[unverified]", "需验证", "需拆", "tbd", "pending source")

# 状态推进最低要求：verified 及以上必须有一级/二级来源
_STATUS_ORDER: dict[str, int] = {
    "lead": 0,
    "contextualized": 1,
    "verified": 2,
    "watchlist": 2,
    "candidate": 3,
    "promoted": 4,
    "rejected": 2,
    "expired": 0,
}


@dataclass(frozen=True)
class SourceRef:
    url: str
    publisher: str
    published_date: str
    captured_at: str
    tier: SourceTier
    excerpt: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRef":
        return cls(
            url=_required_str(data, "url"),
            publisher=_required_str(data, "publisher"),
            published_date=_required_str(data, "published_date"),
            captured_at=_required_str(data, "captured_at"),
            tier=_enum_value(data, "tier", {1, 2, 3}),
            excerpt=_required_str(data, "excerpt"),
        )


@dataclass(frozen=True)
class DiscoveryScores:
    change_score: int
    evidence_score: int
    economic_impact_score: int
    recognition_gap_score: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DiscoveryScores":
        return cls(
            change_score=_bounded_int(data, "change_score", 0, 5),
            evidence_score=_bounded_int(data, "evidence_score", 0, 5),
            economic_impact_score=_bounded_int(data, "economic_impact_score", 0, 5),
            recognition_gap_score=_bounded_int(data, "recognition_gap_score", 0, 5),
        )

    @property
    def total(self) -> int:
        return (
            self.change_score
            + self.evidence_score
            + self.economic_impact_score
            + self.recognition_gap_score
        )


@dataclass(frozen=True)
class CandidateRecord:
    ticker: str
    company: str
    exchange: str
    country: str
    event_date: str
    event_type: EventType
    relationship_level: RelationshipLevel
    counterparty: str
    summary: str
    why_mentioned: str
    unilateral: bool
    economic_impact_note: str
    price_reaction_note: str
    sources: list[SourceRef]
    scores: DiscoveryScores
    discovery_score: int
    status: Status
    review_by: str
    fingerprint: str
    captured_at: str
    score_rationale: str
    supersedes: str = ""
    red_flags: list[RedFlag] = field(default_factory=list)
    mispricing_hypothesis: str = ""
    falsification_signals: list[str] = field(default_factory=list)
    kill_rules_triggered: list[str] = field(default_factory=list)
    next_questions: list[str] = field(default_factory=list)
    outcome_note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateRecord":
        record = cls(
            ticker=_required_str(data, "ticker"),
            company=_required_str(data, "company"),
            exchange=_required_str(data, "exchange"),
            country=_required_str(data, "country"),
            event_date=_required_str(data, "event_date"),
            event_type=_enum_value(data, "event_type", set(EventType.__args__)),
            relationship_level=_enum_value(data, "relationship_level", {"A", "B", "C", "D", "E"}),
            counterparty=_required_str(data, "counterparty"),
            summary=_required_str(data, "summary"),
            why_mentioned=_required_str(data, "why_mentioned"),
            unilateral=_required_bool(data, "unilateral"),
            economic_impact_note=_required_str(data, "economic_impact_note"),
            price_reaction_note=_required_str(data, "price_reaction_note"),
            sources=[SourceRef.from_dict(item) for item in _required_dict_list(data, "sources")],
            scores=DiscoveryScores.from_dict(_required_dict(data, "scores")),
            discovery_score=_bounded_int(data, "discovery_score", 0, 20),
            status=_enum_value(data, "status", set(Status.__args__)),
            review_by=_required_str(data, "review_by"),
            fingerprint=_required_str(data, "fingerprint"),
            captured_at=_required_str(data, "captured_at"),
            score_rationale=_required_str(data, "score_rationale"),
            supersedes=str(data.get("supersedes", "")),
            red_flags=[
                _member(value, set(RedFlag.__args__), "red_flags")
                for value in data.get("red_flags", [])
            ],
            mispricing_hypothesis=str(data.get("mispricing_hypothesis", "")),
            falsification_signals=list(data.get("falsification_signals", [])),
            kill_rules_triggered=list(data.get("kill_rules_triggered", [])),
            next_questions=list(data.get("next_questions", [])),
            outcome_note=str(data.get("outcome_note", "")),
        )
        record.validate()
        return record

    def validate(self) -> None:
        if self.discovery_score != self.scores.total:
            raise ValueError("discovery_score must equal the sum of the four score components")
        if _STATUS_ORDER[self.status] >= 2 and not self.has_primary_or_secondary_source():
            raise ValueError(
                "status verified/watchlist/candidate/promoted/rejected requires a tier 1 or 2 source"
            )
        if self.status in {"candidate", "promoted"} and self.scores.evidence_score <= 2:
            raise ValueError("gate G1: evidence_score <= 2 cannot reach candidate/promoted")
        if self.status in {"candidate", "promoted"} and self.relationship_level == "E":
            raise ValueError("gate G2: relationship level E cannot reach candidate/promoted")
        if self.status == "promoted":
            if not self.mispricing_hypothesis.strip():
                raise ValueError("promoted records require mispricing_hypothesis")
            if not self.falsification_signals:
                raise ValueError("promoted records require falsification_signals")
        if self.status == "rejected" and not self.kill_rules_triggered:
            raise ValueError("rejected records must list kill_rules_triggered")
        if self.unilateral and "unilateral_claim_only" not in self.red_flags:
            raise ValueError("unilateral events must carry the unilateral_claim_only red flag")
        if (
            self.relationship_level in {"A", "B"}
            and not any(source.tier == 1 for source in self.sources)
        ):
            raise ValueError("relationship level A/B requires at least one tier 1 source")
        if self.status not in {"lead", "expired"} and self._has_pending_marker():
            raise ValueError("records with pending or unverified fields must stay at status=lead")

    def has_primary_or_secondary_source(self) -> bool:
        return any(source.tier in {1, 2} for source in self.sources)

    def _has_pending_marker(self) -> bool:
        marker_values = [
            self.summary,
            self.why_mentioned,
            self.economic_impact_note,
            self.price_reaction_note,
            self.score_rationale,
            self.mispricing_hypothesis,
            *(source.excerpt for source in self.sources),
            *self.falsification_signals,
            *self.next_questions,
        ]
        return any(
            any(marker in value.lower() for marker in PENDING_MARKERS) for value in marker_values
        )


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_dict_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a non-empty array of objects")
    return value


def _bounded_int(data: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum or value > maximum:
        raise ValueError(f"{key} must be an integer between {minimum} and {maximum}")
    return value


def _enum_value(data: dict[str, Any], key: str, allowed: set[Any]) -> Any:
    return _member(data.get(key), allowed, key)


def _member(value: Any, allowed: set[Any], key: str) -> Any:
    if value not in allowed:
        allowed_values = ", ".join(sorted(str(item) for item in allowed))
        raise ValueError(f"{key} must be one of: {allowed_values}")
    return value
