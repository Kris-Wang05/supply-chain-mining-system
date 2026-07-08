# Discovery Engine 架构说明（codex 必读）

本文档定义模块契约和系统不变量。**改动"不变量"或"冻结区"里的任何内容，
必须先在 PR 里说明理由并同步更新测试；其余部分可以自由扩展。**

---

## 1. 数据流

```text
SEC EDGAR ──collect-8k/collect-form4──> raw/<collector>/YYYY-MM-DD.jsonl   (append-only, accession 去重)
                                              │
                                     ingest (extractors/to_candidate)
                                              │
                    ┌─────────────────────────┴───────────────┐
                    ▼                                         ▼
     state/candidate_pool.jsonl                state/classification_queue.jsonl
     (每指纹一行=最新状态, 原子重写)              (需人工分类的 8.01/5.02/7.01 等)
                    │
        人工调查十问 + 评分 + 状态推进 (upsert, 状态机强制)
                    │
              expire (自动过期)          每次写池同时 append → state/history.jsonl (审计日志)
                    │
              report → output/weekly/YYYY-MM-DD.md
                    │
              promoted 记录 → 3+1 分析框架
```

## 2. 模块契约

| 模块 | 职责 | 禁止 |
|---|---|---|
| `collectors/` | 从数据源拉取事实，输出 `RawFiling` | 评分、判断、过滤"不重要"的记录（例行 Form 4 除外，规则见代码） |
| `collectors/base.py` | 唯一的 HTTP 出口（UA + 限速） | 任何采集器绕过 `RateLimitedFetcher` 直接发请求 |
| `extractors/` | raw → `CandidateRecord(status=lead)` 结构转换 | 填任何编造的值；未知一律 `[unverified]`；分类不了的进队列，不许猜 |
| `models.py` | 数据模型 + 全部校验规则（门槛 G1/G2 在这里强制） | 放宽校验来"让数据通过" |
| `scoring.py` | 分数分档 + 门槛 G1–G5 | 引入模型校验之外的新数据依赖 |
| `lifecycle.py` | 状态机 + 过期 | 增加绕过状态机的旁路 |
| `storage.py` | 池的原子读写、审计日志、raw 去重 | 直接用 open() 写池文件 |
| `reports/` | 纯函数生成 markdown | 在报告里修改记录状态 |
| `cli.py` | 命令编排 | 业务逻辑（全部下沉到对应模块） |

## 3. 系统不变量（冻结区）

1. **池内指纹唯一**：`candidate_pool.jsonl` 每个 fingerprint 只有一行 = 最新状态。
2. **历史不可覆盖**：每次池变更同时追加 `history.jsonl`；raw 文件 append-only 永不修改。
3. **状态推进走状态机**：`storage.upsert` 强制 `lifecycle.check_transition`，没有旁路。
4. **门槛在模型层强制**：G1（证据 ≤2 不得 candidate+）、G2（E 级不得 candidate+）在
   `CandidateRecord.validate` 里，写不进池就是写不进，不靠自觉。
5. **pending 标记锁定 lead**：任何字段含 `[unverified]`/`unknown` 等标记的记录只能是 lead/expired。
6. **采集与判断分离**：collectors 只存事实；评分字段在 ingest 后由人工（或独立任务卡）填写。
7. **SEC 合规**：自定义 User-Agent（含联系方式）、请求间隔 ≥0.15s，全部走 `RateLimitedFetcher`。
8. **8-K Item 映射是确定性的**：`ITEM_EVENT_MAP` 映射不到 → 待分类队列。给队列做自动分类
   属于新功能，需要单独任务卡和测试。

## 4. 关键设计决策（为什么这么做）

- **无第三方依赖**（纯标准库）：环境永不腐烂，codex 在任何机器上 `python -m pytest` 直接跑。
- **8-K 用日索引而非全文搜索 API**：`form.YYYYMMDD.idx` 是固定格式纯文本，十年不变；
  全文搜索 API 的响应结构无正式文档，不值得依赖。
- **池文件"最新状态"+ 单独审计日志**，而不是池内多版本：读池的代码（评分、报告）永远
  不需要处理"哪条是最新"的问题；回溯需求走 history.jsonl。
- **Form 4 只保留非例行 P 买入**：阈值 $50k + 排除 10b5-1，在采集层过滤是唯一例外
  （信号密度太低，全存会淹没 raw 层），阈值改动需改 `ROUTINE_THRESHOLD_USD` 并说明。

## 5. 已实现 vs 待实现

| 状态 | 内容 |
|---|---|
| ✅ 已实现并有测试 | 模型/校验、评分门槛、去重、生命周期、存储、8-K 采集器、Form 4 采集器、转换器、周报、CLI 全链路 |
| ✅ 已对真实 SEC 冒烟验证 | 日索引解析（214 份 8-K）、Items 提取 |
| ⬜ codex 待做 | 见 prompts/codex_task_cards.md：日常运行、ticker resolver、USAspending、分类队列处理 |

## 6. 运行手册（日常操作序列）

```bash
cd discovery-engine
python -m discovery_engine.cli collect-8k    --date 2026-07-07
python -m discovery_engine.cli collect-form4 --date 2026-07-07
python -m discovery_engine.cli ingest raw/edgar_8k/2026-07-07.jsonl
python -m discovery_engine.cli ingest raw/edgar_form4/2026-07-07.jsonl
python -m discovery_engine.cli expire
python -m discovery_engine.cli report
python -m pytest        # 任何改动后必须全绿
```
