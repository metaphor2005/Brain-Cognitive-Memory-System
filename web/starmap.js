/* ============================================================
 * 记忆宇宙 · 独立页面
 * - 数据：GET /api/memory/universe
 * - 内容：信念 / 往事 / 经历 / 人物与事物 / 人格变迁 / 情绪 / 关系
 * - 形态：旋涡星系（核心 + 多条悬臂 + 星尘 + 星云）
 * - 映射：重要程度 → 星体大小与亮度；类型 → 色温
 * ============================================================ */
"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  space: "default",
  graph: null,
  universe: null,
  allNodes: [],
  allLinks: [],
  dust: [],
  data: { nodes: [], links: [] },
  selected: null,
  loaded: false,
  cameraInitialized: false,
  userInteracted: false,
  starEls: new Map(),
  dustEls: [],
  haloEl: null,
  deepStars: [],
  deepCtx: null,
  deepW: 0,
  deepH: 0,
  deepVec: null,
  lastFrameTs: 0,
  deepLastTs: 0,
  starRaf: null,
};

const STATUS_LABEL = {
  active: "生效",
  candidate: "待验证",
  rejected: "已否决",
  superseded: "已被取代",
};

const DOMAINS = [
  { id: "belief", label: "信念", color: "#9fb3c8", stat: "beliefs" },
  { id: "topic", label: "往事", color: "#c8bda3", stat: "topics" },
  { id: "experience", label: "经历", color: "#c8a99b", stat: "experiences" },
  { id: "entity", label: "人与物", color: "#a3c2b6", stat: "entities" },
  { id: "snapshot", label: "人格版本", color: "#c8bda8", stat: "snapshots" },
  { id: "change", label: "变迁", color: "#b3a8c8", stat: "changes" },
  { id: "mood", label: "情绪", color: "#a3c2bd", stat: "moods" },
  { id: "relation", label: "关系", color: "#c8aab3", stat: "affection" },
];
const DOMAIN_MAP = Object.fromEntries(DOMAINS.map((d) => [d.id, d]));

const ETYPE_LABEL = {
  AgentSelf: "自我",
  Person: "人物",
  Animal: "动物",
  Work: "作品",
  Character: "角色",
  Place: "地点",
  Project: "项目",
  Component: "组件",
  Belief: "信念",
  Other: "其他",
};

const MOOD_LABEL = {
  self_reflect: "自省",
  skeptical: "审慎",
  exploratory: "探索",
  analytic: "分析",
  empathetic: "共情",
};

/* 显示名修正：种子数据里用了「江妍」，但人格正式名是「江秀妍」 */
const NAME_FIXES = [["江妍", "江秀妍"]];
function fixName(text) {
  let out = String(text == null ? "" : text);
  for (const [from, to] of NAME_FIXES) out = out.split(from).join(to);
  return out;
}

/* 英文关系键 → 中文主题；长关系名 → 短枢纽标签 */
const REL_LABELS = {
  hometown_is: "家乡",
  live_near: "住在附近",
  prefer_style: "偏好风格",
  reside_in: "居住地",
  share_origin_region_with: "同乡",
  study_subject: "就读专业",
  "是江秀妍的室友": "室友",
  "是江秀妍的母亲": "母亲",
  "是江秀妍的父亲": "父亲",
  "是江秀妍养的猫": "猫",
  "是江秀妍最喜欢的动画": "最喜欢的动画",
  "是江秀妍最喜欢的干员": "最喜欢的干员",
  "是江秀妍喜欢的干员": "喜欢的干员",
  "是江秀妍的 cos 搭子": "cos 搭子",
  "是江秀妍出过的角色": "出过的角色",
};
const REL_CONTENT = {
  hometown_is: "家乡是",
  live_near: "住在附近",
  prefer_style: "偏好",
  reside_in: "住在",
  share_origin_region_with: "同乡",
  study_subject: "就读于",
};
function relLabel(rel) {
  const key = fixName(String(rel == null ? "" : rel).trim());
  return REL_CONTENT[key] || key;
}
function shortRel(rel) {
  const key = fixName(String(rel == null ? "" : rel).trim());
  return REL_LABELS[key] || key;
}

