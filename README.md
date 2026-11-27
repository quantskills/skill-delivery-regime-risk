# Q5：交割月梯度制度事件能否形成有用的前置风险规则

原作者：gedingbaod。依作者授权以 [GPL-3.0-only](LICENSE) 发布。 QuantSkills 社区发布维护者：[abgyjaguo](https://github.com/abgyjaguo)。

**一句话结论**：能，但只对"滞留近月的持仓"有效——T-1 触发提前减仓相对冻结基线节省保证金占用中位 **51.4%**（173/173 合约方向一致）；不防系统性冲击（82% 最差单日在 T-1 前）。

- **品种组**：上期所 RB（螺纹钢）+ HC（热轧卷板），187 个历史合约（2009–2026）
- **平台**：QuantStudio（panda_data SDK）真实入口，597+3 次调用全程留痕
- **与 E10 分工**：本题做合约制度时点，E10 做组合资金压力

## 快速开始

```bash
python scripts/run_all.py         # 一键复现：验证→拉数→日历→实验→案例
python scripts/run_all.py --fast  # 数据已就位，只重跑分析（改参数后用）
```

或分步执行：

```bash
python scripts/verify_env.py      # 1. 平台连通性（需凭证环境变量）
python scripts/pull_data.py       # 2. 拉数（幂等；本目录已含数据会自动跳过）
python scripts/build_calendar.py  # 3. 事件日历（步骤 3–5 可离线重跑）
python scripts/run_experiment.py  # 4. 对照实验（核心结果）
python scripts/analyze_cases.py   # 5. 误报/漏报案例
```

前提：conda 主环境（panda_data + pandas），环境变量 `PANDA_DATA_USERNAME` / `PANDA_DATA_PASSWORD`。

## 目录导航

| 路径 | 内容 |
|---|---|
| `reports/Q5_report.md` | **研究报告（先看这个）**：方法、结果、价值验收、适用边界 |
| `reports/rule_card.md` | 规则卡：触发时点→检查项→减仓动作 + 实盘接入步骤 |
| `reports/cases.md` | 误报/漏报案例档案（5 类） |
| `references/rules_evidence.md` | 规则取证：官方逐字条款 + URL + 历史演变 |
| `data/event_calendar.csv` | 事件日历 181 条（合约 × T-1/T0） |
| `data/experiment_result.csv` | 对照实验逐合约结果 |
| `data/case_analysis.csv` | 漏报A（最差单日早于 T-1）逐合约明细 |
| `platform_logs/` | 平台调用留痕：pull_log.jsonl（597 次）+ verify_env.json + output_samples.json（完整返回样本） |
| `scripts/` | 7 个可复现脚本（含 run_all.py 一键入口） |
| `notes.md` | 课题决策、接口踩坑、实验修正记录 |
| `README.en.md` | 英文版导读（English guide） |
| `references/data_guide.md` | 数据字典：平台接口入参、日线字段口径、日期格式差异、本地 CSV 结构 |
| `SKILL.md` | 方法论技能卡：同类制度事件课题的复用流程（7 步 + 伪结果陷阱） |

## 核心数字

| 指标 | A 提前减仓 | B 冻结基线 | 结论 |
|---|---|---|---|
| 保证金占用积分（中位） | 72,712 | 152,283 | 节省 51.4%，100% 方向一致 |
| 持仓暴露天数 | 44 | 65 | −32% |
| 带仓最差单日 | −0.02 | −0.02 | 无改善（规则边界） |
| 提前减仓机会成本 | — | — | 47% 合约少赚，最大 19pp |

三条可靠负结果与完整适用边界见 `reports/Q5_report.md` 第七节。
