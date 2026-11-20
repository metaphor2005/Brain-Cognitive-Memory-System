"""
结构化信念存储（轻量属性图 KG）。

核心能力：
1. 实体/关系写入（幂等 upsert）
2. 同一 (头实体, 关系) 下的冲突检测：新值出现时，旧值自动标记失效
3. 重复出现的信念自动加权（confidence / importance 递增），实现"多次验证→信念加固"
4. 按实体名做精确/包含匹配，支持"配置、偏好、约定"类查询
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import config
from cognitive.models import KGEntity, KGRelation, Topic
from cognitive.storage.database import Database


# 关系写回时的权重增量已移到 config.py（BELIEF_BOOST_CONFIDENCE /
# BELIEF_BOOST_IMPORTANCE / BELIEF_BOOST_WEIGHTS / BELIEF_BOOST_SATURATION），
# 便于按部署场景调整；这里保留兼容别名，避免外部 import 断裂。
CONFIDENCE_BOOST: float = config.BELIEF_BOOST_CONFIDENCE
IMPORTANCE_BOOST: float = config.BELIEF_BOOST_IMPORTANCE


class KGStore:
    """知识图谱存储。"""

    def __init__(self, db: Database) -> None:
        """
        :param db: 数据库访问对象
        """
        self.db = db

    # ------------------------------------------------------------
    # 实体
    # ------------------------------------------------------------
    def upsert_entity(self, entity: KGEntity) -> None:
        """
        写入或更新实体（同 space_id + eid 视为同一实体）。

        :param entity: 实体对象
        """
        connection = self.db.conn()
        connection.execute(
            """
            insert into kg_entity (space_id, eid, etype, name, attrs, is_active, create_ts)
            values (?, ?, ?, ?, ?, ?, ?)
            on conflict (space_id, eid) do update set
                etype = excluded.etype,
                name = excluded.name,
                attrs = excluded.attrs,
                is_active = excluded.is_active
            """,
            (
                entity.space_id,
                entity.eid,
                entity.etype,
                entity.name,
                json.dumps(entity.attrs, ensure_ascii=False),
                1 if entity.is_active else 0,
                entity.create_ts or int(time.time()),
            ),
        )
        connection.commit()

    def list_entities(self, space_id: str, etype: Optional[str] = None) -> List[sqlite3.Row]:
        """
        列出空间内实体。

        :param space_id: 记忆空间
        :param etype: 限定实体类型，None 表示全部
        :return: 数据行列表
        """
        connection = self.db.conn()
        if etype:
            rows = connection.execute(
                """
                select e.eid as eid, e.etype as etype, e.name as name, e.attrs as attrs
                from kg_entity as e
                where e.space_id = ? and e.etype = ? and e.is_active = 1
                """,
                (space_id, etype),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                select e.eid as eid, e.etype as etype, e.name as name, e.attrs as attrs
                from kg_entity as e
                where e.space_id = ? and e.is_active = 1
                """,
                (space_id,),
            ).fetchall()
        return rows

    # ------------------------------------------------------------
    # 关系（含冲突与权重演化）
    # ------------------------------------------------------------
    @staticmethod
    def _boost_amount(source_type: str) -> float:
        """证据分级：这条确认来自谁，决定基础增益的倍数。"""
        return float(config.BELIEF_BOOST_WEIGHTS.get(source_type or "", 0.6))

    @staticmethod
    def _boosted_confidence(current: float, source_type: str) -> float:
        """
        加固后的置信度。

        饱和增益：越接近 1.0，单次提升越小（乘 1 - current），
        避免同一句话被确认几次就到满分。证据权重来自 source_type。
        """
        gain = config.BELIEF_BOOST_CONFIDENCE * KGStore._boost_amount(source_type)
        if config.BELIEF_BOOST_SATURATION:
            gain *= max(0.0, 1.0 - float(current))
        return max(0.0, min(1.0, float(current) + gain))

    @staticmethod
    def _boosted_importance(current: float, source_type: str) -> float:
        """加固后的重要度（同样带饱和与证据分级）。"""
        gain = config.BELIEF_BOOST_IMPORTANCE * KGStore._boost_amount(source_type)
        if config.BELIEF_BOOST_SATURATION:
            gain *= max(0.0, 1.0 - float(current))
        return max(0.0, min(1.0, float(current) + gain))

    @staticmethod
    def _is_single_value(rel: str, relation_multi: bool, row_multi: bool) -> bool:
        """
        是否按单值维度处理（不同 tail 时推翻旧值）。

        规则：
        1. 任一方显式声明多值 → 共存；
        2. 关系名在多值白名单 → 共存（模型漏标时兜底）；
        3. 其余 → 单值，新值推翻旧值（保持既有语义）。
        """
        if relation_multi or row_multi:
            return False
        return rel not in config.BELIEF_MULTI_VALUE_RELS

    def upsert_relation(self, relation: KGRelation) -> Dict[str, Any]:
        """
        写入关系，并处理与既有信念的冲突。

        规则：
        - 若同一 (head_name, rel) 下已存在生效且 tail 不同的旧关系：
          · 双方都允许多值（multi_valued）→ 共存，互不推翻
            （"室友/朋友/喜欢的作品"这类维度天然可以有多个取值）
          · 任一方是单值 → 旧关系标记失效（被推翻）
            （"生日/主用语言"这类维度只能有一个当前值）
        - 若 tail 相同（重复确认同一信念）→ 置信度与重要性加权提升，本次不重复插入
          生产路径（archiver）的 rid 由三元组稳定生成，同一信念再次确认必然是 rid 命中，
          同样走这条加固分支
        - rid 已存在（含失效行）时 → on conflict 复活/更新该行，created=False

        :param relation: 关系对象
        :return: {"conflicts": [(旧值, 新值)], "boosted": bool, "created": bool, "coexisted": bool}
        """
        connection = self.db.conn()
        now = int(time.time())

        conflicts: List[Tuple[str, str]] = []
        boosted = False
        created = False
        coexisted = False

        # 查询同头同关系下已生效的记录
        existing = connection.execute(
            """
            select r.rid as rid, r.tail_name as tail_name, r.confidence as confidence,
                   r.importance as importance, r.multi_valued as multi_valued
            from kg_relation as r
            where r.space_id = ? and r.head_name = ? and r.rel = ? and r.is_active = 1
            """,
            (relation.space_id, relation.head_name, relation.rel),
        ).fetchall()

        for row in existing:
            if row["rid"] == relation.rid:
                # rid 命中 = 同一三元组再次确认（archiver 的 rid 由三元组决定）。
                # 之前这里是 continue —— 死分支：生产路径永远不会走进下面的
                # "tail 相同"加固逻辑，on conflict 又把权重原样覆盖回去，
                # 导致"重复确认会加固"只在测试里成立。
                if row["tail_name"] == relation.tail_name:
                    source = relation.source_type or "model_inferred"
                    confidence = self._boosted_confidence(row["confidence"], source)
                    importance = self._boosted_importance(row["importance"], source)
                    # 同一信念再次被确认时，多值属性按"或"合并：
                    # 一旦这个维度被判定过多值，就不再退化回单值推翻
                    multi = 1 if (relation.multi_valued or row["multi_valued"]) else 0
                    connection.execute(
                        """
                        update kg_relation
                        set confidence = ?, importance = ?, multi_valued = ?, update_ts = ?
                        where space_id = ? and rid = ?
                        """,
                        (confidence, importance, multi, now, relation.space_id, row["rid"]),
                    )
                    boosted = True
                # rid 相同但 tail 不同（手动复用 rid 的写法）：留给下方 on conflict 更新
                continue

            if row["tail_name"] == relation.tail_name:
                # 同一信念被再次确认：权重加固，本次不重复插入
                source = relation.source_type or "model_inferred"
                confidence = self._boosted_confidence(row["confidence"], source)
                importance = self._boosted_importance(row["importance"], source)
                multi = 1 if (relation.multi_valued or row["multi_valued"]) else 0
                connection.execute(
                    """
                    update kg_relation
                    set confidence = ?, importance = ?, multi_valued = ?, update_ts = ?
                    where space_id = ? and rid = ?
                    """,
                    (confidence, importance, multi, now, relation.space_id, row["rid"]),
                )
                boosted = True
            elif not self._is_single_value(
                relation.rel, bool(relation.multi_valued), bool(row["multi_valued"])
            ):
                # 白名单外的维度（或显式多值）：不同取值合法共存，旧行保持生效，
                # 本次照常插入新行。默认"宁可多记，不可误杀"。
                coexisted = True
            else:
                # 单值维度出现不同取值：旧信念被推翻
                # 同时标记 superseded 并补 valid_to，让"以前/曾经"能命中旧值，
                # 也让审计能区分"被取代"与"用户否决"。
                connection.execute(
                    """
                    update kg_relation
                    set is_active = 0, status = 'superseded', valid_to = ?, update_ts = ?
                    where space_id = ? and rid = ?
                    """,
                    (now, now, relation.space_id, row["rid"]),
                )
                conflicts.append((row["tail_name"], relation.tail_name))

        # 仅在没有被"重复确认"时才插入/更新本次记录，避免同一信念双份存在
        if not boosted:
            # on conflict (space_id, rid) 命中旧行（含失效行）时是"复活/更新"而非新建，
            # created 必须如实反映，否则统计会把旧信念复活当成新信念
            rid_existed = connection.execute(
                "select 1 from kg_relation as r where r.space_id = ? and r.rid = ?",
                (relation.space_id, relation.rid),
            ).fetchone()
            connection.execute(
                """
                insert into kg_relation
                    (space_id, rid, head_name, rel, tail_name, confidence, importance,
                     multi_valued, is_active, source_topic_id,
                     source_turn_id, source_type, status, valid_from, valid_to,
                     user_confirmed, create_ts, update_ts)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict (space_id, rid) do update set
                    tail_name = excluded.tail_name,
                    confidence = excluded.confidence,
                    importance = excluded.importance,
                    multi_valued = excluded.multi_valued,
                    is_active = excluded.is_active,
                    source_topic_id = excluded.source_topic_id,
                    source_turn_id = excluded.source_turn_id,
                    source_type = excluded.source_type,
                    status = excluded.status,
                    valid_from = excluded.valid_from,
                    valid_to = excluded.valid_to,
                    user_confirmed = excluded.user_confirmed,
                    update_ts = excluded.update_ts
                """,
                (
                    relation.space_id,
                    relation.rid,
                    relation.head_name,
                    relation.rel,
                    relation.tail_name,
                    max(0.0, min(1.0, relation.confidence)),
                    max(0.0, min(1.0, relation.importance)),
                    1 if relation.multi_valued else 0,
                    1 if relation.is_active else 0,
                    relation.source_topic_id,
                    relation.source_turn_id or "",
                    relation.source_type or "model_inferred",
                    relation.status or "active",
                    int(relation.valid_from or 0),
                    int(relation.valid_to or 0),
                    1 if relation.user_confirmed else 0,
                    relation.create_ts or now,
                    now,
                ),
            )
            created = not rid_existed

        connection.commit()
        return {
            "conflicts": conflicts,
            "boosted": boosted,
            "created": created,
            "coexisted": coexisted,
        }

    def list_relations(
        self, space_id: str, only_active: bool = True, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        列出该空间的 KG 关系（API 展示用）。

        :param space_id: 记忆空间
        :param only_active: 只取生效关系（False 时包含被推翻的历史行）
        :param limit: 条数上限
        :return: [{"rid","head","rel","tail","confidence","importance","multi_valued","is_active","source_topic_id"}]
        """
        sql = """
            select rid, head_name, rel, tail_name, confidence, importance,
                   multi_valued, is_active, source_topic_id, update_ts
            from kg_relation
            where space_id = ?
        """
        if only_active:
            sql += " and is_active = 1"
        sql += " order by importance desc, confidence desc limit ?"

        rows = self.db.conn().execute(sql, (space_id, int(limit))).fetchall()
        return [
            {
                "rid": row["rid"],
                "head": row["head_name"],
                "rel": row["rel"],
                "tail": row["tail_name"],
                "confidence": float(row["confidence"]),
                "importance": float(row["importance"]),
                "multi_valued": bool(row["multi_valued"]),
                "is_active": bool(row["is_active"]),
                "source_topic_id": row["source_topic_id"] or "",
                "update_ts": int(row["update_ts"] or 0),
            }
            for row in rows
        ]

    def query_by_text(
        self,
        space_id: str,
        text: str,
        limit: Optional[int] = None,
    ) -> List[str]:
        """
        根据用户输入做信念查询（实体名/尾值包含匹配 + 过去值检索）。

        这是"精确查询"而非向量相似：
        - 用户提到实体名或尾值 → 精确命中；
        - 没有匹配 → 回退到重要性最高的"自身核心信念"；
        - 对"以前/曾经/过去"的查询，返回过去值（见 query_past_beliefs）。

        :param space_id: 记忆空间
        :param text: 用户输入文本
        :param limit: 返回条数上限
        :return: 可直接注入 Prompt 的事实文本行
        """
        query_text = text or ""
        if config.PAST_CUE_PATTERN.search(query_text):
            return [
                self._format_fact(b)
                for b in self.query_past_beliefs(space_id, query_text, limit)
            ]

        connection = self.db.conn()
        limit = limit or config.KG_MAX_ROWS

        # 匹配池 = 生效实体名 + 关系尾值。尾值可能没登记成实体，
        # 只看实体表会让"只出现在关系里的取值"永远召回不了（spec §8 缺口 3）。
        names = {
            str(row["name"])
            for row in connection.execute(
                """
                select e.name as name
                from kg_entity as e
                where e.space_id = ? and e.is_active = 1
                """,
                (space_id,),
            ).fetchall()
            if row["name"]
        }
        names.update(
            str(row["tail_name"])
            for row in connection.execute(
                """
                select distinct r.tail_name as tail_name
                from kg_relation as r
                where r.space_id = ? and r.is_active = 1
                  and coalesce(r.lifecycle_state, 'active') != 'forgotten'
                """,
                (space_id,),
            ).fetchall()
            if row["tail_name"]
        )
        matched_names = {n for n in names if n in query_text}

        rows: List[sqlite3.Row]
        if matched_names:
            placeholders = ",".join(["?"] * len(matched_names))
            sql = f"""
                select r.head_name as head_name, r.rel as rel, r.tail_name as tail_name,
                        r.confidence as confidence, r.importance as importance
                from kg_relation as r
                where r.space_id = ? and r.is_active = 1
                  and coalesce(r.lifecycle_state, 'active') != 'forgotten'
                  and (r.head_name in ({placeholders}) or r.tail_name in ({placeholders}))
                order by r.importance desc, r.confidence desc
                limit ?
            """
            params = [space_id, *matched_names, *matched_names, limit]
            rows = connection.execute(sql, params).fetchall()
        else:
            # 没命中任何实体/尾值：回退到最重要的几条核心信念。
            rows = connection.execute(
                """
                select r.head_name as head_name, r.rel as rel, r.tail_name as tail_name,
                        r.confidence as confidence, r.importance as importance
                from kg_relation as r
                where r.space_id = ? and r.is_active = 1
                  and coalesce(r.lifecycle_state, 'active') != 'forgotten'
                order by r.importance desc, r.confidence desc
                limit ?
                """,
                (space_id, min(limit, 5)),
            ).fetchall()

        if not rows:
            return []

        def _format(row: sqlite3.Row, score: Optional[float] = None) -> str:
            suffix = f"，相关度 {score:.2f}" if score is not None else ""
            return (
                f"{row['head_name']} {row['rel']} {row['tail_name']}"
                f"（置信度 {float(row['confidence']):.2f}，"
                f"重要性 {float(row['importance']):.2f}{suffix}）"
            )

        if not matched_names:
            # 回退分支：核心信念直接全部返回，不做相关性过滤
            return [_format(row) for row in rows]

        # 相关性打分：尾值命中 1.0 > 头实体 0.9 > 关系名 0.8。
        # 必须拿用户查询文本比对 —— 早期版本用行内拼出的文本，导致永远满分。
        def _relevance(row: sqlite3.Row) -> float:
            head = str(row["head_name"] or "")
            rel = str(row["rel"] or "")
            tail = str(row["tail_name"] or "")
            if tail and tail in query_text:
                return 1.0
            if head and head in query_text:
                return 0.9
            if rel and rel in query_text:
                return 0.8
            return 0.0

        scored = [(row, score) for row in rows if (score := _relevance(row)) >= 0.5]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [_format(row, score) for row, score in scored]

    def _format_fact(self, belief: Dict[str, Any]) -> str:
        return (
            f"{belief['head']} {belief['rel']} {belief['tail']}"
            f"（置信度 {float(belief['confidence']):.2f}，重要性 {float(belief['importance']):.2f}，"
            f"valid_from={belief['valid_from']}, valid_to={belief['valid_to']}, "
            f"status={belief['status']}）"
        )

    def _current_tail(self, space_id: str, head_name: str, rel: str) -> str:
        """取同头同关系的当前生效尾值（用于补"现在值"）。"""
        connection = self.db.conn()
        row = connection.execute(
            """
            select r.tail_name as tail_name
            from kg_relation as r
            where r.space_id = ? and r.head_name = ? and r.rel = ? and r.is_active = 1
            order by r.update_ts desc
            limit 1
            """,
            (space_id, head_name, rel),
        ).fetchone()
        return row["tail_name"] if row else ""

    def query_past_beliefs(
        self,
        space_id: str,
        text: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询"过去值"（有效到今天之前的信念）。

        为什么要单独做：用户常问"以前/曾经/过去/上次"，检索必须能把
        "现在偏好"与"过去偏好"分开：
        - 现在值：valid_to > now（仍有效）
        - 过去值：valid_to <= now 的生效值 + 被取代的 superseded 值
        分开后，回答"以前喜欢吃什么"才能准确命中苹果，
        而不是被"现在喜欢西瓜"抢走。

        :param space_id: 记忆空间
        :param text: 查询文本（用于相关性筛选）
        :param limit: 返回条数上限
        :return: [{"head","rel","tail","confidence","importance","status","valid_to","current"}]
        """
        if not config.PAST_CUE_PATTERN.search(text):
            return []
        if limit is None:
            limit = config.OVERTURNED_MAX_ITEMS
        connection = self.db.conn()

        rows = connection.execute(
            """
            select r.head_name as head_name, r.rel as rel, r.tail_name as tail_name,
                    r.confidence as confidence, r.importance as importance,
                    r.status as status, r.valid_to as valid_to,
                    r.is_active as is_active
            from kg_relation as r
            where r.space_id = ? and r.status in ('active', 'superseded')
              and (r.is_active = 1 or r.status = 'superseded')
              and coalesce(r.lifecycle_state, 'active') != 'forgotten'
            order by r.importance desc, r.confidence desc
            limit ?
            """,
            (space_id, int(limit)),
        ).fetchall()

        now = int(time.time())
        items: List[Dict[str, Any]] = []
        for row in rows:
            # 过去值：被取代的行，或已经到期（valid_to 在现在之前）的生效行；
            # valid_to = 0 表示"仍然有效、没有到期"，不算过去值。
            is_past = row["status"] == "superseded" or (
                row["valid_to"] > 0 and row["valid_to"] <= now
            )
            if not is_past:
                continue
            current = self._current_tail(space_id, row["head_name"], row["rel"])
            items.append(
                {
                    "head": row["head_name"] or "",
                    "rel": row["rel"] or "",
                    "tail": row["tail_name"] or "",
                    "confidence": float(row["confidence"]),
                    "importance": float(row["importance"]),
                    "status": row["status"],
                    "valid_to": int(row["valid_to"] or 0),
                    "is_active": bool(row["is_active"]),
                    "current": current or "",
                }
            )
        return items

    def query_overturned(self, space_id: str, text: str = "", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        查询"最近被推翻的信念"（is_active = 0 的历史关系）。

        为什么要单独查这一路：
        - 生效关系只呈现"我现在信什么"，AI 感知不到"我改过主意"
        - 旧值虽然失效，但它解释了"为什么现在是这个值"，是因果链的一部分
        - 模型曾自己指出这个缺口：图里的信念在掉，但没有被推翻的标记

        取值策略：
        1. 优先取与本次输入相关的（头实体出现在用户问题里）
        2. 没有相关的，则取最近被推翻的几条（让 AI 至少知道自己最近改过什么）
        3. 每条都尽量补上"现在的值"，形成「曾被推翻：X（原值）→ 现为 Y」

        :param space_id: 记忆空间
        :param text: 用户输入文本（用于相关性筛选）
        :param limit: 返回条数上限
        :return: [{"head","rel","old","new","ts"}] 字典列表
        """
        if not config.SHOW_OVERTURNED_BELIEFS:
            return []

        limit = limit or config.OVERTURNED_MAX_ITEMS
        connection = self.db.conn()

        rows = connection.execute(
            """
            select r.head_name as head_name, r.rel as rel, r.tail_name as tail_name,
                   r.update_ts as update_ts
            from kg_relation as r
            where r.space_id = ? and r.is_active = 0
              and coalesce(r.lifecycle_state, 'active') != 'forgotten'
            order by r.update_ts desc
            limit 40
            """,
            (space_id,),
        ).fetchall()

        if not rows:
            return []

        # 先按相关性筛（头实体出现在输入里）
        related = [row for row in rows if row["head_name"] and row["head_name"] in text]
        candidates = related[:limit] if related else rows[:limit]

        connection = self.db.conn()
        items: List[Dict[str, Any]] = []
        for row in candidates:
            # 补齐"现在的值"：同头实体同关系的生效行
            current = connection.execute(
                """
                select r.tail_name as tail_name
                from kg_relation as r
                where r.space_id = ? and r.head_name = ? and r.rel = ? and r.is_active = 1
                order by r.update_ts desc
                limit 1
                """,
                (space_id, row["head_name"], row["rel"]),
            ).fetchone()

            items.append(
                {
                    "head": row["head_name"] or "",
                    "rel": row["rel"] or "",
                    "old": row["tail_name"] or "",
                    "new": (current["tail_name"] if current else "") or "",
                    "ts": int(row["update_ts"] or 0),
                }
            )

        return items

    def query_core_beliefs(self, space_id: str, importance_threshold: float = 0.75) -> List[Dict[str, Any]]:
        """
        查询"对自我最重要"的核心信念，用于生成人格快照。

        :param space_id: 记忆空间
        :param importance_threshold: 重要性阈值
        :return: 信念字典列表
        """
        connection = self.db.conn()
        rows = connection.execute(
            """
            select r.head_name as head_name, r.rel as rel, r.tail_name as tail_name,
                   r.confidence as confidence, r.importance as importance
            from kg_relation as r
            where r.space_id = ?
              and r.is_active = 1
              and r.importance >= ?
            -- 排序必须带上 confidence：只按 importance 排，三个月前那条 0.9
            -- 会永远占住快照前排，新近的高置信信念挤不进来，
            -- 快照反映的就成了"曾经的她"而不是"现在的她"。
            order by (r.confidence * r.importance) desc, r.confidence desc
            limit 12
            """,
            (space_id, importance_threshold),
        ).fetchall()

        return [
            {
                "statement": f"{row['head_name']} {row['rel']} {row['tail_name']}",
                "confidence": float(row["confidence"]),
                "importance": float(row["importance"]),
            }
            for row in rows
        ]

    def count_active_relations(self, space_id: str) -> int:
        """统计当前生效的关系条数，用于健康度观测。"""
        connection = self.db.conn()
        row = connection.execute(
            """
            select count(1) as cnt
            from kg_relation as r
            where r.space_id = ? and r.is_active = 1
            """,
            (space_id,),
        ).fetchone()
        return int(row["cnt"]) if row else 0

    # ------------------------------------------------------------
    # 信念查询与修正（P1：用户可纠正、可确认、可否决）
    # ------------------------------------------------------------
    def list_beliefs(
        self,
        space_id: str,
        status: Optional[str] = None,
        only_active: bool = True,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        列出该空间的信念（KG 关系）。

        :param space_id: 记忆空间
        :param status: 限定信念状态；None 表示全部
        :param only_active: 只取生效记录（False 时包含被推翻历史行）
        :param limit: 返回条数上限
        :return: 信念字典列表
        """
        connection = self.db.conn()
        sql = """
            select r.rid as rid, r.head_name as head_name, r.rel as rel,
                   r.tail_name as tail_name, r.confidence as confidence,
                   r.importance as importance, r.status as status,
                   r.valid_from as valid_from, r.valid_to as valid_to,
                   r.user_confirmed as user_confirmed, r.source_turn_id as source_turn_id,
                   r.source_type as source_type, r.is_active as is_active,
                   r.multi_valued as multi_valued, r.update_ts as update_ts
            from kg_relation as r
            where r.space_id = ?
        """
        if status:
            sql += " and r.status = ?"
        if only_active:
            sql += " and r.is_active = 1"
        sql += " order by r.importance desc, r.confidence desc limit ?"
        params: list = [space_id]
        if status:
            params.append(status)
        params.append(int(limit))
        rows = connection.execute(sql, params).fetchall()
        return [
            {
                "rid": row["rid"],
                "head": row["head_name"],
                "rel": row["rel"],
                "tail": row["tail_name"],
                "confidence": float(row["confidence"]),
                "importance": float(row["importance"]),
                "status": row["status"],
                "valid_from": int(row["valid_from"] or 0),
                "valid_to": int(row["valid_to"] or 0),
                "user_confirmed": bool(row["user_confirmed"]),
                "source_turn_id": row["source_turn_id"] or "",
                "source_type": row["source_type"] or "",
                "is_active": bool(row["is_active"]),
                "multi_valued": bool(row["multi_valued"]),
                "update_ts": int(row["update_ts"] or 0),
            }
            for row in rows
        ]

    def get_belief(self, space_id: str, rid: str) -> Optional[Dict[str, Any]]:
        """按 rid 取回单条信念。"""
        connection = self.db.conn()
        row = connection.execute(
            """
            select r.rid as rid, r.head_name as head_name, r.rel as rel,
                   r.tail_name as tail_name, r.confidence as confidence,
                   r.importance as importance, r.status as status,
                   r.valid_from as valid_from, r.valid_to as valid_to,
                   r.user_confirmed as user_confirmed, r.source_turn_id as source_turn_id,
                   r.source_type as source_type, r.is_active as is_active,
                   r.multi_valued as multi_valued, r.update_ts as update_ts
            from kg_relation as r
            where r.space_id = ? and r.rid = ?
            """,
            (space_id, rid),
        ).fetchone()
        if not row:
            return None
        return {
            "rid": row["rid"],
            "head": row["head_name"],
            "rel": row["rel"],
            "tail": row["tail_name"],
            "confidence": float(row["confidence"]),
            "importance": float(row["importance"]),
            "status": row["status"],
            "valid_from": int(row["valid_from"] or 0),
            "valid_to": int(row["valid_to"] or 0),
            "user_confirmed": bool(row["user_confirmed"]),
            "source_turn_id": row["source_turn_id"] or "",
            "source_type": row["source_type"] or "",
            "is_active": bool(row["is_active"]),
            "multi_valued": bool(row["multi_valued"]),
            "update_ts": int(row["update_ts"] or 0),
        }

    def confirm_belief(self, space_id: str, rid: str) -> bool:
        """
        用户手动确认一条信念（把状态置为已确认、标记生效、写审计）。

        :param space_id: 记忆空间
        :param rid: 信念 id
        :return: 是否成功
        """
        return bool(
            self.update_belief(space_id, rid, action="confirm", note="用户确认")[
                "updated"
            ]
        )

    def correct_belief(self, space_id: str, rid: str) -> bool:
        """
        用户手动纠正一条信念（把状态置为待验证，保留原值作对照）。

        :param space_id: 记忆空间
        :param rid: 信念 id
        :return: 是否成功
        """
        return bool(
            self.update_belief(space_id, rid, action="correct", note="用户纠正")[
                "updated"
            ]
        )

    def reject_belief(self, space_id: str, rid: str) -> bool:
        """
        用户否决一条信念（状态置为 rejected，保留原值作对照）。

        :param space_id: 记忆空间
        :param rid: 信念 id
        :return: 是否成功
        """
        return bool(
            self.update_belief(space_id, rid, action="reject", note="用户否决")[
                "updated"
            ]
        )

    def replace_belief(
        self,
        space_id: str,
        rid: str,
        head: str,
        rel: str,
        tail: str,
        confidence: Optional[float] = None,
        importance: Optional[float] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """
        用户手动填写纠正内容：用新的主语/关系/宾语替换旧信念。

        - 旧信念标记为 superseded 并保留历史（不物理删除）
        - 新信念按三元组生成稳定 rid，状态 active、来源 user_corrected
        - 写入 belief_correction 审计记录

        :return: {"updated", "rid", "old_rid", "replaced"}
        """
        connection = self.db.conn()
        old = connection.execute(
            "select * from kg_relation where space_id = ? and rid = ?",
            (space_id, rid),
        ).fetchone()
        if not old:
            return {"updated": False, "rid": "", "old_rid": rid, "replaced": False}

        new_head = (head or "").strip() or (old["head_name"] or "")
        new_rel = (rel or "").strip() or (old["rel"] or "")
        new_tail = (tail or "").strip() or (old["tail_name"] or "")
        if not (new_head and new_rel and new_tail):
            return {"updated": False, "rid": rid, "old_rid": rid, "replaced": False}

        now = int(time.time())
        same = (
            new_head == (old["head_name"] or "")
            and new_rel == (old["rel"] or "")
            and new_tail == (old["tail_name"] or "")
        )

        if same:
            connection.execute(
                """
                update kg_relation
                set confidence = ?, importance = ?, status = 'active',
                    is_active = 1, user_confirmed = 1, source_type = 'user_corrected',
                    update_ts = ?
                where space_id = ? and rid = ?
                """,
                (
                    max(0.0, min(1.0, float(confidence if confidence is not None else old["confidence"]))),
                    max(0.0, min(1.0, float(importance if importance is not None else old["importance"]))),
                    now,
                    space_id,
                    rid,
                ),
            )
            new_rid = rid
        else:
            # 旧信念：标记被取代，保留历史，方便回看
            connection.execute(
                """
                update kg_relation
                set is_active = 0, status = 'superseded', valid_to = ?, update_ts = ?
                where space_id = ? and rid = ?
                """,
                (now, now, space_id, rid),
            )
            new_rid = hashlib.md5(
                f"{space_id}|{new_head}|{new_rel}|{new_tail}".encode("utf-8")
            ).hexdigest()[:12]
            existing = connection.execute(
                "select 1 from kg_relation where space_id = ? and rid = ?",
                (space_id, new_rid),
            ).fetchone()
            new_conf = max(
                0.0,
                min(
                    1.0,
                    float(confidence if confidence is not None else old["confidence"]),
                ),
            )
            new_imp = max(
                0.0,
                min(
                    1.0,
                    float(importance if importance is not None else old["importance"]),
                ),
            )
            if existing:
                connection.execute(
                    """
                    update kg_relation
                    set head_name = ?, rel = ?, tail_name = ?, confidence = ?,
                        importance = ?, is_active = 1, status = 'active',
                        user_confirmed = 1, source_type = 'user_corrected',
                        valid_to = 0, update_ts = ?
                    where space_id = ? and rid = ?
                    """,
                    (
                        new_head,
                        new_rel,
                        new_tail,
                        new_conf,
                        new_imp,
                        now,
                        space_id,
                        new_rid,
                    ),
                )
            else:
                connection.execute(
                    """
                    insert into kg_relation
                        (space_id, rid, head_name, rel, tail_name, confidence, importance,
                         multi_valued, is_active, source_topic_id, source_turn_id,
                         source_type, status, valid_from, valid_to, user_confirmed,
                         create_ts, update_ts)
                    values (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'user_corrected', 'active',
                            ?, 0, 1, ?, ?)
                    """,
                    (
                        space_id,
                        new_rid,
                        new_head,
                        new_rel,
                        new_tail,
                        new_conf,
                        new_imp,
                        1 if old["multi_valued"] else 0,
                        old["source_topic_id"],
                        old["source_turn_id"] or "",
                        now,
                        now,
                        now,
                    ),
                )

        self._append_correction(
            space_id,
            "correct",
            note
            or f"手动纠正：{old['head_name']} {old['rel']} {old['tail_name']} → "
            f"{new_head} {new_rel} {new_tail}",
            {
                "rid": rid,
                "head_name": old["head_name"] if old else "",
                "rel": old["rel"] if old else "",
                "old_tail": old["tail_name"] if old else "",
                "new_tail": new_tail,
            },
        )
        connection.commit()
        return {
            "updated": True,
            "rid": new_rid,
            "old_rid": rid,
            "replaced": new_rid != rid,
        }

    def update_belief(
        self,
        space_id: str,
        rid: str,
        action: Optional[str] = None,
        confidence: Optional[float] = None,
        importance: Optional[float] = None,
        status: Optional[str] = None,
        user_confirmed: Optional[bool] = None,
        valid_from: Optional[int] = None,
        valid_to: Optional[int] = None,
        source_turn_id: Optional[str] = None,
        source_type: Optional[str] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """
        更新（或回填）一条信念的字段。

        :param space_id: 记忆空间
        :param rid: 信念 id
        :param action: confirm / correct / reject（缺省时只按参数更新）
        :param confidence/importance/status/valid_from/valid_to：新值
        :param user_confirmed: 用户是否手动确认
        :param source_turn_id/source_type: 溯源字段（来自抽取结果）
        :param note: 备注
        :return: 更新结果字典
        """
        connection = self.db.conn()
        result: Dict[str, Any] = {
            "updated": False,
            "action": action,
            "note": note,
        }
        if not connection.execute(
            "select 1 from kg_relation where space_id = ? and rid = ?",
            (space_id, rid),
        ).fetchone():
            return result

        updates: List[Tuple[str, Any]] = [
            ("confidence", confidence),
            ("importance", importance),
            ("status", status),
            (
                "user_confirmed",
                int(user_confirmed) if user_confirmed is not None else None,
            ),
            ("valid_from", valid_from),
            ("valid_to", valid_to),
            ("source_turn_id", source_turn_id),
            ("source_type", source_type),
        ]
        for column, value in updates:
            if value is None:
                continue
            connection.execute(
                f"update kg_relation set {column} = ?, update_ts = ?"
                " where space_id = ? and rid = ?",
                (value, int(time.time()), space_id, rid),
            )

        # 用户动作落审计表：确认 → active + user_confirmed；纠正 → candidate；否决 → rejected
        if action == "confirm":
            connection.execute(
                "update kg_relation set status = 'active', user_confirmed = 1,"
                " is_active = 1, update_ts = ? where space_id = ? and rid = ?",
                (int(time.time()), space_id, rid),
            )
        elif action == "correct":
            connection.execute(
                "update kg_relation set status = 'candidate', user_confirmed = 0,"
                " update_ts = ? where space_id = ? and rid = ?",
                (int(time.time()), space_id, rid),
            )
        elif action == "reject":
            connection.execute(
                "update kg_relation set status = 'rejected', is_active = 0,"
                " update_ts = ? where space_id = ? and rid = ?",
                (int(time.time()), space_id, rid),
            )

        if action:
            row = connection.execute(
                "select head_name, rel, tail_name from kg_relation"
                " where space_id = ? and rid = ?",
                (space_id, rid),
            ).fetchone()
            self._append_correction(
                space_id,
                action,
                note or f"用户{action}",
                {
                    "rid": rid,
                    "head_name": row["head_name"] if row else "",
                    "rel": row["rel"] if row else "",
                    "old_tail": row["tail_name"] if row else "",
                    "new_tail": row["tail_name"] if row else "",
                },
            )

        result["updated"] = True
        result["action"] = action or "update"
        connection.commit()
        return result

    def _append_correction(
        self,
        space_id: str,
        action: str,
        note: str = "",
        relation: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        写一条信念纠正审计记录（confirm / correct / reject）。

        :param space_id: 记忆空间
        :param action: 动作类型
        :param note: 备注
        :param relation: 相关信念信息（rid / head_name / rel / old_tail / new_tail）
        :return: 写入的记录列表
        """
        from cognitive.models import new_id

        relation = relation or {}
        now = int(time.time())
        record_id = new_id("clr")
        connection = self.db.conn()
        connection.execute(
            """
            insert into belief_correction
                (space_id, correction_id, rid, head_name, rel, old_tail, new_tail,
                 action, note, create_ts)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                space_id,
                record_id,
                relation.get("rid", ""),
                relation.get("head_name", ""),
                relation.get("rel", ""),
                relation.get("old_tail", ""),
                relation.get("new_tail", ""),
                action,
                note or "",
                now,
            ),
        )
        connection.commit()
        return [
            {
                "correction_id": record_id,
                "rid": relation.get("rid", ""),
                "action": action,
                "note": note or "",
                "create_ts": now,
            }
        ]

    def list_corrections(
        self, space_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        列出信念纠正审计记录（最新的在前）。

        :param space_id: 记忆空间
        :param limit: 条数上限
        :return: 审计记录列表
        """
        connection = self.db.conn()
        rows = connection.execute(
            """
            select correction_id, rid, head_name, rel, old_tail, new_tail,
                   action, note, create_ts
            from belief_correction
            where space_id = ?
            order by create_ts desc
            limit ?
            """,
            (space_id, int(limit)),
        ).fetchall()
        return [
            {
                "correction_id": row["correction_id"],
                "rid": row["rid"],
                "head": row["head_name"],
                "rel": row["rel"],
                "old_tail": row["old_tail"],
                "new_tail": row["new_tail"],
                "action": row["action"],
                "note": row["note"],
                "create_ts": int(row["create_ts"] or 0),
            }
            for row in rows
        ]

    def clear_belief(self, space_id: str, rid: str) -> bool:
        """
        把一条已失效信念标记为未生效（回滚）。

        :param space_id: 记忆空间
        :param rid: 信念 id
        :return: 是否成功
        """
        connection = self.db.conn()
        cursor = connection.execute(
            """
            update kg_relation set is_active = 0, update_ts = ?
            where space_id = ? and rid = ?
            """,
            (int(time.time()), space_id, rid),
        )
        connection.commit()
        return cursor.rowcount > 0