function starHash(str) {
  let h = 0;
  for (let i = 0; i < String(str).length; i++) {
    h = (h * 31 + String(str).charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

/* 8 字（双纽线）参数曲线：phase 沿笔画方向增长 */
const EIGHT_A = 680;
const EIGHT_B = 392;
const EIGHT_WIDTH = 150;
const EIGHT_THICK = 62;
const EIGHT_DEPTH = 156;

function eightPoint(phase, v, h) {
  const s = Math.sin(phase);
  const c = Math.cos(phase);
  const x0 = EIGHT_A * s;
  const y0 = EIGHT_B * s * c;
  const dx = EIGHT_A * c;
  const dy = EIGHT_B * (c * c - s * s);
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  return {
    x: x0 + v * nx,
    y: y0 + v * ny,
    // 让 8 字在空间中上下扭转：交叉处两条带分别位于不同高度
    z: EIGHT_DEPTH * Math.cos(phase) + h + v * 0.12 * Math.sin(phase * 0.5),
  };
}

function eightRadius(phase) {
  const s = Math.sin(phase);
  const c = Math.cos(phase);
  return Math.hypot(EIGHT_A * s, EIGHT_B * s * c);
}

/* 曲线在 phase 处的速度，用于按弧长均匀采样 */
function eightSpeed(phase) {
  const s = Math.sin(phase);
  const c = Math.cos(phase);
  return Math.hypot(EIGHT_A * c, EIGHT_B * (c * c - s * s));
}

/* 沿 8 字笔画较均匀地分布；两环交叉处因两条带重叠会自然略密 */
function sampleEightPhase() {
  for (let attempt = 0; attempt < 60; attempt++) {
    const phase = Math.random() * Math.PI * 2;
    if (Math.random() < eightSpeed(phase) / EIGHT_A) return phase;
  }
  return Math.random() * Math.PI * 2;
}

/* 星带中间收细、外侧放宽：交叉处约为原来一半，最外圈约为原来一倍半 */
function eightSpread(phase) {
  const r = Math.min(1, eightRadius(phase) / EIGHT_A);
  return 0.45 + 0.9 * r;
}
function clamp01(v) {
  return Math.max(0, Math.min(1, Number(v) || 0));
}
function intSafe(v) {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
}
function transparentColor(color) {
  const s = String(color || "").trim();
  const m = s.match(/^#([0-9a-f]{6})$/i);
  if (m) {
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, 0)`;
  }
  const rgb = s.match(/^rgba?\(([^)]+)\)$/i);
  if (rgb) {
    const [r, g, b] = rgb[1].split(",").map((x) => parseFloat(x));
    return `rgba(${r || 0}, ${g || 0}, ${b || 0}, 0)`;
  }
  return "rgba(143, 211, 255, 0)";
}
function truncate(text, n) {
  const s = String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function beliefShortLabel(b, head, tail) {
  const selfNames = new Set(["江秀妍", "用户", "我", "你", ""]);
  const rel = shortRel(b.rel);
  if (selfNames.has(head)) {
    return tail && tail.length <= 12 ? tail : rel;
  }
  if (selfNames.has(tail)) {
    return rel || head;
  }
  return rel || tail || head;
}

function beliefStarColor(b) {
  if (b.status === "rejected" || b.status === "superseded" || b.is_active === false) {
    return "#6f7a8c";
  }
  if (b.status === "candidate") return "#ffd479";
  return DOMAIN_MAP.belief.color;
}

function topicKindLabel(t) {
  if (t.is_big_event) return "大事";
  if (t.kind === "event") return "事件";
  if (t.kind === "daily") return "日结";
  return "日常";
}

function topicImportance(t) {
  let v = 0.45;
  if (t.is_big_event) v += 0.3;
  if (t.kind === "event") v += 0.08;
  else if (t.kind === "daily") v += 0.1;
  if (t.consolidated) v -= 0.04;
  const title = String(t.title || "");
  if (/【虚拟人生】|高考|漫展|声之形|辣椒|志愿/.test(title)) v += 0.06;
  return clamp01(v);
}

function entityTypeLabel(etype) {
  return ETYPE_LABEL[etype] || etype || "其他";
}

/* ---------------- 构建星系数据 ---------------- */

function buildUniverse(u) {
  const beliefs = dedupeBeliefs(u.beliefs || []);
  const entities = dedupeEntities(u.entities || []);

  const relationTouch = {};
  for (const b of beliefs) {
    const h = fixName(b.head);
    const t = fixName(b.tail);
    relationTouch[h] = (relationTouch[h] || 0) + 1;
    relationTouch[t] = (relationTouch[t] || 0) + 1;
  }

  const topicImp = new Map();
  for (const t of u.topics || []) topicImp.set(t.topic_id, topicImportance(t));

  const buckets = new Map(); // domain -> Map(cat -> items[])
  function bucket(domain, cat) {
    if (!buckets.has(domain)) buckets.set(domain, new Map());
    const m = buckets.get(domain);
    const key = cat || "其他";
    if (!m.has(key)) m.set(key, []);
    return m.get(key);
  }
  function push(domain, cat, item) {
    item.cat = cat || "其他";
    item.domain = domain;
    bucket(domain, cat).push(item);
  }

  for (const b of beliefs) {
    const head = fixName(b.head);
    const tail = fixName(b.tail);
    const inactive =
      b.status === "rejected" || b.status === "superseded" || b.is_active === false;
    const confidence = clamp01(b.confidence);
    push("belief", shortRel(b.rel) || "其他", {
      id: `belief:${b.rid}`,
      kind: "belief",
      domain: "belief",
      label: `${head} ${relLabel(b.rel)} ${tail}`,
      shortLabel: beliefShortLabel(b, head, tail),
      subtitle: `置信度 ${confidence.toFixed(2)} · ${STATUS_LABEL[b.status] || b.status || "生效"}`,
      importance: clamp01(b.importance),
      confidence,
      ts: Number(b.update_ts || 0),
      color: beliefStarColor(b),
      data: { ...b, head, tail },
      inactive,
    });
  }

  for (const t of u.topics || []) {
    push("topic", topicKindLabel(t), {
      id: `topic:${t.topic_id}`,
      kind: "topic",
      domain: "topic",
      label: fixName(t.title || "未命名往事"),
      shortLabel: truncate(t.title || "往事", 12),
      subtitle: truncate(t.abstract || "", 70),
      importance: topicImp.get(t.topic_id) || 0.5,
      ts: Number(t.create_ts || 0),
      color: DOMAIN_MAP.topic.color,
      data: t,
    });
  }

  for (const e of u.experiences || []) {
    const parent = (u.topics || []).find((t) => t.topic_id === e.topic_id);
    const parentImp = topicImp.get(e.topic_id) || 0.45;
    const imp = clamp01(parentImp * 0.68 + 0.08);
    push("experience", parent ? truncate(parent.title, 14) : "零散经历", {
      id: `exp:${e.exp_id}`,
      kind: "experience",
      domain: "experience",
      label: truncate(e.content, 54),
      shortLabel: truncate(e.content, 14),
      subtitle: parent ? `属于：${parent.title}` : "未归属主题",
      importance: imp,
      ts: Number(e.create_ts || 0),
      color: DOMAIN_MAP.experience.color,
      data: { ...e, parentTitle: parent ? parent.title : "" },
    });
  }

  for (const en of entities) {
    const degree = relationTouch[fixName(en.name)] || 0;
    let imp = 0.45 + Math.min(0.3, degree * 0.03);
    if (en.etype === "AgentSelf") imp = 0.98;
    else if (en.etype === "Person") imp += 0.08;
    else if (en.etype === "Animal") imp += 0.05;
    else if (en.etype === "Work" || en.etype === "Character") imp += 0.03;
    push("entity", entityTypeLabel(en.etype), {
      id: `entity:${en.eid}`,
      kind: "entity",
      domain: "entity",
      label: fixName(en.name || "无名"),
      shortLabel: fixName(en.name || "实体"),
      subtitle: `${entityTypeLabel(en.etype)} · 关联 ${degree} 条信念`,
      importance: clamp01(imp),
      ts: 0,
      color: DOMAIN_MAP.entity.color,
      data: en,
    });
  }

  for (const s of u.snapshots || []) {
    const version = intSafe(s.version);
    push("snapshot", version ? `v${version}` : "版本", {
      id: `snapshot:${version || s.topic_id || s.create_ts}`,
      kind: "snapshot",
      domain: "snapshot",
      label: `人格版本 v${version || 0}`,
      shortLabel: `v${version || 0}`,
      subtitle: truncate(s.narrative || s.self_view || "", 70),
      importance: clamp01(0.7 + Math.min(0.2, version * 0.03)),
      ts: Number(s.create_ts || 0),
      color: DOMAIN_MAP.snapshot.color,
      data: s,
    });
  }

  for (const c of u.changes || []) {
    const field = String(c.field || "");
    let imp = 0.55;
    if (field.startsWith("life")) imp += 0.18;
    else if (field.startsWith("kernel")) imp += 0.08;
    if (Number(c.snapshot_to) > Number(c.snapshot_from)) imp += 0.05;
    push("change", field.startsWith("life") ? "人生" : field.split(":")[0] || "人格", {
      id: `change:${c.log_id}`,
      kind: "change",
      domain: "change",
      label: truncate(`${field} → ${c.new}`, 60),
      shortLabel: truncate(c.new || field, 14),
      subtitle: truncate(c.reason || "", 70),
      importance: clamp01(imp),
      ts: Number(c.create_ts || 0),
      color: DOMAIN_MAP.change.color,
      data: c,
    });
  }

  for (const m of u.moods || []) {
    push("mood", "情景状态", {
      id: `mood:${m.mode}`,
      kind: "mood",
      domain: "mood",
      label: MOOD_LABEL[m.mode] || m.mode,
      shortLabel: MOOD_LABEL[m.mode] || m.mode,
      subtitle: `强度 ${Number(m.intensity || 0).toFixed(2)}`,
      importance: clamp01(0.35 + Number(m.intensity || 0) * 0.55),
      ts: 0,
      color: DOMAIN_MAP.mood.color,
      data: m,
    });
  }

  for (const a of u.affection || []) {
    const value = Number(a.value || 0);
    push("relation", a.status === "broken" ? "断交" : a.status === "cold" ? "冷淡" : "正常", {
      id: `affection:${a.person_name}`,
      kind: "relation",
      domain: "relation",
      label: `${fixName(a.person_name)} · 好感度 ${value.toFixed(0)}`,
      shortLabel: fixName(a.person_name),
      subtitle: truncate(a.reason || "", 70),
      importance: clamp01(0.4 + (value / 100) * 0.45),
      ts: Number(a.update_ts || 0),
      color: DOMAIN_MAP.relation.color,
      data: a,
    });
  }

  // ---------- 8 字形布局 ----------
  const nodes = [];
  const links = [];

  const counts = {};
  const sums = {};
  const allItems = [];
  buckets.forEach((cats, domain) => {
    cats.forEach((list) => {
      list.forEach((item) => {
        item.domain = domain;
        allItems.push(item);
        counts[domain] = (counts[domain] || 0) + 1;
        sums[domain] = (sums[domain] || 0) + item.importance;
      });
    });
  });

  // 所有记忆星随机分布在 8 字带上，少量散布到带外的宇宙晕里
  for (const item of allItems) {
    const imp = clamp01(item.importance);
    const phase = sampleEightPhase();
    const spread = eightSpread(phase);
    const v = (Math.random() - 0.5) * EIGHT_WIDTH * spread;
    const h = (Math.random() - 0.5) * EIGHT_THICK * spread;
    const p = eightPoint(phase, v, h);
    let ox = 0;
    let oy = 0;
    let oz = 0;
    if (Math.random() >= 0.88) {
      const off = 40 + Math.random() * 180;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      ox = off * Math.sin(ph) * Math.cos(th);
      oy = off * Math.cos(ph) * 0.8;
      oz = off * Math.sin(ph) * Math.sin(th);
      p.x += ox;
      p.y += oy;
      p.z += oz;
    }
    nodes.push({
      ...item,
      val: 1,
      starColor: item.color,
      color: item.color,
      starSize: 7,
      phase,
      v,
      h,
      ox,
      oy,
      oz,
      // 重要度越高：越亮，沿 8 字运动越快；最慢 4 分钟一圈，最快 2 分钟一圈
      speed: (Math.PI / 120) * (1 + Math.max(0, Math.min(1, (imp - 0.3) / 0.7))),
      brightness: Math.min(0.95, 0.3 + imp * 0.62),
      x: p.x,
      y: p.y,
      z: p.z,
      fx: p.x,
      fy: p.y,
      fz: p.z,
    });
  }

  const domainStats = DOMAINS.map((d) => ({
    id: d.id,
    label: d.label,
    color: d.color,
    count: counts[d.id] || 0,
    importance: (sums[d.id] || 0) / Math.max(1, counts[d.id] || 0),
  })).filter((d) => d.count > 0);

  return {
    nodes,
    links,
    domains: domainStats,
    counts,
  };
}

function dedupeBeliefs(list) {
  const map = new Map();
  for (const b of list) {
    const key = `${fixName(b.head)}|${fixName(b.rel)}|${fixName(b.tail)}`;
    const prev = map.get(key);
    if (!prev) {
      map.set(key, b);
      continue;
    }
    const score = (x) =>
      (x.is_active === false ? 0 : 2) +
      (x.status === "active" ? 2 : x.status === "candidate" ? 1 : 0) +
      Number(x.confidence || 0) * 0.5 +
      Number(x.importance || 0);
    if (score(b) > score(prev)) map.set(key, b);
  }
  return [...map.values()];
}

function dedupeEntities(list) {
  const map = new Map();
  for (const en of list) {
    const key = `${en.etype}|${fixName(en.name)}`;
    if (!map.has(key)) map.set(key, en);
  }
  return [...map.values()];
}

/* ---------------- 深空星场（真实星系底噪） ---------------- */

function buildDeepSkyStars() {
  const stars = [];
  const push = (phase, v, h, r, a, c, glow, ox, oy, oz) => {
    stars.push({
      phase,
      v,
      h,
      r,
      a,
      c,
      glow: Boolean(glow),
      ox: ox || 0,
      oy: oy || 0,
      oz: oz || 0,
      speed: 0.004 + a * 0.0175 + Math.random() * 0.004,
      tw: Math.random() * Math.PI * 2,
      sp: 0.0004 + Math.random() * 0.0016,
    });
  };

  // 8 字星带：主体
  for (let i = 0; i < 3200; i++) {
    const phase = sampleEightPhase();
    const spread = eightSpread(phase);
    const v = (Math.random() - 0.5) * EIGHT_WIDTH * spread;
    const h = (Math.random() - 0.5) * EIGHT_THICK * spread;
    const c =
      Math.random() < 0.12
        ? "205, 198, 185"
        : Math.random() < 0.25
          ? "170, 188, 215"
          : "198, 210, 226";
    push(phase, v, h, 0.22 + Math.random() * 0.64, 0.06 + Math.random() * 0.28, c);
  }

  // 星带里更亮的一批
  for (let i = 0; i < 140; i++) {
    const phase = sampleEightPhase();
    const spread = eightSpread(phase);
    const v = (Math.random() - 0.5) * EIGHT_WIDTH * 0.7 * spread;
    const h = (Math.random() - 0.5) * EIGHT_THICK * 0.7 * spread;
    push(
      phase,
      v,
      h,
      0.55 + Math.random() * 0.95,
      0.35 + Math.random() * 0.35,
      Math.random() < 0.5 ? "200, 218, 242" : "225, 222, 210",
      Math.random() < 0.18
    );
  }

  // 两环交叉处：只保留稀薄的过桥星，不放置中心星
  for (let i = 0; i < 80; i++) {
    const phase =
      i % 2 === 0
        ? (Math.random() - 0.5) * 0.12
        : Math.PI + (Math.random() - 0.5) * 0.12;
    const v = (Math.random() - 0.5) * 34;
    const h = (Math.random() - 0.5) * 26;
    push(
      phase,
      v,
      h,
      0.2 + Math.random() * 0.5,
      0.06 + Math.random() * 0.2,
      Math.random() < 0.5 ? "198, 210, 226" : "190, 200, 218"
    );
  }

  // 带外的稀薄宇宙晕
  for (let i = 0; i < 450; i++) {
    const phase = Math.random() * Math.PI * 2;
    const v = (Math.random() - 0.5) * EIGHT_WIDTH * 1.8;
    const h = (Math.random() - 0.5) * EIGHT_THICK * 1.8;
    const off = 40 + Math.random() * 190;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    push(
      phase,
      v,
      h,
      0.2 + Math.random() * 0.55,
      0.04 + Math.random() * 0.16,
      "190, 205, 225",
      false,
      off * Math.sin(ph) * Math.cos(th),
      off * Math.cos(ph) * 0.8,
      off * Math.sin(ph) * Math.sin(th)
    );
  }

  // 8 字笔画上少量亮星，不做密集星团
  for (let k = 0; k < 2; k++) {
    const centerPhase = sampleEightPhase();
    const spread = eightSpread(centerPhase);
    const centerV = (Math.random() - 0.5) * EIGHT_WIDTH * 0.6 * spread;
    const centerH = (Math.random() - 0.5) * EIGHT_THICK * 0.6 * spread;
    for (let i = 0; i < 16; i++) {
      const bright = i < 2;
      push(
        centerPhase + (Math.random() - 0.5) * 0.05,
        centerV + (Math.random() - 0.5) * 30,
        centerH + (Math.random() - 0.5) * 22,
        bright ? 0.55 + Math.random() * 0.75 : 0.28 + Math.random() * 0.55,
        bright ? 0.32 + Math.random() * 0.22 : 0.12 + Math.random() * 0.22,
        Math.random() < 0.5 ? "188, 205, 230" : "215, 215, 215",
        bright
      );
    }
  }

  return stars;
}

function resizeDeepSky() {
  const canvas = $("#deepSkyCanvas");
  const stage = document.querySelector(".star-stage");
  if (!canvas || !stage) return;
  const dpr = 1;
  state.deepW = Math.max(1, stage.clientWidth);
  state.deepH = Math.max(1, stage.clientHeight);
  canvas.width = Math.round(state.deepW * dpr);
  canvas.height = Math.round(state.deepH * dpr);
  canvas.style.width = `${state.deepW}px`;
  canvas.style.height = `${state.deepH}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  state.deepCtx = ctx;
  if (!state.deepStars.length) state.deepStars = buildDeepSkyStars();
}

function drawDeepSky(t) {
  const ctx = state.deepCtx;
  const graph = state.graph;
  if (!ctx || !graph) return;
  const w = state.deepW;
  const h = state.deepH;
  ctx.clearRect(0, 0, w, h);

  const camera = graph.camera && graph.camera();
  if (!camera) return;
  camera.updateMatrixWorld();
  const V3 = camera.position.constructor;
  if (!state.deepVec) state.deepVec = new V3();
  const v = state.deepVec;
  const d = Math.min(0.1, (t - (state.deepLastTs || t)) / 1000);
  state.deepLastTs = t;

  ctx.globalCompositeOperation = "lighter";
  for (const s of state.deepStars) {
    s.phase = (s.phase || 0) + (s.speed || 0.05) * d;
    const p = eightPoint(s.phase, s.v || 0, s.h || 0);
    v.set(p.x + (s.ox || 0), p.y + (s.oy || 0), p.z + (s.oz || 0)).project(camera);
    if (v.z < -1 || v.z > 1) continue;
    const x = (v.x * 0.5 + 0.5) * w;
    const y = (-v.y * 0.5 + 0.5) * h;
    if (x < -6 || x > w + 6 || y < -6 || y > h + 6) continue;
    const tw = 0.84 + 0.16 * Math.sin(t * s.sp + s.tw);
    const a = Math.min(0.78, s.a * tw);
    ctx.fillStyle = `rgb(${s.c})`;
    if (s.r > 0.8 || s.glow) {
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.arc(x, y, s.r, 0, Math.PI * 2);
      ctx.fill();
      if (s.glow) {
        ctx.globalAlpha = Math.min(0.26, a * 0.3);
        ctx.beginPath();
        ctx.arc(x, y, s.r * 2.2, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.globalAlpha = Math.min(0.68, a);
      ctx.fillRect(x, y, s.r, s.r);
    }
  }
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
}

/* ---------------- 星点覆盖层 ---------------- */

let starLayerToken = 0;

function buildStarLayer() {
  const layer = $("#starLayer");
  if (!layer) return;
  layer.innerHTML = "";
  state.starEls = new Map();
  state.dustEls = [];
  state.haloEl = null;

  // 无中心星：不再绘制核心光晕

  // 星系盘里的暗星由深空星场（deepSkyCanvas）绘制，这里不再创建 DOM 星尘
  state.dust = [];
  state.dustEls = [];

  for (const n of state.allNodes) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = `star-node ${n.kind}`;
    el.dataset.id = n.id;
    const color = n.starColor || n.color || "#9fb3c8";
    el.style.setProperty("--c", color);
    el.style.setProperty("--c0", transparentColor(color));
    const isCore = n.kind === "core";
    const size = isCore ? 14 : 7;
    el.style.width = `${size}px`;
    el.style.height = `${size}px`;
    const alpha = isCore ? 0.92 : Math.min(0.95, Number(n.brightness ?? 0.3 + (n.importance || 0) * 0.62));
    el.style.setProperty("--a", String(alpha));
    el.style.setProperty("--glow", isCore ? "12px" : "8px");
    el.style.setProperty("--glow2", isCore ? "28px" : "16px");
    if (n.inactive) el.classList.add("inactive");

    el.addEventListener("click", () => {
      state.selected = n.id;
      showNodeDetail(n);
      flyTo(n, n.kind === "core" ? 520 : maybeDistance(n));
      highlight(n.id);
      updateSelectedLabel();
    });
    layer.appendChild(el);
    state.starEls.set(n.id, el);
  }
}

function maybeDistance(n) {
  const mag = Math.hypot(n.x || 0, n.y || 0, n.z || 0);
  return Math.max(120, Math.min(360, mag * 0.55));
}

function updateSelectedLabel() {
  const label = $("#selectedLabel");
  if (!label) return;
  if (!state.selected) {
    label.classList.add("hidden");
    return;
  }
  const node = state.allNodes.find((n) => n.id === state.selected);
  const star = state.starEls.get(state.selected);
  if (!node || !star || star.classList.contains("hidden-star")) {
    label.classList.add("hidden");
    return;
  }
  label.textContent =
    node.kind === "core"
      ? "江秀妍 · 核心"
      : node.kind === "domain"
        ? `${node.label}星团`
        : node.label || node.shortLabel || node.id;
  label.classList.remove("hidden");
  const g = state.graph;
  if (!g || !g.graph2ScreenCoords) return;
  const p = g.graph2ScreenCoords(node.x || 0, node.y || 0, node.z || 0);
  if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) return;
  label.style.left = `${p.x}px`;
  label.style.top = `${p.y}px`;
}

function positionStarLayerOnce(t) {
  const g = state.graph;
  if (!g || !g.graph2ScreenCoords) return;
  const now = t || performance.now();
  const dt = Math.min(0.06, (now - (state.lastFrameTs || now)) / 1000);
  state.lastFrameTs = now;

  // 让每颗记忆星沿 8 字笔画前进；重要度越高速度越快
  for (const n of state.allNodes) {
    if (n.kind === "core") continue;
    n.phase = (n.phase || 0) + (n.speed || 0.1) * dt;
    const p = eightPoint(n.phase, n.v || 0, n.h || 0);
    n.x = p.x + (n.ox || 0);
    n.y = p.y + (n.oy || 0);
    n.z = p.z + (n.oz || 0);
  }

  state.deepFrame = (state.deepFrame || 0) + 1;
  const doDraw = state.deepFrame % 2 === 0;
  if (doDraw) drawDeepSky(now);
  if (!doDraw) {
    updateSelectedLabel();
    return;
  }

  const core = state.allNodes.find((n) => n.kind === "core");
  if (state.haloEl && core) {
    const p = g.graph2ScreenCoords(core.x || 0, core.y || 0, core.z || 0);
    if (p && Number.isFinite(p.x)) {
      state.haloEl.style.left = `${p.x}px`;
      state.haloEl.style.top = `${p.y}px`;
    }
  }

  for (const n of state.allNodes) {
    const el = state.starEls.get(n.id);
    if (!el || el.classList.contains("hidden-star")) continue;
    const p = g.graph2ScreenCoords(n.x || 0, n.y || 0, n.z || 0);
    if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) continue;
    el.style.left = `${p.x}px`;
    el.style.top = `${p.y}px`;
  }
  updateSelectedLabel();
}

function startStarLayer() {
  starLayerToken += 1;
  const token = starLayerToken;
  if (state.starRaf) cancelAnimationFrame(state.starRaf);
  positionStarLayerOnce(performance.now());
  const tick = (t) => {
    if (token !== starLayerToken || !state.graph) return;
    positionStarLayerOnce(t);
    state.starRaf = requestAnimationFrame(tick);
  };
  state.starRaf = requestAnimationFrame(tick);
}

function stopStarLayer() {
  starLayerToken += 1;
  if (state.starRaf) cancelAnimationFrame(state.starRaf);
  state.starRaf = null;
}

function ensureGraph() {
  const container = $("#graph");
  if (!container || state.graph || typeof ForceGraph3D === "undefined") {
    return state.graph;
  }
  const g = ForceGraph3D({ controlType: "orbit" })(container)
    .backgroundColor("rgba(0,0,0,0)")
    .showNavInfo(false)
    .nodeVisibility(false)
    .linkColor(() => "rgba(150, 190, 240, 0.06)")
    .linkWidth((l) => (l.kind === "domain" ? 0.45 : l.kind === "hub" ? 0.22 : 0.07))
    .linkOpacity(0.5)
    .onBackgroundClick(() => {
      state.selected = null;
      updateSelectedLabel();
      $("#detail").classList.add("hidden");
      highlight(null);
    });
  g.controls().autoRotate = true;
  g.controls().autoRotateSpeed = 0.05;
  g.controls().enableDamping = true;
  g.controls().addEventListener("start", () => {
    state.userInteracted = true;
  });
  // 首次创建时立刻放到 3/4 视角，避免异步加载后相机落在默认角度
  g.camera().position.set(700, 755, 1335);
  g.controls().target.set(0, 0, 0);
  g.controls().update();
  state.graph = g;
  setTimeout(resizeGraph, 60);
  window.addEventListener("resize", resizeGraph);
  if (typeof ResizeObserver !== "undefined") {
    const stage = document.querySelector(".star-stage");
    if (stage) new ResizeObserver(() => resizeGraph()).observe(stage);
  }
  startStarLayer();
  return g;
}

function resizeGraph() {
  const stage = $(".star-stage");
  if (state.graph && stage) {
    state.graph.width(stage.clientWidth).height(stage.clientHeight);
  }
  resizeDeepSky();
}

function flyTo(node, distance = 180) {
  if (!state.graph || !node || node.x == null) return;
  const mag = Math.hypot(node.x, node.y, node.z || 1);
  if (mag < 1) {
    state.graph.cameraPosition({ x: 0, y: 0, z: distance }, { x: 0, y: 0, z: 0 }, 900);
    return;
  }
  const ratio = 1 + distance / mag;
  state.graph.cameraPosition(
    { x: node.x * ratio, y: node.y * ratio, z: (node.z || 0) * ratio },
    { x: node.x, y: node.y, z: node.z || 0 },
    900
  );
}

function highlight(nodeId) {
  const linked = new Set();
  if (nodeId) {
    linked.add(nodeId);
    state.data.links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      if (s === nodeId) linked.add(t);
      if (t === nodeId) linked.add(s);
    });
  }
  state.starEls.forEach((el, id) => {
    el.classList.toggle("dim", Boolean(nodeId) && !linked.has(id));
    el.classList.toggle("selected", id === nodeId);
  });
  if (state.graph) {
    state.graph.linkColor(state.graph.linkColor());
  }
}

function freshGraphData(nodes, links) {
  return {
    nodes: nodes.map((n) => ({ ...n })),
    links: links.map((l) => ({
      ...l,
      source: typeof l.source === "object" ? l.source.id : l.source,
      target: typeof l.target === "object" ? l.target.id : l.target,
    })),
  };
}

/* ---------------- 搜索 ---------------- */
function applyFilters() {
  if (!state.graph || !state.allNodes.length) return;
  const q = (($("#searchInput") && $("#searchInput").value) || "").trim().toLowerCase();
  const stars = state.allNodes.filter(
    (n) => n.kind !== "core" && n.kind !== "domain" && n.kind !== "hub"
  );

  const visible = new Set(["__core__"]);
  if (q) {
    stars.forEach((n) => {
      const hay = `${n.label || ""} ${n.shortLabel || ""} ${n.subtitle || ""}`.toLowerCase();
      if (hay.includes(q)) visible.add(n.id);
    });
  } else {
    state.allNodes.forEach((n) => visible.add(n.id));
  }

  const nodes = state.allNodes.filter((n) => visible.has(n.id));
  const nodeSet = new Set(nodes.map((n) => n.id));
  const links = state.allLinks.filter((l) => {
    const s = typeof l.source === "object" ? l.source.id : l.source;
    const t = typeof l.target === "object" ? l.target.id : l.target;
    return nodeSet.has(s) && nodeSet.has(t);
  });
  state.data = freshGraphData(nodes, links);
  state.graph.graphData(state.data);

  state.allNodes.forEach((n) => {
    const el = state.starEls.get(n.id);
    if (el) el.classList.toggle("hidden-star", !visible.has(n.id));
  });

  if (q) {
    const first = nodes.find((n) => n.kind !== "core" && n.kind !== "domain" && n.kind !== "hub");
    if (first) {
      flyTo(first, 200);
      highlight(first.id);
      state.selected = first.id;
      updateSelectedLabel();
    } else {
      state.selected = null;
      updateSelectedLabel();
      highlight(null);
    }
  } else {
    highlight(state.selected);
  }
}

/* ---------------- 详情面板 ---------------- */

function escHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function openDetail(html, actionsHtml = "") {
  $("#detailBody").innerHTML = html;
  $("#detailActions").innerHTML = actionsHtml;
  $("#correctionForm").classList.add("hidden");
  $("#detail").classList.remove("hidden");
  $("#toggleRightBtn")?.classList.add("active");
  setTimeout(resizeGraph, 260);
}

function fmtTime(ts) {
  if (!ts) return "-";
  const d = new Date(Number(ts) * 1000);
  if (Number.isNaN(d.getTime())) return "-";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function starsInDomain(domainId) {
  return state.allNodes.filter(
    (n) => n.domain === domainId && n.kind !== "domain" && n.kind !== "hub"
  );
}
function starsInCat(domainId, cat) {
  return state.allNodes.filter(
    (n) => n.domain === domainId && n.cat === cat && n.kind !== "hub" && n.kind !== "domain"
  );
}

function showNodeButtons(host, nodes, title) {
  if (!nodes.length) return;
  const seen = new Set();
  const unique = nodes.filter((item) => {
    const key = String(item.label || item.id || "");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const wrap = document.createElement("div");
  wrap.className = "star-neighbors";
  const t = document.createElement("div");
  t.className = "star-neighbors-title";
  t.textContent = title;
  wrap.appendChild(t);
  unique.slice(0, 14).forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "star-neighbor";
    btn.textContent = truncate(item.label || item.shortLabel || item.id, 48);
    btn.addEventListener("click", () => {
      state.selected = item.id;
      showNodeDetail(item);
      flyTo(item, maybeDistance(item));
      highlight(item.id);
      updateSelectedLabel();
    });
    wrap.appendChild(btn);
  });
  host.appendChild(wrap);
}

function showNodeDetail(n) {
  if (!n) return;
  switch (n.kind) {
    case "core":
      showCoreDetail();
      break;
    case "domain":
      showDomainDetail(n);
      break;
    case "hub":
      showHubDetail(n);
      break;
    case "belief":
      showBeliefDetail(n);
      break;
    case "topic":
      showTopicDetail(n);
      break;
    case "experience":
      showExperienceDetail(n);
      break;
    case "entity":
      showEntityDetail(n);
      break;
    case "change":
      showChangeDetail(n);
      break;
    case "snapshot":
      showSnapshotDetail(n);
      break;
    case "mood":
      showMoodDetail(n);
      break;
    case "relation":
      showRelationDetail(n);
      break;
    default:
      openDetail(`<div class="star-breadcrumb">记忆宇宙</div><div class="kv">${escHtml(n.label || n.id)}</div>`);
  }
}

function showBeliefDetail(node) {
  const belief = node.data || {};
  const status = STATUS_LABEL[belief.status] || belief.status || "生效";
  const body = $("#detailBody");
  const cat = node.catLabel || shortRel(belief.rel) || "其他";
  const neighbors = starsInCat("belief", node.cat).filter((n) => n.id !== node.id);
  const neighborHtml = neighbors.length
    ? `<div class="star-neighbors"><div class="star-neighbors-title">同一分类 · ${escHtml(cat)}</div>${neighbors
        .slice(0, 6)
        .map((n) => `<button class="star-neighbor" data-rid="${escHtml(n.id)}">${escHtml(n.label)}</button>`)
        .join("")}</div>`
    : "";

  openDetail(
    `<div class="star-breadcrumb">记忆宇宙 / 信念 / ${escHtml(belief.rid || "")}</div>
     <div class="kv"><b>内容：</b>${escHtml(belief.head)} ${escHtml(relLabel(belief.rel))} ${escHtml(belief.tail)}</div>
     <div class="kv"><b>状态：</b>${escHtml(status)} / 当前有效：${belief.is_active === false ? "否(历史)" : "是"}</div>
     <div class="kv"><b>置信度：</b>${Number(belief.confidence || 0).toFixed(2)}　<b>重要性：</b>${Number(belief.importance || 0).toFixed(2)}</div>
     <div class="kv"><b>来源：</b>${escHtml(belief.source_type || "未知")}　<b>轮次：</b>${escHtml(belief.source_turn_id || "-")}</div>
     <div class="kv"><b>RID：</b>${escHtml(belief.rid || "")}</div>
     ${neighborHtml}`
  );

  body.querySelectorAll(".star-neighbor").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = state.allNodes.find((x) => x.id === btn.dataset.rid);
      if (target) {
        state.selected = target.id;
        showNodeDetail(target);
        flyTo(target, maybeDistance(target));
        highlight(target.id);
        updateSelectedLabel();
      }
    });
  });

  const actions = $("#detailActions");
  actions.innerHTML = "";
  [
    { label: "确认", cls: "", run: (btn) => updateBelief(belief.rid, "confirm", btn) },
    { label: "纠正", cls: "", run: () => showCorrectionForm(belief) },
    { label: "否决", cls: "danger", run: (btn) => updateBelief(belief.rid, "reject", btn) },
  ].forEach((item) => {
    const btn = document.createElement("button");
    btn.className = `star-btn ${item.cls}`.trim();
    btn.textContent = item.label;
    btn.onclick = () => item.run(btn);
    actions.appendChild(btn);
  });
}

