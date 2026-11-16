"""
Jester Entity Graph: track which people, companies, products, and tickers
appear across searches and how they co-occur.

Backed by SQLite. No NLP library, pure regex extraction.

Extracts:
  - CAPITALIZED multi-word names  (e.g. "Sam Altman", "Stripe", "Y Combinator")
  - $TICKER symbols               (e.g. "$SOL", "$BTC")
  - @handles                      (e.g. "@sama", "@levelsio")
  - domain names from URLs        (e.g. "stripe.com")

Co-occurrence: two entities in the same finding = linked edge (weight += 1).
"""

import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

from paths import jester_home

_DB = None


def _db_path() -> Path:
    return jester_home() / "entity_graph.db"


def _conn() -> sqlite3.Connection:
    p = _db_path()
    c = sqlite3.connect(str(p))
    c.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            type       TEXT,
            topic      TEXT,
            source     TEXT,
            seen_at    REAL
        );
        CREATE INDEX IF NOT EXISTS idx_ent_name  ON entities(name);
        CREATE INDEX IF NOT EXISTS idx_ent_topic ON entities(topic);

        CREATE TABLE IF NOT EXISTS edges (
            entity_a   TEXT NOT NULL,
            entity_b   TEXT NOT NULL,
            topic      TEXT,
            weight     INTEGER DEFAULT 1,
            PRIMARY KEY (entity_a, entity_b, topic)
        );
        CREATE INDEX IF NOT EXISTS idx_edge_a ON edges(entity_a);
        CREATE INDEX IF NOT EXISTS idx_edge_b ON edges(entity_b);
    """)
    c.commit()
    return c


# ── Extractors ────────────────────────────────────────────────────────────────

_TICKER_RE  = re.compile(r"\$([A-Z]{2,6})\b")
_HANDLE_RE  = re.compile(r"@([A-Za-z0-9_]{3,30})\b")
_DOMAIN_RE  = re.compile(r"https?://(?:www\.)?([a-z0-9\-]+\.[a-z]{2,6})")
_PROPER_RE  = re.compile(r"\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){0,3})\b")

_NOISE = {
    "The", "This", "That", "These", "Those", "When", "Where", "What",
    "How", "Why", "Here", "There", "Also", "Just", "Like", "Some",
    "Many", "More", "Most", "Such", "Even", "Then", "Than", "From",
    "With", "Into", "Over", "Under", "After", "Before", "During",
    "Reddit", "Twitter", "YouTube", "Google", "GitHub", "LinkedIn",
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
}


def extract_entities(text: str) -> list[dict]:
    """Extract named entities from text. Returns list of {name, type}."""
    entities = []
    seen = set()

    for m in _TICKER_RE.finditer(text):
        name = f"${m.group(1)}"
        if name not in seen:
            seen.add(name)
            entities.append({"name": name, "type": "ticker"})

    for m in _HANDLE_RE.finditer(text):
        name = f"@{m.group(1)}"
        if name not in seen:
            seen.add(name)
            entities.append({"name": name, "type": "handle"})

    for m in _DOMAIN_RE.finditer(text):
        name = m.group(1)
        if name not in seen and len(name) > 4:
            seen.add(name)
            entities.append({"name": name, "type": "domain"})

    for m in _PROPER_RE.finditer(text):
        name = m.group(1).strip()
        if name not in seen and name not in _NOISE and len(name) > 3:
            seen.add(name)
            entities.append({"name": name, "type": "proper"})

    return entities


# ── Ingest ────────────────────────────────────────────────────────────────────

def ingest(findings: list[dict], topic: str = "") -> dict:
    """
    Extract entities from a batch of findings, store them, and build co-occurrence edges.
    Returns {"entities": int, "edges": int}.
    """
    now = time.time()
    conn = _conn()
    total_ents = 0
    total_edges = 0

    try:
        for item in findings:
            text = f"{item.get('title','')} {item.get('content','')[:1500]}"
            source = item.get("source", "")
            ents = extract_entities(text)
            names = [e["name"] for e in ents]

            for e in ents:
                conn.execute(
                    "INSERT INTO entities(name, type, topic, source, seen_at) VALUES(?,?,?,?,?)",
                    (e["name"], e["type"], topic, source, now),
                )
                total_ents += 1

            # Co-occurrence edges
            for i, a in enumerate(names):
                for b in names[i+1:i+6]:  # window of 5
                    if a == b:
                        continue
                    a_s, b_s = sorted([a, b])
                    conn.execute(
                        "INSERT INTO edges(entity_a, entity_b, topic, weight) VALUES(?,?,?,1) "
                        "ON CONFLICT(entity_a, entity_b, topic) DO UPDATE SET weight = weight + 1",
                        (a_s, b_s, topic),
                    )
                    total_edges += 1

        conn.commit()
    finally:
        conn.close()

    return {"entities": total_ents, "edges": total_edges}


# ── Query ─────────────────────────────────────────────────────────────────────

def top_entities(topic: str = "", limit: int = 20, entity_type: str = "") -> list[dict]:
    """Return most-mentioned entities for a topic, sorted by frequency."""
    conn = _conn()
    try:
        if topic and entity_type:
            rows = conn.execute(
                "SELECT name, type, COUNT(*) as freq FROM entities WHERE topic=? AND type=? "
                "GROUP BY name ORDER BY freq DESC LIMIT ?",
                (topic, entity_type, limit),
            ).fetchall()
        elif topic:
            rows = conn.execute(
                "SELECT name, type, COUNT(*) as freq FROM entities WHERE topic=? "
                "GROUP BY name ORDER BY freq DESC LIMIT ?",
                (topic, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, type, COUNT(*) as freq FROM entities "
                "GROUP BY name ORDER BY freq DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()
    return [{"name": r[0], "type": r[1], "freq": r[2]} for r in rows]


def top_edges(topic: str = "", limit: int = 15) -> list[dict]:
    """Return strongest co-occurrence pairs."""
    conn = _conn()
    try:
        if topic:
            rows = conn.execute(
                "SELECT entity_a, entity_b, weight FROM edges WHERE topic=? "
                "ORDER BY weight DESC LIMIT ?",
                (topic, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT entity_a, entity_b, SUM(weight) as w FROM edges "
                "GROUP BY entity_a, entity_b ORDER BY w DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()
    return [{"a": r[0], "b": r[1], "weight": r[2]} for r in rows]


def entity_stats() -> dict:
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        unique = conn.execute("SELECT COUNT(DISTINCT name) FROM entities").fetchone()[0]
        edges  = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        by_type = dict(conn.execute(
            "SELECT type, COUNT(DISTINCT name) FROM entities GROUP BY type"
        ).fetchall())
    finally:
        conn.close()
    return {"total_mentions": total, "unique_entities": unique,
            "edges": edges, "by_type": by_type}


def format_for_report(topic: str, limit: int = 10) -> str:
    """Markdown block of top entities + key relationships for report injection."""
    ents = top_entities(topic, limit=limit)
    edges = top_edges(topic, limit=8)
    if not ents:
        return ""
    lines = ["## 🗺 Entity Map\n"]
    lines.append("**Top mentions:**")
    for e in ents[:limit]:
        lines.append(f"- `{e['name']}` ({e['type']}): {e['freq']}×")
    if edges:
        lines.append("\n**Key relationships:**")
        for ed in edges[:8]:
            lines.append(f"- {ed['a']}  ↔  {ed['b']}  ({ed['weight']} co-occurrences)")
    return "\n".join(lines)
