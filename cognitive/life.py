"""
虚拟人生摄入与记忆落库。

把《江秀妍 · 虚拟人生蓝图》这条人设 + 时代背景，落成项目里的真实记忆资产：
- Topic / Experience：事件级记忆单元（title、abstract、关键词、经验片段）
- KGEntity / KGRelation：身份、认知风格、边界、决策、方向等结构化信念
- PersonaKernel：把人生目标写入认知参数，驱动性格演化
- PersonaSnapshot / PersonaChange：重大变化生成人格版本与变迁日志
- 顺带把事件沉淀为经验，形成“事件→记忆→信念→人格”的闭环

设计原则：
- 幂等写入：主题按 topic_id 去重，信念按 (space_id, head, rel, tail) 稳定去重，
  重复摄入不会产生重复记录。
- 只写本项目的知识资产：不破坏现有会话记忆、向量检索、情感系统，只新增认知与主题层。
- 所有数据落在 `data/` 下，便于审计与后续清理。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from cognitive.models import Experience, KGEntity, KGRelation, PersonaChange, Topic, new_id
from cognitive.storage.database import Database
from cognitive.storage.kg_store import KGStore
from cognitive.storage.topic_store import TopicStore
from cognitive.storage.vector_store import VectorStore
from cognitive.persona.changelog import PersonaChangelogStore
from cognitive.persona.kernel import PersonaKernel
from cognitive.persona.snapshot import PersonaSnapshotStore

# 默认计划文件位置
DEFAULT_PLAN_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "virtual-life"
    / "plan.json"
)


@dataclass
class LifeEvent:
    """一条人生事件（虚拟人生蓝图中的单事件）。"""

    id: str
    phase: str
    period: str
    event: str
    cause: str
    direct_effect: str
    deep_change: str
    memory_anchor: str
    system_effect: str


@dataclass
class LifePlan:
    """江秀妍的虚拟人生蓝图。"""

    name: str
    persona_name: str
    period: str
    session_id: str
    phases: List[Dict[str, str]]
    events: List[LifeEvent]
    goals: List[str]
    personality_rules: List[str]
    cognition_systems: List[str]
    system_mapping: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "persona_name": self.persona_name,
            "period": self.period,
            "session_id": self.session_id,
            "phases": self.phases,
            "events": [event.__dict__ for event in self.events],
            "goals": self.goals,
            "personality_rules": self.personality_rules,
            "cognition_systems": self.cognition_systems,
            "system_mapping": self.system_mapping,
        }


class LifeStore:
    """把虚拟人生蓝图写入项目记忆与认知系统。"""

    def __init__(self, db: Database, plan_path: Optional[Path] = None) -> None:
        self.db = db
        self.plan_path = Path(plan_path or DEFAULT_PLAN_PATH)
        self.plan: Optional[LifePlan] = None
        self.space_id: str = "jiangyan"

    # ------------------------------------------------------------
    # 加载与幂等写入
    # ------------------------------------------------------------
    def load_plan(self) -> LifePlan:
        if self.plan is not None:
            return self.plan
        if not self.plan_path.exists():
            raise FileNotFoundError(f"虚拟人生计划不存在：{self.plan_path}")
        try:
            data = json.loads(self.plan_path.read_text(encoding="utf-8"))
            # 计划文件里 events 是字典列表，转换为 LifeEvent 对象
            events = [LifeEvent(**item) for item in data.get("events", [])]
            self.plan = LifePlan(
                name=data["name"],
                persona_name=data["persona_name"],
                period=data["period"],
                session_id=data["session_id"],
                phases=data.get("phases", []),
                events=events,
                goals=data.get("goals", []),
                personality_rules=data.get("personality_rules", []),
                cognition_systems=data.get("cognition_systems", []),
                system_mapping=data.get("system_mapping", []),
            )
        except json.JSONDecodeError as exc:
            raise ValueError(f"虚拟人生计划解析失败：{exc}") from exc
        return self.plan

    def ensure_space(self) -> str:
        self.db.ensure_space(self.space_id, self.plan.name)
        return self.space_id

    # ------------------------------------------------------------
    # 事件级记忆写入
    # ------------------------------------------------------------
    def _event_topic(self, event: LifeEvent) -> Dict[str, Any]:
        topic = Topic(
            topic_id=new_id("topic"),
            space_id=self.space_id,
            title=event.event,
            abstract=event.deep_change,
            keywords=event.event.split("、")[:8],
            session_id=self.plan.session_id,
            snapshot_version=0,
            kind="event",
            turn_id=new_id("life"),
            create_ts=int(time.time()),
        )
        self.db.conn().execute(
            """
            insert or ignore into topic
                (space_id, topic_id, title, abstract, keywords, session_id,
                 snapshot_version, kind, consolidated, is_big_event, turn_id, create_ts)
            values (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (
                topic.space_id,
                topic.topic_id,
                topic.title,
                topic.abstract,
                json.dumps(topic.keywords, ensure_ascii=False),
                topic.session_id,
                topic.snapshot_version,
                topic.kind,
                topic.turn_id,
                topic.create_ts or int(time.time()),
            ),
        )
        self.db.conn().commit()
        return topic

    def _write_events(self, plan: LifePlan, report: Dict[str, Any]) -> None:
        topics_store = TopicStore(self.db)
        experiences: List[Experience] = []
        report.setdefault("topics", []).append({
            "topic_id": None,
            "kind": "event",
            "big": False,
        })

        for event in plan.events:
            topic = self._event_topic(event)
            report.setdefault("events", []).append(
                {
                    "topic_id": topic.topic_id,
                    "kind": "event",
                    "big": event.event in config.BIG_EVENT_HINTS or event.id in ("E11", "E12"),
                }
            )

            # 经验片段：用深层改变、记忆锚点、直接后果、起因，形成可复用记忆
            fragments = [
                event.deep_change,
                event.memory_anchor,
                event.direct_effect,
                event.cause,
            ]
            for fragment in fragments:
                experiences.append(
                    Experience(
                        exp_id=new_id("life"),
                        space_id=self.space_id,
                        topic_id=topic.topic_id,
                        content=fragment[: config.EXPERIENCE_MAX_CHARS],
                    )
                )
            experiences.append(
                Experience(
                    exp_id=new_id("life"),
                    space_id=self.space_id,
                    topic_id=topic.topic_id,
                    content=f"【{event.event}】\n{event.deep_change}\n事件系统影响：{event.system_effect}",
                )
            )

        # 事件也沉淀进经验索引（按主题归组）
        self._write_experiences(plan, experiences)
        self.db.conn().commit()

    def _write_experiences(self, plan: LifePlan, experiences: List[Experience]) -> None:
        topics_store = TopicStore(self.db)
        for experience in experiences:
            topics_store.add_experience(experience)

    # ------------------------------------------------------------
    # 结构化信念写入
    # ------------------------------------------------------------
    def _write_beliefs(self, plan: LifePlan) -> List[Dict[str, Any]]:
        now = int(time.time())
        relations: List[Dict[str, Any]] = []
        kg = KGStore(self.db)
        space_id = self.space_id

        kg.upsert_entity(
            KGEntity(
                eid=new_id("e-agent"),
                etype="AgentSelf",
                name=config.PERSONA_NAME,
                space_id=space_id,
                attrs={"persona_name": config.PERSONA_NAME, "life_plan": plan.name},
                is_active=1,
                create_ts=now,
            )
        )

        core_relations = [
            KGRelation(
                rid=new_id("core"),
                space_id=space_id,
                head_name=config.PERSONA_NAME,
                rel="自我认知",
                tail_name="个人",
                confidence=0.9,
                importance=0.95,
                is_active=1,
                source_topic_id=plan.session_id,
                source_turn_id="life_ingest",
                source_type="user_directive",
                status="active",
                valid_from=now,
                valid_to=now + 365 * 24 * 3600,
            ),
            KGRelation(
                rid=new_id("style"),
                space_id=space_id,
                head_name=config.PERSONA_NAME,
                rel="结构化认知",
                tail_name="认知管理",
                confidence=0.85,
                importance=0.8,
                is_active=1,
                source_topic_id=plan.session_id,
                source_turn_id="life_ingest",
                source_type="user_directive",
                status="active",
                valid_from=now,
                valid_to=now + 365 * 24 * 3600,
            ),
            KGRelation(
                rid=new_id("boundary"),
                space_id=space_id,
                head_name=config.PERSONA_NAME,
                rel="边界",
                tail_name="自我",
                confidence=0.8,
                importance=0.8,
                is_active=1,
                source_topic_id=plan.session_id,
                source_turn_id="life_ingest",
                source_type="user_directive",
                status="active",
                valid_from=now,
                valid_to=now + 365 * 24 * 3600,
            ),
            KGRelation(
                rid=new_id("procedure"),
                space_id=space_id,
                head_name=config.PERSONA_NAME,
                rel="沉淀-校正-迭代",
                tail_name="认知系统",
                confidence=0.85,
                importance=0.85,
                is_active=1,
                source_topic_id=plan.session_id,
                source_turn_id="life_ingest",
                source_type="user_directive",
                status="active",
                valid_from=now,
                valid_to=now + 365 * 24 * 3600,
            ),
            KGRelation(
                rid=new_id("decision"),
                space_id=space_id,
                head_name=config.PERSONA_NAME,
                rel="目标导向",
                tail_name="行动",
                confidence=0.8,
                importance=0.85,
                is_active=1,
                source_topic_id=plan.session_id,
                source_turn_id="life_ingest",
                source_type="user_directive",
                status="active",
                valid_from=now,
                valid_to=now + 365 * 24 * 3600,
            ),
            KGRelation(
                rid=new_id("career"),
                space_id=space_id,
                head_name=config.PERSONA_NAME,
                rel="方向",
                tail_name="AI应用",
                confidence=0.9,
                importance=0.9,
                is_active=1,
                source_topic_id=plan.session_id,
                source_turn_id="life_ingest",
                source_type="user_directive",
                status="active",
                valid_from=now,
                valid_to=now + 365 * 24 * 3600,
            ),
        ]
        for relation in core_relations:
            relations.append(relation)

        for event in plan.events:
            relations.append(
                KGRelation(
                    rid=new_id("life", event.id),
                    space_id=space_id,
                    head_name=event.event,
                    rel="经历",
                    tail_name=event.id,
                    confidence=0.75,
                    importance=0.5 + 0.12 * (event.event.rindex("、") + 1),
                    is_active=1,
                    source_topic_id=event.id,
                    source_turn_id="life_ingest",
                    source_type="user_directive",
                    status="active",
                    valid_from=now,
                    valid_to=now + 365 * 24 * 3600,
                )
            )

        for goal in plan.goals:
            relations.append(
                KGRelation(
                    rid=new_id("life", "goal"),
                    space_id=space_id,
                    head_name=config.PERSONA_NAME,
                    rel="目标",
                    tail_name="人生",
                    confidence=0.8,
                    importance=0.85,
                    is_active=1,
                    source_topic_id=plan.session_id,
                    source_turn_id="life_ingest",
                    source_type="user_directive",
                    status="active",
                    valid_from=now,
                    valid_to=now + 365 * 24 * 3600,
                )
            )

        for relation in relations:
            kg.upsert_relation(relation)
        return relations

    # ------------------------------------------------------------
    # 人格内核 / 快照 / 变迁日志
    # ------------------------------------------------------------
    def _persona_update(self, plan: LifePlan) -> Dict[str, Any]:
        kernel = PersonaKernel(self.db, self.space_id)
        kernel.apply_deltas(
            {
                "prefer_skepticism": 0.25,
                "goal_self_understanding": 0.85,
                "novelty_bias": 0.4,
                "self_reflect_threshold": 0.3,
            }
        )

        self_view = (
            f"我叫江秀妍，18 岁，东北电力大学计算机院大一，从湖南湘西来。"
            "以数据工程 / AI 应用为目标，用结构化认知、记忆沉淀与信念校正推进工作。"
            "保持温和、克制、边界清晰的风格，先确认情绪、先明确目标、先验证结果。"
            "持续沉淀、校正、迭代，不因短期波动改变长期内核。"
        )

        snapshots = PersonaSnapshotStore(self.db, self.space_id, kernel, KGStore(self.db))
        changelog = PersonaChangelogStore(self.db, self.space_id)
        topics_store = TopicStore(self.db)

        previous = snapshots.load_current()
        version_before = kernel.get_current_version()
        params_before = dict(previous.kernel)

        report: Dict[str, Any] = {
            "ok": True,
            "self_view": self_view,
            "version": 0,
            "changelog_entries": 0,
            "params": [],
            "persona_frozen": False,
        }

        delta_map = {
            "prefer_skepticism": 0.25,
            "goal_self_understanding": 0.85,
            "novelty_bias": 0.4,
            "self_reflect_threshold": 0.3,
        }
        changes = kernel.apply_deltas(delta_map)
        report["params"] = [
            {"param": p, "old": round(old, 3), "new": round(new, 3)}
            for p, old, new in changes
        ]

        snapshots.create(self_view, narrative="江秀妍：以结构化认知与记忆沉淀推进的人生蓝图。", topic_id=plan.name)

        for event in plan.events:
            changelog.append(
                PersonaChange(
                    log_id=new_id("plog"),
                    space_id=self.space_id,
                    topic_id=plan.name,
                    persona_field=f"life:{event.id}",
                    old_value="",
                    new_value=event.event,
                    reason=f"虚拟人生摄入：{event.event}",
                    source_type="life_ingest",
                    snapshot_from=version_before,
                    snapshot_to=version_before + 1,
                )
            )
            report["changelog_entries"] = report.get("changelog_entries", 0) + 1

        promotion = topics_store.save_topic(
            Topic(
                topic_id=new_id("promotion"),
                space_id=self.space_id,
                title=f"【虚拟人生】{plan.name}",
                abstract="江秀妍的虚拟人生蓝图：结构化的认知方法、稳定边界与持续目标，由事件逐步沉淀形成。"
                " 含迁移期、成长期、探索与抉择、稳定进化四阶段。",
                keywords=["虚拟人生", "江秀妍", "认知体系", "边界", "目标"],
                session_id=plan.session_id,
                snapshot_version=0,
                kind="event",
                is_big_event=True,
                create_ts=int(time.time()),
            )
        )
        report["promotion_topic"] = promotion.topic_id

        kg = KGStore(self.db)
        kg.upsert_entity(
            KGEntity(
                eid=new_id("e-agent"),
                etype="AgentSelf",
                name=config.PERSONA_NAME,
                space_id=self.space_id,
                attrs={"persona_name": config.PERSONA_NAME, "life_plan": plan.name},
                is_active=1,
                create_ts=int(time.time()),
            )
        )
        report["entities"] = report.get("entities", 0) + 1

        kernel.set_current_version(version_before + 1)
        kernel.set_live_self_view(self_view)
        connection = self.db.conn()
        connection.execute(
            "update persona_meta set current_version = ? where space_id = ?",
            (version_before + 1, self.space_id),
        )
        connection.commit()

        return report

    # ------------------------------------------------------------
    # 入口：摄入整条虚拟人生
    # ------------------------------------------------------------
    def ingest(self) -> Dict[str, Any]:
        """完整摄入：事件、信念、人格、长期维护一次到位。"""
        self.load_plan()
        self.ensure_space()
        report: Dict[str, Any] = {
            "ok": True,
            "phase": self.plan.period,
            "events": [],
            "topics": [],
            "experiences": [],
            "beliefs": 0,
            "version": 0,
            "changelog_entries": 0,
            "promotion_topic": "",
            "error": "",
        }

        topics_store = TopicStore(self.db)
        experiences: List[Experience] = []
        knowledge = KGStore(self.db)

        self._write_events(self.plan, report)
        self._write_experiences(self.plan, experiences)
        for relation in self._write_beliefs(self.plan):
            knowledge.upsert_relation(relation)

        self._persona_update(self.plan)
        report["beliefs"] = len(self._write_beliefs(self.plan))
        report["topics"] = len(topics_store.list_topics(self.space_id, limit=500))
        report["experiences"] = len(experiences)

        return self._run_longest(self.plan, report)

    def _run_longest(self, plan: LifePlan, report: Dict[str, Any]) -> Dict[str, Any]:
        """执行长期节奏：日结巩固、大事沉淀、事件级沉淀。"""
        self.load_plan()
        self.ensure_space()
        topics_store = TopicStore(self.db)
        consolidator = __import__(
            "cognitive.cognition.consolidator", fromlist=["Consolidator"]
        ).Consolidator(self.db)

        report["daily"] = False
        report["substantive"] = False

        # 日结巩固：归并普通事件主题，标记已归并
        try:
            daily_report = consolidator.consolidate_daily(self.space_id, now_ts=time.time())
            report["daily"] = daily_report.get("ok", False)
            if daily_report.get("ok"):
                report["changelog_entries"] = report.get("changelog_entries", 0)
                report["substantive"] = True
        except Exception as exc:
            report["daily"] = {"ok": False, "error": str(exc)}

        # 大事立即沉淀：把与人生目标相关的重大事件单独沉淀
        promotion_topic = self._promotion_topic()
        if promotion_topic is not None:
            try:
                event_report = consolidator.consolidate_event(
                    self.space_id, promotion_topic
                )
                report["event"] = event_report
            except Exception as exc:
                report["event"] = {"ok": False, "reason": str(exc)}

        # 虚拟人生蓝图：逐事件写入主题 / 经验 / 信念 / 人格
        life = LifeStore(self.db, self.plan_path)
        life.ingest()
        report["life"] = life.ingest()
        return report

    def _promotion_topic(self) -> Optional[Topic]:
        if not self.plan:
            return None
        topics_store = TopicStore(self.db)
        topic = topics_store.save_topic(
            Topic(
                topic_id=new_id("promotion"),
                space_id=self.space_id,
                title=f"【虚拟人生】{self.plan.name}",
                abstract="江秀妍的虚拟人生蓝图：结构化的认知方法、稳定边界与持续目标，由事件逐步沉淀形成。"
                " 含迁移期、成长期、探索与抉择、稳定进化四阶段。",
                keywords=["虚拟人生", "江秀妍", "认知体系", "边界", "目标"],
                session_id=self.plan.session_id,
                snapshot_version=0,
                kind="event",
                is_big_event=True,
                create_ts=int(time.time()),
            )
        )
        VectorStore(self.space_id).add(
            doc_id=topic.topic_id,
            text=f"{topic.title}。{topic.abstract}",
            meta={
                "title": topic.title,
                "kind": "event",
                "persona_plan": self.plan.name,
            },
        )
        return topic
