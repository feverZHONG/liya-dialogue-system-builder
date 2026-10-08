#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
19_卡导出.py —— 台词系统 · 导出到酒馆角色卡（V2）
=====================================================
把台词库变成一张 SillyTavern 能用**卡初稿**：台词填得进去的字段全填，其余留占位给人精修。

字段映射（口径见 SKILL.md「方向适配」／references/adaptation-notes.md）：

| 卡字段 | 来源 |
|:--|:--|
| `description` | 场景块 `[Genre: …; Tags: …; Scenario: …]` ＋ `<START>` 示例（开场类格子） |
| `first_mes` | 开场格台词 ＋ 动作描写占位（规格：`*动作*` ＋ 登场 ＋ 钩子，**别替用户行动**） |
| `mes_example` | `<START>` 分组的示例对话（`{{char}}` 行已填，`{{user}}` 行留占位） |
| `system_prompt` | `硬规则.json` → 约束句（长度上限／必须包含／禁用词） |
| `tags` | 维度取值 ＋ `--tags` |
| `personality`／`scenario` | 留空（酒馆规格：内容进 PList／Ali:Chat，不塞这两个） |
| `extensions.depth_prompt` | **占位**——PList 是角色设定活，台词库给不出（风格素材在报告里给参考） |

用法：
    python3 19_卡导出.py 小雨                       # 只出报告
    python3 19_卡导出.py 小雨 --out 小雨卡.json      # 写卡初稿（本机有 validator 时自动跑校验）
    python3 19_卡导出.py 小雨 --out 卡.json --genre 日常 --tags 陪伴,记录
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os
import subprocess
import sys
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)          # toolkit/
SKILL_ROOT = os.path.dirname(PROJECT_ROOT)     # dialogue-system-builder/
SKILLS_ROOT = os.path.dirname(SKILL_ROOT)      # skills/
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

PLACEHOLDER = "【需补充】{}"   # 前缀用酒馆 validator 认得的标记——占位就该被 --deep 点出来
DEFAULT_MAX_EXAMPLES = 6


def read_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_role(role):
    """→ (角色目录, 角色名, 配置, 硬规则, 错误)"""
    if os.path.isfile(role):
        role_dir = os.path.dirname(os.path.abspath(role))
        role = os.path.basename(role_dir)
    else:
        role_dir = os.path.join(ROLE_ROOT, role)
    cfg = read_json(os.path.join(role_dir, "台词配置.json"))
    if cfg is None:
        return role_dir, role, None, None, f"找不到角色配置: {os.path.join(role_dir, '台词配置.json')}"
    rule = read_json(os.path.join(role_dir, "硬规则.json"), {}) or {}
    return role_dir, role, cfg, rule, None


def opener_cell(cfg):
    """挑开场格：优先「场景＝问候」那一档，否则第一个维度第一个取值"""
    dims = cfg.get("dimensions", {})
    for dim, values in dims.items():
        if "问候" in values:
            return dim, "问候"
    first_dim = next(iter(dims), None)
    if not first_dim:
        return None, None
    return first_dim, dims[first_dim][0]


def build_scene_block(cfg, genre, extra_tags):
    dims = cfg.get("dimensions", {})
    tag_pool = []
    for values in dims.values():
        tag_pool.extend(str(v) for v in values)
    tags = list(dict.fromkeys(tag_pool + extra_tags))   # 维度取值在前，--tags 补后
    scenario = "；".join(f"{k}={ '/'.join(str(v) for v in vals)}" for k, vals in dims.items())
    inner = "; ".join(filter(None, [
        f"Genre: {genre}" if genre else "",
        f"Tags: {', '.join(tags)}" if tags else "",
        f"Scenario: {scenario}" if scenario else "",
    ]))
    return f"[{inner}]", tags


def build_system_prompt(rule, name):
    lines = []
    limit = rule.get("长度上限")
    if isinstance(limit, int) and limit > 0:
        lines.append(f"每句话不超过 {limit} 个字。")
    must = [w for w in (rule.get("必须包含") or []) if str(w).strip()]
    if must:
        lines.append("每句话都要带上：" + "、".join(str(w) for w in must) + "。")
    banned = [w for w in (rule.get("禁用词") or []) if str(w).strip()]
    if banned:
        lines.append("不许说：" + "、".join(str(w) for w in banned) + "。")
    if not lines:
        return ""
    return "{{original}}\n你是" + name + "——\n" + "\n".join(lines)


def example_groups(cfg, opener, per_cell, max_groups):
    """→ [(格key, [台词...]), ...]：开场格之外的格子，按格取样"""
    dims = list(cfg.get("dimensions", {}).keys())
    lib = cfg.get("line_lib", {}) or {}
    op_key = "|".join(str(opener[1]) if d == opener[0] else "?" for d in dims) if opener[0] else None
    groups = []
    for key in sorted(lib):
        if op_key and key.split("|")[0] == str(opener[1]):
            continue          # 开场格已用在 description 里
        lines = [l for l in lib[key] if str(l).strip()][:per_cell]
        if lines:
            groups.append((key, lines))
    return groups[:max_groups]


