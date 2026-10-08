#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_校验配置.py —— 台词系统 · 配置入口把关
============================================
校验台词配置 JSON 的 schema：维度非空、line_lib 键格式、模板/变量类型。

用法：
    python3 02_校验配置.py 配置.json
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import json
import sys


def ensure_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def validate(path: str) -> list:
    """返回错误列表，空 = 通过"""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"无法读取/解析配置: {e}"]

    if not isinstance(cfg, dict):
        return ["配置根节点必须是 JSON 对象"]

    dims = cfg.get("dimensions")
    if not isinstance(dims, dict) or not dims:
        errors.append("dimensions 必须是非空对象")
    else:
        for name, values in dims.items():
            if not isinstance(values, list) or not values:
                errors.append(f"维度 {name!r} 的取值必须是非空列表")
            elif not all(isinstance(v, str) and v for v in values):
                errors.append(f"维度 {name!r} 的取值必须是非空字符串")

    line_lib = cfg.get("line_lib", {})
    if not isinstance(line_lib, dict):
        errors.append("line_lib 必须是对象")
    elif dims:
        n = len(dims)
        for key_str, lines in line_lib.items():
            if not isinstance(key_str, str):
                errors.append(f"line_lib 键必须是字符串: {key_str!r}")
                continue
            parts = [p.strip() for p in key_str.split("|")]
            if len(parts) != n:
                errors.append(f"line_lib 键 {key_str!r} 维度数应为 {n}（按 dimensions 顺序用 | 连接）")
            if not isinstance(lines, list) or not lines:
                errors.append(f"line_lib 键 {key_str!r} 的台词必须是非空列表")

    for field, kind in [("templates", list), ("variables", dict)]:
        if field in cfg and not isinstance(cfg[field], kind):
            errors.append(f"{field} 必须是 {kind.__name__}")
    if isinstance(cfg.get("variables"), dict):
        for name, values in cfg["variables"].items():
            if not isinstance(values, list) or not values:
                errors.append(f"variables.{name} 必须是非空列表")
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python3 02_校验配置.py 配置.json")
        sys.exit(1)
    errors = validate(sys.argv[1])
    if not errors:
        print("✅ 配置通过校验")
    else:
        print(f"❌ 发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)


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
