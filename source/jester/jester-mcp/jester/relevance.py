"""Post-fetch relevance filter.

Score how well a finding matches the topic. Pure local heuristics, no LLM.
Combines:
  - keyword density (how many topic tokens appear in title + content)
  - title-match bonus (topic tokens in title weighted higher)
  - length penalty (very short snippets without topic tokens get dropped)

Default threshold drops political/worldbuilding noise that high-engagement
Reddit posts produce when keyword search picks them up loosely.
"""
import re

_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "for", "to",
    "is", "are", "was", "were", "be", "been", "being", "i", "you", "we", "they",
    "it", "this", "that", "with", "as", "by", "from", "what", "how", "why",
    "make", "made", "making", "build", "built",
}


def _toks(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(t) >= 3 and t not in _STOP]


def score(topic: str, finding: dict) -> float:
    """Return 0-1 relevance score. 0 = irrelevant noise, 1 = strong match."""
    topic_toks = set(_toks(topic))
    if not topic_toks:
        return 0.5
    title = finding.get("title", "") or ""
    content = (finding.get("content", "") or finding.get("snippet", "") or "")[:2000]
    title_toks = set(_toks(title))
    content_toks = _toks(content)
    if not content_toks and not title_toks:
        return 0.0
    title_overlap = len(title_toks & topic_toks) / max(1, len(topic_toks))
    body_hits = sum(1 for t in content_toks if t in topic_toks)
    body_density = body_hits / max(20, len(content_toks))
    raw = title_overlap * 0.6 + min(1.0, body_density * 8) * 0.4
    if title_overlap == 0 and body_hits < 2:
        return 0.0
    return min(1.0, raw)


def filter_findings(topic: str, findings: list[dict], threshold: float = 0.18) -> tuple[list[dict], list[dict]]:
    """Split findings into (kept, dropped). Kept have score >= threshold."""
    kept, dropped = [], []
    for f in findings:
        s = score(topic, f)
        f = {**f, "_relevance": round(s, 3)}
        (kept if s >= threshold else dropped).append(f)
    return kept, dropped
