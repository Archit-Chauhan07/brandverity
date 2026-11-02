"""Deterministic brand-governance pipeline.

No external AI API calls. Every hard finding cites the exact rule code
and quotes the offending span from the draft (or the offending meta value
for images). Rules are the Northpeak Coffee brand library, v1.
"""
import math
import re

RULE_TEXTS = {
    "BR-FACT-01": 'Founded 2019. Roasted in small batches. Bags are 250 g.',
    "BR-TONE-01": 'Tone is warm and plain. No superlatives ("best", "#1", "world\'s").',
    "BR-TERM-01": '"Single-origin" may be used only when one origin is named. '
                  'Approved phrase: "hand-roasted in small batches".',
    "BR-CLAIM-01": "No health claims (detox, cures, boosts energy) unless an approved "
                    "source is cited. No guaranteed outcomes.",
    "BR-VIS-01": "Primary colour #1F4D3A (deep green), secondary #E8DCC3. "
                 "Logo: mountain mark, never stretched, recoloured, or "
                 "replaced by an old variant.",
    "BR-ACC-01": "Text contrast at least 4.5:1. Every image needs alt text. "
                 "Link text must describe its destination.",
}

SUBJECTIVE_WORDS = ["bold", "rich", "smooth", "delicious", "perfect"]
PRIMARY_HEX = "#1F4D3A"


def _word_present(text_lower: str, word: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text_lower) is not None


def _find_span(body: str, candidates):
    """Return the first candidate found in body (original casing), else ''."""
    low = body.lower()
    for cand in candidates:
        idx = low.find(cand.lower())
        if idx != -1:
            return body[idx:idx + len(cand)]
    return ""


def _hex_to_rgb(hex_color: str):
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"bad hex colour: {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_distance(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _relative_luminance(rgb) -> float:
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    fg, bg = _hex_to_rgb(fg_hex), _hex_to_rgb(bg_hex)
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _ocr_fact_term_findings(text: str):
    """Northpeak term/fact checks applied to text read from an image (OCR).

    Same rules as the text checks (BR-TERM-01, BR-FACT-01), with the source
    stated in every finding so a judge can tell image text apart from body
    copy. Bag weight is part of BR-FACT-01 ("Bags are 250 g"), so a bag
    weight other than 250 g in image text is a BR-FACT-01 finding too.
    Never invents a rule: only these two existing library rules are used.
    """
    low = text.lower()
    findings = []
    if "single-origin" in low and ("blend" in low or "three regions" in low
                                  or "multiple regions" in low):
        span = _find_span(text, ["single-origin blend from three regions",
                                 "single-origin blend", "single-origin"])
        findings.append({
            "rule_code": "BR-TERM-01", "rule_version": "v1",
            "quoted_span": span,
            "why": "Image text (OCR): \"Single-origin\" is contradicted by a blend / "
                   f"multiple regions: {RULE_TEXTS['BR-TERM-01']}",
            "suggested_edit": 'Replace "single-origin blend from three regions" '
                              'with "blend from three regions".',
        })
    m = re.search(r"since\s+(\d{4})", text, re.IGNORECASE)
    if m and m.group(1) != "2019":
        findings.append({
            "rule_code": "BR-FACT-01", "rule_version": "v1",
            "quoted_span": m.group(0),
            "why": f"Image text (OCR): founding year {m.group(1)} conflicts "
                   f"with the library fact (founded 2019): {RULE_TEXTS['BR-FACT-01']}",
            "suggested_edit": "Since 2019",
        })
    weight = None
    weight_span = ""
    for pattern in (r"(\d+)\s*g\s*bags?\b", r"\bbags?\s*(?:of\s*)?(\d+)\s*g\b"):
        wm = re.search(pattern, text, re.IGNORECASE)
        if wm:
            weight = wm.group(1)
            weight_span = wm.group(0)
            break
    if weight is not None and weight != "250":
        findings.append({
            "rule_code": "BR-FACT-01", "rule_version": "v1",
            "quoted_span": weight_span,
            "why": f"Image text (OCR): bag weight {weight} g conflicts with the "
                   f"library fact (bags are 250 g): {RULE_TEXTS['BR-FACT-01']}",
            "suggested_edit": "250 g bags",
        })
    return findings


