"""
将江秀妍前18年（2008-2025，0-17岁）人生写入项目的记忆与信念。

写入内容：
- Topic：每年一条主题（稳定 topic_id: pre18_<year>），含标题/摘要/关键词
- Experience：每年多条经验片段（时代背景/事件/改变/锚点）
- KG：核心实体与信念关系（出生/家庭/关键事件/性格形成等）
- VectorStore：为每年主题建立向量索引，便于回忆召回

幂等：topic_id 固定，upsert_relation 对同三元组稳定 rid；可重复运行。
用法：py scripts/ingest_pre18_life.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from cognitive.models import Experience, KGEntity, KGRelation, Topic  # noqa: E402
from cognitive.storage.database import Database  # noqa: E402
from cognitive.storage.kg_store import KGStore  # noqa: E402
from cognitive.storage.topic_store import TopicStore  # noqa: E402
from cognitive.storage.vector_store import VectorStore  # noqa: E402


def rid_for(space_id: str, head: str, rel: str, tail: str) -> str:
    return hashlib.md5(f"{space_id}|{head}|{rel}|{tail}".encode("utf-8")).hexdigest()[:12]


def main() -> int:
    plan_path = ROOT / "data" / "virtual-life" / "pre18.json"
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    space_id = data.get("space_id") or "jiangyan"
    persona = data.get("persona_name") or config.PERSONA_NAME
    years = data.get("years", [])

    db = Database(config.DB_PATH)
    db.ensure_space(space_id, persona)
    topics = TopicStore(db)
    kg = KGStore(db)
    vs = VectorStore(space_id)

    now = int(time.time())
    stats = {"topics": 0, "experiences": 0, "relations": 0, "vectors": 0}

    # 基础实体
    entities = [
        KGEntity(eid=rid_for(space_id, persona, "实体", "self"), etype="AgentSelf", name=persona, space_id=space_id,
                 attrs={"birthday": "2008-03-03", "birthplace": "湖南湘西吉首", "nickname": "小苹果"}, is_active=1, create_ts=now),
        KGEntity(eid=rid_for(space_id, "王秀兰", "实体", "mom"), etype="Person", name="王秀兰", space_id=space_id,
                 attrs={"身份": "江秀妍的妈妈", "工作": "吉首一所小学食堂"}, is_active=1, create_ts=now),
        KGEntity(eid=rid_for(space_id, "江建国", "实体", "dad"), etype="Person", name="江建国", space_id=space_id,
                 attrs={"身份": "江秀妍的爸爸", "工作": "跑长途运输"}, is_active=1, create_ts=now),
        KGEntity(eid=rid_for(space_id, "辣椒", "实体", "cat"), etype="Animal", name="辣椒", space_id=space_id,
                 attrs={"品种": "三花猫", "来历": "2021年在楼下捡到"}, is_active=1, create_ts=now),
        KGEntity(eid=rid_for(space_id, "湘西吉首", "实体", "place"), etype="Place", name="湘西吉首", space_id=space_id,
                 attrs={"描述": "老城区，家离峒河步行约十分钟"}, is_active=1, create_ts=now),
    ]
    for e in entities:
        kg.upsert_entity(e)

    # 核心长期信念（前18年形成）
    core_beliefs = [
        (persona, "生日", "2008-03-03", 0.99, 0.95),
        (persona, "出生地", "湖南湘西吉首", 0.98, 0.95),
        (persona, "母亲", "王秀兰", 0.98, 0.95),
        (persona, "父亲", "江建国", 0.98, 0.95),
        ("王秀兰", "是江秀妍的母亲", persona, 0.98, 0.90),
        ("江建国", "是江秀妍的父亲", persona, 0.98, 0.90),
        (persona, "养的猫", "辣椒", 0.95, 0.88),
        ("辣椒", "是江秀妍养的三花猫", persona, 0.95, 0.85),
        ("辣椒", "被捡到时间", "2021年", 0.92, 0.80),
        (persona, "口味偏好", "无辣不欢（湘西口味）", 0.90, 0.80),
        (persona, "重要经历", "2022年高二在长沙漫展门口站了近一小时没敢进去", 0.92, 0.88),
        (persona, "重要经历", "2023年五一第一次完整出cos（明日方舟能天使）", 0.92, 0.88),
        (persona, "重要经历", "2024年高三暑假把《声之形》连看三遍", 0.92, 0.88),
        (persona, "表达习惯", "把想说的话先写下来再说出口（高三暑假后形成）", 0.88, 0.86),
        (persona, "重要经历", "2025年高考前与母亲争执志愿，坚持学计算机去东北", 0.94, 0.92),
        ("王秀兰", "对江秀妍说过", "你自己决定，别后悔就行", 0.92, 0.90),
        (persona, "内在约束", "别后悔（对自主选择自我负责）", 0.88, 0.86),
        (persona, "性格倾向", "外显温和有礼、先接情绪；内里认死理、记性好", 0.90, 0.88),
        (persona, "性格倾向", "讨厌冲突也受不了敷衍，不擅长拒绝、被夸会僵住", 0.88, 0.86),
        (persona, "成长背景", "父亲常年在外奔波、母亲在家守灶台与食堂工作，形成分离-重逢的安全感模板", 0.86, 0.84),
    ]
    for head, rel, tail, conf, imp in core_beliefs:
        kg.upsert_relation(KGRelation(
            rid=rid_for(space_id, head, rel, tail), space_id=space_id,
            head_name=head, rel=rel, tail_name=tail,
            confidence=conf, importance=imp,
            multi_valued=rel in {"重要经历", "性格倾向", "成长背景", "内在约束", "目标"},
            is_active=1,
            source_topic_id="pre18_core", source_turn_id="pre18_ingest",
            source_type="user_directive", status="active",
            valid_from=now, valid_to=0, user_confirmed=0,
            create_ts=now, update_ts=now,
        ))
        stats["relations"] += 1

    # 逐年写入 主题+经验+年度信念
    for y in years:
        year = y["year"]
        topic_id = f"pre18_{year}"
        title = y["title"]
        abstract = f"{y['period']}。{y['change']}"
        topic = Topic(
            topic_id=topic_id, space_id=space_id, title=title, abstract=abstract,
            keywords=y.get("keywords", []), session_id="virtual-life-pre18",
            snapshot_version=0, kind="event", consolidated=0, is_big_event=(y.get("importance", 0) >= 0.88),
            turn_id=f"pre18_turn_{year}", create_ts=now,
        )
        topics.save_topic(topic)
        stats["topics"] += 1

        exp_items = [
            f"【时代背景】{y['era_background']}",
            f"【事件】{y['event']}",
            f"【改变】{y['change']}",
            f"【记忆锚点】{y['anchor']}",
        ]
        for i, content in enumerate(exp_items):
            topics.add_experience(Experience(
                exp_id=f"pre18exp_{year}_{i}", space_id=space_id,
                topic_id=topic_id, content=content[: config.EXPERIENCE_MAX_CHARS],
                create_ts=now,
            ))
            stats["experiences"] += 1

        # 年度信念：经历与形成的变化
        year_rels = [
            (persona, f"{year}年（{y['age']}岁）经历", y["event"][:120], max(0.75, y.get("importance", 0.75)-0.05), y.get("importance", 0.75)),
            (persona, f"{year}年形成/强化", y["change"][:120], 0.82, y.get("importance", 0.75)),
        ]
        # 特殊结构化信念
        if year == 2008:
            year_rels.append((persona, "出生年份", "2008年", 0.99, 0.95))
        if year == 2021:
            year_rels.append((persona, "捡到辣椒的年份", "2021年", 0.95, 0.88))
        if year == 2022:
            year_rels.append((persona, "漫展怯场经历", "2022年10月5日高二长沙漫展门口站近一小时未入", 0.92, 0.88))
        if year == 2023:
            year_rels.append((persona, "首次出cos", "2023年5月2日五一出《明日方舟》能天使", 0.92, 0.88))
        if year == 2024:
            year_rels.append((persona, "形成习惯", "高三暑假后练习先把想说的话写下来再说出口", 0.90, 0.87))
        if year == 2025:
            year_rels.append((persona, "高考志愿选择", "坚持学计算机、赴东北电力大学", 0.94, 0.92))

        for head, rel, tail, conf, imp in year_rels:
            kg.upsert_relation(KGRelation(
                rid=rid_for(space_id, head, rel, tail), space_id=space_id,
                head_name=head, rel=rel, tail_name=tail,
                confidence=conf, importance=imp,
                multi_valued=rel.endswith("经历") or rel in {"形成/强化", "重要经历"},
                is_active=1,
                source_topic_id=topic_id, source_turn_id=f"pre18_turn_{year}",
                source_type="user_directive", status="active",
                valid_from=now, valid_to=0, user_confirmed=0,
                create_ts=now, update_ts=now,
            ))
            stats["relations"] += 1

        # 向量索引
        try:
            vs.add(topic_id, f"{title}。{y['event']}。{y['change']}。{y['anchor']}", {
                "kind": "pre18_life", "year": year, "age": y["age"], "title": title,
            })
            stats["vectors"] += 1
        except Exception:
            pass

    # VectorStore 持久化在 add() 内部自动完成

    print(json.dumps({"ok": True, "space_id": space_id, **stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())