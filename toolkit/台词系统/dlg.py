#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dlg —— 台词系统 CLI 总入口
============================
注册表驱动：dlg <子命令> [参数...]，每个子命令对应系统的一个小脚本。

角色模式（一个角色一个文件夹）：
    台词角色库/<角色名>/
        ├── 台词配置.json     # 画格子/生成/验证的输入
        ├── 硬规则.json       # 可选：角色硬规则（dlg rule 默认用）
        ├── 引擎.py           # dlg gen 默认输出
        ├── 素材/             # 台词原句素材
        └── 日志/             # dlg run 默认写日志，dlg log 默认读

用法（角色名可替代路径，自动展开）：
    dlg help
    dlg grid "场景:问候,工作;情绪:平静"          # 画格子预览（纯维度，无需角色）
    dlg check 小雨                              # = dlg check 台词角色库/小雨/台词配置.json
    dlg gen 小雨                               # 生成引擎到 台词角色库/小雨/引擎.py
    dlg run 小雨 --batch 10                     # 运行 + 日志到 台词角色库/小雨/日志/
    dlg log 小雨                               # 分析 台词角色库/小雨/日志/运行日志.jsonl
"""

import os
import signal
import subprocess
import sys

signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # 管道被提前关闭时安静退出，不抛 BrokenPipeError

__version__ = "1.3.0"

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)          # 主目录（台词系统/ 的上一级）
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

COMMANDS = {
    "grid":  ("01_画格子.py",     "画格子预览: dlg grid \"场景:问候,工作;情绪:平静\""),
    "check": ("02_校验配置.py",   "配置把关:   dlg check 小雨 / 配置.json"),
    "dup":   ("03_查重.py",       "台词查重:   dlg dup 小雨 / 配置.json"),
    "rule":  ("04_硬规则检查.py", "硬规则检查: dlg rule 小雨 [规则.json]"),
    "stock": ("05_空库盘点.py",   "空库盘点:   dlg stock 小雨 / 配置.json"),
    "gen":   ("06_生成引擎.py",   "生成引擎:   dlg gen 小雨 [-o 引擎.py]"),
    "cover": ("07_验证覆盖率.py", "覆盖率验证: dlg cover 小雨 / 配置.json"),
    "run":   ("08_运行演示.py",   "运行接入:   dlg run 小雨 --batch 10 / --interactive / --input 文件 / --stdin"),
    "log":   ("09_日志分析.py",   "日志分析:   dlg log 小雨 / 运行日志.jsonl"),
    "new":   ("10_新建角色.py",   "新建角色:   dlg new <角色名>（脚手架+模板配置）"),
    "list":  ("11_角色列表.py",   "角色总览:   dlg list"),
    "stats": ("12_角色统计.py",   "跨角色统计: dlg stats"),
    "audit": ("13_全量体检.py",   "一键体检:   dlg audit [角色名...]（缺省=全部）"),
    "seed":  ("14_素材提炼.py",   "素材提炼:   dlg seed 小雨 [--apply]"),
    "selftest": ("15_自检.py",    "回归自检:   dlg selftest"),
    "install": ("16_安装.py",    "安装部署:   dlg install [--check]"),
    "rhythm":  ("17_句式节奏.py", "句式节奏:   dlg rhythm 小雨 [--top 5]（句数分布/行首/签名/序列维）"),
    "fill":    ("18_补台词建议.py", "补台词建议: dlg fill 小雨 [--apply]（日志 → 三张清单）"),
    "export":  ("19_卡导出.py",  "卡导出:    dlg export 小雨 [--out 卡.json]（台词库 → 酒馆角色卡 V2）"),
}


def role_dir(name: str):
    """如果 name 是 台词角色库/ 下已有角色，返回其目录；否则 None"""
    d = os.path.join(ROLE_ROOT, name)
    return d if os.path.isdir(d) else None


def expand(cmd: str, args: list) -> list:
    """把角色名参数展开为实际路径，返回处理后的参数列表"""
    if not args:
        return args
    if cmd in ("new", "list", "stats", "audit", "seed", "fill", "export"):
        return args  # 吃角色名/无参数，保持透传，不展开路径
    role = role_dir(args[0])
    if role is None:
        return args  # 不是角色名，原样（可能是显式路径）

    cfg = os.path.join(role, "台词配置.json")
    engine = os.path.join(role, "引擎.py")
    rule = os.path.join(role, "硬规则.json")
    log = os.path.join(role, "日志", "运行日志.jsonl")

    if cmd in ("check", "dup", "stock", "cover", "rhythm"):
        return [cfg] + args[1:]
    if cmd == "rule":
        rest = args[1:]
        if not rest and os.path.exists(rule):
            rest = [rule]
        return [cfg] + rest
    if cmd == "gen":
        rest = args[1:]
        if "-o" not in rest and "--output" not in rest:
            rest += ["-o", engine]
        return [cfg] + rest
    if cmd == "run":
        rest = args[1:]
        if "--log" not in rest:
            rest += ["--log", log]
        return [engine] + rest
    if cmd == "log":
        return [log] + args[1:]
    return args


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("help", "-h", "--help", "version"):
        print(f"台词系统 CLI (dlg) v{__version__} —— 每个子命令对应一个小脚本；角色名自动展开路径：")
        print("-" * 60)
        for name, (_, desc) in COMMANDS.items():
            print(f"  {name:<6} {desc}")
        print("-" * 60)
        print(f"角色库: {ROLE_ROOT}/<角色名>/（一个角色一个文件夹）")
        print("流水线: dlg grid 预览 → 写配置 → dlg check → dlg dup/rule/stock")
        print("        → dlg gen → dlg cover → dlg run → dlg log → dlg fill（日志 → 补哪一格）")
        return
    cmd, rest = args[0], args[1:]
    if cmd not in COMMANDS:
        print(f"未知子命令: {cmd}（dlg help 查看全部）")
        sys.exit(2)
    script, _ = COMMANDS[cmd]
    rest = expand(cmd, rest)
    script_path = os.path.join(BASE, script)
    use_stdin = (cmd == "run" and ("--interactive" in rest or "--stdin" in rest))
    proc = subprocess.run([sys.executable, script_path] + rest,
                          stdin=None if use_stdin else subprocess.DEVNULL)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