def run_custom_rules(body: str, content_type: str, meta: dict, custom_rules):
    """Check a draft against a tenant's own generic rules (see CustomRule).

    Each rule is a dict with rule_code, version, kind, params, text. Only
    the latest version per rule_code should be passed in. Returns findings
    in the same shape as the Northpeak checks."""
    body = body or ""
    meta = meta or {}
    low = body.lower()
    findings = []
    for rule in custom_rules or []:
        code = rule.get("rule_code", "")
        version = rule.get("version", "v1")
        kind = rule.get("kind", "")
        params = rule.get("params") or {}
        text = rule.get("text", "")
        if kind == "forbidden_words" and content_type == "text":
            for word in params.get("words") or []:
                if _word_present(low, str(word).lower()):
                    span = _find_span(body, [str(word)])
                    findings.append({
                        "rule_code": code, "rule_version": version,
                        "quoted_span": span,
                        "why": f"Forbidden by {code}: {span!r} is not allowed. {text}",
                        "suggested_edit": f"Remove {span!r}.",
                    })
        elif kind == "fact_year" and content_type == "text":
            try:
                year = int(params.get("year"))
            except (TypeError, ValueError):
                continue
            m = re.search(r"since\s+(\d{4})", body, re.IGNORECASE)
            if m and m.group(1) != str(year):
                findings.append({
                    "rule_code": code, "rule_version": version,
                    "quoted_span": m.group(0),
                    "why": f"Founding year {m.group(1)} conflicts with the library "
                           f"fact (founded {year}): {text}",
                    "suggested_edit": f"Since {year}",
                })
        elif kind == "palette" and content_type == "image":
            primary = meta.get("primary_color")
            hex_brand = params.get("hex")
            try:
                tolerance = float(params.get("tolerance", 100))
            except (TypeError, ValueError):
                tolerance = 100.0
            if primary and hex_brand:
                try:
                    dist = _rgb_distance(_hex_to_rgb(primary), _hex_to_rgb(hex_brand))
                    if dist > tolerance:
                        findings.append({
                            "rule_code": code, "rule_version": version,
                            "quoted_span": str(primary),
                            "why": f"Primary colour {primary} is off-brand (RGB distance "
                                   f"{dist:.0f} from {hex_brand}): {text}",
                            "suggested_edit": f"Use primary colour {hex_brand}.",
                        })
                except ValueError:
                    pass
    return findings