function showTopicDetail(node) {
  const t = node.data || {};
  const exps = (state.universe?.experiences || []).filter((e) => e.topic_id === t.topic_id);
  const beliefs = (state.universe?.beliefs || []).filter((b) => b.source_topic_id === t.topic_id);
  const body = document.createElement("div");
  body.innerHTML = `
    <div class="star-breadcrumb">记忆宇宙 / 往事 / ${escHtml(t.kind || "normal")}</div>
    <div class="kv"><b>标题：</b>${escHtml(t.title || "")}</div>
    <div class="kv"><b>时间：</b>${fmtTime(t.create_ts)}　<b>类型：</b>${escHtml(topicKindLabel(t))}</div>
    <div class="kv"><b>摘要：</b>${escHtml(t.abstract || "—")}</div>
    <div class="kv"><b>关键词：</b>${escHtml((t.keywords || []).join("、") || "—")}</div>
    <div class="kv"><b>关联：</b>经验 ${exps.length} 条 · 信念 ${beliefs.length} 条</div>`;
  if (beliefs.length) {
    const fakeHost = document.createElement("div");
    body.appendChild(fakeHost);
    showNodeButtons(
      fakeHost,
      beliefs
        .map((b) => state.allNodes.find((n) => n.kind === "belief" && n.data?.rid === b.rid))
        .filter(Boolean),
      "关联信念"
    );
  }
  if (exps.length) {
    const fakeHost = document.createElement("div");
    body.appendChild(fakeHost);
    showNodeButtons(
      fakeHost,
      exps
        .map((e) => state.allNodes.find((n) => n.kind === "experience" && n.data?.exp_id === e.exp_id))
        .filter(Boolean),
      "这段往事里的经历"
    );
  }
  openDetail(body.innerHTML);
}

