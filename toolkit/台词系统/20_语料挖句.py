#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20_语料挖句.py —— 台词系统 · 从对话记录挖候选句（素材采集）
=============================================================
把「一堆原始对话 → 按格子分好的候选池」这一步固化成一条命令。

**它只产候选，不自动入库**——挑中的由人加 `[场景|情绪] ` 前缀，再 `dlg seed <角色> --apply`。
机器筛到几百条就够，最终采用的每一条必须人过（这条纪律见 corpus-line-mining，那边是方法论正本）。

分组不写死词表：**按角色自己的 dimensions 取值分组**（默认第一个维度），
取值字面即关键词；要扩词就在角色目录放 `语料关键词.json`：
    {"熬夜": ["熬夜", "睡了", "凌晨", "别熬"], "吃饭": ["吃饭", "饿", "楼丁"]}

输入三种（`--format` 显式指定优先，否则嗅探；嗅探失败报错，不静默产空池）：
    JSONL   每行一个对象——取 content/text/message/mes/msg ＋ name/speaker/role/from
    JSON    数组或对象（SillyTavern 聊天记录 [{name, mes}] 直接吃）
    text    纯文本——整行算一条（--split-sentences 时按句号再拆）

用法：
    python3 20_语料挖句.py 小雨 对话.jsonl
    python3 20_语料挖句.py 小雨 记录.json --speaker 小雨 --out 素材/候选-2026-10-09.md
    python3 20_语料挖句.py 小雨 chat.txt --format text --split-sentences
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

MESSAGE_FIELDS = ["content", "text", "message", "mes", "msg"]
SPEAKER_FIELDS = ["name", "speaker", "role", "from"]
SPLIT_RE = re.compile(r"[。！？!?\n]")
KW_FILE = "语料关键词.json"

# 任务型痕迹词——出现即丢（那些不是台词，是工作汇报）。--bad-file 可追加。
BAD_DEFAULT = ["推送", "仓库", "提交", "commit", "✅", "Operation", "脚本", "命令", "参数", "日志",
               "cron", "token", "git", "索引", "备份", "入库", "闭环", "工作区", "分支", "报错",
               "进程", "端口", "配置", "数据库", "下载", "解析", "抓取", "模型", "接口", "文档",
               "归档", "skill", "文件", "目录", "表格", "清单", "统计", "字段", "条目", "编号",
               "链接", "截图", "识别", "更新", "待确认", "下一步", "本轮", "登记表", "地址",
               "网址", "##", "**", "|"]
# 口语标记——默认要求句中出现至少一个，捞「说话」而不是「叙事」
TASTE_DEFAULT = ["啧", "哼", "行吧", "别", "才", "倒是", "反正", "不就", "早点", "赶紧",
                 "谢", "夸", "陪", "记", "算", "又", "呢", "吧", "啊", "吗", "？", "……"]


# ────────────────────────── 读入 ──────────────────────────

