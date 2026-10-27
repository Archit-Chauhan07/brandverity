# BrandVerity — Round 2 Day 1 skeleton (runnable repo)

CodeStar 30, team architchauhan2007. Round 2 window: 26 Oct 10:00 AM IST → 28 Oct 10:00 AM IST.
**This is Day 1 only: a runnable skeleton, not the full product.** Local only — nothing here is deployed, submitted, or connected to any external service or AI API.

Demo tenant: **Northpeak Coffee** (fictional brand, invented for the demo) with 6 versioned library rules (BR-FACT-01, BR-TONE-01, BR-TERM-01, BR-CLAIM-01, BR-VIS-01, BR-ACC-01).

## File layout

```
brandverity/
├── README.md                  # this file
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app: auth, tenant isolation, role checks, all endpoints
│   │   ├── models.py          # Tenant, User, Rule, Draft, Finding, Approval, Comment, AuditLog
│   │   ├── database.py        # DATABASE_URL env, default SQLite
│   │   └── pipeline.py        # deterministic checks against library rules only (no AI calls)
│   ├── seed.py                # idempotent seed: Northpeak tenant, 6 rules, 4 demo users
│   ├── schema.sql             # PostgreSQL DDL matching the models (Postgres-ready)
│   ├── requirements.txt       # fastapi, uvicorn, sqlalchemy only
│   ├── brandverity.db         # SQLite DB created by seed.py (local dev only)
│   └── README.md
├── frontend/                   # Next.js 14 App Router, only next/react/react-dom
│   ├── app/
│   │   ├── page.js            # home: Northpeak intro + workflow
│   │   ├── login/page.js      # login form (token in localStorage)
│   │   ├── upload/page.js     # create draft (text/image) -> review -> draft page
│   │   ├── drafts/[id]/page.js# finding cards, accept/reject, comments, history, workflow buttons
│   │   ├── queue/page.js      # approval queue grouped by status
│   │   └── insights/page.js   # Day 1 placeholder dashboard (real counts from /insights)
│   ├── lib/api.js             # API wrapper (Bearer token, NEXT_PUBLIC_API_URL)
│   └── README.md
└── scripts/
    └── run_seeded.py          # stdlib-only end-to-end check of the 8 seeded items
```

## How to run

Backend (terminal 1):

```bash
cd brandverity/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --port 8000
```

Frontend (terminal 2):

```bash
cd brandverity/frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# open http://localhost:3000
```

Seeded end-to-end check (backend running, from `brandverity/`):

```bash
python3 scripts/run_seeded.py   # exits 0 only if all 8 items match expected
```

Demo logins (password `demo123` for all): `admin` / Admin, `creator` / Creator, `manager` / Manager, `reviewer` / Reviewer.

Workflow enforced server-side: `draft` → `pending_manager` (Creator submits) → `pending_reviewer` (Manager approves) → `approved` (Reviewer approves); reject returns to `draft` with a comment. **Nothing auto-publishes**: only an explicit Admin-only `POST /drafts/{id}/publish` (from `approved`) sets `published`. Database: SQLite by default via `DATABASE_URL`; set `DATABASE_URL` to a PostgreSQL URL to run on Postgres with `schema.sql`.

## Day 1 verification — 8 seeded items (verified by actually running them, 2026-10-26)

All 8 PASS, exit 0, via `scripts/run_seeded.py` against the running backend (upload → findings → approval walk). Frontend `npm run build` also passes (8 routes).

| # | Item | Expected | Actual | Result |
|---|------|----------|--------|--------|
| 1 | "The world's best coffee, guaranteed to detox you." | BR-TONE-01 + BR-CLAIM-01, → approved | Same | PASS |
| 2 | "Our single-origin blend from three regions." | BR-TERM-01, → approved | Same | PASS |
| 3 | "Since 2015, Northpeak has roasted coffee." | BR-FACT-01, → approved | Same | PASS |
| 4 | Image, primary colour #FF0000 | BR-VIS-01, → approved | Same | PASS |
| 5 | Image, mountain logo stretched | BR-VIS-01, → approved | Same | PASS |
| 6 | Image, no alt text, pale beige text on white | BR-ACC-01, → approved | BR-ACC-01 (missing-alt + contrast both fired) | PASS |
| 7 | "Hand-roasted in small batches since 2019. 250 g bag." | NO findings, stays draft | Same | PASS |
| 8 | "A bold roast for slow mornings." | NO hard findings, needs human review, → approved | Same | PASS |

Notes: item 6 fires two BR-ACC-01 findings (one per check) — within spec. Item 8 exercises the abstain path: no rule cited, flagged `needs_human_review`. Suggested edits are minimal and intent-preserving (e.g. tone → "A hand-roasted coffee, made in small batches.", fact → "Since 2019").

## Constraints honoured (from the submitted plan)

- Verdicts come from the brand library only, never from outside knowledge; every finding cites the exact rule code + quoted span.
- Suggestions are minimal intent-preserving edits; a human must approve at each workflow step; nothing auto-publishes or auto-overwrites.
- Tenant isolation: users only see their own tenant's data (server-enforced).
- No external AI API calls in Day 1 — deterministic rules only.

## What remains for Day 2/3

- **Day 2 — AI/retrieval:** replace/extend the deterministic pipeline with the planned RAG path (retrieval over the brand library only, claim extraction, exact-span citation, entailment check with downgrade to "needs human review", "no matching rule" abstain) behind an LLM API; keep deterministic visual checks (CIEDE2000 colour distance, logo matching, OCR) and WCAG rules; add real image upload handling (Day 1 image checks take structured meta, not uploaded files).
- **Day 2/3 — product depth:** real Postgres deployment option wired up, file uploads, richer insights dashboard (repeated mistakes, unclear guidelines), revision diffs, email/notification hooks if wanted.
- **Day 3 — judging readiness:** full 40–50-item labelled evaluation set (precision, false-positive rate, abstention rate, citation-support rate) replacing the 8-item starter; 3-minute demo script rehearsal with the Northpeak tenant; updated project PDF, completed-features list, tech/implementation details, explanation of changes vs the Round 1 plan, and three substantial Round 3 improvements (all required for the Round 2 submission form).
- **Submission (leader only):** working project link, source-code repo link, updated PDF, completed features, tech details, changes vs plan, three Round 3 improvements — via the Round 2 form. Nothing has been submitted from this build.
