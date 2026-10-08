#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
09_日志分析.py —— 台词系统 · 运行日志分析（反馈层）
======================================================
消费 08_运行演示.py 产出的 JSONL 日志，输出：
  - 兜底占比：模板兜底比例高 → 格子有洞
  - 高频格子：TOP 触发组合
  - 迭代建议：优先补哪些格子、模板是否过度兜底

用法：
    python3 09_日志分析.py 运行日志.jsonl
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import json
import sys
from collections import Counter


def ensure_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("用法: python3 09_日志分析.py 运行日志.jsonl")
        sys.exit(1)
    path = sys.argv[1]
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not records:
        print("日志为空或格式不正确")
        sys.exit(1)

    total = len(records)
    modes = Counter(r.get("mode", "?") for r in records)
    grid_hits = modes.get("格子命中", 0)
    fallback = modes.get("模板兜底", 0)
    fallback_rate = fallback / total if total else 0.0

    print("=" * 60)
    print("运行日志分析")
    print("=" * 60)
    print(f"  日志条目   : {total}")
    print(f"  格子命中   : {grid_hits}  ({grid_hits/total*100:.1f}%)")
    print(f"  模板兜底   : {fallback}  ({fallback_rate*100:.1f}%)")
    print("-" * 60)

    ctx_counter = Counter()
    for r in records:
        ctx = r.get("context", {})
        ctx_counter[tuple(sorted(ctx.items()))] += 1

    print(f"  高频触发 TOP5：")
    for ctx_tuple, n in ctx_counter.most_common(5):
        ctx = dict(ctx_tuple)
        mode = next((r["mode"] for r in records if dict(sorted(r.get("context", {}).items())) == ctx), "?")
        print(f"    {ctx} × {n}  [{mode}]")

    print("-" * 60)
    print("迭代建议：")
    if fallback_rate > 0.2:
        print(f"  ⚠ 模板兜底占比 {fallback_rate*100:.0f}% > 20%：格子有洞，优先补兜底高的格子（见高频 TOP）。")
    elif fallback_rate > 0:
        print(f"  ✓ 模板兜底占比 {fallback_rate*100:.0f}%：健康，兜底只做保险丝。")
    else:
        print("  ✓ 无模板兜底：格子全覆盖。")
    if grid_hits > 0 and fallback == 0:
        print("  ✓ 所有触发都命中格子，无需补写。")
    print("  下一步：按高频格子补变体（2~3 条），改配置后重跑 06 → 07 → 08。")


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
