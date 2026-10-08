#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
18_补台词建议.py —— 台词系统 · 日志驱动的补台词清单（反馈层 → 行动）
=====================================================================
把运行日志与配置对起来，直接回答「补哪一格、补几条」——不再让人肉推：

  【优先补变体】高频格 × 变体少 —— 重复感最先从这里冒出来
  【待补格子】  真实触发过、却只能吃模板兜底的组合 —— line_lib 缺这些 key，补上就是真覆盖
  【冷格子】    配了却从没被触发的格子 —— 触发源没喂这些值 / 格子白画，二选一，判断留给人

用法：
    python3 18_补台词建议.py 小雨            # 只看清单
    python3 18_补台词建议.py 小雨 --apply    # 另写 <角色>/素材/待补台词.md，填完走 dlg seed

口径：
    - 格子 key 只用 dimensions 声明的维度取值组成；日志 context 里的变量键（对象/事件）不进 key。
    - 清单一律给数字不给命令——「高频但变体少」也可能是触发源喂错了值，判断留给人。
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from itertools import product

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

VAR_MIN = 3          # 每格变体下限（skill 标准：2~3 条变体）
TOP_N = 8            # 每张清单最多列几条
STUB_NAME = "待补台词.md"


def read_log(path):
    recs = []
    if not path or not os.path.exists(path):
        return recs
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return recs


def key_of(ctx, dims):
    """按配置的维度顺序取值组 key——变量键（对象/事件）不进 key"""
    return "|".join(str(ctx.get(d, "?")) for d in dims)


