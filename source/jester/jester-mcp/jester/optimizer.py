"""
Jester Self-Optimizer
After every run: scores sources, discovers new domains, evolves query patterns.
Every future run reads these learnings and searches smarter.

What it learns:
  1. Source quality scores:   which sources produce HIGH CONVICTION findings
  2. New domains:             extract URLs from best findings, add to search rotation
  3. Query boost terms:       words/phrases that consistently improve result quality
  4. Dead sources:            sources that never contribute, skip them automatically
"""

import re
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from paths import optimizer_state_path, learned_domains_path
OPTIMIZER_FILE  = optimizer_state_path()
LEARNED_DOMAINS = learned_domains_path()

# Minimum runs before a source is penalized or promoted
MIN_RUNS_TO_JUDGE = 5

# Score thresholds
PROMOTE_THRESHOLD = 0.6   # >60% HIGH/MULTI = promoted source
DEMOTE_THRESHOLD  = 0.15  # <15% HIGH/MULTI = deprioritized


# ── State management ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    if OPTIMIZER_FILE.exists():
        try:
            return json.loads(OPTIMIZER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "source_scores": {},   # {source: {runs, high, multi, single, score}}
        "query_boosts":  {},   # {topic_keyword: [boost_terms]}
        "promoted":      [],   # sources scoring above threshold
        "deprioritized": [],   # sources scoring below threshold
        "total_optimizations": 0,
        "last_run": None,
    }


def _save_state(state: dict):
    OPTIMIZER_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_learned_domains() -> dict:
    if LEARNED_DOMAINS.exists():
        try:
            return json.loads(LEARNED_DOMAINS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"domains": [], "domain_scores": {}}


def _save_learned_domains(data: dict):
    LEARNED_DOMAINS.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Source quality scoring ────────────────────────────────────────────────────

def score_sources(extraction: str, active_sources: list[str]) -> dict:
    """
    Score each source by how many HIGH/MULTI conviction findings cite it.
    Returns {source: {high, multi, single, total_citations, quality_ratio}}
    """
    scores = {src: {"high": 0, "multi": 0, "single": 0, "total": 0} for src in active_sources}

    # Find all [HIGH CONVICTION] and [MULTI SOURCE] findings and their citations
    high_pattern  = re.findall(r"\[HIGH CONVICTION\][^\n]*\[via ([^\]]+)\]", extraction, re.IGNORECASE)
    multi_pattern = re.findall(r"\[MULTI SOURCE\][^\n]*\[via ([^\]]+)\]",     extraction, re.IGNORECASE)
    single_pattern = re.findall(r"\[SINGLE SOURCE\][^\n]*\[via ([^\]]+)\]",   extraction, re.IGNORECASE)

    def _attribute(citation_str: str, level: str):
        """Map a citation like 'reddit.com, hn' to source names."""
        citation_lower = citation_str.lower()
        for src in active_sources:
            src_signals = {
                "reddit": ["reddit"],
                "hn":     ["hn", "hackernews", "hacker news", "news.ycombinator"],
                "web":    ["web", "blog", "site"],
                "news":   ["news", "techcrunch", "wired", "bloomberg"],
                "papers": ["arxiv", "paper", "research", "study"],
                "github": ["github"],
                "medium": ["medium"],
                "youtube": ["youtube", "youtu"],
                "linkedin": ["linkedin"],
                "quora":  ["quora"],
            }
            signals = src_signals.get(src, [src])
            if any(sig in citation_lower for sig in signals):
                scores[src][level] = scores[src].get(level, 0) + 1
                scores[src]["total"] = scores[src].get("total", 0) + 1

    for c in high_pattern:  _attribute(c, "high")
    for c in multi_pattern: _attribute(c, "multi")
    for c in single_pattern: _attribute(c, "single")

    # Calculate quality ratio
    result = {}
    for src, data in scores.items():
        total = data["total"] or 1
        ratio = (data["high"] * 2 + data["multi"]) / (total * 2)
        result[src] = {**data, "quality_ratio": round(ratio, 3)}

    return result


# ── Domain discovery ──────────────────────────────────────────────────────────

