# -*- coding: utf-8 -*-
"""
Q5 任务#1：QuantStudio(PandaAI/panda_data) 平台真实入口连通性验证
- 每次调用的入参/返回截取都会写入 platform_logs/，作为「从平台真实入口执行」的记录
"""
import json
import os
import sys
from datetime import datetime

import panda_data

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE, "platform_logs")
os.makedirs(LOG_DIR, exist_ok=True)

log = {"run_at": datetime.now().isoformat(), "calls": []}


def record(api: str, params: dict, result, error: str = None, keep: int = 3):
    """记录一次平台调用：接口名、入参、返回摘要（前 keep 条）/错误"""
    entry = {"api": api, "params": params, "ts": datetime.now().isoformat()}
    if error:
        entry["error"] = str(error)[:300]
    else:
        rows = result if isinstance(result, list) else [result]
        entry["return_type"] = type(result).__name__
        entry["rows_total"] = len(rows) if hasattr(rows, "__len__") else "?"
        entry["rows_sample"] = rows[:keep]
    log["calls"].append(entry)
    status = "FAIL" if error else "OK"
    print(f"[{status}] {api} {params}")
    return entry


def main():
    # 1) 凭证初始化（平台入口）
    try:
        panda_data.init_token(
            username=os.environ["PANDA_DATA_USERNAME"],
            password=os.environ["PANDA_DATA_PASSWORD"],
        )
        record("init_token", {"username": "***"}, "token ok")
    except Exception as e:
        record("init_token", {"username": "***"}, None, e)
        finish(1)

    # 2) 期货合约基本信息（RB 交割月合约——课题数据前提之一）
    try:
        r = panda_data.get_future_detail(symbol="RB2510.SHF")
        record("get_future_detail", {"symbol": "RB2510.SHF"}, r)
    except Exception as e:
        record("get_future_detail", {"symbol": "RB2510.SHF"}, None, e)

    # 3) 期货日线行情（价格/持仓量——课题数据前提之二）
    # 注：文档中的 get_future_daily 在当前 SDK 版本中实际为 get_future_daily_post
    try:
        r = panda_data.get_future_daily_post(
            start_date="20250801", end_date="20250815", symbol="RB2510.SHF"
        )
        record("get_future_daily_post", {"symbol": "RB2510.SHF",
                                         "start_date": "20250801", "end_date": "20250815"}, r)
    except Exception as e:
        record("get_future_daily_post", {"symbol": "RB2510.SHF"}, None, e)

    # 4) 主力合约映射
    try:
        r = panda_data.get_future_dominant(
            underlying_symbol=["RB"], start_date="20250801", end_date="20250815"
        )
        record("get_future_dominant", {"underlying_symbol": ["RB"],
                                       "start_date": "20250801", "end_date": "20250815"}, r)
    except Exception as e:
        record("get_future_dominant", {"underlying_symbol": ["RB"]}, None, e)

    ok = sum(1 for c in log["calls"] if "error" not in c)
    log["summary"] = {"total": len(log["calls"]), "ok": ok}
    finish(0 if ok >= 2 else 1)


def finish(code):
    out = os.path.join(LOG_DIR, "20261115_verify_env.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n日志已保存: {out}")
    sys.exit(code)


if __name__ == "__main__":
    main()
