"""SQLAlchemy models for BrandVerity (demo, Day 1 skeleton)."""
from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    users = relationship("User", back_populates="tenant")
    rules = relationship("Rule", back_populates="tenant")
    drafts = relationship("Draft", back_populates="tenant")
    custom_rules = relationship("CustomRule", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # Creator | Manager | Reviewer | Admin
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    tenant = relationship("Tenant", back_populates="users")


class Rule(Base):
    __tablename__ = "rules"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    rule_code = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False, default="v1")
    category = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    tenant = relationship("Tenant", back_populates="rules")


class CustomRule(Base):
    """A brand-library rule defined by a tenant's own admin, in a generic
    machine-checkable form (not Northpeak's hardcoded rules). One row is one
    version; a new version of the same rule_code supersedes older rows.
    kind: forbidden_words | fact_year | palette.
    params: forbidden_words -> {"words": [...]};
            fact_year -> {"year": 2019};
            palette -> {"hex": "#RRGGBB", "tolerance": 100}."""
    __tablename__ = "custom_rules"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    rule_code = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False, default="v1")
    kind = Column(String, nullable=False)
    params = Column(JSON, nullable=False, default=dict)
    text = Column(Text, nullable=False)
    tenant = relationship("Tenant", back_populates="custom_rules")


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    content_type = Column(String, nullable=False, default="text")  # "text" | "image"
    meta = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="draft")
    # draft | pending_manager | pending_reviewer | approved | published
    tenant = relationship("Tenant", back_populates="drafts")
    findings = relationship("Finding", back_populates="draft", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="draft", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="draft", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    rule_code = Column(String, nullable=False)
    rule_version = Column(String, nullable=False, default="v1")
    quoted_span = Column(Text, nullable=False, default="")
    why = Column(Text, nullable=False, default="")
    suggested_edit = Column(Text, nullable=False, default="")
    status = Column(String, nullable=False, default="open")  # open|accepted|rejected|needs_review
    draft = relationship("Draft", back_populates="findings")


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    from_status = Column(String, nullable=False)
    to_status = Column(String, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=True, default="")
    draft = relationship("Draft", back_populates="approvals")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    draft = relationship("Draft", back_populates="comments")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True, default="")
