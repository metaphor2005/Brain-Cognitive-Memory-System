# Cognitive Agent (Jiang Xiuyan / 江秀妍)

A Chinese cognitive-agent project with **layered memory, belief management, persona evolution, and a web UI**.  
The current default persona is **江秀妍** (nickname: **小苹果 / "Little Apple"**), implemented with Python + SQLite + a web frontend, and designed to work with DeepSeek or OpenAI-compatible chat-completions APIs.

> This is not just a chatbot with a vector database attached. Conversations feed into memory and archiving flows, beliefs can be retrieved, confirmed, superseded, and manually corrected, the persona can evolve slowly over time, and the frontend provides chat and a 3D belief star map.

---

## Current Persona

- **Name**: 江秀妍 (nickname: 小苹果 / "Little Apple")
- **Identity**: 18-year-old freshman, Class 1 (2026), Computer Science and Technology, School of Computer Science, Northeast Electric Power University
- **Background**: From Jishou, Xiangxi, Hunan; speaks Mandarin with a slight Xiangxi accent
- **Profile highlights**: 160 cm, round face, a small mole under her right eye; enjoys cosplay (mainly *Arknights*, likes Ch'en and Exusiai), likes *A Silent Voice*, loves spicy food, and has a calico cat named “辣椒” (Chili)
- **Personality**: outwardly gentle and polite; inwardly stubborn and observant. When dismissed or pressured into decisions, she becomes quiet but more specific. She has emotions and boundaries rather than a customer-service tone.

Base persona assets and initial seed/backstory beliefs live in `data/persona/` (`profile.json`, `kernel.json`, `meta.json`, `seed.json`, `avatar.jpg`).  
On first run (when no usable memory DB exists), the system can seed initial backstory/beliefs from `data/persona/seed.json` (or you can run the seed command manually).

---

## Key Features

- **Layered memory & cognitive pipeline**: short-term conversation context, topic/experience memory, structured beliefs (KG), persona state, and self-view work together in responses.
- **Belief system**: beliefs carry confidence, importance, status, source, and auditability; supports updates, supersession/deactivation, confirmation, and correction flows.
- **Manual belief correction/write-in**: when a belief is wrong, users can correct it or manually write the correct belief from the memory view or the star-map detail panel (optionally replacing/superseding the old one). User corrections are recorded with a user-corrected source.
- **3D belief star map**:
  - Radial layout: **core → category hubs → beliefs** (with hubs arranged around the center, including top/bottom placement).
  - **All beliefs are shown**, including superseded/deactivated ones.
  - Placement uses existing parameters (importance, confidence, status/active state, etc.): more important/certain beliefs tend to be closer to the center; less important or no-longer-active beliefs tend to be farther out.
  - Star-like node colors with nebula/starfield visuals; on hover highlight, non-focused elements are only lightly dimmed. Supports search, reset view, auto-rotate, category filtering, and detail inspection.
- **More natural replies**: response prompting is tuned for a more human conversational rhythm (context-following replies, flexible length, fewer template-like phrases/bullet patterns) while preserving memory-grounded, no-fabrication, in-character constraints.
- **Persona/relationship mechanisms**: persona parameters/state, affection, and proactive contact features (behavior depends on config/runtime state).
- **Web UI**: chat interface, settings, memory inspection, and belief star map visualization.

---

## Repository Structure (Overview)

- `api/` — HTTP API server
- `cognitive/` — core cognition (prompts, memory/belief storage, persona, retrieval, pipeline logic, etc.)
- `web/` — frontend UI (chat, settings, memory, star map)
- `data/persona/` — **base persona assets and initial seed data (keep this)**
- `data/corpus/` — corpus/knowledge files for retrieval
- `tests/` — tests/smoke checks
- `config.py` — global configuration
- `run.py`, `demo.py`, `maintenance.py` — run/maintenance entry points
- `.env.example` — environment variable template

---

## Quick Start

### 1. Environment
- Python 3.10+ recommended (virtual environment preferred)
- Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables
Copy `.env.example` to `.env` and fill in your API settings (example):

```ini
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-flash
LLM_MODE=api
```

> `.env` contains secrets. Do not commit it to GitHub.

### 3. Run
Start the project using the provided entry point (commonly):

```bash
python run.py
```

(Use the API/server entry script if your workflow requires it.) Then open the web UI in a browser to chat and inspect memory/star map.

### 4. Seed persona backstory/beliefs (optional)
To (re)inject initial seed/backstory beliefs (idempotency depends on implementation):

```bash
python maintenance.py --seed-persona --space jiangyan
```

---

## Belief Correction & Manual Write-in

- **In memory/belief views**: confirm, correct, or reject beliefs, and manually write the correct content.
- **In the belief star map**: click a belief node to open details and correct/write from there.
- **Write-in behavior**:
  - Provide subject, relation, object (correct content), confidence/importance, etc.
  - Optionally replace/supersede an existing belief (old belief is marked superseded/deactivated while audit history is preserved).
  - Manual corrections are recorded as a user-corrected source (e.g. `user_corrected`).

---

## Reply Style Notes

Response prompting has been adjusted to feel more like natural human chat:
- replies follow the user’s message and context instead of always producing report-style answers;
- more conversational tone, with fewer template phrases and less rigid bullet-pointing;
- mild emotional expression is allowed while staying in character;
- hard constraints remain: no fabricated memories, do not treat superseded beliefs as current truth, and state uncertainty when details are not remembered.

> Note: backend prompt changes require restarting the backend process to take effect. Frontend static changes take effect after a page refresh.

---

## Before Publishing to GitHub (Important)

If this folder is intended as a public repository, avoid uploading local/runtime/personal data:

- `.env` (API keys/secrets)
- `data/memory.db` (and `*-wal` / `*-shm`, contains real conversation/runtime memory)
- `data/user_avatar.json` (user-uploaded avatar data)
- `data/vectors/` (rebuildable vector index cache)
- `data/persona_snapshots/` (runtime persona snapshots)
- `__pycache__/`, `.venv/`, `.idea/`, `.ruff_cache/`, `*.pyc`, and other local cache/environment files

Recommended to include:
- source code (`api/`, `cognitive/`, `web/`, `tests/`, etc.)
- base persona and seed data (`data/persona/`, `data/corpus/`, `data/README.md`)
- config/docs (`.env.example`, `.gitignore`, `README.md`, `README.cn.md`, `requirements.txt`, etc.)

---

## Notes

- The persona and UI are Chinese-first; this English README is for usage/development reference.
- If the belief star map relies on a local offline 3D engine file (e.g. `web/vendor/3d-force-graph.min.js`), make sure it is included in the published copy; otherwise the star map may fail to load offline.
