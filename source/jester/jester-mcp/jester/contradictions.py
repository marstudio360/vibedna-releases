"""
Jester Contradiction Engine: surface opposing claims across sources.

When two findings from DIFFERENT sources make opposite claims about the
same subject, flag the contradiction explicitly.

Algorithm:
  1. Cluster findings by subject (same Jaccard fingerprint as corroborate.py)
  2. Within each cluster, run sentiment + negation analysis on each item
  3. If cluster contains BOTH positive and negative signals → contradiction
  4. Return contradiction pairs with source attribution + confidence

No LLM. Pure regex + lexicon heuristics. Fast enough to run inline.
"""

import re
from collections import defaultdict

from corroborate import fingerprint, jaccard


# ── Sentiment lexicon ─────────────────────────────────────────────────────────

_POSITIVE = {
    # market / trend
    "growing", "rising", "exploding", "hot", "profitable", "winning",
    "dominant", "best", "leading", "popular", "successful", "booming",
    "thriving", "accelerating", "increasing", "surging", "opportunity",
    "bullish", "underrated", "hidden", "gem", "up",
    # tool / product preference
    "better", "prefer", "preferred", "recommend", "recommended", "love",
    "winner", "wins", "superior", "faster", "smarter", "cleaner",
    "solid", "reliable", "excellent", "great", "amazing", "impressed",
    "switched", "chose", "choosing", "sticking", "staying", "keep",
    "worth", "useful", "powerful", "smooth", "polished", "stable",
    # developer sentiment
    "productive", "efficient", "saves", "helps", "impressed", "happy",
    # comparison / "vs" language: tool preference
    "wins", "winner", "beats", "dominates", "outperforms", "surpasses",
    "clear", "obvious", "easily", "hands", "down", "definitely", "absolutely",
    "finally", "switched", "migrated", "moved", "converted",
}

_NEGATIVE = {
    # market / trend
    "dying", "dead", "declining", "falling", "failing", "saturated",
    "oversaturated", "crowded", "impossible", "avoid", "waste", "scam",
    "overhyped", "hype", "bubble", "down", "dropping", "losing",
    "bearish", "worst", "broken", "abandoned", "deprecated",
    # tool / product rejection
    "worse", "inferior", "slower", "buggy", "terrible", "awful",
    "disappointing", "disappointed", "regret", "dropped", "left",
    "switched", "quit", "uninstalled", "removed", "replaced",
    "mediocre", "frustrating", "frustration", "annoying", "unreliable",
    "unstable", "crashes", "laggy", "bloated", "overpriced",
    # developer sentiment
    "harmful", "hurts", "ruins", "destroys", "deskills", "dangerous",
    "problematic", "concerned", "worried", "skeptical", "skepticism",
    # comparison / "vs" language: rejection
    "loses", "loser", "behind", "lacking", "disappoints", "underwhelming",
    "overrated", "hyped", "overhyped", "avoid", "skip", "dropped",
    "uninstalled", "reverted", "went", "back", "regretted",
}

_NEGATION_RE = re.compile(
    r"\b(not|no|never|isn'?t|aren'?t|wasn'?t|doesn'?t|don'?t|won'?t|can'?t)\b\s+\w+",
    re.I,
)

_TOKEN_RE = re.compile(r"[a-z]{4,}")


def _sentiment(text: str) -> str:
    """Return 'positive', 'negative', or 'neutral'."""
    tokens = set(_TOKEN_RE.findall(text.lower()))
    pos = len(tokens & _POSITIVE)
    neg = len(tokens & _NEGATIVE)
    # Negation flips the leading sentiment
    negations = len(_NEGATION_RE.findall(text))
    if negations % 2 == 1:
        pos, neg = neg, pos
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


_SUBJECT_STOP = {
    "the","and","for","with","from","that","this","what","best","are","was","have",
    "not","just","also","they","their","more","most","like","very","into","over",
    "fast","slow","good","bad","new","old","big","small","using","about","some",
}

def _subject_tokens(text: str) -> set[str]:
    """Extract subject tokens: nouns/proper nouns, ignoring sentiment words."""
    all_toks = set(_TOKEN_RE.findall(text.lower()))
    return all_toks - _POSITIVE - _NEGATIVE - _SUBJECT_STOP


