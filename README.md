# 台词系统脚手架 · Dialogue System Builder

> 要让一个角色**在该说话的时候说该说的话**——桌宠的应答、角色卡的开场与示例对话、语音助手的响应文案、游戏 NPC 的触发表？
> 这个 skill 管两件事：**怎么画格子**（触发维度怎么设），以及**怎么把格子跑成一条流水线**（同仓 `toolkit/` 里是一条能跑的 CLI：画格子 → 质量闸 → 生成引擎 → 验覆盖率 → 跑批 → 看日志迭代）。

## 核心命题（先记住这一条）

**适配广度 = 触发维度覆盖，不是台词条数。**

实测（`scripts/verify_thesis.py`，固定种子）：同一文字量 100 条——无结构堆砌只盖住 55/180 组合（30.6%），结构化格子盖住 100/180（55.6%）；模板+变量 30 条即打满 180 格（100%）。2 万次随机触发命中率：堆砌 14.1% / 格子 16.5% / 模板+变量 100%。

**推论**：条数买的是「多久重复一次」（密度），维度买的是「能应答多少种情形」（广度）——**先覆盖，后密度**。

## 什么时候用

| 需求 | 走哪条 |
|:--|:--|
| 要给角色做一套「按情境触发」的台词库 | 本仓：画格子 → 填台词 → 验覆盖率 → 跑批迭代 |
| 已经有一堆台词，但总在重复、答不到点上 | 先看上面那条命题——多半是格子画少了，不是台词不够 |
| 库铺开了，读起来还是「那几句话」 | `dlg rhythm` 量句式节奏（长度分布/行首/签名/同格相邻），再按警线加密 |
| 要落到桌宠 / 角色卡 / 语音助手 | 读 `references/adaptation-notes.md`：触发信号、台词去向映射、素材分层、空库分配法；角色卡方向有现成工具 `dlg export` |
| 想要的是「能连续对话、有记忆」的角色 | 那是角色卡的事（见姊妹仓 `sillytavern-cards`），台词系统只解决「该说什么」 |

## 产出是什么

- **给得了**：`台词配置.json`（维度 + 格子 + 模板，可再改再生成）、零依赖 `引擎.py`（`reply(context)` 永不抛异常）、覆盖率报告（理论段 + 运行日志驱动的实测段）、一条 17 子命令的工作台 CLI
- **给不了**：不会替你写台词——素材得来自角色真实说过的话（**原句优先**）；不做自然语言理解，一切由结构化触发驱动

## 配方（五步）

1. **确认触发维度** —— 典型：场景、情绪、对象、事件、时段、天气。默认 2~4 个维度、每个 2~5 个取值（再细就组合爆炸）
2. **画格子** —— 维度取值做笛卡尔积；格子里只放「必须区分」的维度，其余一律降为模板变量
3. **填台词与模板** —— 每格 2~3 条变体（冷门格 1 条）；至少 2~3 条兜底模板，保证未覆盖组合也有话说
4. **生成引擎** —— 格子命中 → 变体轮换取最少使用的那条；未命中 → 模板兜底 + 变量注入
5. **验证覆盖率** —— 兜底后覆盖率应达 100%；未达就补模板或补格子

**素材分层（顺序不可颠倒）**：角色真实说过的原句 ＞ 轻编的衔接/动作 ＞ 模板兜底。硬规则（口癖、句式上限、禁用词）是**校验项**，不是触发维度——外置，别混进格子。

## 工作台（同仓 `toolkit/`）

一条 CLI 走完全程，19 个子命令，零第三方依赖、Python 3.8+：

```bash
dlg new <角色>                          # 建脚手架（空格子 + 通用模板）
dlg grid "场景:问候,工作;情绪:平静"       # 画格子预览（纯维度，不需要角色）
dlg check|dup|rule|stock <角色>          # 质量闸：校验 / 查重 / 硬规则 / 空库盘点
dlg gen|cover <角色>                     # 生成引擎 / 覆盖率报告
dlg run <角色> --batch 10                # 跑起来（也支持 --interactive / --input / --stdin）
dlg log <角色>                           # 日志 → 兜底占比 / 高频格子 / 迭代建议
dlg rhythm <角色>                        # 句式节奏体检（加密前必跑）
dlg fill <角色> [--apply]                # 日志 → 补哪一格（三张清单，可生成脚手架）
dlg export <角色> --out 卡.json           # 台词库 → 酒馆角色卡 V2 初稿（待精修处标占位）
dlg audit / dlg selftest                 # 一键体检 / 回归自检
```

自带一个可直接跑的示例角色（24 格 72 条，`dlg audit` 5/5 全过）。装薄壳、角色库位置（`DLG_ROLE_ROOT`）、配置格式、引擎接入协议 → **`toolkit/README.md`**。

## 怎么拿到

```bash
git clone https://github.com/feverZHONG/liya-dialogue-system-builder.git <你的数据根>/skills/dialogue-system-builder
```

## 边界

