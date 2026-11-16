# Cognitive Agent (Jiang Xiuyan)

A continuously running cognitive agent for Chinese-language interaction, featuring layered memory, active archiving, structured beliefs (confirm/correct/reject with traceability), an evolvable persona, and a web UI. The backend is built with Python + SQLite and works with DeepSeek or any OpenAI-compatible Chat Completions API.

[中文文档](README.cn.md)

> This is not a chatbot with a vector database bolted on. Each conversation turn goes through a cognitive pipeline: session/context handling, memory recall and routing, belief extraction and updates, persona/relationship state changes, retrieval when needed, and response generation. Beliefs support source tracking and audit history. The frontend provides chat, memory inspection, and a 3D belief star map.

---

## Persona

**Current persona: 江秀妍 (nickname: “小苹果” / Little Apple)**

- 18-year-old freshman (Class of 2026), Computer Science and Technology, School of Computer Science, Northeast Electric Power University
- From Jishou, Xiangxi, Hunan; speaks Mandarin with a slight Xiangxi accent
- Profile highlights: 160 cm, round face, a small mole under her right eye; enjoys cosplay (mainly *Arknights*, likes Ch'en and Exusiai), likes *A Silent Voice*, loves spicy food, and has a calico cat named “辣椒” (Chili)
- Personality: outwardly gentle and polite, tends to acknowledge emotions before responding; inwardly stubborn, observant, and detail-oriented. When dismissed or pressured into decisions, she becomes quiet but more specific. She has emotions and boundaries rather than a customer-service tone.

Base persona assets and seed data live in `data/persona/` (`profile.json`, `kernel.json`, `meta.json`, `seed.json`, `avatar.jpg`). Additional virtual-life/backstory materials can be found in `docs/virtual-life/` and `data/virtual-life/`.

---

## Key Features

### Layered Memory & Cognitive Replies
- **Conversation context**: keeps recent turns for response generation.
- **Topic/experience memory**: archives events and conversation content for later recall.
- **Structured beliefs (knowledge graph)**: extracts key information into queryable, updatable records (subject/relation/object, confidence, importance, status, source, etc.).
- **Persona & self-view**: persona parameters and self-narrative influence responses and can evolve over time.
- **Retrieval when needed**: supplements context/memory when available information is insufficient (depending on implementation/config).

### Belief Management & Audit
- Beliefs can be updated, coexist, or be superseded/rejected as new information arrives (depending on relation semantics and rules).
- Supports **confirm, correct, and reject** actions with source tracking and audit records.
- Supports **manual belief edits/writes** (subject, relation, object, confidence/importance). Superseded beliefs can be deactivated while history is preserved.

### 3D Memory Universe (Web Visualization)
- **Structure**: all memory stars are distributed fairly evenly along a **figure-eight (infinity) star stream** and continuously move along the stroke order of the 8; the two star bands twist in 3D and separate at the crossing instead of overlapping in the same plane.
- **Coverage**: not just beliefs, but **topics (past events), experiences, entities (people/things), persona versions, persona changes, moods, and relationship affection** — every memory type that can be expressed visually.
- **Visual mapping**: stars use a fixed absolute size; **higher importance means higher brightness and faster motion**; the slowest completes a lap in about 4 minutes and the fastest in about 2 minutes; colors are low-saturation type tints, keeping the cold gray/blue feel of a real starfield.
- **Interaction**: drag to rotate, zoom, auto-rotate, and search; click any star for details (topics show related experiences/beliefs, entities show related beliefs, beliefs can be confirmed/corrected/rejected).

### Web UI & API
- Web UI: chat, settings, memory inspection, memory universe, etc.
- HTTP API: messaging, state/memory/settings access, and belief operations (see `api/server.py` for routes).

---

## Quick Start

### 1. Requirements
- Python 3.10+ (3.11/3.12 recommended)
- A model API key (e.g. DeepSeek or an OpenAI-compatible provider)

Install dependencies (preferably in a virtual environment):

```bash
pip install -r requirements.txt
```

### 2. Configuration
Copy `.env.example` to `.env` and fill in your settings, for example:

```ini
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-flash
LLM_MODE=api
```

Other tunables (temperature, max tokens, timeout/retry, path overrides such as `DB_PATH`, `VECTOR_DIR`, etc.) are defined in `config.py` and `.env.example`.

### 3. Run

**CLI entry:**
```bash
python run.py
```
Common options include `--space`, `--session`, `--debug`, `--state` (refer to the script for exact behavior).

**Web UI / API server:**
```bash
python api/server.py
```
or
```bash
python -m api.server
```
Then open `http://127.0.0.1:8000/` (belief star map: `/starmap.html`).

> After changing backend prompts or Python logic, restart the server. Frontend static changes take effect after a page refresh.

---

## Repository Structure

```text
.
├─ api/                  # HTTP API / web service
├─ cognitive/            # Core cognition (memory, beliefs, persona, retrieval, prompts, orchestration)
├─ web/                  # Frontend UI (chat, settings, memory, memory universe)
├─ data/
│  ├─ persona/           # Base persona assets and seed data (profile/kernel/meta/seed/avatar)
│  ├─ corpus/            # Corpus/knowledge texts
│  ├─ virtual-life/      # Structured virtual-life data
│  ├─ persona_snapshots/ # Persona snapshots (runtime/consolidation output)
│  ├─ vectors/           # Vector index
│  └─ memory.db          # SQLite database (created/updated at runtime)
├─ docs/                 # Documentation (including virtual-life materials)
├─ scripts/              # Utility scripts (e.g. backstory ingestion, snapshot generation)
├─ tests/                # Tests and smoke checks
├─ config.py             # Global configuration
├─ run.py                # CLI entry point
├─ maintenance.py        # Maintenance tools
├─ requirements.txt
├─ .env.example
├─ README.md
└─ README.cn.md
```

---

## Maintenance & Scripts

`maintenance.py` provides common maintenance operations (see the script for exact arguments):

```bash
# Daily consolidation
python maintenance.py --daily
python maintenance.py --daily --space jiangyan

# Stats / persona & data path info
python maintenance.py --stats
python maintenance.py --persona-info

# Prune old snapshots (keep recent N)
python maintenance.py --prune-snapshots --keep 30

# Seed initial persona backstory/beliefs
python maintenance.py --seed-persona --space jiangyan
```

Additional helper scripts are available under `scripts/` (for example, backstory ingestion and snapshot generation).

---

## Testing

On Windows PowerShell, use UTF-8 output for readable Chinese text:

```powershell
$env:PYTHONIOENCODING='utf-8'; py tests/smoke_test.py
```

Run other tests in `tests/` as needed.

---

## Notes

- The default persona, interaction style, and primary content target Chinese-language scenarios.
- Response quality depends on the model, configuration, and current memory/belief state. When information is missing, the system should state uncertainty rather than fabricate details.
- Runtime data (database, vector index, snapshots, avatars, etc.) changes over time; handle it appropriately when sharing or migrating the project.