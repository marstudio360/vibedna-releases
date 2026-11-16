"""
Jester Budget Guard: self-regulating API cost control.

Set limits in JESTER/.env:
  JESTER_DAILY_LIMIT=1.00     # hard stop per day  (default $1.00)
  JESTER_MONTHLY_LIMIT=20.00  # hard stop per month (default $20.00)
  JESTER_WARN_PCT=80          # warn + auto-downgrade at this % of limit (default 80)

Cost estimates (per run, approximate):
  haiku  ~$0.02 to $0.05
  sonnet ~$0.08 to $0.20
  opus   ~$0.40 to $0.80
"""

import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

from paths import budget_dir
BUDGET_DIR = budget_dir()

# ── Model cost per 1M tokens (input / output), current Anthropic 2026 list ──
MODEL_COSTS = {
    "haiku":  {"input": 1.00,  "output": 5.00},
    "sonnet": {"input": 3.00,  "output": 15.00},
    "opus":   {"input": 15.00, "output": 75.00},
}

# ── External API costs (2026 list pricing) ───────────────────────────────────
EXA_COST_PER_CALL      = 0.005   # auto / quick mode
EXA_DEEP_COST_PER_CALL = 0.025   # deep mode (5× more results, larger contents)
FIRECRAWL_COST_PER_PAGE = 0.001  # scrape ~$1/1000 pages

# ── Limits from env ───────────────────────────────────────────────────────────
DAILY_LIMIT   = float(os.getenv("JESTER_DAILY_LIMIT",   "1.00"))
MONTHLY_LIMIT = float(os.getenv("JESTER_MONTHLY_LIMIT", "20.00"))
WARN_PCT      = float(os.getenv("JESTER_WARN_PCT",      "80")) / 100


def _budget_file() -> Path:
    return BUDGET_DIR / f"{datetime.now().strftime('%Y-%m')}.json"


def _load() -> dict:
    path = _budget_file()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"month": datetime.now().strftime("%Y-%m"), "days": {}, "total": 0.0}


def _save(data: dict) -> None:
    _budget_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ── Cost estimation ───────────────────────────────────────────────────────────

