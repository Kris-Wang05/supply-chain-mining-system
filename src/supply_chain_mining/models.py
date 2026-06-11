from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Transmission = Literal[
    "designed-in",
    "sole-source",
    "per-unit-consumable",
    "capacity-gap",
    "competitive-bid",
]
Rating = Literal["A", "B", "C", "pending", "坐标", "出局"]
TestResult = Literal["pass", "fail", "unknown"]


@dataclass(frozen=True)
class CoverageTest:
    coverage_density: TestResult
    rerating_check: TestResult
    keyword_density: TestResult

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoverageTest":
        return cls(
            coverage_density=_enum_value(data, "coverage_density", {"pass", "fail", "unknown"}),
            rerating_check=_enum_value(data, "rerating_check", {"pass", "fail", "unknown"}),
            keyword_density=_enum_value(data, "keyword_density", {"pass", "fail", "unknown"}),
        )


@dataclass(frozen=True)
class Candidate:
    ticker: str
    exchange: str
    region: Literal["US", "EU", "coordinate"]
    node: str
    transmission_type: Transmission
    order_inevitability: int
    purity_pct: str
    coverage_test: CoverageTest
    kill_rules_triggered: list[str] = field(default_factory=list)
    price_history_note: str = ""
    rating: Rating = "C"
    mispricing_hypothesis: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candidate":
        candidate = cls(
            ticker=_required_str(data, "ticker"),
            exchange=_required_str(data, "exchange"),
            region=_enum_value(data, "region", {"US", "EU", "coordinate"}),
            node=_required_str(data, "node"),
            transmission_type=_enum_value(
                data,
                "transmission_type",
                {
                    "designed-in",
                    "sole-source",
                    "per-unit-consumable",
                    "capacity-gap",
                    "competitive-bid",
                },
            ),
            order_inevitability=_bounded_int(data, "order_inevitability", 1, 5),
            purity_pct=_required_str(data, "purity_pct"),
            coverage_test=CoverageTest.from_dict(_required_dict(data, "coverage_test")),
            kill_rules_triggered=list(data.get("kill_rules_triggered", [])),
            price_history_note=str(data.get("price_history_note", "")),
            rating=_enum_value(data, "rating", {"A", "B", "C", "pending", "坐标", "出局"}),
            mispricing_hypothesis=str(data.get("mispricing_hypothesis", "")),
        )
        candidate.validate()
        return candidate

    def validate(self) -> None:
        if self.rating in {"A", "B"} and not self.mispricing_hypothesis.strip():
            raise ValueError("A/B candidates require mispricing_hypothesis")
        if self.rating == "出局" and not self.kill_rules_triggered:
            raise ValueError("Rejected candidates should list kill_rules_triggered")
        if self.rating in {"A", "B", "C"} and self._has_pending_marker():
            raise ValueError("Candidates with pending or unverified fields must use rating=pending")

    def _has_pending_marker(self) -> bool:
        marker_values = [
            self.purity_pct,
            self.price_history_note,
            self.mispricing_hypothesis,
            self.coverage_test.coverage_density,
            self.coverage_test.rerating_check,
            self.coverage_test.keyword_density,
            *self.kill_rules_triggered,
        ]
        markers = ("unknown", "[unverified]", "需验证", "需拆", "tbd", "pending source")
        return any(any(marker in value.lower() for marker in markers) for value in marker_values)


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _bounded_int(data: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value < minimum or value > maximum:
        raise ValueError(f"{key} must be an integer between {minimum} and {maximum}")
    return value


def _enum_value(data: dict[str, Any], key: str, allowed: set[str]) -> Any:
    value = data.get(key)
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{key} must be one of: {allowed_values}")
    return value