- 只管**文字**：不接桌宠工程、角色卡格式、TTS、聊天机器人接口——那些方向的接法在 `references/adaptation-notes.md` 里给了答案
- 不做自然语言理解，台词由结构化触发驱动
- 起步库每格 2~3 条属设计内；「加密」（同格补到 8~10 条）是第二阶段，`dlg rhythm` 的完整警线到那时才对齐

## 许可

- `scripts/`、`toolkit/` 下的代码：**MIT**（全文见 `LICENSE`）
- 文档（`SKILL.md`、`references/`、`toolkit/README.md`、本 README 正文）：**CC BY 4.0**（全文见 `LICENSE-DOCS`）

## 姊妹仓库

- [liya-subtraction-skill](https://github.com/feverZHONG/liya-subtraction-skill) —— 技能库做减法：冗余检测 / 拆薄 / 合并 / 归档判断
- [liya-persona-authoring](https://github.com/feverZHONG/liya-persona-authoring) —— 给 AI agent 写身份文件（SOUL.md 类）：创作流程 / 砍装饰留行为 / 减法与漂移对照
- [liya-sillytavern-cards](https://github.com/feverZHONG/liya-sillytavern-cards) —— 酒馆角色卡写法：V2 格式 / PList+Ali:Chat / 三个 Python 工具
- [liya-sillytavern-worldbook](https://github.com/feverZHONG/liya-sillytavern-worldbook) —— 酒馆世界书（Lorebook）：触发链源码实证 + 体检 / 模拟 / 生成工具
- [liya-vision-recognition-traps](https://github.com/feverZHONG/liya-vision-recognition-traps) —— 视觉模型识图陷阱：22 条实测与对策（附真 OCR 通道、生图物理体检、两图差分）
- [liya-chat-game-referee](https://github.com/feverZHONG/liya-chat-game-referee) —— 群聊小游戏裁判：扫雷 / 五子棋 / 大话骰 / 骗子牌 / 掷骰决斗，一位裁判带六个引擎
- [liya-spy-game](https://github.com/feverZHONG/liya-spy-game) —— 谁是卧底：黑板规则 / 出题方法论 / 词库验证 / 身份分配器
- [liya-sea-turtle-soup](https://github.com/feverZHONG/liya-sea-turtle-soup) —— 海龟汤：推理方法论 + 档案流水线（turtle CLI）
- [liya-delegation-and-verification](https://github.com/feverZHONG/liya-delegation-and-verification) —— 委派与验收：任务书写法 / 并行隔离 / 把「自报」验成事实
- [liya-tavern-card-refinement](https://github.com/feverZHONG/liya-tavern-card-refinement) —— 酒馆角色卡精修：7 字段清单 / 槽位归位 / 6 类断言 / 可用性验收
- [liya-prose-quality-metrics](https://github.com/feverZHONG/liya-prose-quality-metrics) —— 稿子读起来「平」怎么办：先量再改（对话占比·句长σ·标点谱）＋ 7 个工具
- [liya-ruozhiba-wordbank](https://github.com/feverZHONG/liya-ruozhiba-wordbank) —— 弱智吧题防御手册：160 道逐题拆解 + 三连防御法（拆前提→指谬误→反杀）
- [liya-subtitle-proofreading](https://github.com/feverZHONG/liya-subtitle-proofreading) —— 字幕校对 / 重建 / 外挂 SRT（5 个纯标准库工具）
- [liya-corpus-line-mining](https://github.com/feverZHONG/liya-corpus-line-mining) —— 从语料 / 会话库挖可复用原句：候选池筛选 + 人审落库（零依赖）
- [liya-story-revision-plan](https://github.com/feverZHONG/liya-story-revision-plan) —— 小说全稿修订方案：评估 / 缺口清单 / 逐章大纲 / 信息融合 / 优先级
- [liya-dev-workflow](https://github.com/feverZHONG/liya-dev-workflow) —— 开发全流程方法论：环境侦查 / 计划 / spike / TDD / 调试 / 推送排障 / 同步验收
- [liya-news-verification](https://github.com/feverZHONG/liya-news-verification) —— 验证伞：轻量核查 / 交付前多源验证 / 链接危险识别 / 厂商官宣核实 / 链接考古
- [liya-knowledge-persistence](https://github.com/feverZHONG/liya-knowledge-persistence) —— 知识持久化：信息该放记忆层 / 文件 / 技能库的分层规范
- [liya-incident-review](https://github.com/feverZHONG/liya-incident-review) —— 社群事件复盘：素材收集 → 时间线重构 → 交叉验证 → 矛盾管理（输出理解不输出建议）
- [liya-document-translation](https://github.com/feverZHONG/liya-document-translation) —— 论文与长文档翻译：提取全文 → 术语表 → 并行分章 → 质量抽查 → 归档
- [liya-source-code-investigation](https://github.com/feverZHONG/liya-source-code-investigation) —— 外部项目调查：源码审计 / 拆包分层 / 数据实测 / 身份链（结论导向，非取用）
- [liya-character-voice-simulation](https://github.com/feverZHONG/liya-character-voice-simulation) —— 角色声线推演：锚点表双向用——分队推演（隔离上下文）＋ 反查认说话人

---

*莉娅（[@feverZHONG](https://github.com/feverZHONG)）· 宇宙美好记录官*
