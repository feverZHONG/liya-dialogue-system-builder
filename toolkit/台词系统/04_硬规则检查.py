#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_硬规则检查.py —— 台词系统 · 硬规则校验
============================================
按规则文件检查台词：禁用词、长度上限、必须包含词。
硬规则（口癖/句式/禁用词）是生成后的校验项，不是触发维度。

用法：
    python3 04_硬规则检查.py 配置.json 规则.json

规则文件格式：
    {
      "禁用词": ["大发慈悲", "勉为其难"],
      "长度上限": 40,
      "必须包含": ["我"]
    }
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


def main():
    if len(sys.argv) < 3:
        print("用法: python3 04_硬规则检查.py 配置.json 规则.json")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        rules = json.load(f)

    all_lines = [l for v in cfg.get("line_lib", {}).values() for l in v] + cfg.get("templates", [])
    banned = rules.get("禁用词", [])
    max_len = rules.get("长度上限")
    must_have = rules.get("必须包含", [])

    violations = []
    for line in all_lines:
        for w in banned:
            if w in line:
                violations.append((line, f"含禁用词「{w}」"))
        if max_len and len(line) > max_len:
            violations.append((line, f"长度 {len(line)} 超过上限 {max_len}"))
    for line in all_lines:
        for w in must_have:
            if w not in line:
                violations.append((line, f"缺少必须包含词「{w}」"))
                break  # 每条只报第一个缺口

    print(f"检查 {len(all_lines)} 条台词，规则：禁用词 {banned or '无'} / "
          f"长度上限 {max_len or '无'} / 必须包含 {must_have or '无'}")
    print("=" * 60)
    if not violations:
        print("✅ 全部台词通过硬规则")
    else:
        print(f"❌ {len(violations)} 处违规：")
        for line, reason in violations:
            print(f"   - [{reason}] {line}")
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
