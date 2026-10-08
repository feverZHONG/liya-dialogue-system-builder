#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_空库盘点.py —— 台词系统 · 台词分布诊断
============================================
统计每格变体数，标出稀缺格（只有 1 条）和空档（没写的格子），给出补写建议。
对应「空库先盘点再定变体数」：素材不足时先看分布再写。

用法：
    python3 05_空库盘点.py 配置.json
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import json
import sys
from itertools import product


def ensure_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("用法: python3 05_空库盘点.py 配置.json")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    dims = cfg["dimensions"]
    line_lib = {}
    for key_str, lines in cfg.get("line_lib", {}).items():
        line_lib[tuple(k.strip() for k in key_str.split("|"))] = lines

    all_combos = list(product(*dims.values()))
    var_combos = len(list(product(*cfg.get("variables", {}).values()))) if cfg.get("variables") else 1

    n_lines = sum(len(v) for v in line_lib.values())
    print(f"维度: {list(dims.keys())}  格子总数: {len(all_combos)}  变量组合: {var_combos}")
    print(f"已写格子: {len(line_lib)} / {len(all_combos)}   台词总条数: {n_lines}")
    print("-" * 60)

    scarce = []
    for key, lines in sorted(line_lib.items()):
        mark = "  ← 稀缺(仅1条)" if len(lines) == 1 else ""
        if len(lines) == 1:
            scarce.append(key)
        print(f"  {key}: {len(lines)} 条{mark}")

    missing = [c for c in all_combos if tuple(c) not in line_lib]
    print("-" * 60)
    if missing:
        print(f"❌ {len(missing)} 个格子没写台词，例如: {[m for m in missing[:5]]}")
        print("   建议：优先补高频格子；或靠模板兜底（02 校验 + 07 验证确认兜底覆盖率 100%）")
    else:
        print("✅ 所有格子都已写台词")
    if scarce:
        print(f"⚠ {len(scarce)} 个格子只有 1 条变体: {scarce[:10]}")
        print("   高频场景建议补到 2~3 条，避免快速重复")
    print(f"\n汇总：{len(line_lib)} 格已写，{len(missing)} 格空缺，{len(scarce)} 格稀缺")


if __name__ == "__main__":
    ensure_utf8()
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        try:
            if sys.stdin.isatty():  # 仅交互终端才等待；管道/脚本调用直接退出
                input("\n按回车键退出...")
        except EOFError:
            pass