def run_pipeline(body: str, content_type: str, meta: dict, custom_rules=None,
                 tenant_name: str | None = None):
    """Return (findings, needs_human_review, note).

    Each finding: dict with rule_code, rule_version, quoted_span, why,
    suggested_edit. Hard findings only; the abstain path never cites a rule.

    Northpeak's hardcoded checks run only for the Northpeak tenant (or when
    no tenant is given, for backward compatibility). Other tenants are
    checked only against their own custom rules, so one brand's library
    never polices another brand's drafts.
    """
    body = body or ""
    meta = meta or {}
    low = body.lower()
    findings = []
    northpeak = tenant_name is None or tenant_name == "Northpeak Coffee"

    if northpeak and content_type == "text":
        # BR-TONE-01: superlatives
        tone_hits = [w for w in ("best", "#1", "world's", "worlds") if _word_present(low, w)]
        # "#1" has no word boundary on the digit side; fall back to substring.
        if "#1" in low and "#1" not in tone_hits:
            tone_hits.append("#1")
        if tone_hits:
            span = _find_span(body, tone_hits)
            findings.append({
                "rule_code": "BR-TONE-01", "rule_version": "v1",
                "quoted_span": span,
                "why": f"Superlative {span!r} breaks the warm-and-plain tone rule: "
                       f"{RULE_TEXTS['BR-TONE-01']}",
                "suggested_edit": "A hand-roasted coffee, made in small batches.",
            })
        # BR-CLAIM-01: health claims / guaranteed outcomes
        claim_hits = [w for w in ("detox", "cure", "cures", "boosts energy", "guaranteed to")
                      if w in low]
        if claim_hits:
            span = _find_span(body, claim_hits)
            findings.append({
                "rule_code": "BR-CLAIM-01", "rule_version": "v1",
                "quoted_span": span,
                "why": f"Health/guaranteed-outcome claim {span!r} with no approved "
                       f"source cited: {RULE_TEXTS['BR-CLAIM-01']}",
                "suggested_edit": "Remove the health claim and any guaranteed outcome.",
            })
        # BR-TERM-01: single-origin contradicted by a blend / multiple regions
        if "single-origin" in low and ("blend" in low or "three regions" in low
                                      or "multiple regions" in low):
            span = _find_span(body, ["single-origin blend from three regions",
                                     "single-origin blend", "single-origin"])
            findings.append({
                "rule_code": "BR-TERM-01", "rule_version": "v1",
                "quoted_span": span,
                "why": '"Single-origin" is contradicted by a blend / multiple regions: '
                       f"{RULE_TEXTS['BR-TERM-01']}",
                "suggested_edit": 'Replace "single-origin blend from three regions" '
                                  'with "blend from three regions".',
            })
        # BR-FACT-01: founding year must be 2019
        m = re.search(r"since\s+(\d{4})", body, re.IGNORECASE)
        if m and m.group(1) != "2019":
            findings.append({
                "rule_code": "BR-FACT-01", "rule_version": "v1",
                "quoted_span": m.group(0),
                "why": f"Founding year {m.group(1)} conflicts with the library fact "
                       f"(founded 2019): {RULE_TEXTS['BR-FACT-01']}",
                "suggested_edit": "Since 2019",
            })
    elif northpeak and content_type == "image":
        # BR-VIS-01: primary colour distance from #1F4D3A
        primary = meta.get("primary_color")
        if primary:
            try:
                dist = _rgb_distance(_hex_to_rgb(primary), _hex_to_rgb(PRIMARY_HEX))
                if dist > 100:
                    findings.append({
                        "rule_code": "BR-VIS-01", "rule_version": "v1",
                        "quoted_span": str(primary),
                        "why": f"Primary colour {primary} is off-brand (RGB distance "
                               f"{dist:.0f} from #1F4D3A): {RULE_TEXTS['BR-VIS-01']}",
                        "suggested_edit": "Use primary colour #1F4D3A instead of the "
                                          "off-brand colour.",
                    })
            except ValueError:
                findings.append({
                    "rule_code": "BR-VIS-01", "rule_version": "v1",
                    "quoted_span": str(primary),
                    "why": f"Primary colour {primary!r} is not a usable brand colour: "
                           f"{RULE_TEXTS['BR-VIS-01']}",
                    "suggested_edit": "Use primary colour #1F4D3A instead of the "
                                      "off-brand colour.",
                })
        # BR-VIS-01: logo distortion
        if meta.get("logo_distorted") is True:
            findings.append({
                "rule_code": "BR-VIS-01", "rule_version": "v1",
                "quoted_span": "logo_distorted=true",
                "why": "Logo is stretched/distorted; the mountain mark must never be "
                       f"stretched: {RULE_TEXTS['BR-VIS-01']}",
                "suggested_edit": "Use the mountain mark undistorted.",
            })
        # BR-ACC-01: missing alt text
        alt = meta.get("alt_text")
        if alt is None or (isinstance(alt, str) and not alt.strip()):
            findings.append({
                "rule_code": "BR-ACC-01", "rule_version": "v1",
                "quoted_span": "alt_text missing",
                "why": f"Image has no alt text: {RULE_TEXTS['BR-ACC-01']}",
                "suggested_edit": "Add alt text and darken text to meet 4.5:1 contrast.",
            })
        # BR-ACC-01: contrast < 4.5:1
        text_color, bg_color = meta.get("text_color"), meta.get("bg_color")
        if text_color and bg_color:
            try:
                ratio = contrast_ratio(text_color, bg_color)
                if ratio < 4.5:
                    findings.append({
                        "rule_code": "BR-ACC-01", "rule_version": "v1",
                        "quoted_span": f"{text_color} on {bg_color}",
                        "why": f"Text contrast {ratio:.2f}:1 is below the required 4.5:1: "
                               f"{RULE_TEXTS['BR-ACC-01']}",
                        "suggested_edit": "Add alt text and darken text to meet 4.5:1 contrast.",
                    })
            except ValueError:
                pass

    # OCR text (Phase 2) runs for EVERY tenant's image drafts, not just
    # Northpeak: text read from the image in the browser is checked
    # against the same term/fact rules as body copy, so a violation
    # printed on the image is cited exactly like one in text. The image
    # file itself never reaches the backend; only the extracted text in
    # meta.ocr_text is checked. Logo matching is NOT built here: the
    # manual logo_distorted checkbox above remains the only logo check,
    # because no reference logo is stored.
    if content_type == "image":
        ocr_text = meta.get("ocr_text")
        if isinstance(ocr_text, str) and ocr_text.strip():
            ocr = ocr_text.strip()[:10000]
            if northpeak:
                findings.extend(_ocr_fact_term_findings(ocr))
            # A tenant's own term/fact rules, applied to image text:
            # run as text so forbidden_words and fact_year apply, while
            # palette (an image-meta rule) is not re-applied to OCR text.
            for f in run_custom_rules(ocr, "text", meta, custom_rules):
                f["why"] = "Image text (OCR): " + f["why"]
                findings.append(f)

    # The tenant's own generic rules run for every tenant, after the
    # Northpeak checks (which are skipped for other brands).
    findings.extend(run_custom_rules(body, content_type, meta, custom_rules))

    # Abstain path: no hard findings + subjective wording -> human review.
    # Northpeak-only: another brand's drafts must not be held for review
    # over wording its own library never restricted.
    needs_human_review = False
    note = None
    if northpeak and not findings and content_type == "text":
        hit = next((w for w in SUBJECTIVE_WORDS if _word_present(low, w)), None)
        if hit:
            needs_human_review = True
            note = (f"No hard rule was violated, but subjective wording ({hit!r}) "
                    f"needs a human reviewer to judge tone. No rule is cited.")
    return findings, needs_human_review, note
