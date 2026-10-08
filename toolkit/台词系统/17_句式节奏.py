#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""句式节奏审计 —— 台词库读起来「一个模子」时用它：先量再改。

量的是「形状」，不是内容：

  1. 句数分布     每行按 。！？…— 切，看是不是全挤在同一个句数上（「是不是都三句话」）
  2. 行首词 top   每行前 2 字，看开头是不是总那几个
  3. 收尾标点谱   句尾标点分布 + 疑问句占比（问句必须是 ？）
  4. 长度         均长 / 标准差 / ≤6 字占比 / ≥20 字占比
  5. 结构签名 top 把每行的标点骨架抽出来（如 `短，短。`、`短。短。`、`长——短。`）——「规律」的量化
  6. 序列维       同格内相邻两条「同签名」或「同开头」→ 报警（单看每条都合格，排开就露）

用法：
    python3 17_句式节奏.py 小雨 [--top 5] [--json]
    python3 17_句式节奏.py 台词角色库/小雨/台词配置.json
"""
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROLE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "台词角色库")

SPLIT = re.compile(r"[。！？…—]+")
END = re.compile(r"[。！？…—]+$")
Q_WORDS = re.compile(r"吗|呢|什么|怎么|哪|几时|是不是|要不要|对不对|行不行|好不好|多少|谁")
Q_TAIL = ("？", "?")
SHORT_MAX = 6
LONG_MIN = 20
SIG_SHORT = 7   # 一段 ≤7 字算「短」，>7 算「长」


def load_config(arg: str):
    p = arg
    if not os.path.exists(p):
        p = os.path.join(ROLE_ROOT, arg, "台词配置.json")
    with open(p, encoding="utf-8") as f:
        return p, json.load(f)


def clauses(line: str):
    """按句末标点切段（保留标点）。`……` / `——` 算一个标点，别拆成两个。"""
    out, buf, i = [], "", 0
    while i < len(line):
        ch = line[i]
        buf += ch
        if ch in "。！？":
            out.append(buf)
            buf = ""
        elif ch in "…—":
            while i + 1 < len(line) and line[i + 1] == ch:
                i += 1
                buf += ch
            out.append(buf)
            buf = ""
        i += 1
    if buf:
        out.append(buf)
    return out


def _punct_of(c: str) -> str:
    m = re.search(r"[。！？]$|[…—]+$", c)
    return m.group() if m else ""


def _bucket(part: str) -> str:
    n = len(part.rstrip("，、"))
    return "短" if n <= 4 else ("中" if n <= 9 else "长")


def signature(line: str) -> str:
    """小节级骨架：每个逗号段按 短/中/长 分档，段末挂它自己的标点。

    '成了。'            → 短。
    '没动静，我守着。' → 短，短。
    '好了——还有别的？'   → 短——短？
    比只看句号切分细一档：单句长句不再和单句短句撞签名。
    """
    out = []
    for c in clauses(line):
        punct = _punct_of(c)
        parts = re.split(r"[，、]", c.rstrip("。！？…—"))
        if len(parts) == 1:
            out.append(_bucket(parts[0]) + punct)
        else:
            out.append("，".join(_bucket(p) for p in parts[:-1]) + "，" + _bucket(parts[-1]) + punct)
    return "".join(out)


def head_of(line: str) -> str:
    s = re.sub(r"^[「『（(【\s]+", "", line)
    return s[:2]


def tail_of(line: str) -> str:
    m = END.search(line)
    return m.group() if m else "无"


def stats_for(lines):
    lens = [len(l) for l in lines]
    sent_counts = [len(SPLIT.findall(l)) for l in lines]
    return {
        "条数": len(lines),
        "均长": round(statistics.mean(lens), 1),
        "σ": round(statistics.pstdev(lens), 1),
        "最短": min(lens),
        "最长": max(lens),
        "≤6字": round(100 * sum(1 for n in lens if n <= SHORT_MAX) / len(lines), 1),
        "≥20字": round(100 * sum(1 for n in lens if n >= LONG_MIN) / len(lines), 1),
        "句数分布": {str(k): sum(1 for n in sent_counts if n == k) for k in sorted(set(sent_counts))},
        "句数均值": round(statistics.mean(sent_counts), 2),
        "句数σ": round(statistics.pstdev(sent_counts), 2),
        "问句%": round(100 * sum(1 for l in lines if l.rstrip().endswith(Q_TAIL) or Q_WORDS.search(l)) / len(lines), 1),
        "行首top": top(list(map(head_of, lines))),
        "签名top": top(list(map(signature, lines))),
        "收尾谱": top([tail_of(l) for l in lines]),
        "签名种类": len({signature(l) for l in lines}),
    }


def top(items, n=5):
    cnt = {}
    for it in items:
        cnt[it] = cnt.get(it, 0) + 1
    return sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def selftest() -> int:
    """自检：签名口径 + 统计口径咬不变量（跑在已知样本上，不看具体台词）。"""
    fails = []
    cases = {
        "成了。": "短。",
        "我不爱说第二遍。": "中。",
        "没动静，我守着。": "短，短。",
        "好了——还有别的？": "短——短？",
        "睡。明天的事明天算。": "短。中。",
    }
    for line, want in cases.items():
        got = signature(line)
        if got != want:
            fails.append(f"签名 {line} → {got}（期望 {want}）")
    st = stats_for(["成了。", "睡。明天的事明天算。", "好了——还有别的？"])
    for k, want in (("条数", 3), ("最短", 3), ("问句%", round(100 / 3, 1))):
        if st[k] != want:
            fails.append(f"统计 {k} = {st[k]}（期望 {want}）")
    if st["签名种类"] != 3:
        fails.append(f"签名种类 = {st['签名种类']}（期望 3）")
    print("自检：" + ("全部通过 ✓" if not fails else f"{len(fails)} 项未过"))
    for f in fails:
        print("  FAIL", f)
    return 1 if fails else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    topn = 5
    if "--top" in sys.argv:
        topn = int(sys.argv[sys.argv.index("--top") + 1])
    if not args:
        print(__doc__)
        return 2
    path, cfg = load_config(args[0])
    cells = cfg.get("line_lib") or {}
    all_lines = [l for v in cells.values() for l in v]

    print(f"句式节奏审计｜{path}")
    print(f"格子 {len(cells)}｜台词 {len(all_lines)} 条"
          f"（模板 {len(cfg.get('templates') or [])} 条不计入）\n")

    st = stats_for(all_lines)
    print("【整体】")
    print(f"  长度  均长 {st['均长']}（{st['最短']}–{st['最长']}）｜σ {st['σ']}"
          f"｜≤6字 {st['≤6字']}%｜≥20字 {st['≥20字']}%")
    print(f"  句数  均值 {st['句数均值']}｜σ {st['句数σ']}｜分布 {st['句数分布']}")
    print(f"  问句  {st['问句%']}%")
    print(f"  行首  {', '.join(f'{k}×{v}' for k, v in st['行首top'][:topn])}")
    print(f"  签名  {', '.join(f'{k}×{v}' for k, v in st['签名top'][:topn])}")
    print(f"  收尾  {', '.join(f'{k}×{v}' for k, v in st['收尾谱'][:topn])}")

    # 序列维：同格内相邻两条同签名 / 同开头
    print("\n【序列维·同格相邻】")
    flags = 0
    for key, lines in cells.items():
        for i in range(len(lines) - 1):
            a, b = lines[i], lines[i + 1]
            if signature(a) == signature(b):
                print(f"  ⚠ {key}：第 {i+1}/{i+2} 条同签名 {signature(a)}")
                flags += 1
            elif head_of(a) == head_of(b):
                print(f"  ⚠ {key}：第 {i+1}/{i+2} 条同开头「{head_of(a)}」")
                flags += 1
    print("  无 ✓" if not flags else f"  共 {flags} 处")

    # 逐格
    print("\n【逐格】")
    thin = []
    for key in sorted(cells):
        lines = cells[key]
        s = stats_for(lines)
        mark = ""
        if s["条数"] < 8:
            mark = " ⟵ 起步规模" if s["条数"] <= 3 else " ⟵ 条数偏少"
            thin.append(key)
        if s["句数σ"] < 0.35:
            mark += " ⟵ 句数一个模子"
        sig_floor = min(4, s["条数"]) if s["条数"] <= 4 else max(4, int(0.6 * s["条数"]))
        if s["签名种类"] < sig_floor:
            mark += " ⟵ 签名种类偏少"
        print(f"  {key}｜{s['条数']} 条｜均长 {s['均长']}｜句数σ {s['句数σ']}"
              f"｜签名 {s['签名种类']} 种｜问句 {s['问句%']}%｜{mark}")
    if thin:
        n_all, n_thin = len(cells), len(thin)
        print(f"\n  条数 <8 的格子 {n_thin} 个：{n_thin/max(1,n_all)*100:.0f}%")
        if n_thin == n_all and max(len(cells[k]) for k in cells) <= 3:
            print("  起步库：每格 2~3 条是设计内的初始规模（先覆盖，后密度），加密阶段再补到 8~10 条/格。")
        else:
            print("  目标：加密到 8~10 条/格，重复感才压得住。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
