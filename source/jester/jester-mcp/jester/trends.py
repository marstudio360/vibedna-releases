"""
Jester Trend Velocity: score whether a topic is accelerating or dying.

Takes a list of findings (each with a captured_at or published_at timestamp)
and returns a velocity score + direction label.

Algorithm:
  - Split findings into two time windows: recent (last 30d) vs older (31-90d)
  - Velocity = recent_count / max(1, older_count)  (normalized per-day)
  - Engagement bonus: upvote/score signals in content boost the score
  - Direction: RISING / STABLE / FALLING + numeric score
"""

import re
import time
from collections import defaultdict
from datetime import datetime, timezone


_UPVOTE_RE = re.compile(r"\b(\d{1,6})\s*(?:upvotes?|points?|votes?|likes?|karma)\b", re.I)
_DATE_RE    = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_ts(item: dict) -> float | None:
    """Extract Unix timestamp from item. Tries captured_at, published_at, date string in content."""
    for key in ("captured_at", "published_at"):
        val = item.get(key)
        if isinstance(val, (int, float)) and val > 1e9:
            return float(val)
        if isinstance(val, str):
            m = _DATE_RE.search(val)
            if m:
                try:
                    return datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                        tzinfo=timezone.utc).timestamp()
                except Exception:
                    pass
    text = (item.get("content") or item.get("snippet") or item.get("title") or "")[:500]
    m = _DATE_RE.search(text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                tzinfo=timezone.utc).timestamp()
        except Exception:
            pass
    return None


def _engagement(item: dict) -> float:
    """Extract engagement signal (upvotes, score) from content. Returns 0-1 bonus."""
    text = (item.get("content") or item.get("snippet") or "")[:300]
    matches = _UPVOTE_RE.findall(text)
    if not matches:
        return 0.0
    total = sum(int(m) for m in matches)
    return min(1.0, total / 1000)


def score_velocity(findings: list[dict], now: float | None = None) -> dict:
    """
    Score trend velocity for a batch of findings.

    Returns:
        {
            "direction":    "RISING" | "STABLE" | "FALLING" | "INSUFFICIENT_DATA",
            "velocity":     float,   # ratio recent/older (>1 = rising)
            "score":        float,   # 0-100 normalized
            "recent_count": int,     # findings in last 30d
            "older_count":  int,     # findings 31-90d ago
            "engagement":   float,   # avg engagement signal
            "peak_sources": list[str],
            "summary":      str,
        }
    """
    if now is None:
        now = time.time()

    DAY = 86400
    RECENT_WINDOW = 30 * DAY
    OLDER_WINDOW  = 90 * DAY

    recent, older = [], []
    no_date = 0

    for item in findings:
        ts = _parse_ts(item)
        if ts is None:
            no_date += 1
            continue
        age = now - ts
        if age <= RECENT_WINDOW:
            recent.append(item)
        elif age <= OLDER_WINDOW:
            older.append(item)

    if len(recent) + len(older) < 3:
        return {
            "direction": "INSUFFICIENT_DATA",
            "velocity": 0.0,
            "score": 0.0,
            "recent_count": len(recent),
            "older_count": len(older),
            "engagement": 0.0,
            "peak_sources": [],
            "summary": f"Not enough dated findings ({no_date} undated). Need timestamps to score velocity.",
        }

    # Per-day normalization: recent window = 30d, older = 60d
    recent_rate = len(recent) / 30
    older_rate  = len(older)  / 60
    velocity    = recent_rate / max(0.01, older_rate)

    avg_engagement = sum(_engagement(i) for i in recent + older) / max(1, len(recent) + len(older))

    # Score 0-100
    raw_score = min(100.0, velocity * 50 + avg_engagement * 20)

    if velocity >= 1.5:
        direction = "RISING"
    elif velocity <= 0.6:
        direction = "FALLING"
    else:
        direction = "STABLE"

    # Peak sources in recent window
    src_counts: dict[str, int] = defaultdict(int)
    for item in recent:
        s = item.get("source") or "unknown"
        src_counts[s] += 1
    peak_sources = sorted(src_counts, key=lambda k: src_counts[k], reverse=True)[:3]

    summary_map = {
        "RISING":  f"Topic is accelerating: {len(recent)} findings in the last 30 days vs {len(older)} in the prior 60. Velocity {velocity:.1f}×.",
        "STABLE":  f"Topic is steady: {len(recent)} findings in 30d vs {len(older)} in prior 60d.",
        "FALLING": f"Topic is cooling: only {len(recent)} findings in the last 30 days vs {len(older)} prior.",
    }

    return {
        "direction":    direction,
        "velocity":     round(velocity, 3),
        "score":        round(raw_score, 1),
        "recent_count": len(recent),
        "older_count":  len(older),
        "engagement":   round(avg_engagement, 3),
        "peak_sources": peak_sources,
        "summary":      summary_map[direction],
    }


def velocity_label(score_dict: dict) -> str:
    """One-line label for report headers."""
    d = score_dict.get("direction", "?")
    v = score_dict.get("velocity", 0)
    arrows = {"RISING": "↑", "STABLE": "→", "FALLING": "↓", "INSUFFICIENT_DATA": "?"}
    return f"{arrows.get(d, '?')} {d}  (velocity {v:.1f}×)"
