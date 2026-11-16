"""Jester digester: pulls entities + facts out of raw aggregated content
and feeds them to the knowledge graph. Pure regex, no LLM call, no network.

Runs post-response in a fire-and-forget thread so it never blocks the user.
"""

import re
import threading
from typing import Iterable

import graph


# ── Pattern bank ─────────────────────────────────────────────────────────────
# Tools / products: capitalized + ".io|.com|.dev|.so|.ai" or "TitleCase Tool"
RE_TOOL_DOMAIN = re.compile(r"\b([A-Z][a-zA-Z0-9_-]{1,30})\.(?:io|com|dev|so|ai|app|co|build|run)\b")
RE_TOOL_NAMED  = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+){1,3})\b")  # CamelCase like "ClaudeCode", "VibeCoding"

# Prices: $X / mo, $X/month, $X per month, $X.XX
RE_PRICE = re.compile(
    r"(?P<sym>\$|€|£)\s?(?P<amount>\d{1,4}(?:[.,]\d{1,2})?)\s?(?:/|per\s)?(?P<period>mo|month|yr|year|day|week|hr|hour)?",
    re.IGNORECASE,
)

# Stats / percentages: "92% of X", "46% adoption", "$9.4B market"
RE_PERCENT = re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s?%(?:\s+(?:of|adoption|growth|increase))?", re.IGNORECASE)
RE_BIGNUM  = re.compile(r"\b\$?(\d+(?:\.\d+)?)\s?(?:B|M|K)\b(?:\s+(?:market|revenue|users|MRR|ARR))?", re.IGNORECASE)

# People (heuristic): "FirstName LastName" near "said|wrote|coined|founded|CEO"
RE_PERSON_VERB = re.compile(
    r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b(?=\s+(?:said|wrote|coined|founded|created|posted|tweeted|is|was|leads|runs))"
)

# Releases / dates: "released in 2026", "launched March 2026", version "v3.4"
RE_VERSION = re.compile(r"\b(?:v|version\s)(\d+\.\d+(?:\.\d+)?)\b", re.IGNORECASE)
RE_DATE_YEAR = re.compile(r"\b(?:since|in|launched|released|founded)\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?(20\d{2})\b", re.IGNORECASE)

# Skip words: never treat these as entities
_STOP = {
    "The", "This", "That", "These", "Those", "There", "Here", "Where",
    "What", "When", "Why", "How", "Who", "Which",
    "Best", "Most", "More", "Many", "Some", "All", "Any",
    "Reddit", "Twitter", "GitHub", "YouTube", "HackerNews",   # source labels, already known
    "Views", "Score", "Comments", "Points", "Source", "URL", "Title",
    "Markdown", "Content", "Time", "Image",
    "Vibe", "Coding", "AI",   # too generic on their own (we want compounds)
}


def _looks_like_entity(s: str) -> bool:
    if s in _STOP:
        return False
    if len(s) < 3 or len(s) > 40:
        return False
    return True


def _classify_entity(name: str, context: str) -> str:
    """Best-effort entity-type guess from surrounding text."""
    ctx = context.lower()
    nm = name.lower()
    if "." in name and any(name.endswith(s) for s in (".io", ".com", ".dev", ".so", ".ai", ".app", ".co", ".build", ".run")):
        return "tool"
    if any(w in ctx for w in ("ceo", "founder", "wrote", "coined", "tweeted", "posted")):
        return "person"
    if any(w in ctx for w in ("inc", "corp", "company", "startup", "raised", "valuation")):
        return "company"
    if any(w in ctx for w in ("tool", "ide", "platform", "app", "framework", "library", "agent")):
        return "tool"
    return "other"


def _extract_around(text: str, match_start: int, match_end: int, window: int = 80) -> str:
    s = max(0, match_start - window)
    e = min(len(text), match_end + window)
    return text[s:e]


