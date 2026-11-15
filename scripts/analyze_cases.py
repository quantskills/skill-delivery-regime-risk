# -*- coding: utf-8 -*-
"""
Q5 任务#6：误报/漏报案例分析
- 误报A：停板台阶≠梯度生效（取证：±3% 全周期统一；可见台阶=单边市联动/临时调整）
- 误报B：规则触发提前减仓的机会成本（价格延续时 A 的持有收益低于冻结基线 B）
- 漏报A：带仓最差单日发生在 T-1 之前（交割月规则覆盖不到的时段）
- 漏报B：流动性先行萎缩（进入 T-1 时 OI 已较峰值大幅衰减，制度时点滞后于市场）
- 漏报C：临时风控调整不在梯度日历（2023-07 保证金7%/停板5% 的事件实证）
- 输出：data/case_analysis.csv（漏报A逐合约）+ report/cases.md（案例档案，供报告引用）
"""
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DAILY = os.path.join(DATA, "daily")
REPORT = os.path.join(BASE, "reports")
os.makedirs(REPORT, exist_ok=True)

N_A = N_B = 5  # 与 run_experiment.py 一致的减仓节奏


def load_daily() -> pd.DataFrame:
    frames = [pd.read_csv(os.path.join(DAILY, f))
              for f in os.listdir(DAILY) if f.endswith(".csv")]
    df = pd.concat(frames, ignore_index=True)
    df["date"] = df["date"].astype(str)
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def paths(sub: pd.DataFrame, t_prev: str, t_deli: str):
    """复现实验的两条持仓路径，返回 (win, posA, posB, ret)——index 已归零"""
    sub = sub.reset_index(drop=True)  # 教训：iloc 前必须归零（notes.md 有记录）
    idx = sub.index[sub["date"] >= t_prev]
    if len(idx) == 0:
        return None
    i_prev = idx[0]
    win = sub.iloc[max(0, i_prev - 40):].reset_index(drop=True)
    if win.empty:
        return None

    def mk(t_reduce, n_days):
        r = win.index[win["date"] >= t_reduce]
        if len(r) == 0:
            return None
        i0 = r[0]
        return pd.Series([1.0] * i0 + [max(0.0, 1.0 - (i - i0 + 1) / n_days)
                                       for i in range(i0, len(win))], index=win.index)

    posA, posB = mk(t_prev, N_A), mk(t_deli, N_B)
    if posA is None or posB is None:
        return None
    ret = win["settlement"].astype(float).pct_change().fillna(0)
    return win, posA, posB, ret


