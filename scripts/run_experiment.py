# -*- coding: utf-8 -*-
"""
Q5 任务#5：对照实验——规则驱动提前减仓 vs 冻结基线（v2 修正版）
- 统一评估窗口：T-1（交割月前第一月首日）前 40 个交易日起、到摘牌为止
  —— 两条路径共享同一时间轴与同一保证金率阶梯，唯一差异是持仓路径（可对照）
- 冻结基线 B：T-1~T0 期间持仓不动（承接已翻倍的 prev_month 保证金率），
  T0 后 N_B 日线性减完
- 规则路径 A：T-1 触发持仓检查并提前减仓，T-1 后 N_A 日线性减完
- v1 的教训：A/B 各用各的窗口（B 从 T0 前 40 日起）导致积分不可比（伪无差异）
- 风险暴露度量（每合约，同一窗口内）：
  1. 保证金占用积分（结算价×乘数×当日梯度保证金率×持仓）
  2. 流动性冲击峰值：减仓日内减仓比例/当日成交量
  3. 波动暴露：日波动率×持仓的积分
  4. 带仓最差单日（结算价收益）
  5. 持仓暴露天数
- 输出：data/experiment_result.csv + 汇总打印
"""
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DAILY = os.path.join(DATA, "daily")

# ============ 规则参数（已取证：rules/shfe_delivery_gradient_rules.md） ============
# 梯度四档：(挂牌档, 交割月前第一月T-1起, 交割月T0起, 最后交易日前二交易日起)
LADDER_CURRENT = {"RB": (0.05, 0.10, 0.15, 0.20),   # RB 细则第四十五条
                  "HC": (0.04, 0.10, 0.15, 0.20)}   # HC 细则第四十七条
LADDER_EARLY_RB = (0.07, 0.10, 0.20, 0.30)  # 2011手册六档简化（2016前到期RB，近似）
SPLIT_2016 = "201601"  # 梯度简化(六档→四档)官方锚点=2016手册；此后到期用现行四档
N_A = 5   # 路径A：T-1 后 5 个交易日内减完
N_B = 5   # 路径B：T0 后 5 个交易日内减完
MULTIPLIER = 10.0  # RB/HC 合约乘数（10 吨/手）


def load_daily() -> pd.DataFrame:
    frames = [pd.read_csv(os.path.join(DAILY, f))
              for f in os.listdir(DAILY) if f.endswith(".csv")]
    df = pd.concat(frames, ignore_index=True)
    df["date"] = df["date"].astype(str)
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def simulate(sub: pd.DataFrame, t_prev: str, t_deli: str,
             t_reduce: str, n_days: int, prev_ym: str, deli_ym: str,
             ladder: tuple) -> dict:
    """统一窗口（T-1 前 40 日~摘牌）内，按 t_reduce 触发减仓的风险暴露度量"""
    sub = sub.reset_index(drop=True)  # index 归零：后续 iloc 才是合约内位置而非全局行号
    idx = sub.index[sub["date"] >= t_prev]
    if len(idx) == 0:
        return {}
    i_prev = idx[0]
    win = sub.iloc[max(0, i_prev - 40):].reset_index(drop=True)
    ev = i_prev - max(0, i_prev - 40)  # T-1 在窗口中的实际位置
    r_idx = win.index[win["date"] >= t_reduce]
    if len(r_idx) == 0:
        return {}
    i_red = r_idx[0]  # 减仓触发日（A=T-1，B=T0）

    # 持仓路径：触发日前满仓 1.0，之后 n_days 日线性减到 0
    pos = [1.0] * i_red + [max(0.0, 1.0 - (i - i_red + 1) / n_days)
                           for i in range(i_red, len(win))]
    pos = pd.Series(pos, index=win.index)

    # 当日生效保证金率（四档梯度，前两档按自然月匹配；末档=最后交易日前二交易日起）
    m_normal, m_prev, m_deli, m_last = ladder
    margin = pd.Series(m_normal, index=win.index)
    margin[win["date"].str[:6] == prev_ym] = m_prev
    margin[win["date"].str[:6] == deli_ym] = m_deli
    margin.iloc[-3:] = m_last  # 数据末条≈最后交易日；两路径此时仓位已减完，仅保完整性

    settle = win["settlement"].astype(float)
    volume = win["volume"].astype(float)
    ret = settle.pct_change().fillna(0)

    margin_int = (settle * MULTIPLIER * margin * pos).sum()   # 元·日/手
    cuts = pos.diff().clip(lower=0)                            # 当日减仓比例
    impact = (cuts / volume.replace(0, pd.NA)).max()           # 流动性冲击峰值
    vol = ret.std()
    return {
        "margin_int": float(margin_int),
        "impact_peak": float(impact) if pd.notna(impact) else None,
        "vol_exposure": float((vol * pos).sum()),
        "worst_day": float((ret * pos).min()),
        "n_days_exposed": int((pos > 0).sum()),
    }


