# Supply Chain Mining System

产业链挖掘系统是一个面向公开信息的研究流水线，用来从“主线叙事”或“锚点事实”出发，拆解工序链、映射可交易标的，并用覆盖、定价和红旗规则筛掉伪机会。

核心问题只有两个：

- 市场还没有定价什么？
- 为什么是我们先知道？

> 免责声明：本仓库是研究流程与工具骨架，不构成投资建议。所有数字必须附来源与日期；无法验证的内容必须标记为 `[unverified]`。

## 流水线

```text
Stage 0 主线登记 -> Stage 1 锚点事实 -> Stage 2 工序分解 -> Stage 3 标的映射
-> Stage 4 定价检验 -> Stage 5 红旗筛查 -> Stage 6 催化剂建模 -> Stage 7-8 执行与监控
```

自动化边界：

- Stage 0-5：适合由 Codex 或脚本辅助自动化，目标是挖掘、记录、筛选。
- Stage 6-8：必须由人工和 AI 协作完成，目标是判断、建模、执行和复盘。

## 仓库内容

- `docs/supply_chain_mining_system_v1.md`：原始 SOP。
- `docs/agent_sop.md`：面向 Agent 的运行说明。
- `prompts/codex_stage_0_5.md`：让 Codex 执行 Stage 0-5 的提示词模板。
- `schemas/`：阶段输出的 JSON Schema。
- `src/supply_chain_mining/`：最小 Python CLI 和数据模型。
- `tests/`：轻量测试。

## 快速开始

生成一次研究运行模板：

```powershell
$env:PYTHONPATH="src"; python -m supply_chain_mining.cli template --mainline "AI先进封装"
```

校验候选标的 JSONL：

```powershell
$env:PYTHONPATH="src"; python -m supply_chain_mining.cli validate-candidates .\runs\candidates.jsonl
```

本地测试：

```powershell
$env:PYTHONPATH="src"; python -m unittest discover -s tests
```

## 输出纪律

每个候选一行，字段为：

```json
{
  "ticker": "",
  "exchange": "",
  "node": "",
  "transmission_type": "",
  "order_inevitability": 1,
  "purity_pct": "",
  "coverage_test": {
    "coverage_density": "pass",
    "rerating_check": "pass",
    "keyword_density": "pass"
  },
  "kill_rules_triggered": [],
  "price_history_note": "",
  "rating": "C",
  "mispricing_hypothesis": ""
}
```

## Kill Criteria

任一阶段触发 kill criteria，候选应立即出局或降级，不进入后续阶段。尤其注意：

- pipeline、MOU、LOI 不得计入 backlog。
- 大额合同必须读到原文或可信披露。
- 稀释史、关联方订单、无残值楼层是优先红旗。
- 写不出“市场为什么还没定价它”的假说，A/B 级候选自动降级。
