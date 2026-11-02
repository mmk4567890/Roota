# Routa

Routa is an SOP drift detection tool. Upload a reference SOP alongside a current process document, and Routa identifies operational deviations before they become operational risk.

> **MVP status:** This repository is an early scaffold. The UI and API health check are in place; document parsing, AI analysis, authentication, and drift detection are not implemented yet.

## Project structure

```
routa/
  frontend/   # React + Vite + TypeScript + Tailwind
  backend/    # Python + FastAPI
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

- Document upload and parsing
- Drift analysis between reference SOP and current process
- Authentication and persistent storage