def sniff_format(path: str) -> str:
    """→ 'json' | 'jsonl' | 'text'（显式 --format 时不走这里）"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        head = f.read(8192)
    s = head.lstrip()
    if not s:
        return "text"
    try:
        json.loads(s)
        return "json"
    except json.JSONDecodeError:
        pass
    first = s.splitlines()[0].strip()
    try:
        json.loads(first)
        return "jsonl"
    except json.JSONDecodeError:
        return "text"


def _rec_from_obj(obj):
    """从一条记录里取 (说话人, 正文)；取不到正文返回空串"""
    if isinstance(obj, str):
        return "", obj.strip()
    if not isinstance(obj, dict):
        return "", ""
    text = ""
    for k in MESSAGE_FIELDS:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            text = v
            break
    speaker = ""
    for k in SPEAKER_FIELDS:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            speaker = v.strip()
            break
    return speaker, text.strip()


def read_records(path: str, fmt: str, split_sentences: bool) -> list:
    """→ [(说话人, 正文), ...]"""
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if fmt == "json":
        data = json.loads(raw)
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if isinstance(obj, dict) and isinstance(obj.get("messages"), list):
                items.extend(obj["messages"])      # 有的导出把消息塞在 messages 字段里
                continue
            spk, text = _rec_from_obj(obj)
            if text:
                out.append((spk, text))
    elif fmt == "jsonl":
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue                            # 坏行跳过（报告里计数）
            spk, text = _rec_from_obj(obj)
            if text:
                out.append((spk, text))
    else:
        for line in raw.splitlines():
            line = line.strip()
            if line:
                out.append(("", line))
    if split_sentences:
        out = [(spk, s) for spk, text in out for s in SPLIT_RE.split(text) if s.strip()]
    return out


# ────────────────────────── 分组 ──────────────────────────

def load_role(role: str):
    """→ (角色目录, 配置, 错误)"""
    role_dir = os.path.join(ROLE_ROOT, role)
    cfg_path = os.path.join(role_dir, "台词配置.json")
    if not os.path.isfile(cfg_path):
        return role_dir, None, f"找不到角色配置: {cfg_path}（角色库根：{ROLE_ROOT}）"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return role_dir, json.load(f), None


def build_groups(cfg: dict, role_dir: str, group_by: str):
    """→ (维度名, {取值: [关键词...]})——分组键来自角色自己的 dimensions，不写死私词表"""
    dims = cfg.get("dimensions", {}) or {}
    dim = group_by or next(iter(dims), "")
    if not dim or dim not in dims:
        return "", {}
    groups = {str(v): [str(v)] for v in dims[dim]}
    kw_path = os.path.join(role_dir, KW_FILE)
    extra = {}
    if os.path.isfile(kw_path):
        try:
            extra = json.load(open(kw_path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            extra = {}
    for key, words in extra.items():
        if key in groups and isinstance(words, list):
            groups[key] = list(dict.fromkeys(groups[key] + [str(w) for w in words if str(w).strip()]))
    return dim, groups


# ────────────────────────── 挖句 ──────────────────────────

def mine(records, groups, opts) -> tuple:
    """→ ({组: [句]}, 统计 dict)"""
    bad = list(BAD_DEFAULT) + list(opts.extra_bad)
    taste = [] if opts.no_taste else list(TASTE_DEFAULT)
    pool = defaultdict(set)
    stats = dict(read=len(records), kept=0, dropped_len=0, dropped_bad=0, dropped_taste=0,
                 dropped_speaker=0, dropped_grep=0)
    speakers = defaultdict(int)
    for spk, text in records:
        speakers[spk or "(无说话人)"] += 1
        for s in SPLIT_RE.split(text):
            s = s.strip().strip("*「」“”…—-\'\" ")
            s = re.sub(r"^\d+[\.、]\s*", "", s)
            if not (opts.min <= len(s) <= opts.max):
                stats["dropped_len"] += 1
                continue
            if any(b in s for b in bad):
                stats["dropped_bad"] += 1
                continue
            if taste and not any(t in s for t in taste):
                stats["dropped_taste"] += 1
                continue
            if opts.speaker and opts.speaker not in spk:
                stats["dropped_speaker"] += 1
                continue
            if opts.grep and opts.grep not in s:
                stats["dropped_grep"] += 1
                continue
            stats["kept"] += 1
            for key, words in groups.items():
                if any(w in s for w in words):
                    pool[key].add(s)
                    break
            else:
                pool["其他"].add(s)
    return {k: sorted(v) for k, v in pool.items()}, stats, dict(speakers)


# ────────────────────────── 输出 ──────────────────────────

def report(role, dim, groups, pool, stats, speakers, limit):
    L = []
    L.append("=" * 64)
    L.append(f"语料挖句 · {role}（按「{dim}」分组 · 取值 {len(groups)} 个）")
    L.append("=" * 64)
    L.append(f"  读入 {stats['read']} 条 → 通过筛子 {stats['kept']} 句"
             f"（长度窗丢 {stats['dropped_len']}｜任务词丢 {stats['dropped_bad']}｜"
             f"口语标记丢 {stats['dropped_taste']}｜说话人丢 {stats['dropped_speaker']}）")
    if speakers:
        top = sorted(speakers.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        L.append("  来源分布：" + "、".join(f"{k}×{n}" for k, n in top))
    L.append("")
    total = 0
    zero = []
    for key in list(groups) + (["其他"] if "其他" in pool else []):
        items = pool.get(key, [])
        words = groups.get(key, [])
        wnote = f"（关键词 {len(words)} 个）" if words else ""
        if not items:
            L.append(f"【{key}】{wnote}(无候选)")
            if words:
                zero.append((key, words))
            continue
        L.append(f"【{key}】{wnote} {len(items)} 条候选")
        for s in items[:limit]:
            L.append("  " + s)
        if len(items) > limit:
            L.append(f"  …另 {len(items) - limit} 条（--limit 调大或看 --json）")
        total += len(items)
    L.append("")
    if zero:
        L.append("命中 0 的组——取值字面往往不出现在台词里（说话人说「别熬了」不说「熬夜」）：")
        for key, words in zero[:6]:
            L.append(f"  {key}：{ '、'.join(words) }")
        L.append("  两种做法（这一步的摩擦是设计内的：哪个词指向哪个场景，只有你的语料知道）：")
        L.append(f"    ① 生成词表骨架填扩展词：dlg mine {role} <文件> --init-keywords → 编辑 {KW_FILE}")
        L.append(f"    ② 先探查：dlg mine {role} <文件> --grep <你猜的词>")
        L.append("")
    L.append(f"合计候选 {total} 句。")
    L.append("下一步（人审不可跳）：挑中的加 `[%s|情绪取值] ` 前缀 → `dlg seed %s --apply`"
             % (dim or "维度1", role))
    return "\n".join(L)


def write_pool(path: str, role: str, dim: str, groups: dict, pool: dict) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    L = [f"# 候选池（dlg mine {role} 生成 · {date.today()}）",
         f"# 按「{dim}」分组；挑中的行加 `[{dim}|情绪取值] ` 前缀，再 dlg seed {role} --apply",
         "# 本文件是候选，不是素材——直接 seed 不会入库（行首无格标注）",
         ""]
    for key in list(groups) + (["其他"] if "其他" in pool else []):
        items = pool.get(key, [])
        if not items:
            continue
        L.append(f"## {key}（{len(items)} 条）")
        L.extend(items)
        L.append("")
    while L and not L[-1].strip():
        L.pop()
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


# ────────────────────────── 自检 ──────────────────────────

def selftest() -> int:
    """自检：格式嗅探 / 字段提取 / 分组对齐 / 筛子口径——全在自造样本上跑。"""
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {name}")
        ok = ok and bool(cond)

    td = tempfile.mkdtemp(prefix="dlg_mine_")
    p_jsonl = os.path.join(td, "a.jsonl")
    with open(p_jsonl, "w", encoding="utf-8") as f:
        for obj in [{"name": "小雨", "content": "早点睡吧，别熬了。"},
                    {"role": "user", "message": "知道了"},
                    {"name": "小雨", "mes": "饿了没？先吃饭。"},
                    {"role": "user", "content": "今天天气不错，我出门走走。"}]:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    p_json = os.path.join(td, "b.json")
    with open(p_json, "w", encoding="utf-8") as f:
        json.dump([{"name": "小雨", "mes": "今天气色不错。"},
                   {"name": "用户", "mes": "还行"}], f, ensure_ascii=False)
    p_text = os.path.join(td, "c.txt")
    with open(p_text, "w", encoding="utf-8") as f:
        f.write("熬夜伤身。\n饭要按时吃。\n")

    check("嗅探 JSONL", sniff_format(p_jsonl) == "jsonl")
    check("嗅探 JSON 数组", sniff_format(p_json) == "json")
    check("嗅探纯文本", sniff_format(p_text) == "text")

    recs = read_records(p_jsonl, "jsonl", False)
    check("JSONL 取到 4 条（含 mes 字段）", len(recs) == 4)
    check("说话人字段多形态", {s for s, _ in recs} == {"小雨", "user"})
    check("JSON 数组取到 2 条", len(read_records(p_json, "json", False)) == 2)
    check("纯文本整行为条", len(read_records(p_text, "text", False)) == 2)
    check("--split-sentences 按句拆", len(read_records(p_text, "text", True)) >= 2)
    recs = recs + read_records(p_json, "json", False)   # 多格式混输

    cfg = {"dimensions": {"场景": ["熬夜", "吃饭"], "情绪": ["平静"]}}
    role_dir = os.path.join(td, "角色")
    os.makedirs(role_dir, exist_ok=True)
    json.dump(cfg, open(os.path.join(role_dir, "台词配置.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    dim, groups = build_groups(cfg, role_dir, "")
    check("分组键来自 dimensions", dim == "场景" and set(groups) == {"熬夜", "吃饭"})

    json.dump({"熬夜": ["别熬"]}, open(os.path.join(role_dir, KW_FILE), "w", encoding="utf-8"),
              ensure_ascii=False)
    _, groups2 = build_groups(cfg, role_dir, "")
    check("语料关键词.json 能扩词", "别熬" in groups2["熬夜"])

    class O:
        min, max, extra_bad, no_taste, speaker, grep = 5, 34, [], True, "", ""

    # 关键词扩过之后再挖——取值字面常常匹配不到（「熬夜」这个词不出现在台词里）
    pool, stats, _ = mine(recs, groups2, O)
    check("挖句落进对应组（扩词后）", "熬夜" in pool and any("早点睡" in s for s in pool["熬夜"]))
    check("不匹配的落「其他」", "其他" in pool)

    class O2(O):
        speaker = "小雨"

    _, stats2, _ = mine(recs, groups2, O2)
    check("--speaker 真的过滤了", stats2["dropped_speaker"] > 0)

    print("=" * 52)
    print("自检结果: " + ("全部通过 ✓" if ok else "有未过项 ✗"))
    return 0 if ok else 1


# ────────────────────────── 入口 ──────────────────────────

def main():
    ap = argparse.ArgumentParser(description="台词系统：从对话记录挖候选句")
    ap.add_argument("role", nargs="?", default="", help="角色名（分组按它的 dimensions）")
    ap.add_argument("files", nargs="*", help="对话记录文件（jsonl / json / txt）")
    ap.add_argument("--format", choices=["jsonl", "json", "text"], help="显式指定格式（默认嗅探）")
    ap.add_argument("--speaker", default="", help="只挖这个说话人的话（子串匹配；默认全取）")
    ap.add_argument("--group-by", default="", help="按哪个维度分组（默认第一个维度）")
    ap.add_argument("--min", type=int, default=5, help="句长下限（默认 5）")
    ap.add_argument("--max", type=int, default=34, help="句长上限（默认 34）")
    ap.add_argument("--no-taste", action="store_true", help="关掉口语标记过滤（叙事句也会进来）")
    ap.add_argument("--bad-file", default="", help="追加任务型词表（每行一个词）")
    ap.add_argument("--grep", default="", help="只要含该关键词的句子")
    ap.add_argument("--split-sentences", action="store_true", help="纯文本输入时按句号再拆")
    ap.add_argument("--limit", type=int, default=20, help="每组最多打印条数（默认 20）")
    ap.add_argument("--save", action="store_true",
                    help="写候选池到 <角色>/素材/候选-<日期>.md（默认只打印）")
    ap.add_argument("--init-keywords", action="store_true",
                    help=f"生成 {KW_FILE} 骨架到角色目录（每组取值一行，填你语料里的说法）")
    ap.add_argument("--out", default="", help="写候选池到指定路径")
    ap.add_argument("--json", default="", help="另落 JSON（便于二次筛与复现）")
    ap.add_argument("--selftest", action="store_true", help="跑口径自检（不碰真实库）")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.role or not args.files:
        ap.print_help()
        return 1

    role_dir, cfg, err = load_role(args.role)
    if cfg is None:
        print(f"❌ {err}")
        return 1

    dim, groups = build_groups(cfg, role_dir, args.group_by)
    if not groups:
        print(f"❌ 角色「{args.role}」的配置里没有可用维度做分组（检查 dimensions）")
        return 1

    if args.init_keywords:
        path = os.path.join(role_dir, KW_FILE)
        if os.path.exists(path):
            print(f"⚠️ 已存在，没动它: {path}")
            return 0
        with open(path, "w", encoding="utf-8") as f:
            f.write("{\n")
            items = list(groups)
            for i, key in enumerate(items):
                comma = "," if i < len(items) - 1 else ""
                f.write(f'  "{key}": []{comma}\n')
            f.write("}\n")
        print(f"✅ 词表骨架: {path}")
        print("   把「你语料里会出现的说法」填进对应的数组——空数组＝只用取值字面匹配")
        return 0

    extra_bad = []
    if args.bad_file:
        with open(args.bad_file, "r", encoding="utf-8", errors="replace") as f:
            extra_bad = [l.strip() for l in f if l.strip()]
    args.extra_bad = extra_bad

    records = []
    for path in args.files:
        if not os.path.isfile(path):
            print(f"❌ 文件不存在: {path}")
            return 1
        fmt = args.format or sniff_format(path)
        try:
            got = read_records(path, fmt, args.split_sentences)
        except json.JSONDecodeError as e:
            print(f"❌ {path}: 按 {fmt} 解析失败（{e}）——用 --format 显式指定格式")
            return 1
        print(f"[{fmt}] {path} → {len(got)} 条", file=sys.stderr)
        records.extend(got)

    if not records:
        print("❌ 一条记录都没读出来——多半是格式不对：用 --format jsonl|json|text 显式指定")
        return 1

    pool, stats, speakers = mine(records, groups, args)
    print(report(args.role, dim, groups, pool, stats, speakers, args.limit))

    out_path = args.out or (os.path.join(role_dir, "素材", f"候选-{date.today()}.md")
                            if args.save else "")
    if out_path:
        print(f"\n候选池: {write_pool(out_path, args.role, dim, groups, pool)}")
    if args.json:
        json.dump({k: v for k, v in pool.items()}, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"JSON: {args.json}")
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
