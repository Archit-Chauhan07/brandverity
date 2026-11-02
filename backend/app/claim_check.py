"""Retrieval-only claim checking (CodeStar Round 3, Phase 3).

This is NOT a generative AI and NOT an external LLM call. There is no
AI library, no AI key, and no network call in this module. Given a claim
text, it retrieves rules from THAT tenant's own brand library only
(Rule rows plus the latest version of each CustomRule), ranked by
transparent keyword overlap, and returns them with their exact rule
code, version, and library text.

It never invents a rule, never cites a rule that is not in the tenant's
library, never changes draft text, never creates a finding, and never
approves or publishes anything. A human reviewer still decides what
any retrieved rule means for the claim. If no rule is clearly relevant,
the result is an abstain: no finding, flag for human review.
"""

import re

# Words too generic to count as evidence of relevance. Everything else
# in the claim is a keyword.
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "we", "our", "us", "you", "your", "it", "its", "this", "that",
    "in", "on", "at", "to", "for", "with", "and", "or", "of", "from",
    "by", "as", "has", "have", "had", "do", "does", "made", "makes",
    "not", "no", "but", "than", "then", "so", "such", "all", "any",
    "can", "will", "just", "very", "also", "each", "per",
}

# A rule is returned only when its relevance score reaches this.
# Score: a keyword found in exactly one library rule counts 2 (it is
# distinctive to that rule); a keyword found in several rules counts 1.
# So one distinctive keyword, or two shared keywords, is enough — a
# single generic word, or nothing at all, abstains.
RELEVANCE_THRESHOLD = 2
MAX_RULES = 3


def _tokens(text: str) -> list[str]:
    """Lowercase word tokens; hyphens and possessives are split so
    'single-origin' and 'single origin' tokenise the same way."""
    text = (text or "").lower().replace("'", " ").replace("-", " ")
    return re.findall(r"[a-z0-9]+", text)


def _claim_keywords(claim: str) -> list[str]:
    """Distinct claim keywords, in order of first appearance."""
    seen: list[str] = []
    for token in _tokens(claim):
        if len(token) < 2 or token in STOPWORDS:
            continue
        if token not in seen:
            seen.append(token)
    return seen


def _matches(claim_word: str, rule_word: str) -> bool:
    """Exact match, or an inflected form with a short suffix ('detoxes'
    / 'detox', 'cures' / 'cure'). The suffix is capped at 2 letters on
    purpose: without the cap, compounds collide ('worldwide' would
    match 'world', 'everything' would match 'every') and unrelated
    claims would falsely surface rules."""
    if claim_word == rule_word:
        return True
    if len(claim_word) >= 4 and len(rule_word) >= 4:
        if claim_word.startswith(rule_word) and len(claim_word) - len(rule_word) <= 2:
            return True
        if rule_word.startswith(claim_word) and len(rule_word) - len(claim_word) <= 2:
            return True
    return False


def _matched_span(claim: str, keyword: str) -> str:
    """The keyword as it actually appears in the claim (original
    casing), or '' if it only matched by stem. Never invented text."""
    low = (claim or "").lower()
    idx = low.find(keyword)
    if idx != -1:
        return claim[idx:idx + len(keyword)]
    return ""


def build_library(rule_rows, custom_rule_rows):
    """Assemble one tenant's library from its DB rows only.

    rule_rows: Rule objects (rule_code, version, category, text).
    custom_rule_rows: CustomRule objects; only the latest version per
    rule_code is kept (highest id wins, same rule as the review
    endpoint). A custom rule with the same code as a seeded rule
    supersedes it. No rule is ever added from outside these rows."""
    library: dict[str, dict] = {}
    for row in rule_rows or []:
        library[row.rule_code] = {
            "rule_code": row.rule_code,
            "rule_version": row.version,
            "category": row.category,
            "text": row.text,
            "searchable": f"{row.rule_code} {row.category} {row.text}",
        }
    latest: dict[str, object] = {}
    for row in sorted(custom_rule_rows or [], key=lambda r: r.id):
        latest[row.rule_code] = row
    for row in latest.values():
        params = row.params or {}
        extra_parts = [str(row.kind)]
        if isinstance(params.get("words"), list):
            extra_parts.extend(str(w) for w in params["words"])
        if params.get("year") is not None:
            extra_parts.append(str(params["year"]))
        if params.get("hex"):
            extra_parts.append(str(params["hex"]))
        library[row.rule_code] = {
            "rule_code": row.rule_code,
            "rule_version": row.version,
            "category": row.kind,
            "text": row.text,
            "searchable": f"{row.rule_code} {' '.join(extra_parts)} {row.text}",
        }
    return list(library.values())


def retrieve_claim_rules(claim: str, library: list[dict]) -> dict:
    """Retrieve the most relevant library rules for a claim.

    Returns a dict with result "relevant" or "abstain", a list of at
    most MAX_RULES rules (each with exact code, version, library text,
    score, and matched keywords), and a plain message. This function
    reads only the supplied library and the claim; it writes nothing
    and creates no findings."""
    claim = claim or ""
    keywords = _claim_keywords(claim)
    if not keywords or not library:
        return {
            "result": "abstain",
            "rules": [],
            "message": ("No library rule clearly matches this claim, so it "
                        "is flagged for human review. No finding was created."),
        }

    # Tokenise each rule's searchable text once, then score.
    rule_tokens: dict[str, list[str]] = {}
    for entry in library:
        rule_tokens[entry["rule_code"]] = _tokens(entry["searchable"])

    # Document frequency per claim keyword: how many library rules it
    # matches. A keyword matching only one rule is distinctive (2
    # points); one matching several is shared (1 point).
    scored = []
    for entry in library:
        tokens = rule_tokens[entry["rule_code"]]
        matched: list[str] = []
        score = 0
        for keyword in keywords:
            if not any(_matches(keyword, token) for token in tokens):
                continue
            matched.append(keyword)
            df = sum(
                1 for other in library
                if any(_matches(keyword, t)
                       for t in rule_tokens[other["rule_code"]])
            )
            score += 2 if df <= 1 else 1
        if score >= RELEVANCE_THRESHOLD:
            span = ""
            for keyword in matched:
                span = _matched_span(claim, keyword)
                if span:
                    break
            scored.append({
                "rule_code": entry["rule_code"],
                "rule_version": entry["rule_version"],
                "category": entry["category"],
                "text": entry["text"],
                "score": score,
                "matched_keywords": matched,
                "matched_span": span,
            })

    scored.sort(key=lambda r: (-r["score"], -len(r["matched_keywords"]),
                               r["rule_code"]))
    rules = scored[:MAX_RULES]
    if not rules:
        return {
            "result": "abstain",
            "rules": [],
            "message": ("No library rule clearly matches this claim, so it "
                        "is flagged for human review. No finding was created."),
        }
    return {
        "result": "relevant",
        "rules": rules,
        "message": ("These library rules were retrieved by keyword overlap "
                    "with the claim. They are candidates for a human "
                    "reviewer to judge — not a verdict, and no finding "
                    "was created by this check."),
    }
