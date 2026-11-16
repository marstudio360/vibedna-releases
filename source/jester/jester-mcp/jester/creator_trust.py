"""Per-(creator, topic) trust graph.

A creator (YouTube channel, podcast host, Twitter handle, substack author, reddit user)
can be gold on one topic and trash on another. Scoring is per-topic, not global.

Score range: 0.0 to 1.0. Default 0.5 (neutral). Adjusted via outcome signals:
explicit flagging, fact survival in the trust graph, repeat exposure, etc.
"""

import re
import sqlite3
import time
from contextlib import contextmanager

from paths import jester_home


SCHEMA = """
CREATE TABLE IF NOT EXISTS creator_topic_trust (
    creator_id   TEXT NOT NULL,
    topic        TEXT NOT NULL,
    score        REAL DEFAULT 0.5,
    n_samples    INTEGER DEFAULT 0,
    n_valuable   INTEGER DEFAULT 0,
    n_flagged    INTEGER DEFAULT 0,
    last_updated REAL NOT NULL,
    PRIMARY KEY (creator_id, topic)
);
CREATE INDEX IF NOT EXISTS idx_ctt_topic ON creator_topic_trust(topic);
CREATE INDEX IF NOT EXISTS idx_ctt_score ON creator_topic_trust(score);

CREATE TABLE IF NOT EXISTS creator_topic_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id   TEXT NOT NULL,
    topic        TEXT NOT NULL,
    signal       TEXT NOT NULL,
    delta        REAL NOT NULL,
    note         TEXT,
    ts           REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ctl_creator ON creator_topic_log(creator_id, topic);
"""


def db_path():
    return jester_home() / "creator_trust.db"


@contextmanager
def _conn():
    c = sqlite3.connect(db_path())
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


_NORM = re.compile(r"[^a-z0-9]+")

def _norm_topic(s: str) -> str:
    return _NORM.sub("", (s or "").lower())[:120]


def _norm_creator(s: str) -> str:
    return (s or "").strip().lower()[:200]


def record_creator_observation(creator_id: str, topic: str, signal: str = "seen",
                               delta: float = 0.0, note: str = "") -> None:
    """Bump n_samples and adjust score by delta. signal is a label (seen|valuable|flagged|fact_survived)."""
    cid = _norm_creator(creator_id)
    t = _norm_topic(topic)
    if not cid or not t:
        return
    now = time.time()
    with _conn() as c:
        row = c.execute(
            "SELECT score, n_samples, n_valuable, n_flagged FROM creator_topic_trust WHERE creator_id=? AND topic=?",
            (cid, t),
        ).fetchone()
        if row:
            score, n, nv, nf = row
            score = max(0.0, min(1.0, score + delta))
            nv += 1 if signal == "valuable" else 0
            nf += 1 if signal == "flagged" else 0
            c.execute(
                "UPDATE creator_topic_trust SET score=?, n_samples=n_samples+1, "
                "n_valuable=?, n_flagged=?, last_updated=? WHERE creator_id=? AND topic=?",
                (score, nv, nf, now, cid, t),
            )
        else:
            score = max(0.0, min(1.0, 0.5 + delta))
            c.execute(
                "INSERT INTO creator_topic_trust(creator_id, topic, score, n_samples, n_valuable, n_flagged, last_updated) "
                "VALUES(?,?,?,1,?,?,?)",
                (cid, t, score,
                 1 if signal == "valuable" else 0,
                 1 if signal == "flagged" else 0,
                 now),
            )
        c.execute(
            "INSERT INTO creator_topic_log(creator_id, topic, signal, delta, note, ts) VALUES(?,?,?,?,?,?)",
            (cid, t, signal, delta, note, now),
        )


def flag_creator_finding(creator_id: str, topic: str, valuable: bool, note: str = "") -> dict:
    """Explicit feedback from user. valuable=True bumps +0.10, False drops -0.15."""
    delta = 0.10 if valuable else -0.15
    signal = "valuable" if valuable else "flagged"
    record_creator_observation(creator_id, topic, signal, delta, note)
    return creator_trust_score(creator_id, topic)


def creator_trust_score(creator_id: str, topic: str) -> dict:
    cid = _norm_creator(creator_id)
    t = _norm_topic(topic)
    with _conn() as c:
        row = c.execute(
            "SELECT score, n_samples, n_valuable, n_flagged, last_updated "
            "FROM creator_topic_trust WHERE creator_id=? AND topic=?",
            (cid, t),
        ).fetchone()
    if not row:
        return {"creator": cid, "topic": t, "score": 0.5, "n_samples": 0, "known": False}
    return {
        "creator": cid, "topic": t,
        "score": round(row[0], 3),
        "n_samples": row[1],
        "n_valuable": row[2],
        "n_flagged": row[3],
        "last_updated": row[4],
        "known": True,
    }


def creator_trust_for_topic(topic: str, limit: int = 20, min_samples: int = 1) -> list[dict]:
    t = _norm_topic(topic)
    with _conn() as c:
        rows = c.execute(
            "SELECT creator_id, score, n_samples, n_valuable, n_flagged FROM creator_topic_trust "
            "WHERE topic=? AND n_samples>=? ORDER BY score DESC, n_samples DESC LIMIT ?",
            (t, min_samples, limit),
        ).fetchall()
    return [
        {"creator": r[0], "score": round(r[1], 3), "n_samples": r[2],
         "n_valuable": r[3], "n_flagged": r[4]}
        for r in rows
    ]


_YT_RE = re.compile(r"youtube\.com/(?:channel/|c/|user/|@)([^/?&\s]+)|youtu\.be/", re.I)
_TWITTER_RE = re.compile(r"(?:twitter|x)\.com/([^/?&\s]+)", re.I)
_REDDIT_RE = re.compile(r"reddit\.com/(?:r/|user/)([^/?&\s]+)", re.I)
_SUBSTACK_RE = re.compile(r"([a-z0-9-]+)\.substack\.com", re.I)


def extract_creator_id(url: str, title: str = "") -> str:
    """Best-effort creator extraction from URL. Empty string if none found."""
    if not url:
        return ""
    for rx, prefix in [(_YT_RE, "yt:"), (_TWITTER_RE, "x:"),
                       (_REDDIT_RE, "reddit:"), (_SUBSTACK_RE, "substack:")]:
        m = rx.search(url)
        if m:
            handle = m.group(1) if m.groups() else ""
            if handle:
                return f"{prefix}{handle.lower()}"
    return ""
