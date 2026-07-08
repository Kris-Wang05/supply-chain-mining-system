from __future__ import annotations

import hashlib


def event_fingerprint(ticker: str, event_type: str, counterparty: str, event_date: str) -> str:
    """同一公司 + 同一事件类型 + 同一交易对手 + 同一自然月 = 同一事件。

    event_date 取 ISO 格式（YYYY-MM-DD），指纹只取到月份，跨月持续事件
    每月最多一条新记录，必须用 supersedes 引用上一条。
    """
    month = event_date.strip()[:7]
    key = "|".join(
        part.strip().upper() for part in (ticker, event_type, counterparty, month)
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def find_duplicates(fingerprints: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for fingerprint in fingerprints:
        if fingerprint in seen:
            duplicates.add(fingerprint)
        seen.add(fingerprint)
    return duplicates
