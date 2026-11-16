"""Jester knowledge graph: the substrate that makes Jester grow.

Every research run feeds this graph. Entities are extracted, deduplicated, linked
to source citations, and given freshness clocks based on volatility. Old or
contradicted claims tier down (hot → warm → cold), never deleted, just
demoted. Compaction is event-driven (no scheduler).

Schema:
  entities:    one row per canonical thing (tool, person, company, claim, etc.)
  aliases:     name variants → entity_id (handles "Cursor" / "cursor.so" / "Cursor IDE")
  facts:       atomic claims about entities ("Cursor costs $20/mo")
  citations:   which source URLs back each fact (preserves provenance)
  topics:      query → entities seen, for topic mastery scoring

All on local SQLite. Zero network. Zero paid API. Zero cron.
"""

import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterable

from paths import jester_home


# ── Freshness model ──────────────────────────────────────────────────────────
# How long each fact-type stays "hot" before re-fetching is recommended.
# Volatile data (prices, news) decays fast; biographical facts decay slow.
FRESHNESS_DAYS = {
    "price":      7,        # Tool pricing changes constantly
    "news":       1,        # News goes stale fast
    "stat":       30,       # Adoption stats, percentages
    "release":    14,       # Software release info
    "person":     365,      # Biographical claims
    "company":    180,      # Company structure
    "tool":       60,       # Tool exists / capabilities
    "claim":      90,       # Generic claim (default)
    "url":        30,       # URL still alive / content unchanged
}

TIER_HOT, TIER_WARM, TIER_COLD = "hot", "warm", "cold"
COMPACT_AFTER_N_INSERTS = 200   # event-driven trigger


# ── Schema ───────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical   TEXT NOT NULL UNIQUE,    -- normalized canonical name
    type        TEXT NOT NULL,           -- tool|person|company|price|stat|other
    first_seen  REAL NOT NULL,
    last_seen   REAL NOT NULL,
    mention_n   INTEGER DEFAULT 1,
    tier        TEXT DEFAULT 'hot'
);
CREATE INDEX IF NOT EXISTS idx_ent_canonical ON entities(canonical);
CREATE INDEX IF NOT EXISTS idx_ent_type      ON entities(type);

CREATE TABLE IF NOT EXISTS aliases (
    alias       TEXT PRIMARY KEY,
    entity_id   INTEGER NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   INTEGER NOT NULL,
    fact_type   TEXT NOT NULL,           -- price|stat|release|claim|...
    fact_text   TEXT NOT NULL,           -- normalized claim
    fact_hash   TEXT NOT NULL,           -- for dedup
    confidence  REAL DEFAULT 0.5,
    captured_at REAL NOT NULL,
    expires_at  REAL NOT NULL,           -- when this fact becomes stale
    tier        TEXT DEFAULT 'hot',
    topic_norm  TEXT,                    -- normalized query that fetched this fact (for cross-topic queries)
    UNIQUE(entity_id, fact_hash),
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);
CREATE INDEX IF NOT EXISTS idx_fact_entity   ON facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_fact_expires  ON facts(expires_at);
CREATE INDEX IF NOT EXISTS idx_fact_tier     ON facts(tier);
-- idx_fact_topic created by _migrate() to handle legacy DBs missing the column

-- Entity ↔ topic linkage table (so we can answer "what bridges topics A and B?" precisely)
CREATE TABLE IF NOT EXISTS entity_topics (
    entity_id   INTEGER NOT NULL,
    topic_norm  TEXT NOT NULL,
    mentions    INTEGER DEFAULT 1,
    last_seen   REAL NOT NULL,
    PRIMARY KEY (entity_id, topic_norm),
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);
CREATE INDEX IF NOT EXISTS idx_et_topic ON entity_topics(topic_norm);

CREATE TABLE IF NOT EXISTS citations (
    fact_id     INTEGER NOT NULL,
    source_url  TEXT NOT NULL,
    source_kind TEXT,                    -- web|reddit|hn|arxiv|...
    captured_at REAL NOT NULL,
    PRIMARY KEY (fact_id, source_url),
    FOREIGN KEY (fact_id) REFERENCES facts(id)
);

