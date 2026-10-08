#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
14_素材提炼.py —— 台词系统 · 素材管道（半自动提炼入库）
=========================================================
素材格式约定（台词角色库/<角色>/素材/ 下任意 .txt/.md，每行一条）：
    [场景|情绪] 台词      # 带目标格标注 → 提炼时自动并入 台词配置.json
    台词                  # 无标注 → 提炼时列出待人工归类

流程：
    1. 扫描素材文件，解析标注（格 key 必须匹配配置的维度取值）
    2. 报告：已标注 M 条（可自动入库）/ 未标注 K 条（待归类）/ 无效 X 条
    3. --apply：已标注的并入配置（对应格去重追加；格不存在则跳过并警告），
       修改前自动备份 台词配置.json → 台词配置.json.bak

用法：
    python3 14_素材提炼.py 小雨             # 只报告，不改配置
    python3 14_素材提炼.py 小雨 --apply     # 自动并入已标注台词
"""

import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
ROLE_ROOT = os.environ.get("DLG_ROLE_ROOT") or os.path.join(PROJECT_ROOT, "台词角色库")

TAG_RE = re.compile(r"^\[([^\]]+)\]\s*(.+)$")


def load_cfg(role_dir):
    cfg_path = os.path.join(role_dir, "台词配置.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f), cfg_path


def valid_key(key: str, cfg) -> str:
    """校验标注格 key（如 问候|平静），合法返回规范化 key，否则 None"""
    dims = list(cfg.get("dimensions", {}))
    parts = [p.strip() for p in key.split("|")]
    if len(parts) != len(dims):
        return None
    for d, v in zip(dims, parts):
        if v not in cfg["dimensions"].get(d, []):
            return None
    return "|".join(parts)


def main():
    ap = argparse.ArgumentParser(description="台词系统：素材提炼")
    ap.add_argument("role", help="角色名")
    ap.add_argument("--apply", action="store_true", help="把已标注台词并入配置")
    args = ap.parse_args()

    role = os.path.join(ROLE_ROOT, args.role)
    if not os.path.isdir(role):
        print(f"❌ 角色不存在: {args.role}（先 dlg new {args.role}）")
        sys.exit(1)

    cfg, cfg_path = load_cfg(role)
    dims = list(cfg.get("dimensions", {}))
    material_dir = os.path.join(role, "素材")
    if not os.path.isdir(material_dir):
        print(f"❌ 素材目录不存在: {material_dir}")
        sys.exit(1)

    files = [f for f in sorted(os.listdir(material_dir))
             if f.lower().endswith((".txt", ".md"))]
    if not files:
        print("素材目录为空。把台词原句放进 素材/*.txt，每行一条：")
        print("  [场景|情绪] 台词     带标注 → 可自动入库")
        print("  台词                 无标注 → 待人工归类")
        sys.exit(0)

    tagged, bare, invalid = [], [], []
    for fn in files:
        with open(os.path.join(material_dir, fn), "r", encoding="utf-8") as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = TAG_RE.match(line)
                if not m:
                    bare.append((fn, ln, line))
                    continue
                key = valid_key(m.group(1).strip(), cfg)
                if key is None:
                    invalid.append((fn, ln, m.group(1).strip(), m.group(2).strip()))
                else:
                    tagged.append((fn, ln, key, m.group(2).strip()))

    print("=" * 60)
    print(f"素材提炼 · {args.role}（维度: {' | '.join(dims)}）")
    print("=" * 60)
    print(f"  素材文件 : {len(files)} 个")
    print(f"  已标注   : {len(tagged)} 条 → 可自动入库")
    print(f"  未标注   : {len(bare)} 条 → 待人工归类")
    print(f"  无效标注 : {len(invalid)} 条 → 格 key 与维度不匹配")
    if tagged:
        print("-" * 60)
        print("已标注预览（--apply 后并入配置）:")
        for fn, ln, key, text in tagged[:10]:
            print(f"  [{key}] {text}")
        if len(tagged) > 10:
            print(f"  ... 还有 {len(tagged) - 10} 条")
    if bare:
        print("-" * 60)
        print("未标注（需人工补 [格key] 前缀或直接改配置）:")
        for fn, ln, text in bare[:10]:
            print(f"  {text}")
        if len(bare) > 10:
            print(f"  ... 还有 {len(bare) - 10} 条")
    if invalid:
        print("-" * 60)
        print("无效标注:")
        for fn, ln, tag, text in invalid[:10]:
            print(f"  [{tag}] {text}")
    print("=" * 60)

    if not args.apply:
        print(f"（未修改配置。确认后加 --apply 自动并入已标注台词）")
        return

    # --apply：已标注的并入配置（备份 + 去重）
    import shutil
    shutil.copy2(cfg_path, cfg_path + ".bak")
    line_lib = cfg.setdefault("line_lib", {})
    added = 0
    for fn, ln, key, text in tagged:
        cell = line_lib.setdefault(key, [])
        if text in cell:
            continue
        cell.append(text)
        added += 1
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"✅ 已并入 {added} 条（去重后），配置备份: {cfg_path}.bak")
    print(f"   下一步: dlg check {args.role} → dlg gen {args.role} → dlg cover {args.role}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        try:
            if sys.stdin.isatty():  # 仅交互终端才等待；管道/脚本调用直接退出
                input("\n按回车键退出...")
        except EOFError:
            pass
