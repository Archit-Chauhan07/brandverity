# BrandVerity backend (Day 1 skeleton)

FastAPI + SQLAlchemy demo for the CodeStar 30 hackathon (team
architchauhan2007). Fictional demo brand: Northpeak Coffee.
Deterministic pipeline only — no external AI API calls; every finding
cites the exact brand-library rule code and quoted span.

## Install

```bash
cd brandverity/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # fastapi, uvicorn, sqlalchemy
```

## Seed

Seed separately, before running the check (from `backend/` so the
default SQLite file `sqlite:///./brandverity.db` matches the server's):

```bash
python seed.py
```

This creates the Northpeak Coffee tenant, the 6 rules (v1), and demo
users all with password `demo123`: `admin` (Admin), `creator` (Creator),
`manager` (Manager), `reviewer` (Reviewer). Re-running seed is safe
(idempotent). Set `DATABASE_URL` to a `postgresql://` URL for Postgres
instead of SQLite; `schema.sql` holds the matching Postgres DDL.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Seeded check

With the backend running on http://localhost:8000:

```bash
python ../scripts/run_seeded.py
# (from brandverity/; or set BRANDVERITY_URL to override the base URL)
```

It logs in as creator, creates the 8 seeded items, reviews each, walks
flagged items through submit → manager approve → reviewer approve, and
prints a PASS/FAIL table, exiting non-zero on any mismatch.

## Workflow

`draft` → `pending_manager` (Creator submits) → `pending_reviewer`
(Manager approves) → `approved` (Reviewer approves). Reject at any step
returns to `draft` with a comment. Nothing auto-publishes: only the
explicit Admin-only `POST /drafts/{id}/publish` (from `approved`) sets
status `published`.

Auth: `POST /auth/login` → `{token, user}`; send
`Authorization: Bearer <token>` on later calls. Users only see their
own tenant's data; role checks are enforced server-side.
