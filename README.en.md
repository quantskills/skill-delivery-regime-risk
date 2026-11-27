# Q5: Can Delivery-Month Regime Events Form Useful Pre-emptive Risk Rules?

[简体中文](README.md) | English

Original author: gedingbaod. Released with the author's authorization under [GPL-3.0-only](LICENSE). QuantSkills release maintainer: [abgyjaguo](https://github.com/abgyjaguo).

**One-line conclusion**: Yes — but only for positions lingering into the delivery month. Triggering position reduction at T-1 (first trading day of the month before delivery, when margin steps from 5%→10%) saves a **median 51.4%** of margin-occupation integral versus a frozen baseline (consistent across 173/173 contracts). It does **not** protect against systemic shocks (82% of worst single-day moves occur *before* T-1).

- **Commodity group**: SHFE rebar (RB) + hot-rolled coil (HC), 187 historical contracts (2009–2026)
- **Platform**: QuantStudio (panda_data SDK) via its real entry point, 597+3 calls fully logged
- **Division of labor with E10**: this study covers contract-level regime timing; E10 covers portfolio funding stress

## Quick Start

```bash
python scripts/run_all.py         # One-shot repro: verify -> pull -> calendar -> experiment -> cases
python scripts/run_all.py --fast  # Data already in place; analysis only (after param changes)
```

Or step by step:

```bash
python scripts/verify_env.py      # 1. Platform connectivity (requires credential env vars)
python scripts/pull_data.py       # 2. Fetch data (idempotent; bundled data auto-skips)
python scripts/build_calendar.py  # 3. Event calendar (steps 3-5 re-runnable offline)
python scripts/run_experiment.py  # 4. A/B experiment (core result)
python scripts/analyze_cases.py   # 5. False-positive/negative cases
```

Prerequisites: conda main environment (panda_data + pandas); environment variables `PANDA_DATA_USERNAME` / `PANDA_DATA_PASSWORD`.

## Directory Guide

| Path | Contents |
|---|---|
| `reports/Q5_report.md` | **Research report (start here)**: methods, results, value assessment, applicability |
| `reports/rule_card.md` | Rule card: trigger points → position checks → reduction actions + production rollout steps |
| `reports/cases.md` | False-positive / false-negative case archive (5 categories) |
| `references/rules_evidence.md` | Rule evidence: verbatim official clauses + URLs + historical evolution |
| `data/event_calendar.csv` | Event calendar, 181 rows (contract × T-1/T0) |
| `data/experiment_result.csv` | Per-contract A/B experiment results |
| `data/case_analysis.csv` | Per-contract detail of false-negative A (worst day before T-1) |
| `platform_logs/` | Platform call logs: pull_log.jsonl (597 calls) + verify_env.json + output_samples.json (full return samples) |
| `scripts/` | 7 reproducible scripts (incl. run_all.py one-shot entry) |
| `notes.md` | Project decisions, API pitfalls, experiment corrections |

## Headline Numbers

| Metric | A: early reduction (median) | B: frozen baseline (median) | Reading |
|---|---|---|---|
| Margin-occupation integral | 72,712 | 152,283 | −51.4%, 100% directionally consistent |
| Days with open exposure | 44 | 65 | −32% |
| Worst day while holding | −0.02 | −0.02 | No improvement (rule boundary) |
| Opportunity cost of early reduction | — | — | Under-performs in 47% of contracts, up to 19pp forgone |

Three reliable negative results and the full applicability boundary are in `reports/Q5_report.md`, Section 7.
