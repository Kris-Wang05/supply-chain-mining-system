# Discovery Engine — Codex 执行任务卡

沿用主仓库 task-card-first 纪律：一次只做一张卡，不做端到端。
每张卡的产出必须通过 `python -m discovery_engine.cli validate-candidates` 校验后才算完成。

运行环境：把 `discovery-engine/src` 加入 PYTHONPATH。测试命令：

```bash
cd discovery-engine
python -m pytest tests -q
```

---

## Task Card D0：环境验证（先做这个）

1. 运行测试套件，确认全绿。
2. 运行 `python -m discovery_engine.cli template --ticker TEST`，确认模板输出。
3. 把模板的空字段填上占位值（company/exchange 等填 "TEST"，日期填今天），写入一行 JSONL，
   跑 `validate-candidates`，确认含 `[unverified]` 的记录以 status=lead 通过校验。
   注意：空模板本身**应该**校验失败——必填字段为空是设计行为，不是 bug。

产出：一句话确认 + 遇到的任何环境问题。

---

## Task Card D1：EDGAR 8-K 采集器（v1 核心）

写 `src/discovery_engine/collectors/edgar_8k.py`：

- 用 SEC EDGAR full-text search API（`https://efts.sec.gov/LATEST/search-index?q=...&dateRange=...&forms=8-K`）
  或每日索引文件拉取近 N 天的 8-K。
- **必须设置 User-Agent 头（SEC 要求，含联系邮箱），限速 <= 10 req/s。**
- 提取：CIK、ticker、公司名、filing date、8-K Item 编号列表、正文 URL。
- Item → event_type 映射：1.01 → formal_agreement；2.02 → financial_inflection；
  5.02/8.01 → 人工分类（先输出到待分类队列）。
- 输出：原始记录存 `raw/edgar_8k/YYYY-MM-DD.jsonl`（append-only），
  每条含抓取时间戳和原文 URL。**不做任何评分，采集与判断分离。**

验收：给定一个历史日期能拉回当天 8-K 列表；重复运行不产生重复记录（用 accession number 去重）。

## Task Card D2：EDGAR Form 4 采集器

同 D1 结构，`collectors/edgar_form4.py`：

- 只保留 transaction code = P（公开市场买入）的记录。
- 提取：内部人姓名、职务、买入金额、买入后持股变化。
- 单笔金额 < $50k 或例行 10b5-1 计划买入的，标记 `routine=true`，默认不生成事件。

## Task Card D3：事件转换器

`extractors/to_candidate.py`：把 raw 记录转成 CandidateRecord（status=lead），
调用 `dedup.event_fingerprint` 生成指纹，同指纹只保留一条。
输出 append 到 `state/candidate_pool.jsonl`，之后跑 validate 确认。

## Task Card D4：USAspending 采集器

`collectors/usaspending.py`：REST API（免费无 key），按 recipient 查新增合同。
难点是 recipient 名称 → ticker 的映射，先维护一个手工 `state/entity_map.json`，
映射不到的进待分类队列，不要猜。

## Task Card D5：周报生成器

`reports/weekly.py`：读 `state/candidate_pool.jsonl`，输出 markdown 周报到
`output/weekly/YYYY-MM-DD.md`，包含 framework_v0.2.md 第 9 节要求的全部小节
（新发现、分档变化、新增一级证据、expired 清单、G5 稀释触发清单、推荐进入 3+1 的前 5–10 家）。

---

## 通用红线（每张卡都适用）

- 不允许编造 URL、日期或摘录；拿不到就写 `[unverified]`，记录留在 lead。
- 采集器只存事实，不打分。评分是人（或单独任务卡）的事。
- 所有输出 append-only，不覆盖历史。
- 改动 models/scoring 的规则必须同时改测试并说明原因。
