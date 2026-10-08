#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_查重.py —— 台词系统 · 台词重复检测
========================================
检测台词配置里的重复：同一格内重复（废稿）与跨格重复（偷懒/污染）。

用法：
    python3 03_查重.py 配置.json
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import json
import sys
from collections import defaultdict


def ensure_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("用法: python3 03_查重.py 配置.json")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    line_lib = cfg.get("line_lib", {})
    # 同格重复
    intra = []
    for key, lines in line_lib.items():
        seen = defaultdict(list)
        for i, line in enumerate(lines):
            seen[line].append(i)
        for line, idxs in seen.items():
            if len(idxs) > 1:
                intra.append((key, line, idxs))
    # 跨格重复（同一句出现在多个格子）
    global_map = defaultdict(list)
    for key, lines in line_lib.items():
        for line in lines:
            global_map[line].append(key)

    print("=== 同格内重复（同一格子里一模一样的台词）===")
    if intra:
        for key, line, idxs in intra:
            print(f"  ❌ {key}: 第 {idxs} 位重复 —— {line}")
    else:
        print("  无 ✓")
    print("\n=== 跨格重复（同一句出现在多个格子）===")
    cross = [(line, keys) for line, keys in global_map.items() if len(keys) > 1]
    if cross:
        for line, keys in cross:
            print(f"  ❌ 重复 {len(keys)} 格: {keys} —— {line}")
    else:
        print("  无 ✓")
    print("\n" + ("✅ 无重复，台词干净" if not intra and not cross else f"❌ 共 {len(intra)+len(cross)} 处重复，建议清理"))
    if cross:
        print("   提示：跨格重复通常是偷懒；同一句表达不同场景，应改写而非复用。")


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