def main():
    cal = pd.read_csv(os.path.join(DATA, "event_calendar.csv"), dtype=str)
    daily = load_daily()

    rows = []
    for c in cal.itertuples(index=False):
        sub = daily[daily["symbol"] == c.symbol]
        if len(sub) < 50 or not c.t_prevmonth or not c.t_delimonth:
            continue
        y, m = int(c.maturity[:4]), int(c.maturity[4:6])
        prev_ym = f"{y}{m-1:02d}" if m > 1 else f"{y-1}12"
        deli_ym = c.maturity[:6]
        # 制度分段：2016手册锚点后到期用现行四档；之前 RB 用2011六档近似（HC早期未核实，沿用现行档）
        sample = "current" if c.maturity >= SPLIT_2016 else "early"
        ladder = (LADDER_CURRENT[c.variety] if sample == "current"
                  else (LADDER_CURRENT["HC"] if c.variety == "HC" else LADDER_EARLY_RB))
        # 同一窗口、同一阶梯；唯一差异 = 减仓触发日（T-1 vs T0）
        rA = simulate(sub, c.t_prevmonth, c.t_delimonth, c.t_prevmonth,
                      N_A, prev_ym, deli_ym, ladder)
        rB = simulate(sub, c.t_prevmonth, c.t_delimonth, c.t_delimonth,
                      N_B, prev_ym, deli_ym, ladder)
        if not rA or not rB:
            continue
        rows.append({"symbol": c.symbol, "variety": c.variety, "maturity": c.maturity,
                     "sample": sample,
                     **{f"A_{k}": v for k, v in rA.items()},
                     **{f"B_{k}": v for k, v in rB.items()}})

    res = pd.DataFrame(rows)
    out = os.path.join(DATA, "experiment_result.csv")
    res.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"对照实验(v2 统一窗口+取证梯度) {len(res)} 个合约 -> {out}\n")

    for sample, grp in res.groupby("sample"):
        tag = ("2016后到期(现行四档,高置信)" if sample == "current"
               else "2016前到期(早期梯度,近似)")
        print(f"===== 样本段: {tag}（{len(grp)} 合约） =====")
        print(f"{'指标':14s} {'A(提前减仓)中位':>16s} {'B(冻结基线)中位':>16s}  A优于B")
        for m in ["margin_int", "vol_exposure", "worst_day", "n_days_exposed", "impact_peak"]:
            if f"A_{m}" not in grp:
                continue
            a, b = grp[f"A_{m}"], grp[f"B_{m}"]
            valid = a.notna() & b.notna()
            if valid.sum() == 0:
                continue
            if m == "worst_day":  # 绝对值越小越好
                improved = (a.abs() < b.abs()) & valid
            else:
                improved = (a < b) & valid
            print(f"{m:14s} {a.median():>16.2f} {b.median():>16.2f}  "
                  f"{improved.sum()}/{valid.sum()} = {improved.sum()/valid.sum():.0%}")
        # 规则价值：保证金占用节省比例（任务#7 价值验收的核心数字）
        saving = 1 - grp["A_margin_int"] / grp["B_margin_int"]
        print(f"保证金节省比例: 中位 {saving.median():.1%}, 均值 {saving.mean():.1%}, "
              f"范围 [{saving.min():.1%}, {saving.max():.1%}]\n")


if __name__ == "__main__":
    main()
