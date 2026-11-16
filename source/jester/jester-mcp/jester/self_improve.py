"""
Jester Self-Improvement Loop
Runs weekly research on topics that make Jester smarter.
Each run feeds into the memory index automatically.
Schedule: Windows Task Scheduler → weekly, any day.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

from paths import logs_dir
PYTHON      = sys.executable
JESTER_PY   = str(Path(__file__).parent / "jester.py")
LOG_PATH    = logs_dir() / "self_improve.log"

GROWTH_TOPICS = [
    # New sources and APIs Jester could add
    ("new public data APIs research sources scraping 2026",       "--source papers github hn --watch"),
    # Better synthesis: prompt engineering for extraction
    ("best prompt engineering structured information extraction",  "--source papers hn reddit --watch"),
    # Track competitors adding features Jester should absorb
    ("Perplexity Exa Firecrawl new features capabilities 2026",   "--source news hn reddit --watch"),
    # What researchers/analysts actually want from AI tools
    ("AI research tool user complaints feature requests 2026",     "--source reddit quora medium --watch"),
    # New AI models Jester could use instead of Haiku/Sonnet
    ("best AI models for information extraction synthesis 2026",   "--source papers hn reddit --watch"),
]

def run():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_lines = [f"\n{'='*60}", f"SELF-IMPROVE RUN: {timestamp}", f"{'='*60}"]

    for topic, flags in GROWTH_TOPICS:
        cmd = [PYTHON, JESTER_PY, topic] + flags.split()
        log_lines.append(f"\n>> {topic}")
        try:
            result = subprocess.run(
                cmd, cwd=str(JESTER_DIR),
                capture_output=True, text=True, timeout=180,
            )
            # Extract just the quality score line from output
            for line in result.stdout.splitlines():
                if "Score" in line or "Grade" in line or "memory" in line or "CONVICTION" in line:
                    log_lines.append(f"   {line.strip()}")
            if result.returncode != 0:
                log_lines.append(f"   ERROR: {result.stderr[:200]}")
            else:
                log_lines.append(f"   OK")
        except subprocess.TimeoutExpired:
            log_lines.append(f"   TIMEOUT: skipped")
        except Exception as e:
            log_lines.append(f"   FAIL: {e}")

    log_lines.append(f"\nDone. Memory index rebuilt.")
    log_text = "\n".join(log_lines)
    print(log_text)

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(log_text)

if __name__ == "__main__":
    run()
