#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_画格子.py —— 台词系统 · 触发组合预览
==========================================
把维度定义展开成完整格子清单（笛卡尔积），画格子前先看全貌。

用法：
    python3 01_画格子.py "场景:问候,工作,熬夜;情绪:平静,开心"

输出：全部触发格子 + 总数。
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import itertools
import sys


def ensure_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def parse_dim_spec(text: str) -> dict:
    """解析 '场景:问候,工作;情绪:平静' 为 {维度: [取值...]}"""
    dims = {}
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"段缺少冒号分隔，应为 维度:取值1,取值2 格式：{part!r}")
        name, values = part.split(":", 1)
        name, values = name.strip(), [v.strip() for v in values.split(",") if v.strip()]
        if not name or not values:
            raise ValueError(f"段为空或取值为空：{part!r}")
        dims[name] = values
    if not dims:
        raise ValueError("未解析到任何维度")
    return dims


def main():
    if len(sys.argv) < 2:
        print("用法: python3 01_画格子.py \"场景:问候,工作;情绪:平静,开心\"")
        sys.exit(1)
    dims = parse_dim_spec(sys.argv[1])
    keys = list(dims.keys())
    combos = list(itertools.product(*[dims[k] for k in keys]))

    print(f"触发空间：{len(combos)} 格 = " + " × ".join(f"{len(dims[k])}种{k}" for k in keys))
    print("-" * 50)
    for i, combo in enumerate(combos, 1):
        cells = " | ".join(f"{k}:{v}" for k, v in zip(keys, combo))
        print(f"  {i:>3}. {cells}")
    print("-" * 50)
    print(f"共 {len(combos)} 格。格子超过 40 建议减少维度或降级为模板变量。")


if __name__ == "__main__":
    ensure_utf8()
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        try:
            if sys.stdin.isatty():  # 仅交互终端才等待；管道/脚本调用直接退出
                input("\n按回车键退出...")
        except EOFError:
            pass
