"""Database setup. DATABASE_URL env, default sqlite:///./brandverity.db.

Postgres-ready via SQLAlchemy: set DATABASE_URL to a postgresql:// URL
and the same models work unchanged (see schema.sql for the Postgres DDL).
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./brandverity.db")
# Render (and some other hosts) hand out postgres:// URLs, but SQLAlchemy
# requires postgresql://, so normalize the scheme here. SQLite URLs are
# untouched by this.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
