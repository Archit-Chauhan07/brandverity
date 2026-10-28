"""Vercel entry point for the BrandVerity backend.

Vercel's Python runtime serves the ASGI app named `app` in api/index.py,
and vercel.json rewrites every path to it, so the API keeps its root
paths (/auth/login, /drafts, ...) on the deployed domain.
"""
import os
import sys

# Make the backend/ directory importable (the `app` package lives there),
# whatever working directory the runtime uses.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: F401  (Vercel serves this ASGI app)
