---
name: skill-delivery-regime-risk
description: 当需要研究期货交易所制度事件（交割月梯度、限仓、保证金调整等带生效日期的规则）能否形成前置风险规则、构建制度事件日历、或做"提前减仓 vs 冻结基线"对照实验时，使用此 skill。覆盖规则取证→平台拉数→事件日历→统一窗口对照→误报/漏报分析→价值验收的完整流程。
tags: [quant, futures, risk, regime, delivery]
license: GPL-3.0-only
metadata:
  license: GPL-3.0-only
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-delivery-regime-risk
  repository_url: https://github.com/quantskills/skill-delivery-regime-risk
  project_type: skill
  collection: futures-risk
---

# 交割制度事件前置风险规则研究

## 适用场景

- 当用户需要把交易所规则（交割/限仓/保证金梯度）转化为持仓检查和提前减仓条件时
- 当用户需要构建"合约 × 制度生效时点"的事件日历并验证其在数据中的体现时
- 当用户需要量化"规则触发提前减仓 vs 冻结持仓"的风险暴露差异（保证金占用/波动/极端日）时
- 当用户需要制度事件的误报/漏报案例分析（规则覆盖边界）时
- 当结论形态为风控价值（可靠负结果同等可交付）而非事件 alpha 时

## 方法原理

**研究对象**：期货合约上市运行不同阶段的梯度制度（以上期所 RB/HC 为原型）：

| 交易时间段 | RB 保证金 | HC 保证金 | 附带变化 |
|---|---|---|---|
| 挂牌之日起 | 5% | 4% | 一般限仓 RB 90000 / HC 120000 手 |
| 交割月前第一月首日起（T-1） | 10% | 10% | 限仓 RB 4500 / HC 9000 手 |
| 交割月首日起（T0） | 15% | 15% | 限仓 RB 900 / HC 1800 手；30 手整倍数 |
| 最后交易日前二交易日起（L-2） | 20% | 20% | — |

规则出处与逐字条款见 `references/rules_evidence.md`（官方一手 URL + 核实等级标注）。

### 对照实验设计（只变一个变量的干净对照）

两条持仓路径共享**同一评估窗口**（T-1 前 40 个交易日 ~ 摘牌）与**同一梯度参数**，
唯一差异为减仓触发日：

```
路径 A（规则）：T-1 当日触发持仓检查，此后 N_A=5 个交易日线性减至 0
路径 B（基线）：持仓冻结越过 T-1，直到 T0 后 N_B=5 个交易日线性减至 0
```

每合约度量四指标（同窗口积分，可直接比较）：

```
保证金占用积分 margin_int = Σ_t ( settlement_t × 乘数 × margin_t × pos_t )
波动暴露   vol_exposure   = std(ret) × Σ_t pos_t
带仓最差日 worst_day      = min_t ( ret_t × pos_t )
暴露天数   n_days_exposed = #{ t : pos_t > 0 }
```

其中当日保证金率 `margin_t` 按四档梯度对日历月匹配赋值（末档=最后交易日前二交易日起）。

### 关键坑 1：评估窗口错位 → 伪"无差异"结果

若路径 A、B 各用各的窗口（如 B 从 T0 前 40 日起算），积分基线不同，比较是苹果比橘子，
会得出"A 仅 49% 合约优于 B"的伪结果。**铁律：对照实验共享同一时间轴，只变持仓路径。**
（本 skill 早期版本曾犯此错并留档 `notes.md`，v2 修正后 A 在 173/173 合约上占优。）

### 关键坑 2：pandas 布尔过滤后 index 未归零 → 窗口错位

`daily[daily.symbol==sym]` 的 index 是全局行号；直接 `iloc[全局行号-40:]` 会切出空/错位窗口
（症状：181 个合约只剩 1 个通过过滤）。**铁律：`sub.reset_index(drop=True)` 后再做位置切片。**

### 关键坑 3：停板台阶 ≠ 梯度生效（信号错位）