function showExperienceDetail(node) {
  const e = node.data || {};
  const parent = state.allNodes.find(
    (n) => n.kind === "topic" && n.data?.topic_id === e.topic_id
  );
  const html = `
    <div class="star-breadcrumb">记忆宇宙 / 经历</div>
    <div class="kv"><b>内容：</b>${escHtml(e.content || "")}</div>
    <div class="kv"><b>时间：</b>${fmtTime(e.create_ts)}</div>
    <div class="kv"><b>归属往事：</b>${escHtml(parent ? parent.label : "未归属")}</div>`;
  openDetail(html);
  if (parent) {
    const actions = $("#detailActions");
    const btn = document.createElement("button");
    btn.className = "star-btn";
    btn.textContent = "查看所属往事";
    btn.onclick = () => {
      state.selected = parent.id;
      showNodeDetail(parent);
      flyTo(parent, maybeDistance(parent));
      highlight(parent.id);
      updateSelectedLabel();
    };
    actions.appendChild(btn);
  }
}

function showEntityDetail(node) {
  const en = node.data || {};
  const attrs = en.attrs || {};
  const related = (state.universe?.beliefs || []).filter(
    (b) => fixName(b.head) === en.name || fixName(b.tail) === en.name
  );
  const attrHtml = Object.entries(attrs)
    .map(([k, v]) => `<div class="kv"><b>${escHtml(k)}：</b>${escHtml(typeof v === "string" ? v : JSON.stringify(v))}</div>`)
    .join("");
  const body = `
    <div class="star-breadcrumb">记忆宇宙 / 人与物 / ${escHtml(entityTypeLabel(en.etype))}</div>
    <div class="kv"><b>名称：</b>${escHtml(en.name || "")}</div>
    <div class="kv"><b>类型：</b>${escHtml(entityTypeLabel(en.etype))}</div>
    ${attrHtml}
    <div class="kv"><b>关联信念：</b>${related.length} 条</div>`;
  openDetail(body);
  if (related.length) {
    const host = document.createElement("div");
    $("#detailBody").appendChild(host);
    showNodeButtons(
      host,
      related
        .map((b) => state.allNodes.find((n) => n.kind === "belief" && n.data?.rid === b.rid))
        .filter(Boolean),
      "与它有关的信念"
    );
  }
}

