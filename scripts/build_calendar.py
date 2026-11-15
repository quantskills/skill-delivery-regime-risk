# -*- coding: utf-8 -*-
"""
Q5 任务#4（数据侧）：构建 RB/HC 交割月梯度事件日历
- 事件定义（上期所风控办法梯度）：T-1 = 交割月前第一月第一个交易日，T0 = 交割月第一个交易日
- 数据验证：从 limit_up/pre_settlement 提取每日实际停板幅度，检验梯度在真实数据中的体现
- 输出：data/event_calendar.csv（合约×梯度时点×前后停板幅度×持仓量对照）
"""
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DAILY = os.path.join(DATA, "daily")


def load_all() -> pd.DataFrame:
    """合并 187 个合约日线为一张宽表"""
    frames = []
    for f in os.listdir(DAILY):
        if f.endswith(".csv"):
            frames.append(pd.read_csv(os.path.join(DAILY, f)))
    df = pd.concat(frames, ignore_index=True)
    df["date"] = df["date"].astype(str)
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def main():
    detail = pd.read_csv(os.path.join(DATA, "future_detail.csv"))
    detail["maturity_date"] = detail["maturity_date"].astype(str).str.replace("-", "")
    daily = load_all()

    # 实际停板幅度 = limit_up / pre_settlement - 1（用涨跌停反推当日执行的风险参数）
    daily["band_pct"] = ((daily["limit_up"] / daily["pre_settlement"] - 1) * 100).round(1)
    # 日收益率（结算价口径，用于事件窗口风险度量）
    daily["ret"] = daily.groupby("symbol")["settlement"].pct_change()

    rows = []
    for c in detail.itertuples(index=False):
        sym, mat = c.symbol, c.maturity_date
        if len(mat) != 8:
            continue
        sub = daily[daily["symbol"] == sym]
        if sub.empty:
            continue
        y, m = int(mat[:4]), int(mat[4:6])
        # 交割月前第一月 / 交割月 的字符串前缀（YYYYMM）
        prev_ym = f"{y}{m-1:02d}" if m > 1 else f"{y-1}12"
        deli_ym = mat[:6]
        # 各阶段第一个交易日
        prev_first = sub[sub["date"].str.startswith(prev_ym)]["date"].min()
        deli_first = sub[sub["date"].str.startswith(deli_ym)]["date"].min()
        if pd.isna(deli_first):
            continue  # 无交割月交易数据（异常合约）

        def around(d0, n):
            """以日期 d0 为界取前/后 n 日窗口"""
            if pd.isna(d0):
                return None
            dates = sub["date"].values
            pos = (dates >= d0).argmax() if (dates >= d0).any() else None
            if pos is None:
                return None
            lo, hi = max(0, pos - n), min(len(sub) - 1, pos + n)
            return sub.iloc[lo:hi + 1]

        # T-1（交割月前第一月首日）前后窗口
        w1 = around(prev_first, 5)
        # T0（交割月首日）前后窗口
        w0 = around(deli_first, 5)

        def agg(w):
            if w is None or w.empty:
                return {}
            return {
                "band_before": w["band_pct"].iloc[0],
                "band_after_max": w["band_pct"].iloc[0:].max(),
                "band_after_min": w["band_pct"].iloc[0:].min(),
                "oi_entry": w["open_interest"].iloc[0],
                "oi_min": w["open_interest"].min(),
                "ret_abs_max": w["ret"].abs().max(),
            }

        r = {
            "symbol": sym,
            "variety": c.underlying_symbol,
            "maturity": mat,
            "t_prevmonth": prev_first if pd.notna(prev_first) else "",
            "t_delimonth": deli_first,
            "margin_rate_base": c.margin_rate,
            **{f"prev_{k}": v for k, v in agg(w1).items()},
            **{f"deli_{k}": v for k, v in agg(w0).items()},
        }
        rows.append(r)

    cal = pd.DataFrame(rows).sort_values(["variety", "maturity"]).reset_index(drop=True)
    out = os.path.join(DATA, "event_calendar.csv")
    cal.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"事件日历 {len(cal)} 条 -> {out}")

    # 梯度体现统计：T-1 与 T0 前后停板幅度是否有台阶
    for col in ["prev_band_before", "deli_band_before"]:
        chg = cal[f"{col}"] < cal[f"{col.replace('before', 'after_max')}"]
        print(f"{col} -> after_max 上升比例: {chg.mean():.1%}")

    # 打印近 6 个合约样例
    cols = ["symbol", "t_prevmonth", "t_delimonth", "prev_band_before",
            "prev_band_after_max", "deli_band_before", "deli_band_after_max"]
    print(cal[cols].tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
