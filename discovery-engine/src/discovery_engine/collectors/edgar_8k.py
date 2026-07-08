from __future__ import annotations

import re
from datetime import date, datetime, timezone

from discovery_engine.collectors.base import RateLimitedFetcher, RawFiling

# 8-K Item 编号 -> event_type 的确定性映射。
# 映射不到的 Item 一律进待分类队列（extra["needs_classification"]=True），禁止猜。
ITEM_EVENT_MAP: dict[str, str] = {
    "1.01": "formal_agreement",          # Entry into a Material Definitive Agreement
    "1.03": "debt_restructuring",        # Bankruptcy or Receivership
    "2.01": "ma_or_strategic_investment",  # Completion of Acquisition or Disposition
    "2.02": "financial_inflection",      # Results of Operations
    "2.03": "debt_restructuring",        # Creation of a Direct Financial Obligation
    "8.01": "",                          # Other Events —— 必须人工分类
    "5.02": "",                          # 高管变动 —— 必须人工分类
    "7.01": "",                          # Reg FD Disclosure —— 必须人工分类
}

DAILY_INDEX_URL = "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.{yyyymmdd}.idx"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{accession}-index.htm"

_ITEMS_PATTERN = re.compile(r"Items?[^\d]{0,20}((?:\d+\.\d+(?:\s*,\s*)?)+)", re.IGNORECASE)


def quarter_of(day: date) -> int:
    return (day.month - 1) // 3 + 1


def daily_index_url(day: date) -> str:
    return DAILY_INDEX_URL.format(
        year=day.year, quarter=quarter_of(day), yyyymmdd=day.strftime("%Y%m%d")
    )


def parse_daily_index(text: str, form_prefix: str = "8-K") -> list[dict]:
    """解析 EDGAR form.idx（固定列宽文本）。返回 form/company/cik/date/path 字典列表。

    idx 格式：头部若干行后是 'Form Type ... File Name' 表头 + 分隔线，之后每行一条。
    列宽不完全固定，按最后一列（路径）和倒数第二列（日期）从右往左切。
    """
    entries: list[dict] = []
    in_body = False
    for line in text.splitlines():
        if not in_body:
            if line.strip().startswith("---"):
                in_body = True
            continue
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        path = parts[-1]
        filed = parts[-2]
        cik = parts[-3]
        form = parts[0]
        if not form.startswith(form_prefix):
            continue
        # 首列是 form，末三列是 cik/date/path，中间全部是公司名（多空格折叠为单空格）
        company = " ".join(parts[1:-3])
        entries.append(
            {"form": form, "company": company, "cik": cik.lstrip("0") or "0", "filed_date": _iso(filed), "path": path}
        )
    return entries


def parse_items_from_index_html(html: str) -> list[str]:
    """从 filing 的 -index.htm 页面提取 8-K Item 编号列表。"""
    match = _ITEMS_PATTERN.search(html)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def accession_from_path(path: str) -> str:
    """edgar/data/320193/0000320193-26-000001.txt -> 0000320193-26-000001"""
    return path.rsplit("/", 1)[-1].removesuffix(".txt")


def map_items_to_event_type(items: list[str]) -> tuple[str, bool]:
    """返回 (event_type, needs_classification)。多 Item 时取第一个能映射的。"""
    for item in items:
        mapped = ITEM_EVENT_MAP.get(item, "")
        if mapped:
            return mapped, False
    return "", True


def collect_8k(day: date, fetcher: RateLimitedFetcher | None = None) -> list[RawFiling]:
    """拉取某天全部 8-K：日索引 -> 每份 filing 的 index 页取 Items。

    网络层唯一入口是 fetcher；测试时注入 stub。
    """
    fetcher = fetcher or RateLimitedFetcher()
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    index_text = fetcher.get_text(daily_index_url(day))
    filings: list[RawFiling] = []
    for entry in parse_daily_index(index_text, form_prefix="8-K"):
        accession = accession_from_path(entry["path"])
        index_url = FILING_INDEX_URL.format(
            cik=entry["cik"], accession_nodash=accession.replace("-", ""), accession=accession
        )
        items = parse_items_from_index_html(fetcher.get_text(index_url))
        event_type, needs_classification = map_items_to_event_type(items)
        filings.append(
            RawFiling(
                accession=accession,
                form_type=entry["form"],
                cik=entry["cik"],
                company=entry["company"],
                filed_date=entry["filed_date"],
                source_url=index_url,
                captured_at=captured_at,
                extra={
                    "items": items,
                    "event_type": event_type,
                    "needs_classification": needs_classification,
                },
            )
        )
    return filings


def _iso(yyyymmdd: str) -> str:
    digits = yyyymmdd.replace("-", "")
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
