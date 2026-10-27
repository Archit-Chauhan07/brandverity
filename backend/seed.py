"""Seed BrandVerity demo data. Idempotent: safe to re-run.

Creates the Northpeak Coffee tenant, 4 demo users (password "demo123"),
and the 6 brand-library rules (v1). Run from the backend/ directory so
the SQLite file matches the server's (DATABASE_URL default
sqlite:///./brandverity.db), or set DATABASE_URL explicitly.

Usage:  python seed.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import hash_password  # noqa: E402
from app.models import Rule, Tenant, User  # noqa: E402
from app.pipeline import RULE_TEXTS  # noqa: E402

RULES = [
    ("BR-FACT-01", "fact"),
    ("BR-TONE-01", "tone"),
    ("BR-TERM-01", "term"),
    ("BR-CLAIM-01", "claim"),
    ("BR-VIS-01", "visual"),
    ("BR-ACC-01", "accessibility"),
]

USERS = [
    ("admin", "Admin"),
    ("creator", "Creator"),
    ("manager", "Manager"),
    ("reviewer", "Reviewer"),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == "Northpeak Coffee").first()
        if tenant is None:
            tenant = Tenant(name="Northpeak Coffee")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"Created tenant: {tenant.name} (id={tenant.id})")
        else:
            print(f"Tenant exists: {tenant.name} (id={tenant.id})")

        for username, role in USERS:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                db.add(User(username=username, password_hash=hash_password("demo123"),
                            role=role, tenant_id=tenant.id))
                print(f"Created user: {username}/{role}")
            else:
                # Keep seed deterministic: reset demo password/role/tenant.
                user.password_hash = hash_password("demo123")
                user.role = role
                user.tenant_id = tenant.id
                print(f"User exists: {username}/{role} (password reset to demo123)")

        for rule_code, category in RULES:
            rule = db.query(Rule).filter(Rule.tenant_id == tenant.id,
                                         Rule.rule_code == rule_code).first()
            if rule is None:
                db.add(Rule(tenant_id=tenant.id, rule_code=rule_code, version="v1",
                            category=category, text=RULE_TEXTS[rule_code]))
                print(f"Created rule: {rule_code} (v1)")
            else:
                rule.version, rule.category, rule.text = "v1", category, RULE_TEXTS[rule_code]
                print(f"Rule exists: {rule_code} (v1)")
        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
