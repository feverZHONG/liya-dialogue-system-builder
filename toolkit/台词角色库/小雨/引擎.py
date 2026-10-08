#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 06_生成引擎.py 生成。改台词请改配置后重新生成，勿手改本文件。

状态层：冷却窗（同句短时不重复）＋ 上下文沿用（没给的维度记得上次的值）。改行为请改配置重生成。
"""

import random

_DIM_ORDER = ['场景', '情绪']
_LINE_LIB = {('问候', '平静'): ['来了。今天没什么大事，本子空着一页。', '嗯，你来了。', '早。外面还那样，不耽误你。'], ('问候', '开心'): ['哟，心情不错？记进本子了。', '这一笔是彩色的，你赚到了。', '什么事这么乐？说来听听。'], ('问候', '疲惫'): ['回来了。先说好，今天的活到这儿为止。', '先坐。', '累成这样还打招呼？先歇。'], ('问候', '烦躁'): ['脸色不太好看。谁惹的？', '别急着说事。', '进门就带火气，本子都不敢翻页。'], ('工作', '平静'): ['慢慢来，这活儿急不死人。', '按你的节奏走，我记着进度。', '干你的。'], ('工作', '开心'): ['顺了？这一条得记上。', '行啊你，这波漂亮。', '看你干得起劲——顺不顺？'], ('工作', '疲惫'): ['又肝到这会儿？歇口气，命比工时长。', '这活儿今天干不完，明天也还在。', '手都抬不直了还敲？停。'], ('工作', '烦躁'): ['卡了？先骂三声，再调。', '这东西要是能听懂人话，早该道歉了。', '别砸东西。砸了还得扫。'], ('熬夜', '平静'): ['还不睡？本子都打了三个哈欠。', '夜是给自己留的，别全给活。', '灯还亮着。要陪吗？'], ('熬夜', '开心'): ['这个点还这么精神，你是真不困啊。', '今晚算你的。', '笑成这样，是想到什么好事了？'], ('熬夜', '疲惫'): ['啧，又熬夜，你是嫌天亮得太早？', '行，我陪着。天塌下来先记一笔。', '去睡。'], ('熬夜', '烦躁'): ['越晚越躁，这活儿是跟你耗上了。', '别硬扛。明天脑子清楚了更好办。', '深夜的脾气不算数，睡醒再定。'], ('吃饭', '平静'): ['到点了啊。饭不等人。', '饿不饿？先吃。', '先吃，事回头说。'], ('吃饭', '开心'): ['吃上了？我批准。', '记得吃——不然半夜又来找我要零食。', '看你吃得香，我就放心了。'], ('吃饭', '疲惫'): ['累到这个点才吃？先吃，别说话。', '随便垫两口也比空着强。', '别撑。'], ('吃饭', '烦躁'): ['气归气，饭得吃。', '别拿胃出气。', '先吃。什么火气都等吃完再说。'], ('道别', '平静'): ['走了？本子给你留了页。', '行，去吧。别走丢了。', '路上小心。'], ('道别', '开心'): ['这就走？好事记得回来说。', '去吧去吧，晚点见。', '看你走得这么轻快——去玩？'], ('道别', '疲惫'): ['回去吧，今天够累了。', '别送。', '到了说一声。'], ('道别', '烦躁'): ['走走走，别在这儿耗着。', '出门透口气也好。', '路上慢点，气顺了再回来。'], ('被夸', '平静'): ['夸我？记下了，别后悔。', '嗯，这话我收着。', '算你有眼光。'], ('被夸', '开心'): ['今天嘴这么甜？有求于我？', '哟，这话我爱听。', '再来一句？我还没听够。'], ('被夸', '疲惫'): ['别夸了，我快睡着了。', '谢了。今天真没力气得意。', '嗯，收下。你也歇歇。'], ('被夸', '烦躁'): ['别拍马屁，说正事。', '这会儿夸我也没用。', '省省，我知道自己什么样。']}
_TEMPLATES = ['{对象}，{事件}了？行，我看着呢。', '哦？{对象}这边{事件}——本子记上了，翻不了案。', '有个{事件}的消息，{对象}自己掂量，我不救场。']
_VARS = {'对象': ['你', '同事'], '事件': ['无', '成功', '失败']}
_COOLDOWN = 2

_seen = {}       # 变体使用计数：保证长期均衡
_recent = []       # 最近用过的台词：冷却窗（跨格生效）
_last_ctx = {}    # 上一次的上下文：没给的维度沿用


def reset():
    """清空状态（新会话／新场景开始时调）。"""
    _recent.clear()
    _seen.clear()
    _last_ctx.clear()


def _resolve(context):
    """补全上下文：这次没给的维度沿用上一次的值（状态连续感）。"""
    merged = dict(_last_ctx)
    for k, v in (context or {}).items():
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
    """根据触发上下文返回一句台词。context: {维度名: 值, ...}

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
        filled = {}
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
        print(f"  {ctx} -> {reply(ctx)}")
    if _TEMPLATES:
        print("=== 模板兜底演示 ===")
        ctx = {d: "未命中" for d in _DIM_ORDER}
        for v in _VARS:
            ctx[v] = list(_VARS[v])[0]
        print(f"  {ctx} -> {reply(ctx)}")
