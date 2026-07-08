from __future__ import annotations

import copy
from datetime import date

from discovery_engine.extractors.to_candidate import convert_batch, raw_to_lead
from discovery_engine.models import CandidateRecord
from discovery_engine.reports.weekly import build_weekly_report
from tests.test_models import VALID_RECORD

RAW_8K = {
    "accession": "0000320193-26-000042",
    "form_type": "8-K",
    "cik": "320193",
    "company": "EXAMPLE CORP",
    "filed_date": "2026-07-07",
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000042/0000320193-26-000042-index.htm",
    "captured_at": "2026-07-08",
    "extra": {"items": ["1.01", "9.01"], "event_type": "formal_agreement", "needs_classification": False},
}

RAW_FORM4 = {
    "accession": "0001234567-26-000001",
    "form_type": "4",
    "cik": "1234567",
    "company": "EXAMPLE CORP",
    "filed_date": "2026-07-07",
    "source_url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/form4.xml",
    "captured_at": "2026-07-08",
    "extra": {
        "event_type": "insider_buying",
        "needs_classification": False,
        "insider_name": "DOE JOHN",
        "insider_title": "CEO",
        "issuer_ticker": "XYZ",
        "purchase_total_usd": 125000.0,
        "purchase_shares": 10000.0,
    },
}

RAW_UNCLASSIFIED = dict(RAW_8K, accession="0000999999-26-000007",
                        extra={"items": ["8.01"], "event_type": "", "needs_classification": True})


def test_raw_8k_to_lead() -> None:
    record = raw_to_lead(RAW_8K)
    assert record is not None
    assert record.status == "lead"
    assert record.event_type == "formal_agreement"
    assert record.sources[0].tier == 1
    assert record.review_by == "2026-10-05"  # event_date + 90 天


def test_raw_form4_to_lead_uses_ticker_and_insider() -> None:
    record = raw_to_lead(RAW_FORM4)
    assert record is not None
    assert record.ticker == "XYZ"
    assert record.counterparty == "DOE JOHN"
    assert "125,000" in record.summary


def test_unclassified_goes_to_queue() -> None:
    assert raw_to_lead(RAW_UNCLASSIFIED) is None
    leads, queue = convert_batch([RAW_8K, RAW_FORM4, RAW_UNCLASSIFIED])
    assert len(leads) == 2
    assert len(queue) == 1
    assert queue[0]["accession"] == "0000999999-26-000007"


def test_convert_batch_dedups_same_fingerprint() -> None:
    leads, _ = convert_batch([RAW_8K, dict(RAW_8K, accession="different-accession")])
    assert len(leads) == 1


def make_record(**overrides) -> CandidateRecord:
    data = copy.deepcopy(VALID_RECORD)
    data.update(overrides)
    return CandidateRecord.from_dict(data)


def test_weekly_report_sections() -> None:
    records = [
        make_record(),
        make_record(
            fingerprint="dilution00000001",
            red_flags=["dilution_or_insider_selling"],
            status="verified",
        ),
        make_record(fingerprint="expired000000001", status="expired",
                    outcome_note="auto-expired on 2026-07-01: review_by passed"),
    ]
    report = build_weekly_report(records, date(2026, 7, 8))
    assert "# Discovery Engine 周报 2026-07-08" in report
    assert "推荐进入 3+1" in report
    assert "G5 稀释门槛触发清单" in report
    assert report.count("XYZ") >= 3
    assert "（无）" in report  # 空小节正常渲染
