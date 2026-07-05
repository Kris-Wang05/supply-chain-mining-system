from __future__ import annotations

from discovery_engine.models import Band, CandidateRecord

_BAND_ORDER: list[Band] = ["priority", "candidate_pool", "watchlist", "noise"]


def score_band(total: int) -> Band:
    if total >= 16:
        return "priority"
    if total >= 13:
        return "candidate_pool"
    if total >= 9:
        return "watchlist"
    return "noise"


def assign_band(record: CandidateRecord) -> Band:
    """分档 = min(分数档, 门槛档)。门槛 G1–G5 见 docs/framework_v0.2.md 第 2 节。"""
    band = score_band(record.discovery_score)

    # G3: 无一级/二级来源，不参与分档
    if not record.has_primary_or_secondary_source():
        return "noise"
    # G1: 证据门槛
    if record.scores.evidence_score <= 2:
        band = _cap(band, "watchlist")
    # G2: 关系门槛
    if record.relationship_level == "E":
        band = _cap(band, "watchlist")
    # G4: 已定价降一档
    if "price_already_moved" in record.red_flags:
        band = _demote(band)
    # G5: 稀释降一档
    if "dilution_or_insider_selling" in record.red_flags:
        band = _demote(band)
    return band


def _cap(band: Band, ceiling: Band) -> Band:
    return band if _BAND_ORDER.index(band) >= _BAND_ORDER.index(ceiling) else ceiling


def _demote(band: Band) -> Band:
    index = min(_BAND_ORDER.index(band) + 1, len(_BAND_ORDER) - 1)
    return _BAND_ORDER[index]
