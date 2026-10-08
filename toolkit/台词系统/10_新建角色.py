#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10_新建角色.py —— 台词系统 · 角色脚手架
========================================
在 台词角色库/ 下创建一个角色的标准文件夹：
    台词角色库/<角色名>/
        ├── 台词配置.json    # 模板配置（空格子 + 通用模板，可直接跑）
        ├── 硬规则.json      # 空规则模板
        ├── 素材/            # 台词原句素材
        └── 日志/            # 运行日志

用法：
    python3 10_新建角色.py <角色名> [--quiet]
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

NAME_RE = re.compile(r"^[\w\u4e00-\u9fff-]+$")  # 中英文/数字/下划线/连字符

CFG_TEMPLATE = {
    "dimensions": {"场景": ["问候", "工作"], "情绪": ["平静", "烦躁"]},
    "line_lib": {},
    "templates": ["{对象}，我在。", "嗯，说，我听着。"],
    "variables": {"对象": ["你"]},
}

RULE_TEMPLATE = {"禁用词": [], "长度上限": 40, "必须包含": []}


def main():
    ap = argparse.ArgumentParser(description="台词系统：新建角色")
    ap.add_argument("name", help="角色名（中英文/数字/下划线/连字符）")
    ap.add_argument("--quiet", action="store_true", help="静默（供脚本调用）")
    args = ap.parse_args()

    name = args.name.strip()
    if not NAME_RE.match(name) or name in (".", ".."):
        print(f"❌ 角色名不合法: {name!r}（仅允许中英文/数字/下划线/连字符）")
        sys.exit(1)

    role = os.path.join(ROLE_ROOT, name)
    if os.path.exists(role):
        print(f"❌ 角色已存在: {role}")
        sys.exit(1)

    os.makedirs(role)
    os.makedirs(os.path.join(role, "素材"))
    os.makedirs(os.path.join(role, "日志"))

    cfg_path = os.path.join(role, "台词配置.json")
    rule_path = os.path.join(role, "硬规则.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(CFG_TEMPLATE, f, ensure_ascii=False, indent=2)
    with open(rule_path, "w", encoding="utf-8") as f:
        json.dump(RULE_TEMPLATE, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print(f"✅ 角色已创建: {role}")
        print(f"   台词配置: {cfg_path}（空格子 + 2 条通用模板，可直接 dlg gen）")
        print(f"   硬规则  : {rule_path}")
        print(f"   下一步  : 填台词 → dlg check {name} → dlg gen {name} → dlg cover {name}")


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
