# Discovery Engine（股票发现引擎）

只负责回答一个问题：**"为什么这家公司现在值得研究？"**
不判断公司质量、不估值、不给仓位——那是下游 3+1 分析框架的事。

```text
公开信息 → 事件提取 → 上下文调查 → 证据验证 → 门槛过滤(gate) → 发现评分 → 候选池 → 输出给 3+1
```

## 与 v0.1 草案的主要区别

1. **加法评分改为"门槛 + 评分"两层**：证据分不达标、关系等级为 E、
   或事件已被定价时，总分再高也会被压到观察名单以下。见 `docs/framework_v0.2.md` 第 7 节。
2. **候选记录有生命周期状态机**：lead → contextualized → verified → candidate →
   promoted / watchlist / rejected / expired，每条记录必须有 `review_by` 复查日期，防止僵尸候选。
3. **事件类型和红旗改为受控枚举**，禁止自由文本，保证可去重、可统计误报率。
4. **去重键有明确定义**：`ticker + event_type + counterparty + 事件月份` 的指纹。
5. **强制"已定价检查"**：记录事件披露前后股价/成交量反应，异动过大自动降档。
6. **闭环校准**：每条 promoted/rejected 记录保留结局字段，季度回看评分规则命中率。

## 目录结构

```text
discovery-engine/
  README.md                    本文件
  docs/
    framework_v0.2.md          优化后的完整框架
    data_sources.md            数据源目录（按质量与可机读性分级）
  prompts/
    codex_task_cards.md        给 codex 的分阶段执行任务卡
  schemas/
    candidate_record.schema.json
  src/discovery_engine/
    models.py                  DiscoveryEvent / CandidateRecord 数据模型 + 校验
    scoring.py                 发现评分 + 门槛分档逻辑
    dedup.py                   事件指纹去重
    cli.py                     template / validate / score 命令
  state/
    candidate_pool.jsonl       候选池（append-only）
    watchlist.md               观察名单（人读）
  tests/
    test_models.py
    test_scoring.py
    test_dedup.py
```

## 快速使用

```bash
# 生成一条候选记录模板
python -m discovery_engine.cli template --ticker XYZ

# 校验 JSONL
python -m discovery_engine.cli validate-candidates state/candidate_pool.jsonl

# 计算分档（读 JSONL，输出每条记录的 band）
python -m discovery_engine.cli score state/candidate_pool.jsonl
```

运行测试：`python -m pytest discovery-engine/tests`（需将 `discovery-engine/src` 加入 PYTHONPATH）。

## 纪律（继承主仓库 operating_playbook）

- 所有数字必须带来源 URL、发布日期、抓取日期和原文摘录（verbatim）。
- 未验证字段标 `[unverified]`，带此标记的记录状态强制为 `lead`。
- 三级来源（新闻/社媒/研报）只能产生线索，不能单独把记录推进到 `verified`。
- 公司单方面宣称的合作，关系等级至少降一级，且必须打 `unilateral_claim_only` 红旗。
- 历史记录 append-only，不允许覆盖；规则改动必须提版本号 + 测试 + Git 提交。
