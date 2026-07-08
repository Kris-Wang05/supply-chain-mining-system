from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from discovery_engine.lifecycle import check_transition
from discovery_engine.models import CandidateRecord

# 存储约定（不可覆盖历史 与 池内指纹唯一 的调和方案）：
#   state/candidate_pool.jsonl  每个指纹只有一行 = 最新状态，通过原子重写更新
#   state/history.jsonl         append-only 审计日志，记录每一次写入（含被替换的旧版本时间点）
#   raw/<collector>/*.jsonl     采集器原始记录，append-only，永不修改


def load_pool(path: Path) -> dict[str, CandidateRecord]:
    """读候选池，返回 fingerprint -> record。文件不存在视为空池。"""
    pool: dict[str, CandidateRecord] = {}
    if not path.exists():
        return pool
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = CandidateRecord.from_dict(json.loads(line))
        if record.fingerprint in pool:
            raise ValueError(f"{path}:{line_number}: duplicate fingerprint {record.fingerprint}")
        pool[record.fingerprint] = record
    return pool


def upsert(pool: dict[str, CandidateRecord], record: CandidateRecord) -> dict[str, CandidateRecord]:
    """插入或更新一条记录。更新时强制生命周期转移合法。返回新池（不修改入参）。"""
    existing = pool.get(record.fingerprint)
    if existing is not None:
        check_transition(existing.status, record.status)
    updated = dict(pool)
    updated[record.fingerprint] = record
    return updated


def write_pool(path: Path, pool: dict[str, CandidateRecord], history_path: Path | None = None) -> None:
    """原子重写候选池；若给出 history_path，同时把本次全量快照差异追加进审计日志。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    old = load_pool(path) if path.exists() else {}
    lines = [
        json.dumps(asdict(record), ensure_ascii=False)
        for record in sorted(pool.values(), key=lambda r: (r.ticker, r.fingerprint))
    ]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.replace(tmp, path)

    if history_path is not None:
        changed = [
            record
            for fingerprint, record in pool.items()
            if fingerprint not in old or old[fingerprint] != record
        ]
        if changed:
            append_history(history_path, [asdict(record) for record in changed])


def append_history(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_raw(path: Path, entries: list[dict[str, Any]], key: str) -> int:
    """append-only 写入原始采集记录，按 key 字段去重（如 accession number）。

    返回实际新增条数。已存在的 key 静默跳过——采集器重复运行不产生重复记录。
    """
    seen: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(str(json.loads(line).get(key, "")))
    path.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    with path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            value = str(entry.get(key, ""))
            if not value:
                raise ValueError(f"raw entry missing dedup key {key!r}")
            if value in seen:
                continue
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            seen.add(value)
            added += 1
    return added
