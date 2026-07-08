from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

from discovery_engine.collectors.base import RateLimitedFetcher, RawFiling
from discovery_engine.collectors.edgar_8k import (
    accession_from_path,
    daily_index_url,
    parse_daily_index,
)

# 只关心公开市场买入。transactionCode 含义（SEC Form 4 说明）：
#   P = open-market purchase（唯一算数的信号）
#   A = grant/award，M = option exercise，S = sale —— 全部忽略
ROUTINE_THRESHOLD_USD = 50_000.0

FILING_DIR_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/"
_XML_HREF_PATTERN = re.compile(r'href="([^"]+\.xml)"', re.IGNORECASE)


def parse_form4_xml(xml_text: str) -> dict:
    """解析 Form 4 XML，汇总 P 代码（公开市场买入）交易。

    返回：{insider_name, insider_title, issuer_ticker, issuer_name,
           purchase_total_usd, purchase_shares, is_10b5_1, transactions: [...]}
    没有 P 交易时 purchase_total_usd = 0。
    """
    root = ET.fromstring(xml_text)

    def text(path: str, default: str = "") -> str:
        node = root.find(path)
        return (node.text or default).strip() if node is not None and node.text else default

    result = {
        "insider_name": text("reportingOwner/reportingOwnerId/rptOwnerName"),
        "insider_title": text("reportingOwner/reportingOwnerRelationship/officerTitle"),
        "issuer_ticker": text("issuer/issuerTradingSymbol"),
        "issuer_name": text("issuer/issuerName"),
        "is_10b5_1": text("aff10b5One") == "1" or text("aff10b5One").lower() == "true",
        "purchase_total_usd": 0.0,
        "purchase_shares": 0.0,
        "transactions": [],
    }
    for txn in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code_node = txn.find("transactionCoding/transactionCode")
        code = (code_node.text or "").strip() if code_node is not None and code_node.text else ""
        shares = _value(txn, "transactionAmounts/transactionShares")
        price = _value(txn, "transactionAmounts/transactionPricePerShare")
        result["transactions"].append({"code": code, "shares": shares, "price": price})
        if code == "P":
            result["purchase_total_usd"] += shares * price
            result["purchase_shares"] += shares
    return result


def is_routine(parsed: dict, threshold_usd: float = ROUTINE_THRESHOLD_USD) -> bool:
    """例行买入不生成事件：金额过小，或 10b5-1 预设计划。"""
    return parsed["purchase_total_usd"] < threshold_usd or bool(parsed["is_10b5_1"])


def collect_form4(day: date, fetcher: RateLimitedFetcher | None = None) -> list[RawFiling]:
    """拉取某天全部 Form 4，只保留非例行的 P 买入。"""
    fetcher = fetcher or RateLimitedFetcher()
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    index_text = fetcher.get_text(daily_index_url(day))
    filings: list[RawFiling] = []
    for entry in parse_daily_index(index_text, form_prefix="4"):
        if entry["form"] != "4":  # 排除 4/A 等修正件，修正件人工处理
            continue
        accession = accession_from_path(entry["path"])
        dir_url = FILING_DIR_URL.format(
            cik=entry["cik"], accession_nodash=accession.replace("-", "")
        )
        xml_url = _find_xml_url(fetcher.get_text(dir_url), dir_url)
        if not xml_url:
            continue
        parsed = parse_form4_xml(fetcher.get_text(xml_url))
        if parsed["purchase_total_usd"] <= 0 or is_routine(parsed):
            continue
        filings.append(
            RawFiling(
                accession=accession,
                form_type="4",
                cik=entry["cik"],
                company=entry["company"],
                filed_date=entry["filed_date"],
                source_url=xml_url,
                captured_at=captured_at,
                extra={
                    "event_type": "insider_buying",
                    "needs_classification": False,
                    "insider_name": parsed["insider_name"],
                    "insider_title": parsed["insider_title"],
                    "issuer_ticker": parsed["issuer_ticker"],
                    "purchase_total_usd": round(parsed["purchase_total_usd"], 2),
                    "purchase_shares": parsed["purchase_shares"],
                },
            )
        )
    return filings


def _find_xml_url(dir_html: str, dir_url: str) -> str:
    for href in _XML_HREF_PATTERN.findall(dir_html):
        name = href.rsplit("/", 1)[-1]
        if "index" not in name.lower():
            return dir_url + name if not href.startswith("http") else href
    return ""


def _value(node: ET.Element, path: str) -> float:
    child = node.find(path + "/value")
    if child is None or not child.text:
        return 0.0
    try:
        return float(child.text.strip())
    except ValueError:
        return 0.0
