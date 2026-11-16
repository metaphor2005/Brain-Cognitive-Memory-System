# Cognitive Agent

一个**持续运行的中文认知 Agent**：分层记忆、主动归档、结构化信念、可演化人格与 Web 可视化界面，基于纯 Python + SQLite 实现，可接入 DeepSeek 或任何 OpenAI 兼容的 Chat Completions 接口。

[English README](README.md)

> 这不是“给聊天机器人外挂一个向量库”。每一轮对话都会进入认知处理流程：会话、记忆路由、信念抽取与更新、人格/关系状态变化、按需检索与回复生成；信念可以被确认、纠正、推翻并保留审计痕迹；前端提供微信风格聊天、记忆查看与 3D 信念星图。

---

## 当前人设

**当前人设：江秀妍（昵称「小苹果」）**

- 18 岁，东北电力大学 计算机学院 计算机科学与技术 2026 级 1 班，大一新生
- 湖南湘西吉首人；普通话带一点湘西尾音
- 外形与生活片段：160cm，圆脸，右眼下有一颗小痣；喜欢 cos（主要是《明日方舟》，推陈、能天使等），喜欢《声之形》，无辣不欢，养了一只三花猫“辣椒”
- 性格：外显温柔有礼、先接住情绪再表达；内里认死理、记性好，被敷衍或被替自己做决定时会安静下来，把话说得更具体；有自己的情绪与边界，不是客服式应答

基础人设与初始前史/信念种子位于 `data/persona/`：`profile.json`、`kernel.json`、`meta.json`、`seed.json`、`avatar.jpg`。  
项目通过 `config.py` / persona 加载逻辑读取这些基础数据；在可用记忆库缺失或按需初始化时，可从 `seed.json` 注入初始前史与信念。

---

## 当前状态与发布说明

- **代码形态**：Python 后端 + Web 前端（`web/`）+ SQLite 持久化（`data/`）
- **默认记忆空间/示例空间**：常用 `default` / `jiangyan`（具体以运行参数和数据为准）
- **基础人设数据**：已包含在 `data/persona/`，适合作为仓库初始内容保留
- **运行时数据**：`data/memory.db`、`data/vectors/`、`data/persona_snapshots/`、`data/user_avatar.json` 等属于本地运行产物/个人数据，公开发布到 GitHub 前应谨慎处理（见文末“发布到 GitHub 前的建议”）

---

## 它能做什么

### 1. 分层记忆与认知回复
- **会话上下文**：保留近期对话轮次，参与当前回复生成。
- **主题/经验记忆**：对对话内容进行归档与沉淀，用于后续召回。
- **结构化信念（KG）**：将关键信息抽取为可查询、可更新的信念记录（主体/关系/客体、置信度、重要度、状态、来源等）。
- **人格与自我认知**：人格参数/倾向与自我叙述参与回复风格与判断。
- **按需检索**：在现有上下文/记忆不足时触发检索与补充（按系统实现与配置执行）。

### 2. 信念管理：确认、冲突、纠正与审计
- 信念可随新信息更新、共存或被新信念替代/推翻（依关系类型与规则而定）。
- 支持**用户确认、纠正、否决**等操作，并记录来源与审计信息。
- 支持**手动写入正确内容**：
  - 可在记忆页或信念星图详情中发起；
  - 可填写主体、关系、客体及置信度/重要度等；
  - 可选择替换某条旧信念（旧信念标记为替代/停用，保留痕迹）；
  - 手动修正来源标记为用户修正（如 `user_corrected`）。

### 3. 3D 信念星图（Web 可视化）
- **布局结构**：`核心 → 类别节点 → 信念节点` 的径向展开；类别枢纽围绕核心分布，包含上下方向的类别节点。
- **全部展示**：所有信念都会显示，包括已被推翻/停用的旧信念（以不同状态/样式区分）。
- **空间含义（基于已有参数）**：不单独显示“遗忘度”参数；节点分布依据**重要度、置信度、状态/是否生效**等已有信息计算：
  - 越靠内：通常越重要、越确信；
  - 越往外：通常越次要，或已被推翻/停用。