function showChangeDetail(node) {
  const c = node.data || {};
  openDetail(`
    <div class="star-breadcrumb">记忆宇宙 / 人格变迁</div>
    <div class="kv"><b>维度：</b>${escHtml(c.field || "")}</div>
    <div class="kv"><b>从：</b>${escHtml(c.old || "—")}</div>
    <div class="kv"><b>到：</b>${escHtml(c.new || "—")}</div>
    <div class="kv"><b>原因：</b>${escHtml(c.reason || "—")}</div>
    <div class="kv"><b>来源：</b>${escHtml(c.source_type || "—")}　<b>版本：</b>v${escHtml(c.snapshot_from)} → v${escHtml(c.snapshot_to)}</div>
    <div class="kv"><b>时间：</b>${fmtTime(c.create_ts)}</div>`);
}

function showSnapshotDetail(node) {
  const s = node.data || {};
  openDetail(`
    <div class="star-breadcrumb">记忆宇宙 / 人格版本</div>
    <div class="kv"><b>版本：</b>v${escHtml(s.version ?? 0)}　<b>时间：</b>${fmtTime(s.create_ts)}</div>
    <div class="kv"><b>自我认知：</b>${escHtml(fixName(s.self_view || "—"))}</div>
    <div class="kv"><b>叙事：</b>${escHtml(fixName(s.narrative || "—"))}</div>
    <div class="kv"><b>来源主题：</b>${escHtml(s.topic_id || "—")}</div>`);
}

