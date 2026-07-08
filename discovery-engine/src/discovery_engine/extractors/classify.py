from __future__ import annotations

import json
from pathlib import Path

from discovery_engine.models import EventType

# 人工分类决定文件（JSONL），每行：
#   {"accession": "...", "action": "<event_type>"}   分类成该事件类型，入池
#   {"accession": "...", "action": "discard"}        噪声，从队列移除（raw 保留）
# 未出现在决定文件里的队列项保持原样。
VALID_ACTIONS = set(EventType.__args__) | {"discard"}


def load_queue(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def apply_decisions(queue: list[dict], decisions: list[dict]) -> tuple[list[dict], list[dict]]:
    """返回 (分类完成待入池的 raws, 剩余队列)。

    决定里的 accession 必须在队列中、action 必须合法，否则整批报错——
    分类是人工判断，出错宁可中止也不静默跳过。
    """
    by_accession = {entry["accession"]: entry for entry in queue}
    classified: list[dict] = []
    removed: set[str] = set()
    for decision in decisions:
        accession = decision.get("accession", "")
        action = decision.get("action", "")
        if accession not in by_accession:
            raise ValueError(f"decision references unknown accession: {accession}")
        if action not in VALID_ACTIONS:
            raise ValueError(f"invalid action {action!r} for {accession}; "
                             f"must be an event_type or 'discard'")
        if accession in removed:
            raise ValueError(f"duplicate decision for accession: {accession}")
        removed.add(accession)
        if action != "discard":
            raw = dict(by_accession[accession])
            raw["extra"] = dict(raw.get("extra", {}), event_type=action, needs_classification=False)
            classified.append(raw)
    remaining = [entry for entry in queue if entry["accession"] not in removed]
    return classified, remaining


def format_queue_listing(queue: list[dict], limit: int) -> str:
    """人读的待分类清单：accession、公司、Items、URL。"""
    lines = [f"classification queue: {len(queue)} entries (showing up to {limit})", ""]
    for entry in queue[:limit]:
        items = ", ".join(entry.get("extra", {}).get("items", [])) or "?"
        lines.append(
            f"{entry['accession']}  {entry['filed_date']}  items[{items}]  {entry['company']}"
        )
        lines.append(f"    {entry['source_url']}")
    return "\n".join(lines)
