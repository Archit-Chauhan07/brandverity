"""BrandVerity backend — FastAPI + SQLAlchemy demo (Day 1 skeleton).

Auth: demo only. Passwords are SHA-256 hashes (stdlib hashlib) and auth
tokens are random hex strings kept in memory. No passlib/jwt libraries.
Nothing auto-publishes: only POST /drafts/{id}/publish (Admin) sets
status "published"; every other transition is listed explicitly below.
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .mailer import (app_url, mail_configured, send_notification_email,
                     send_reset_email, send_verification_email)
from .models import (Approval, AuditLog, Comment, CustomRule, Draft, Finding,
                     Notification, Rule, Tenant, User, UserEmail)
from .claim_check import build_library, retrieve_claim_rules
from .pipeline import RULE_TEXTS, run_pipeline

Base.metadata.create_all(bind=engine)

# Round 3: create_all creates NEW tables only — it never adds a column
# to an existing table. AuditLog.created_at is new, so an existing
# database (e.g. the live one) would otherwise keep inserting without
# it. Add the column on startup if it is missing, in the same
# import-time-repair spirit as the demo-account repair below; a failure
# is printed and never crashes the app.
try:
    from sqlalchemy import inspect as _sa_inspect, text as _sa_text
    _insp = _sa_inspect(engine)
    if _insp.has_table("audit_logs"):
        _cols = [c["name"] for c in _insp.get_columns("audit_logs")]
        if "created_at" not in _cols:
            if engine.dialect.name == "postgresql":
                _ddl = ("ALTER TABLE audit_logs "
                        "ADD COLUMN IF NOT EXISTS created_at TEXT")
            else:
                _ddl = "ALTER TABLE audit_logs ADD COLUMN created_at TEXT"
            with engine.begin() as _conn:
                _conn.execute(_sa_text(_ddl))
            print("Audit timestamp column added to audit_logs.")
except Exception as _audit_col_exc:
    print(f"Audit timestamp column check skipped: {_audit_col_exc}")

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
    """Legacy demo scheme (deterministic SHA-256). Still used for the
    public demo accounts, which the repair block below keeps on it."""
    return hashlib.sha256(f"brandverity:{password}".encode()).hexdigest()


def hash_password_new(password: str) -> str:
    """Genuine scheme for registered users: salted PBKDF2-HMAC-SHA256,
    stdlib only (no new dependency). Format:
    pbkdf2$<iterations>$<salt hex>$<hash hex>."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(),
                             200_000)
    return f"pbkdf2$200000${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Scheme-aware: new pbkdf2 hashes verify by their own format, old
    demo hashes verify exactly as before. Demo logins are untouched."""
    if password_hash.startswith("pbkdf2$"):
        try:
            _, iters, salt, want = password_hash.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     salt.encode(), int(iters))
            return secrets.compare_digest(dk.hex(), want)
        except Exception:
            return False
    return hash_password(password) == password_hash


def _token_hash(token: str) -> str:
    """Tokens are stored hashed, so a database read alone never yields a
    usable verification or reset link."""
    return hashlib.sha256(f"brandverity-token:{token}".encode()).hexdigest()


def _expiry(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _expired(iso: str | None) -> bool:
    if not iso:
        return True
    try:
        return datetime.now(timezone.utc) > datetime.fromisoformat(iso)
    except Exception:
        return True


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


# Demo account repair: the seed above only runs when no tenant exists, so
# a partial seed (tenant created, users missing or with a wrong password
# hash) would leave the demo logins broken forever. On every import, make
# sure the 4 public demo accounts exist with the documented demo password.
# This only touches the 4 demo usernames; it never changes real users, and
# it is a no-op when the accounts are already correct.
try:
    _repair_db = SessionLocal()
    try:
        _tenant = _repair_db.query(Tenant).filter(
            Tenant.name == "Northpeak Coffee").first()
        if _tenant is not None:
            _want_hash = hash_password("demo123")
            for _username, _role in [("admin", "Admin"), ("creator", "Creator"),
                                     ("manager", "Manager"),
                                     ("reviewer", "Reviewer")]:
                _user = _repair_db.query(User).filter(
                    User.username == _username).first()
                if _user is None:
                    _repair_db.add(User(username=_username,
                                        password_hash=_want_hash,
                                        role=_role, tenant_id=_tenant.id))
                elif _user.password_hash != _want_hash:
                    _user.password_hash = _want_hash
            _repair_db.commit()
    finally:
        _repair_db.close()
except Exception as _repair_exc:
    print(f"Demo account repair skipped: {_repair_exc}")


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit(db: Session, tenant_id: int, actor_id, action: str, entity: str,
          entity_id, detail: str = ""):
    # Round 3: every new audit row carries its timestamp. Rows written
    # before this column existed keep created_at NULL (unknown time).
    db.add(AuditLog(tenant_id=tenant_id, actor_id=actor_id, action=action,
                    entity=entity, entity_id=entity_id, detail=detail,
                    created_at=_now_iso()))


def _audit_out(db: Session, log: AuditLog) -> dict:
    """One audit row as the export shows it: who (username, not just
    id), what, when (null = written before Round 3, time unknown),
    plus the decision and the rule version where this row concerns a
    specific finding — and null there otherwise, never invented."""
    actor = db.query(User).filter(User.id == log.actor_id).first() \
        if log.actor_id else None
    decision = None
    rule_code = None
    rule_version = None
    finding_status = None
    if log.action == "finding_decision" and log.entity == "finding":
        decision = log.detail or None
        finding = db.query(Finding).filter(Finding.id == log.entity_id).first()
        if finding is not None:
            rule_code = finding.rule_code
            rule_version = finding.rule_version
            finding_status = finding.status
    elif log.action.startswith("transition:"):
        # e.g. transition:draft->pending_manager — the decision is the
        # status the draft moved TO. Draft transitions cite no single
        # rule, so rule_code/rule_version stay null for these rows.
        decision = log.action.split("->", 1)[1] if "->" in log.action else None
    return {"id": log.id, "actor_id": log.actor_id,
            "actor": actor.username if actor else None,
            "action": log.action, "entity": log.entity,
            "entity_id": log.entity_id, "detail": log.detail,
            "created_at": log.created_at, "decision": decision,
            "rule_code": rule_code, "rule_version": rule_version,
            "finding_status": finding_status}


def _notify(db: Session, draft: Draft, actor: User, to_status: str):
    """Round 3 email-first notifications for a draft state change.

    Recipients are the next role in creator -> manager -> reviewer
    (plus the draft creator on a decision), all from this draft's own
    tenant — never another brand. Each attempt is recorded in the
    notifications table with its true outcome: "sent" only when
    mailer.send_email returned True, otherwise "unsent" with the
    reason. No SMTP config means no network attempt at all, just an
    unsent record. Sending a notification never changes the draft
    transition itself and never auto-publishes anything."""
    if to_status == "pending_manager":
        roles, kind = ["Manager"], "action_needed"
        creator_also = False
    elif to_status == "pending_reviewer":
        roles, kind = ["Reviewer"], "action_needed"
        creator_also = False
    elif to_status == "approved":
        roles, kind = ["Admin"], "decision"
        creator_also = True
    elif to_status == "draft":
        roles, kind = [], "decision"  # rejected: back to the creator
        creator_also = True
    elif to_status == "published":
        roles, kind = [], "decision"
        creator_also = True
    else:
        return
    recipients: dict[int, User] = {}
    for role in roles:
        for u in db.query(User).filter(User.tenant_id == draft.tenant_id,
                                       User.role == role).all():
            recipients[u.id] = u
    if creator_also and draft.creator_id and draft.creator_id != actor.id:
        creator = db.query(User).filter(User.id == draft.creator_id).first()
        if creator is not None:
            recipients[creator.id] = creator
    for recipient in recipients.values():
        if recipient.id == actor.id:
            continue
        row = db.query(UserEmail).filter(
            UserEmail.user_id == recipient.id).first()
        email = row.email if row is not None and row.verified == 1 else None
        if not mail_configured():
            status, reason = "unsent", "SMTP not configured"
        elif email is None:
            status, reason = "unsent", "no verified email on file"
        else:
            sent = send_notification_email(
                email,
                f"BrandVerity: '{draft.title or 'Untitled'}' needs your action"
                if kind == "action_needed" else
                f"BrandVerity: decision on '{draft.title or 'Untitled'}'",
                f"Draft '{draft.title or 'Untitled'}' is now {to_status}.\n\n"
                f"Open BrandVerity and check the approval queue.\n")
            status, reason = ("sent", "") if sent else ("unsent", "send failed")
        db.add(Notification(tenant_id=draft.tenant_id,
                            recipient_id=recipient.id,
                            recipient_role=recipient.role,
                            draft_id=draft.id, kind=kind, status=status,
                            reason=reason, created_at=_now_iso()))


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
                     "detail": l.detail, "created_at": l.created_at} for l in logs],
    }


# ---------- request bodies ----------
class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str = ""
    email: str = ""
    password: str = ""
    brand_name: str = ""


class TokenBody(BaseModel):
    token: str = ""


class EmailBody(BaseModel):
    email: str = ""


class ResetBody(BaseModel):
    token: str = ""
    new_password: str = ""


class DraftBody(BaseModel):
    title: str = ""
    body: str = ""
    content_type: str = "text"
    meta: dict | None = None


class ClaimCheckBody(BaseModel):
    claim: str = ""


class CommentBody(BaseModel):
    comment: str = ""
    text: str = ""


class DecisionBody(BaseModel):
    decision: str  # accept | reject


class TenantBody(BaseModel):
    name: str = ""


class CustomRuleBody(BaseModel):
    rule_code: str = ""
    kind: str = ""  # forbidden_words | fact_year | palette
    params: dict | None = None
    text: str = ""
    version: str | None = None  # omitted -> auto (v1, then v2, v3, ...)


# ---------- auth ----------
@app.post("/auth/login")
def login(payload: LoginBody, db: Session = Depends(get_db)):
    # Login accepts a username OR an email address.
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None:
        row = db.query(UserEmail).filter(
            UserEmail.email == payload.username.strip().lower()).first()
        if row is not None:
            user = db.query(User).filter(User.id == row.user_id).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    # Genuine accounts must verify their email first. Demo accounts have
    # no UserEmail row, so this gate never touches them.
    row = db.query(UserEmail).filter(UserEmail.user_id == user.id).first()
    if row is not None and not row.verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in. "
                   "Check your inbox for the verification link, or request a new one.")
    token = secrets.token_hex(32)
    TOKENS[token] = user.id
    audit(db, user.tenant_id, user.id, "login", "user", user.id, f"login {user.username}")
    db.commit()
    return {"token": token,
            "user": {"id": user.id, "username": user.username, "role": user.role,
                     "tenant_id": user.tenant_id}}


_DEMO_USERNAMES = {"admin", "creator", "manager", "reviewer"}
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


@app.post("/auth/register")
def register(payload: RegisterBody, db: Session = Depends(get_db)):
    """Genuine signup: creates a personal brand tenant where the new user
    is Admin, plus an unverified email identity. The account cannot log
    in until the emailed verification link is clicked."""
    username = (payload.username or "").strip()
    email = (payload.email or "").strip().lower()
    password = payload.password or ""
    brand = (payload.brand_name or "").strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-32 letters, digits, _ or -")
    if username in _DEMO_USERNAMES:
        raise HTTPException(
            status_code=400, detail="That username is reserved for demo accounts")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters")
    if not brand:
        raise HTTPException(status_code=400, detail="Brand name is required")
    if db.query(User).filter(User.username == username).first() is not None:
        raise HTTPException(status_code=400, detail="That username is taken")
    if db.query(UserEmail).filter(UserEmail.email == email).first() is not None:
        raise HTTPException(status_code=400, detail="That email is already registered")
    if db.query(Tenant).filter(Tenant.name == brand).first() is not None:
        raise HTTPException(status_code=400,
                            detail="A brand with this name already exists")
    tenant = Tenant(name=brand)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    user = User(username=username, password_hash=hash_password_new(password),
                role="Admin", tenant_id=tenant.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = secrets.token_urlsafe(32)
    db.add(UserEmail(user_id=user.id, email=email, verified=0,
                     verify_token_hash=_token_hash(token),
                     verify_expires=_expiry(24)))
    audit(db, tenant.id, user.id, "register", "user", user.id, username)
    db.commit()
    link = f"{app_url()}/verify?token={token}"
    sent = send_verification_email(email, link)
    return {"ok": True, "email_sent": sent,
            "message": ("Check your email for the verification link."
                        if sent else
                        "Account created, but the verification email could not "
                        "be sent yet — use the resend link on the verify page.")}


@app.post("/auth/verify-email")
def verify_email(payload: TokenBody, db: Session = Depends(get_db)):
    row = db.query(UserEmail).filter(
        UserEmail.verify_token_hash == _token_hash(payload.token or "")).first()
    if row is None or _expired(row.verify_expires):
        raise HTTPException(
            status_code=400, detail="This link is invalid or expired")
    row.verified = 1
    row.verify_token_hash = None
    row.verify_expires = None
    audit(db, _user_tenant(db, row.user_id), row.user_id,
          "verify_email", "user", row.user_id, row.email)
    db.commit()
    return {"ok": True, "message": "Email verified — you can now log in."}


def _user_tenant(db: Session, user_id: int) -> int:
    user = db.query(User).filter(User.id == user_id).first()
    return user.tenant_id if user else 0


@app.post("/auth/resend-verification")
def resend_verification(payload: EmailBody, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    row = db.query(UserEmail).filter(UserEmail.email == email).first()
    if row is None or row.verified:
        # Generic reply: never reveal whether an email is registered.
        return {"ok": True,
                "message": "If that email is registered and unverified, "
                           "a new verification link is on its way."}
    token = secrets.token_urlsafe(32)
    row.verify_token_hash = _token_hash(token)
    row.verify_expires = _expiry(24)
    db.commit()
    sent = send_verification_email(email, f"{app_url()}/verify?token={token}")
    return {"ok": True, "email_sent": sent,
            "message": "If that email is registered and unverified, "
                       "a new verification link is on its way."}


@app.post("/auth/forgot-password")
def forgot_password(payload: EmailBody, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    row = db.query(UserEmail).filter(UserEmail.email == email).first()
    if row is not None:
        token = secrets.token_urlsafe(32)
        row.reset_token_hash = _token_hash(token)
        row.reset_expires = _expiry(1)
        db.commit()
        send_reset_email(email, f"{app_url()}/reset-password?token={token}")
    # Generic reply either way: never reveal whether an email is registered.
    return {"ok": True,
            "message": "If that email is registered, a password reset link "
                       "is on its way."}


@app.post("/auth/reset-password")
def reset_password(payload: ResetBody, db: Session = Depends(get_db)):
    if len(payload.new_password or "") < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters")
    row = db.query(UserEmail).filter(
        UserEmail.reset_token_hash == _token_hash(payload.token or "")).first()
    if row is None or _expired(row.reset_expires):
        raise HTTPException(
            status_code=400, detail="This link is invalid or expired")
    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="This link is invalid")
    user.password_hash = hash_password_new(payload.new_password)
    row.reset_token_hash = None
    row.reset_expires = None
    audit(db, user.tenant_id, user.id, "reset_password", "user", user.id, "")
    db.commit()
    return {"ok": True, "message": "Password changed — you can now log in."}


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


@app.post("/tenants")
def create_tenant(payload: TenantBody, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Create a brand (tenant) with its own demo accounts. Admin only.
    Demo usernames are globally unique, so a new brand's accounts are
    suffixed with the brand slug (e.g. creator-harbor-roasters)."""
    require_role(user, "Admin")
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Brand name is required")
    if db.query(Tenant).filter(Tenant.name == name).first() is not None:
        raise HTTPException(status_code=400,
                            detail="A brand with this name already exists")
    slug = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    if not slug:
        slug = "brand"
    demo = []
    for role_lower, role in [("admin", "Admin"), ("creator", "Creator"),
                             ("manager", "Manager"), ("reviewer", "Reviewer")]:
        username = f"{role_lower}-{slug}"
        if db.query(User).filter(User.username == username).first() is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Demo username {username} is taken; pick another brand name")
        demo.append((username, role))
    tenant = Tenant(name=name)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    for username, role in demo:
        db.add(User(username=username, password_hash=hash_password("demo123"),
                    role=role, tenant_id=tenant.id))
    db.commit()
    audit(db, tenant.id, user.id, "create", "tenant", tenant.id, name)
    db.commit()
    return {"id": tenant.id, "name": tenant.name,
            "demo_users": [{"username": u, "role": r} for u, r in demo]}


