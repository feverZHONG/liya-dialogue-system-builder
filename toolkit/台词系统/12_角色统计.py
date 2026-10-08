#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_角色统计.py —— 台词系统 · 跨角色统计
========================================
汇总整个 台词角色库/：角色数、台词总量、格子总和、日志总量、
空库警告（line_lib 为空的角色）、覆盖率健康（日志有兜底的）。

用法：
    python3 12_角色统计.py [--json]
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import itertools
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")


def main():
    ap = argparse.ArgumentParser(description="台词系统：跨角色统计")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    args = ap.parse_args()

    if not os.path.isdir(ROLE_ROOT):
        print("❌ 台词角色库不存在: " + ROLE_ROOT)
        sys.exit(1)

    stats = {"角色数": 0, "台词总数": 0, "模板总数": 0, "格子总和": 0,
             "日志总条数": 0, "空库角色": [], "无规则角色": [], "兜底依赖角色": []}

    for name in sorted(os.listdir(ROLE_ROOT)):
        role = os.path.join(ROLE_ROOT, name)
        cfg_path = os.path.join(role, "台词配置.json")
        if not os.path.isdir(role) or not os.path.exists(cfg_path):
            continue
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        stats["角色数"] += 1
        line_lib = cfg.get("line_lib", {})
        templates = cfg.get("templates", [])
        stats["台词总数"] += sum(len(v) for v in line_lib.values())
        stats["模板总数"] += len(templates)
        dims = cfg.get("dimensions", {})
        if dims:
            stats["格子总和"] += len(list(itertools.product(*[dims[d] for d in dims])))
        if not line_lib:
            stats["空库角色"].append(name)
        if not os.path.exists(os.path.join(role, "硬规则.json")):
            stats["无规则角色"].append(name)
        log_path = os.path.join(role, "日志", "运行日志.jsonl")
        if os.path.exists(log_path):
            modes = {"格子命中": 0, "模板兜底": 0}
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    stats["日志总条数"] += 1
                    m = rec.get("mode")
                    if m in modes:
                        modes[m] += 1
            if modes["模板兜底"] > 0 and modes["格子命中"] > 0:
                rate = modes["模板兜底"] / (modes["格子命中"] + modes["模板兜底"])
                if rate > 0.2:
                    stats["兜底依赖角色"].append(f"{name}({rate:.0%})")

    if args.json:
        print(json.dumps(stats, ensure_ascii=False))
        return

    print("=" * 56)
    print("台词角色库 · 跨角色统计")
    print("=" * 56)
    print(f"  角色数     : {stats['角色数']}")
    print(f"  台词总数   : {stats['台词总数']} 条（格子台词）")
    print(f"  模板总数   : {stats['模板总数']} 条（兜底用）")
    print(f"  格子总和   : {stats['格子总和']} 种触发组合")
    print(f"  日志总条数 : {stats['日志总条数']} 条")
    print("-" * 56)
    if stats["角色数"] == 0:
        print("  空库：用 `dlg new <角色名>` 创建第一个角色。")
    if stats["空库角色"]:
        print(f"  ⚠️ 空库角色（无格子台词，全靠模板）: {', '.join(stats['空库角色'])}")
    if stats["无规则角色"]:
        print(f"  ⚠️ 无硬规则角色: {', '.join(stats['无规则角色'])}")
    if stats["兜底依赖角色"]:
        print(f"  ⚠️ 兜底占比 >20%（建议补格子）: {', '.join(stats['兜底依赖角色'])}")
    if not stats["空库角色"] and not stats["无规则角色"] and not stats["兜底依赖角色"]:
        print("  健康：无空库、无缺规则、无兜底依赖。")


if __name__ == "__main__":
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
