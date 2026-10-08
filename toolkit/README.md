# 台词系统开发包

纯文字类台词系统：**触发维度 × 台词素材 → 可运行引擎 → 覆盖率验证**。
核心命题：**适配广度 = 维度覆盖，不是台词条数。**

零第三方依赖，Python 3.8+，UTF-8，SIGPIPE 管道安全。

## 结构

本工作台是 `dialogue-system-builder` skill 的执行层，与同仓的方法论配套使用：

```
dialogue-system-builder/
├── SKILL.md                    # 方法论：触发维度设计 / 画格子 / 句式节奏 / 方向适配
├── references/                 # 设计指南 · 方向适配速查
├── assets/example_config.json  # 配置示例（复制它当起点）
├── scripts/                    # 命题验证实验（可复现证据）
└── toolkit/                    # ← 本工作台
    ├── 台词系统/                # 17 个小脚本 + dlg CLI 总入口
    ├── 台词角色库/小雨/          # 示例角色（24 格全覆盖，可直接跑）
    └── README.md               # 本文件
```

## 安装

工作台不需要安装——`python3 台词系统/dlg.py <命令>` 直接能跑。

想要全局短命令 `dlg`（可选）：

```bash
python3 台词系统/16_安装.py                            # 装薄壳（默认 ~/.local/bin）
python3 台词系统/16_安装.py --bin-dir <PATH 里的目录>   # 指定薄壳目录
python3 台词系统/16_安装.py --role-root <角色库目录>    # 角色库另放一处时写进薄壳
python3 台词系统/16_安装.py --check                    # 只看环境不动手
```

重装与自检会认 PATH 里已有的 `dlg`，自动装回原位——不必每次手敲 `--bin-dir`。

## 使用（命令行）

```bash
dlg help                       # 全部子命令
dlg new 新角色                  # 新建角色脚手架
dlg grid "场景:问候,工作;情绪:平静"   # 画格子预览（纯维度，不需要角色）
dlg gen 小雨                    # 生成引擎
dlg cover 小雨                  # 覆盖率报告
dlg run 小雨 --batch 10          # 跑起来
dlg audit                      # 一键体检全部角色
dlg selftest                   # 回归自检
```

## 快速开始（新角色完整流水线）

1. `dlg new <角色名>` 建脚手架（空格子 + 2 条通用模板 + 空规则）
2. 填 `台词角色库/<角色>/台词配置.json`（格子台词 + 模板 + 变量池）
3. 质量闸：`dlg check` → `dlg dup` → `dlg rule` → `dlg stock`
4. 生成与验证：`dlg gen` → `dlg cover`（**兜底后必须 100%**）
5. 跑起来：`dlg run --batch N` / `--interactive` / `--input 文件.jsonl` / `--stdin`
6. 迭代：`dlg log` 看兜底占比与高频格子，改配置重跑
7. 收尾：`dlg audit` 一键全质量闸；`dlg rhythm` 量句式节奏（加密前必跑）

## 架构（八层，全部文字处理）

```
管理层 → 配置设计层 → 质量闸 → 生成层 → 验证层 → 运行层 → 反馈层 → 治理层
```

| 层 | 职责 | 脚本 |
| --- | --- | --- |
| 管理层 | 角色脚手架、总览、统计 | `10_新建角色`、`11_角色列表`、`12_角色统计` |
| 配置设计层 | 画格子预览、配置把关 | `01_画格子`、`02_校验配置` |
| 质量闸 | 查重、硬规则、分布诊断 | `03_查重`、`04_硬规则检查`、`05_空库盘点` |
| 生成层 | 配置 → 零依赖引擎 | `06_生成引擎` |
| 验证层 | 覆盖率/命中率/变体密度报告 | `07_验证覆盖率` |
| 运行层 | 批量/交互/文件/管道触发 + 日志 | `08_运行演示` |
| 反馈层 | 日志 → 兜底占比/高频格子/迭代建议 | `09_日志分析` |
| 治理层 | 一键体检、素材提炼、回归自检、安装部署、句式节奏 | `13`~`17` |

数据流：**信号（context dict）→ engine.reply(context) → 台词文本**；反馈层从运行日志回灌配置。

## 子命令一览