def main():
    cal = pd.read_csv(os.path.join(DATA, "event_calendar.csv"), dtype=str)
    cal["maturity"] = cal["maturity"].astype(str)
    daily = load_daily()
    lines = ["# Q5 误报/漏报案例档案（任务#6 自动生成）", ""]

    # ---------- 漏报A：最差单日发生在 T-1 之前 ----------
    rows = []
    for c in cal.itertuples(index=False):
        sub = daily[daily["symbol"] == c.symbol]
        if sub.empty or not c.t_prevmonth:
            continue
        sub = sub.reset_index(drop=True)
        ret = sub["settlement"].astype(float).pct_change()
        i_worst = ret.abs().idxmax()
        worst_date = sub.loc[i_worst, "date"]
        rows.append({
            "symbol": c.symbol, "t_prevmonth": c.t_prevmonth,
            "worst_date": worst_date, "worst_ret": round(ret.loc[i_worst], 4),
            "before_Tprev": worst_date < c.t_prevmonth,
        })
    miss_a = pd.DataFrame(rows)
    miss_a.to_csv(os.path.join(DATA, "case_analysis.csv"),
                  index=False, encoding="utf-8-sig")
    pct_before = miss_a["before_Tprev"].mean()
    lines += ["## 漏报A：最差单日早于 T-1（规则覆盖外）",
              f"- {miss_a['before_Tprev'].sum()}/{len(miss_a)}（{pct_before:.0%}）合约的带仓最差单日"
              f"发生在 T-1 之前——交割月梯度规则对此无保护", ""]
    top = miss_a[miss_a["before_Tprev"]].reindex(
        miss_a.loc[miss_a["before_Tprev"], "worst_ret"].abs().sort_values(ascending=False).index)
    lines += ["典型漏报案例（最差单日 Top5，均在 T-1 之前）：",
              "| 合约 | 最差日 | 单日结算价变动 | T-1 时点 |", "|---|---|---|---|"]
    for r in top.head(5).itertuples(index=False):
        lines.append(f"| {r.symbol} | {r.worst_date} | {r.worst_ret:+.1%} | {r.t_prevmonth} |")
    lines.append("")

    # ---------- 误报A：停板台阶来源分类（非梯度） ----------
    has_step = cal[cal["deli_band_after_max"].notna()].copy()
    has_step["band_before"] = has_step["deli_band_before"].astype(float)
    has_step["band_after"] = has_step["deli_band_after_max"].astype(float)
    up = has_step[has_step["band_after"] > has_step["band_before"] + 0.01]
    # 单边市联动特征：新停板 = 3% + 3pp / +5pp 等（即 6/8/11 一类值）；临时调整：5% 等

    def origin(v):
        if abs(v - 6.0) < 0.3 or abs(v - 8.0) < 0.3 or abs(v - 11.0) < 0.3:
            return "单边市联动(+3/+5pp)"
        return "临时调整公告"

    up["origin"] = up["band_after"].map(origin)
    cnt = up["origin"].value_counts()
    lines += ["## 误报A：T0 前后停板台阶的来源（若用台阶检测梯度会误报）",
              f"- {len(up)}/{len(has_step)} 合约在 T0 窗口可见停板台阶，"
              f"但取证证实停板全周期统一 ±3%、无交割梯度", f"- 台阶来源分类：{dict(cnt)}", ""]
    for r in up.head(3).itertuples(index=False):
        lines.append(f"  - 例：{r.symbol} 停板 {r.band_before:.0f}%→{r.band_after:.0f}%（{r.origin}），"
                     f"梯度变量实为保证金率 10%→15%")
    lines.append("")

    # ---------- 误报B：提前减仓的机会成本 ----------
    costs = []
    for c in cal.itertuples(index=False):
        sub = daily[daily["symbol"] == c.symbol]
        if sub.empty or not c.t_prevmonth or not c.t_delimonth:
            continue
        p = paths(sub, c.t_prevmonth, c.t_delimonth)
        if p is None:
            continue
        win, posA, posB, ret = p
        pnl_a, pnl_b = (ret * posA).sum(), (ret * posB).sum()
        costs.append({"symbol": c.symbol, "pnl_a": pnl_a, "pnl_b": pnl_b,
                      "diff": pnl_a - pnl_b})  # 多头视角；空头对称
    costs = pd.DataFrame(costs)
    n_neg = (costs["diff"] < 0).sum()
    lines += ["## 误报B：规则触发提前减仓的机会成本（多头视角，空头对称）",
              f"- {n_neg}/{len(costs)}（{n_neg/len(costs):.0%}）合约上路径 A 持有收益低于冻结基线 B"
              f"（价格在 T-1 后延续上行，提前减仓少赚）", ""]
    worst = costs.nsmallest(3, "diff")
    for r in worst.itertuples(index=False):
        lines.append(f"  - 例：{r.symbol} A 收益 {r.pnl_a:+.1%} vs B {r.pnl_b:+.1%}"
                     f"（放弃 {r.diff:+.1%}）——规则在平稳/趋势市中的代价")
    lines.append("")

    # ---------- 漏报B：流动性先行萎缩 ----------
    decay = []
    for c in cal.itertuples(index=False):
        sub = daily[daily["symbol"] == c.symbol]
        if sub.empty or not c.t_prevmonth:
            continue
        sub = sub.reset_index(drop=True)
        i = sub.index[sub["date"] >= c.t_prevmonth]
        if len(i) == 0:
            continue
        peak = sub.iloc[:i[0]]["open_interest"].max()  # T-1 之前的 OI 峰值
        at_t1 = sub.loc[i[0], "open_interest"]
        if peak and peak > 0:
            decay.append({"symbol": c.symbol,
                          "oi_at_T1": at_t1, "oi_peak": peak,
                          "remain": at_t1 / peak})
    decay = pd.DataFrame(decay)
    lines += ["## 漏报B：进入 T-1 时持仓量（OI）已较峰值衰减——制度时点滞后于市场流动性",
              f"- OI/峰值 中位 {decay['remain'].median():.0%}，"
              f"25分位 {decay['remain'].quantile(.25):.0%}，最极端 {decay['remain'].min():.0%}",
              "- 含义：市场自发移仓早于 T-1，最需要提前减仓的时点早于制度触发点", ""]
    ex = decay.nsmallest(3, "remain")
    for r in ex.itertuples(index=False):
        lines.append(f"  - 例：{r.symbol} 进入 T-1 时 OI 仅剩峰值 {r.remain:.0%}"
                     f"（{r.oi_at_T1:.0f} vs {r.oi_peak:.0f} 手）")
    lines.append("")

    # ---------- 漏报C：临时风控调整不在梯度日历（2023-07 实证） ----------
    rb23 = daily[(daily["symbol"].str.startswith("RB"))
                 & (daily["date"] >= "20230501") & (daily["date"] <= "20231031")].copy()
    rb23["band"] = ((rb23["limit_up"] / rb23["pre_settlement"] - 1) * 100).round(1)
    around = rb23[(rb23["date"] >= "20230717") & (rb23["date"] <= "20230721")]
    jump = around.groupby("date")["band"].mean()
    lines += ["## 漏报C：临时调整不在梯度日历（2023-07-19 结算起停板3%→5%、保证金7%）",
              f"- 受影响合约数（窗口内有数据）：{around['symbol'].nunique()}",
              f"- 2023-07-17~21 逐日全样本平均停板：{ {d: round(v, 1) for d, v in jump.items()} }",
              "- 含义：梯度日历只覆盖制度化时点，临时风控公告构成漏报源，需公告流补充", ""]

    out = os.path.join(REPORT, "cases.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n案例档案 -> {out}；漏报A明细 -> data/case_analysis.csv")


if __name__ == "__main__":
    main()
