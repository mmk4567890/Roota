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

Health check: [http://localhost:8000/health](http://localhost:8000/health)

Run backend tests:

```bash
cd backend
pytest
```

## What's next

- Fault graphs and deterministic diagnostic engine
- Session UI for technicians
- Natural-language observation translation (LLM as translator only)
- Persistent append-only session event log
