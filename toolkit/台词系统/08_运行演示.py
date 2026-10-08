#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
08_运行演示.py —— 台词系统 · 引擎运行（演示 + 接入 + 冷却 + 日志）
================================================================
加载生成的引擎，支持四种触发来源：
  - 批量模式：随机触发 N 次，演示响应、冷却与日志
  - 交互模式：手动输入 context（key:value），实时触发
  - 文件接入：--input contexts.jsonl，从 JSONL 逐行读 context 批量触发
  - 管道接入：--stdin，从标准输入读 JSONL（程序喂 context）
  - 结构化输出：--json，stdout 输出 JSONL（{"context","reply","mode"}），供程序消费
  - 冷却：同一触发组合在冷却秒数内不重复输出，防刷屏
  - 日志：每次触发写一行 JSONL（09_日志分析.py 消费）

用法：
    python3 08_运行演示.py 引擎.py [--batch 10] [--cooldown 3] [--log 运行日志.jsonl]
    python3 08_运行演示.py 引擎.py --interactive
    python3 08_运行演示.py 引擎.py --input contexts.jsonl [--json]
    cat contexts.jsonl | python3 08_运行演示.py 引擎.py --stdin --json
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import importlib.util
import json
import os
import random
import sys
import time


def ensure_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_engine(path: str):
    spec = importlib.util.spec_from_file_location("_engine", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description="台词系统：引擎运行")
    ap.add_argument("engine", help="生成的引擎 .py 路径")
    ap.add_argument("--batch", type=int, default=0, help="批量随机触发次数（默认 0=不批量）")
    ap.add_argument("--interactive", action="store_true", help="交互模式")
    ap.add_argument("--input", default="", help="从 JSONL 文件读 context 批量触发（每行一个 dict）")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读 JSONL 触发（管道接入）")
    ap.add_argument("--json", action="store_true", help="结构化输出 JSONL（context/reply/mode）")
    ap.add_argument("--cooldown", type=float, default=3.0, help="冷却秒数（默认 3，0=关闭）")
    ap.add_argument("--log", default="运行日志.jsonl", help="日志文件（默认 运行日志.jsonl）")
    args = ap.parse_args()

    sources = sum([args.batch > 0, args.interactive, bool(args.input), args.stdin])
    if sources != 1:
        ap.error("--batch / --interactive / --input / --stdin 四选一")
    if args.stdin and not sys.stdin.isatty():
        pass  # 管道喂入
    elif args.stdin:
        ap.error("--stdin 需要管道输入（本终端是交互终端，别用 --stdin）")

    engine = load_engine(args.engine)
    dim_order = list(engine._DIM_ORDER)
    var_names = list(engine._VARS.keys())
    cooldown = {}  # key -> 上次输出时间
    log_dir = os.path.dirname(os.path.abspath(args.log))
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)  # 日志目录不存在时自动建（克隆后直接可跑）
    log_f = open(args.log, "a", encoding="utf-8")

    def say(text: str):
        """人类可读输出；--json 模式下静音"""
        if not args.json:
            print(text)

    def trigger(ctx: dict, source: str):
        key = tuple(ctx.get(d, "") for d in dim_order)
        now = time.time()
        if args.cooldown > 0 and key in cooldown:
            left = args.cooldown - (now - cooldown[key])
            if left > 0:
                say(f"  [冷却 {left:.1f}s] {key} 暂不重复输出")
                return None
        t0 = time.time()
        line = engine.reply(ctx)
        cost = (time.time() - t0) * 1000
        mode = "格子命中" if tuple(ctx.get(d, "") for d in dim_order) in engine._LINE_LIB else "模板兜底"
        cooldown[key] = time.time()
        rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "context": ctx,
               "line": line, "mode": mode, "cost_ms": round(cost, 2), "source": source}
        log_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log_f.flush()
        if args.json:
            print(json.dumps({"context": ctx, "reply": line, "mode": mode}, ensure_ascii=False))
        else:
            say(f"  {ctx} -> {line}  [{mode} {cost:.1f}ms]")
        return line

    def parse_lines(lines):
        """逐行解析 JSONL；坏行跳过不炸进程，返回 (records, 坏行数)"""
        records, bad = [], 0
        for line in lines:
            s = line.strip()
            if not s:
                continue
            try:
                records.append(json.loads(s))
            except json.JSONDecodeError:
                bad += 1
        return records, bad

    def feed(records, source: str, bad_parse: int = 0):
        n_ok, n_bad = 0, bad_parse
        for i, rec in enumerate(records):
            if not isinstance(rec, dict):
                n_bad += 1
                say(f"  [跳过] 第 {i+1} 行不是 dict: {rec!r}")
                continue
            trigger(rec, source)
            n_ok += 1
        say(f"=== 完成：有效 {n_ok} 条，跳过 {n_bad} 条 ===")

    if args.batch > 0:
        say(f"=== 批量触发 {args.batch} 次（冷却 {args.cooldown}s）===")
        for i in range(args.batch):
            ctx = {}
            for di, d in enumerate(dim_order):
                values = sorted({k[di] for k in engine._LINE_LIB})
                ctx[d] = random.choice(values) if values else ""
            for v in var_names:
                ctx[v] = random.choice(engine._VARS[v])
            trigger(ctx, f"batch#{i+1}")
            if i < args.batch - 1:
                time.sleep(0.3)

    if args.input:
        say(f"=== 从文件接入: {args.input} ===")
        with open(args.input, "r", encoding="utf-8") as f:
            records, bad_parse = parse_lines(f)
        feed(records, "input", bad_parse)

    if args.stdin:
        say("=== 从标准输入接入（JSONL）===")
        records, bad_parse = parse_lines(sys.stdin)
        feed(records, "stdin", bad_parse)

    if args.interactive:
        say("=== 交互模式（输入 key:value，空格分隔；q 退出）===")
        while True:
            raw = input("> ").strip()
            if raw.lower() in ("q", "quit", "exit"):
                break
            if not raw:
                continue
            ctx = {}
            try:
                for part in raw.split():
                    k, v = part.split(":", 1)
                    ctx[k.strip()] = v.strip()
            except ValueError:
                say("  格式: 场景:熬夜 情绪:疲惫 [对象:你]")
                continue
            trigger(ctx, "interactive")

    log_f.close()
    say(f"\n日志已写入: {args.log}")


if __name__ == "__main__":
    ensure_utf8()
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # 仅交互终端才等待；管道/脚本调用直接退出（避免噪音与卡顿）
        try:
            if sys.stdin.isatty():
                input("\n按回车键退出...")
        except EOFError:
            pass