function showMoodDetail(node) {
  const m = node.data || {};
  openDetail(`
    <div class="star-breadcrumb">记忆宇宙 / 情绪</div>
    <div class="kv"><b>状态：</b>${escHtml(MOOD_LABEL[m.mode] || m.mode)}</div>
    <div class="kv"><b>强度：</b>${Number(m.intensity || 0).toFixed(2)}</div>
    <p class="setting-note">情景状态会随时间衰减，只有反复出现才会沉淀到人格底层。</p>`);
}

function showRelationDetail(node) {
  const a = node.data || {};
  const statusLabel = a.status === "broken" ? "断交" : a.status === "cold" ? "冷淡" : "正常";
  openDetail(`
    <div class="star-breadcrumb">记忆宇宙 / 关系</div>
    <div class="kv"><b>对象：</b>${escHtml(fixName(a.person_name))}</div>
    <div class="kv"><b>好感度：</b>${Number(a.value || 0).toFixed(0)} / 100　<b>状态：</b>${statusLabel}</div>
    <div class="kv"><b>最近变化原因：</b>${escHtml(a.reason || "—")}</div>
    <div class="kv"><b>更新时间：</b>${fmtTime(a.update_ts)}</div>`);
}

function showHubDetail(hub) {
  const items = starsInCat(hub.domain, hub.cat);
  const domain = DOMAIN_MAP[hub.domain];
  const body = `
    <div class="star-breadcrumb">记忆宇宙 / ${escHtml(domain ? domain.label : "")} / ${escHtml(hub.cat)}</div>
    <div class="kv"><b>星团：</b>${escHtml(hub.cat)}</div>
    <div class="kv"><b>星体数：</b>${items.length}</div>`;
  openDetail(body);
  if (items.length) {
    const host = document.createElement("div");
    $("#detailBody").appendChild(host);
    showNodeButtons(host, [...items].sort((a, b) => b.importance - a.importance), "包含的记忆");
  }
}

