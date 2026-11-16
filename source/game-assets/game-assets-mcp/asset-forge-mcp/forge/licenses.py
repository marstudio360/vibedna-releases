"""License classification for harvested game assets.

The whole point of ASSET FORGE is that "free" on itch.io means six different
things legally. This module turns whatever license text a page/README carries
into a structured verdict with an audit trail, so a pack can never end up in a
sold game without someone having seen the exact phrase that authorized it.

Every verdict records the matched phrase. Nothing is classified on vibes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclass
class Verdict:
    license_id: str
    name: str
    commercial_ok: bool | None      # may I sell a game containing this?
    attribution_required: bool | None
    share_alike: bool | None        # does it infect derivative work?
    redistribute_ok: bool | None    # may I ship the raw asset files onward?
    confidence: float               # 0.0 - 1.0
    matched: str = ""               # the exact substring that decided it
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def blocking(self) -> bool:
        return self.commercial_ok is False


# ---------------------------------------------------------------------------
# Rules
#
# ORDER IS LOAD-BEARING. "CC BY-NC 4.0" contains the substring "CC BY", and
# "CC BY-SA" contains it too. The restrictive variants MUST be tested first or
# a non-commercial pack silently classifies as safe-to-sell.
# ---------------------------------------------------------------------------

_RULES: list[tuple[str, str, list[str], dict]] = [
    # -- hard blockers, checked first ---------------------------------------
    (
        "CC-BY-NC",
        "Creative Commons Attribution-NonCommercial",
        [
            r"\bcc[\s\-_]?by[\s\-_]?nc(?:[\s\-_]?(?:sa|nd))?\b",
            r"attribution[\s\-]?noncommercial",
        ],
        dict(commercial_ok=False, attribution_required=True, share_alike=None,
             redistribute_ok=True, confidence=0.95),
    ),
    (
        "NONCOMMERCIAL",
        "Non-commercial / personal use only",
        [
            r"non[\s\-]?commercial(?:\s+(?:use|projects?|only))?",
            r"personal\s+use\s+only",
            # Allow a few words between the negation and "commercial" so
            # "not free for commercial use" and "may not be used in
            # commercial games" both land here.
            r"\b(?:not|never|cannot|can'?t|may\s+not|don'?t)\b[^.;]{0,30}\b(?:for|in|with)\s+commercial",
            r"\bno\s+commercial\s+use",
            r"free\s+for\s+personal\s+(?:use|projects?)\s+only",
        ],
        dict(commercial_ok=False, attribution_required=None, share_alike=None,
             redistribute_ok=None, confidence=0.8),
    ),
    (
        "CC-ND",
        "Creative Commons NoDerivatives",
        [r"\bcc[\s\-_]?by[\s\-_]?nd\b", r"no\s?derivatives?"],
        dict(commercial_ok=False, attribution_required=True, share_alike=None,
             redistribute_ok=True, confidence=0.9,),
    ),

    # -- viral / share-alike ------------------------------------------------
    #
    # GPL before CC-BY-SA on purpose: OpenGameArt content (the whole LPC set)
    # is routinely dual-licensed "GPL 3.0 / CC-BY-SA 3.0". Both are viral so
    # the flags come out identical either way, but GPL is the stricter read
    # and that is the safer label to carry forward.
    (
        "GPL",
        "GNU General Public License",
        [r"\bgpl\s?-?\s?[23](?:\.0)?\b", r"gnu\s+general\s+public"],
        dict(commercial_ok=True, attribution_required=True, share_alike=True,
             redistribute_ok=True, confidence=0.9),
    ),
    (
        "CC-BY-SA",
        "Creative Commons Attribution-ShareAlike",
        [r"\bcc[\s\-_]?by[\s\-_]?sa\b", r"attribution[\s\-]?sharealike"],
        dict(commercial_ok=True, attribution_required=True, share_alike=True,
             redistribute_ok=True, confidence=0.95),
    ),

    # -- clean public domain ------------------------------------------------
    (
        "CC0",
        "Creative Commons Zero / public domain",
        [
            r"\bcc0\b",
            r"creative\s+commons\s+zero",
            r"public\s+domain",
            r"\bunlicense\b",
            r"no\s+rights\s+reserved",
        ],
        dict(commercial_ok=True, attribution_required=False, share_alike=False,
             redistribute_ok=True, confidence=0.95),
    ),

    # -- attribution-only ---------------------------------------------------
    (
        "CC-BY",
        "Creative Commons Attribution",
        [r"\bcc[\s\-_]?by(?:[\s\-_]?[34](?:\.0)?)?\b", r"attribution\s+[34]\.0"],
        dict(commercial_ok=True, attribution_required=True, share_alike=False,
             redistribute_ok=True, confidence=0.9),
    ),
    (
        "OGA-BY",
        "OpenGameArt Attribution 3.0",
        [r"oga[\s\-_]?by", r"opengameart\s+attribution"],
        dict(commercial_ok=True, attribution_required=True, share_alike=False,
             redistribute_ok=True, confidence=0.9),
    ),
    (
        "MIT",
        "MIT License",
        [r"\bmit\s+licen[cs]e\b"],
        dict(commercial_ok=True, attribution_required=True, share_alike=False,
             redistribute_ok=True, confidence=0.9),
    ),
    (
        "APACHE-2",
        "Apache License 2.0",
        [r"apache\s+licen[cs]e[,\s]+version\s+2", r"\bapache[\s\-]2\.0\b"],
        dict(commercial_ok=True, attribution_required=True, share_alike=False,
             redistribute_ok=True, confidence=0.9),
    ),

    # -- itch.io-style prose grants ----------------------------------------
    #
    # Very common on itch: no formal license, just a sentence in the
    # description. Lower confidence on purpose -- these get surfaced for a
    # human read rather than auto-trusted.
    (
        "CUSTOM-FREE-COMMERCIAL",
        "Custom grant: free for commercial use",
        [
            # "free for commercial use" / "free in commercial projects"
            r"\bfree\s+(?:for|in)\s+(?:both\s+)?(?:any\s+)?(?:personal\s+and\s+)?commercial",
            # "free to use these in commercial projects" -- allow a short object
            # phrase between the verb and the preposition. Bounded to one
            # sentence so it can't reach across into an unrelated clause.
            r"\bfree\s+to\s+use\b[^.;]{0,60}\bcommercial",
            r"\b(?:use|used)\b[^.;]{0,40}\b(?:in|for)\s+(?:your\s+|any\s+)?commercial\s+(?:projects?|games?|work)",
            r"commercial\s+use\s+(?:is\s+)?(?:allowed|permitted|ok|fine)",
            r"you\s+(?:can|may)\s+sell\s+games?\s+(?:made\s+)?with",
        ],
        dict(commercial_ok=True, attribution_required=None, share_alike=False,
             redistribute_ok=None, confidence=0.6),
    ),
]

# Modifiers: refine an already-matched verdict rather than deciding it.
_ATTRIBUTION_HINTS = [
    r"credit\s+(?:is\s+)?required",
    r"please\s+(?:give\s+)?credit",
    r"must\s+(?:credit|attribute)",
    r"attribution\s+(?:is\s+)?required",
]
_NO_ATTRIBUTION_HINTS = [
    r"attribution\s+is\s+not\s+required",
    r"no\s+(?:credit|attribution)\s+(?:is\s+)?(?:required|needed|necessary)",
    r"credit\s+is\s+not\s+required",
]
_NO_RESELL_HINTS = [
    r"(?:do\s+not|don'?t|may\s+not|cannot)\s+(?:re)?sell\s+(?:the\s+)?(?:assets?|pack|files?)",
    r"not\s+(?:allowed\s+)?to\s+redistribute",
    r"no\s+redistribution",
]

# Prose rules match loose English, so a negation sitting just before the match
# can invert the meaning ("these are NOT free for commercial use"). Formal
# license identifiers (CC0, MIT, ...) don't need this -- a license tag is a
# name, not a claim -- so only the prose rule is guarded.
_NEGATION_GUARDED = {"CUSTOM-FREE-COMMERCIAL"}
_NEGATION_BEFORE = re.compile(
    r"\b(?:not|never|cannot|can'?t|isn'?t|aren'?t|no|except|unless|without)\b[^.;]{0,25}$"
)

_UNKNOWN = Verdict(
    license_id="UNKNOWN",
    name="No license text found",
    commercial_ok=None,
    attribution_required=None,
    share_alike=None,
    redistribute_ok=None,
    confidence=0.0,
    notes="Quarantined. A human must read the source page before this ships.",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).lower()


def _excerpt(text: str, span: tuple[int, int], pad: int = 90) -> str:
    a = max(0, span[0] - pad)
    b = min(len(text), span[1] + pad)
    return ("..." if a else "") + text[a:b].strip() + ("..." if b < len(text) else "")


# ---------------------------------------------------------------------------
# Tiered pages
#
# itch pack pages routinely carry TWO licenses: one for the free download and
# a different one for the "pay at least $N" tier. No regex can decide which
# governs the free zip, and both possible guesses are expensive -- wrongly
# permissive risks shipping a restricted asset, wrongly restrictive discards a
# usable pack. So detect the shape and quarantine with a reason.
#
# This also absorbs the "commercial or non-commercial" trap: that phrase is a
# grant of BOTH, but a naive `non-commercial` match reads it as a block.
# ---------------------------------------------------------------------------

_PAID_TIER = [
    r"pay\s+at\s+least",
    r"\b(?:premium|paid|pro|full|extended)\s+(?:version|tier|license|edition)\b",
    r"\bfree\s+version\b",
    r"\$\s?\d",
]
_BOTH_GRANT = re.compile(
    r"\bcommercial\s+(?:or|and|&|/)\s*non[\s\-]?commercial|"
    r"\bnon[\s\-]?commercial\s+(?:or|and|&|/)\s*commercial"
)


def _detect_tiered(t: str) -> Verdict | None:
    has_paid_tier = any(re.search(p, t) for p in _PAID_TIER)
    mentions_license = "licen" in t or "commercial" in t
    if has_paid_tier and mentions_license:
        m = next((re.search(p, t) for p in _PAID_TIER if re.search(p, t)), None)
        return Verdict(
            license_id="TIERED",
            name="Page carries separate free-tier and paid-tier licenses",
            commercial_ok=None, attribution_required=None,
            share_alike=None, redistribute_ok=None,
            confidence=0.0,
            matched=_excerpt(t, m.span()) if m else "",
            notes="Quarantined: two licenses on one page. A human must confirm "
                  "which one governs the free download before this ships.",
        )
    return None


def classify(text: str) -> Verdict:
    """Classify license text into a structured verdict.

    Returns UNKNOWN (quarantine) rather than guessing when nothing matches,
    and TIERED when the page grants different rights at different price tiers.
    """
    t = _norm(text)
    if not t.strip():
        return Verdict(**_UNKNOWN.as_dict())

    tiered = _detect_tiered(t)
    if tiered:
        return tiered

    # "commercial or non-commercial" grants both; don't let the bare
    # non-commercial pattern read it as a restriction.
    if _BOTH_GRANT.search(t):
        t = _BOTH_GRANT.sub(" commercial ", t)

    for lic_id, name, patterns, flags in _RULES:
        guarded = lic_id in _NEGATION_GUARDED
        for pat in patterns:
            for m in re.finditer(pat, t):
                if guarded and _NEGATION_BEFORE.search(t[:m.start()]):
                    continue  # negated grant -- keep looking
                v = Verdict(license_id=lic_id, name=name,
                            matched=_excerpt(t, m.span()), **flags)
                _apply_modifiers(v, t)
                return v

    return Verdict(**_UNKNOWN.as_dict())


def _apply_modifiers(v: Verdict, t: str) -> None:
    """Prose hints refine an already-decided verdict.

    Only fills in fields the rule left as None, or tightens a permission --
    never loosens one. A pack that says "CC0" but also "don't resell the
    assets" keeps the stricter redistribute answer.
    """
    for pat in _NO_ATTRIBUTION_HINTS:
        if re.search(pat, t):
            if v.attribution_required is None:
                v.attribution_required = False
            break
    else:
        for pat in _ATTRIBUTION_HINTS:
            if re.search(pat, t):
                v.attribution_required = True
                break

    for pat in _NO_RESELL_HINTS:
        if re.search(pat, t):
            v.redistribute_ok = False
            v.notes = (v.notes + " Source forbids redistributing the raw asset files.").strip()
            break


# ---------------------------------------------------------------------------
# Shipping policy
# ---------------------------------------------------------------------------

POLICIES = {
    # Safe to put in a game sold on Steam/itch with zero paperwork.
    "sellable_clean": dict(require_commercial=True, allow_share_alike=False,
                           allow_attribution=False, min_confidence=0.85),
    # Safe to sell, but the pack lands in CREDITS.md.
    "sellable_credited": dict(require_commercial=True, allow_share_alike=False,
                              allow_attribution=True, min_confidence=0.6),
    # Prototype only -- never ships.
    "prototype": dict(require_commercial=False, allow_share_alike=True,
                      allow_attribution=True, min_confidence=0.0),
}


def passes(v: Verdict, policy: str = "sellable_credited") -> tuple[bool, str]:
    """Does this verdict clear the given shipping policy? Returns (ok, reason)."""
    p = POLICIES[policy]

    if p["require_commercial"] and v.commercial_ok is not True:
        return False, f"commercial use not established ({v.license_id})"
    if not p["allow_share_alike"] and v.share_alike:
        return False, f"{v.license_id} is share-alike / viral"
    if not p["allow_attribution"] and v.attribution_required is not False:
        return False, f"{v.license_id} needs attribution; policy wants zero-paperwork"
    if v.confidence < p["min_confidence"]:
        return False, f"confidence {v.confidence:.2f} below {p['min_confidence']:.2f} for {policy}"
    return True, "ok"


def credit_line(pack_title: str, author: str, url: str, v: Verdict) -> str:
    return f'- **{pack_title}** by {author}: {v.name} ({v.license_id}), {url}'