def analyze(cfg: dict, records: list) -> dict:
    dims = list(cfg["dimensions"].keys())
    lib = cfg.get("line_lib", {}) or {}

    touched = Counter()
    fallback = Counter()
    for r in records:
        k = key_of(r.get("context", {}), dims)
        touched[k] += 1
        if r.get("mode") == "模板兜底":
            fallback[k] += 1

    all_cells = set()
    for combo in product(*[cfg["dimensions"][d] for d in dims]):
        all_cells.add("|".join(str(v) for v in combo))

    # 待补格子：触发过、走了兜底、且配置里没有这个 key（有 key 就走不到兜底）
    to_fill = sorted(((k, n) for k, n in fallback.items() if k not in lib),
                     key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    # 优先补变体：已配、被触发过、变体不足
    thin = sorted(((k, n, len(lib.get(k, []))) for k, n in touched.items()
                   if k in lib and len(lib[k]) < VAR_MIN),
                  key=lambda t: (-t[1], t[0]))[:TOP_N]
    # 冷格子：配了、从没被触发
    cold = sorted(set(lib) - set(touched))
    # 没配、也没被触发过的格子（全空间里的剩余）
    never = sorted(all_cells - set(lib) - set(touched) - set(fallback))

    return dict(dims=dims, total=len(records), cells=len(all_cells),
                to_fill=to_fill, thin=thin, cold=cold, never=never,
                fallback_total=sum(fallback.values()))


def report(role, cfg, r, log_path):
    ok = "✓"
    L = []
    L.append("=" * 64)
    L.append(f"补台词建议 · {role}")
    L.append("=" * 64)
    L.append(f"  日志 {r['total']} 条｜配置格子 {len(cfg.get('line_lib', {}))} 个｜"
             f"触发组合空间 {r['cells']}｜模板兜底 {r['fallback_total']} 次")
    if not r["total"]:
        L.append("")
        L.append("  日志为空——先跑一段真实触发：dlg run <角色> --batch N")
        L.append("  （只跑过测试批次的库看不出冷热，别拿它当结论）")
        return "\n".join(L), True

    L.append("-" * 64)
    L.append("【优先补变体】高频 × 变体少（重复感最先从这里冒出来）")
    if r["thin"]:
        for k, n, have in r["thin"]:
            L.append(f"  {k:<16} 触发 {n:>4} 次｜现有 {have} 条   ← 补到 {VAR_MIN}~5 条")
    else:
        L.append(f"  {ok} 无——被触发的格子变体都够")

    L.append("")
    L.append("【待补格子】触发过、却只吃到兜底（line_lib 缺这些组合）")
    if r["to_fill"]:
        for k, n in r["to_fill"]:
            L.append(f"  {k:<16} 兜底 {n:>4} 次   ← 配置里没有这个格子")
    else:
        L.append(f"  {ok} 无——没有组合掉进兜底")

    L.append("")
    L.append("【冷格子】配了、却从没被触发")
    if r["cold"]:
        for k in r["cold"][:TOP_N]:
            L.append(f"  {k}")
        more = len(r["cold"]) - TOP_N
        if more > 0:
            L.append(f"  …另 {more} 个")
        L.append("  → 两种可能，判给自己：触发源没喂这些取值 / 格子白画（触发源本来就到不了）")
    else:
        L.append(f"  {ok} 无——配了的格子都被触发过")

    L.append("-" * 64)
    L.append("下一步：")
    if r["to_fill"] or r["thin"]:
        L.append("  补台词 → `dlg fill " + role + " --apply` 生成 <角色>/素材/" + STUB_NAME)
        L.append("           填好后 `dlg seed " + role + " --apply` 入库（自动备份 + 去重）")
        L.append("           再 `dlg gen " + role + "` → `dlg cover " + role + "` 看数字动了没")
    else:
        L.append("  没有要写的台词——待补格子与变体两项都空。")
    if r["cold"]:
        L.append(f"  冷格子 {len(r['cold'])} 个（不是补台词的对象）：先判是触发源没喂这些取值、还是格子白画。")
    else:
        L.append("  冷格子 0 个——配了的格子都被触发过。")
    return "\n".join(L), False


def write_stub(role_dir, role, r):
    """生成可填脚手架——与 dlg seed 的素材格式同构，闭环不断"""
    mat = os.path.join(role_dir, "素材")
    os.makedirs(mat, exist_ok=True)
    path = os.path.join(mat, STUB_NAME)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    dims_hint = "|".join(r["dims"]) or "维度1|维度2"
    L = [
        f"# 待补台词（dlg fill {role} 生成 · {now}）——本文件每次生成会覆盖，别往里写长期素材",
        f"# 填法：[{dims_hint}] 台词   一行一条",
        "# `#` 开头的行会被忽略；标了格但后面空着的行也不会入库（占位用）",
        f"# 填完跑：dlg seed {role} --apply",
        "",
    ]
    if r["to_fill"]:
        L.append("## 待补格子——触发过却只吃到兜底（补上就是真覆盖）")
        for k, n in r["to_fill"]:
            L.append(f"[{k}] ")
        L.append("")
    if r["thin"]:
        L.append("## 优先补变体——高频格，现有变体少")
        for k, n, have in r["thin"]:
            L.append(f"[{k}] ")
        L.append("")
    if not r["to_fill"] and not r["thin"]:
        L.append("# （三张清单都干净，没有要补的格子）")
    while L and not L[-1].strip():   # 只去末尾空行，别动内容行（行尾空格被吃会让占位行认不出来）
        L.pop()
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def selftest() -> int:
    """自检：清单口径咬在造出来的日志上（不碰真实库）——
    变量键不进 key / 兜底归并 / 冷格子判据 / 空日志不炸。"""
    ok = True
    cfg = {
        "dimensions": {"场景": ["A", "B"], "情绪": ["x", "y"]},
        "line_lib": {"A|x": ["一"], "A|y": ["二", "三"], "B|x": ["四"]},
        "templates": ["兜底"],
    }
    recs = [
        {"context": {"场景": "A", "情绪": "x", "对象": "你"}, "mode": "格子命中"},
        {"context": {"场景": "A", "情绪": "x", "对象": "同事"}, "mode": "格子命中"},
        {"context": {"场景": "A", "情绪": "x", "对象": "你"}, "mode": "格子命中"},
        {"context": {"场景": "B", "情绪": "y", "对象": "你"}, "mode": "模板兜底"},
        {"context": {"场景": "B", "情绪": "y", "对象": "你"}, "mode": "模板兜底"},
        {"context": {"场景": "A", "情绪": "y"}, "mode": "格子命中"},
    ]
    r = analyze(cfg, recs)

    def check(name, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {name}")
        ok = ok and bool(cond)

    check("变量键不进格子 key", all("对象" not in k for k, _, _ in r["thin"]))
    check("优先补变体按触发次数排序", [k for k, _, _ in r["thin"]] == ["A|x", "A|y"])
    check("变体现有量跟着报", [h for _, _, h in r["thin"]] == [1, 2])
    check("兜底组合进待补格子", [k for k, _ in r["to_fill"]] == ["B|y"])
    check("兜底次数统计正确", [n for _, n in r["to_fill"]] == [2])
    check("冷格子＝配了没触发", r["cold"] == ["B|x"])
    check("触发组合空间＝笛卡尔积", r["cells"] == 4)
    r0 = analyze(cfg, [])
    check("空日志不炸且冷格子＝全部已配格",
          r0["total"] == 0 and r0["to_fill"] == [] and r0["cold"] == ["A|x", "A|y", "B|x"])
    print("=" * 52)
    print("自检结果: " + ("全部通过 ✓" if ok else "有未过项 ✗"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="台词系统：日志驱动的补台词清单")
    ap.add_argument("role", nargs="?", default="", help="角色名（或台词配置.json 路径）")
    ap.add_argument("--apply", action="store_true",
                    help=f"另写 <角色>/素材/{STUB_NAME}（可填后走 dlg seed）")
    ap.add_argument("--log", default="", help="指定运行日志（默认取 <角色>/日志/运行日志.jsonl）")
    ap.add_argument("--selftest", action="store_true", help="跑口径自检（不碰真实库）")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.role:
        ap.print_help()
        return 1

    role = args.role
    if os.path.isfile(role):
        role_dir = os.path.dirname(os.path.abspath(role))
        role = os.path.basename(role_dir)
    else:
        role_dir = os.path.join(ROLE_ROOT, role)
    cfg_path = os.path.join(role_dir, "台词配置.json")
    if not os.path.isfile(cfg_path):
        print(f"❌ 找不到角色配置: {cfg_path}")
        print(f"   （角色库根：{ROLE_ROOT}——用 `dlg list` 看有哪些角色）")
        return 1
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    log_path = args.log or os.path.join(role_dir, "日志", "运行日志.jsonl")

    records = read_log(log_path)
    r = analyze(cfg, records)
    text, _empty = report(role, cfg, r, log_path)
    print(text)
    if args.apply:
        path = write_stub(role_dir, role, r)
        print(f"\n✅ 脚手架已生成: {path}")
        print(f"   填好后: dlg seed {role} --apply")
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            if sys.stdin.isatty():
                input("\n按回车键退出...")
        except EOFError:
            pass