CREATE TABLE IF NOT EXISTS topics (
    query_norm  TEXT PRIMARY KEY,
    first_seen  REAL NOT NULL,
    last_seen   REAL NOT NULL,
    query_n     INTEGER DEFAULT 1,
    sources_n   INTEGER DEFAULT 0,
    entities_n  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key         TEXT PRIMARY KEY,
    value       TEXT
);
"""


def db_path():
    return jester_home() / "graph.db"


def _migrate(c: sqlite3.Connection) -> None:
    """Add columns/tables to existing DBs that predate the current schema.
    Runs BEFORE the SCHEMA executescript so any indexes referencing new columns
    won't crash on legacy DBs."""
    # Check if facts table exists (skip migration on first-ever run; SCHEMA will create it)
    has_facts = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='facts'"
    ).fetchone()
    if has_facts:
        cols = {row[1] for row in c.execute("PRAGMA table_info(facts)")}
        if "topic_norm" not in cols:
            c.execute("ALTER TABLE facts ADD COLUMN topic_norm TEXT")
    # Always (idempotent) ensure the index exists post-migration
    # Done after SCHEMA completes


@contextmanager
def _conn():
    c = sqlite3.connect(db_path())
    _migrate(c)                  # FIRST: patch legacy schema
    c.executescript(SCHEMA)      # THEN: ensure base tables/indexes exist
    # Index that references topic_norm must run after migration guaranteed it exists
    c.execute("CREATE INDEX IF NOT EXISTS idx_fact_topic ON facts(topic_norm)")
    try:
        yield c
        c.commit()
    finally:
        c.close()


# ── Entity resolution ────────────────────────────────────────────────────────
_NORMALIZE_STRIP = re.compile(r"[^a-z0-9]+")
_YEAR_STRIP = re.compile(r"\b20\d{2}\b")

def _normalize(name: str) -> str:
    """Lowercase + strip year tokens + strip punctuation → canonical key."""
    cleaned = _YEAR_STRIP.sub("", name.lower())
    return _NORMALIZE_STRIP.sub("", cleaned).strip()


def resolve_or_create(name: str, ent_type: str = "other") -> int:
    """Find an entity by name (or alias), or create it. Returns entity_id."""
    if not name or not name.strip():
        return 0
    canonical = _normalize(name)
    if not canonical:
        return 0
    now = time.time()
    with _conn() as c:
        cur = c.execute("SELECT id FROM entities WHERE canonical=?", (canonical,))
        row = cur.fetchone()
        if row:
            c.execute(
                "UPDATE entities SET last_seen=?, mention_n=mention_n+1, tier='hot' WHERE id=?",
                (now, row[0]),
            )
            return row[0]
        cur = c.execute("SELECT entity_id FROM aliases WHERE alias=?", (canonical,))
        row = cur.fetchone()
        if row:
            c.execute(
                "UPDATE entities SET last_seen=?, mention_n=mention_n+1, tier='hot' WHERE id=?",
                (now, row[0]),
            )
            return row[0]
        c.execute(
            "INSERT INTO entities(canonical, type, first_seen, last_seen) VALUES(?,?,?,?)",
            (canonical, ent_type, now, now),
        )
        eid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Self-alias the original (un-normalized) name
        c.execute(
            "INSERT OR IGNORE INTO aliases(alias, entity_id) VALUES(?,?)",
            (_normalize(name), eid),
        )
        return eid


def add_alias(alias: str, entity_id: int) -> None:
    if not alias or not entity_id:
        return
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO aliases(alias, entity_id) VALUES(?,?)",
            (_normalize(alias), entity_id),
        )


# ── Fact insertion ───────────────────────────────────────────────────────────
import hashlib

def _fact_hash(entity_id: int, fact_type: str, fact_text: str) -> str:
    # blake2b for fact dedup: non-cryptographic, avoids SHA-1 OWASP flag
    h = hashlib.blake2b(digest_size=8)
    h.update(f"{entity_id}|{fact_type}|{fact_text.strip().lower()}".encode())
    return h.hexdigest()[:16]