def _cluster(items: list[dict], similarity: float = 0.07) -> list[list[dict]]:
    """Cluster by SUBJECT tokens only (strip sentiment words) so opposing claims
    about the same subject still land in the same cluster."""
    clusters: list[dict] = []
    for it in items:
        text = f"{it.get('title','')} {it.get('content','')[:300]}"
        fp = _subject_tokens(text)
        placed = False
        for cl in clusters:
            if fp and cl["centroid"] and jaccard(fp, cl["centroid"]) >= similarity:
                cl["members"].append({**it, "_fp": fp})
                cl["centroid"] = cl["centroid"] | fp
                placed = True
                break
        if not placed:
            clusters.append({"centroid": set(fp), "members": [{**it, "_fp": fp}]})
    return [cl["members"] for cl in clusters]


def detect(findings: list[dict], min_cluster_size: int = 2) -> list[dict]:
    """
    Detect contradictions in a list of findings.

    Each finding should have: title, content (or snippet), source, url.

    Returns list of contradiction dicts:
        {
            "subject":    str,      # representative title of the cluster
            "claim_a":    dict,     # {title, source, url, sentiment}
            "claim_b":    dict,     # opposing claim
            "confidence": float,   # 0-1, higher = clearer opposition
            "sources":    list[str],
        }
    """
    if not findings:
        return []

    clusters = _cluster(findings)
    contradictions = []

    for members in clusters:
        if len(members) < min_cluster_size:
            continue

        # Tag each member with sentiment
        tagged = []
        for m in members:
            text = f"{m.get('title','')} {m.get('content','')[:600]}"
            tagged.append({**m, "_sentiment": _sentiment(text)})

        positives = [m for m in tagged if m["_sentiment"] == "positive"]
        negatives = [m for m in tagged if m["_sentiment"] == "negative"]

        if not positives or not negatives:
            continue

        # Must come from different sources for a real contradiction
        pos_sources = {m.get("source", "") for m in positives}
        neg_sources = {m.get("source", "") for m in negatives}
        if pos_sources == neg_sources and len(pos_sources) == 1:
            continue

        best_pos = max(positives, key=lambda m: len(m.get("content", "")))
        best_neg = max(negatives, key=lambda m: len(m.get("content", "")))

        # Confidence: how many sources on each side, how clean the split
        total = len(tagged)
        split_ratio = min(len(positives), len(negatives)) / max(1, total)
        src_diversity = len(pos_sources | neg_sources) / max(1, len(pos_sources | neg_sources))
        confidence = round(min(1.0, split_ratio * 1.5 + src_diversity * 0.3), 3)

        subject = best_pos.get("title") or best_neg.get("title") or "Unknown subject"

        contradictions.append({
            "subject":    subject[:200],
            "claim_a": {
                "title":     best_pos.get("title", "")[:150],
                "source":    best_pos.get("source", ""),
                "url":       best_pos.get("url", ""),
                "sentiment": "positive",
            },
            "claim_b": {
                "title":     best_neg.get("title", "")[:150],
                "source":    best_neg.get("source", ""),
                "url":       best_neg.get("url", ""),
                "sentiment": "negative",
            },
            "confidence":     confidence,
            "sources":        sorted(pos_sources | neg_sources),
            "positive_count": len(positives),
            "negative_count": len(negatives),
        })

    contradictions.sort(key=lambda x: x["confidence"], reverse=True)
    return contradictions


def format_for_report(contradictions: list[dict]) -> str:
    """Format contradiction list as a markdown block for report injection."""
    if not contradictions:
        return ""
    lines = ["## ⚡ Contradictions Detected\n"]
    for i, c in enumerate(contradictions[:5], 1):
        conf = int(c["confidence"] * 100)
        lines.append(f"### {i}. {c['subject'][:120]}  *(confidence {conf}%)*")
        lines.append(f"- ✅ **{c['claim_a']['source']}**: {c['claim_a']['title']}")
        lines.append(f"  [{c['claim_a']['url']}]({c['claim_a']['url']})" if c['claim_a']['url'] else "")
        lines.append(f"- ❌ **{c['claim_b']['source']}**: {c['claim_b']['title']}")
        lines.append(f"  [{c['claim_b']['url']}]({c['claim_b']['url']})" if c['claim_b']['url'] else "")
        lines.append(f"- Sources disagree: {', '.join(c['sources'])}\n")
    return "\n".join(l for l in lines if l is not None)