涨跌停板可能全周期统一（RB/HC 为 ±3%），**梯度上调的变量是保证金率与限仓，不是停板**。
数据中可见的停板台阶来自单边市联动（D2 停板 +3pp、D3 +5pp，特征值 6/8/11%）与临时调整公告。
先取证规则文本确认梯度变量，再选检测量；用停板台阶检测梯度会产生系统性误报。

### 关键坑 4：制度参数历史分段

交易所规则跨修订点（如 RB 2011 手册六档 → 2016 手册四档）时，回测须按官方锚点分段设参；
锚点间的修订公告若不可得，宁可标注【未核实】并分段近似，不可编造。自然人清零时点、
交割制度（五日→二日）等亦随版本变化。

### 误报/漏报分析框架（5 类，均可数据化）

| 类型 | 定义 | 检测法 |
|---|---|---|
| 漏报A 规则覆盖外 | 风险事件早于 T-1 | 带仓最差单日日期 vs T-1 比较（RB/HC 实测 82% 在 T-1 前） |
| 误报A 信号错位 | 把非梯度信号当梯度 | 停板台阶来源分类（联动档/临时调整，实测 0 个来自梯度） |
| 误报B 机会成本 | 触发减仓但价格延续 | A/B 持有收益差分布（实测 47% 合约 A 少赚，最大 19pp） |
| 漏报B 时点滞后 | 制度时点晚于市场 | 事件日 OI / 生命周期峰值（实测中位仅剩 30%） |
| 漏报C 临时调整 | 临时风控不在日历 | 已知临时调整日的停板数据实证（如 2023-07-20 跳 5.0%） |

## 输入数据

使用 Panda data SDK（QuantStudio 平台入口）拉取期货合约生命周期与日线。
正式研究必须使用 PandaAI data 数据拉取库或项目明确指定的数据源。

| 数据 | 接口 | 用途 |
|---|---|---|
| 历史活跃合约池 | `get_future_contract_pool` | 半年窗遍历得全历史合约清单 |
| 合约生命周期 | `get_future_detail` | 上市/退市/到期/交割起止/margin_rate |
| 期货日线 | **`get_market_data(type='future')`** | 结算价/持仓量/停板——**唯一正路**，不传 type 默认查股票返回空 |
| 主力映射 | `get_future_dominant` | 环境验证（参数是 `underlying_symbol` 非 symbol） |

字段口径、日期格式差异（daily=YYYYMMDD，future_detail=YYYY-MM-DD）与接口踩坑详见
`references/data_guide.md`。

## 输出结果

| 文件 | 粒度 | 关键字段 |
|---|---|---|
| `data/contracts.csv` | 合约 | symbol, underlying_symbol |
| `data/future_detail.csv` | 合约 | listed/de_listed/maturity/start_delivery/end_delivery, margin_rate |
| `data/daily/<SYMBOL>.csv` | 日 | settlement, pre_settlement, open_interest, limit_up/down, volume |
| `data/event_calendar.csv` | 合约×时点 | t_prevmonth, t_delimonth（YYYYMMDD）, margin_rate_base, prev_/deli_ 前缀 band/oi/ret 对照 |
| `data/experiment_result.csv` | 合约 | sample（current/early 制度分段）, A_/B_ 前缀的 margin_int/vol_exposure/worst_day/n_days_exposed |
| `data/case_analysis.csv` | 合约 | worst_date, worst_ret, before_Tprev |
| `reports/cases.md` | 汇总 | 五类误报/漏报案例档案 |

## 评价标准

对照实验类任务需同时报告**改善面**与**边界面**，不允许只报节省不报代价：

| 分类 | 指标 | 方向 | 说明 |
|---|---|---|---|
| 改善 | 保证金占用节省比例 | 越大越好 | 1 − A_margin_int/B_margin_int（RB/HC 实测中位 51.4%） |
| 改善 | 波动暴露 / 暴露天数 | 越小越好 | 100% 合约方向一致则规则无需逐合约调参 |
| 边界 | 带仓最差单日 | 相等也算结论 | 实测中位无差异（风险在 T-1 前），规则边界证据 |
| 边界 | 机会成本分布 | 如实报告 | 多头视角 A−B 收益差（空头对称） |
| 边界 | 事件日 OI/峰值 | 越低越说明时点滞后 | 制度约束对象的再定位依据 |

