# 记忆生命周期与遗忘规范

## 1. 目标

给三类记忆单元（信念 / 主题 / 经验）一套统一的生命周期：**能被想起，也能被淡忘，但永不物理删除**。

- 信念：`kg_relation`
- 主题：`topic`
- 经验：`experience`

## 2. 状态机

```
active ──衰减──> candidate ──遗忘──> forgotten ──恢复──> active
   └──────────────────归档────────────────> archived
```

| 状态 | 含义 | 是否参与日常召回 |
| --- | --- | --- |
| `active` | 当前有效记忆 | 是 |
| `candidate` | 长期未被想起，等待淘汰 | 否（由 `decay` 自动进入） |
| `archived` | 已被上层归并 / 主动归档 | 否（保留供审计） |
| `forgotten` | 已退出认知，但记录完整保留 | 否 |

**关键区分**：`status` 记信念的真假（`active / superseded / rejected`），`lifecycle_state` 记这段记忆是否还在认知里。两者独立，不要混用。遗忘一条信念时，会把 `is_active=0, status='forgotten', valid_to=now`；恢复时置回 `is_active=1, status='active', valid_to=0`。

## 3. 记忆强度

```
strength = confidence * (0.5 + 0.5 * importance) * 0.5 ** (age_days / half_life_days)
```

- `age_days` 基于 `last_access_ts`，老数据为 NULL 时回退到 `create_ts`；
- 主题强度基线 `confidence=0.7`，经验 `0.6`；
- 半衰期默认 30 天；`strength < 0.25` 进入 candidate，`< 0.10` 进入 forgotten；
- 冷却期 `LIFECYCLE_MIN_AGE_DAYS=30`：刚写入的记忆就算算得低也不会被淘汰。

配置全部集中在 `config.py` 的「五之二、记忆生命周期与遗忘策略」段，支持 `.env` 覆盖。

## 4. 遗忘保护（永不遗忘）

以下单元会被标记为 `protected`，衰减和遗忘都会跳过：

- 信念：`user_confirmed=1`、`importance >= LIFECYCLE_IMPORTANCE_EXEMPT`、`source_type='seed'`；
- 主题：seed 前史会话、大事主题、`kind in ('daily','event')`；
- 经验：挂在受保护主题下的经验片段。

## 5. 召回记账

`MemoryRouter.route()` 在召回完成后调用 `LifecycleManager.touch_recall()`：

- 命中的主题及其经验片段 → 更新 `last_access_ts`；
- 查询文本里提到的实体名对应的信念 → 更新 `last_access_ts`；
- 记账失败一律吞掉异常，不影响本次回答。

可通过 `LIFECYCLE_ENABLED=false` 关闭记账。

## 6. 审计与可逆性

每一次状态变化都写入 `memory_lifecycle_event`（append-only）：

| 字段 | 含义 |
| --- | --- |
| `space_id, event_id` | 主键 |
| `unit_type, unit_id` | 哪个单元 |
| `from_state, to_state` | 状态迁移 |
| `reason` | 原因（如「强度 0.082 < 遗忘线 0.10」或「用户手动恢复」） |
| `create_ts` | 发生时间 |

遗忘**不物理删除任何记录**，来源、内容、审计链全部保留。任何 `forgotten` / `candidate` 单元都能通过 `restore()` 恢复为 `active`。

## 7. 用法

### 命令行

```powershell
# 预演（默认，不落库）
python maintenance.py --forget

# 真正执行
python maintenance.py --forget --yes

# 只看某个空间
python maintenance.py --forget --space me
```

### API

```
GET  /api/memory/lifecycle?space_id=default&events=100
POST /api/memory/lifecycle/forget        {"space_id":"default"}              # dry-run
POST /api/memory/lifecycle/forget        {"space_id":"default","apply":true} # 真正执行
POST /api/memory/lifecycle/restore       {"space_id":"default","unit_type":"topic","unit_id":"..."}
```

所有 `/api/*` 受全局 `API_TOKEN` 鉴权保护（如果配置了的话）。

### Python

```python
from cognitive.cognition.lifecycle import LifecycleManager

manager = LifecycleManager(db)
manager.scan(space_id)                     # 强度 / 状态 / 保护标记
manager.decay(space_id, dry_run=True)      # active -> candidate
manager.forget(space_id, dry_run=True)     # candidate -> forgotten
manager.restore(space_id, "topic", tid)    # 恢复到 active
manager.list_events(space_id)              # 审计账本
```

## 8. 读路径过滤

以下读路径默认跳过 `forgotten` 单元，审计/导出可按需放开：

- `TopicStore.list_topics()` → `include_forgotten=True` 可包含；
- `TopicStore.get_experiences_by_topic()` → 直接过滤；
- `KGStore.query_by_text() / query_past_beliefs() / query_overturned()` → 直接过滤；
- `MemoryRouter.route()` → 双重保险（存储层 + 路由层）；
- `cognitive.proactive` 的经验/关系查询 → 直接过滤；
- `/api/memory/universe` 的经验查询 → 直接过滤。

注意：向量索引文件中可能仍残留已遗忘主题的摘要，但召回时会按数据库状态二次过滤，不会进入 Prompt。
