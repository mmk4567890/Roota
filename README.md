# Roota

[![CI](https://github.com/mmk4567890/roota/actions/workflows/ci.yml/badge.svg)](https://github.com/mmk4567890/roota/actions/workflows/ci.yml)

Stateful fault isolation for industrial variable-frequency drives.

## Why

Technicians diagnose drive faults from long PDF manuals. Roota walks them through the documented checks one at a time, updates what is known from their answers, and cites the manual page for every recommendation — so the next step is always grounded in the procedure, not guesswork.

## Screenshots

![Session screen](docs/session.png)

![Session summary](docs/summary.png)

> Replace these placeholders with real captures of a live session and a completed summary.

## Architecture

```mermaid
flowchart LR
  UI[React UI] --> API[FastAPI]
  API --> Engine[Diagnostic engine]
  API --> Log[(Session event log<br/>SQLite)]
  API --> Parser[Observation parser<br/>keyword or LLM]
  API --> Retrieval[Manual retrieval<br/>Chroma]
  Engine --> Graphs[Fault graphs JSON]
  Retrieval --> Manuals[Ingested manuals]
```

Design decisions:

- The diagnostic engine is deterministic and separate from the language parser — the parser only translates technician wording into field values.
- Sessions are event-sourced (append-only SQLite log) with undo; current state is always replayed.
- Causes can be confirmed, ruled out, open, or inconclusive when checks finish without a clear outcome.
- Every check and corrective action carries a manual citation (`doc_id`, section, page).
- The default keyword parser runs fully offline; the Anthropic parser is optional.

## Quick start

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (typically http://localhost:5173). API docs: http://localhost:8000/api/docs.

Copy `.env.example` for optional settings (`ROOTA_PARSER=keyword` by default).

## Getting the manual

The ABB ACS580 firmware manual (document **3AXD50000016097**, Rev J) is not included for copyright reasons. Download it from [ABB's library](https://library.abb.com/), place the PDF in `docs/manuals/`, then from `backend/`:

```bash
python -m app.retrieval.prefetch
python -m app.retrieval.ingest ../docs/manuals/<file>.pdf --doc-id abb_acs580_fw --title "ABB ACS580 firmware manual"
python scripts/check_citations.py
```

Without the manual Roota still runs, but recommendations show no cited passages.

## Try it

Start a session for **ABB ACS580 drive overtemperature**, then type observations such as:

1. `The cooling fan is not running.` → root cause: cooling fan failure.
2. `Fan is spinning fine but the vents are packed with dust.` → continues; then `Heatsink fins are full of dust.` → blocked airflow / dusty heatsink.
3. `Fan is fine, vents clear, heatsink clean.` then `Room is cool.` then `Motor matches the drive.` → all causes ruled out → escalate.
4. Escalation path with inconclusive fan: `The cooling fan is noisy.` then clear the rest (`vents clear`, `heatsink clean`, `room is cool`, `motor matches the drive`) → escalate, naming the noisy fan as inconclusive.

Use **Enter values directly** if you want to set fields without natural language.

## Testing

```bash
# Backend — expect 249 passed, 3 skipped (live tests opt-in with --live)
cd backend
python -X dev -m pytest -W error::DeprecationWarning -W error::ResourceWarning

# Keyword parser eval against the shipped ACS580 graph — 70/70 cases, 83/83 fields
python scripts/eval_parser.py --parser keyword

# Frontend — expect 28 passed; also type-check + production build
cd frontend
npm test
npm run build
```

## Roadmap

- More fault graphs beyond ACS580 overtemperature
- Photo observations (keypad / heatsink images as structured facts)