硬性要求：

- **统一评估窗口**：A/B 共享时间轴，只变持仓路径（关键坑 1）。
- **梯度参数须有官方出处**（条款号 + URL），历史分段点用官方锚点。
- **负结果单独成节**：规则覆盖外的风险、机会成本、时点滞后必须量化呈现。
- 价值验收按三问陈述：改变什么决策 / 作用多大（核心数字）/ 适用边界。

## 代码结构

- `scripts/run_all.py` —— 一键复现入口（按序编排以下步骤，`--fast` 跳过前两步，失败即中止）
- `scripts/verify_env.py` —— 平台连通性验证（4 接口，留痕 platform_logs/）
- `scripts/pull_data.py` —— 数据拉取层：合约池→生命周期→日线（幂等断点续传，jsonl 留痕）
- `scripts/build_calendar.py` —— 事件日历：maturity 反推 T-1/T0 + 真实交易日校验 + 停板/OI 对照
- `scripts/run_experiment.py` —— 对照实验：统一窗口 A/B 路径四指标 + 制度分段汇总
- `scripts/analyze_cases.py` —— 五类误报/漏报案例 → `reports/cases.md`
- `scripts/save_output_samples.py` —— 平台完整返回样本存档（补"输出记录"）
- `references/data_guide.md` —— 数据源与字段契约
- `references/rules_evidence.md` —— 规则取证档案（官方逐字条款）

## 使用方式

Agent 使用本 skill 时，在 skill 根目录按序执行：

```bash
python scripts/run_all.py         # 一键：验证→拉数→日历→实验→案例（失败即中止）
python scripts/run_all.py --fast  # 已有 data/，只重跑分析步骤 3–5
```

或分步：

```bash
python scripts/verify_env.py      # 1. 平台连通性（凭证环境变量）
python scripts/pull_data.py       # 2. 拉数（幂等；已有 data/ 则自动跳过）
python scripts/build_calendar.py  # 3. 事件日历
python scripts/run_experiment.py  # 4. 对照实验（核心结果）
python scripts/analyze_cases.py   # 5. 误报/漏报案例
```

运行前设置 `PANDA_DATA_USERNAME` / `PANDA_DATA_PASSWORD`。
本目录已含一套 187 合约的完整数据与留痕（data/ + platform_logs/），步骤 3–5 可离线重跑；
换品种组时删除 data/ 重新执行步骤 2。

## Agent 执行规则

1. 先跑 `verify_env.py` 确认凭证与接口，失败不得继续。
2. 换品种组/窗口时只改 `pull_data.py` 顶部常量（VARIETIES/START_YEAR），其余脚本无参数。
3. 实验前核对梯度参数与 `references/rules_evidence.md` 一致；横跨修订点必须分段。
4. 结果解读必须同时报告改善面与边界面（评价标准硬性要求），负结果如实呈现。
5. 任一步失败，报告失败命令、错误信息与数据日期，不得跳过直接给结论。

## 成功标准

- `build_calendar.py` 输出事件日历覆盖全部样本合约，T-1/T0 与真实交易日一致。
- `run_experiment.py` 输出逐合约 A/B 指标 + 分段汇总，A/B 共享评估窗口。
- `analyze_cases.py` 输出五类案例档案，每类含具体合约、日期与数值。
- 平台调用全程留痕（输入参数 + 行数 + 完整返回样本）。
- 结论包含：核心节省数字、方向一致性比例、至少一条量化负结果、适用边界。

## 验收要求

- 规则数字必须有官方出处（条款号 + URL + 生效日期），二手来源如实标注。
- 对照实验必须统一评估窗口（防伪结果）。
- 必须有冻结基线对照与误报/漏报案例（课题硬性完成条件）。
- 价值验收按"改变什么决策/作用多大/适用边界"三问陈述。
- 正式任务必须使用 PandaAI data 或项目指定数据源。

## 依赖

- Python 3.10+
- pandas
- panda-data（数据源 SDK；离线重跑步骤 3–5 不需要）
