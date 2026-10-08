#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
15_自检.py —— 台词系统 · 回归测试（防破坏）
============================================
内置样例断言集，跑一遍核心脚本的行为，验证打磨不倒退：
    1. 合法配置 → check 通过 / gen 成功 / cover 兜底后 100%
    2. 空库配置 → gen 成功 / cover 兜底后 100%（模板兜底）
    3. 缺 dimensions → check 拒绝
    4. line_lib 维度数不符 → check 拒绝
    5. 重复台词 → dup 报问题
    6. 超长台词 → rule 报问题（长度上限 20）
    7. 禁用词 → rule 报问题
    8. 引擎冒烟 → reply 命中/模板兜底/占位文案不抛错
    9. SIGPIPE 管道安全 → 脚本输出 | head 不崩

用法：
    python3 15_自检.py [--quiet]
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))


def run(script, *args, timeout=60):
    cmd = [sys.executable, os.path.join(BASE, script), *args]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=timeout)
    return out.returncode, out.stdout + out.stderr


def load_mod(path):
    spec = importlib.util.spec_from_file_location("_t_engine", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VALID = {
    "dimensions": {"场景": ["问候", "熬夜"], "情绪": ["平静", "烦躁"]},
    "line_lib": {"问候|平静": ["早。", "来了？"], "熬夜|烦躁": ["睡。"],
                 "问候|烦躁": ["嗯。"], "熬夜|平静": ["在看。"]},
    "templates": ["{对象}，先记着。"],
    "variables": {"对象": ["你"]},
}

NO_DIMS = {"dimensions": {}, "line_lib": {}, "templates": ["兜底。"], "variables": {}}

BAD_DIM_COUNT = {
    "dimensions": {"场景": ["问候"], "情绪": ["平静"]},
    "line_lib": {"问候": ["只给一个维度值"]},  # key 只 1 段，维度 2 个
    "templates": [], "variables": {},
}

DUP = {
    "dimensions": {"场景": ["问候"], "情绪": ["平静"]},
    "line_lib": {"问候|平静": ["同一句", "同一句"]},
    "templates": [], "variables": {},
}

LONG_LINE = {
    "dimensions": {"场景": ["问候"], "情绪": ["平静"]},
    "line_lib": {"问候|平静": ["这是一个超过二十个字符的超长测试台词句子因为太长所以一定超"]},
    "templates": [], "variables": {},
}

BAD_WORD = {
    "dimensions": {"场景": ["问候"], "情绪": ["平静"]},
    "line_lib": {"问候|平静": ["大发慈悲，我不干。"]},
    "templates": [], "variables": {},
}

EMPTY = {
    "dimensions": {"场景": ["问候", "工作"], "情绪": ["平静", "烦躁"]},
    "line_lib": {},
    "templates": ["{对象}，我在。"],
    "variables": {"对象": ["你"]},
}


def main():
    ap = argparse.ArgumentParser(description="台词系统：回归自检")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总")
    args = ap.parse_args()

    results = []
    with tempfile.TemporaryDirectory(prefix="dlg_selftest_") as td:
        def w(name, obj):
            p = os.path.join(td, name)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
            return p

        p_valid = w("valid.json", VALID)
        p_empty = w("empty.json", EMPTY)
        p_nodims = w("nodims.json", NO_DIMS)
        p_baddim = w("baddim.json", BAD_DIM_COUNT)
        p_dup = w("dup.json", DUP)
        p_long = w("long.json", LONG_LINE)
        p_badword = w("badword.json", BAD_WORD)

        # 1 合法配置
        rc, out = run("02_校验配置.py", p_valid)
        results.append(("合法配置校验", rc == 0 and "✅" in out, "exit=0 且通过"))
        rc, out = run("06_生成引擎.py", p_valid, "-o", os.path.join(td, "e_valid.py"))
        results.append(("合法配置生成", rc == 0 and "✅" in out, "exit=0 且生成"))
        if os.path.exists(os.path.join(td, "e_valid.py")):
            rc, out = run("07_验证覆盖率.py", p_valid, "--trials", "500")
            results.append(("合法配置覆盖率", "100.0%" in out, "兜底后 100%"))

        # 2 空库配置
        rc, out = run("06_生成引擎.py", p_empty, "-o", os.path.join(td, "e_empty.py"))
        ok_gen = rc == 0 and os.path.exists(os.path.join(td, "e_empty.py"))
        results.append(("空库生成", ok_gen, "空 line_lib 可生成"))
        rc, out = run("07_验证覆盖率.py", p_empty, "--trials", "500")
        results.append(("空库覆盖率", "100.0%" in out, "模板兜底 100%"))

        # 3 缺 dimensions
        rc, out = run("02_校验配置.py", p_nodims)
        results.append(("缺维度拒绝", rc != 0 or "❌" in out, "非 0 或报错"))

        # 4 key 维度数不符
        rc, out = run("02_校验配置.py", p_baddim)
        results.append(("维度数不符拒绝", rc != 0 or "❌" in out, "非 0 或报错"))

        # 5 重复台词
        rc, out = run("03_查重.py", p_dup)
        results.append(("重复台词检出", "❌" in out or "重复" in out, "报重复"))

        # 6 超长台词
        rc, out = run("04_硬规则检查.py", p_long, os.path.join(td, "no_rule.json"))
        # 无规则文件时按默认上限？04 可能报错规则文件缺失——用临时规则文件
        rule_p = os.path.join(td, "rule20.json")
        with open(rule_p, "w", encoding="utf-8") as f:
            json.dump({"禁用词": [], "长度上限": 20, "必须包含": []}, f, ensure_ascii=False)
        rc, out = run("04_硬规则检查.py", p_long, rule_p)
        results.append(("超长台词检出", "❌" in out or "超" in out, "报超长"))

        # 7 禁用词
        rule_bad_p = os.path.join(td, "rule_badword.json")
        with open(rule_bad_p, "w", encoding="utf-8") as f:
            json.dump({"禁用词": ["大发慈悲"], "长度上限": 40, "必须包含": []}, f, ensure_ascii=False)
        rc, out = run("04_硬规则检查.py", p_badword, rule_bad_p)
        results.append(("禁用词检出", "❌" in out or "大发慈悲" in out, "报禁用词"))

        # 8 引擎冒烟
        if os.path.exists(os.path.join(td, "e_valid.py")):
            mod = load_mod(os.path.join(td, "e_valid.py"))
            try:
                r1 = mod.reply({"场景": "问候", "情绪": "平静"})
                r2 = mod.reply({"场景": "不存在", "情绪": "未知"})
                r3 = mod.reply({})
                ok = isinstance(r1, str) and len(r1) > 0 and \
                     isinstance(r2, str) and len(r2) > 0 and \
                     isinstance(r3, str) and len(r3) > 0
                results.append(("引擎冒烟", ok, "命中/模板兜底/占位都不抛错"))
            except Exception as e:
                results.append(("引擎冒烟", False, f"抛错: {e}"))

        # 9 SIGPIPE 管道安全
        try:
            p = subprocess.Popen(
                [sys.executable, os.path.join(BASE, "09_日志分析.py"),
                 os.path.join(td, "no_log.jsonl")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
            head = p.stdout.readline()
            p.stdout.close()
            p.wait(timeout=15)
            ok_pipe = p.returncode in (0, 141)  # 141 = SIGPIPE 默认终止，也算安全
            results.append(("SIGPIPE 管道安全", ok_pipe, f"退出码 {p.returncode}"))
        except Exception as e:
            results.append(("SIGPIPE 管道安全", False, f"异常: {e}"))

        # 10 日志子目录自动创建（克隆后 --log 指向不存在目录也能跑）
        if os.path.exists(os.path.join(td, "e_valid.py")):
            sub_log = os.path.join(td, "子目录", "log.jsonl")
            try:
                rc_log, _ = run("08_运行演示.py", os.path.join(td, "e_valid.py"),
                                "--batch", "1", "--cooldown", "0", "--log", sub_log)
                ok_logdir = rc_log == 0 and os.path.exists(sub_log)
                results.append(("日志子目录自动创建", ok_logdir, f"exit={rc_log} 文件存在={os.path.exists(sub_log)}"))
            except Exception as e:
                results.append(("日志子目录自动创建", False, f"异常: {e}"))

        # 11 非交互调用不吐「按回车」噪音（管道/脚本调用应直接退出）
        try:
            p = subprocess.run(
                [sys.executable, os.path.join(BASE, "11_角色列表.py")],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=15)
            blob = (p.stdout or "") + (p.stderr or "")
            no_pause = "按回车" not in blob
            results.append(("非交互无回车噪音", no_pause,
                            "管道调用输出干净" if no_pause else "仍在输出「按回车键退出」"))
        except Exception as e:
            results.append(("非交互无回车噪音", False, f"异常: {e}"))

        # 12 补台词清单口径（18 自带 --selftest：变量键不进 key / 兜底归并 / 冷格子判据）
        try:
            rc, out = run("18_补台词建议.py", "--selftest")
            ok_fill = rc == 0 and "全部通过" in out
            results.append(("补台词清单口径", ok_fill,
                            "变量键/兜底/冷格子" if ok_fill else "18 --selftest 未过"))
        except Exception as e:
            results.append(("补台词清单口径", False, f"异常: {e}"))

        # 13 卡导出字段映射（19 自带 --selftest：场景块/开场格/硬规则/V2 双份）
        try:
            rc, out = run("19_卡导出.py", "--selftest")
            ok_card = rc == 0 and "全部通过" in out
            results.append(("卡导出字段映射", ok_card,
                            "场景块/开场格/硬规则/双份" if ok_card else "19 --selftest 未过"))
        except Exception as e:
            results.append(("卡导出字段映射", False, f"异常: {e}"))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    if not args.quiet:
        print("=" * 52)
        print("台词系统 · 回归自检")
        print("=" * 52)
        for name, ok, detail in results:
            mark = "✅" if ok else "❌"
            print(f"  {mark} {name:<16} {detail}")
        print("=" * 52)
    print(f"自检结果: {passed}/{total} 通过" + (" 🎉" if passed == total else " ← 有失败，先修再发布"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