# ── Main digestion ───────────────────────────────────────────────────────────
def digest_block(text: str, source_url: str = "", source_kind: str = "", topic_norm: str = "") -> dict:
    """Extract entities + facts from one chunk of raw content. Synchronous.
    topic_norm: normalized query. Links entities/facts to the topic for cross-topic intersection."""
    counts = {"entities": 0, "facts": 0}

    # Tools (domain form)
    for m in RE_TOOL_DOMAIN.finditer(text):
        full = m.group(0)
        if not _looks_like_entity(full):
            continue
        eid = graph.resolve_or_create(full, ent_type="tool")
        if eid:
            counts["entities"] += 1
            if topic_norm:
                graph.link_entity_to_topic(eid, topic_norm)

    # Tools (CamelCase form), limited to avoid noise
    seen_camel = set()
    for m in RE_TOOL_NAMED.finditer(text):
        name = m.group(1)
        if name in seen_camel or not _looks_like_entity(name):
            continue
        seen_camel.add(name)
        if len(seen_camel) > 30:    # cap per block
            break
        ctx = _extract_around(text, m.start(), m.end())
        etype = _classify_entity(name, ctx)
        eid = graph.resolve_or_create(name, ent_type=etype)
        if eid:
            counts["entities"] += 1
            if topic_norm:
                graph.link_entity_to_topic(eid, topic_norm)

    # Prices
    for m in RE_PRICE.finditer(text):
        ctx = _extract_around(text, m.start(), m.end(), window=60)
        name_match = re.search(r"\b([A-Z][a-zA-Z0-9_-]{2,30})\b", ctx)
        if not name_match:
            continue
        name = name_match.group(1)
        if not _looks_like_entity(name):
            continue
        eid = graph.resolve_or_create(name, ent_type="tool")
        if eid:
            fact = m.group(0).strip()
            graph.add_fact(eid, "price", fact, source_url, source_kind, confidence=0.7, topic_norm=topic_norm)
            counts["facts"] += 1

    # Stats / percentages
    for m in RE_PERCENT.finditer(text):
        ctx = _extract_around(text, m.start(), m.end(), window=80).strip()
        graph.add_fact(
            graph.resolve_or_create("_global_stat_" + m.group(1) + "pct", ent_type="stat"),
            "stat", ctx[:200],
            source_url, source_kind, confidence=0.5, topic_norm=topic_norm,
        )
        counts["facts"] += 1

    # Big numbers (market sizes, MRR, etc)
    for m in RE_BIGNUM.finditer(text):
        ctx = _extract_around(text, m.start(), m.end(), window=80).strip()
        graph.add_fact(
            graph.resolve_or_create("_global_bignum_" + m.group(1), ent_type="stat"),
            "stat", ctx[:200],
            source_url, source_kind, confidence=0.5, topic_norm=topic_norm,
        )
        counts["facts"] += 1

    # People
    for m in RE_PERSON_VERB.finditer(text):
        name = m.group(1)
        if not _looks_like_entity(name):
            continue
        eid = graph.resolve_or_create(name, ent_type="person")
        if eid:
            counts["entities"] += 1
            if topic_norm:
                graph.link_entity_to_topic(eid, topic_norm)

    return counts


def digest_aggregation(query: str, used: dict) -> dict:
    """Digest the entire aggregated result of a research_topic call.
    `used` is the dict {source_name: [{title, url, content}, ...]} from _gather_and_extract.
    Synchronous: call this in a thread for fire-and-forget.
    """
    total = {"entities": 0, "facts": 0, "blocks": 0}
    sources_n = 0
    topic_norm = graph._normalize(query)[:200]
    for src_name, payload in used.items():
        if not isinstance(payload, list):
            continue
        sources_n += 1
        for p in payload:
            content = p.get("content", "") if isinstance(p, dict) else ""
            url = p.get("url", "") if isinstance(p, dict) else ""
            if not content:
                continue
            counts = digest_block(content, source_url=url, source_kind=src_name, topic_norm=topic_norm)
            total["entities"] += counts["entities"]
            total["facts"] += counts["facts"]
            total["blocks"] += 1

    graph.record_topic(query, sources_n=sources_n, entities_n=total["entities"])
    graph._bump_insert_counter(total["entities"] + total["facts"])
    compact_result = graph.maybe_compact()
    total["compaction"] = compact_result
    return total


def digest_async(query: str, used: dict) -> threading.Thread:
    """Fire-and-forget digestion. Returns the thread (caller can ignore)."""
    def _runner():
        try:
            digest_aggregation(query, used)
        except Exception:
            pass    # Never let digestion crash the host
    t = threading.Thread(target=_runner, daemon=True, name="jester-digest")
    t.start()
    return t