def add_fact(entity_id: int, fact_type: str, fact_text: str,
             source_url: str = "", source_kind: str = "",
             confidence: float = 0.5, topic_norm: str = "") -> int:
    """Add or refresh a fact. Returns fact_id. If duplicate, refreshes captured_at + adds citation.
    topic_norm: normalized query that fetched this fact. Enables true cross-topic intersection."""
    if not entity_id or not fact_text.strip():
        return 0
    now = time.time()
    days = FRESHNESS_DAYS.get(fact_type, FRESHNESS_DAYS["claim"])
    expires_at = now + (days * 86400)
    fhash = _fact_hash(entity_id, fact_type, fact_text)
    with _conn() as c:
        # Try insert; if dup, refresh
        try:
            c.execute(
                "INSERT INTO facts(entity_id, fact_type, fact_text, fact_hash, confidence, captured_at, expires_at, tier, topic_norm) "
                "VALUES(?,?,?,?,?,?,?,'hot',?)",
                (entity_id, fact_type, fact_text, fhash, confidence, now, expires_at, topic_norm),
            )
            fid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            cur = c.execute(
                "SELECT id FROM facts WHERE entity_id=? AND fact_hash=?",
                (entity_id, fhash),
            )
            fid = cur.fetchone()[0]
            c.execute(
                "UPDATE facts SET captured_at=?, expires_at=?, tier='hot', topic_norm=COALESCE(topic_norm, ?) WHERE id=?",
                (now, expires_at, topic_norm, fid),
            )
        if source_url:
            c.execute(
                "INSERT OR REPLACE INTO citations(fact_id, source_url, source_kind, captured_at) "
                "VALUES(?,?,?,?)",
                (fid, source_url, source_kind, now),
            )
        # Link entity ↔ topic (separate from fact for entities that have no facts)
        if topic_norm:
            try:
                c.execute(
                    "INSERT INTO entity_topics(entity_id, topic_norm, mentions, last_seen) VALUES(?,?,1,?) "
                    "ON CONFLICT(entity_id, topic_norm) DO UPDATE SET mentions=mentions+1, last_seen=excluded.last_seen",
                    (entity_id, topic_norm, now),
                )
            except Exception:
                pass
        return fid


def link_entity_to_topic(entity_id: int, topic_norm: str) -> None:
    """Record that an entity was seen during a specific topic's research run.
    Use this for entities with no facts (still want them in cross-topic queries)."""
    if not entity_id or not topic_norm:
        return
    now = time.time()
    with _conn() as c:
        try:
            c.execute(
                "INSERT INTO entity_topics(entity_id, topic_norm, mentions, last_seen) VALUES(?,?,1,?) "
                "ON CONFLICT(entity_id, topic_norm) DO UPDATE SET mentions=mentions+1, last_seen=excluded.last_seen",
                (entity_id, topic_norm, now),
            )
        except Exception:
            pass


# ── Topic tracking ───────────────────────────────────────────────────────────
def record_topic(query: str, sources_n: int, entities_n: int) -> None:
    if not query.strip():
        return
    qnorm = _normalize(query)[:200]
    if not qnorm:
        return
    now = time.time()
    with _conn() as c:
        cur = c.execute("SELECT query_n FROM topics WHERE query_norm=?", (qnorm,))
        row = cur.fetchone()
        if row:
            c.execute(
                "UPDATE topics SET last_seen=?, query_n=query_n+1, sources_n=?, entities_n=? WHERE query_norm=?",
                (now, sources_n, entities_n, qnorm),
            )
        else:
            c.execute(
                "INSERT INTO topics(query_norm, first_seen, last_seen, sources_n, entities_n) VALUES(?,?,?,?,?)",
                (qnorm, now, now, sources_n, entities_n),
            )


# ── Compaction (event-driven, no scheduler) ──────────────────────────────────
def _inserts_since_compact() -> int:
    with _conn() as c:
        row = c.execute("SELECT value FROM meta WHERE key='inserts_since_compact'").fetchone()
        return int(row[0]) if row else 0


def _bump_insert_counter(n: int = 1) -> None:
    with _conn() as c:
        cur = c.execute("SELECT value FROM meta WHERE key='inserts_since_compact'").fetchone()
        cur_val = int(cur[0]) if cur else 0
        new_val = cur_val + n
        c.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('inserts_since_compact', ?)",
            (str(new_val),),
        )


def maybe_compact() -> dict:
    """Event-driven compaction: only runs when N inserts have accumulated.
    Demotes stale facts hot→warm→cold. Never deletes."""
    if _inserts_since_compact() < COMPACT_AFTER_N_INSERTS:
        return {"ran": False, "reason": "below threshold"}
    return compact_now()