function showDomainDetail(node) {
  const items = starsInDomain(node.domain);
  const domain = DOMAIN_MAP[node.domain];
  const cats = new Map();
  items.forEach((n) => cats.set(n.cat || "其他", (cats.get(n.cat || "其他") || 0) + 1));
  const entries = [...cats.entries()].sort((a, b) => b[1] - a[1]);
  const catRows = entries
    .slice(0, 12)
    .map(([cat, count]) => `<div class="kv"><b>${escHtml(cat)}：</b>${count}</div>`)
    .join("");
  const rest = entries.length > 12 ? `<div class="kv"><b>其余：</b>${entries.length - 12} 类</div>` : "";
  openDetail(`
    <div class="star-breadcrumb">记忆宇宙 / ${escHtml(domain ? domain.label : "星团")}</div>
    <div class="kv"><b>星体总数：</b>${items.length}</div>
    <div class="kv"><b>平均重要性：</b>${(items.reduce((s, n) => s + n.importance, 0) / Math.max(1, items.length)).toFixed(2)}</div>
    ${catRows}${rest}`);
  if (items.length) {
    const host = document.createElement("div");
    $("#detailBody").appendChild(host);
    showNodeButtons(host, [...items].sort((a, b) => b.importance - a.importance), "最亮的记忆");
  }
}

function showCoreDetail() {
  const u = state.universe;
  if (!u) return;
  const counts = DOMAINS.map((d) => {
    const count = u.stats[d.stat] || 0;
    return `<div class="kv"><b>${d.label}：</b>${count}</div>`;
  }).join("");
  const top = state.allNodes
    .filter((n) => n.kind !== "core" && n.kind !== "domain" && n.kind !== "hub")
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 10);
  openDetail(`
    <div class="star-breadcrumb">记忆宇宙 / 核心</div>
    <div class="kv"><b>人格：</b>${escHtml(fixName(u.core?.name || "江秀妍"))}　<b>版本：</b>v${escHtml(u.core?.version ?? 0)}</div>
    <div class="kv"><b>记忆星总数：</b>${u.stats?.total || state.allNodes.length}</div>
    ${counts}`);
  const host = document.createElement("div");
  $("#detailBody").appendChild(host);
  showNodeButtons(host, top, "最亮的记忆");
}

/* 兼容旧名称 */
function showDetail(belief) {
  const node = state.allNodes.find((n) => n.kind === "belief" && n.data?.rid === belief.rid);
  if (node) showBeliefDetail(node);
}

function showCorrectionForm(belief) {
  const host = $("#correctionForm");
  if (!host || !belief) return;
  host.innerHTML = `
    <div class="cf-title">手动纠正这条信念</div>
    <label>主语<input id="cfHead" type="text" value="${escHtml(fixName(belief.head))}"></label>
    <label>关系<input id="cfRel" type="text" value="${escHtml(relLabel(belief.rel))}"></label>
    <label>宾语<input id="cfTail" type="text" value="${escHtml(fixName(belief.tail))}"></label>
    <div class="cf-row">
      <label>置信度<input id="cfConf" type="number" min="0" max="1" step="0.05" value="${Number(belief.confidence || 0).toFixed(2)}"></label>
      <label>重要性<input id="cfImp" type="number" min="0" max="1" step="0.05" value="${Number(belief.importance || 0).toFixed(2)}"></label>
    </div>
    <div class="cf-actions">
      <button class="star-btn" id="cfCancel">取消</button>
      <button class="star-btn save" id="cfSave">保存纠正</button>
    </div>`;
  host.classList.remove("hidden");
  $("#cfCancel").addEventListener("click", () => host.classList.add("hidden"));
  $("#cfSave").addEventListener("click", async () => {
    const head = $("#cfHead").value.trim();
    const rel = $("#cfRel").value.trim();
    const tail = $("#cfTail").value.trim();
    if (!head || !rel || !tail) {
      alert("主语、关系、宾语都不能为空");
      return;
    }
    const confidence = parseFloat($("#cfConf").value);
    const importance = parseFloat($("#cfImp").value);
    const saveBtn = $("#cfSave");
    saveBtn.disabled = true;
    try {
      await api("/api/memory/beliefs/update", {
        method: "POST",
        body: JSON.stringify({
          space_id: state.space,
          rid: belief.rid,
          action: "correct",
          head,
          rel,
          tail,
          confidence: Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence)) : undefined,
          importance: Number.isFinite(importance) ? Math.max(0, Math.min(1, importance)) : undefined,
          note: "用户在记忆宇宙中手动纠正",
        }),
      });
      $("#detail").classList.add("hidden");
      $("#toggleRightBtn")?.classList.remove("active");
      state.selected = null;
      updateSelectedLabel();
      await load(true);
    } catch (err) {
      alert(`保存失败：${err.message}`);
      saveBtn.disabled = false;
    }
  });
}

