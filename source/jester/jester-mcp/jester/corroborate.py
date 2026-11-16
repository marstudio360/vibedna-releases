"""Cross-source corroboration: cluster ideas appearing across multiple sources.

Lightweight fingerprint: lowercased, stop-stripped token shingles + Jaccard similarity.
No embeddings dependency (works offline). When `neural` embeddings are available
the caller can swap in cosine_rerank; the public API stays the same.
"""

import re
import sqlite3
import time
from collections import Counter, defaultdict
from contextlib import contextmanager

from paths import jester_home


SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic         TEXT NOT NULL,
    source        TEXT,
    creator_id    TEXT,
    url           TEXT,
    title         TEXT,
    snippet       TEXT,
    fingerprint   TEXT,
    captured_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_find_topic ON findings(topic);
CREATE INDEX IF NOT EXISTS idx_find_fp ON findings(fingerprint);

CREATE TABLE IF NOT EXISTS finding_clusters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic         TEXT NOT NULL,
    idea          TEXT,
    n_findings    INTEGER DEFAULT 0,
    n_sources     INTEGER DEFAULT 0,
    n_creators    INTEGER DEFAULT 0,
    created_at    REAL NOT NULL
);
"""


def db_path():
    return jester_home() / "findings.db"


@contextmanager
def _conn():
    c = sqlite3.connect(db_path())
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


_STOP = {
    "the","and","for","with","from","that","this","what","best","tools","you","your",
    "are","was","were","have","has","had","but","not","just","also","then","than","into",
    "more","most","some","like","very","they","them","their","there","here","about","over",
    "i","it","is","of","to","a","an","in","on","be","or","as","by","at","my","we","our","us",
}
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def fingerprint(text: str) -> set[str]:
    """Token shingles of size 1 from cleaned text. Returns set for Jaccard."""
    if not text:
        return set()
    toks = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]
    return set(toks[:200])


def _fp_str(fp: set[str]) -> str:
    return ",".join(sorted(fp)[:40])


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def add_findings(topic: str, items: list[dict], source: str = "") -> int:
    if not items:
        return 0
    now = time.time()
    n = 0
    with _conn() as c:
        for it in items:
            title = it.get("title", "") or ""
            snippet = (it.get("content") or it.get("snippet") or "")[:600]
            url = it.get("url", "") or ""
            creator = it.get("creator_id", "") or ""
            fp = fingerprint(f"{title} {snippet}")
            c.execute(
                "INSERT INTO findings(topic, source, creator_id, url, title, snippet, fingerprint, captured_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (topic, source, creator, url, title, snippet, _fp_str(fp), now),
            )
            n += 1
    return n


def cluster_findings(topic: str, similarity: float = 0.25, limit: int = 200) -> list[dict]:
    """Greedy clustering by Jaccard similarity. Returns clusters sorted by
    (n_creators desc, n_sources desc, n_findings desc)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, source, creator_id, url, title, snippet, fingerprint "
            "FROM findings WHERE topic=? ORDER BY captured_at DESC LIMIT ?",
            (topic, limit),
        ).fetchall()
    if not rows:
        return []
    items = []
    for r in rows:
        fp = set(r[6].split(",")) if r[6] else set()
        items.append({"id": r[0], "source": r[1], "creator_id": r[2],
                      "url": r[3], "title": r[4], "snippet": r[5], "fp": fp})
    clusters = []
    for it in items:
        placed = False
        for cl in clusters:
            sim = jaccard(it["fp"], cl["_centroid"])
            if sim >= similarity:
                cl["members"].append(it)
                cl["_centroid"] = cl["_centroid"] | it["fp"]
                placed = True
                break
        if not placed:
            clusters.append({"_centroid": set(it["fp"]), "members": [it]})
    out = []
    for cl in clusters:
        members = cl["members"]
        sources = {m["source"] for m in members if m["source"]}
        creators = {m["creator_id"] for m in members if m["creator_id"]}
        top = members[0]
        out.append({
            "idea": top["title"] or top["snippet"][:140],
            "sample_url": top["url"],
            "n_findings": len(members),
            "n_sources": len(sources),
            "n_creators": len(creators),
            "corroborating_sources": sorted(sources),
            "members": [
                {"source": m["source"], "title": m["title"], "url": m["url"]}
                for m in members[:8]
            ],
        })
    out.sort(key=lambda x: (x["n_creators"], x["n_sources"], x["n_findings"]), reverse=True)
    return out
