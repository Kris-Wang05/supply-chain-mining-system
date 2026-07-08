# Discovery Engine — Codex 执行任务卡 v2

**先读 `docs/architecture.md`**——模块契约和不变量在那里，冻结区的东西不许改。
核心架构（模型、门槛、状态机、存储、EDGAR 8-K/Form 4 采集器、转换器、周报、CLI）
**已经实现并有 42 个测试**，你的工作是运行、修补和扩展，不是重新设计。

一次只做一张卡。每张卡完成的标准：`python -m pytest` 全绿 + 卡内验收项通过。

---

## Task Card D0：环境验证（先做这个）

1. `cd discovery-engine && python -m pytest`，确认 42 个测试全绿。
2. 跑一遍 architecture.md 第 6 节的日常操作序列（用最近一个交易日的日期）。
   预期：raw/ 下生成两个 JSONL，池里出现 status=lead 的记录，output/weekly/ 生成周报。
3. 检查 state/classification_queue.jsonl：8.01/5.02/7.01 的 8-K 应该在这里，不在池里。

产出：运行结果摘要 + 各文件行数。遇到 SEC 网络问题记录重试情况。

## Task Card D1：ticker resolver

现状：8-K 转换的记录 ticker 字段暂用 CIK。写 `resolvers/cik_ticker.py`：

- 数据源：https://www.sec.gov/files/company_tickers.json（免费，SEC 官方 CIK↔ticker 映射）。
- 下载缓存到 `state/cik_ticker_map.json`，带抓取日期，7 天过期重拉。
- 在 ingest 流程里接入：CIK 能映射的替换成 ticker 并补 exchange；映射不到的保持 CIK 原样
  （多为私有公司/基金，人工处理）。
- 走 `RateLimitedFetcher`，测试用 fixture。

## Task Card D2：分类队列处理流程

`state/classification_queue.jsonl` 里是 Item 8.01/5.02/7.01 等需要人工判断的 8-K。写一个辅助命令：

- `cli classify --limit 20`：逐条打印 accession、公司、Items、filing URL，
  读入人工判定的 event_type（或 skip/discard），合法值校验后转成 lead 进池。
- 处理过的记录从队列移除（重写队列文件，原始 raw 不动）。
- **不做自动分类**。LLM 辅助分类是未来单独的卡，需要先积累人工标注样本。

## Task Card D3：USAspending 采集器

`collectors/usaspending.py`，照抄 edgar_8k.py 的结构（fetch 薄、parse 纯、测试用 fixture）：

- API：POST https://api.usaspending.gov/api/v2/search/spending_by_award/（免费无 key）。
- 按 `time_period` 查新增 prime awards，金额 >= $5M 起步（阈值放常量）。
- recipient → ticker 映射：维护手工 `state/entity_map.json`，映射不到的进待分类队列，不要猜。
- event_type = "government_contract"，raw 去重键用 award id。

## Task Card D4：定期运行与提交纪律

- 写 `scripts/daily_run.py`（或平台等价物）串起 architecture.md 第 6 节的序列。
- 每次运行后 `git add raw/ state/ output/ && git commit -m "scan(daily): N new leads, M expired"`。
- 失败重试：SEC 5xx/超时重试 3 次，间隔 30s；仍失败则记录日期到 `state/missed_days.md`，
  下次运行先补漏。

---

## 通用红线（每张卡都适用）

- **architecture.md 第 3 节的不变量不许动**；确需改动，PR 里单独说明 + 改测试。
- 不编造 URL、日期、摘录；拿不到写 `[unverified]`，记录留在 lead。
- 采集器只存事实，不打分。评分和状态推进是人工环节。
- 所有输出 append-only 或原子重写（走 storage.py），禁止手写 open() 改池。
- 新代码风格对齐现有：frozen dataclass、`from __future__ import annotations`、
  纯函数解析器 + fixture 测试、零第三方依赖。
