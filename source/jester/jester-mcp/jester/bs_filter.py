"""Bullshit detector: heuristic spam/affiliate/AI-slop scoring.

Score 0-100: 100 = looks legit, 0 = obvious slop.
Flag threshold default: <30 (configurable).
Does NOT delete content. Flags for downstream filtering / UI surfacing.

Rules layered, each loses points:
- Affiliate farm: title patterns ("top 10 X", "best X for", coupon codes)
- AI-gen transcript: low type-token ratio + telltale phrases
- Suspicious cadence: same creator producing >5 items/day on same topic
- Bot comments: many short comments with same fingerprint (caller passes signal)
- Stuffed keywords / clickbait

Pure heuristic, no LLM, zero cost.
"""

import re
from collections import Counter


AFFILIATE_TITLE_RX = re.compile(
    r"\b(top\s*\d+|best\s+\w+\s+(?:for|of)|\#\d+\s+ranked|coupon\s+code|"
    r"discount\s+code|use\s+code|affiliate|sponsored\s+by|review\s+\d{4})\b",
    re.I,
)

CLICKBAIT_RX = re.compile(
    r"\b(you won't believe|shocking|secret|insane|crazy|gone wrong|"
    r"what happened next|doctors hate|this one trick|nobody talks about)\b",
    re.I,
)

AI_SLOP_PHRASES = [
    "in the realm of",
    "in the ever-evolving",
    "in today's fast-paced",
    "delve into",
    "embark on",
    "navigate the complexities",
    "it is important to note",
    "as an ai",
    "as a large language model",
    "i hope this helps",
    "in conclusion,",
    "harnessing the power of",
    "unleash the power",
    "unlock the secrets",
    "game-changer",
    "paradigm shift",
]

EXCESSIVE_EMOJI_RX = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")


def _type_token_ratio(text: str) -> float:
    toks = re.findall(r"[a-z]{2,}", text.lower())
    if len(toks) < 50:
        return 1.0
    return len(set(toks)) / len(toks)


def score(item: dict, creator_cadence: int = 0) -> dict:
    """Score a finding. Returns {score, flags, reasons}.

    item: {title, content/snippet, url, source, creator_id}
    creator_cadence: items this creator has produced today on this topic (caller tracks).
    """
    title = (item.get("title") or "")[:300]
    body = (item.get("content") or item.get("snippet") or "")[:4000]
    text = f"{title} {body}"
    s = 100.0
    reasons = []

    if AFFILIATE_TITLE_RX.search(title):
        s -= 25
        reasons.append("affiliate-title-pattern")

    if CLICKBAIT_RX.search(title):
        s -= 20
        reasons.append("clickbait")

    body_low = body.lower()
    slop_hits = sum(1 for p in AI_SLOP_PHRASES if p in body_low)
    if slop_hits >= 2:
        s -= 15 + (slop_hits * 5)
        reasons.append(f"ai-slop-phrases({slop_hits})")

    ttr = _type_token_ratio(body)
    if ttr < 0.35 and len(body) > 400:
        s -= 15
        reasons.append(f"low-lexical-diversity({ttr:.2f})")

    emojis = len(EXCESSIVE_EMOJI_RX.findall(title))
    if emojis >= 3:
        s -= 10
        reasons.append("excessive-emojis")

    if creator_cadence >= 5:
        s -= 20
        reasons.append(f"suspicious-cadence({creator_cadence}/day)")

    cap_words = sum(1 for w in title.split() if w.isupper() and len(w) > 2)
    if cap_words >= 3:
        s -= 8
        reasons.append("shouting-title")

    s = max(0.0, min(100.0, s))
    return {
        "score": round(s, 1),
        "flagged": s < 30,
        "reasons": reasons,
    }


def filter_findings(items: list[dict], threshold: float = 30.0,
                    cadence_map: dict | None = None) -> dict:
    """Score every item, return {kept, flagged, stats}.
    cadence_map: {creator_id: items_today}."""
    cadence_map = cadence_map or {}
    kept, flagged = [], []
    reason_counter = Counter()
    for it in items:
        cad = cadence_map.get(it.get("creator_id", ""), 0)
        r = score(it, creator_cadence=cad)
        it_out = dict(it)
        it_out["bullshit_score"] = r["score"]
        it_out["bullshit_flagged"] = r["flagged"]
        it_out["bullshit_reasons"] = r["reasons"]
        if r["score"] >= threshold:
            kept.append(it_out)
        else:
            flagged.append(it_out)
        for rn in r["reasons"]:
            reason_counter[rn.split("(")[0]] += 1
    return {
        "kept": kept,
        "flagged": flagged,
        "stats": {
            "total": len(items),
            "kept_n": len(kept),
            "flagged_n": len(flagged),
            "filter_rate": round(len(flagged) / max(len(items), 1), 3),
            "top_reasons": reason_counter.most_common(10),
        },
    }
