from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from discovery_engine.collectors.base import RateLimitedFetcher

# SEC 官方 CIK <-> ticker/exchange 映射，每日更新
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
CACHE_MAX_AGE_DAYS = 7


def parse_company_tickers(payload: dict) -> dict[str, dict[str, str]]:
    """company_tickers_exchange.json: {"fields": ["cik","name","ticker","exchange"], "data": [[...]]}

    返回 cik(无前导零字符串) -> {"ticker", "exchange", "name"}。
    同一 CIK 多个上市类别（普通股/优先股）时保留第一条（SEC 数据主类别在前）。
    """
    fields = payload["fields"]
    idx = {name: fields.index(name) for name in ("cik", "name", "ticker", "exchange")}
    mapping: dict[str, dict[str, str]] = {}
    for row in payload["data"]:
        cik = str(row[idx["cik"]])
        if cik in mapping:
            continue
        mapping[cik] = {
            "ticker": str(row[idx["ticker"]] or ""),
            "exchange": str(row[idx["exchange"]] or ""),
            "name": str(row[idx["name"]] or ""),
        }
    return mapping


def load_map(
    cache_path: Path,
    today: date | None = None,
    fetcher: RateLimitedFetcher | None = None,
) -> dict[str, dict[str, str]]:
    """带缓存的映射加载：缓存 7 天内直接用，过期或缺失时从 SEC 重拉。"""
    today = today or date.today()
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched = date.fromisoformat(cached["fetched_at"])
        if today - fetched <= timedelta(days=CACHE_MAX_AGE_DAYS):
            return cached["map"]

    fetcher = fetcher or RateLimitedFetcher()
    payload = json.loads(fetcher.get_text(COMPANY_TICKERS_URL))
    mapping = parse_company_tickers(payload)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"fetched_at": today.isoformat(), "map": mapping}, ensure_ascii=False),
        encoding="utf-8",
    )
    return mapping


def resolve(cik: str, mapping: dict[str, dict[str, str]]) -> dict[str, str] | None:
    """CIK -> {"ticker","exchange","name"}；映射不到返回 None（私有公司/基金，人工处理）。"""
    return mapping.get(cik.lstrip("0") or "0")