async function updateBelief(rid, action, btn) {
  if (btn) btn.disabled = true;
  try {
    await api("/api/memory/beliefs/update", {
      method: "POST",
      body: JSON.stringify({ space_id: state.space, rid, action }),
    });
    $("#detail").classList.add("hidden");
    state.selected = null;
    updateSelectedLabel();
    await load(true);
  } catch (err) {
    alert(`操作失败：${err.message}`);
    if (btn) btn.disabled = false;
  }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

function renderStats(u) {
  const el = $("#stats");
  if (!el) return;
  const parts = DOMAINS.map((d) => `${d.label} <b>${u.stats?.[d.stat] ?? 0}</b>`);
  el.innerHTML = `共 <b>${u.stats?.total ?? 0}</b> 颗记忆星 · ${parts.join(" · ")}`;
}

async function load(force) {
  if (!force && state.loaded && state.graph && state.allNodes.length) {
    resizeGraph();
    return;
  }
  if (typeof ForceGraph3D === "undefined") {
    $("#graph").innerHTML =
      '<div style="color:#cfd8ff;padding:20px;font-size:13px">星图引擎未加载（缺少 web/vendor/3d-force-graph.min.js）。</div>';
    return;
  }

  $("#emptyHint").classList.add("hidden");
  if (state.graph && typeof state.graph._destructor === "function") {
    try {
      state.graph._destructor();
    } catch (_) {
      /* 旧实例清理失败不影响重新加载 */
    }
  }
  stopStarLayer();
  const oldLayer = $("#starLayer");
  if (oldLayer) oldLayer.innerHTML = "";
  state.starEls.clear();
  state.dustEls = [];
  state.cameraInitialized = false;
  state.userInteracted = false;
  state.lastFrameTs = 0;
  state.deepLastTs = 0;
  $("#graph").innerHTML = "";
  state.graph = null;

  try {
    try {
      const settings = await api("/api/settings");
      if (settings.space) state.space = settings.space;
    } catch (_) {
      /* 读取失败时回退到 default */
    }

    const u = await api(
      `/api/memory/universe?space_id=${encodeURIComponent(state.space)}&limit=2000`
    );
    state.universe = u;
    const total = Number(u.stats?.total || 0);
    if (!total) {
      $("#emptyHint").classList.remove("hidden");
      return;
    }

    const built = buildUniverse(u);
    const actualStats = { ...u.stats };
    for (const d of DOMAINS) actualStats[d.stat] = built.counts[d.id] || 0;
    actualStats.total = DOMAINS.reduce((sum, d) => sum + (built.counts[d.id] || 0), 0);
    u.stats = actualStats;
    renderStats(u);
    state.allNodes = built.nodes.map((n) => ({ ...n }));
    state.allLinks = built.links.map((l) => ({ ...l }));
    state.data = freshGraphData(state.allNodes, state.allLinks);
    state.loaded = true;

    const g = ensureGraph();
    if (!g) return;
    resizeGraph();
    g.graphData(state.data);
    buildStarLayer();
    startStarLayer();
    applyFilters();
    const setInitialCamera = () => {
      if (!state.graph || state.userInteracted) return;
      const cam = state.graph.camera();
      cam.position.set(700, 755, 1335);
      const controls = state.graph.controls();
      controls.target.set(0, 0, 0);
      controls.update();
      positionStarLayerOnce(performance.now());
    };
    setTimeout(setInitialCamera, 250);
    setTimeout(setInitialCamera, 1000);
    setTimeout(setInitialCamera, 1600);
  } catch (err) {
    $("#graph").innerHTML = `<div style="color:#ffb4b4;padding:20px;font-size:13px">记忆宇宙加载失败：${escHtml(err.message)}</div>`;
  }
}

function bind() {
  $("#refreshBtn").addEventListener("click", () => load(true));

  const toggleLeft = (force) => {
    const panel = $("#leftPanel");
    const hidden = force != null ? !force : !panel.classList.contains("collapsed");
    panel.classList.toggle("collapsed", hidden);
    $("#toggleLeftBtn")?.classList.toggle("active", !hidden);
    setTimeout(resizeGraph, 260);
  };
  $("#toggleLeftBtn")?.addEventListener("click", () => toggleLeft());
  $("#leftCollapse")?.addEventListener("click", () => toggleLeft(false));

  const toggleRight = (force) => {
    const panel = $("#detail");
    const show = force != null ? force : panel.classList.contains("hidden");
    if (show) {
      if (state.selected) {
        const node = state.allNodes.find((n) => n.id === state.selected);
        if (node) {
          showNodeDetail(node);
          return;
        }
      }
      $("#detailBody").innerHTML =
        '<p class="setting-note">点击任意星点查看这条记忆。信念可以在这里手动确认、纠正或否决。</p>';
      $("#detailActions").innerHTML = "";
      $("#correctionForm").classList.add("hidden");
      panel.classList.remove("hidden");
      $("#toggleRightBtn")?.classList.add("active");
      setTimeout(resizeGraph, 260);
    } else {
      panel.classList.add("hidden");
      $("#toggleRightBtn")?.classList.remove("active");
      state.selected = null;
      updateSelectedLabel();
      highlight(null);
      setTimeout(resizeGraph, 260);
    }
  };
  $("#toggleRightBtn")?.addEventListener("click", () => toggleRight());
  $("#searchInput").addEventListener("input", applyFilters);
  $("#detailClose").addEventListener("click", () => {
    $("#detail").classList.add("hidden");
    $("#toggleRightBtn")?.classList.remove("active");
    state.selected = null;
    updateSelectedLabel();
    highlight(null);
    setTimeout(resizeGraph, 260);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      $("#detail").classList.add("hidden");
      $("#toggleRightBtn")?.classList.remove("active");
      state.selected = null;
      updateSelectedLabel();
      highlight(null);
      setTimeout(resizeGraph, 260);
    }
  });
}

/* ---------------- 背景星空 / 星云 ---------------- */
let skyRaf = null;
let skyStars = [];
let nebulaCanvas = null;

function initSky() {
  const canvas = $("#skyCanvas");
  if (!canvas) return;
  const stage = canvas.parentElement;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  let dpr = Math.min(2, window.devicePixelRatio || 1);
  let w = 1;
  let h = 1;

  function paintNebula() {
    const nc = document.createElement("canvas");
    nc.width = Math.max(1, Math.round(w * dpr));
    nc.height = Math.max(1, Math.round(h * dpr));
    const nctx = nc.getContext("2d");
    if (!nctx) return nc;
    nctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const blobs = [
      { x: 0.3, y: 0.36, r: 0.55, c: "rgba(54, 96, 210, 0.16)" },
      { x: 0.7, y: 0.62, r: 0.5, c: "rgba(96, 84, 160, 0.10)" },
      { x: 0.5, y: 0.45, r: 0.38, c: "rgba(255, 214, 150, 0.055)" },
      { x: 0.16, y: 0.78, r: 0.4, c: "rgba(70, 150, 190, 0.05)" },
      { x: 0.86, y: 0.22, r: 0.42, c: "rgba(170, 100, 160, 0.045)" },
    ];
    for (const b of blobs) {
      const g = nctx.createRadialGradient(
        b.x * w,
        b.y * h,
        0,
        b.x * w,
        b.y * h,
        b.r * Math.min(w, h)
      );
      g.addColorStop(0, b.c);
      g.addColorStop(0.55, b.c.replace(/[\d.]+\)$/, "0.06)"));
      g.addColorStop(1, "rgba(0,0,0,0)");
      nctx.fillStyle = g;
      nctx.fillRect(0, 0, w, h);
    }
    return nc;
  }

  const resize = () => {
    w = Math.max(1, stage.clientWidth);
    h = Math.max(1, stage.clientHeight);
    dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    nebulaCanvas = paintNebula();
    const count = Math.max(300, Math.min(1800, Math.round((w * h) / 700)));
    skyStars = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.25 + 0.1,
      a: Math.random() * 0.58 + 0.16,
      tw: Math.random() * Math.PI * 2,
      sp: 0.0004 + Math.random() * 0.0016,
      big: Math.random() < 0.05,
      c: Math.random() < 0.16 ? "190, 214, 255" : Math.random() < 0.2 ? "255, 226, 180" : "215, 232, 255",
    }));
  };

  const draw = (t) => {
    if (!canvas.isConnected) return;
    ctx.clearRect(0, 0, w, h);
    if (nebulaCanvas) {
      ctx.globalAlpha = 0.9;
      ctx.drawImage(nebulaCanvas, 0, 0, w, h);
      ctx.globalAlpha = 1;
    }
    for (const s of skyStars) {
      const twinkle = 0.55 + 0.45 * Math.sin(t * s.sp + s.tw);
      const alpha = Math.max(0, s.a * twinkle);
      if (s.r > 1.0) {
        ctx.shadowBlur = 8;
        ctx.shadowColor = `rgba(${s.c}, 0.85)`;
      } else {
        ctx.shadowBlur = 0;
      }
      ctx.beginPath();
      ctx.fillStyle = `rgba(${s.c}, ${alpha})`;
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
      if (s.big) {
        const len = s.r * 5;
        ctx.strokeStyle = `rgba(${s.c}, ${alpha * 0.7})`;
        ctx.lineWidth = 0.55;
        ctx.beginPath();
        ctx.moveTo(s.x - len, s.y);
        ctx.lineTo(s.x + len, s.y);
        ctx.moveTo(s.x, s.y - len);
        ctx.lineTo(s.x, s.y + len);
        ctx.stroke();
      }
    }
    ctx.shadowBlur = 0;

    skyRaf = requestAnimationFrame(draw);
  };

  resize();
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(resize).observe(stage);
  } else {
    window.addEventListener("resize", resize);
  }
  if (skyRaf) cancelAnimationFrame(skyRaf);
  skyRaf = requestAnimationFrame(draw);
}

initSky();
bind();
load(false);
