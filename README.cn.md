# 认知 Agent（江秀妍）

一个面向中文场景的持续运行认知 Agent 项目：具备分层记忆、主动归档、结构化信念（可确认/纠正/否决/追溯）、可演化人格与 Web 可视化界面。后端基于 Python + SQLite，可接入 DeepSeek 或任意 OpenAI 兼容的 Chat Completions 接口。

[English README](README.md)

> 这不是“给聊天机器人外挂一个向量库”。每一轮对话都会进入认知处理流程：会话上下文管理、记忆召回与路由、信念抽取与更新、人格/关系状态变化、按需检索与回复生成。信念支持来源追踪与审计，前端提供聊天界面、记忆查看与 3D 信念星图。

---

## 当前人设

**江秀妍（昵称：小苹果）**

- 18 岁，东北电力大学计算机学院 2026 级大一新生（计算机科学与技术）
- 湖南湘西吉首人，普通话带一点湘西尾音
- 形象与生活片段：160cm、圆脸、右眼下有小痣；喜欢 cos（《明日方舟》，偏爱陈、能天使）、《声之形》，无辣不欢，养三花猫“辣椒”
- 性格特点：外在温和有礼、会先接住情绪再回应；内里认真执拗、观察细致、记性好；被敷衍或被替自己做决定时会先安静下来，把话说得更具体；有情绪与边界

基础人设与初始资料位于 `data/persona/`（`profile.json`、`kernel.json`、`meta.json`、`seed.json`、`avatar.jpg`）。项目中的虚拟人生与前史资料可见 `docs/virtual-life/` 与 `data/virtual-life/`。

---

## 主要功能

### 分层记忆与认知回复
- **会话上下文**：保留近期对话参与回复生成。
- **主题/经验记忆**：对事件与对话内容归档沉淀，支持后续召回。
- **结构化信念（知识图谱）**：将关键信息抽取为可查询、可更新的信念记录（主体/关系/客体、置信度、重要度、状态、来源等）。
- **人格与自我认知**：人格参数与自我叙述参与回复风格与判断，并可随事件演化。
- **按需检索**：在上下文/记忆不足时进行补充检索（依实现与配置）。

### 信念管理与审计
- 信念可随新信息更新、共存或被替代/推翻（依关系语义与规则）。
- 支持**确认、纠正、否决**，保留来源与审计记录。
- 支持**手动写入/修正信念内容**（可填写主体、关系、客体及置信度/重要度），旧信念可标记为替代/停用并保留历史。

### 3D 记忆宇宙
- **结构**：所有记忆星沿 **8 字形（无限环）星带**较均匀地分布，并持续沿 8 的笔画方向运动；两条星带在空间中上下扭转，交叉处彼此分开，不在同一平面重叠。
- **覆盖范围**：不只信念，还包括**往事（主题）、经历（经验片段）、人与物（实体）、人格版本、人格变迁、情绪状态、关系好感度**等所有可表达的记忆。
- **视觉映射**：星体使用固定绝对大小；**重要程度越高，亮度越高、运动速度越快**；最慢约 4 分钟一圈，最快约 2 分钟一圈；颜色采用低饱和类型色，整体保持真实星空的冷灰/淡蓝质感。
- **交互**：拖拽旋转、缩放、自动旋转、搜索定位；点击任意星体查看详情（往事可看关联经历与信念，实体可看关联信念，信念可直接确认/纠正/否决）。

### Web 界面与接口
- Web UI：聊天、设置、记忆查看、记忆宇宙等页面。
- HTTP API：消息收发、状态/记忆/设置读取、信念操作等（具体路由以 `api/server.py` 为准）。

---

## 快速开始

### 1. 环境准备
- Python 3.10+（推荐 3.11 / 3.12）
- 可用的模型接口 Key（如 DeepSeek 或 OpenAI 兼容服务）

安装依赖（建议在虚拟环境中）：

```bash
pip install -r requirements.txt
```

### 2. 配置
复制 `.env.example` 为 `.env`，填写必要配置，例如：

```ini
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-flash
LLM_MODE=api
```

更多可调项（温度、最大 token、超时/重试、路径覆盖如 `DB_PATH`、`VECTOR_DIR` 等）以 `config.py` 与 `.env.example` 为准。

### 3. 启动

**命令行入口：**
```bash
python run.py
```
常用参数示例：`--space`、`--session`、`--debug`、`--state`（以脚本实际实现为准）。

**Web 界面 / API 服务：**
```bash
python api/server.py
```
或
```bash
python -m api.server
```
启动后访问：`http://127.0.0.1:8000/`（信念星图：`/starmap.html`）。

> 修改后端提示词或 Python 逻辑后需重启服务；前端静态资源修改后刷新页面即可。

---

## 目录结构

```text
.
├─ api/                  # HTTP API / Web 服务
├─ cognitive/            # 认知核心（记忆、信念、人格、检索、提示词、流程编排等）
├─ web/                  # 前端页面与交互（聊天、设置、记忆、记忆宇宙）
├─ data/
│  ├─ persona/           # 基础人设与初始种子（profile/kernel/meta/seed/avatar）
│  ├─ corpus/            # 语料/知识文本
│  ├─ virtual-life/      # 虚拟人生结构化数据
│  ├─ persona_snapshots/ # 人格快照（运行/沉淀产物）
│  ├─ vectors/           # 向量索引
│  └─ memory.db          # SQLite 记忆/信念等数据（运行后生成或已有）
├─ docs/                 # 文档（含虚拟人生等）
├─ scripts/              # 脚本工具（如前史写入等）
├─ tests/                # 测试与冒烟检查
├─ config.py             # 全局配置
├─ run.py                # CLI 入口
├─ maintenance.py        # 维护工具
├─ requirements.txt
├─ .env.example
├─ README.md
└─ README.cn.md
```

---

## 维护与脚本

`maintenance.py` 提供常用维护能力（参数以脚本实际实现为准）：

```bash
# 日结/巩固
python maintenance.py --daily
python maintenance.py --daily --space jiangyan

# 查看统计 / 人设与数据路径
python maintenance.py --stats
python maintenance.py --persona-info

# 清理旧快照（保留最近 N 个）
python maintenance.py --prune-snapshots --keep 30

# 注入初始人设前史/信念种子
python maintenance.py --seed-persona --space jiangyan
```

`scripts/` 下包含辅助脚本（例如前史数据写入、快照生成等），可按需运行。

---

## 测试

在 Windows PowerShell 下建议使用 UTF-8 输出以正常显示中文：

```powershell
$env:PYTHONIOENCODING='utf-8'; py tests/smoke_test.py
```

其他测试以 `tests/` 目录实际内容为准。

---

## 说明

- 本项目的默认人设、交互与主要内容面向中文场景。
- 回复效果受模型、配置、记忆与信念状态影响；当信息不足时，系统应明确不确定而非编造细节。
- 运行数据（如数据库、向量索引、快照、头像等）会随使用持续变化，分享或迁移时请按需处理。