def compact_now() -> dict:
    """Run one compaction pass: hot→warm if expired, warm→cold if very stale.
    Cold facts stay queryable but ranked low. Returns counts moved."""
    now = time.time()
    warm_cutoff = now                       # past expires_at = warm
    cold_cutoff = now + (90 * 86400) * -1   # 90 days past expiry = cold
    with _conn() as c:
        h2w = c.execute(
            "UPDATE facts SET tier='warm' WHERE tier='hot' AND expires_at < ?",
            (warm_cutoff,),
        ).rowcount
        w2c = c.execute(
            "UPDATE facts SET tier='cold' WHERE tier='warm' AND expires_at < ?",
            (cold_cutoff,),
        ).rowcount
        # Cold entities (no facts in hot/warm for 6 months)
        cold_cut = now - (180 * 86400)
        e_demote = c.execute(
            "UPDATE entities SET tier='cold' WHERE tier!='cold' AND last_seen < ?",
            (cold_cut,),
        ).rowcount
        c.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('inserts_since_compact', '0')"
        )
        c.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('last_compact_at', ?)",
            (str(now),),
        )
    return {"ran": True, "facts_h2w": h2w, "facts_w2c": w2c, "entities_demoted": e_demote}


# ── Status / introspection ───────────────────────────────────────────────────
def status() -> dict:
    with _conn() as c:
        ent = c.execute("SELECT COUNT(*), SUM(mention_n) FROM entities").fetchone()
        ent_by_tier = dict(c.execute(
            "SELECT tier, COUNT(*) FROM entities GROUP BY tier"
        ).fetchall())
        facts = c.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        facts_by_tier = dict(c.execute(
            "SELECT tier, COUNT(*) FROM facts GROUP BY tier"
        ).fetchall())
        facts_stale = c.execute(
            "SELECT COUNT(*) FROM facts WHERE expires_at < ? AND tier='hot'",
            (time.time(),),
        ).fetchone()[0]
        topics = c.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        last_compact = c.execute(
            "SELECT value FROM meta WHERE key='last_compact_at'"
        ).fetchone()
        last_compact_iso = (
            datetime.fromtimestamp(float(last_compact[0])).isoformat(timespec="seconds")
            if last_compact else "never"
        )
    p = db_path()
    size_mb = round(p.stat().st_size / (1024 * 1024), 2) if p.exists() else 0.0
    return {
        "entities":           ent[0] or 0,
        "entities_by_tier":   ent_by_tier,
        "total_mentions":     ent[1] or 0,
        "facts":              facts,
        "facts_by_tier":      facts_by_tier,
        "facts_stale_in_hot": facts_stale,
        "topics_seen":        topics,
        "last_compaction":    last_compact_iso,
        "db_path":            str(p),
        "db_size_mb":         size_mb,
    }


def recall_entity(name: str, max_facts: int = 50, include_cold: bool = False) -> dict:
    """Return everything Jester knows about an entity. Includes facts + sources + tier."""
    canonical = _normalize(name)
    if not canonical:
        return {"found": False, "message": "Empty query"}
    with _conn() as c:
        # Resolve via canonical or alias
        ent = c.execute(
            "SELECT id, canonical, type, first_seen, last_seen, mention_n, tier "
            "FROM entities WHERE canonical=?",
            (canonical,),
        ).fetchone()
        if not ent:
            row = c.execute("SELECT entity_id FROM aliases WHERE alias=?", (canonical,)).fetchone()
            if not row:
                # Fuzzy: try LIKE
                row = c.execute(
                    "SELECT id, canonical, type, first_seen, last_seen, mention_n, tier "
                    "FROM entities WHERE canonical LIKE ? ORDER BY mention_n DESC LIMIT 1",
                    (f"%{canonical}%",),
                ).fetchone()
                if not row:
                    return {"found": False, "message": f"No entity matching '{name}'"}
                ent = row
            else:
                ent = c.execute(
                    "SELECT id, canonical, type, first_seen, last_seen, mention_n, tier FROM entities WHERE id=?",
                    (row[0],),
                ).fetchone()
        eid, canon, etype, first, last, mentions, tier = ent
        tier_filter = "" if include_cold else " AND tier != 'cold'"
        facts = c.execute(
            f"SELECT id, fact_type, fact_text, captured_at, expires_at, tier, confidence "
            f"FROM facts WHERE entity_id=?{tier_filter} ORDER BY captured_at DESC LIMIT ?",
            (eid, max_facts),
        ).fetchall()
        fact_list = []
        for fid, ft, ftext, captured, expires, ftier, conf in facts:
            sources = c.execute(
                "SELECT source_url, source_kind FROM citations WHERE fact_id=? LIMIT 5",
                (fid,),
            ).fetchall()
            stale = expires < time.time()
            fact_list.append({
                "type":       ft,
                "text":       ftext,
                "tier":       ftier,
                "stale":      stale,
                "captured":   datetime.fromtimestamp(captured).isoformat(timespec="seconds"),
                "confidence": conf,
                "sources":    [{"url": u, "kind": k} for u, k in sources],
            })
        aliases = [a for (a,) in c.execute(
            "SELECT alias FROM aliases WHERE entity_id=? AND alias != ?",
            (eid, canon),
        ).fetchall()]
    return {
        "found":          True,
        "canonical":      canon,
        "type":           etype,
        "tier":           tier,
        "mention_count":  mentions,
        "first_seen":     datetime.fromtimestamp(first).isoformat(timespec="seconds"),
        "last_seen":      datetime.fromtimestamp(last).isoformat(timespec="seconds"),
        "aliases":        aliases,
        "facts":          fact_list,
    }


