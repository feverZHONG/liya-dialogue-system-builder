#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_角色列表.py —— 台词系统 · 角色总览
======================================
扫描 台词角色库/，每个角色一行摘要：
    角色名 | 台词数 | 格子数 | 模板数 | 直覆盖% | 日志条数 | 规则

用法：
    python3 11_角色列表.py [--json]
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


def load_cfg(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cell_count(cfg):
    dims = cfg.get("dimensions", {})
    return len(list(itertools.product(*[dims[d] for d in dims]))) if dims else 0


def main():
    ap = argparse.ArgumentParser(description="台词系统：角色总览")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    args = ap.parse_args()

    if not os.path.isdir(ROLE_ROOT):
        print("❌ 台词角色库不存在: " + ROLE_ROOT)
        sys.exit(1)

    roles = []
    for name in sorted(os.listdir(ROLE_ROOT)):
        role = os.path.join(ROLE_ROOT, name)
        cfg_path = os.path.join(role, "台词配置.json")
        if not os.path.isdir(role) or not os.path.exists(cfg_path):
            continue
        cfg = load_cfg(cfg_path)
        line_lib = cfg.get("line_lib", {})
        templates = cfg.get("templates", [])
        n_lines = sum(len(v) for v in line_lib.values())
        n_cells = cell_count(cfg)
        has_rule = os.path.exists(os.path.join(role, "硬规则.json"))
        log_path = os.path.join(role, "日志", "运行日志.jsonl")
        n_logs = 0
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                n_logs = sum(1 for _ in f)
        roles.append({"角色": name, "台词数": n_lines, "格子数": n_cells,
                      "模板数": len(templates), "日志条数": n_logs, "硬规则": has_rule})

    if args.json:
        for r in roles:
            print(json.dumps(r, ensure_ascii=False))
        return

    if not roles:
        print("台词角色库为空。用 `dlg new <角色名>` 创建第一个角色。")
        return
    print(f"{'角色':<12}{'台词':>6}{'格子':>6}{'模板':>6}{'日志':>6}  硬规则")
    print("-" * 48)
    for r in roles:
        print(f"{r['角色']:<12}{r['台词数']:>6}{r['格子数']:>6}{r['模板数']:>6}"
              f"{r['日志条数']:>6}  {'✓' if r['硬规则'] else '—'}")
    print("-" * 48)
    print(f"共 {len(roles)} 个角色")


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