def estimate_run_cost(
    model: str,
    sources: list[str],
    depth: str = "quick",
    is_youtube: bool = False,
) -> float:
    """Estimate cost of one Jester run before hitting the API."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS["haiku"])

    # Estimate token counts based on typical run
    base_input_tokens  = 25_000 if depth == "deep" else 15_000
    base_output_tokens = 2_000

    # More sources = more combined content = more input tokens
    source_multiplier = 1 + (len(sources) - 1) * 0.15
    if is_youtube:
        base_input_tokens += 8_000  # transcripts are large

    input_tokens  = base_input_tokens * source_multiplier
    output_tokens = base_output_tokens

    claude_cost = (input_tokens / 1_000_000) * costs["input"] + \
                  (output_tokens / 1_000_000) * costs["output"]

    # Exa: ~1 call per source, some heavy sources make 2 calls. Free sources don't hit Exa.
    free_sources = {"reddit", "hn", "web", "wikipedia", "github", "market", "youtube_search", "youtube"}
    paid_exa_sources = [s for s in sources if s not in free_sources]
    per_call_cost = EXA_DEEP_COST_PER_CALL if depth == "deep" else EXA_COST_PER_CALL
    exa_cost = len(paid_exa_sources) * per_call_cost

    return round(claude_cost + exa_cost, 4)


# ── Per-tool realistic cost estimates ────────────────────────────────────────

def per_tool_cost_estimates(paid_mode: bool = True) -> list[dict]:
    """Realistic per-call cost estimates for every Jester tool, with breakdown.
    paid_mode=False shows the free-tier shape (no Exa, no Firecrawl, no Sonnet/Opus)."""
    tools: list[dict] = []

    def add(name: str, free_cost: float, paid_cost: float, breakdown: str):
        tools.append({
            "tool": name,
            "free_cost": free_cost,
            "paid_cost": paid_cost,
            "breakdown": breakdown,
            "shown_cost": paid_cost if paid_mode else free_cost,
        })

    # Free-only tools (no API spend at all)
    add("quick_lookup",       0.000, 0.000, "DDG + cache, no Claude")
    add("deep_search",        0.000, 0.000, "DDG up to 20 results, no Claude")
    add("fetch_url",          0.000, 0.000, "HTTP fetch + HTML→text strip")
    add("read_pdf",           0.000, 0.000, "pypdf extract, no Claude")
    add("bulk_transcribe",    0.000, 0.000, "Whisper local on N URLs")
    add("read_github_repo",   0.000, 0.000, "GitHub API (60 req/hr)")
    add("fetch_image",        0.000, 0.000, "HTTP image download to cache")
    add("extract_video_frames", 0.000, 0.000, "yt-dlp + ffmpeg keyframes")
    add("query_memory",       0.000, 0.000, "local index lookup")
    add("neural_search",       0.000, 0.000, "free retrieval + local re-rank")
    add("find_similar",        0.000, 0.000, "personal vector index search")
    add("index_stats",         0.000, 0.000, "personal index summary")
    add("search_substack",     0.000, 0.000, "DDG site:substack + neural re-rank")
    add("fetch_substack_feed", 0.000, 0.000, "Substack RSS, no auth")
    add("search_linkedin",     0.000, 0.000, "DDG site:linkedin + neural re-rank")
    add("search_papers",       0.000, 0.000, "Semantic Scholar / OpenAlex API")
    add("get_stats",          0.000, 0.000, "local file read")
    add("get_budget",         0.000, 0.000, "local file read")
    add("get_optimizer",      0.000, 0.000, "local file read")

    # Whisper-local tools: transcription is FREE; synthesis is opt-in
    haiku_synth = estimate_run_cost("haiku",  ["audio"], "quick", False)
    add("digest_audio (default: transcript only)",
        0.000, 0.000,
        "Whisper local, no Claude")
    add("digest_audio (synthesize=True)",
        haiku_synth, haiku_synth,
        "Whisper local + 1 Haiku synth")
    add("digest_youtube (default: transcript only)",
        0.000, 0.000,
        "yt captions or Whisper fallback, no Claude")
    add("digest_youtube (synthesize=True)",
        haiku_synth, haiku_synth,
        "transcript + 1 Haiku synth")
    add("digest_playlist (10 videos)",
        haiku_synth * 11, haiku_synth * 11,
        "10 per-video Haiku + 1 meta-synth (always synthesizes)")

    # Compost: default raw, opt-in synth
    add("compost_memory (default: raw highlights)",
        0.000, 0.000, "local report read, no Claude")
    add("compost_memory (synthesize=True)",
        0.020, 0.020, "local read + 1 Haiku synth")

    # Search-amazon
    add("search_amazon (default: raw)",
        0.000, 0.000, "DDG site:amazon.com, no Claude")
    add("search_amazon (synthesize=True)",
        haiku_synth, haiku_synth, "DDG + 1 Haiku synth")

    # research_topic varies by sources/depth/model
    rt_free  = estimate_run_cost("haiku",  ["web", "reddit", "hn"], "quick", False)
    rt_paid_h = estimate_run_cost("haiku",  ["web", "reddit", "hn", "news", "papers", "medium", "indiehackers"], "quick", False)
    rt_paid_s = estimate_run_cost("sonnet", ["web", "reddit", "hn", "news", "papers", "medium", "indiehackers"], "quick", False)
    rt_paid_o = estimate_run_cost("opus",   ["web", "reddit", "hn", "news", "papers", "medium", "indiehackers", "linkedin", "twitter", "substack", "quora", "podcast", "amazon"], "deep", False)

    # Free retrieval-only (default behavior: Claude synthesizes in-chat)
    add("research_topic (default: raw, free 3 srcs)",
        0.000, 0.000, "DDG+Reddit+HN raw, no Claude call")
    add("research_topic (default: raw, paid 7 srcs)",
        0.000, round(rt_paid_h - haiku_synth, 4), "Exa-only spend, no Claude call")
    add("research_topic (default: raw, paid 13 srcs deep)",
        0.000, round(rt_paid_o - estimate_run_cost('opus', ['audio'], 'quick'), 4), "13 Exa deep srcs, no Claude")

    # Synth-on (CLI users / explicit ask)
    add("research_topic (synth=True, free 3 srcs, haiku)",  rt_free,   rt_free,    "DDG+Reddit+HN + 1 Haiku synth")
    add("research_topic (synth=True, paid 7 srcs, sonnet)", rt_free,   rt_paid_s,  "+4 Exa srcs + 1 Sonnet synth")
    add("research_topic (synth=True, all 13, opus, deep)",  rt_free,   rt_paid_o,  "13 Exa deep + 1 Opus synth")

    # Specialized modes, default raw
    add("find_niche (default: raw + prompt)",
        0.000, round(estimate_run_cost("haiku", ["web","reddit","hn","news","medium"], "quick") - haiku_synth, 4),
        "5 Exa srcs raw + niche prompt template")
    add("find_niche (synthesize=True, sonnet)",
        rt_free,
        estimate_run_cost("sonnet", ["web", "reddit", "hn", "news", "medium"], "quick"),
        "5 Exa + Sonnet niche-mode synth")
    add("research_youtube (default: raw + prompt)",
        0.000, round(estimate_run_cost("haiku", ["web","reddit","hn","youtube_search","medium"], "quick") - haiku_synth, 4),
        "5 srcs raw + youtube prompt template")
    add("scan_competitor (default: raw + prompt)",
        0.000, round(estimate_run_cost("haiku", ["web","reddit","hn","news","medium","quora"], "quick") - haiku_synth, 4),
        "6 Exa srcs raw + competitor prompt")
    add("scan_competitor (synthesize=True, sonnet)",
        rt_free,
        estimate_run_cost("sonnet", ["web", "reddit", "hn", "news", "medium", "quora"], "quick"),
        "6 Exa + Sonnet competitor synth")

    # Crawl (Firecrawl)
    add("crawl_url (default: raw)",
        0.020,
        round(FIRECRAWL_COST_PER_PAGE, 4),
        "1 Firecrawl page, no Claude")
    add("crawl_url (deep, 8 pages, default raw)",
        0.020,
        round(FIRECRAWL_COST_PER_PAGE * 8, 4),
        "8 Firecrawl pages, no Claude")
    add("crawl_url (synth=True, 1 page)",
        0.020,
        round(FIRECRAWL_COST_PER_PAGE + haiku_synth, 4),
        "Firecrawl + 1 Haiku synth")

    # Watch: same as research_topic
    add("watch_topic",
        rt_free, rt_paid_h,
        "research_topic synth + diff vs snapshot")

    # Job mode, default raw
    add("score_job (default: raw + prompt)",
        0.000, 0.000, "no retrieval, returns prompt template")
    add("score_job (synthesize=True)",
        0.015, 0.015, "1 Haiku call")

    return tools


def format_cost_table(paid_mode: bool = True) -> str:
    """Pretty-print the per-tool cost table."""
    rows = per_tool_cost_estimates(paid_mode=paid_mode)
    mode = "PAID" if paid_mode else "FREE"
    lines = [
        f"  Per-tool {mode}-mode cost estimates (true 2026 prices):",
        f"  {'tool':<48}  {'cost':>10}  notes",
        f"  {'─'*48}  {'─'*10}  {'─'*30}",
    ]
    for r in rows:
        cost = r["shown_cost"]
        cost_str = "FREE" if cost == 0 else f"${cost:.4f}"
        lines.append(f"  {r['tool']:<48}  {cost_str:>10}  {r['breakdown']}")
    return "\n".join(lines)


# ── Spend tracking ────────────────────────────────────────────────────────────

def record_spend(
    model: str,
    input_chars: int,
    output_chars: int,
    sources: list[str],
    query: str = "",
) -> float:
    """Record actual spend after a run. Returns amount recorded."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS["haiku"])
    input_tokens  = input_chars  / 4  # ~4 chars per token
    output_tokens = output_chars / 4

    claude_cost = (input_tokens  / 1_000_000) * costs["input"] + \
                  (output_tokens / 1_000_000) * costs["output"]

    exa_calls = len([s for s in sources if s not in ("youtube", "wikipedia")])
    exa_cost  = exa_calls * EXA_COST_PER_CALL

    total = round(claude_cost + exa_cost, 4)

    data = _load()
    today = _today()
    day_data = data["days"].get(today, {"spend": 0.0, "runs": 0})
    day_data["spend"] = round(day_data["spend"] + total, 4)
    day_data["runs"]  = day_data["runs"] + 1
    data["days"][today] = day_data
    data["total"] = round(data["total"] + total, 4)
    _save(data)

    return total


