# -*- coding: utf-8 -*-
"""
Q5 平台留痕补全：对 3 个核心接口各存一次完整返回样本（输出记录）
- 弥补 pull_log.jsonl 只记参数+行数、无返回数据的缺口（课题要求"输入与输出记录"）
- 输出：platform_logs/20261115_output_samples.json
"""
import json
import os
import sys
from datetime import datetime

import pandas as pd
import panda_data

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "platform_logs", "20261115_output_samples.json")

# (接口, 入参) —— 与 pull_data.py 实际使用完全一致的参数形态
CALLS = [
    ("get_future_detail",
     {"symbol": "RB2510.SHF"}),
    ("get_future_contract_pool",
     {"underlying_symbol": ["RB", "HC"], "start_date": "20250101", "end_date": "20250630"}),
    ("get_market_data",
     {"symbol": "RB2510.SHF", "start_date": "20250101", "end_date": "20251015",
      "type": "future"}),
]


def main():
    panda_data.init_token(username=os.environ["PANDA_DATA_USERNAME"],
                          password=os.environ["PANDA_DATA_PASSWORD"])
    log = {"run_at": datetime.now().isoformat(), "purpose": "平台输出记录样本存档", "calls": []}
    for api, params in CALLS:
        entry = {"ts": datetime.now().isoformat(), "api": api, "params": params}
        try:
            r = getattr(panda_data, api)(**params)
            df = pd.DataFrame(r) if not isinstance(r, pd.DataFrame) else r
            entry["rows_total"] = len(df)
            entry["columns"] = list(df.columns)
            entry["data"] = df.to_dict(orient="records")  # 完整返回记录
            status = "OK"
        except Exception as e:
            entry["error"] = str(e)[:300]
            status = "FAIL"
        log["calls"].append(entry)
        print(f"[{status}] {api} -> {entry.get('rows_total', '?')} 行完整样本")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2, default=str)
    print(f"输出样本存档 -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