def build_description(scene_block, opener_lines, opener_name):
    parts = [scene_block, ""]
    for line in opener_lines:
        parts.append("<START>")
        parts.append("{{user}}: " + PLACEHOLDER.format(f"一句把话题引到「{opener_name}」的用户话"))
        parts.append("{{char}}: " + line)
        parts.append("")
    return "\n".join(parts).strip()


def build_mes_example(groups):
    parts = []
    for key, lines in groups:
        scene = key.replace("|", "·")
        for line in lines:
            parts.append("<START>")
            parts.append("{{user}}: " + PLACEHOLDER.format(f"一句引到「{scene}」的用户话"))
            parts.append("{{char}}: " + line)
    return "\n".join(parts)


def build_card(role, cfg, rule, genre, extra_tags, per_cell, max_examples) -> tuple:
    opener = opener_cell(cfg)
    op_dim, op_val = opener
    lib = cfg.get("line_lib", {}) or {}
    op_lines = []
    if op_dim:
        for key in sorted(lib):
            if key.split("|")[0] == str(op_val):
                op_lines.extend([l for l in lib[key] if str(l).strip()][:per_cell])
    op_lines = op_lines[:per_cell]

    scene_block, tags = build_scene_block(cfg, genre, extra_tags)
    description = build_description(scene_block, op_lines, op_val or "开场")
    first_mes = ("*" + PLACEHOLDER.format("一段动作描写——登场姿态，别替用户行动") + "*\n"
                 + "「" + (op_lines[0] if op_lines else PLACEHOLDER.format("开场台词")) + "」")
    mes_example = build_mes_example(example_groups(cfg, opener, per_cell, max_examples))
    system_prompt = build_system_prompt(rule, role)
    post_hist = ("{{original}}\n对话节奏：一次只回应一小句" +
                 ("，不超过 %s 字" % rule["长度上限"] if isinstance(rule.get("长度上限"), int) else "") +
                 "；不解释、不说教、不留长段落。")
    notes = (f"由台词系统 dlg export 从「{role}」的台词库导出（{date.today()}）。"
             f"格子 {len(lib)} 个 / 台词 {sum(len(v) for v in lib.values())} 条。"
             "**待精修**：first_mes 的动作描写、<START> 里的 {{user}} 行、depth_prompt 的 PList（角色设定活）。")
    data = {
        "name": role,
        "description": description,
        "personality": "",          # 酒馆规格：内容进 PList／Ali:Chat，不塞这两个
        "scenario": "",
        "first_mes": first_mes,
        "mes_example": mes_example,
        "creator_notes": notes,
        "system_prompt": system_prompt,
        "post_history_instructions": post_hist,
        "alternate_greetings": [],
        "tags": tags,
        "creator": "莉娅",
        "character_version": "0.1",
        "extensions": {
            "talkativeness": 0.5,
            "depth_prompt": {
                "prompt": PLACEHOLDER.format("PList：角色性格/身体/设定标签，≤16 字×N——台词库给不出，见报告"),
                "depth": 4,
                "role": "system",
            },
        },
    }
    card = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "name": data["name"],
        "description": data["description"],
        "personality": data["personality"],
        "scenario": data["scenario"],
        "first_mes": data["first_mes"],
        "mes_example": data["mes_example"],
        "data": data,
    }
    return card, dict(opener=opener, op_lines=op_lines, groups=example_groups(cfg, opener, per_cell, max_examples))


def find_validator():
    """sillytavern-cards 的官方 validator 翻译——本机有就跑，没有就跳过（不是本仓依赖）"""
    cand = os.path.join(SKILLS_ROOT, "sillytavern-cards", "scripts", "validate_tavern_card.py")
    return cand if os.path.isfile(cand) else ""


