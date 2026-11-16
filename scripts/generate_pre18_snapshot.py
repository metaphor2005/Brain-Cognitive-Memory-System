import sys, time
sys.path.insert(0, '.')
import config
from cognitive.storage.database import Database
from cognitive.storage.kg_store import KGStore
from cognitive.persona.kernel import PersonaKernel
from cognitive.persona.snapshot import PersonaSnapshotStore
from cognitive.persona.changelog import PersonaChangelogStore
from cognitive.models import PersonaChange, new_id

db = Database(config.DB_PATH)
space = 'jiangyan'
kernel = PersonaKernel(db, space)
kg = KGStore(db)
snap_store = PersonaSnapshotStore(db, space, kernel, kg)
change_store = PersonaChangelogStore(db, space)

prev = snap_store.load_current()
v_before = kernel.get_current_version()
v_after = v_before + 1
now = int(time.time())

reason = '补全并写入江秀妍前18年（2008-2025，0-17岁）逐年人生：主题pre18_2008-pre18_2025、经验片段、关键信念与向量索引已落库。'
change_store.append(PersonaChange(
    log_id=new_id('plog'), space_id=space, topic_id='pre18_life',
    persona_field='life:pre18',
    old_value=f'v{v_before} 未系统沉淀前18年逐年记忆',
    new_value=f'v{v_after} 已沉淀前18年（2008-2025）主题/经验/信念/向量',
    reason=reason, source_type='life_ingest',
    snapshot_from=v_before, snapshot_to=v_after, create_ts=now,
))

narrative = (
    '基于《江秀妍·前18年虚拟人生（逐年推演）》补全0-17岁人生底色：'
    '出生与湘西家庭分工、捡到辣椒、漫展怯场与首次出cos、'
    '《声之形》三刷与“先写后说”、高考志愿争执与“别后悔”等关键节点，'
    '已作为主题、经验与信念沉淀入记忆库。'
)
snap_store.create(self_view=prev.self_view or config.PERSONA_INITIAL_SELF_VIEW,
                  narrative=narrative, topic_id='pre18_life')

kernel.set_current_version(v_after)
conn = db.conn()
conn.execute('update persona_meta set current_version = ? where space_id = ?', (v_after, space))
conn.commit()

print('ok', v_before, '->', v_after)
print('changelog_count', change_store.count())