#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_验证覆盖率.py —— 台词系统 · 覆盖率验证
============================================
分两段，口径分开写清，别把模拟当实测：

  【理论】触发组合空间、格子直覆盖率、模板兜底后覆盖率、随机触发命中率（模拟）、变体密度
  【实测】运行日志里的真实数据：格子命中/模板兜底占比、触达格子、冷格子、高频触发

标准：兜底后覆盖率应达 100%。

用法：
    python3 07_验证覆盖率.py 配置.json [--trials 20000]
    --log PATH     指定运行日志（默认取 <角色>/日志/运行日志.jsonl）
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import itertools
import json
import os
import random
from collections import Counter


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if "dimensions" not in cfg or not cfg["dimensions"]:
        raise ValueError("配置缺少非空的 dimensions 字段")
    return cfg


def parse_line_lib(cfg: dict) -> dict:
    return {tuple(k.strip() for k in ks.split("|")): list(lines)
            for ks, lines in cfg.get("line_lib", {}).items()}


def combos_of(lists) -> int:
    return len(list(itertools.product(*lists)))


def default_log_path(config_path: str) -> str:
    """<角色>/台词配置.json → <角色>/日志/运行日志.jsonl"""
    return os.path.join(os.path.dirname(os.path.abspath(config_path)), "日志", "运行日志.jsonl")


def real_stats(log_path: str, dim_names: list):
    """真实运行统计（来自 08 的运行日志 JSONL）。没日志返回 None。"""
    if not log_path or not os.path.exists(log_path):
        return None
    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not records:
        return None
    modes = Counter(r.get("mode", "?") for r in records)
    hit = modes.get("格子命中", 0)
    fb = modes.get("模板兜底", 0)
    touched = Counter()
    for r in records:
        ctx = r.get("context", {})
        touched[tuple(str(ctx.get(d)) for d in dim_names)] += 1
    return dict(total=len(records), hit=hit, fallback=fb,
                touched=len(touched), top=touched.most_common(3),
                log_path=log_path)


def evaluate(cfg: dict, trials: int = 20000) -> dict:
    dims = list(cfg["dimensions"].values())
    vars_lists = [list(v) for v in cfg.get("variables", {}).values()]
    line_lib = parse_line_lib(cfg)
    templates = cfg.get("templates", [])

    total_dim = combos_of(dims)
    total_var = combos_of(vars_lists) if vars_lists else 1
    total_space = total_dim * total_var
    n_cells = len(line_lib)
    grid_covered = n_cells * total_var
    grid_rate = grid_covered / total_space if total_space else 0.0
    final_rate = 1.0 if (templates or grid_covered >= total_space) else grid_rate

    def random_ctx():
        ctx = {}
        for name, values in cfg["dimensions"].items():
            ctx[name] = random.choice(values)
        for name, values in cfg.get("variables", {}).items():
            ctx[name] = random.choice(values)
        return ctx

    def has_line(ctx) -> bool:
        key = tuple(ctx[d] for d in cfg["dimensions"])
        return key in line_lib or bool(templates)

    hits = sum(1 for _ in range(trials) if has_line(random_ctx()))
    hit_rate = hits / trials

    # 变体密度：每格台词条数分布——这才是「会不会很快重复」的真实指标（静态可测）
    sizes = [len(v) for v in line_lib.values()] or [0]
    thin = sum(1 for s in sizes if s <= 1)

    return dict(total_space=total_space, total_dim=total_dim, total_var=total_var,
                n_lines=sum(len(v) for v in line_lib.values()), n_templates=len(templates),
                n_cells=n_cells, grid_covered=grid_covered, grid_rate=grid_rate,
                final_rate=final_rate, hit_rate=hit_rate, trials=trials,
                v_min=min(sizes), v_avg=sum(sizes) / len(sizes), v_max=max(sizes), v_thin=thin)


def render(cfg: dict, r: dict, real) -> str:
    L = []
    L.append("=" * 60)
    L.append("台词配置覆盖率报告")
    L.append("=" * 60)
    L.append("【理论】按配置算，不依赖运行")
    L.append(f"  参与匹配维度 : {list(cfg['dimensions'].keys())}")
    L.append(f"  变量注入维度 : {list(cfg.get('variables', {}).keys()) or '（无）'}")
    L.append(f"  触发组合空间 : {r['total_space']} 种 = {r['total_dim']} 种维度组合 × {r['total_var']} 种变量组合")
    L.append("-" * 60)
    L.append(f"  台词文字量   : {r['n_lines']} 条格子台词 + {r['n_templates']} 条模板")
    L.append(f"  格子直覆盖   : {r['grid_covered']} / {r['total_space']}  (覆盖率 {r['grid_rate']*100:.1f}%)")
    if r["n_templates"]:
        L.append(f"  模板兜底后   : {r['final_rate']*100:.1f}%  ← 模板接住剩余组合")
    else:
        L.append(f"  兜底后覆盖   : {r['final_rate']*100:.1f}%  （无模板，漏掉的返回占位文案）")
    L.append(f"  随机触发命中 : {r['hit_rate']*100:.1f}%   （模拟口径：均匀随机 {r['trials']} 次）")
    L.append(f"  变体密度     : 平均 {r['v_avg']:.1f} 条/格（{r['v_min']}~{r['v_max']}）" + (
        f"，{r['v_thin']} 个格子才 1 条 → 那些格子很快会重复" if r['v_thin'] else
        "，每格都有变体轮换空间" if r['v_min'] >= 2 else ""))
    L.append("-" * 60)
    L.append("【实测】来自运行日志（真触发，不是模拟）")
    if real is None:
        L.append(f"  （还没跑过真实触发，日志空）→ dlg run <角色> --batch N 跑一段再看")
    else:
        tot = real["total"]
        L.append(f"  日志条目     : {tot}    （{real['log_path']}）")
        L.append(f"  格子命中     : {real['hit']} ({real['hit']/tot*100:.1f}%)"
                 f"   模板兜底: {real['fallback']} ({real['fallback']/tot*100:.1f}%)")
        L.append(f"  触达格子     : {real['touched']} / {r['n_cells']}"
                 f"   （{r['n_cells'] - real['touched']} 个从未触发）")
        top = "；".join(f"{'|'.join(k)} × {n}" for k, n in real["top"])
        L.append(f"  高频触发     : {top}")
    L.append("=" * 60)
    if r["final_rate"] < 0.99:
        L.append("⚠ 覆盖未满：缺模板兜底，建议补 2~3 条模板。")
    elif r["grid_rate"] >= 0.99:
        L.append("✓ 格子已打满全空间：没有漏网组合。")
    else:
        L.append("✓ 格子 + 模板已覆盖全空间。")
    if real and real["fallback"] > 0:
        L.append("⚠ 真实运行里有兜底命中 → 用 dlg log <角色> 看是哪几个格子有洞。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="台词系统：覆盖率验证")
    ap.add_argument("config")
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--log", help="运行日志路径（默认 <角色>/日志/运行日志.jsonl）")
    args = ap.parse_args()
    random.seed(42)
    cfg = load_config(args.config)
    r = evaluate(cfg, args.trials)
    real = real_stats(args.log or default_log_path(args.config), list(cfg["dimensions"]))
    print(render(cfg, r, real))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