def discover_domains(extraction: str) -> list[str]:
    """
    Extract domains from HIGH CONVICTION source citations.
    These are the sites that produced the best intelligence.
    """
    # Pull URLs cited next to HIGH CONVICTION findings
    pattern = re.findall(
        r"\[(?:HIGH CONVICTION|MULTI SOURCE)\].*?https?://([a-zA-Z0-9._-]+)",
        extraction, re.IGNORECASE | re.DOTALL
    )

    # Also pull [via domain.com] style citations near high-conviction findings
    via_pattern = re.findall(
        r"\[HIGH CONVICTION\][^\n]*\[via ([a-zA-Z0-9._/-]+)\]",
        extraction, re.IGNORECASE
    )

    domains = set()
    for raw in pattern + via_pattern:
        # Extract just the domain
        raw = raw.split("/")[0].strip()
        if "." in raw and len(raw) > 4 and len(raw) < 60:
            # Skip generic/noise domains
            skip = {"google", "twitter", "facebook", "instagram", "tiktok",
                    "youtube", "reddit", "amazon", "wikipedia", "linkedin"}
            if not any(s in raw.lower() for s in skip):
                domains.add(raw.lower().lstrip("www."))

    return list(domains)


# ── Query boost learning ──────────────────────────────────────────────────────

def learn_query_boosts(query: str, extraction: str, quality_score: float):
    """
    If this run scored high, extract terms that likely boosted quality
    and associate them with this topic type for future queries.
    """
    if quality_score < 70:
        return  # Only learn from good runs

    state = _load_state()

    # Extract topic keywords from query (4+ char words, no stopwords)
    stopwords = {"that","this","with","from","what","when","which","about","into",
                 "best","make","made","year","data","tool","also","just","like"}
    words = re.findall(r"\b[a-z]{4,}\b", query.lower())
    topic_words = [w for w in words if w not in stopwords]

    if not topic_words:
        return

    # Find high-conviction terms in the extraction to use as future boosts
    high_lines = re.findall(r"\[HIGH CONVICTION\][^\n]{20,100}", extraction)
    boost_candidates = []
    for line in high_lines:
        terms = re.findall(r"\b[a-z]{5,}\b", line.lower())
        boost_candidates.extend([t for t in terms if t not in stopwords])

    if not boost_candidates:
        return

    # Associate top boost terms with this topic's keywords
    from collections import Counter
    top_boosts = [term for term, _ in Counter(boost_candidates).most_common(3)]

    for kw in topic_words[:3]:
        existing = state["query_boosts"].get(kw, [])
        for boost in top_boosts:
            if boost not in existing and boost != kw:
                existing.append(boost)
        state["query_boosts"][kw] = existing[:8]  # cap at 8 per keyword

    _save_state(state)


# ── Main optimizer call: run after every research run ────────────────────────

def optimize(
    query: str,
    extraction: str,
    active_sources: list[str],
    quality_score: float,
) -> dict:
    """
    Called after every Jester run. Updates all learned state.
    Returns a summary of what was learned.
    """
    state   = _load_state()
    learned = {"new_domains": [], "promoted": [], "deprioritized": [], "boosts_learned": 0}

    # 1. Score sources
    run_scores = score_sources(extraction, active_sources)
    src_state  = state.get("source_scores", {})

    for src, data in run_scores.items():
        if src not in src_state:
            src_state[src] = {"runs": 0, "high": 0, "multi": 0, "single": 0, "total": 0}
        src_state[src]["runs"]   += 1
        src_state[src]["high"]   += data["high"]
        src_state[src]["multi"]  += data["multi"]
        src_state[src]["single"] += data["single"]
        src_state[src]["total"]  += data["total"]

    # Recalculate cumulative quality ratios
    for src, data in src_state.items():
        total = data["total"] or 1
        ratio = (data["high"] * 2 + data["multi"]) / (total * 2)
        data["quality_ratio"] = round(ratio, 3)

        # Promote / deprioritize based on enough data
        if data["runs"] >= MIN_RUNS_TO_JUDGE:
            if ratio >= PROMOTE_THRESHOLD and src not in state["promoted"]:
                state["promoted"].append(src)
                learned["promoted"].append(src)
            elif ratio <= DEMOTE_THRESHOLD and src not in state["deprioritized"]:
                state["deprioritized"].append(src)
                learned["deprioritized"].append(src)

    state["source_scores"] = src_state

    # 2. Discover new domains from high-conviction sources
    new_domains = discover_domains(extraction)
    if new_domains:
        ld = _load_learned_domains()
        existing = set(ld["domains"])
        fresh = [d for d in new_domains if d not in existing]
        if fresh:
            ld["domains"].extend(fresh)
            for d in fresh:
                ld["domain_scores"][d] = {"quality_score": quality_score, "added": datetime.now().isoformat()[:10]}
            _save_learned_domains(ld)
            learned["new_domains"] = fresh

    # 3. Learn query boosts from high-quality runs
    learn_query_boosts(query, extraction, quality_score)
    boosts_before = sum(len(v) for v in state["query_boosts"].values())

    state["total_optimizations"] = state.get("total_optimizations", 0) + 1
    state["last_run"] = datetime.now().isoformat()[:19]
    _save_state(state)

    boosts_after = sum(len(v) for v in state["query_boosts"].values())
    learned["boosts_learned"] = boosts_after - boosts_before

    return learned


