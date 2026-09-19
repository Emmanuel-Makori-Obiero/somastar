# Somastar

Adaptive learning and exam intelligence: upload an exam, get a question-by-question breakdown,
a skill profile, revision items and career suggestions.

- **Frontend:** React + Vite (`src/`)
- **Backend:** FastAPI + SQLAlchemy + Alembic (`backend/`)

## Run it locally

### Backend
```bash
cd backend
python -m venv venv
source venv/Scripts/activate        # Windows Git Bash  (macOS/Linux: source venv/bin/activate)
python -m pip install -r requirements.txt
cp .env.example .env                # then edit; see "Real AI" below
uvicorn app.main:app --reload --port 8000
```
Database migrations run automatically on startup. Health check: http://localhost:8000/api/health

### Frontend
```bash
npm install
npm run dev                         # http://localhost:5173
```

## Real AI (Claude)

The default `LLM_PROVIDER=mock` works offline but does **not** read your uploaded file.
For real extraction and analysis, set in `backend/.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5
```
Claude reads the uploaded PDF/PNG/JPG directly. If it can't read a score it leaves it blank rather than guessing.

## How analysis works

`POST /api/exams` validates the upload, returns `202` immediately and analyses in the background.
The exam's `status` moves `queued → extracting → analysing_questions → generating_skills → aggregating → completed`
(or `failed` with a safe `error_message`). The frontend polls `GET /api/exams/{id}` for real progress.
Failed exams can be retried with `POST /api/exams/{id}/reanalyze`.

## Tests
```bash
cd backend && python -m pytest
```

## Changing the database schema
```bash
cd backend
alembic revision --autogenerate -m "describe change"
# review the generated file in migrations/versions/, then restart the server (or: alembic upgrade head)
```

## Production checklist
- `ENV=production`, a random `JWT_SECRET` (32+ chars), explicit `CORS_ORIGINS` — the app refuses to start otherwise.
- Postgres via `DATABASE_URL`; object storage instead of local `uploads/`.
- Run analysis in a real worker/queue once volume grows (currently FastAPI background tasks).
- Auth rate limiting is in-memory (single process); back it with Redis for multiple workers.
