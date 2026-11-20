# Improvement plan (P0–P3)

This document records the external code-review roadmap and how each item was implemented. It is the companion to `docs/consistency-review-2026-11-11.md` (the review that produced it).

Guiding rule: fix **correctness** before **reliability**, then **UX**, then **runtime**. Every item below is implemented, covered by an offline test where possible, and verified with `python -m compileall`, `tests/smoke_test.py`, and `tests/eval/run_eval.py`.

For **why** each design was chosen (literature, engineering constraints, or bugs that forced a change), see the [设计来源 section of docs/issues-and-fixes.md](issues-and-fixes.md#设计来源每个决定是怎么来的). That document also keeps a running log of problems encountered and how they were fixed.

---

## Scope at a glance

| Priority | Theme | Items | Status |
|---|---|---|---|
| P0 | Archiving correctness | turn-aware transcript, idempotency, explicit big-event input | Done |
| P1 | Memory reliability | belief provenance, user correction, correction ledger | Done |
| P2 | UX and control | persona freeze/reset, proactive policy (DND / cap / cooldown / skip) | Done |
| P3 | Runtime safety | optional API token, export/backup/reset maintenance commands | Done |
| — | Evaluation | offline retrieval + persona-prompt eval harness | Done |
| — | Memory lifecycle | lifecycle states, decay/forget, audit ledger, restore | Done |
| — | Confidence & conflict | saturation boost, evidence tiers, multi-value fallback, query_by_text fix | Done |
| — | Eval dataset | externalized cases.json (21 queries / 10 topics) | Done |
| — | Concurrency & security | task id fix, rate-limit lock, thread-safe & auth tests | Done |
| — | Multi-process rate limiting | optional SQLite backend (BEGIN IMMEDIATE), cross-process/shared tests | Done |
| — | Optional work | replay harness, severance arc, embedding backend, external worker, phrasing tiers | Done |

---

## P0 — Archiving correctness

### Problem

The archiver reconstructed "this turn" from the tail of session history. With multi-bubble replies that is ambiguous: a user message could be labelled `assistant`, and re-running archiving on the same turn duplicated topics, beliefs and experiences.

### Changes

| File | Change |
|---|---|
| `cognitive/models.py` | `Message.turn_id`, `new_id("turn")`; `SessionContext.append(..., turn_id=...)` |
| `cognitive/session.py` | `SessionManager.append(..., turn_id=...)` persists the turn id |
| `cognitive/storage/topic_store.py` | `Topic.turn_id` column; `get_topic_by_turn(space_id, turn_id)` |
| `cognitive/cognition/archiver.py` | `archive(..., user_message, answer_parts, turn_id)`; `_build_transcript` uses explicit inputs; duplicate check returns `ok=True, duplicate=True, skipped=True` |
| `cognitive/cognition/judge.py` | `judge_big_event(relations, user_message="", user_text="")` uses the explicit user message |
| `cognitive/engine.py` | generates one `turn_id` per chat turn; passes it to user message, every assistant bubble, and archiving |

### Guarantees

- One `turn_id` per user turn; every assistant bubble shares it.
- Re-archiving the same turn returns a duplicate report instead of writing twice.
- Big-event detection reads the actual user message, not a slice of the transcript that may start with an assistant bubble.
- `ARCHIVE_SYNC=false` runs archiving in a daemon thread and returns an immediate placeholder report (`{"ok": true, "async": true, "turn_id": ...}`) so callers never mistake `None` for failure.

### Tests

`test_p0_turn_aware_transcript`, `test_p0_archiver_idempotent`, `test_p0_judge_uses_explicit_message`.

---

## P1 — Memory reliability

### Problem

Beliefs had no provenance and no user-facing correction path. A model-inferred claim looked identical to something the user explicitly said, and a wrong belief could not be confirmed, corrected, or rejected.

### Data model

`kg_relation` gains additive columns (via `_COLUMN_MIGRATIONS`; existing DBs migrate on open):

| Column | Meaning |
|---|---|
| `source_turn_id` | which turn produced the belief |
| `source_type` | `user_stated` / `model_inferred` / `user_corrected` / `seed` |
| `status` | `active` / `candidate` / `rejected` |
| `valid_from` / `valid_to` | validity window (0 = open) |
| `user_confirmed` | user pressed "confirm" |

New table `belief_correction` is an append-only audit ledger: `space_id, correction_id, rid, head_name, rel, old_tail, new_tail, action, note, create_ts`.

### Changes

| File | Change |
|---|---|
| `cognitive/storage/kg_store.py` | provenance-aware `upsert_relation`; `list_beliefs`, `get_belief`, `update_belief`, `confirm_belief`, `correct_belief`, `reject_belief`, `_append_correction`, `list_corrections` |
| `cognitive/cognition/archiver.py` | persists provenance from extraction; freeze gate; writes correction audit entries; `_stable_id` restored |
| `api/server.py` | `GET /api/memory/beliefs`, `POST /api/memory/beliefs/update`, `GET /api/memory/corrections` |

### Semantics

- **confirm** → `status='active'`, `user_confirmed=1`.
- **correct** → `status='candidate'`, `user_confirmed=0` (kept for re-validation, not deleted).
- **reject** → `status='rejected'`, `is_active=0` (kept for history).
- Every action appends to `belief_correction`.
- `list_beliefs` filters to `status='active'` by default.

### Tests

`test_p1_belief_provenance`, `test_p1_user_correction_api_shape`.

---

## P2 — UX and control

### Persona freeze / reset

| File | Change |
|---|---|
| `cognitive/persona/kernel.py` | `is_frozen`, `set_frozen`, `reset_to_baseline` |
| `cognitive/cognition/archiver.py` | when frozen, clears `persona_deltas`, `persona_mood`, `self_view_update` |
| `api/server.py` | `POST /api/persona/freeze`, `POST /api/persona/reset` |
| `cognitive/engine.py` | `persona_state` exposes `frozen` |

Semantics: freezing keeps **memory growing** (topics, beliefs, experiences) but stops personality, mood and self-view drift. Reset restores `config.PERSONA_KERNEL_INIT` into `value` and `base_value`, clears pending drift and moods, and **keeps all memories**.

Note: `persona_kernel` columns are `space_id, param, value, base_value, pending_value, update_ts`.

### Proactive policy

| File | Change |
|---|---|
| `cognitive/storage/affection_store.py` | `ProactivePolicyStore` (DND / daily cap / cooldown / skip), `ProactiveScheduleStore.skip` |
| `cognitive/engine.py` | `proactive_tick` checks policy before firing; `force=true` skips policy except `skip_next` |
| `api/server.py` | `GET/POST /api/proactive/policy`, `POST /api/proactive/skip` |
| `config.py` | `PROACTIVE_DND_START/END`, `PROACTIVE_DAILY_CAP`, `PROACTIVE_COOLDOWN_MINUTES` |

Block reasons are explicit strings: `dnd`, `daily_cap`, `cooldown`, `skip_next`. Supported DND windows cross midnight (e.g. 23 → 8).

### Web UI

New settings tabs:

- **记忆** — belief list with 确认 / 纠正 / 否决 and refresh.
- **人格** — freeze switch, "回到最初" reset, DND / daily cap / cooldown fields, "这轮先别发" button.

### Tests

`test_p2_persona_freeze_reset`, `test_p2_proactive_policy`.

---

## P3 — Runtime safety

### Optional API token

`config.API_TOKEN` (empty = no auth; default binds `127.0.0.1`). When set, `/api/*` requires `X-API-Token` header or `?token=`. `/api/health` and static files are exempt so health checks and page loads still work.

### Maintenance commands

| Command | Purpose |
|---|---|
| `python maintenance.py --export data/export.json` | dump persona, beliefs, corrections, topics, experiences as JSON |
| `python maintenance.py --backup` | back up DB + vectors + snapshots to `data/backups/` (keeps recent 10) |
| `python maintenance.py --reset --yes` | clear runtime memory for the space, re-seed persona baseline (destructive; requires `--yes`) |

`--export` and `--backup` are non-destructive and recommended before `--reset`.

---

## Evaluation harness

`tests/eval/run_eval.py` (offline, no model calls):

- 21 colloquial retrieval queries over 10 topics, stored in `tests/eval/cases.json`;
- thresholds live in the JSON too (`recall@1`, `recall@3`, `false_recall`, `false_recall_score`);
- missing/malformed data file fails loudly — no silent "empty dataset green";
- persona prompt checks: name present, identity, rules, non-empty, no `sk-` key, no local paths.

Current result: Recall@1 = 0.952, Recall@3 = 1.000, false recall = 0, persona checks all pass.

To add cases, edit `tests/eval/cases.json` only — no Python changes needed.

---

## File map

```
cognitive/models.py                     # turn_id on messages
cognitive/session.py                    # append(..., turn_id)
cognitive/engine.py                     # turn pipeline, async archiving, policy-aware tick
cognitive/cognition/archiver.py         # turn-aware, idempotent, provenance, freeze, ledger
cognitive/cognition/judge.py            # explicit user-message big-event decision
cognitive/persona/kernel.py             # freeze / reset
cognitive/storage/kg_store.py           # provenance + correction API
cognitive/storage/topic_store.py        # turn_id, get_topic_by_turn
cognitive/storage/affection_store.py    # ProactivePolicyStore, schedule.skip
cognitive/storage/database.py           # belief_correction, proactive_policy, migrations
cognitive/storage/rate_limit_store.py   # cross-process SQLite sliding-window limiter
api/server.py                           # belief / persona / policy endpoints, API_TOKEN, rate-limit backend dispatch
maintenance.py                          # --export / --backup / --reset
web/index.html, web/app.js, web/style.css  # 记忆 / 人格 tabs
tests/smoke_test.py                     # 46 offline tests
tests/eval/run_eval.py                  # offline retrieval + persona eval
tests/eval/cases.json                   # externalized eval dataset
tests/replay/dialogue_replay.py         # scripted archive replay + golden diff
tests/replay/cases.json                 # replay dialogue script
tests/replay/golden.json                # replay snapshot (--record to refresh)
tests/replay/severance_arc.json         # severance arc case
scripts/run_severance_arc.py            # explicit, offline arc runner
scripts/proactive_worker.py             # external proactive worker (--once / --loop)
docs/memory-lifecycle-spec.md           # lifecycle / forget design
docs/improvement-plan.md                # this document
```

---

## Verification commands

```bash
python -X utf8 -m compileall -q api cognitive config.py maintenance.py scripts tests/smoke_test.py tests/eval/run_eval.py tests/replay/dialogue_replay.py
python -X utf8 tests/smoke_test.py                  # expect 46/46
python -X utf8 tests/eval/run_eval.py               # expect all checks pass
py -X utf8 tests/replay/dialogue_replay.py          # archive golden diff
py -X utf8 scripts/run_severance_arc.py             # print arc trace + messages
py -X utf8 scripts/proactive_worker.py --once       # drain due proactive schedules
```

---

## Optional work (all 5 implemented)

这些都不是正确性修复，而是"有了更好"的增强；默认行为保持不变。

| Item | Implementation | Entry point |
|---|---|---|
| Affection phrasing tiers | `phrasing_tier()` maps value+status to warm/neutral/distant; cues injected into the relation-temperature block and the proactive prompt | `config.AFFECTION_TIER_*`, `cognitive/storage/affection_store.py` |
| Fixed-dialogue replay harness | scripted client feeds fixed extract results into `MemoryArchiver.archive`; report is canonicalized (ids/timestamps stripped) and diffed against a golden snapshot | `tests/replay/dialogue_replay.py --record` to refresh |
| Optional severance storyline | data-driven arc over the existing state machine; reuses archiver templates + outbox; never runs in the background | `scripts/run_severance_arc.py` |
| External proactive worker | `run_due_once()` shared by the in-process loop and the CLI worker; SQLite schedule table is the durable queue, `claim` prevents double-send | `scripts/proactive_worker.py --once/--loop`; set `PROACTIVE_IN_PROCESS_SCHEDULER=false` |
| Embedding backend | `VectorStore` stays a façade with unchanged `add/search/count/has`; `VECTOR_BACKEND=embedding` lazily imports a local model and falls back to TF-IDF on any failure | `config.VECTOR_BACKEND`, `config.EMBEDDING_MODEL` |

Notes:
- The replay harness caught a real production bug: `_SELF_SHAPING_HINTS` was referenced
  in `archiver._persona_update_allowed` but never defined. All smoke tests used
  `client=None` and degraded before reaching that line; any real model client hit a
  `NameError` on every archive. Fixed by defining the constant.
- The embedding backend is off by default. With `VECTOR_BACKEND=embedding` but no
  `sentence-transformers` installed, it prints a warning and uses TF-IDF; eval metrics
  are unchanged (Recall@1 0.952 / Recall@3 1.000).
- The external worker does not introduce Celery/RQ/Redis. The in-process scheduler
  remains the default; switching to the worker is one config flag.

## Multi-process rate limiting (optional)

The default limiter is still in-process (`_RATE_BUCKETS` + `_RATE_LOCK`), which is enough
for a single Flask process. For multi-worker deployments, set:
```
RATE_LIMIT_BACKEND=sqlite
# optional: RATE_LIMIT_DB_PATH=/path/to/shared.db   (defaults to DB_PATH)
```
`cognitive/storage/rate_limit_store.py` records one row per allowed hit and uses a
`BEGIN IMMEDIATE` write transaction to serialize "count → insert" across processes, so
multiple workers share a single sliding window without Redis. Verified with two limiter
instances plus a threaded test that the cap is never exceeded.

---

## Emotion language ("更像人", in progress)

This is the first step toward a more human-like persona. It targets the exact gap named
by the project's own review (`docs/persona-module-review.md` §5.3): a core belief got
overturned and the agent "felt nothing, just silently changed a field". It does **not**
touch the `belief-system-spec.md` §9–15 refactor (`belief_id` / `dormant` / three-tier
recall), which remains intentionally deferred.

Two mechanisms, both behind config flags (on by default, easy to A/B against old behavior):

| Mechanism | What it does | Config / code |
|---|---|---|
| Emotion → wording | Turns mood intensity into a dedicated `【此刻的情绪】` prompt block with concrete speech cues (short sentences, pauses, soften tone) instead of a bare "strength 0.62". Low/high cue tiers; capped at 3 lines; no cue below threshold. | `config.EMOTION_SPEECH_ENABLED`, `EMOTION_SPEECH_MIN_INTENSITY`; `kernel.render_emotion_block()` (pure), injected via `engine.chat()` → `build_answer_messages(emotion_block=...)` |
| Event → emotion | Real events activate feelings deterministically (not at the model's discretion): belief overturned → hurt + self_reflect + skeptical; relation cold → hurt; severed → stronger hurt; reconciled / affection up → warm. | `config.EMOTION_EVENT_TRIGGER_ENABLED`; archiver collects `emotion_events`, fires `kernel.react_to_events()` after `decay_moods()` |

Safety properties (unchanged constraints):
- Emotions only change the inner mood table — **no message is sent automatically** and
  nothing enters the background scheduler. Severance statements still require `SEVERANCE_OPT_IN`.
- Event firing happens after decay so a fresh feeling is not immediately discounted.
- The event trigger only writes moods that are in `MOOD_MODE_WHITELIST`.
- Verified by `test_emotion_feels_human`; replay golden refreshed for the new
  `emotion_events` / `emotion_activated` report fields (turn 3, 关系转冷).

---

## Reunion / passage of time ("更像人", in progress)

Second step toward a more human-like persona. The system already recorded the last
interaction time (`session_store.update_ts`) but never used it in answering — so opening
a chat after three days looked identical to opening it after three minutes. This adds a
time-gap awareness. Still no §9–15 refactor; still zero dependencies.

| Mechanism | What it does | Config / code |
|---|---|---|
| Time gap → reunion block | If the gap since the last turn exceeds a threshold, inject a `【久别重逢】` prompt block: "好久不见" for long gaps, "最近怎么样" for medium; optionally bring up the last聊 topic ("上次你说…后来怎么样了"). Below threshold → empty string (byte-identical prompt to old behavior). | `config.REUNION_ENABLED`, `REUNION_MIN_HOURS` (24h), `REUNION_LONG_HOURS` (72h); `prompts.render_reunion_block()` (pure), injected via `engine.chat()` → `build_answer_messages(reunion_block=...)` |
| Injectable clock | `chat/save/append` take an optional `now` (Unix seconds). Production defaults to real clock; tests inject a fixed time so "3 days later" is deterministic. | `CognitiveAgent.chat(..., now=None)`, `SessionManager.save/append(..., now=None)`, `SessionContext.append(..., now=None)` |

Safety properties:
- Reunion changes **only the prompt** — it sends no message, changes no affection/persona
  state, and never enters the scheduler. It describes time background; the model is told
  it need not recite the greeting and should follow the user's lead if they get straight
  to the point (avoids piling on pleasantries).
- The gap is captured **before** appending the current user message (append would refresh
  the anchor); new sessions never trigger reunion.
- `now` is required by the pure renderer (no hidden `time.time()` inside), so the block is
  fully deterministic. Verified by `test_reunion_feels_human`, which also exercises the
  real `chat()` path and thereby guards the `new_id` import bug (issue #18).

Post-implementation review hardening (issues #21–#25): "上次聊的话题" is now looked up
by the previous turn's `turn_id` from real archive records (never from current retrieval);
the time anchor uses the last message's `ts`; `describe()` no longer duplicates the
emotion block; event triggers respect the existing `is_core_belief` gate; all new config
is validated; and the emotion step degrades gracefully instead of half-committing an
archive. Regression-locked by `test_review_fixes`.