- **视觉与交互**：
  - 星光色节点、星云/星空背景；
  - 悬停高亮时，其他元素仅轻微变暗，保持整体可读；
  - 支持拖拽旋转、缩放、搜索定位、重置视角、自动旋转、类别筛选；
  - 点击节点查看详情，并可从星图详情对信念进行手动修正。

### 4. 更自然的对话回复（人设一致）
- 回复提示词已调整为更贴近真人聊天的表达方式：
  - 顺着对方的话自然回应，不必每次都输出“报告式”长文；
  - 语气更口语化，句子长短随情境变化；
  - 避免“作为一个…”“首先其次”“希望对你有帮助”等模板腔与机械列点（除非用户明确需要）。
- 同时保留关键约束：
  - 基于记忆与上下文，不编造细节；
  - 不把已被推翻/停用的旧信念当作当前结论；
  - 记不清时明确说明不确定；
  - 保持江秀妍的人设、情绪与边界表达。

> 注意：修改后端提示词（如 `cognitive/cognition/prompts.py`）后，需要重启后端进程，新回复才会生效；前端静态文件刷新页面即可。

### 5. 人格、关系与主动机制（按实现/配置生效）
- 人格内核与状态参与回复与演化。
- 支持好感度/关系温度等关系状态记录与展示（以项目当前实现为准）。
- 支持主动联系相关能力与偏好设置（如启用/免打扰/节奏等，依当前版本接口与 UI 为准）。

### 6. Web 界面与 API
- Web UI：聊天、设置、记忆查看、信念星图等。
- HTTP API：用于发送消息、读取状态/记忆/设置信息、执行信念操作等（见 `api/server.py` 及实际路由）。

---

## 快速开始

### 1. 环境要求
- Python 3.10+（推荐 3.11/3.12）
- Windows / Linux / macOS（本项目当前在 Windows 环境下开发与验证较多）
- 可用的模型接口 Key（如 DeepSeek 或兼容 OpenAI 的服务）

### 2. 安装依赖
建议使用虚拟环境：

```bash
pip install -r requirements.txt
```

### 3. 配置 `.env`
复制 `.env.example` 为 `.env`，并填写配置（示例）：

```ini
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-flash
LLM_MODE=api
```

常见可调项（以 `config.py` / `.env.example` 为准）还包括：温度、最大 token、超时、重试、路径覆盖（如 `DB_PATH`、`VECTOR_DIR`）等。

> `.env` 包含密钥与本地配置，**不要提交到 GitHub**。

### 4. 启动项目

#### 方式 A：运行入口脚本
```bash
python run.py
```
`run.py` 提供 CLI 交互/调试入口（支持 `--space`、`--session`、`--debug`、`--state` 等参数，具体以脚本实现为准）。

#### 方式 B：启动 Web/API 服务
项目包含 `api/server.py`（Flask）用于 Web UI 与接口服务。可按你的使用习惯运行该服务（例如直接运行脚本或由现有启动脚本封装），启动后在浏览器打开对应页面。

> 不同环境的推荐启动方式可能略有差异；若你已有固定启动命令，请以实际项目脚本为准。

### 5. 首次运行与人设前史注入（可选）
基础人设与初始前史/信念种子位于 `data/persona/seed.json`。  
若需要手动注入或重置注入初始前史（幂等行为以实现为准），可使用维护脚本：

```bash
python maintenance.py --seed-persona --space jiangyan
```

---

## 目录结构

