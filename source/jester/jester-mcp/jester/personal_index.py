"""
Jester Personal Index: your own growing semantic memory of every page Jester has retrieved.

Backed by SQLite + numpy blob columns. Cosine similarity computed at query time.
Scales fine to ~100k entries on a laptop. Beyond that, swap to sqlite-vec or chromadb.

This is the "personal Exa". Exa can sell you a global index, but only Jester gives you
a private index of everything YOU have ever researched.
"""

import sqlite3
import json
import hashlib
import time
import blas_threads  # noqa: F401  must precede numpy, see module docstring
import numpy as np
from pathlib import Path

from paths import personal_index_db
INDEX_DB = personal_index_db()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(INDEX_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id          TEXT PRIMARY KEY,
            url         TEXT,
            title       TEXT,
            content     TEXT,
            source      TEXT,
            query       TEXT,
            created_at  REAL,
            embedding   BLOB
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON entries(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON entries(source)")
    return conn


def _row_id(url: str, title: str) -> str:
    # blake2b for index key: non-cryptographic, avoids OWASP MD5 flag
    return hashlib.blake2b(f"{url}||{title}".encode(), digest_size=16).hexdigest()


def add_entries(items: list[dict], source: str = "", query: str = "") -> int:
    """Embed and store a batch of items. Each item: {url, title, content}.
    De-dupes by (url, title) hash. Returns number of NEW entries added."""
    if not items:
        return 0

    from neural import embed

    items = [i for i in items if (i.get("url") or i.get("title"))]
    if not items:
        return 0

    docs = []
    for it in items:
        title = (it.get("title") or "")[:200]
        content = (it.get("content") or "")[:1500]
        docs.append(f"{title} {title} {content}".strip())

    try:
        vecs = embed(docs)
    except Exception:
        return 0

    now = time.time()
    rows = []
    for it, vec in zip(items, vecs):
        url = (it.get("url") or "")[:500]
        title = (it.get("title") or "")[:300]
        rows.append((
            _row_id(url, title),
            url,
            title,
            (it.get("content") or "")[:2500],
            source[:60],
            query[:300],
            now,
            vec.tobytes(),
        ))

    conn = _conn()
    inserted = 0
    try:
        for row in rows:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO entries (id,url,title,content,source,query,created_at,embedding) VALUES (?,?,?,?,?,?,?,?)",
                    row,
                )
                if conn.total_changes > inserted:
                    inserted = conn.total_changes
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()
    return inserted


def search(query: str, top_k: int = 5, source: str | None = None) -> list[dict]:
    """Cosine-search the personal index for entries similar to the query.
    Optional source filter (e.g. only 'reddit' or only 'web')."""
    from neural import embed

    conn = _conn()
    try:
        if source:
            cur = conn.execute(
                "SELECT id,url,title,content,source,query,created_at,embedding FROM entries WHERE source = ?",
                (source,),
            )
        else:
            cur = conn.execute(
                "SELECT id,url,title,content,source,query,created_at,embedding FROM entries"
            )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    embs = np.stack([np.frombuffer(r[7], dtype=np.float32) for r in rows])
    q_vec = embed([query])[0]
    scores = embs @ q_vec

    top_idx = np.argsort(-scores)[: min(top_k, len(rows))]
    out = []
    for i in top_idx:
        r = rows[int(i)]
        out.append({
            "url":        r[1],
            "title":      r[2],
            "content":    r[3],
            "source":     r[4],
            "query":      r[5],
            "created_at": r[6],
            "score":      float(scores[int(i)]),
        })
    return out


def find_similar_to_url(url: str, top_k: int = 5) -> list[dict]:
    """Given a URL already in the index, return semantically similar entries."""
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT title, content, embedding FROM entries WHERE url = ? LIMIT 1",
            (url,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return search(url, top_k=top_k)

    title, content, emb_blob = row
    seed_text = f"{title} {content}"[:2000]
    return search(seed_text, top_k=top_k + 1)[1:top_k + 1]


def stats() -> dict:
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        sources = dict(conn.execute(
            "SELECT source, COUNT(*) FROM entries GROUP BY source ORDER BY 2 DESC"
        ).fetchall())
        oldest = conn.execute("SELECT MIN(created_at) FROM entries").fetchone()[0]
        newest = conn.execute("SELECT MAX(created_at) FROM entries").fetchone()[0]
    finally:
        conn.close()
    return {
        "total":   total,
        "sources": sources,
        "oldest":  oldest,
        "newest":  newest,
        "db_path": str(INDEX_DB),
        "db_size_kb": INDEX_DB.stat().st_size / 1024 if INDEX_DB.exists() else 0,
    }
