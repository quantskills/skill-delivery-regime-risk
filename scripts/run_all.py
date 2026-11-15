# -*- coding: utf-8 -*-
"""
一键复现入口：按依赖顺序执行全部 5 个步骤
用法：python scripts/run_all.py          （完整流程）
      python scripts/run_all.py --fast   （跳过环境验证与拉数，只重跑分析 3~5 步）
- 任一步骤失败（非零退出）立即中止并报告
- 步骤幂等：pull_data 已有 data/ 数据自动跳过，可断点续传后重跑
- 在 skill 根目录或本 scripts/ 目录下运行均可（路径按脚本自身位置定位）
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))  # scripts/ 目录

# (脚本, 说明, 是否属于 --fast 可跳过的前置步骤)
STEPS = [
    ("verify_env.py",     "① 平台连通性验证", True),
    ("pull_data.py",      "② 数据拉取（合约生命周期+日线）", True),
    ("build_calendar.py", "③ 生成事件日历（T-1/T0）", False),
    ("run_experiment.py", "④ 对照实验（提前减仓 vs 冻结基线）", False),
    ("analyze_cases.py",  "⑤ 误报/漏报案例分析", False),
]


def main():
    fast = "--fast" in sys.argv  # 快速模式：数据已就位，只重跑分析
    t0 = time.time()
    print(f"全流程开始（{'快速模式' if fast else '完整模式'}）\n" + "=" * 60)
    for script, desc, skippable in STEPS:
        if fast and skippable:
            print(f"[跳过] {desc}")
            continue
        print(f"\n>>> {desc}: {script}")
        # 用当前解释器逐个调用兄弟脚本，继承环境变量（凭证）
        r = subprocess.run([sys.executable, os.path.join(HERE, script)],
                           cwd=os.path.dirname(HERE))
        if r.returncode != 0:
            print(f"\n[失败] {desc} 退出码 {r.returncode}，流程中止。"
                  f"修复后可重跑（已完成的步骤会自动跳过）。")
            sys.exit(r.returncode)
    mins = (time.time() - t0) / 60
    print("\n" + "=" * 60)
    print(f"全部完成，耗时 {mins:.1f} 分钟。结果查看：")
    print("  报告       reports/Q5_report.md")
    print("  规则卡     reports/rule_card.md")
    print("  案例       reports/cases.md")
    print("  规则取证   references/rules_evidence.md")
    print("  平台留痕   platform_logs/")
    print("  实验数据   data/experiment_result.csv")


if __name__ == "__main__":
    main()