# ── Budget check ──────────────────────────────────────────────────────────────

def check_budget(
    model: str,
    sources: list[str],
    depth: str = "quick",
    is_youtube: bool = False,
) -> dict:
    """
    Check if this run is safe to proceed.
    Returns {ok, reason, suggested_model, day_spend, month_spend, estimated_cost}
    """
    data       = _load()
    today      = _today()
    day_spend  = data["days"].get(today, {}).get("spend", 0.0)
    month_spend = data.get("total", 0.0)
    estimated  = estimate_run_cost(model, sources, depth, is_youtube)

    result = {
        "ok":             True,
        "reason":         None,
        "suggested_model": model,
        "day_spend":      day_spend,
        "month_spend":    month_spend,
        "estimated_cost": estimated,
        "day_limit":      DAILY_LIMIT,
        "month_limit":    MONTHLY_LIMIT,
    }

    # Hard stop: over limit
    if day_spend + estimated > DAILY_LIMIT:
        result["ok"]     = False
        result["reason"] = (
            f"Daily limit ${DAILY_LIMIT:.2f} would be exceeded "
            f"(spent ${day_spend:.4f}, estimated ${estimated:.4f}). "
            f"Set JESTER_DAILY_LIMIT in .env to raise it."
        )
        return result

    if month_spend + estimated > MONTHLY_LIMIT:
        result["ok"]     = False
        result["reason"] = (
            f"Monthly limit ${MONTHLY_LIMIT:.2f} would be exceeded "
            f"(spent ${month_spend:.4f}, estimated ${estimated:.4f}). "
            f"Set JESTER_MONTHLY_LIMIT in .env to raise it."
        )
        return result

    # Soft warn: near limit, auto-downgrade model
    day_pct   = (day_spend + estimated) / DAILY_LIMIT
    month_pct = (month_spend + estimated) / MONTHLY_LIMIT

    if (day_pct > WARN_PCT or month_pct > WARN_PCT) and model != "haiku":
        result["suggested_model"] = "haiku"
        result["reason"] = (
            f"Near budget limit ({day_pct*100:.0f}% of daily / {month_pct*100:.0f}% of monthly). "
            f"Auto-downgraded to haiku to conserve credits."
        )

    return result


