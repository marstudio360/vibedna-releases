"""
Jester Metrics: quality verifier + growth tracker.
Scores every report, saves stats, surfaces Jester's own improvement over time.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich import box

from paths import metrics_dir
METRICS_DIR = metrics_dir()

console = Console()


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_report(extraction: str) -> dict:
    """Parse extraction text and return quality metrics."""
    high   = len(re.findall(r"\[HIGH CONVICTION\]", extraction))
    multi  = len(re.findall(r"\[MULTI SOURCE\]",    extraction))
    single = len(re.findall(r"\[SINGLE SOURCE\]",   extraction))
    total  = high + multi + single

    # Conviction ratio: weighted (HIGH=3, MULTI=2, SINGLE=1) / max possible
    conviction_ratio = round(
        (high * 3 + multi * 2 + single * 1) / max(1, total * 3) * 100
    )

    # Quality score 0-100
    base   = conviction_ratio
    bonus  = min(15, high * 5)            # up to +15 for high conviction hits
    has_wtb = 1 if "What to Build" in extraction else 0
    penalty = min(20, max(0, single - 5) * 2)  # mild penalty for lots of singles
    score  = min(100, max(0, base + bonus + has_wtb * 5 - penalty))

    grade = "S" if score >= 90 else "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

    return {
        "high_conviction": high,
        "multi_source":    multi,
        "single_source":   single,
        "total_insights":  total,
        "conviction_ratio": conviction_ratio,
        "quality_score":   score,
        "grade":           grade,
        "has_what_to_build": bool(has_wtb),
    }


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_metrics(
    topic: str,
    sources_count: int,
    char_count: int,
    score_data: dict,
    model: str,
    depth: str,
    report_file: str,
    active_sources: list[str],
) -> Path:
    slug = re.sub(r"[^\w]+", "-", topic.lower()).strip("-")[:50]
    path = METRICS_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{slug}.json"
    record = {
        "date":           datetime.now().isoformat(),
        "topic":          topic,
        "sources_count":  sources_count,
        "char_count":     char_count,
        "active_sources": active_sources,
        "model":          model,
        "depth":          depth,
        "report_file":    report_file,
        **score_data,
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def load_all_metrics() -> list[dict]:
    records = []
    for f in sorted(METRICS_DIR.glob("*.json")):
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return records


# ── Display: post-run quality panel ──────────────────────────────────────────

def print_quality_panel(score_data: dict, sources_count: int, char_count: int, model: str):
    score = score_data["quality_score"]
    grade = score_data["grade"]
    high  = score_data["high_conviction"]
    multi = score_data["multi_source"]
    sing  = score_data["single_source"]
    conv  = score_data["conviction_ratio"]

    # Score bar
    filled  = int(score / 5)
    empty   = 20 - filled
    bar     = f"[bold green]{'█' * filled}[/][dim]{'░' * empty}[/]"
    grade_color = {
        "S": "bold magenta", "A": "bold green",
        "B": "bold cyan",    "C": "bold yellow", "D": "bold red"
    }.get(grade, "white")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column(justify="left",  style="dim")
    table.add_column(justify="left")

    table.add_row("Score",    f"{bar} [bold]{score}/100[/]  [{grade_color}]Grade {grade}[/]")
    table.add_row("",         "")
    table.add_row("[bold green]HIGH CONVICTION[/]", f"{'█' * min(high, 10)}  {high} insights")
    table.add_row("[bold cyan]MULTI SOURCE[/]",     f"{'█' * min(multi, 10)}  {multi} insights")
    table.add_row("[dim]SINGLE SOURCE[/]",           f"{'░' * min(sing, 10)}  {sing} insights")
    table.add_row("",         "")
    table.add_row("Conviction", f"{conv}%  |  Sources: {sources_count}  |  {char_count:,} chars  |  [{model.upper()}]")
    if score_data["has_what_to_build"]:
        table.add_row("[green]What to Build[/]", "[green]✓ opportunity identified[/]")

    console.print(Panel(table, title="[bold]QUALITY ANALYSIS[/]", border_style="cyan", padding=(0, 1)))


# ── Display: growth stats dashboard ──────────────────────────────────────────

def print_stats():
    records = load_all_metrics()
    if not records:
        console.print("[yellow]No metrics yet. Run some research first.[/]")
        return

    total_chars   = sum(r.get("char_count", 0) for r in records)
    total_sources = sum(r.get("sources_count", 0) for r in records)
    avg_score     = round(sum(r.get("quality_score", 0) for r in records) / len(records))
    avg_conv      = round(sum(r.get("conviction_ratio", 0) for r in records) / len(records))

    # Trend: compare last 5 vs previous 5
    trend_str = ""
    if len(records) >= 10:
        recent  = records[-5:]
        older   = records[-10:-5]
        r_score = sum(r.get("quality_score", 0) for r in recent) / 5
        o_score = sum(r.get("quality_score", 0) for r in older) / 5
        delta   = round(r_score - o_score)
        trend_str = f"[bold green]+{delta}%[/] this week" if delta >= 0 else f"[bold red]{delta}%[/] this week"
    elif len(records) >= 2:
        first_5 = records[:max(1, len(records)//2)]
        last_5  = records[max(1, len(records)//2):]
        f_score = sum(r.get("quality_score", 0) for r in first_5) / len(first_5)
        l_score = sum(r.get("quality_score", 0) for r in last_5) / len(last_5)
        delta   = round(l_score - f_score)
        trend_str = f"[bold green]+{delta}%[/] vs start" if delta >= 0 else f"[bold red]{delta}%[/] vs start"

    # Best report
    best = max(records, key=lambda r: r.get("quality_score", 0))

    # Source frequency
    source_freq: dict[str, int] = {}
    for r in records:
        for s in r.get("active_sources", []):
            source_freq[s] = source_freq.get(s, 0) + 1
    top_sources = sorted(source_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    # Conviction trend (bucketed by run index)
    conv_history = [r.get("conviction_ratio", 0) for r in records]
    first_conv = conv_history[0] if conv_history else 0
    last_conv  = conv_history[-1] if conv_history else 0
    conv_delta = last_conv - first_conv

    # Build table
    main = Table(box=box.ROUNDED, border_style="magenta", padding=(0, 1))
    main.add_column("Metric",  style="bold", width=28)
    main.add_column("Value",   justify="left")

    main.add_row("Total reports",       f"[bold]{len(records)}[/]")
    main.add_row("Knowledge ingested",  f"[bold]{total_chars/1_000_000:.2f}M[/] chars")
    main.add_row("Total sources fired", f"[bold]{total_sources:,}[/]")
    main.add_row("Avg quality score",   f"[bold]{avg_score}/100[/]  {trend_str}")
    main.add_row("Avg conviction ratio",f"[bold]{avg_conv}%[/]  ({first_conv}% → {last_conv}%  Δ{'+' if conv_delta >= 0 else ''}{conv_delta}%)")
    main.add_row("Best report",         f"[bold green]{best['topic'][:40]}[/]  Score: {best['quality_score']}")
    main.add_row("Top sources",         "  ".join(f"[cyan]{s}[/]({n})" for s, n in top_sources))

    # Conviction bar chart (last 10 runs)
    last_10 = conv_history[-10:]
    bar_chart = ""
    for v in last_10:
        blocks = int(v / 10)
        bar_chart += f"{'█' * blocks}{'░' * (10 - blocks)} {v}%\n"

    console.print()
    console.print(Panel(main, title="[bold magenta]JESTER BRAIN: GROWTH STATS[/]", padding=(0, 1)))
    console.print(Panel(
        f"[dim]Conviction trend (last {len(last_10)} runs):[/]\n\n{bar_chart.rstrip()}",
        title="[bold]Conviction History[/]",
        border_style="blue",
        padding=(0, 2)
    ))
    console.print()
