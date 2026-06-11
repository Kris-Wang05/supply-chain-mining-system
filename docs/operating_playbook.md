# Operating Playbook

本系统的最佳用法不是一次性让 Agent 跑完整条八阶段流水线。长任务会诱发捷径：用叙事代替取数、用模式匹配代替硬锚点、评级先于证据。

正确分工：

- 用户：流水线质检员。审核上一阶段输出，决定是否进入下一阶段。
- Codex：单工位研究工人。一次只跑一个 Stage，只交付事实集合和待验证清单。
- Stage 6：由用户和 AI 协作做四问与赔率建模。
- Stage 7：仓位和执行永远由用户独立决定。

## Default Workflow

1. 选择一张任务卡。
2. Codex 只执行该卡，不跳到后续阶段。
3. 用户抽查来源和逻辑。
4. 审核通过后，把输出 commit 到 repo。
5. 下一阶段只使用已审核输出作为输入。

Codex 的 `A` 只代表“值得用户花一小时继续核”，不代表“值得买入”。

## Persistent State

仓库必须维护这些状态文件：

- `state/mainline_registry.md`：主线清单、生命周期、嫁接密度、证伪信号。
- `state/anchor_facts.json`：已审核锚点事实。
- `candidate_cards/`：单票候选卡和尽调记录。

没有持久状态就没有增量比较；没有增量比较，Agent 每次都会从零开始，容易幻觉或重复旧结论。

## Task Card 1: Anchor Facts

每月运行，或主线出现新硬数字时运行。

```text
任务:针对主线 [X],采集锚点事实。
规则:
1. 只接受前瞻性的产能/数量/金额承诺 (wpm、片/年、美元、舰数),
   收入占比等结果性指标一律不合格
2. 每条锚点必须附:原文摘录一句 (逐字) + URL + 日期 + Tier 分级
3. 打不开来源 = 标 [unverified],禁止凭记忆补数字
4. 输出:锚点表 + 一行"本月相对上月的新增/失效锚点"
```

## Task Card 2: Process Decomposition

只在锚点经用户确认后运行。

```text
任务:把锚点 [Y] 分解为工序链/BOM。
对每个环节回答三问:供给结构 (垄断/双寡头/分散)、
缩放函数 (线性/超线性/可选)、传导类型 (designed-in/sole-source/
按片耗材/产能缺口/竞标)。
要求:明确区分"当前订单的传导"和"未来世代的传导",
两者不得混在同一节点。
输出:节点表,每个节点附一句因果链文字推导。
```

## Task Card 3: Ticker Mapping

对单个节点运行，不对整条主线泛泛扫描。

```text
任务:对节点 [Z] 枚举上市标的。
硬性规则:
1. 每个节点必须枚举至少一个 EU 标的 (Xetra/米兰/阿姆斯特丹/巴黎),
   确实没有就写 "EU: none exists",禁止默认只扫美股
2. 任何字段写"需验证/需拆"的候选,评级只准写 PENDING
3. 对每个非 PENDING 候选,单独写一段"市场为什么还没定价它"
   的假说,且必须引用证据 (覆盖行数、6个月相对板块超额收益、
   电话会词频),用"可能/或许"支撑的假说自动降级
```

## Task Card 4: Red-Flag Diligence

对单只候选运行。这是 Agent 最适合承担的工作。

```text
任务:对 [ticker] 执行七条 kill rules 尽调。
逐条输出:规则名 / pass或fail / 证据原文摘录 / 来源。
特别核查:最近8个季度的增发与ATM记录、backlog与
pipeline的措辞区分、大额合同的counterparty原文、
内部人交易记录 (Form 4 / Directors' Dealings)。
```

## Task Card 5: Keyword Graft Monitor

每周自动运行，只输出监控变化，不直接升级或降级仓位。

```text
任务:扫描 [词汇表] 在小市值公司 (<$2B) 新闻稿/电话会中的
出现频次,对比上月。输出:新增嫁接者名单 + 各主线
嫁接密度变化 + 升降级建议 (仅建议,不执行)。
```

## Four Operating Rules

### 1. State Persistence

每次任务卡输出都要进入 repo。没有状态文件，Codex 不能声称“新增”“失效”或“变化”。

### 2. Adversarial Second Pass

任何被评为 `A` 或 `B` 的候选，必须新开一次 bear-frame 检查：

```text
请扮演 short seller，给出做空 [ticker] 的最强三条论据。
```

牛熊两份报告的交集是可信事实；差集是人工核查清单。

### 3. Citation Audit Tax

每份输出随机抽两条引用，手动打开 URL 核对原文。发现一次编造，该批次全部降级重跑。

Prompt 中必须明确写入：引用会被随机抽查。

### 4. Division Of Labor

Codex 产出的是经过初筛的事实集合，不是结论。流程必须是：

```text
Codex 跑卡1-5 -> 用户抽查 -> Stage 6 四问与赔率建模 -> 用户独立做 Stage 7 仓位
```

任何一步都不得跳级，尤其不得把 Codex 的评级直接当成买入清单。

## Recommended Cadence

- 卡5：每周自动跑。
- 卡1：每月跑一次。
- 卡2-4：新锚点出现或用户看上某票时按需触发。

## System Test

用 `FY2026 SCN 采购九艘 LSM (中型登陆舰)` 作为锚点跑卡2。它不是热门卖方链条；若系统能从中挖出至少一个 designed-in 分包商候选，说明系统开始从复述已知转向生产未知。

