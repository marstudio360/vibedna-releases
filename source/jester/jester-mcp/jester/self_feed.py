"""
Jester Self-Feed Loop
Runs nightly. Reads the most recent reports, extracts follow-up topics,
researches each one, compounds the knowledge base automatically.
Schedule: Windows Task Scheduler → nightly 3AM
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

from paths import reports_dir, self_feed_log_path, self_feed_state_path
PYTHON      = sys.executable
JESTER_PY   = str(Path(__file__).parent / "jester.py")
REPORTS_DIR = reports_dir()
FEED_LOG    = self_feed_log_path()
FEED_STATE  = self_feed_state_path()

MAX_REPORTS_PER_RUN = 3   # how many past reports to extract topics from
MAX_TOPICS_PER_REPORT = 5  # topics extracted per report
MAX_RESEARCH_RUNS = 8      # hard cap on API calls per night


def _load_state() -> dict:
    if FEED_STATE.exists():
        try:
            return json.loads(FEED_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"processed": [], "queued": [], "total_runs": 0}


def _save_state(state: dict):
    FEED_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _get_unprocessed_reports(state: dict) -> list[Path]:
    """Return recent reports that haven't been self-fed yet."""
    all_reports = sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    processed = set(state.get("processed", []))
    unprocessed = [r for r in all_reports if r.name not in processed]
    return unprocessed[:MAX_REPORTS_PER_RUN]


def _extract_topics_from_report(report_path: Path) -> list[dict]:
    """Use modes.py self_feed prompt to extract follow-up topics from a report."""
    import os
    from dotenv import load_dotenv
    load_dotenv(JESTER_DIR / ".env")

    sys.path.insert(0, str(JESTER_DIR))
    from modes import run_mode
    from jester import MODEL_MAP

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return []

    try:
        content = report_path.read_text(encoding="utf-8", errors="ignore")[:15000]
        result  = run_mode(content, "self_feed", MODEL_MAP["haiku"], api_key)

        # Parse topics from the structured output
        topics = []
        lines  = result.splitlines()
        current_topic = None
        current_sources = "web reddit hn"
        current_priority = "MEDIUM"

        for line in lines:
            line = line.strip()
            # Match numbered topic lines like "1. [TOPIC NAME]"
            import re
            m = re.match(r"^\d+\.\s+\[?(.+?)\]?\s*$", line)
            if m:
                if current_topic:
                    topics.append({
                        "topic":    current_topic,
                        "sources":  current_sources,
                        "priority": current_priority,
                    })
                current_topic    = m.group(1).strip()
                current_sources  = "web reddit hn"
                current_priority = "MEDIUM"
            elif line.startswith("Sources:") and current_topic:
                raw = line.replace("Sources:", "").strip()
                # Convert "web/reddit/youtube_search/papers" → "web reddit youtube_search papers"
                current_sources = raw.replace("/", " ").replace(",", " ").strip()
            elif line.startswith("Priority:") and current_topic:
                current_priority = line.replace("Priority:", "").strip()

        if current_topic:
            topics.append({
                "topic":    current_topic,
                "sources":  current_sources,
                "priority": current_priority,
            })

        # Sort: HIGH first
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        topics.sort(key=lambda t: priority_order.get(t["priority"], 1))
        return topics[:MAX_TOPICS_PER_REPORT]

    except Exception as e:
        return []


def _research_topic(topic: str, sources: str) -> bool:
    """Run jester.py on a topic. Optimizer runs automatically inside jester.py."""
    # Enhance query with learned boosts before running
    sys.path.insert(0, str(JESTER_DIR))
    try:
        from optimizer import enhance_query, get_best_sources
        topic   = enhance_query(topic)
        src_list = get_best_sources(sources.split())
        sources = " ".join(src_list)
    except Exception:
        pass

    cmd = [PYTHON, JESTER_PY, topic] + sources.split()
    try:
        result = subprocess.run(
            cmd, cwd=str(JESTER_DIR),
            capture_output=True, text=True, timeout=240,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def run():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log = [f"\n{'='*60}", f"SELF-FEED RUN: {timestamp}", f"{'='*60}"]

    state = _load_state()
    reports = _get_unprocessed_reports(state)

    if not reports:
        log.append("No new reports to process. Knowledge base is current.")
        _write_log(log)
        return

    log.append(f"Processing {len(reports)} report(s) → extracting topics...")

    all_topics: list[dict] = []
    for report in reports:
        log.append(f"\n>> Extracting from: {report.name}")
        topics = _extract_topics_from_report(report)
        log.append(f"   Found {len(topics)} follow-up topic(s)")
        for t in topics:
            log.append(f"   [{t['priority']}] {t['topic']}")
        all_topics.extend(topics)
        state["processed"].append(report.name)

    # Prioritize: HIGH first, cap at MAX_RESEARCH_RUNS
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_topics.sort(key=lambda t: priority_order.get(t["priority"], 1))
    to_research = all_topics[:MAX_RESEARCH_RUNS]

    log.append(f"\nResearching {len(to_research)} topic(s)...")

    runs_done = 0
    for t in to_research:
        log.append(f"\n>> {t['topic']} [{t['priority']}]")
        ok = _research_topic(t["topic"], t["sources"])
        status = "OK" if ok else "FAILED"
        log.append(f"   {status}")
        runs_done += 1

    state["total_runs"] = state.get("total_runs", 0) + runs_done
    _save_state(state)

    log.append(f"\nDone. {runs_done} new research runs. "
               f"Total all-time: {state['total_runs']}. Memory index rebuilt.")
    _write_log(log)


def _write_log(lines: list):
    text = "\n".join(lines)
    print(text.encode("ascii", errors="replace").decode("ascii"))
    with FEED_LOG.open("a", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    run()
