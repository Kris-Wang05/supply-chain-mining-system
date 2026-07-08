from __future__ import annotations

from datetime import date, timedelta

from discovery_engine.dedup import event_fingerprint
from discovery_engine.models import CandidateRecord

REVIEW_WINDOW_DAYS = 90


def raw_to_lead(raw: dict) -> CandidateRecord | None:
    """把一条 raw 采集记录转成 status=lead 的 CandidateRecord。

    - 采集器已分类的用其 event_type；needs_classification 的返回 None（进待分类队列）。
    - 一切未知字段填 [unverified]，符合 lead 状态的 pending 规则。
    - 上下文调查十问、评分、门槛全部留给后续人工/任务卡，这里只做结构转换。
    """
    extra = raw.get("extra", {})
    event_type = extra.get("event_type", "")
    if not event_type or extra.get("needs_classification"):
        return None

    ticker = extra.get("issuer_ticker") or raw["cik"]  # 8-K 没有 ticker 时先用 CIK，resolver 后补
    event_date = raw["filed_date"]
    counterparty = extra.get("insider_name") or "[unverified]"
    review_by = (date.fromisoformat(event_date) + timedelta(days=REVIEW_WINDOW_DAYS)).isoformat()

    summary_bits = [f"{raw['form_type']} filed by {raw['company']}"]
    if extra.get("items"):
        summary_bits.append(f"items {', '.join(extra['items'])}")
    if extra.get("purchase_total_usd"):
        summary_bits.append(
            f"open-market purchase ${extra['purchase_total_usd']:,.0f} by {extra.get('insider_name', '?')}"
        )

    return CandidateRecord.from_dict(
        {
            "ticker": ticker,
            "company": raw["company"],
            "exchange": "[unverified]",
            "country": "US",
            "event_date": event_date,
            "event_type": event_type,
            "relationship_level": "D",
            "counterparty": counterparty,
            "summary": "; ".join(summary_bits),
            "why_mentioned": "[unverified]",
            "unilateral": False,
            "economic_impact_note": "[unverified]",
            "price_reaction_note": "[unverified]",
            "sources": [
                {
                    "url": raw["source_url"],
                    "publisher": "SEC EDGAR",
                    "published_date": event_date,
                    "captured_at": raw["captured_at"],
                    "tier": 1,
                    "excerpt": "; ".join(summary_bits),
                }
            ],
            "scores": {
                "change_score": 0,
                "evidence_score": 0,
                "economic_impact_score": 0,
                "recognition_gap_score": 0,
            },
            "discovery_score": 0,
            "status": "lead",
            "review_by": review_by,
            "fingerprint": event_fingerprint(ticker, event_type, counterparty, event_date),
            "captured_at": raw["captured_at"],
            "score_rationale": "[unverified]",
        }
    )


def convert_batch(raws: list[dict]) -> tuple[list[CandidateRecord], list[dict]]:
    """返回 (转换成功的 leads, 待分类队列)。同批内指纹去重，保留先出现的。"""
    leads: list[CandidateRecord] = []
    queue: list[dict] = []
    seen: set[str] = set()
    for raw in raws:
        record = raw_to_lead(raw)
        if record is None:
            queue.append(raw)
        elif record.fingerprint not in seen:
            leads.append(record)
            seen.add(record.fingerprint)
    return leads, queue