@app.get("/tenants/{tenant_id}/custom-rules")
def list_custom_rules(tenant_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    rules = db.query(CustomRule).filter(CustomRule.tenant_id == tenant_id).order_by(
        CustomRule.rule_code, CustomRule.id).all()
    return [{"id": r.id, "tenant_id": r.tenant_id, "rule_code": r.rule_code,
             "version": r.version, "kind": r.kind, "params": r.params or {},
             "text": r.text} for r in rules]


@app.post("/tenants/{tenant_id}/custom-rules")
def create_custom_rule(tenant_id: int, payload: CustomRuleBody,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    require_role(user, "Admin")
    code = (payload.rule_code or "").strip()
    kind = (payload.kind or "").strip()
    text = (payload.text or "").strip()
    params = payload.params or {}
    if not code or not text:
        raise HTTPException(status_code=400, detail="rule_code and text are required")
    if kind == "forbidden_words":
        if not isinstance(params.get("words"), list) or not params["words"]:
            raise HTTPException(
                status_code=400,
                detail="forbidden_words needs params.words (non-empty list)")
    elif kind == "fact_year":
        try:
            int(params.get("year"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400,
                                detail="fact_year needs params.year (integer)")
    elif kind == "palette":
        if not params.get("hex"):
            raise HTTPException(status_code=400, detail="palette needs params.hex")
    else:
        raise HTTPException(
            status_code=400,
            detail="kind must be forbidden_words, fact_year or palette")
    existing = db.query(CustomRule).filter(CustomRule.tenant_id == tenant_id,
                                           CustomRule.rule_code == code).all()
    version = (payload.version or "").strip()
    if version:
        if any(r.version == version for r in existing):
            raise HTTPException(
                status_code=400,
                detail=f"Version {version} already exists for {code}")
    else:
        nums = []
        for r in existing:
            if r.version.startswith("v") and r.version[1:].isdigit():
                nums.append(int(r.version[1:]))
        version = f"v{max(nums) + 1}" if nums else "v1"
    row = CustomRule(tenant_id=tenant_id, rule_code=code, version=version,
                     kind=kind, params=params, text=text)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, tenant_id, user.id, "create", "custom_rule", row.id, f"{code} {version}")
    db.commit()
    return {"id": row.id, "tenant_id": row.tenant_id, "rule_code": row.rule_code,
            "version": row.version, "kind": row.kind, "params": row.params or {},
            "text": row.text}


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
    tenant = db.query(Tenant).filter(Tenant.id == draft.tenant_id).first()
    # Latest custom rule per code (highest id wins) for this tenant.
    latest: dict[str, CustomRule] = {}
    for r in db.query(CustomRule).filter(
            CustomRule.tenant_id == draft.tenant_id).order_by(CustomRule.id).all():
        latest[r.rule_code] = r
    custom = [{"rule_code": r.rule_code, "version": r.version, "kind": r.kind,
               "params": r.params or {}, "text": r.text} for r in latest.values()]
    findings, needs_human_review, note = run_pipeline(
        draft.body, draft.content_type, draft.meta or {},
        custom_rules=custom, tenant_name=tenant.name if tenant else None)
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


@app.post("/drafts/{draft_id}/claim-check")
def claim_check(draft_id: int, payload: ClaimCheckBody,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Retrieval-only claim check (Round 3, Phase 3).

    Read-only: it retrieves rules from THIS draft's tenant library
    only, by keyword overlap, and returns them (or an abstain). It
    creates no finding, changes no draft text or status, and makes no
    approval or publish decision — a human reviewer still decides.
    It is not a generative AI verdict and uses no external AI provider
    or key. Tenant isolation comes from get_draft_for_user: another
    brand's draft is a 404, so its library can never be surfaced."""
    draft = get_draft_for_user(db, draft_id, user)
    rule_rows = db.query(Rule).filter(Rule.tenant_id == draft.tenant_id).all()
    custom_rows = db.query(CustomRule).filter(
        CustomRule.tenant_id == draft.tenant_id).all()
    library = build_library(rule_rows, custom_rows)
    result = retrieve_claim_rules(payload.claim or "", library)
    return {
        "draft_id": draft.id,
        "claim": payload.claim or "",
        "method": ("retrieval-only: keyword overlap over this brand's "
                   "library only. No external AI, no generated verdict."),
        "result": result["result"],
        "rules": result["rules"],
        "message": result["message"],
        "finding_created": False,
        "draft_changed": False,
    }


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
    # Round 3: notify the next role / the creator by email. A failed or
    # unconfigured notification is recorded unsent; it never blocks
    # or changes this transition.
    _notify(db, draft, user, to_status)
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
    notes = db.query(Notification).filter(
        Notification.draft_id == draft.id).order_by(Notification.id).all()
    return {
        "draft_id": draft.id, "status": draft.status,
        "approvals": [{"id": a.id, "from_status": a.from_status, "to_status": a.to_status,
                       "actor_id": a.actor_id, "comment": a.comment} for a in approvals],
        "audit": [{"id": l.id, "action": l.action, "actor_id": l.actor_id,
                   "detail": l.detail, "created_at": l.created_at} for l in logs],
        # Round 3: the honest record of notification attempts for this
        # draft — "sent" only when mail actually went out.
        "notifications": [{"id": n.id, "recipient_id": n.recipient_id,
                           "recipient_role": n.recipient_role, "kind": n.kind,
                           "status": n.status, "reason": n.reason,
                           "created_at": n.created_at} for n in notes],
    }


@app.get("/tenants/{tenant_id}/audit-export")
def audit_export(tenant_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Round 3 per-brand audit export (JSON). Tenant-scoped: a user can
    only export their own brand's rows, never another brand's.

    Each row shows who did what, when, under which rule version, and
    what decision was made — where that information exists. Rows
    written before Round 3 have created_at null (time unknown, never
    backfilled), and rows that concern no single finding have
    rule_code/rule_version null. The response says both plainly."""
    if tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    logs = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id).order_by(AuditLog.id).all()
    rows = [_audit_out(db, l) for l in logs]
    notes = db.query(Notification).filter(
        Notification.tenant_id == tenant_id).order_by(Notification.id).all()
    users = {u.id: u.username for u in
             db.query(User).filter(User.tenant_id == tenant_id).all()}
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.name if tenant else None,
        "exported_at": _now_iso(),
        "note": ("Audit rows written before Round 3 have created_at null: "
                 "their time is unknown and was not backfilled. "
                 "rule_code/rule_version are shown only for audit rows "
                 "that concern a specific finding; draft transitions "
                 "cite no single rule, so those fields are null there."),
        "rows_without_timestamp": sum(1 for r in rows if r["created_at"] is None),
        "rows": rows,
        "notifications": [{"id": n.id,
                           "recipient": users.get(n.recipient_id),
                           "recipient_role": n.recipient_role,
                           "draft_id": n.draft_id, "kind": n.kind,
                           "status": n.status, "reason": n.reason,
                           "created_at": n.created_at} for n in notes],
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
# Deterministic rewrite suggestions (templates, not generated text): one
# per rule family, offered when a rule looks unclear from real findings.
_REWRITE_TEMPLATES = {
    "BR-TONE": "Add one allowed-phrase example to this rule, so writers can see what good looks like.",
    "BR-CLAIM": "List the approved sources a claim may cite, so writers know what evidence counts.",
    "BR-TERM": "Show one correct and one incorrect example of the term.",
    "BR-FACT": "Keep the fact in one place and quote it exactly, so writers copy it instead of recalling it.",
    "BR-VIS": "Attach the approved asset (colour swatch, logo file) to this rule.",
    "BR-ACC": "Add a pass/fail example — good alt text versus missing alt text.",
}


def _rewrite_suggestion(rule_code: str) -> str:
    for prefix, text in _REWRITE_TEMPLATES.items():
        if rule_code.startswith(prefix):
            return text
    return "Add a concrete example of a passing draft to this rule."


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
    # Most repeated mistake: the rule with the most findings.
    most_repeated = None
    if per_rule:
        top_code = sorted(per_rule.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        most_repeated = {"rule_code": top_code, "count": per_rule[top_code],
                         "rule_text": RULE_TEXTS.get(top_code, "")}
    # Least clear rule: highest rejected share among rules with >= 2
    # findings. A rule writers keep pushing back on is the one to rewrite.
    totals: dict[str, int] = {}
    rejected: dict[str, int] = {}
    for f in findings:
        totals[f.rule_code] = totals.get(f.rule_code, 0) + 1
        if f.status == "rejected":
            rejected[f.rule_code] = rejected.get(f.rule_code, 0) + 1
    least_clear = None
    candidates = [(code, rejected.get(code, 0) / total, total)
                  for code, total in totals.items() if total >= 2]
    if candidates:
        code, rate, total = sorted(
            candidates, key=lambda c: (-c[1], -c[2], c[0]))[0]
        least_clear = {"rule_code": code, "rejected": rejected.get(code, 0),
                       "total": total, "rejection_rate": round(rate, 2),
                       "rule_text": RULE_TEXTS.get(code, ""),
                       "suggested_rewrite": _rewrite_suggestion(code)}
    return {"tenant_id": tid, "findings_per_rule": per_rule,
            "drafts_per_status": per_status,
            "most_repeated_mistake": most_repeated,
            "least_clear_rule": least_clear}


# ---------- demo repair (observable) ----------
@app.get("/demo-reset")
def demo_reset(db: Session = Depends(get_db)):
    """Demo-only repair: ensure the 4 public demo accounts exist with the
    documented demo password, and report what changed. Unlike the
    import-time repair (invisible on serverless), calling this shows the
    result, so a login failure can be traced to the stored accounts or
    ruled out. It only touches the 4 demo usernames."""
    tenant = db.query(Tenant).filter(Tenant.name == "Northpeak Coffee").first()
    if tenant is None:
        raise HTTPException(status_code=500, detail="Demo tenant missing")
    want = hash_password("demo123")
    report: dict[str, str] = {}
    for _username, _role in [("admin", "Admin"), ("creator", "Creator"),
                             ("manager", "Manager"), ("reviewer", "Reviewer")]:
        _user = db.query(User).filter(User.username == _username).first()
        if _user is None:
            db.add(User(username=_username, password_hash=want,
                        role=_role, tenant_id=tenant.id))
            report[_username] = "created"
        elif _user.password_hash != want:
            _user.password_hash = want
            report[_username] = "password fixed"
        else:
            report[_username] = "already ok"
    db.commit()
    return {"tenant": tenant.name, "users": report}