def find_connections(topic_a: str, topic_b: str) -> dict:
    """Find entities that genuinely appear in BOTH topics' research history.
    Real intersection via entity_topics linkage table, not a heuristic."""
    a_norm = _normalize(topic_a)
    b_norm = _normalize(topic_b)
    if not a_norm or not b_norm:
        return {"connections": [], "topic_a_known": False, "topic_b_known": False}
    with _conn() as c:
        # Confirm both topics have been seen
        topic_a_known = c.execute("SELECT 1 FROM topics WHERE query_norm=?", (a_norm,)).fetchone() is not None
        topic_b_known = c.execute("SELECT 1 FROM topics WHERE query_norm=?", (b_norm,)).fetchone() is not None
        # Real intersection: entities that appear in entity_topics for BOTH topics
        rows = c.execute("""
            SELECT e.canonical, e.type,
                   ta.mentions AS mentions_a,
                   tb.mentions AS mentions_b,
                   (ta.mentions + tb.mentions) AS total
            FROM entities e
            JOIN entity_topics ta ON ta.entity_id = e.id AND ta.topic_norm = ?
            JOIN entity_topics tb ON tb.entity_id = e.id AND tb.topic_norm = ?
            ORDER BY total DESC
            LIMIT 30
        """, (a_norm, b_norm)).fetchall()
    return {
        "topic_a_known": topic_a_known,
        "topic_b_known": topic_b_known,
        "connections": [
            {"entity": r[0], "type": r[1], "mentions_in_a": r[2], "mentions_in_b": r[3]}
            for r in rows
        ],
    }


def per_source_trust() -> dict:
    """Returns each source domain's track record: how many facts it backed, average tier.
    Sources whose facts mostly survive (stay hot/warm) are higher-trust."""
    with _conn() as c:
        rows = c.execute("""
            SELECT
                source_kind,
                COUNT(*) as fact_count,
                SUM(CASE WHEN f.tier='hot'  THEN 1 ELSE 0 END) as hot_n,
                SUM(CASE WHEN f.tier='warm' THEN 1 ELSE 0 END) as warm_n,
                SUM(CASE WHEN f.tier='cold' THEN 1 ELSE 0 END) as cold_n
            FROM citations c
            JOIN facts f ON f.id = c.fact_id
            WHERE c.source_kind != ''
            GROUP BY source_kind
            ORDER BY fact_count DESC
        """).fetchall()
    out = {}
    for kind, total, hot, warm, cold in rows:
        # Trust score: weighted mix favoring hot facts
        score = (hot * 1.0 + warm * 0.5 + cold * 0.1) / max(total, 1)
        out[kind] = {
            "fact_count": total,
            "hot": hot,
            "warm": warm,
            "cold": cold,
            "trust_score": round(score, 3),
        }
    return out


def topic_mastery(query: str) -> dict:
    """How well does Jester know this topic?"""
    qnorm = _normalize(query)[:200]
    with _conn() as c:
        row = c.execute(
            "SELECT first_seen, last_seen, query_n, sources_n, entities_n FROM topics WHERE query_norm=?",
            (qnorm,),
        ).fetchone()
    if not row:
        return {"queried": False, "message": "Never researched this exact topic"}
    first, last, qn, sn, en = row
    days_since = (time.time() - last) / 86400
    return {
        "queried":         True,
        "query_count":     qn,
        "sources_average": sn,
        "entities_built":  en,
        "first_researched": datetime.fromtimestamp(first).isoformat(timespec="seconds"),
        "last_researched":  datetime.fromtimestamp(last).isoformat(timespec="seconds"),
        "days_since_last":  round(days_since, 1),
        "stale":            days_since > 30,
    }