| 子命令 | 脚本 | 功能 | 用法 |
| --- | --- | --- | --- |
| `dlg new` | 10_新建角色 | 建角色脚手架 | `dlg new <角色名>` |
| `dlg list` | 11_角色列表 | 角色总览 | `dlg list` |
| `dlg stats` | 12_角色统计 | 跨角色统计 | `dlg stats` |
| `dlg grid` | 01_画格子 | 触发组合预览 | `dlg grid "场景:问候,工作;情绪:平静"` |
| `dlg check` | 02_校验配置 | 配置把关 | `dlg check 小雨` |
| `dlg dup` | 03_查重 | 台词重复检测 | `dlg dup 小雨` |
| `dlg rule` | 04_硬规则检查 | 禁用词/长度上限 | `dlg rule 小雨 [规则.json]` |
| `dlg stock` | 05_空库盘点 | 台词分布诊断 | `dlg stock 小雨` |
| `dlg gen` | 06_生成引擎 | 配置 → 引擎 | `dlg gen 小雨`（默认输出到角色目录） |
| `dlg cover` | 07_验证覆盖率 | 覆盖率报告 | `dlg cover 小雨` |
| `dlg run` | 08_运行演示 | 运行/接入 | `dlg run 小雨 --batch 10` / `--interactive` / `--input 文件.jsonl` / `--stdin` |
| `dlg log` | 09_日志分析 | 日志 → 迭代建议 | `dlg log 小雨` |
| `dlg audit` | 13_全量体检 | 一键体检 | `dlg audit [角色名...]`（缺省=全部） |
| `dlg seed` | 14_素材提炼 | 素材 → 台词 | `dlg seed 小雨 [--apply]` |
| `dlg selftest` | 15_自检 | 回归自检 | `dlg selftest` |
| `dlg install` | 16_安装 | 安装/环境自检 | `dlg install [--check] [--role-root DIR]` |
| `dlg rhythm` | 17_句式节奏 | 句式节奏体检 | `dlg rhythm 小雨 [--top 5]` |

传角色名时自动展开路径：`check/dup/stock/cover → <角色>/台词配置.json`；`gen → 配置 + 默认 -o <角色>/引擎.py`；`rule → 配置 + 默认规则`；`run → 引擎 + 默认 --log <角色>/日志/运行日志.jsonl`；`log → <角色>/日志/运行日志.jsonl`。显式路径写法同样兼容。

## 角色库位置

默认取 `台词系统/` 上一级的 `台词角色库/`（本包内即 `toolkit/台词角色库/`）。

要放别处（比如工作台随仓库走、私人角色库另置），两种写法：

- 环境变量：`export DLG_ROLE_ROOT=/path/to/台词角色库`
- 写进薄壳：`dlg install --role-root /path/to/台词角色库`（重装时自动沿用）

## 角色组织（一个角色一个文件夹）

```
台词角色库/<角色名>/
├── 台词配置.json     # 画格子/生成/验证的输入（必填）
├── 硬规则.json       # 可选：角色硬规则（dlg rule 默认用）
├── 引擎.py           # dlg gen 默认输出
├── 素材/             # 台词原句素材（dlg seed 读这里）
└── 日志/             # dlg run 默认写日志，dlg log 默认读
```

每个角色的配置/引擎/规则/日志/素材全隔离，互不污染。

## 配置格式

```json
{
  "dimensions": {"场景": ["问候", "工作", "熬夜"], "情绪": ["平静", "烦躁"]},
  "line_lib": {
    "问候|平静": ["台词一", "台词二"],
    "熬夜|烦躁": ["台词三"]
  },
  "templates": ["{对象}，{事件}了？我看着呢。"],
  "variables": {"对象": ["你"], "事件": ["无", "成功", "失败"]}
}
```

- `dimensions`：参与格子匹配的维度（顺序即匹配顺序），`line_lib` 的 key 用 `|` 按此顺序连接
- `line_lib`：格子台词，每个 key 的维度数必须与 `dimensions` 一致
- `templates`：兜底模板，未覆盖组合靠它接住；变量槽用 `{变量名}`
- `variables`：模板变量取值池，做兜底注入

## 素材格式（dlg seed 消费）

`台词角色库/<角色>/素材/*.txt`（或 .md），每行一条：

```
[场景|情绪] 台词      # 带目标格标注 → dlg seed --apply 自动并入配置
台词                  # 无标注 → dlg seed 列出待人工归类
```

- 格 key 必须与 `dimensions` 的取值完全匹配（顺序同配置）
- `--apply` 入库前自动备份 `台词配置.json.bak`，并入按格去重

## 引擎调用协议（接入方照抄）

```python
import 引擎                      # 或 from 引擎 import reply

line = 引擎.reply({"场景": "熬夜", "情绪": "烦躁", "对象": "你"})   # 返回 str，永不抛异常
```

- **context**：dict，键 = 维度名（必给），变量键可选
- **返回**：str 台词；未覆盖组合走模板兜底（变量注入），模板也没有则占位文案
- **元信息**（可选读）：`引擎._DIM_ORDER` 维度顺序、`引擎._LINE_LIB` 格子台词表、`引擎._VARS` 变量池
- **批量接入**：context 逐行写 JSONL，`cat ctx.jsonl | dlg run 小雨 --stdin --json`，stdout 拿 `{"context","reply","mode"}`；坏行自动跳过不炸进程

## 明确不做

- 不接桌宠工程、角色卡格式、语音/TTS、聊天机器人接口——纯文字台词处理（那些方向的接法见 SKILL.md 的方向适配）
- 不做复杂自然语言理解，台词由结构化触发驱动