def report(role, cfg, card, info, out_path):
    data = card["data"]
    lib = cfg.get("line_lib", {}) or {}
    L = []
    L.append("=" * 64)
    L.append(f"角色卡导出 · {role}（格子 {len(lib)} / 台词 {sum(len(v) for v in lib.values())} 条）")
    L.append("=" * 64)
    L.append("")
    L.append("【已填】台词库能直接给的字段")
    L.append(f"  description  : 场景块 ＋ {len(info['op_lines'])} 条 <START> 开场示例")
    L.append(f"  first_mes    : 开场格台词（{len(info['op_lines'])} 条取第一）")
    L.append(f"  mes_example  : {len(info['groups'])} 组 <START> 示例（{{{{char}}}} 已填、{{{{user}}}} 留占位）")
    L.append(f"  system_prompt: {'已由硬规则生成' if data['system_prompt'] else '空（硬规则.json 没写东西）'}")
    L.append(f"  tags         : {', '.join(data['tags']) or '（无）'}")
    L.append("")
    L.append("【留占位】要人写的活（都标【需补充】——validator --deep 会把它们逐条点出来）")
    L.append("  first_mes 的 *动作描写*、<START> 里的 {{user}} 行、depth_prompt 的 PList")
    L.append("")
    L.append("【风格素材】（写 PList 标签时用得上的参考，从台词库实测）")
    all_lines = [l for v in lib.values() for l in v if str(l).strip()]
    if all_lines:
        heads = {}
        for l in all_lines:
            heads[l[:2]] = heads.get(l[:2], 0) + 1
        top_heads = sorted(heads.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        lens = [len(l) for l in all_lines]
        L.append(f"  台词 {len(all_lines)} 条｜均长 {sum(lens)/len(lens):.1f} 字｜最短 {min(lens)}｜最长 {max(lens)}")
        L.append("  高频开头：" + "、".join(f"{h}×{n}" for h, n in top_heads))
        L.append("  → 这些是「她说话什么形状」，PList 的 Personality 标签照它写才贴")
    L.append("")
    if out_path:
        L.append(f"卡初稿: {out_path}")
        L.append("下一步：`dlg export <角色> --out 卡.json` → 精修三处 → 用 sillytavern-cards 的")
        L.append("        validate_tavern_card.py 卡.json --deep 验收")
    else:
        L.append("（只出报告。加 --out 卡.json 写卡初稿）")
    return "\n".join(L)


def selftest() -> int:
    """自检：卡字段口径咬在造出来的配置上——场景块格式 / 开场格挑选 / 硬规则映射 / V2 双份同步。"""
    ok = True
    cfg = {"dimensions": {"场景": ["问候", "熬夜"], "情绪": ["平静", "烦躁"]},
           "line_lib": {"问候|平静": ["早。"], "熬夜|烦躁": ["睡。"]},
           "templates": [], "variables": {}}
    rule = {"长度上限": 20, "必须包含": ["我"], "禁用词": ["闭嘴"]}
    card, info = build_card("测试", cfg, rule, "测试genre", ["额外"], 1, 6)
    d = card["data"]

    def check(name, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {name}")
        ok = ok and bool(cond)

    check("场景块格式 [Genre; Tags; Scenario]",
          d["description"].startswith("[Genre: 测试genre; Tags: 问候, 熬夜, 平静, 烦躁, 额外; Scenario: "))
    check("开场格优先挑「问候」", info["opener"] == ("场景", "问候"))
    check("开场格不重复进 mes_example", all("问候" not in k for k, _ in info["groups"]))
    check("硬规则三条都进 system_prompt",
          all(s in d["system_prompt"] for s in ["不超过 20 个字", "都要带上：我", "不许说：闭嘴"]))
    check("V2 顶层与 data 双份同步",
          card["first_mes"] == d["first_mes"] and card["description"] == d["description"]
          and card["name"] == d["name"])
    check("personality/scenario 留空（酒馆规格）", d["personality"] == "" and d["scenario"] == "")
    check("占位用的是 validator 认得的标记",
          all("【需补充】" in d[f] for f in ("first_mes", "description", "mes_example")))
    check("depth_prompt 结构（depth=4 / role=system）",
          d["extensions"]["depth_prompt"]["depth"] == 4
          and d["extensions"]["depth_prompt"]["role"] == "system")
    print("=" * 52)
    print("自检结果: " + ("全部通过 ✓" if ok else "有未过项 ✗"))
    return 0 if ok else 1


def run_validator(path):
    val = find_validator()
    if not val:
        print("\n（本机没找到 sillytavern-cards 的 validator——跳过格式验收）")
        return 0
    print(f"\n=== 官方 validator 验收（{os.path.basename(val)}）===")
    out = subprocess.run([sys.executable, val, path, "--deep"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", stdin=subprocess.DEVNULL, timeout=120)
    print((out.stdout or "") + (out.stderr or ""))
    return out.returncode


def main():
    ap = argparse.ArgumentParser(description="台词系统：导出到酒馆角色卡（V2）")
    ap.add_argument("role", nargs="?", default="", help="角色名（或台词配置.json 路径）")
    ap.add_argument("--out", default="", help="写卡初稿 JSON 到该路径")
    ap.add_argument("--genre", default="", help="场景块的 Genre")
    ap.add_argument("--tags", default="", help="额外标签（逗号分隔），会与维度取值合并")
    ap.add_argument("--per-cell", type=int, default=1, help="每格取几条台词做示例（默认 1）")
    ap.add_argument("--max-examples", type=int, default=DEFAULT_MAX_EXAMPLES,
                    help=f"mes_example 最多几组（默认 {DEFAULT_MAX_EXAMPLES}）")
    ap.add_argument("--no-validate", action="store_true", help="不跑格式验收")
    ap.add_argument("--selftest", action="store_true", help="跑口径自检（不碰真实库）")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.role:
        ap.print_help()
        return 1

    role_dir, role, cfg, rule, err = load_role(args.role)
    if cfg is None:
        print(f"❌ {err}")
        return 1

    extra_tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    card, info = build_card(role, cfg, rule, args.genre, extra_tags, args.per_cell, args.max_examples)
    print(report(role, cfg, card, info, args.out))

    rc = 0
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
        if not args.no_validate:
            rc = run_validator(args.out)
    return rc


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
