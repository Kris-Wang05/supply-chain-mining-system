from __future__ import annotations

import json
from datetime import date

from discovery_engine.extractors.to_candidate import raw_to_lead
from discovery_engine.resolvers.cik_ticker import load_map, parse_company_tickers, resolve
from tests.test_extractors_reports import RAW_8K

SAMPLE_PAYLOAD = {
    "fields": ["cik", "name", "ticker", "exchange"],
    "data": [
        [320193, "Example Corp", "XYZ", "Nasdaq"],
        [320193, "Example Corp (pref)", "XYZ-P", "Nasdaq"],  # 同 CIK 第二类别，应被忽略
        [1234567, "Other Co", "OTH", "NYSE"],
    ],
}


def test_parse_keeps_first_listing_per_cik() -> None:
    mapping = parse_company_tickers(SAMPLE_PAYLOAD)
    assert mapping["320193"] == {"ticker": "XYZ", "exchange": "Nasdaq", "name": "Example Corp"}
    assert len(mapping) == 2


def test_resolve_strips_leading_zeros() -> None:
    mapping = parse_company_tickers(SAMPLE_PAYLOAD)
    assert resolve("0000320193", mapping)["ticker"] == "XYZ"
    assert resolve("999", mapping) is None


def test_load_map_uses_fresh_cache_without_fetch(tmp_path) -> None:
    cache = tmp_path / "map.json"
    cache.write_text(
        json.dumps({"fetched_at": "2026-07-05", "map": {"1": {"ticker": "T", "exchange": "N", "name": "x"}}}),
        encoding="utf-8",
    )

    class ExplodingFetcher:
        def get_text(self, url: str) -> str:
            raise AssertionError("must not fetch when cache is fresh")

    mapping = load_map(cache, today=date(2026, 7, 8), fetcher=ExplodingFetcher())
    assert mapping["1"]["ticker"] == "T"


def test_load_map_refetches_stale_cache(tmp_path) -> None:
    cache = tmp_path / "map.json"
    cache.write_text(json.dumps({"fetched_at": "2026-01-01", "map": {}}), encoding="utf-8")

    class StubFetcher:
        def get_text(self, url: str) -> str:
            return json.dumps(SAMPLE_PAYLOAD)

    mapping = load_map(cache, today=date(2026, 7, 8), fetcher=StubFetcher())
    assert mapping["320193"]["ticker"] == "XYZ"
    assert json.loads(cache.read_text(encoding="utf-8"))["fetched_at"] == "2026-07-08"


def test_raw_to_lead_resolves_ticker_and_exchange() -> None:
    mapping = parse_company_tickers(SAMPLE_PAYLOAD)
    record = raw_to_lead(RAW_8K, ticker_map=mapping)
    assert record.ticker == "XYZ"
    assert record.exchange == "Nasdaq"


def test_raw_to_lead_unresolved_keeps_cik() -> None:
    record = raw_to_lead(dict(RAW_8K, cik="999"), ticker_map={})
    assert record.ticker == "999"
    assert record.exchange == "[unverified]"
