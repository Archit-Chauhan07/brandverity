"""BrandVerity backend — FastAPI + SQLAlchemy demo (Day 1 skeleton).

Auth: demo only. Passwords are SHA-256 hashes (stdlib hashlib) and auth
tokens are random hex strings kept in memory. No passlib/jwt libraries.
Nothing auto-publishes: only POST /drafts/{id}/publish (Admin) sets
status "published"; every other transition is listed explicitly below.
"""
import hashlib
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Approval, AuditLog, Comment, Draft, Finding, Rule, Tenant, User
from .pipeline import RULE_TEXTS, run_pipeline

Base.metadata.create_all(bind=engine)

app = FastAPI(title="BrandVerity")

# CORS: the frontend calls this API from another origin (localhost:3000
# locally, any *.vercel.app deployment in production). Without this, the
# browser blocks those calls even though direct API tests pass.
# allow_origin_regex covers any Vercel deployment URL, so no code change
# is needed once the frontend address is known.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# token -> user_id (in-memory, demo only)
TOKENS: dict[str, int] = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(f"brandverity:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


# Demo seeding for hosts with no manual seed step (e.g. serverless):
# on import, if the database has no tenant yet, create the Northpeak
# demo tenant, its 4 demo users (password "demo123") and the 6 rules.
# Same data as seed.py, idempotent (the empty check skips it once data
# exists), and never crashes the app: a seed failure is printed and
# the API still starts.
try:
    _seed_db = SessionLocal()
    try:
        if _seed_db.query(Tenant).count() == 0:
            _tenant = Tenant(name="Northpeak Coffee")
            _seed_db.add(_tenant)
            _seed_db.commit()
            _seed_db.refresh(_tenant)
            for _username, _role in [("admin", "Admin"), ("creator", "Creator"),
                                     ("manager", "Manager"), ("reviewer", "Reviewer")]:
                _seed_db.add(User(username=_username,
                                  password_hash=hash_password("demo123"),
                                  role=_role, tenant_id=_tenant.id))
            for _code, _category in [("BR-FACT-01", "fact"), ("BR-TONE-01", "tone"),
                                     ("BR-TERM-01", "term"), ("BR-CLAIM-01", "claim"),
                                     ("BR-VIS-01", "visual"),
                                     ("BR-ACC-01", "accessibility")]:
                _seed_db.add(Rule(tenant_id=_tenant.id, rule_code=_code, version="v1",
                                  category=_category, text=RULE_TEXTS[_code]))
            _seed_db.commit()
            print("Demo seed: created Northpeak Coffee tenant, users and rules.")
    finally:
        _seed_db.close()
except Exception as _seed_exc:
    print(f"Demo seed skipped: {_seed_exc}")


def get_current_user(authorization: str | None = Header(default=None),
                     db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[len("Bearer "):].strip()
    user_id = TOKENS.get(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_role(user: User, *roles: str):
    if user.role not in roles:
        raise HTTPException(status_code=403, detail=f"Requires role: {'/'.join(roles)}")


def audit(db: Session, tenant_id: int, actor_id, action: str, entity: str,
          entity_id, detail: str = ""):
    db.add(AuditLog(tenant_id=tenant_id, actor_id=actor_id, action=action,
                    entity=entity, entity_id=entity_id, detail=detail))


def get_draft_for_user(db: Session, draft_id: int, user: User) -> Draft:
    draft = db.query(Draft).filter(Draft.id == draft_id,
                                   Draft.tenant_id == user.tenant_id).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def draft_out(draft: Draft, db: Session) -> dict:
    findings = db.query(Finding).filter(Finding.draft_id == draft.id).all()
    approvals = db.query(Approval).filter(Approval.draft_id == draft.id).all()
    comments = db.query(Comment).filter(Comment.draft_id == draft.id).all()
    logs = db.query(AuditLog).filter(AuditLog.entity == "draft",
                                     AuditLog.entity_id == draft.id).all()
    return {
        "id": draft.id, "tenant_id": draft.tenant_id, "creator_id": draft.creator_id,
        "title": draft.title, "body": draft.body, "content_type": draft.content_type,
        "meta": draft.meta, "status": draft.status,
        "findings": [{"id": f.id, "draft_id": f.draft_id, "rule_code": f.rule_code,
                      "rule_version": f.rule_version, "quoted_span": f.quoted_span,
                      "why": f.why, "suggested_edit": f.suggested_edit,
                      "status": f.status} for f in findings],
        "approvals": [{"id": a.id, "draft_id": a.draft_id, "from_status": a.from_status,
                       "to_status": a.to_status, "actor_id": a.actor_id,
                       "comment": a.comment} for a in approvals],
        "comments": [{"id": c.id, "draft_id": c.draft_id, "author_id": c.author_id,
                      "text": c.text} for c in comments],
        "history": [{"id": l.id, "action": l.action, "actor_id": l.actor_id,
                     "detail": l.detail} for l in logs],
    }


# ---------- request bodies ----------
class LoginBody(BaseModel):
    username: str
    password: str


class DraftBody(BaseModel):
    title: str = ""
    body: str = ""
    content_type: str = "text"
    meta: dict | None = None


class CommentBody(BaseModel):
    comment: str = ""
    text: str = ""


class DecisionBody(BaseModel):
    decision: str  # accept | reject


# ---------- auth ----------
@app.post("/auth/login")
def login(payload: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_hex(32)
    TOKENS[token] = user.id
    audit(db, user.tenant_id, user.id, "login", "user", user.id, f"login {user.username}")
    db.commit()
    return {"token": token,
            "user": {"id": user.id, "username": user.username, "role": user.role,
                     "tenant_id": user.tenant_id}}


# ---------- tenants / rules ----------
@app.get("/tenants")
def list_tenants(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Tenant isolation: a user only ever sees their own tenant.
    tenants = db.query(Tenant).filter(Tenant.id == user.tenant_id).all()
    return [{"id": t.id, "name": t.name} for t in tenants]


@app.get("/tenants/{tenant_id}/rules")
def list_rules(tenant_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    rules = db.query(Rule).filter(Rule.tenant_id == tenant_id).all()
    return [{"id": r.id, "tenant_id": r.tenant_id, "rule_code": r.rule_code,
             "version": r.version, "category": r.category, "text": r.text} for r in rules]


# ---------- drafts ----------
@app.post("/drafts")
def create_draft(payload: DraftBody, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if payload.content_type not in ("text", "image"):
        raise HTTPException(status_code=400, detail='content_type must be "text" or "image"')
    draft = Draft(tenant_id=user.tenant_id, creator_id=user.id, title=payload.title,
                  body=payload.body, content_type=payload.content_type,
                  meta=payload.meta or {}, status="draft")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    audit(db, user.tenant_id, user.id, "create", "draft", draft.id, draft.title)
    db.commit()
    return draft_out(draft, db)


@app.get("/drafts")
def list_drafts(status: str | None = None, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    q = db.query(Draft).filter(Draft.tenant_id == user.tenant_id)
    if status:
        q = q.filter(Draft.status == status)
    return [{"id": d.id, "tenant_id": d.tenant_id, "creator_id": d.creator_id,
             "title": d.title, "body": d.body, "content_type": d.content_type,
             "meta": d.meta, "status": d.status} for d in q.all()]


@app.get("/drafts/{draft_id}")
def get_draft(draft_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    return draft_out(get_draft_for_user(db, draft_id, user), db)


@app.post("/drafts/{draft_id}/review")
def review_draft(draft_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    draft = get_draft_for_user(db, draft_id, user)
    findings, needs_human_review, note = run_pipeline(draft.body, draft.content_type,
                                                      draft.meta or {})
    # Re-review replaces prior findings for this draft.
    db.query(Finding).filter(Finding.draft_id == draft.id).delete()
    stored = []
    for f in findings:
        row = Finding(draft_id=draft.id, rule_code=f["rule_code"],
                      rule_version=f["rule_version"], quoted_span=f["quoted_span"],
                      why=f["why"], suggested_edit=f["suggested_edit"], status="open")
        db.add(row)
        stored.append(row)
    audit(db, user.tenant_id, user.id, "review", "draft", draft.id,
          f"{len(findings)} finding(s); needs_human_review={needs_human_review}")
    db.commit()
    for row in stored:
        db.refresh(row)
    return {"draft_id": draft.id, "status": draft.status,
            "needs_human_review": needs_human_review, "note": note,
            "findings": [{"id": r.id, "rule_code": r.rule_code,
                          "rule_version": r.rule_version, "quoted_span": r.quoted_span,
                          "why": r.why, "suggested_edit": r.suggested_edit,
                          "status": r.status} for r in stored]}


@app.post("/drafts/{draft_id}/findings/{finding_id}/decision")
def finding_decision(draft_id: int, finding_id: int, payload: DecisionBody,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    draft = get_draft_for_user(db, draft_id, user)
    finding = db.query(Finding).filter(Finding.id == finding_id,
                                       Finding.draft_id == draft.id).first()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    if payload.decision == "accept":
        finding.status = "accepted"
    elif payload.decision == "reject":
        finding.status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="decision must be accept or reject")
    audit(db, user.tenant_id, user.id, "finding_decision", "finding", finding.id,
          payload.decision)
    db.commit()
    db.refresh(finding)
    return {"id": finding.id, "rule_code": finding.rule_code, "status": finding.status}


def _transition(db: Session, draft: Draft, user: User, to_status: str, comment: str):
    from_status = draft.status
    draft.status = to_status
    db.add(Approval(draft_id=draft.id, from_status=from_status, to_status=to_status,
                    actor_id=user.id, comment=comment or ""))
    if comment:
        db.add(Comment(draft_id=draft.id, author_id=user.id, text=comment))
    audit(db, user.tenant_id, user.id, f"transition:{from_status}->{to_status}",
          "draft", draft.id, comment or "")
    db.commit()
    db.refresh(draft)
    return draft_out(draft, db)


@app.post("/drafts/{draft_id}/submit")
def submit_draft(draft_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    require_role(user, "Creator")
    draft = get_draft_for_user(db, draft_id, user)
    if draft.status != "draft":
        raise HTTPException(status_code=400, detail="Only a draft can be submitted")
    return _transition(db, draft, user, "pending_manager", "")


@app.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: int, payload: CommentBody, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    draft = get_draft_for_user(db, draft_id, user)
    comment = payload.comment or payload.text or ""
    if draft.status == "pending_manager":
        require_role(user, "Manager")
        return _transition(db, draft, user, "pending_reviewer", comment)
    if draft.status == "pending_reviewer":
        require_role(user, "Reviewer")
        return _transition(db, draft, user, "approved", comment)
    raise HTTPException(status_code=400,
                        detail="Nothing to approve in current status")


@app.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: int, payload: CommentBody, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    draft = get_draft_for_user(db, draft_id, user)
    comment = payload.comment or payload.text or ""
    if draft.status == "pending_manager":
        require_role(user, "Manager")
    elif draft.status == "pending_reviewer":
        require_role(user, "Reviewer")
    else:
        raise HTTPException(status_code=400,
                            detail="Only a pending draft can be rejected")
    # Reject at any step returns to draft with a comment.
    return _transition(db, draft, user, "draft", comment)


@app.post("/drafts/{draft_id}/comments")
def add_comment(draft_id: int, payload: CommentBody, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    draft = get_draft_for_user(db, draft_id, user)
    text = payload.text or payload.comment or ""
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    row = Comment(draft_id=draft.id, author_id=user.id, text=text)
    db.add(row)
    audit(db, user.tenant_id, user.id, "comment", "draft", draft.id, text)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "draft_id": row.draft_id, "author_id": row.author_id,
            "text": row.text}


@app.get("/drafts/{draft_id}/history")
def draft_history(draft_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    draft = get_draft_for_user(db, draft_id, user)
    approvals = db.query(Approval).filter(Approval.draft_id == draft.id).all()
    logs = db.query(AuditLog).filter(AuditLog.entity == "draft",
                                     AuditLog.entity_id == draft.id).all()
    return {
        "draft_id": draft.id, "status": draft.status,
        "approvals": [{"id": a.id, "from_status": a.from_status, "to_status": a.to_status,
                       "actor_id": a.actor_id, "comment": a.comment} for a in approvals],
        "audit": [{"id": l.id, "action": l.action, "actor_id": l.actor_id,
                   "detail": l.detail} for l in logs],
    }


@app.post("/drafts/{draft_id}/publish")
def publish_draft(draft_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """The ONLY path to published. Admin only, from approved."""
    require_role(user, "Admin")
    draft = get_draft_for_user(db, draft_id, user)
    if draft.status != "approved":
        raise HTTPException(status_code=400,
                            detail="Only an approved draft can be published")
    return _transition(db, draft, user, "published", "")


# ---------- insights ----------
@app.get("/insights")
def insights(tenant_id: int | None = None, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    tid = tenant_id if tenant_id is not None else user.tenant_id
    if tid != user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    drafts = db.query(Draft).filter(Draft.tenant_id == tid).all()
    draft_ids = [d.id for d in drafts]
    findings = (db.query(Finding).filter(Finding.draft_id.in_(draft_ids)).all()
                if draft_ids else [])
    per_rule: dict[str, int] = {}
    for f in findings:
        per_rule[f.rule_code] = per_rule.get(f.rule_code, 0) + 1
    per_status: dict[str, int] = {}
    for d in drafts:
        per_status[d.status] = per_status.get(d.status, 0) + 1
    return {"tenant_id": tid, "findings_per_rule": per_rule,
            "drafts_per_status": per_status}
