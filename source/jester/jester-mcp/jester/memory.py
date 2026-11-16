"""
Jester Memory Layer: past knowledge feeds into every new run.
Scans all saved reports for relevance to the current query,
injects matching excerpts as prior context before Claude synthesizes.
"""

import re
import json
from pathlib import Path
from datetime import datetime

from paths import reports_dir, memory_index_path
REPORTS_DIR   = reports_dir()
MEMORY_INDEX  = memory_index_path()


# ── Indexing ──────────────────────────────────────────────────────────────────

def _extract_keywords(text: str) -> set[str]:
    """Pull meaningful words: strip stopwords, lowercase, min 4 chars."""
    STOPWORDS = {
        "that", "this", "with", "from", "they", "have", "will", "your",
        "more", "been", "also", "were", "their", "what", "when", "which",
        "about", "into", "than", "other", "some", "only", "most", "over",
        "such", "each", "much", "very", "just", "like", "used", "using",
        "based", "data", "tool", "tools", "best", "make", "made", "year",
        "2026", "2025", "2024", "source", "report", "jester",
    }
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return {w for w in words if w not in STOPWORDS}


def _extract_highlights(text: str, max_chars: int = 800) -> str:
    """Pull TL;DR + first 3 Key Insights from a report."""
    highlights = []

    tldr = re.search(r"## TL;DR\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if tldr:
        highlights.append(tldr.group(1).strip()[:300])

    insights = re.findall(r"- \[(HIGH CONVICTION|MULTI SOURCE)\](.*?)(?=\n-|\n##|\Z)", text, re.DOTALL)
    for _, insight in insights[:3]:
        highlights.append(insight.strip()[:150])

    wtb = re.search(r"## What to Build\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if wtb:
        highlights.append(wtb.group(1).strip()[:200])

    return "\n".join(highlights)[:max_chars]


def build_index() -> dict:
    """Scan all reports and build a keyword → report mapping."""
    index = {}
    for path in REPORTS_DIR.glob("*.md"):
        try:
            text  = path.read_text(encoding="utf-8", errors="ignore")
            words = _extract_keywords(text[:5000])  # index first 5k chars
            highlights = _extract_highlights(text)
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
            date = date_match.group(1) if date_match else "unknown"
            index[path.name] = {
                "path":       str(path),
                "keywords":   list(words),
                "highlights": highlights,
                "date":       date,
            }
        except Exception:
            pass
    MEMORY_INDEX.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def load_index() -> dict:
    if MEMORY_INDEX.exists():
        try:
            return json.loads(MEMORY_INDEX.read_text(encoding="utf-8"))
        except Exception:
            pass
    return build_index()


# ── Recall ────────────────────────────────────────────────────────────────────

def recall(query: str, top_k: int = 3, min_overlap: int = 3) -> list[dict]:
    """
    Find the most relevant past reports for a query.
    Scores = keyword overlap * temporal recency weight (recent reports rank higher).
    Returns list of {filename, date, highlights, overlap_score, final_score}.
    """
    query_words = _extract_keywords(query)
    if not query_words:
        return []

    index   = load_index()
    today   = datetime.now()
    scored  = []

    for fname, entry in index.items():
        report_words = set(entry.get("keywords", []))
        overlap = len(query_words & report_words)
        if overlap < min_overlap:
            continue

        # Temporal decay: reports lose 5% relevance per 30 days (Ebbinghaus-inspired)
        date_str = entry.get("date", "")
        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d")
            days_old    = (today - report_date).days
            decay       = max(0.3, 1.0 - (days_old / 30) * 0.05)  # floor at 0.3
        except Exception:
            decay = 0.5

        final_score = overlap * decay
        scored.append({
            "filename":    fname,
            "date":        date_str,
            "highlights":  entry.get("highlights", ""),
            "overlap":     overlap,
            "final_score": round(final_score, 3),
        })

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored[:top_k]


def _compress_highlights(highlights: str, max_chars: int = 400) -> str:
    """Compress highlights to key facts only, which prevents context bloat."""
    if not highlights:
        return ""
    lines = [l.strip() for l in highlights.splitlines() if l.strip()]
    # Keep lines with numbers, names, percentages, or conviction tags (highest signal)
    high_signal = [l for l in lines if any(c in l for c in ["$", "%", "HIGH", "MULTI", "→", "://"])]
    rest        = [l for l in lines if l not in high_signal]
    ordered     = high_signal + rest
    compressed  = " | ".join(ordered)
    return compressed[:max_chars]


def build_memory_block(query: str) -> str:
    """
    Returns a compressed memory block to prepend to combined_content.
    Compresses highlights to key facts only (prevents context bloat).
    Empty string if no relevant past reports found.
    """
    matches = recall(query, top_k=3, min_overlap=3)
    if not matches:
        return ""

    lines = ["=== JESTER MEMORY (past research, compressed key facts only) ==="]
    for m in matches:
        score_label = f"relevance: {m['overlap']} | recency score: {m.get('final_score', m['overlap'])}"
        lines.append(f"\n--- {m['filename']} ({m['date']}) | {score_label} ---")
        lines.append(_compress_highlights(m["highlights"]))

    lines.append("\n=== END JESTER MEMORY ===\n")
    return "\n".join(lines)


# ── Index refresh (call after each report save) ───────────────────────────────

def refresh_index():
    """Rebuild the memory index. Call after saving a new report."""
    build_index()


# ── Compost: re-ingest past research, surface cross-report patterns ──────────

def compost_memory(days_back: int = 30, max_reports: int = 50, model: str = "haiku") -> dict:
    """
    Read recent reports, run a cross-report synthesis to surface recurring themes,
    contradictions, gaps, and follow-up questions. Saves a KNOWLEDGE_DIGEST report
    and refreshes the memory index. User-triggered, no cron.

    Returns {"digest_path": str, "report_count": int, "synthesis": str}.
    """
    import os
    cutoff = datetime.now().timestamp() - (days_back * 86400)
    reports = []
    for path in REPORTS_DIR.glob("*.md"):
        if path.name.startswith("KNOWLEDGE_DIGEST_"):
            continue  # don't re-ingest our own digests
        if path.stat().st_mtime < cutoff:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            reports.append({
                "filename": path.name,
                "date": re.match(r"(\d{4}-\d{2}-\d{2})", path.name).group(1) if re.match(r"(\d{4}-\d{2}-\d{2})", path.name) else "",
                "highlights": _extract_highlights(text, max_chars=600),
            })
        except Exception:
            continue

    reports.sort(key=lambda r: r["date"], reverse=True)
    reports = reports[:max_reports]

    if not reports:
        return {"digest_path": "", "report_count": 0, "synthesis": "No reports found in window."}

    blocks = []
    for r in reports:
        if r["highlights"]:
            blocks.append(f"=== {r['filename']} ({r['date']}) ===\n{r['highlights']}")
    combined = "\n\n".join(blocks)[:30000]

    import anthropic
    MODEL_MAP = {
        "haiku":  "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-6",
        "opus":   "claude-opus-4-7",
    }
    model_id = MODEL_MAP.get(model, MODEL_MAP["haiku"])
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""You are Jester's compost engine. You're being shown the highlights of {len(reports)} past research reports from the last {days_back} days.

Your job: extract cross-report intelligence that no single report could see.

Output EXACTLY this format:

## Recurring Themes
What topics keep appearing? Why? List 3-7 with frequency count and 1-line interpretation.

## Cross-Report Contradictions
Where do reports disagree? Which is more credible based on recency or source quality?

## Knowledge Gaps
What questions came up across multiple reports but were never resolved? List as researchable follow-up queries.

## Highest-Conviction Findings
Synthesize the most-confirmed claims across all reports. One bullet each, prefix with how many reports back it.

## What Jester Should Research Next
Top 5 follow-up topics ranked by leverage. Each as a one-line query you could feed back into research_topic.

REPORT HIGHLIGHTS:
{combined}
"""

    msg = client.messages.create(
        model=model_id,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    synthesis = msg.content[0].text

    today = datetime.now().strftime("%Y-%m-%d")
    digest_path = REPORTS_DIR / f"KNOWLEDGE_DIGEST_{today}.md"
    digest_path.write_text(
        f"# Jester Knowledge Digest: {today}\n"
        f"*Composted from {len(reports)} reports (last {days_back} days)*\n\n"
        f"{synthesis}\n",
        encoding="utf-8",
    )
    refresh_index()
    return {
        "digest_path": str(digest_path),
        "report_count": len(reports),
        "synthesis": synthesis,
    }
