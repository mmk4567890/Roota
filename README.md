# Roota

Roota is a stateful fault-isolation assistant for industrial variable-frequency drives (VFDs). A technician starts a session for a supported fault, Roota recommends the next documented diagnostic check, the technician reports the result in natural language, and Roota updates the diagnostic state (facts known, causes ruled out / still open / confirmed) and picks the next check. Every recommendation cites the technical manual.

## Project structure

```
roota/
  frontend/   # React + Vite + TypeScript + Tailwind
  backend/    # Python + FastAPI
  AGENTS.md
  README.md
  .gitignore
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL shown in the terminal (typically http://localhost:5173).

Run frontend tests:

```bash
cd frontend
npm test
```

## Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health) · API docs (Swagger): [http://localhost:8000/api/docs](http://localhost:8000/api/docs). `/docs` itself lists ingested manuals.

### Configuration

Copy `.env.example` and set what you need. Everything has a working offline default.

| Variable | Default | Purpose |
|---|---|---|
| `ROOTA_PARSER` | `keyword` | `keyword` (offline rules) or `anthropic` (LLM translation) |
| `ANTHROPIC_API_KEY` | none | Required when `ROOTA_PARSER=anthropic`; the server will not start without it |
| `ROOTA_LLM_MODEL` | `claude-sonnet-5-5` | Model used by the Anthropic parser |
| `ROOTA_DB_PATH` | `backend/data/roota.db` | Session event log (SQLite) |
| `ROOTA_CHROMA_DIR` | `backend/data/chroma` | Vector store for ingested manuals |
| `ROOTA_DOCS_DB_PATH` | `backend/data/docs.db` | Registry of ingested manuals |

### Manuals

Put PDFs in `docs/manuals/` (gitignored), then from `backend/`:

```bash
python -m app.retrieval.ingest ../docs/manuals/<file>.pdf --doc-id <id> --title "<title>"
python scripts/check_citations.py
```

The first ingest downloads Chroma's local embedding model once. The ingest command lists any pages with no extractable text (scanned pages). `check_citations.py` lists every graph citation that points at a missing manual, a page that does not exist, or a page with no text.

### Parser evaluation

```bash
python scripts/eval_parser.py --parser keyword
python scripts/eval_parser.py --parser anthropic   # calls the real API
```

Run backend tests:

```bash
cd backend
python -X dev -m pytest -W error::DeprecationWarning -W error::ResourceWarning
```

The tests never call the Anthropic API or download models, whatever is set in your shell.

## What's next

- Session UI for technicians (Prompt 7)
- Session summary, photo input and demo (Prompt 8)
- Real fault graphs and citations from the chosen VFD manual (every `TODO(roota)` in `backend/app/graphs/data/`)
