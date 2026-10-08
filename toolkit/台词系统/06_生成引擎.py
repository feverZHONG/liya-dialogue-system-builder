#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_生成引擎.py —— 台词系统 · 配置 → 引擎
==========================================
从配置 JSON 生成零依赖引擎。
引擎规则：格子命中 → 变体轮换；未命中 → 模板兜底 + 变量注入。

用法：
    python3 06_生成引擎.py 配置.json -o 引擎.py
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg.get("dimensions"), dict) or not cfg["dimensions"]:
        raise ValueError("配置缺少非空的 dimensions 字段")
    return cfg


def gen_engine_code(cfg: dict) -> str:
    dim_order = list(cfg["dimensions"].keys())
    line_lib = {}
    for key_str, lines in cfg.get("line_lib", {}).items():
        key = tuple(k.strip() for k in key_str.split("|"))
        if len(key) != len(dim_order):
            raise ValueError(f"line_lib 键 {key_str!r} 维度数不符（应为 {len(dim_order)}）")
        line_lib[key] = list(lines)
    templates = cfg.get("templates", [])
    variables = cfg.get("variables", {})

    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 06_生成引擎.py 生成。改台词请改配置后重新生成，勿手改本文件。"""

import random

_DIM_ORDER = {repr(dim_order)}
_LINE_LIB = {repr(line_lib)}
_TEMPLATES = {repr(templates)}
_VARS = {repr(variables)}
_seen = {{}}  # 变体轮换计数


def reply(context: dict) -> str:
    """根据触发上下文返回一句台词。context: {{维度名: 值, ...}}"""
    key = tuple(context.get(d, "") for d in _DIM_ORDER)
    lines = _LINE_LIB.get(key)
    if lines:
        counts = [_seen.get((id(lines), i), 0) for i in range(len(lines))]
        idx = counts.index(min(counts))
        _seen[(id(lines), idx)] = _seen.get((id(lines), idx), 0) + 1
        return lines[idx]
    if _TEMPLATES:
        filled = {{}}
        for var, values in _VARS.items():
            filled[var] = context.get(var) if context.get(var) else random.choice(values)
        try:
            return random.choice(_TEMPLATES).format(**filled)
        except (KeyError, IndexError):
            return random.choice(_TEMPLATES)
    return "[无台词] 格子未覆盖且无模板，请补配置。"


if __name__ == "__main__":
    print("=== 格子命中演示 ===")
    for key in list(_LINE_LIB)[:3]:
        ctx = dict(zip(_DIM_ORDER, key))
        for v in _VARS:
            ctx[v] = list(_VARS[v])[0]
        print(f"  {{ctx}} -> {{reply(ctx)}}")
    if _TEMPLATES:
        print("=== 模板兜底演示 ===")
        ctx = {{d: "未命中" for d in _DIM_ORDER}}
        for v in _VARS:
            ctx[v] = list(_VARS[v])[0]
        print(f"  {{ctx}} -> {{reply(ctx)}}")
'''


def main():
    ap = argparse.ArgumentParser(description="台词系统：配置 → 引擎")
    ap.add_argument("config")
    ap.add_argument("-o", "--output", default="引擎.py")
    args = ap.parse_args()

    cfg = load_config(args.config)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(gen_engine_code(cfg))
    print(f"✅ 引擎已生成: {os.path.abspath(args.output)}")
    print(f"   维度: {list(cfg['dimensions'].keys())}  格子: {len(cfg.get('line_lib', {}))}  模板: {len(cfg.get('templates', []))}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