# ── Status summary ────────────────────────────────────────────────────────────

def get_budget_status() -> str:
    data        = _load()
    today       = _today()
    day_spend   = data["days"].get(today, {}).get("spend", 0.0)
    day_runs    = data["days"].get(today, {}).get("runs", 0)
    month_spend = data.get("total", 0.0)
    month       = data.get("month", "unknown")

    day_pct   = (day_spend   / DAILY_LIMIT)   * 100 if DAILY_LIMIT   else 0
    month_pct = (month_spend / MONTHLY_LIMIT) * 100 if MONTHLY_LIMIT else 0

    def bar(pct: float, width: int = 20) -> str:
        filled = int(min(pct / 100, 1.0) * width)
        color  = "█" if pct < 80 else ("▓" if pct < 95 else "░")
        return color * filled + "·" * (width - filled)

    lines = [
        "╔════════════════════════════════════╗",
        "║      JESTER BUDGET STATUS          ║",
        "╚════════════════════════════════════╝",
        "",
        f"  Today ({today})",
        f"    Spent : ${day_spend:.4f} / ${DAILY_LIMIT:.2f}",
        f"    Runs  : {day_runs}",
        f"    [{bar(day_pct)}] {day_pct:.1f}%",
        "",
        f"  This month ({month})",
        f"    Spent : ${month_spend:.4f} / ${MONTHLY_LIMIT:.2f}",
        f"    [{bar(month_pct)}] {month_pct:.1f}%",
        "",
        "  Limits (set in JESTER/.env)",
        f"    JESTER_DAILY_LIMIT   = ${DAILY_LIMIT:.2f}",
        f"    JESTER_MONTHLY_LIMIT = ${MONTHLY_LIMIT:.2f}",
        f"    JESTER_WARN_PCT      = {int(WARN_PCT*100)}%",
        "",
        "",
        format_cost_table(paid_mode=True),
        "",
        "  (Free-mode tools: quick_lookup, query_memory, digest_audio, digest_youtube,",
        "   compost_memory, search_amazon, research_topic w/ web+reddit+hn: all $0 except the synth call)",
    ]

    if day_pct >= 95 or month_pct >= 95:
        lines += ["", "  ⚠  NEAR LIMIT: runs will be blocked or downgraded"]

    return "\n".join(lines)
