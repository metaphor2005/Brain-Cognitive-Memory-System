# Cognitive Agent

A **continuously running Chinese cognitive agent** with layered memory, active archiving, structured beliefs, evolvable persona, and a web visualization UI. Built with pure Python + SQLite, and compatible with DeepSeek or any OpenAI-compatible Chat Completions API.

[中文文档](README.cn.md)

> This is not a chatbot with a vector database bolted on. Each conversation turn goes through a cognitive pipeline (session/context handling, memory routing, belief extraction/update, persona/relationship state updates, retrieval when needed, and response generation). Beliefs can be confirmed, corrected, superseded, and audited. The frontend provides a WeChat-style chat UI, memory views, and a 3D belief star map.

---

## Current Persona

**Current persona: 江秀妍 (nickname: "小苹果" / Little Apple)**

- 18-year-old freshman, Class 1 (2026), Computer Science and Technology, School of Computer Science, Northeast Electric Power University
- From Jishou, Xiangxi, Hunan; speaks Mandarin with a slight Xiangxi accent
- Profile highlights: 160 cm, round face, a small mole under her right eye; enjoys cosplay (mainly *Arknights*, likes Ch'en and Exusiai), likes *A Silent Voice*, loves spicy food, and has a calico cat named "辣椒" (Chili)
- Personality: outwardly gentle and polite, tends to acknowledge emotions before responding; inwardly stubborn and observant. When dismissed or forced into decisions, she becomes quiet but more specific. She has emotions and boundaries rather than a customer-service tone.

Base persona assets and initial seed/backstory beliefs live in `data/persona/`: `profile.json`, `kernel.json`, `meta.json`, `seed.json`, and `avatar.jpg`.  
The project loads these base assets through `config.py` / persona-loading logic. When needed (e.g. first run or missing usable memory DB), initial backstory/beliefs can be seeded from `seed.json`.

---

## Current Status & Release Notes

- **Project form**: Python backend + web frontend (`web/`) + SQLite persistence (`data/`)
- **Common memory spaces**: `default` / `jiangyan` (depending on runtime args and data)
- **Base persona data**: included in `data/persona/` and intended to be kept in the repository
- **Runtime data**: `data/memory.db`, `data/vectors/`, `data/persona_snapshots/`, `data/user_avatar.json`, etc. are local runtime/personal artifacts and should be handled carefully before publishing to GitHub (see “Before Publishing to GitHub” below)

---

## What It Can Do

### 1. Layered Memory and Cognitive Replies
- **Conversation context**: keeps recent turns for response generation.
- **Topic/experience memory**: archives and consolidates conversation content for later recall.
- **Structured beliefs (KG)**: extracts key information into queryable/updatable belief records (subject/relation/object, confidence, importance, status, source, etc.).
- **Persona and self-view**: persona parameters/tendencies and self-narrative influence responses and behavior.
- **Retrieval when needed**: supplements context/memory through retrieval flows when existing material is insufficient (subject to implementation/config).

### 2. Belief Management: Confirm, Conflict, Correct, and Audit
- Beliefs can be updated, coexist, or be superseded/rejected as new information arrives (depending on relation semantics and rules).
- Supports **user confirmation, correction, and rejection**, with source tracking and audit records.
- Supports **manual write-in of correct beliefs**:
  - available from memory views or the belief star-map detail panel;
  - allows editing subject/relation/object and confidence/importance;
  - can replace/supersede an existing belief (old belief is marked superseded/deactivated while history is preserved);
  - manual corrections are recorded as user-corrected (e.g. `user_corrected`).

### 3. 3D Belief Star Map (Web Visualization)
- **Layout**: radial structure `core → category hubs → beliefs`; category hubs are distributed around the center (including top/bottom placement).
- **Full visibility**: all beliefs are displayed, including superseded/deactivated ones (distinguished by status/style).
- **Spatial meaning (using existing parameters)**: no separate “forgetting score” UI parameter is shown. Placement is derived from existing fields such as **importance, confidence, and status/active state**:
  - closer to center: generally more important and/or more certain;
  - farther out: generally less important, or no longer active/superseded/rejected.
- **Visuals and interaction**:
  - star-like node colors with nebula/starfield background;
  - on hover highlight, non-focused elements are only lightly dimmed for readability;
  - supports drag-to-rotate, zoom, search/fly-to, reset view, auto-rotate, category filtering;
  - click nodes for details and manually correct beliefs from the detail panel.

### 4. More Natural, In-Character Replies
- Response prompting has been tuned for a more human conversational style:
  - follows the user’s message naturally instead of producing report-style replies every time;
  - more conversational tone with flexible length and pacing;
  - avoids template-like phrases and rigid bullet-pointing unless explicitly requested.
- Core constraints remain:
  - grounded in memory/context, no fabricated details;
  - superseded/deactivated beliefs are not treated as current conclusions;
  - uncertainty is stated clearly when details are not remembered;
  - stays consistent with 江秀妍’s persona, emotions, and boundaries.

> Note: after changing backend prompts (e.g. `cognitive/cognition/prompts.py`), restart the backend process for new replies to take effect. Frontend static changes apply after a page refresh.

### 5. Persona, Relationship, and Proactive Mechanisms (Implementation/Config Dependent)
- Persona kernel/state participates in responses and evolution.
- Affection/relationship warmth and related states are tracked and surfaced (as implemented in the current version).
- Proactive contact features and preferences (enablement, quiet hours/rhythm, etc.) are supported depending on the current API/UI implementation.

### 6. Web UI and API
- Web UI: chat, settings, memory inspection, belief star map, etc.
- HTTP API: message handling, state/memory/settings access, and belief operations (see `api/server.py` and actual routes).

---

## Quick Start

### 1. Requirements
- Python 3.10+ (3.11/3.12 recommended)
- Windows / Linux / macOS (development and validation have been done mostly on Windows)
- A model API key (e.g. DeepSeek or an OpenAI-compatible provider)

### 2. Install Dependencies
Use a virtual environment if possible:

```bash
pip install -r requirements.txt
```

### 3. Configure `.env`
Copy `.env.example` to `.env` and fill in your settings (example):

```ini
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-flash
LLM_MODE=api
```

Other tunables (depending on `config.py` / `.env.example`) may include temperatures, token limits, timeout/retry settings, and path overrides (e.g. `DB_PATH`, `VECTOR_DIR`).

> `.env` contains secrets and local configuration. **Do not commit it to GitHub.**

### 4. Run the Project

#### Option A: CLI entry
```bash
python run.py
```
`run.py` provides a CLI/debug entry point (supports args such as `--space`, `--session`, `--debug`, `--state`; refer to the script for exact behavior).

#### Option B: Start the Web/API service
The project includes `api/server.py` (Flask) for the web UI and HTTP APIs. Run the service using your preferred workflow (direct script execution or your existing launcher/wrapper), then open the web UI in a browser.

> The recommended startup command may vary by environment; use the project’s actual scripts/entry points if you have a fixed workflow.

### 5. First Run / Seed Persona Backstory (Optional)
Base persona and initial seed beliefs live in `data/persona/seed.json`.  
To manually inject/reseed initial backstory beliefs (idempotency depends on implementation), use:

```bash
python maintenance.py --seed-persona --space jiangyan
```

---

## Repository Structure

```text
.
├─ api/                  # HTTP API / web service
├─ cognitive/            # Core cognition (prompts, memory, beliefs, persona, retrieval, orchestration, etc.)
├─ web/                  # Frontend UI (chat, settings, memory, belief star map)
├─ data/
│  ├─ persona/           # Base persona assets and seed data (profile/kernel/meta/seed/avatar)
│  ├─ corpus/            # Corpus/knowledge texts
│  └─ README.md          # Notes for the data directory
├─ docs/                 # Documentation
├─ tests/                # Tests and smoke checks
├─ config.py             # Global configuration
├─ run.py                # CLI entry point
├─ demo.py               # Demo/example script (if used)
├─ maintenance.py        # Maintenance tools (stats, daily consolidation, snapshot pruning, seed, etc.)
├─ requirements.txt      # Dependencies
├─ .env.example          # Environment variable template
├─ README.cn.md
└─ README.md
```

> Runtime may also create `data/memory.db`, `data/vectors/`, `data/persona_snapshots/`, `logs/`, and other local artifacts.

---

## Data and Persona Notes

### `data/persona/` (recommended to keep in the repo)
- `profile.json`: identity, personality, relationships, preferences, etc.
- `kernel.json`: initial persona kernel/parameters
- `meta.json`: persona metadata
- `seed.json`: initial backstory and belief seed data (for cold start/seeding)
- `avatar.jpg`: default avatar asset

### `data/corpus/` (recommended to keep)
Text corpus for retrieval/knowledge augmentation; extend as needed.

### Local runtime data (usually not for public upload)
- `data/memory.db` (and `*-wal` / `*-shm`): real conversations, memory, beliefs, and runtime state
- `data/vectors/`: rebuildable vector index cache
- `data/persona_snapshots/`: runtime persona snapshots
- `data/user_avatar.json`: user-specific avatar/personal data
- `logs/`: runtime logs

---

## Maintenance (`maintenance.py`)

Common commands (refer to the script for exact behavior):

```bash
# Daily consolidation (per space / all spaces as implemented)
python maintenance.py --daily
python maintenance.py --daily --space jiangyan

# Show stats
python maintenance.py --stats

# Prune old snapshots (keep recent N)
python maintenance.py --prune-snapshots --keep 30

# Show persona/data path info
python maintenance.py --persona-info

# Seed initial persona backstory/beliefs
python maintenance.py --seed-persona --space jiangyan
```

---

## Testing and Verification

The project includes test scripts (e.g. `tests/smoke_test.py`). On Windows PowerShell, UTF-8 output is recommended for Chinese text:

```powershell
$env:PYTHONIOENCODING='utf-8'; py tests/smoke_test.py
```

Run additional tests in `tests/` as needed.

---

## Before Publishing to GitHub (Important)

If you are publishing this as a public repository, carefully review and clean the following:

### Recommended NOT to upload
- `.env` (API keys/secrets)
- `data/memory.db`, `data/memory.db-wal`, `data/memory.db-shm` (real conversations/runtime memory)
- `data/user_avatar.json` (personal data)
- `data/vectors/` (rebuildable cache)
- `data/persona_snapshots/` (runtime snapshots)
- `.venv/`, `__pycache__/`, `.ruff_cache/`, `.idea/`, `*.pyc`, and other environment/cache files

### Recommended to keep
- source and frontend: `api/`, `cognitive/`, `web/`, `tests/`
- base persona and corpus: `data/persona/`, `data/corpus/`, `data/README.md`
- config templates and docs: `.env.example`, `.gitignore`, `README.md`, `README.cn.md`, `requirements.txt`, `docs/`

### Additional notes
- If the belief star map depends on a local offline 3D engine file (e.g. `web/vendor/3d-force-graph.min.js`), ensure it is included in the published copy; otherwise the star map may fail to load offline.
- Backend prompt/logic changes require restarting the backend process; frontend static asset updates take effect after a page refresh.

---

## Notes

- The default persona, interaction style, and primary documentation target Chinese usage scenarios.
- This English README is for developers and users; it does not change the persona’s in-character Chinese expression.
