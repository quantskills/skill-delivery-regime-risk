# -*- coding: utf-8 -*-
"""
Q5 任务#2：拉取 RB/HC 全历史合约的 生命周期 + 日线行情（价格/持仓量）
- 幂等可续传：已有产出文件则跳过
- 全程留痕：每次平台调用追加一行 JSON 到 platform_logs/pull_log.jsonl
- 数据落盘：data/contracts.csv, data/future_detail.csv, data/daily/<SYMBOL>.csv
"""
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd
import panda_data

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
LOG_PATH = os.path.join(BASE, "platform_logs", "pull_log.jsonl")
os.makedirs(DAILY_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

VARIETIES = ["RB", "HC"]          # 品种：螺纹钢、热轧卷板（上期所）
START_YEAR = 2009                 # RB 上市年（HC 2014，多余窗口无害）
END_DATE = "20261115"             # 截至今日
FREQ_SLEEP = 0.15                 # 限速（秒/次）


def log_call(api: str, params: dict, n_rows: int, error: str = None):
    """追加一行平台调用留痕"""
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "api": api,
        "params": params,
        "rows": n_rows,
        **({"error": error[:200]} if error else {}),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def call(api: str, params: dict, retry: int = 1):
    """带留痕与重试的平台调用，返回 DataFrame 或 None"""
    fn = getattr(panda_data, api)
    for attempt in range(retry + 1):
        try:
            r = fn(**params)
            df = pd.DataFrame(r) if not isinstance(r, pd.DataFrame) else r
            log_call(api, params, len(df))
            time.sleep(FREQ_SLEEP)
            return df
        except Exception as e:
            if attempt == retry:
                log_call(api, params, 0, str(e))
                return None
            time.sleep(1.0)


def step1_contract_list() -> pd.DataFrame:
    """按半年窗遍历合约池，得到 RB/HC 历史活跃合约全集"""
    out = os.path.join(DATA_DIR, "contracts.csv")
    if os.path.exists(out):
        df = pd.read_csv(out)
        print(f"[跳过] contracts.csv 已存在（{len(df)} 合约）")
        return df
    frames = []
    for year in range(START_YEAR, 2027):
        for half, (s, e) in enumerate([("0101", "0630"), ("0701", "1231")], 1):
            if f"{year}{e}" > END_DATE:
                e = END_DATE[4:]
                if s > e:
                    continue
            df = call("get_future_contract_pool",
                      {"underlying_symbol": VARIETIES,
                       "start_date": f"{year}{s}", "end_date": f"{year}{e}"})
            if df is not None and not df.empty:
                frames.append(df)
    all_pool = pd.concat(frames, ignore_index=True)
    contracts = (all_pool[all_pool["underlying_symbol"].isin(VARIETIES)]
                 .drop_duplicates("symbol")[["symbol", "underlying_symbol"]]
                 .sort_values("symbol")
                 .reset_index(drop=True))
    contracts.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[完成] 合约清单 {len(contracts)} 个 -> {out}")
    return contracts


def step2_contract_detail(contracts: pd.DataFrame) -> pd.DataFrame:
    """逐合约拉取生命周期（上市/退市/交割起止/保证金率）"""
    out = os.path.join(DATA_DIR, "future_detail.csv")
    done_path = out + ".done"  # 断点标记（已完成的合约清单）
    rows = []
    done = set()
    if os.path.exists(done_path):
        done = set(open(done_path, encoding="utf-8").read().split())
    for i, sym in enumerate(contracts["symbol"], 1):
        if sym in done:
            continue
        df = call("get_future_detail", {"symbol": sym})
        if df is not None and not df.empty:
            rows.append(df)
            with open(done_path, "a", encoding="utf-8") as f:
                f.write(sym + "\n")
        if i % 50 == 0:
            print(f"  detail 进度 {i}/{len(contracts)}")
    detail = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    # 与已有产出合并（断点续传场景）
    if os.path.exists(out):
        detail = pd.concat([pd.read_csv(out), detail], ignore_index=True)
    detail = detail.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    detail.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[完成] 合约明细 {len(detail)} 条 -> {out}")
    return detail


def step3_daily(detail: pd.DataFrame) -> None:
    """逐合约拉取全历史日线（价格+持仓量）
    接口踩坑记录：文档的 get_future_daily 在 SDK 未注册；
    get_future_daily_post(后复权) 对单合约/主力连续均返回空；
    正确入口是 get_market_data(type='future')，字段含
    open/high/low/close/settlement/volume/open_interest/limit_up/down
    """
    need = detail[detail["symbol"].notna()].copy()
    print(f"[开始] 日线拉取，共 {len(need)} 个合约")
    ok = fail = skip = 0
    for i, row in enumerate(need.itertuples(index=False), 1):
        sym = row.symbol
        out = os.path.join(DAILY_DIR, f"{sym.replace('.', '_')}.csv")
        if os.path.exists(out):
            skip += 1
            continue
        # 用生命周期确定窗口；缺日期则用 2009~今
        start = str(getattr(row, "listed_date", "")) or "20090101"
        end = str(getattr(row, "de_listed_date", "")) or END_DATE
        start, end = start.replace("-", "")[:8], end.replace("-", "")[:8]
        if len(start) != 8 or len(end) != 8:
            start, end = "20090101", END_DATE
        frames = []
        # 5 年窗分段（接口限制）
        cs, ce = start, min(end, _shift(start, 5))
        while cs <= end:
            df = call("get_market_data",
                      {"symbol": sym, "start_date": cs, "end_date": ce,
                       "type": "future"})
            if df is not None and not df.empty:
                frames.append(df)
            if ce >= end:
                break
            cs = _shift(ce, 1)
            ce = min(end, _shift(cs, 5))
        if frames:
            daily = pd.concat(frames, ignore_index=True).drop_duplicates(
                subset=["date", "symbol"]).sort_values("date")
            daily.to_csv(out, index=False, encoding="utf-8-sig")
            ok += 1
        else:
            fail += 1
        if i % 20 == 0:
            print(f"  daily 进度 {i}/{len(need)} (ok={ok} skip={skip} fail={fail})")
    print(f"[完成] 日线 ok={ok} skip={skip} fail={fail} -> {DAILY_DIR}")


def _shift(ymd: str, years: int) -> str:
    """日期平移 N 年（用于 5 年窗切分）"""
    y, m, d = int(ymd[:4]), int(ymd[4:6]), min(int(ymd[6:8]), 28)
    return f"{y + years:04d}{m:02d}{d:02d}"


def main():
    panda_data.init_token(username=os.environ["PANDA_DATA_USERNAME"],
                          password=os.environ["PANDA_DATA_PASSWORD"])
    contracts = step1_contract_list()
    detail = step2_contract_detail(contracts)
    step3_daily(detail)
    print("全部拉取完成")


if __name__ == "__main__":
    sys.exit(main())
