#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
13_全量体检.py —— 台词系统 · 一键体检
======================================
对指定角色（缺省=全部）跑全部质量闸 + 覆盖率，汇总一份报告：
    校验 → 查重 → 硬规则 → 空库 → 覆盖率（直覆盖/兜底后）
复用 02/03/04/05/07 的判定逻辑（subprocess 调用，标准输出解析）。

用法：
    python3 13_全量体检.py                 # 全部角色
    python3 13_全量体检.py 小雨 新角色      # 指定角色
    python3 13_全量体检.py --json
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

CHECKS = [  # (名称, 脚本, 通过标记, 额外抓取)
    ("校验",   "02_校验配置.py",   "✅"),
    ("查重",   "03_查重.py",       "✅"),
    ("硬规则", "04_硬规则检查.py", "✅"),
    ("空库",   "05_空库盘点.py",   "✅"),
    ("覆盖率", "07_验证覆盖率.py", "✓"),
]


def run_check(script: str, role_dir: str):
    cfg = os.path.join(role_dir, "台词配置.json")
    rule = os.path.join(role_dir, "硬规则.json")
    cmd = [sys.executable, os.path.join(BASE, script), cfg]
    if script == "04_硬规则检查.py" and os.path.exists(rule):
        cmd.append(rule)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace",
                             stdin=subprocess.DEVNULL, timeout=120)
        text = out.stdout + out.stderr
    except Exception as e:
        return {"项": script[:4], "通过": False, "说明": f"执行失败: {e}"}
    return {"项": script[:4], "通过": ("❌" not in text and "失败" not in text), "说明": "见专项报告"}


def main():
    ap = argparse.ArgumentParser(description="台词系统：一键体检")
    ap.add_argument("roles", nargs="*", help="角色名（缺省=全部）")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    args = ap.parse_args()

    if not os.path.isdir(ROLE_ROOT):
        print("❌ 台词角色库不存在: " + ROLE_ROOT)
        sys.exit(1)

    roles = args.roles or sorted(os.listdir(ROLE_ROOT))
    reports = []
    for name in roles:
        role = os.path.join(ROLE_ROOT, name)
        cfg_path = os.path.join(role, "台词配置.json")
        if not os.path.isdir(role) or not os.path.exists(cfg_path):
            reports.append({"角色": name, "状态": "❌ 不是有效角色", "各项": []})
            continue
        items = [run_check(s, role) for s, _, _ in CHECKS]
        # 覆盖率数字（兜底后）
        cover_out = subprocess.run(
            [sys.executable, os.path.join(BASE, "07_验证覆盖率.py"), cfg_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, timeout=120).stdout
        m = re.search(r"模板兜底后\s*:\s*([\d.]+)%", cover_out)
        cover_pct = m.group(1) if m else "?"
        n_lines = 0
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        n_lines = sum(len(v) for v in cfg.get("line_lib", {}).values())
        ok = sum(1 for it in items if it["通过"])
        reports.append({"角色": name, "状态": f"{ok}/5 项通过",
                        "台词": n_lines, "兜底后覆盖": f"{cover_pct}%",
                        "各项": items})

    if args.json:
        print(json.dumps(reports, ensure_ascii=False))
        return

    print("=" * 64)
    print("台词系统 · 一键体检")
    print("=" * 64)
    for r in reports:
        if "各项" not in r or not r["各项"]:
            print(f"  ❌ {r['角色']}: {r['状态']}")
            continue
        tags = "  ".join(f"{it['项']}:{'✓' if it['通过'] else '✗'}" for it in r["各项"])
        print(f"  {r['角色']:<10} {r['状态']:<12} 台词 {r['台词']:<4} 兜底后 {r['兜底后覆盖']:<7}")
        print(f"             {tags}")
    print("=" * 64)
    total_roles = sum(1 for r in reports if r.get("各项"))
    total_ok = sum(1 for r in reports if r.get("状态", "").startswith("5/5"))
    print(f"  汇总：{total_ok}/{total_roles} 个角色全项通过；" +
          ("继续跑 dlg log <角色> 看迭代建议。" if total_ok else "未通过项见上方 ✗，先修再跑。"))


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
