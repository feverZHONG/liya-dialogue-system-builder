#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_生成引擎.py —— 台词系统 · 配置 → 引擎
==========================================
从配置 JSON 生成零依赖引擎。

引擎规则：
    格子命中 → 状态层选句（均衡 + 冷却窗 + 随机）
    未命中   → 模板兜底 + 变量注入

状态层（2026-10-09 加）：
    ① **冷却窗**：最近用过的几句短期不再优先选——同句短时不重复，且同格的出场顺序
       不再是 A→B→C 的死循环（先取用得最少的那批，再避开最近用过的，最后随机）
    ② **上下文沿用**：context 没给的维度沿用上一次的值——调用方只说「场景＝熬夜」，
       引擎记得上次是烦躁的，状态有惯性；从未给过的值仍落兜底（不凭空造状态）

接口承诺：`reply(context: dict) -> str` 签名与语义不变，行为只增强；仍永不抛异常、零依赖。
另给 `reset()`：要清空状态（新会话／新场景）时调它。

用法：
    python3 06_生成引擎.py 配置.json -o 引擎.py
    python3 06_生成引擎.py --selftest          # 状态层口径自检
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import importlib.util
import json
import os
import tempfile

DEFAULT_COOLDOWN = 2


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
    cooldown = cfg.get("state", {}).get("cooldown", DEFAULT_COOLDOWN)
    try:
        cooldown = max(0, int(cooldown))
    except (TypeError, ValueError):
        cooldown = DEFAULT_COOLDOWN

    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 06_生成引擎.py 生成。改台词请改配置后重新生成，勿手改本文件。

状态层：冷却窗（同句短时不重复）＋ 上下文沿用（没给的维度记得上次的值）。改行为请改配置重生成。
"""

import random

_DIM_ORDER = {repr(dim_order)}
_LINE_LIB = {repr(line_lib)}
_TEMPLATES = {repr(templates)}
_VARS = {repr(variables)}
_COOLDOWN = {cooldown}

_seen = {{}}       # 变体使用计数：保证长期均衡
_recent = []       # 最近用过的台词：冷却窗（跨格生效）
_last_ctx = {{}}    # 上一次的上下文：没给的维度沿用


def reset():
    """清空状态（新会话／新场景开始时调）。"""
    _recent.clear()
    _seen.clear()
    _last_ctx.clear()


def _resolve(context):
    """补全上下文：这次没给的维度沿用上一次的值（状态连续感）。"""
    merged = dict(_last_ctx)
    for k, v in (context or {{}}).items():
        if v not in ("", None):
            merged[k] = v
    return merged


def _pick(lines):
    """选一句：冷却窗排除最近用过的 → 剩下按「用得越少权重越大」随机。

    冷却窗按池子自适应：k = min(_COOLDOWN, len-2)，至少留 2 个候选，
    否则「排除」会把随机性吃光、退化成确定轮换（实测踩过）。
    """
    n = len(lines)
    counts = [_seen.get((id(lines), i), 0) for i in range(n)]
    k = min(_COOLDOWN, max(1, n - 2)) if n > 1 else 0
    if k:
        recent = set(_recent[-k:])
        pool = [i for i in range(n) if lines[i] not in recent]
    else:
        pool = list(range(n))
    if not pool:
        pool = list(range(n))
    weights = [1.0 / (1.0 + counts[i]) for i in pool]
    idx = random.choices(pool, weights=weights)[0]
    _seen[(id(lines), idx)] = counts[idx] + 1
    if _COOLDOWN:
        _recent.append(lines[idx])
        while len(_recent) > _COOLDOWN:
            _recent.pop(0)
    return lines[idx]


def reply(context: dict) -> str:
    """根据触发上下文返回一句台词。context: {{维度名: 值, ...}}

    永不抛异常。没给的维度沿用上一次；从未给过的组合走模板兜底。
    """
    global _last_ctx
    ctx = _resolve(context)
    _last_ctx = ctx
    key = tuple(ctx.get(d, "") for d in _DIM_ORDER)
    lines = _LINE_LIB.get(key)
    if lines:
        return _pick(lines)
    if _TEMPLATES:
        filled = {{}}
        for var, values in _VARS.items():
            filled[var] = ctx.get(var) if ctx.get(var) else random.choice(values)
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


def selftest() -> int:
    """自检：状态层口径——冷却不连续重复 / 缺键沿用 / 从不给键落兜底 / 不抛异常。"""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {name}")
        ok = ok and bool(cond)

    def load(cfg):
        td = tempfile.mkdtemp(prefix="dlg_engine_")
        p = os.path.join(td, "引擎.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(gen_engine_code(cfg))
        spec = importlib.util.spec_from_file_location("_t_engine", p)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    cfg = {
        "dimensions": {"场景": ["A"], "情绪": ["x", "y"]},
        "line_lib": {"A|x": ["一", "二", "三"], "A|y": ["四"]},
        "templates": ["兜底{对象}"],
        "variables": {"对象": ["你"]},
        "state": {"cooldown": 2},
    }
    m = load(cfg)

    seq = [m.reply({"场景": "A", "情绪": "x"}) for _ in range(200)]
    check("200 次调用无连续重复", all(seq[i] != seq[i - 1] for i in range(1, len(seq))))
    check("三个变体都被用到（均衡）", set(seq) == {"一", "二", "三"})

    def run30(mod):
        mod.reset()
        return [mod.reply({"场景": "A", "情绪": "x"}) for _ in range(30)]

    check("不是确定循环（两次独立序列不同）", run30(m) != run30(m))
    check("30 次里三个变体都出现", set(run30(m)) == {"一", "二", "三"})

    m.reset()
    m.reply({"场景": "A", "情绪": "x"})
    second = m.reply({"场景": "A"})          # 缺情绪 → 沿用 x
    check("缺键沿用上次值（不掉兜底）", second in ("一", "二", "三"))

    m.reset()
    v = ""
    for _ in range(5):
        v = m.reply({"场景": "A", "情绪": "y"})   # 单变体格
        if v != "四":
            break
    check("单变体格稳定返回、不饿死", v == "四")

    m.reset()
    out = m.reply({"场景": "Z", "情绪": "x"})
    check("从未给过的值落兜底", "兜底" in out)

    m.reset()
    check("空 context 不抛异常", isinstance(m.reply({}), str) and len(m.reply({})) > 0)

    cfg2 = {"dimensions": {"场景": ["A"]}, "line_lib": {},
            "templates": [], "variables": {}}
    m2 = load(cfg2)
    check("无模板无格子返回占位文案（不抛）", m2.reply({"场景": "A"}).startswith("[无台词]"))

    print("=" * 52)
    print("自检结果: " + ("全部通过 ✓" if ok else "有未过项 ✗"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="台词系统：配置 → 引擎")
    ap.add_argument("config", nargs="?", default="")
    ap.add_argument("-o", "--output", default="引擎.py")
    ap.add_argument("--selftest", action="store_true", help="跑状态层口径自检")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.config:
        ap.print_help()
        return 1

    cfg = load_config(args.config)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(gen_engine_code(cfg))
    cd = cfg.get("state", {}).get("cooldown", DEFAULT_COOLDOWN)
    print(f"✅ 引擎已生成: {os.path.abspath(args.output)}")
    print(f"   维度: {list(cfg['dimensions'].keys())}  格子: {len(cfg.get('line_lib', {}))}  "
          f"模板: {len(cfg.get('templates', []))}  冷却窗: {cd}")
    return 0


if __name__ == "__main__":
    try:
        import sys
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
