# BrandVerity — Frontend (Day 1 skeleton)

Brand-governance demo for the CodeStar 30 hackathon, team
`architchauhan2007`. Fictional demo tenant: **Northpeak Coffee**.

Workflow: `draft` → `pending_manager` (Creator submits) →
`pending_reviewer` (Manager approves) → `approved` (Reviewer approves).
Reject returns a draft to `draft` with a comment. Nothing auto-publishes.
Only an Admin can publish an approved draft. Role/status button hiding in
the UI is display only — the backend enforces every transition.

## How to run

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Then open http://localhost:3000. The backend is expected at
`http://localhost:8000` by default (override with `NEXT_PUBLIC_API_URL`).
No live backend is needed for `npm run build`.

## Demo logins

Password for all demo users: `demo123`

| Username | Role |
| --- | --- |
| `admin` | Admin |
| `creator` | Creator |
| `manager` | Manager |
| `reviewer` | Reviewer |

Login stores the token + user in `localStorage` (`brandverity_token`,
`brandverity_user`) and sends `Authorization: Bearer <token>` on API calls.

## Page map

| Page | What it does |
| --- | --- |
| `/` | Brand intro + workflow overview + links |
| `/login` | Username/password form, stores token+user, redirects home |
| `/upload` | Create draft form (tenant default Northpeak/first tenant, title, body, content type text/image; image fields: primary_color default `#1F4D3A`, logo_distorted, alt_text, text_color, bg_color). Creates the draft, runs review, then navigates to the draft page |
| `/drafts/[id]` | Draft body + status badge, finding cards (rule_code + version, quoted span, why, suggested minimal edit, Accept/Reject), "Needs human review" banner, comments + add-comment form, revision/approval history, workflow buttons per role/status (Submit / Approve / Reject with comment / Publish) |
| `/queue` | Approval queue, drafts grouped/filtered by status, each linking to its draft page |
| `/insights` | Day 1 placeholder dashboard — real counts from `GET /insights` (findings per rule, drafts per status) as plain lists/bars |

## Code map

- `lib/api.js` — fetch wrapper attaching the Bearer token and `NEXT_PUBLIC_API_URL`, plus one helper per backend endpoint.
- `app/globals.css` — plain CSS only. Dependencies are only `next`, `react`, `react-dom` — no UI libraries.
