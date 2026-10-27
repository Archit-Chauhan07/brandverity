#!/usr/bin/env python3
"""Seeded end-to-end check for BrandVerity (stdlib only: urllib).

Prerequisite (run separately, from backend/):
    python seed.py
Then, with the backend running on http://localhost:8000:
    python scripts/run_seeded.py
    (or: python run_seeded.py from scripts/, BRANDVERITY_URL env overrides base)

What it does: logs in as creator, creates the 8 seeded items, reviews
each, then walks flagged items through submit -> manager approve ->
reviewer approve, and prints a PASS/FAIL table of expected vs actual
per item. Exits non-zero on any mismatch.

Nothing here publishes: walked items must end at "approved", never
"published" (publishing is Admin-only via POST /drafts/{id}/publish).
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BRANDVERITY_URL", "http://localhost:8000").rstrip("/")


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            detail = json.loads(raw)
        except ValueError:
            detail = raw
        raise SystemExit(f"HTTP {e.code} {method} {path}: {detail}")


def login(username):
    status, out = req("POST", "/auth/login", body={"username": username,
                                                  "password": "demo123"})
    assert status == 200, out
    return out["token"]


ITEMS = [
    # (label, content_type, body, meta, expected_rule_codes or None, expected_nhr)
    ("1 tone+claim", "text", "The world's best coffee, guaranteed to detox you.",
     {}, {"BR-TONE-01", "BR-CLAIM-01"}, False),
    ("2 term", "text", "Our single-origin blend from three regions.",
     {}, {"BR-TERM-01"}, False),
    ("3 fact", "text", "Since 2015, Northpeak has roasted coffee.",
     {}, {"BR-FACT-01"}, False),
    ("4 vis colour", "image", "", {"primary_color": "#FF0000", "logo_distorted": False,
     "alt_text": "A bag of Northpeak coffee", "text_color": "#1F4D3A",
     "bg_color": "#FFFFFF"}, {"BR-VIS-01"}, False),
    ("5 vis logo", "image", "", {"primary_color": "#1F4D3A", "logo_distorted": True,
     "alt_text": "A bag of Northpeak coffee", "text_color": "#1F4D3A",
     "bg_color": "#FFFFFF"}, {"BR-VIS-01"}, False),
    ("6 acc", "image", "", {"primary_color": "#1F4D3A", "logo_distorted": False,
     "alt_text": None, "text_color": "#E8DCC3", "bg_color": "#FFFFFF"},
     {"BR-ACC-01"}, False),  # at least BR-ACC-01; alt+contrast may both fire
    ("7 clean", "text", "Hand-roasted in small batches since 2019. 250 g bag.",
     {}, set(), False),
    ("8 abstain", "text", "A bold roast for slow mornings.",
     {}, set(), True),
]

WALK = {0, 1, 2, 3, 4, 5, 7}  # items 1-6 and 8; item 7 ends after review


def main():
    try:
        creator = login("creator")
        manager = login("manager")
        reviewer = login("reviewer")
    except SystemExit as e:
        print(f"FAIL: login failed ({e}). Did you run backend/seed.py first?")
        return 1

    rows = []
    all_pass = True
    for idx, (label, ctype, body, meta, expected, expected_nhr) in enumerate(ITEMS):
        _, draft = req("POST", "/drafts", token=creator,
                       body={"title": f"Seed {label}", "body": body,
                             "content_type": ctype, "meta": meta})
        did = draft["id"]
        _, review = req("POST", f"/drafts/{did}/review", token=creator)
        actual = {f["rule_code"] for f in review["findings"]}
        nhr = review["needs_human_review"]
        if label.startswith("6 "):
            codes_ok = "BR-ACC-01" in actual and actual <= {"BR-ACC-01"}
        else:
            codes_ok = actual == expected
        nhr_ok = nhr == expected_nhr
        status_ok = True
        detail = ""
        if idx in WALK:
            try:
                req("POST", f"/drafts/{did}/submit", token=creator)
                req("POST", f"/drafts/{did}/approve", token=manager,
                    body={"comment": "Manager approved"})
                _, final = req("POST", f"/drafts/{did}/approve", token=reviewer,
                               body={"comment": "Reviewer approved"})
                status_ok = final["status"] == "approved"
                detail = f"final={final['status']}"
            except SystemExit as e:
                status_ok = False
                detail = str(e)
        else:
            _, final = req("GET", f"/drafts/{did}", token=creator)
            status_ok = final["status"] == "draft"
            detail = f"final={final['status']}"
        passed = codes_ok and nhr_ok and status_ok
        all_pass = all_pass and passed
        rows.append((label, "PASS" if passed else "FAIL",
                     f"expected={sorted(expected) if expected else '[]'} "
                     f"nhr={expected_nhr}",
                     f"actual={sorted(actual) if actual else '[]'} nhr={nhr} {detail}"))

    print(f"{'item':<14} {'result':<6} {'expected':<45} actual")
    for label, result, exp, act in rows:
        print(f"{label:<14} {result:<6} {exp:<45} {act}")
    print("ALL PASS" if all_pass else "FAILURES PRESENT")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
