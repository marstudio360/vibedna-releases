"""State-of-world snapshots + temporal diff.

Snapshot = a frozen summary of a topic at point T (clusters + money claims +
trusted creators + top patterns). Diff between snapshots T1 and T2 surfaces
what's new, what died, what got replaced.

Schema is pack-export friendly (versioned + portable).
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

from paths import jester_home
from corroborate import cluster_findings
from money_flow import money_flow_summary
from creator_trust import creator_trust_for_topic


SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS state_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_version  INTEGER DEFAULT 1,
    topic           TEXT NOT NULL,
    snapshot_date   TEXT NOT NULL,
    summary_json    TEXT NOT NULL,
    raw_findings_ref TEXT,
    created_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snap_topic ON state_snapshots(topic);
CREATE INDEX IF NOT EXISTS idx_snap_date  ON state_snapshots(snapshot_date);

CREATE TABLE IF NOT EXISTS snapshot_schedule (
    topic           TEXT PRIMARY KEY,
    cadence         TEXT NOT NULL,
    last_run        REAL,
    next_due        REAL
);
"""


def db_path():
    return jester_home() / "snapshots.db"


@contextmanager
def _conn():
    c = sqlite3.connect(db_path())
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def snapshot_state(topic: str, raw_findings_ref: str = "") -> dict:
    """Materialize current state of a topic into a snapshot row."""
    clusters = cluster_findings(topic)
    money = money_flow_summary(topic)
    creators = creator_trust_for_topic(topic, limit=10)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "topic": topic,
        "captured_at": time.time(),
        "n_clusters": len(clusters),
        "top_ideas": [c["idea"] for c in clusters[:10]],
        "money_patterns": money.get("top_patterns", []),
        "top_creators": creators,
    }
    now = time.time()
    date_iso = datetime.utcnow().strftime("%Y-%m-%d")
    with _conn() as c:
        c.execute(
            "INSERT INTO state_snapshots(schema_version, topic, snapshot_date, "
            "summary_json, raw_findings_ref, created_at) VALUES(?,?,?,?,?,?)",
            (SCHEMA_VERSION, topic, date_iso, json.dumps(summary),
             raw_findings_ref, now),
        )
        sid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"snapshot_id": sid, "topic": topic, "snapshot_date": date_iso,
            "summary": summary}


def _load_snapshot(topic: str, since_date: str | None = None) -> dict | None:
    with _conn() as c:
        if since_date:
            row = c.execute(
                "SELECT id, snapshot_date, summary_json FROM state_snapshots "
                "WHERE topic=? AND snapshot_date<=? ORDER BY snapshot_date DESC LIMIT 1",
                (topic, since_date),
            ).fetchone()
        else:
            row = c.execute(
                "SELECT id, snapshot_date, summary_json FROM state_snapshots "
                "WHERE topic=? ORDER BY snapshot_date DESC LIMIT 1",
                (topic,),
            ).fetchone()
    if not row:
        return None
    return {"id": row[0], "date": row[1], "summary": json.loads(row[2])}


def checkpoint_diff(topic: str, since_date: str) -> dict:
    """Compare latest snapshot vs the most recent snapshot <= since_date.
    Returns what's new, what died, what tools won, what got replaced."""
    latest = _load_snapshot(topic)
    prior = _load_snapshot(topic, since_date=since_date)
    if not latest:
        return {"error": f"No snapshot for topic '{topic}'"}
    if not prior:
        return {"error": f"No snapshot at or before {since_date} for topic '{topic}'",
                "latest_only": latest}

    prior_ideas = set(prior["summary"].get("top_ideas", []))
    latest_ideas = set(latest["summary"].get("top_ideas", []))
    new_ideas = sorted(latest_ideas - prior_ideas)
    died = sorted(prior_ideas - latest_ideas)

    def _stack_set(snap):
        return {p.get("stack", "") for p in snap.get("money_patterns", []) if p.get("stack")}

    prior_stacks = _stack_set(prior["summary"])
    latest_stacks = _stack_set(latest["summary"])
    won_stacks = sorted(latest_stacks - prior_stacks)
    lost_stacks = sorted(prior_stacks - latest_stacks)

    prior_creators = {c["creator"] for c in prior["summary"].get("top_creators", [])}
    latest_creators = {c["creator"] for c in latest["summary"].get("top_creators", [])}

    return {
        "topic": topic,
        "from_date": prior["date"],
        "to_date": latest["date"],
        "new_ideas": new_ideas,
        "died_ideas": died,
        "stacks_gained": won_stacks,
        "stacks_lost": lost_stacks,
        "creators_rising": sorted(latest_creators - prior_creators),
        "creators_fading": sorted(prior_creators - latest_creators),
        "prior_snapshot_id": prior["id"],
        "latest_snapshot_id": latest["id"],
    }


def schedule_weekly_snapshot(topic: str, cadence: str = "weekly") -> dict:
    """[STUB scheduler] Queues a topic for recurring snapshots. Actual cron
    must be wired by self_feed or external scheduler. This stores intent."""
    cadence_days = {"daily": 1, "weekly": 7, "monthly": 30}.get(cadence, 7)
    now = time.time()
    next_due = now + cadence_days * 86400
    with _conn() as c:
        c.execute(
            "INSERT INTO snapshot_schedule(topic, cadence, last_run, next_due) "
            "VALUES(?,?,?,?) ON CONFLICT(topic) DO UPDATE SET "
            "cadence=excluded.cadence, next_due=excluded.next_due",
            (topic, cadence, None, next_due),
        )
    return {"topic": topic, "cadence": cadence, "next_due_ts": next_due,
            "note": "Scheduled. Hook into self_feed loop or external cron to auto-run snapshot_state(topic)."}


def list_schedule() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT topic, cadence, last_run, next_due FROM snapshot_schedule"
        ).fetchall()
    return [{"topic": r[0], "cadence": r[1], "last_run": r[2], "next_due": r[3]} for r in rows]