```text
.
├─ api/                  # HTTP API / Web 服务
├─ cognitive/            # 认知核心（提示词、记忆、信念、人格、检索、流程编排等）
├─ web/                  # 前端页面与交互（聊天、设置、记忆、信念星图）
├─ data/
│  ├─ persona/           # 基础人设与初始种子（profile/kernel/meta/seed/avatar）
│  ├─ corpus/            # 语料/知识库文本
│  └─ README.md          # data 目录说明
├─ docs/                 # 文档
├─ tests/                # 测试与冒烟脚本
├─ config.py             # 全局配置
├─ run.py                # CLI 入口
├─ demo.py               # 示例/演示脚本（如有使用）
├─ maintenance.py        # 维护工具（统计、日结、快照清理、seed 等）
├─ requirements.txt      # 依赖
├─ .env.example          # 环境变量示例
├─ README.cn.md
└─ README.md
```

> 实际运行后还可能生成：`data/memory.db`、`data/vectors/`、`data/persona_snapshots/`、`logs/` 等目录或文件。

---

## 数据与人设说明

### `data/persona/`（建议保留并纳入仓库）
- `profile.json`：身份档案、性格、关系、偏好等基础设定
- `kernel.json`：人格内核/参数初始状态
- `meta.json`：人设元信息
- `seed.json`：初始前史与信念种子（用于冷启动/注入）
- `avatar.jpg`：默认头像资源

### `data/corpus/`（建议保留）
用于检索增强或知识补充的文本语料，可按需扩展。

### 本地运行时数据（通常不建议公开上传）
- `data/memory.db`（及 `*-wal` / `*-shm`）：实际对话、记忆、信念与运行状态数据库
- `data/vectors/`：向量索引缓存
- `data/persona_snapshots/`：运行中生成的人格快照
- `data/user_avatar.json`：用户自定义头像等个人数据
- `logs/`：运行日志

---

## 维护脚本（`maintenance.py`）

常用命令（以脚本实际参数为准）：

```bash
# 日结/巩固（按空间）
python maintenance.py --daily
python maintenance.py --daily --space jiangyan

# 查看统计
python maintenance.py --stats

# 清理旧快照（保留最近 N 个）
python maintenance.py --prune-snapshots --keep 30

# 查看人设/数据路径信息
python maintenance.py --persona-info

# 注入初始人设前史/信念种子
python maintenance.py --seed-persona --space jiangyan
```

---

## 测试与验证

项目包含测试脚本（如 `tests/smoke_test.py`）。在 Windows PowerShell 下建议使用 UTF-8 输出以避免中文乱码：

```powershell
$env:PYTHONIOENCODING='utf-8'; py tests/smoke_test.py
```

也可按需运行其他测试文件（以 `tests/` 目录实际内容为准）。

---

## 发布到 GitHub 前的建议（重要）

如果目标是公开仓库，请重点检查并清理以下内容：

### 不建议上传
- `.env`（API Key 等密钥）
- `data/memory.db`、`data/memory.db-wal`、`data/memory.db-shm`（真实对话与运行记忆）
- `data/user_avatar.json`（个人数据）
- `data/vectors/`（可重建缓存）
- `data/persona_snapshots/`（运行时快照）
- `.venv/`、`__pycache__/`、`.ruff_cache/`、`.idea/`、`*.pyc` 等环境/缓存文件

### 建议保留
- 源码与前端：`api/`、`cognitive/`、`web/`、`tests/`
- 基础人设与语料：`data/persona/`、`data/corpus/`、`data/README.md`
- 配置模板与文档：`.env.example`、`.gitignore`、`README.md`、`README.cn.md`、`requirements.txt`、`docs/`

### 额外提醒
- 若前端信念星图依赖离线 3D 库文件（如 `web/vendor/3d-force-graph.min.js`），请确认发布目录中已包含该文件；缺失时星图可能无法加载。
- 修改提示词/后端逻辑后需重启后端；前端静态资源更新后刷新页面即可。

---

## 说明

- 本项目的默认人设、交互与主要文档面向中文场景。
- 英文 README 用于开发者理解与使用，不改变角色本身的中文表达设定。
