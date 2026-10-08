#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
16_安装.py —— 台词系统 · 部署（dlg 薄壳安装/环境自检）
========================================================
在 <薄壳目录>（默认 ~/.local/bin）安装（或更新）薄壳 `dlg`，指向本台词系统目录的 dlg.py。
解压 zip 到新位置后跑一次 `dlg install`，命令即可用。

用法：
    python3 16_安装.py                          # 安装/更新薄壳（默认 ~/.local/bin）
    python3 16_安装.py --bin-dir DIR            # 指定薄壳目录（该目录须在 PATH 里）
    python3 16_安装.py --role-root DIR          # 角色库不在默认位置时写进薄壳（DLG_ROLE_ROOT）
    python3 16_安装.py --check                  # 只检查不写（同样支持 --bin-dir）

角色库默认取本目录上一级的 `台词角色库/`；把它放在别处（如私人库与发布包分离）时，
用 --role-root 指定，薄壳会带着 DLG_ROLE_ROOT 一起装好，之后 `dlg <角色名>` 照常展开。
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import os
import re
import shutil
import stat
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BIN_DIR = os.path.expanduser("~/.local/bin")
DEFAULT_ROLE_ROOT = os.path.join(os.path.dirname(BASE), "台词角色库")


def detect_bin_dir() -> str:
    """认得出自己装在哪：PATH 里已有 dlg 薄壳就用它所在目录，否则用默认目录。

    重装与自检都靠这条——不必每次手敲 --bin-dir（薄壳目录常在 PATH 里的自定义位置）。
    """
    p = shutil.which("dlg")
    return os.path.dirname(os.path.abspath(p)) if p else DEFAULT_BIN_DIR

SHELL_TMPL = """#!/bin/sh
# dlg 薄壳: 台词系统 CLI（由 16_安装.py 生成；路径失效时重跑 dlg install）
DLG="{dlg_py}"
{role_root_line}if [ ! -f "$DLG" ]; then
  echo "dlg: 台词系统脚本缺失——检查路径或重建后更新本薄壳" >&2
  exit 1
fi
exec python3 "$DLG" "$@"
"""


def shell_path(bin_dir: str) -> str:
    return os.path.join(bin_dir, "dlg")


def check(bin_dir: str) -> tuple:
    """返回 (薄壳存在?, 指向正确?, 在 PATH?, 说明列表, 薄壳内角色库根)"""
    issues = []
    dlg_py = os.path.join(BASE, "dlg.py")
    shell = shell_path(bin_dir)
    exists = os.path.exists(shell)
    correct = False
    role_root = ""
    if exists:
        try:
            with open(shell, "r", encoding="utf-8") as f:
                content = f.read()
            correct = dlg_py in content  # 路径字符串出现在薄壳内容即可（兼容变量/直写格式）
            m = re.search(r'DLG_ROLE_ROOT="([^"]+)"', content)
            if m:
                role_root = m.group(1)
        except OSError:
            correct = False
    in_path = False
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.realpath(d) == os.path.realpath(bin_dir):
            in_path = True
            break
    if not exists:
        issues.append(f"薄壳不存在: {shell}")
    elif not correct:
        issues.append(f"薄壳存在但指向不对: {shell}")
    if not in_path:
        issues.append(f"{bin_dir} 不在 PATH，需要 export PATH=\"$PATH:{bin_dir}\"")
    return exists, correct, in_path, issues, role_root


def main():
    ap = argparse.ArgumentParser(description="台词系统：部署")
    ap.add_argument("--check", action="store_true", help="只检查不写")
    ap.add_argument("--bin-dir", default=None,
                    help=f"薄壳安装目录（默认认 PATH 里已有的 dlg 所在目录；都没有则 {DEFAULT_BIN_DIR}）")
    ap.add_argument("--role-root", default="",
                    help="角色库根目录（默认取本目录上一级的 台词角色库/；指定后写进薄壳的 DLG_ROLE_ROOT）")
    args = ap.parse_args()
    bin_dir = os.path.abspath(os.path.expanduser(args.bin_dir or detect_bin_dir()))
    shell = shell_path(bin_dir)

    exists, correct, in_path, issues, sh_role_root = check(bin_dir)
    role_root = sh_role_root or (os.path.abspath(args.role_root) if args.role_root else DEFAULT_ROLE_ROOT)
    role_root_display = role_root + ("" if os.path.isdir(role_root) else "  ⚠️ 不存在")
    if args.check:
        print("=" * 52)
        print("台词系统 · 环境自检")
        print("=" * 52)
        print(f"  台词系统目录 : {BASE}")
        print(f"  角色库根目录 : {role_root_display}")
        print(f"  薄壳位置     : {shell}  {'✅' if exists else '❌ 未安装'}")
        if exists:
            print(f"  指向正确     : {'✅' if correct else '❌ 指向不对（重跑 dlg install）'}")
        print(f"  PATH 包含    : {'✅' if in_path else '❌ 未加入 PATH'}")
        if issues:
            print("-" * 52)
            for it in issues:
                print(f"  ⚠️ {it}")
        else:
            print("-" * 52)
            print("  环境就绪：直接敲 dlg 使用。")
        return 0 if not issues else 1

    os.makedirs(bin_dir, exist_ok=True)
    # 薄壳里的角色库根：显式 --role-root 优先，其次沿用旧薄壳里已有的（重装不丢配置），都没有就留空（走默认）
    role_root_line = ""
    if sh_role_root or args.role_root:
        role_root_line = f'DLG_ROLE_ROOT="{role_root}"; export DLG_ROLE_ROOT\n'
    with open(shell, "w", encoding="utf-8") as f:
        f.write(SHELL_TMPL.format(dlg_py=os.path.join(BASE, "dlg.py"),
                                  role_root_line=role_root_line))
    os.chmod(shell, os.stat(shell).st_mode | stat.S_IEXEC)
    print(f"✅ 薄壳已安装: {shell}")
    if role_root_line:
        print(f"   角色库根: {role_root_display}")
    if not in_path:
        print(f"⚠️  {bin_dir} 不在 PATH，执行: export PATH=\"$PATH:{bin_dir}\"")
    print(f"   验证: dlg help")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
