"""
记忆生命周期与遗忘策略。

把三类记忆单元（信念 / 主题 / 经验）统一成一条可逆的生命周期：

    active ──衰减──> candidate ──遗忘──> forgotten ──恢复──> active
      └────────────────归档────────────> archived

设计约束：
1. 遗忘只改状态、不物理删除。记录、来源、审计都在，随时可恢复。
2. 每一次状态变化都写 memory_lifecycle_event，回答"它为什么消失/回来"。
3. 核心信念（用户确认 / 高重要度 / 前史种子）与人格事件永不遗忘。
4. 遗产数据兼容：last_access_ts 为 NULL 时回退到 create_ts。
5. 记账失败不允许打断召回 —— 调用方一律 try/except 包住。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import config
from cognitive.models import new_id
from cognitive.persona.seed import SEED_SESSION_ID
from cognitive.storage.database import Database


UNIT_BELIEF = "belief"
UNIT_TOPIC = "topic"
UNIT_EXPERIENCE = "experience"
VALID_UNITS = (UNIT_BELIEF, UNIT_TOPIC, UNIT_EXPERIENCE)

STATE_ACTIVE = "active"
STATE_CANDIDATE = "candidate"
STATE_ARCHIVED = "archived"
STATE_FORGOTTEN = "forgotten"

# unit_type -> 物理表名（只通过白名单拼 SQL，绝不接外部字符串）
_TABLES = {
    UNIT_BELIEF: "kg_relation",
    UNIT_TOPIC: "topic",
    UNIT_EXPERIENCE: "experience",
}
_ID_COLUMNS = {
    UNIT_BELIEF: "rid",
    UNIT_TOPIC: "topic_id",
    UNIT_EXPERIENCE: "exp_id",
}


def memory_strength(
    confidence: float,
    importance: float,
    last_access_ts: int,
    now: int,
    half_life_days: Optional[float] = None,
) -> float:
    """
    计算记忆强度：置信度 × 重要度权重 × 时间衰减。

    :param confidence: 信念置信度（主题/经验用固定基线）
    :param importance: 对自我的重要度
    :param last_access_ts: 最近一次被召回时间（0 表示从未，调用方应先回退到创建时间）
    :param now: 当前时间戳
    :param half_life_days: 半衰期（天），None 表示用配置值
    :return: 0~1 的强度
    """
    half_life = half_life_days or config.LIFECYCLE_HALF_LIFE_DAYS
    age_days = max(0.0, (int(now) - int(last_access_ts or 0)) / 86400.0)
    recency = 0.5 ** (age_days / max(0.1, half_life))
    return max(0.0, min(1.0, float(confidence) * (0.5 + 0.5 * float(importance)) * recency))


class LifecycleManager:
    """记忆单元的注册、召回记账、衰减、遗忘与恢复。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------
    # 记账
    # ------------------------------------------------------------
    def register_topic(self, space_id: str, topic_id: str, now: Optional[int] = None) -> None:
        """
        归档完成后登记新单元：主题 + 挂载经验 + 同轮产生的信念。

        已存在的 last_access_ts 不覆盖（幂等），已遗忘的单元不自动复活
        （遗忘是显式决定，不能因为重新抽取一次就被悄悄撤销）。

        :param space_id: 记忆空间
        :param topic_id: 刚归档的主题 id
        :param now: 当前时间戳（测试可注入）
        """
        now = int(now or time.time())
        connection = self.db.conn()
        connection.execute(
            """
            update topic set lifecycle_state = 'active',
                last_access_ts = coalesce(last_access_ts, ?)
            where space_id = ? and topic_id = ?
            """,
            (now, space_id, topic_id),
        )
        connection.execute(
            """
            update experience set lifecycle_state = 'active',
                last_access_ts = coalesce(last_access_ts, ?)
            where space_id = ? and topic_id = ?
            """,
            (now, space_id, topic_id),
        )
        connection.execute(
            """
            update kg_relation set lifecycle_state = 'active',
                last_access_ts = coalesce(last_access_ts, ?)
            where space_id = ? and source_topic_id = ?
            """,
            (now, space_id, topic_id),
        )
        connection.commit()

    def touch(
        self,
        space_id: str,
        unit_type: str,
        unit_id: str,
        now: Optional[int] = None,
    ) -> bool:
        """
        记一次"被想起"：只更新 last_access_ts，不改变状态。

        :return: 是否真的更新到一行
        """
        if not config.LIFECYCLE_ENABLED:
            return False
        table = _TABLES.get(unit_type)
        id_column = _ID_COLUMNS.get(unit_type)
        if not table or not id_column or not unit_id:
            return False

        connection = self.db.conn()
        cursor = connection.execute(
            f"update {table} set last_access_ts = ? where space_id = ? and {id_column} = ?",
            (int(now or time.time()), space_id, unit_id),
        )
        connection.commit()
        return bool(cursor.rowcount)

    def touch_recall(
        self,
        space_id: str,
        query: str,
        topic_ids: Optional[List[str]] = None,
        now: Optional[int] = None,
    ) -> int:
        """
        一次召回的批量记账：命中的主题、其经验片段，以及查询里提到的实体相关信念。

        :param space_id: 记忆空间
        :param query: 用户本轮输入（用于匹配实体名）
        :param topic_ids: 本轮命中的主题 id
        :return: 更新的单元数（用于观测，失败时为 0）
        """
        if not config.LIFECYCLE_ENABLED:
            return 0
        now = int(now or time.time())
        connection = self.db.conn()
        touched = 0

        for topic_id in topic_ids or []:
            for table, id_column in (("topic", "topic_id"), ("experience", "topic_id")):
                cursor = connection.execute(
                    f"update {table} set last_access_ts = ?"
                    f" where space_id = ? and {id_column} = ?",
                    (now, space_id, topic_id),
                )
                touched += cursor.rowcount or 0

        # 与 KGStore.query_by_text 的匹配规则保持一致：实体名包含匹配
        names = [
            str(row["name"])
            for row in connection.execute(
                "select name from kg_entity where space_id = ? and is_active = 1",
                (space_id,),
            ).fetchall()
            if row["name"] and str(row["name"]) in (query or "")
        ]
        if names:
            placeholders = ",".join("?" for _ in names)
            cursor = connection.execute(
                f"update kg_relation set last_access_ts = ? where space_id = ?"
                f" and (head_name in ({placeholders}) or tail_name in ({placeholders}))",
                (now, space_id, *names, *names),
            )
            touched += cursor.rowcount or 0

        connection.commit()
        return touched

    # ------------------------------------------------------------
    # 扫描与打分
    # ------------------------------------------------------------
    def scan(self, space_id: str, now: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        列出空间内全部记忆单元及其强度/豁免标记（复用同一套 SQL，便于审计）。

        :param space_id: 记忆空间
        :param now: 当前时间戳（测试可注入）
        :return: [{"unit_type","unit_id","strength","state","protected",...}]
        """
        now = int(now or time.time())
        rows = self.db.conn().execute(
            """
            select 'belief' as unit_type, r.rid as unit_id,
                   r.confidence as confidence, r.importance as importance,
                   coalesce(nullif(r.last_access_ts, 0), r.create_ts) as accessed_ts,
                   coalesce(r.create_ts, 0) as create_ts,
                   coalesce(r.lifecycle_state, 'active') as state,
                   case when r.user_confirmed = 1 or r.importance >= ?
                             or r.source_type = 'seed' then 1 else 0 end as protected
            from kg_relation as r where r.space_id = ?
            union all
            select 'topic', t.topic_id, 0.7,
                   case when t.is_big_event = 1 then 0.9 else 0.5 end,
                   coalesce(nullif(t.last_access_ts, 0), t.create_ts),
                   coalesce(t.create_ts, 0),
                   coalesce(t.lifecycle_state, 'active'),
                   case when t.session_id = ? or t.is_big_event = 1
                             or t.kind in ('daily', 'event') then 1 else 0 end
            from topic as t where t.space_id = ?
            union all
            select 'experience', x.exp_id, 0.6, 0.5,
                   coalesce(nullif(x.last_access_ts, 0), x.create_ts),
                   coalesce(x.create_ts, 0),
                   coalesce(x.lifecycle_state, 'active'),
                   case when exists (
                       select 1 from topic as pt
                       where pt.space_id = x.space_id and pt.topic_id = x.topic_id
                         and (pt.session_id = ? or pt.is_big_event = 1
                              or pt.kind in ('daily', 'event'))
                   ) then 1 else 0 end
            from experience as x where x.space_id = ?
            """,
            (
                config.LIFECYCLE_IMPORTANCE_EXEMPT,
                space_id,
                SEED_SESSION_ID,
                space_id,
                SEED_SESSION_ID,
                space_id,
            ),
        ).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            accessed = int(row["accessed_ts"] or 0)
            created = int(row["create_ts"] or 0)
            items.append(
                {
                    "unit_type": str(row["unit_type"]),
                    "unit_id": str(row["unit_id"]),
                    "state": str(row["state"]),
                    "protected": bool(row["protected"]),
                    "confidence": float(row["confidence"] or 0.0),
                    "importance": float(row["importance"] or 0.0),
                    "strength": memory_strength(
                        float(row["confidence"] or 0.0),
                        float(row["importance"] or 0.0),
                        accessed,
                        now,
                    ),
                    "age_days": round(max(0.0, (now - accessed) / 86400.0), 2),
                    "accessed_ts": accessed,
                    "create_ts": created,
                }
            )
        return items

    # ------------------------------------------------------------
    # 状态迁移
    # ------------------------------------------------------------
    def _write_event(
        self,
        space_id: str,
        unit_type: str,
        unit_id: str,
        from_state: str,
        to_state: str,
        reason: str,
        now: int,
    ) -> None:
        self.db.conn().execute(
            """
            insert into memory_lifecycle_event
                (space_id, event_id, unit_type, unit_id, from_state, to_state, reason, create_ts)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                space_id,
                new_id("lc"),
                unit_type,
                unit_id,
                from_state,
                to_state,
                reason,
                now,
            ),
        )

    def _set_state(
        self,
        space_id: str,
        item: Dict[str, Any],
        to_state: str,
        reason: str,
        now: int,
    ) -> None:
        """写一个单元的状态（含信念的生效位），并留审计事件。"""
        unit_type = str(item["unit_type"])
        table = _TABLES[unit_type]
        id_column = _ID_COLUMNS[unit_type]
        connection = self.db.conn()

        # 衰减/遗忘时**不能**刷新 last_access_ts：否则强度立刻回到 1.0，
        # 这条记忆就永远淘汰不掉。只有恢复为 active 才给一个全新的访问时间。
        if to_state == STATE_ACTIVE:
            access_clause = ", last_access_ts = ?"
            access_params: tuple = (now,)
        else:
            access_clause = ""
            access_params = ()

        if unit_type == UNIT_BELIEF:
            connection.execute(
                f"update {table} set lifecycle_state = ?, update_ts = ?{access_clause}"
                f" where space_id = ? and {id_column} = ?",
                (to_state, now, *access_params, space_id, item["unit_id"]),
            )
        else:
            connection.execute(
                f"update {table} set lifecycle_state = ?{access_clause}"
                f" where space_id = ? and {id_column} = ?",
                (to_state, *access_params, space_id, item["unit_id"]),
            )

        if unit_type == UNIT_BELIEF:
            if to_state == STATE_FORGOTTEN:
                connection.execute(
                    """
                    update kg_relation set is_active = 0, status = 'forgotten', valid_to = ?
                    where space_id = ? and rid = ?
                    """,
                    (now, space_id, item["unit_id"]),
                )
            elif to_state == STATE_ACTIVE:
                connection.execute(
                    """
                    update kg_relation set is_active = 1, status = 'active', valid_to = 0
                    where space_id = ? and rid = ?
                    """,
                    (space_id, item["unit_id"]),
                )

        self._write_event(
            space_id,
            unit_type,
            item["unit_id"],
            str(item["state"]),
            to_state,
            reason,
            now,
        )

    def decay(
        self,
        space_id: str,
        now: Optional[int] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        active → candidate：长期没被想起、强度跌破衰减线。

        :param space_id: 记忆空间
        :param now: 当前时间戳
        :param dry_run: True 只给出清单不落库
        """
        now = int(now or time.time())
        candidates: List[Dict[str, Any]] = []
        for item in self.scan(space_id, now):
            if item["protected"] or item["state"] != STATE_ACTIVE:
                continue
            if item["age_days"] < config.LIFECYCLE_MIN_AGE_DAYS:
                continue
            if item["strength"] >= config.LIFECYCLE_DECAY_THRESHOLD:
                continue
            candidates.append(item)

        if not dry_run:
            for item in candidates:
                self._set_state(
                    space_id,
                    item,
                    STATE_CANDIDATE,
                    f"强度 {item['strength']:.3f} < 衰减线 {config.LIFECYCLE_DECAY_THRESHOLD}",
                    now,
                )
            self.db.conn().commit()

        return {
            "ok": True,
            "dry_run": dry_run,
            "decayed": len(candidates),
            "items": candidates,
        }

    def forget(
        self,
        space_id: str,
        now: Optional[int] = None,
        dry_run: bool = True,
        decay_first: bool = True,
    ) -> Dict[str, Any]:
        """
        candidate → forgotten：强度跌破遗忘线，退出日常认知但保留记录。

        :param space_id: 记忆空间
        :param now: 当前时间戳
        :param dry_run: True 只给清单不落库（命令行默认）
        :param decay_first: 先跑一次 decay，让新到期的单元能直接进入候选
        """
        now = int(now or time.time())
        if decay_first:
            self.decay(space_id, now=now, dry_run=dry_run)

        candidates: List[Dict[str, Any]] = []
        protected_skipped = 0
        for item in self.scan(space_id, now):
            if item["state"] in (STATE_FORGOTTEN, STATE_ARCHIVED):
                continue
            if item["protected"]:
                protected_skipped += 1
                continue
            if item["age_days"] < config.LIFECYCLE_MIN_AGE_DAYS:
                continue
            if item["strength"] >= config.LIFECYCLE_FORGET_THRESHOLD:
                continue
            candidates.append(item)

        candidates = candidates[: max(0, config.LIFECYCLE_FORGET_BATCH)]

        if not dry_run:
            for item in candidates:
                self._set_state(
                    space_id,
                    item,
                    STATE_FORGOTTEN,
                    f"强度 {item['strength']:.3f} < 遗忘线 {config.LIFECYCLE_FORGET_THRESHOLD}",
                    now,
                )
            self.db.conn().commit()

        return {
            "ok": True,
            "dry_run": dry_run,
            "forgotten": len(candidates),
            "protected_skipped": protected_skipped,
            "items": candidates,
        }

    def restore(
        self,
        space_id: str,
        unit_type: str,
        unit_id: str,
        now: Optional[int] = None,
    ) -> bool:
        """
        把一个被遗忘/衰减的单元恢复为 active（信念同时恢复生效位）。

        :return: 是否找到并更新了目标
        """
        if unit_type not in VALID_UNITS:
            return False
        now = int(now or time.time())
        table = _TABLES[unit_type]
        id_column = _ID_COLUMNS[unit_type]
        connection = self.db.conn()
        row = connection.execute(
            f"select coalesce(lifecycle_state, 'active') as state from {table}"
            f" where space_id = ? and {id_column} = ?",
            (space_id, unit_id),
        ).fetchone()
        if not row:
            return False

        item = {
            "unit_type": unit_type,
            "unit_id": unit_id,
            "state": str(row["state"]),
        }
        self._set_state(space_id, item, STATE_ACTIVE, "用户手动恢复", now)
        connection.commit()
        return True

    def list_events(self, space_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """列出生命周期事件（最新在前）。"""
        rows = self.db.conn().execute(
            """
            select event_id, unit_type, unit_id, from_state, to_state, reason, create_ts
            from memory_lifecycle_event
            where space_id = ? order by create_ts desc, event_id desc limit ?
            """,
            (space_id, int(limit)),
        ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "unit_type": row["unit_type"],
                "unit_id": row["unit_id"],
                "from_state": row["from_state"],
                "to_state": row["to_state"],
                "reason": row["reason"] or "",
                "create_ts": int(row["create_ts"] or 0),
            }
            for row in rows
        ]