# ── Query enhancer: call BEFORE searching ────────────────────────────────────

def enhance_query(query: str) -> str:
    """
    Boost a query with terms learned from past high-quality runs.
    Returns enhanced query string.
    """
    state = _load_state()
    boosts = state.get("query_boosts", {})

    stopwords = {"that","this","with","from","what","when","which","about","into",
                 "best","make","made","year","data","tool","also","just","like"}
    words = re.findall(r"\b[a-z]{4,}\b", query.lower())
    topic_words = [w for w in words if w not in stopwords]

    added = set()
    for kw in topic_words:
        for boost in boosts.get(kw, [])[:2]:  # max 2 boosts per keyword
            if boost not in query.lower() and boost not in added:
                added.add(boost)

    if added:
        return f"{query} {' '.join(list(added)[:3])}"
    return query


def get_best_sources(requested: list[str]) -> list[str]:
    """
    Reorder sources: promoted first, deprioritized last.
    Never removes sources the user asked for, just reorders.
    """
    state       = _load_state()
    promoted    = set(state.get("promoted", []))
    deprioritized = set(state.get("deprioritized", []))

    first  = [s for s in requested if s in promoted]
    middle = [s for s in requested if s not in promoted and s not in deprioritized]
    last   = [s for s in requested if s in deprioritized]

    return first + middle + last


def get_learned_domains(limit: int = 10) -> list[str]:
    """Return top learned domains sorted by quality score."""
    ld = _load_learned_domains()
    scored = sorted(
        ld["domain_scores"].items(),
        key=lambda x: x[1].get("quality_score", 0),
        reverse=True
    )
    return [d for d, _ in scored[:limit]]


# ── Status report ─────────────────────────────────────────────────────────────

def get_optimizer_status() -> str:
    state = _load_state()
    ld    = _load_learned_domains()

    src_scores = state.get("source_scores", {})
    ranked = sorted(src_scores.items(), key=lambda x: x[1].get("quality_ratio", 0), reverse=True)

    lines = [
        "JESTER SELF-OPTIMIZER STATUS",
        f"Total optimizations : {state.get('total_optimizations', 0)}",
        f"Last run            : {state.get('last_run', 'never')}",
        f"Learned domains     : {len(ld['domains'])}",
        f"Promoted sources    : {', '.join(state.get('promoted', [])) or 'none yet'}",
        f"Deprioritized       : {', '.join(state.get('deprioritized', [])) or 'none yet'}",
        "",
        "Source quality rankings (quality ratio = HIGH+MULTI / total findings):",
    ]
    for src, data in ranked[:10]:
        bar = "=" * int(data.get("quality_ratio", 0) * 20)
        lines.append(f"  {src:<18} {data.get('quality_ratio',0):.2f}  [{bar:<20}]  ({data.get('runs',0)} runs)")

    if ld["domains"]:
        lines += ["", f"Top learned domains (from HIGH CONVICTION sources):"]
        for d in get_learned_domains(8):
            lines.append(f"  {d}")

    return "\n".join(lines)
