#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台词系统构思验证
================
验证命题：台词适配广度 不取决于「台词总条数」，而取决于「触发维度覆盖」。
对比三种策略，在同一触发空间、同一台词文字量下，度量覆盖率 / 命中率 / 利用率：

  A. 无结构堆砌   —— 凭感觉写 N 条，分布偏斜（集中写热门场景，冷门场景漏光）
  B. 结构化格子   —— 先画触发格子（场景×情绪×对象×事件），一格一条，不重复
  C. 模板 + 变量  —— 一条模板带变量槽（对象/事件从上下文注入），一条顶多条

运行：python3 台词系统验证.py
结果：确定性可复现（固定随机种子）。任何环境（含 Windows 双击）都不会闪退：
      编码异常与运行时异常均有兜底，错误会打印出来而不是直接退出。
"""

import random
import sys
from collections import Counter
from itertools import product

# ---- 编码兜底：Windows 控制台(GBK) 下中文输出不再 UnicodeEncodeError ----
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 旧版 Python 无 reconfigure，保持默认即可

random.seed(42)


def main() -> None:
    # ==================================================================
    # 1. 触发空间：台词会在什么条件下被触发
    # ==================================================================
    SCENES  = ["问候", "工作", "熬夜", "吃饭", "道别"]   # 5
    MOODS   = ["平静", "开心", "疲惫", "烦躁"]           # 4
    TARGETS = ["你", "同事", "路人"]                   # 3
    EVENTS  = ["无", "成功", "失败"]                     # 3

    TOTAL_COMBOS = len(SCENES) * len(MOODS) * len(TARGETS) * len(EVENTS)
    ALL_COMBOS = list(product(SCENES, MOODS, TARGETS, EVENTS))

    print(f"触发空间：{len(SCENES)} 场景 × {len(MOODS)} 情绪 × {len(TARGETS)} 对象 × {len(EVENTS)} 事件 = {TOTAL_COMBOS} 种触发组合")

    def random_trigger():
        """真实触发：均匀随机落在一个组合上"""
        return (random.choice(SCENES), random.choice(MOODS),
                random.choice(TARGETS), random.choice(EVENTS))

    # ==================================================================
    # 2. 策略 A：无结构堆砌（模拟"凭感觉写"的偏斜分布）
    # ==================================================================
    # 写台词的人不系统：绝大多数心思花在 1~2 个热门场景/情绪上，冷门区域漏光。
    SCENE_WEIGHTS  = {"问候": 0.45, "工作": 0.35, "熬夜": 0.06, "吃饭": 0.09, "道别": 0.05}
    MOOD_WEIGHTS   = {"平静": 0.45, "开心": 0.30, "疲惫": 0.15, "烦躁": 0.10}
    TARGET_WEIGHTS = {"你": 0.55, "同事": 0.30, "路人": 0.15}
    EVENT_WEIGHTS  = {"无": 0.65, "成功": 0.18, "失败": 0.17}

    def run_strategy_A(n_lines: int):
        """堆 N 条无结构台词 → 覆盖的组合集合（重复落在同一组合不计）"""
        covered = set()
        for _ in range(n_lines):
            combo = (
                random.choices(list(SCENE_WEIGHTS),  weights=list(SCENE_WEIGHTS.values()))[0],
                random.choices(list(MOOD_WEIGHTS),   weights=list(MOOD_WEIGHTS.values()))[0],
                random.choices(list(TARGET_WEIGHTS), weights=list(TARGET_WEIGHTS.values()))[0],
                random.choices(list(EVENT_WEIGHTS),  weights=list(EVENT_WEIGHTS.values()))[0],
            )
            covered.add(combo)
        return covered

    def run_strategy_B(n_lines: int):
        """结构化格子：填 N 个格子，一格一条不重复"""
        return set(ALL_COMBOS[:min(n_lines, TOTAL_COMBOS)])

    VARIANTS_PER_TEMPLATE = len(TARGETS) * len(EVENTS)  # 每模板 9 种变体

    def run_strategy_C(n_templates: int):
        """模板+变量：每条模板绑定(场景,情绪)一格，对象/事件用变量注入"""
        covered = set()
        for s, m in list(product(SCENES, MOODS))[:n_templates]:
            for t, e in product(TARGETS, EVENTS):
                covered.add((s, m, t, e))
        return covered

    # ==================================================================
    # 3. 评估
    # ==================================================================
    def hit_rate(covered: set, trials: int = 20000) -> float:
        hits = sum(1 for _ in range(trials) if random_trigger() in covered)
        return hits / trials

    def utilization(covered: set, trials: int = 80000):
        """利用率：覆盖区每条台词(格子)被命中的平均次数 + 峰值比（越接近1越均匀）"""
        if not covered:
            return 0.0, 0.0
        counts = Counter()
        for _ in range(trials):
            c = random_trigger()
            if c in covered:
                counts[c] += 1
        if not counts:
            return 0.0, 0.0
        vals = list(counts.values())
        return sum(vals) / len(vals), min(vals) / max(vals)

    # ==================================================================
    # 4. 主实验：多个台词量档位 × 三种策略
    # ==================================================================
    print("\n" + "=" * 78)
    print("对比一：相同台词文字量下，覆盖的触发组合数（总数 180）")
    print("=" * 78)
    print(f"{'台词量':>6} | {'A 无结构堆砌':>14} | {'B 结构化格子':>14} | {'C 模板+变量':>14} | 结论")
    print("-" * 78)

    summary = {}
    for N in [10, 30, 60, 100]:
        a, b, c = run_strategy_A(N), run_strategy_B(N), run_strategy_C(N)
        summary[N] = (len(a), len(b), len(c))
        tag = "C 已打满/超出空间" if len(c) >= TOTAL_COMBOS else ""
        print(f"{N:>6} | {len(a):>10} ({len(a)/TOTAL_COMBOS*100:4.1f}%) | "
              f"{len(b):>10} ({len(b)/TOTAL_COMBOS*100:4.1f}%) | "
              f"{len(c):>10} ({len(c)/TOTAL_COMBOS*100:4.1f}%) | {tag}")

    print("\n" + "=" * 78)
    print("对比二：N=30 时，随机触发 2 万次的命中率（有台词可回的概率）")
    print("=" * 78)
    for label, covered in [("A 无结构堆砌", run_strategy_A(30)),
                           ("B 结构化格子", run_strategy_B(30)),
                           ("C 模板+变量 ", run_strategy_C(30))]:
        print(f"  {label}: 命中率 {hit_rate(covered)*100:5.1f}%")

    print("\n" + "=" * 78)
    print("对比三：台词利用率（覆盖区内平均命中次数 / 峰值比，峰值比越接近 1 越不浪费）")
    print("=" * 78)
    for label, covered in [("A 无结构堆砌", run_strategy_A(30)),
                           ("B 结构化格子", run_strategy_B(30)),
                           ("C 模板+变量 ", run_strategy_C(30))]:
        avg, ratio = utilization(covered)
        print(f"  {label}: 平均 {avg:6.1f} 次/组合   峰值比 {ratio:.2f}")

    # ==================================================================
    # 5. 结论判定
    # ==================================================================
    print("\n" + "=" * 78)
    print("结论")
    print("=" * 78)
    a30, b30, c30 = summary[30]
    print(f"  30 条文字量：A 覆盖 {a30} 格，B 覆盖 {b30} 格，C 覆盖 {c30} 格（已饱和）。")
    print(f"  → 同一文字量，格子比凭感觉堆多覆盖 {b30 - a30} 个组合；")
    print(f"  → 模板+变量把区分度放大 {VARIANTS_PER_TEMPLATE} 倍，30 条模板即可打满 180 格；")
    print(f"  → 命题成立：适配广度由维度覆盖决定，不由台词条数决定。")

    # ==================================================================
    # 6. 迷你台词引擎：证明这套系统能直接跑
    # ==================================================================
    print("\n" + "=" * 78)
    print("迷你台词引擎（结构化格子 + 模板变量 双通道）")
    print("=" * 78)

    LINE_LIB = {
        ("熬夜", "疲惫"): ["啧，又熬夜，你是嫌天亮得太早？", "行，我陪着。天塌下来先记一笔。"],
        ("熬夜", "平静"): ["还不睡？记录一下：某人在跟月亮较劲。", "夜是给素描本用的，不是给你熬的。"],
        ("问候", "平静"): ["来了？今天的宇宙没爆炸，先记着。", "早上好——行，勉强算个好。"],
        ("问候", "开心"): ["哟，心情不错？记进素描本了。", "这一笔是彩色的，你赚到了。"],
        ("工作", "烦躁"): ["卡了？先骂三声，再调。", "这代码要是能听懂人话，早该道歉了。"],
        ("吃饭", "开心"): ["吃上了？我批准。", "记得吃——不然半夜又来找我要布丁。"],
    }

    TEMPLATES = [
        "{对象}，{事件}了？行，我看着呢。",
        "哦？{对象}这边{事件}——素描本记上了，翻不了案。",
        "有个{事件}的消息，{对象}自己掂量，我不救场。",
    ]

    _seen = {}  # 变体轮换：记录每条台词被使用次数，优先选说得少的

    def engine_reply(scene: str, mood: str, target: str, event: str) -> str:
        lines = LINE_LIB.get((scene, mood))
        if lines:
            # 真·变体轮换：优先返回使用次数最少的，同格连调不重复
            counts = [_seen.get((id(lines), i), 0) for i in range(len(lines))]
            idx = counts.index(min(counts))
            _seen[(id(lines), idx)] = _seen.get((id(lines), idx), 0) + 1
            return f"[格子命中] {lines[idx]}"
        tmpl = random.choice(TEMPLATES)  # 格子没覆盖 → 模板兜底，变量注入
        return f"[模板+变量] {tmpl.format(对象=target, 事件=event)}"

    demo_cases = [
        ("熬夜", "疲惫", "你", "无"),
        ("熬夜", "疲惫", "你", "无"),    # 同格第二次 → 变体轮换，不重复
        ("问候", "平静", "你", "无"),
        ("开会", "烦躁", "同事", "失败"),  # 格子没覆盖 → 模板兜底
        ("吃饭", "开心", "你", "成功"),
    ]
    for c in demo_cases:
        print(f"  触发 {c} -> {engine_reply(*c)}")

    print("\n运行结束，无异常。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已手动中断。")
    except Exception:
        # 异常兜底：任何错误都打印出来，绝不静默闪退
        import traceback
        traceback.print_exc()
    finally:
        # 防闪退：双击运行时窗口停住，让用户看清输出/错误
        try:
            input("\n按回车键退出...")
        except EOFError:
            pass  # 非交互环境（管道/自动化）下自动结束
