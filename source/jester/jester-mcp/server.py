"""
Jester Intelligence MCP: VibeDNA MCP Studio
Gives Claude direct access to Jester's multi-source research engine.

Free tools:  research_topic, digest_youtube, digest_playlist, find_niche,
             research_youtube, score_job, query_memory, get_stats, get_budget, get_optimizer
Paid tools:  watch_topic, crawl_url, scan_competitor  (JesterDNA Pro, https://vibedna.ai/store)
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env early so JESTER_LIB / JESTER_HOME from .env files are visible
# before the Jester library import path is resolved. Tries candidate locations
# in order: alongside server.py, monorepo JESTER folder, current working dir.
_HERE = Path(__file__).resolve().parent
for _env_candidate in (
    _HERE / ".env",
    _HERE.parent.parent.parent / "JESTER" / ".env",
    Path.cwd() / ".env",
):
    if _env_candidate.exists():
        load_dotenv(_env_candidate, override=False)

# ── Import Jester core ────────────────────────────────────────────────────────
# Resolve the Jester library directory in this order:
#   1. JESTER_LIB env var (explicit override, set this in your .env for personal installs)
#   2. ./jester subdir alongside server.py (bundled distribution)
#   3. ../../../JESTER (development monorepo layout)
def _resolve_jester_dir() -> Path:
    explicit = os.environ.get("JESTER_LIB")
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / "jester.py").exists():
            return p
    here = Path(__file__).resolve().parent
    bundled = here / "jester"
    if (bundled / "jester.py").exists():
        return bundled
    monorepo = here.parent.parent.parent / "JESTER"
    if (monorepo / "jester.py").exists():
        return monorepo
    raise RuntimeError(
        "Could not locate jester library. Set JESTER_LIB env var to the directory "
        "containing jester.py, or place the jester source as a 'jester' subfolder "
        "next to server.py."
    )

JESTER_DIR = _resolve_jester_dir()
sys.path.insert(0, str(JESTER_DIR))

from memory import build_memory_block, refresh_index, recall, load_index
from metrics import load_all_metrics, score_report, save_metrics
from budget import check_budget, record_spend, get_budget_status, estimate_run_cost, format_cost_table, per_tool_cost_estimates
from modes import run_mode, MODE_PROMPTS
from optimizer import optimize, enhance_query, get_best_sources, get_optimizer_status
from jester import (
    exa_search,
    exa_search_papers,
    exa_search_news,
    free_web_search,
    free_reddit_search,
    free_hn_search,
    free_substack_rss,
    free_papers_search,
    free_news_search,
    free_appstore_search,
    free_twitter_search,
    free_brave_search,
    free_stackoverflow_search,
    free_arxiv_search,
    free_trends_search,
    fetch_github_repos,
    fetch_market_data,
    fetch_youtube_search,
    fetch_wikipedia,
    firecrawl_url,
    get_youtube_transcript,
    fetch_playlist_urls,
    extract_intelligence,
    build_report,
    save_report,
    load_snapshot,
    save_snapshot,
    build_watch_diff,
    whisper_transcribe_url,
    fetch_url_text,
    fetch_pdf_text,
    fetch_github_repo_info,
    fetch_image_to_path,
    extract_video_keyframes,
    SOURCE_DOMAINS,
    ALL_SOURCE_NAMES,
    _is_crypto_topic,
    YOUTUBE_RE,
    slugify,
)
from memory import compost_memory as _compost_memory
from neural import cosine_rerank
from personal_index import add_entries as _idx_add, search as _idx_search, find_similar_to_url as _idx_similar, stats as _idx_stats

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
# gate is bundled into the jester library directory for self-contained distribution
try:
    from gate import is_paid, UPGRADE_MSG
except ImportError:
    from lib.gate import is_paid, UPGRADE_MSG  # monorepo dev fallback

load_dotenv()

CURRENT_YEAR = datetime.now().year
FREE_SOURCES  = ["web", "reddit", "hn"]
ALL_SOURCES   = ALL_SOURCE_NAMES

# Lite mode: for the free hosted version on mcpize.com.
# Mirrors the public vibedna.ai/jester experience: shallow search + manual YouTube digest only,
# no auto-transcript ingestion in deep mode, no watch_topic, no scan_competitor,
# no personal-index growth. Pro buyers (via vibedna.ai) get the full surface.
LITE_MODE = os.environ.get("JESTER_LITE", "").strip() in ("1", "true", "yes", "on")
LITE_UPGRADE_MSG = (
    "This is JesterDNA Lite (free hosted version). "
    "For the full experience (deep mode with auto-transcripts, watch mode, competitor scans, "
    "growing personal index, Firecrawl + Exa BYOK), get the Pro MCP at "
    "https://vibedna.ai/store "
    "(runs locally on your machine)."
)

from paths import cache_dir
CACHE_DIR = cache_dir()
CACHE_TTL_HOURS = 168  # 7 days default. Research is rarely truly stale faster than that
QUICK_LOOKUP_TTL_HOURS = 24  # tighter for quick facts that shift

_EXA_ONLY_SOURCES = {
    "twitter", "producthunt", "substack", "tradingview", "linkedin",
    "podcast", "quora", "medium", "indiehackers", "devto", "news",
    "amazon", "appstore",
}

mcp = FastMCP("jester-intelligence")

# This copy's version. Bump it when packaging; check_for_update compares it against
# what the site currently publishes, so an installed copy can tell it is behind.
VERSION = "1.0.5"
PRODUCT_SLUG = "jester"


@mcp.tool()
def check_for_update() -> str:
    """Is this copy behind the published version?

    Your copy is a folder on your machine, so it stays exactly as it was the day you
    installed it while fixes keep shipping. This asks what is published now and tells
    you whether to update, and how. It sends nothing about you: just a version number
    comes back."""
    import json as _json
    import urllib.request as _url
    try:
        req = _url.Request(
            "https://vibedna.ai/api/mcp/latest?slug=" + PRODUCT_SLUG,
            headers={"Accept": "application/json"},
        )
        with _url.urlopen(req, timeout=15) as r:
            d = _json.loads(r.read() or b"{}")
    except Exception as e:
        return f"could not reach the update check ({type(e).__name__}). Your copy still works; try later."

    latest = str(d.get("version") or "")
    if not latest:
        return "the update service did not report a version. Nothing to do."

    def parts(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)

    if parts(latest) <= parts(VERSION):
        return f"up to date (you have {VERSION}, published is {latest})."

    try:
        from paths import jester_home as _jh
        home = str(_jh())
    except Exception:
        home = "your home folder, under .jester"

    return "\n".join([
        f"UPDATE AVAILABLE: you have {VERSION}, published is {latest}.",
        "",
        "To update, from the same email you got it with:",
        f"  1. Download: https://vibedna.ai/api/download?slug={PRODUCT_SLUG}&license=<your key>",
        "     (your key is in your purchase email, and in your library at vibedna.ai/library)",
        "  2. Unzip over your current folder, keeping your own files:",
        "     your .env with your keys stays as it is.",
        "  3. Close your AI app and give the old Jester background process up to 30",
        "     minutes to exit (it stops on its own after 30 minutes without use), then",
        "     open your AI app again so it loads the new tools.",
        "",
        f"Everything you researched lives outside this folder, in {home}: your saved",
        "reports, memory, caches and spend log. An update never touches them.",
    ])


# ── Daemon-mode dispatch (HTTP-backed) ────────────────────────────────────────
# When run as Claude Code stdio MCP (JESTER_ROLE != "daemon"), every tool call
# is proxied via HTTP to a single persistent daemon (jester-daemon.py on port
# 7843). This eliminates per-tab process bloat: N tabs share one engine.
# When jester-daemon.py imports this module, JESTER_ROLE=daemon is set so tools
# run their original implementations.
#
# IMPORTANT: this does NOT affect JESTER/api_server.py (port 7842) which powers
# the website's live search. That's a separate process / consumer.

import functools as _functools
import inspect as _inspect
import json as _json
import socket as _socket
import subprocess as _subprocess
import time as _time
import sys as _sys
from pathlib import Path as _Path

JESTER_HOST = "127.0.0.1"
JESTER_PORT = 7843
_JESTER_ROLE = os.environ.get("JESTER_ROLE", "client")
_CLIENT_MODE = (_JESTER_ROLE != "daemon")


def _daemon_alive(timeout: float = 0.3) -> bool:
    try:
        with _socket.create_connection((JESTER_HOST, JESTER_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def _spawn_daemon() -> bool:
    """Spawn jester-daemon.py as a detached process. Returns True once /health responds."""
    daemon_path = str(_Path(__file__).parent / "jester-daemon.py")
    kwargs = dict(
        stdin=_subprocess.DEVNULL,
        stdout=_subprocess.DEVNULL,
        stderr=_subprocess.DEVNULL,
        close_fds=True,
    )
    if _sys.platform == "win32":
        # CREATE_NO_WINDOW alone gives the daemon a hidden console that every tool it runs
        # (yt-dlp, ffmpeg) inherits. Adding DETACHED_PROCESS leaves it with no console at all,
        # and then each of those tools pops its own visible window.
        kwargs["creationflags"] = _subprocess.CREATE_NO_WINDOW | _subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        _subprocess.Popen([_sys.executable, daemon_path], **kwargs)
    except Exception as e:
        print(f"[jester-client] spawn daemon failed: {e}", file=_sys.stderr)
        return False
    # Wait up to 30s for daemon to come up (jester takes longer than Hive to import)
    for _ in range(300):
        if _daemon_alive():
            return True
        _time.sleep(0.1)
    return False


def _rpc(tool: str, args: dict):
    """
    Forward a tool call to jester-daemon over HTTP. Auto-respawns daemon if dead.
    Handles 503 (draining) with retry. Raises RuntimeError on persistent failure.
    """
    import urllib.request
    import urllib.error
    body = _json.dumps(args, default=str).encode("utf-8")
    req = urllib.request.Request(
        f"http://{JESTER_HOST}:{JESTER_PORT}/rpc/{tool}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # 5min for slow research tools
                payload = _json.loads(r.read())
                return payload.get("result", payload)
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < 2:
                _time.sleep(0.5 * (attempt + 1))
                continue
            try:
                err = _json.loads(e.read()).get("error", str(e))
            except Exception:
                err = str(e)
            raise RuntimeError(f"jester[{tool}]: {err}")
        except (urllib.error.URLError, ConnectionError, _socket.timeout) as e:
            if attempt < 2:
                _spawn_daemon()
                continue
            raise RuntimeError(f"jester[{tool}]: daemon unreachable: {e}")


def smart_tool(*deco_args, **deco_kwargs):
    """
    Drop-in replacement for @smart_tool(). In client mode, wraps the function so
    each invocation proxies via HTTP to jester-daemon. Preserves signature so
    the MCP tool schema Claude sees is identical to the daemon's.
    """
    base = mcp.tool(*deco_args, **deco_kwargs)

    def wrap(fn):
        if not _CLIENT_MODE:
            return base(fn)
        sig = _inspect.signature(fn)
        tool_name = fn.__name__

        @_functools.wraps(fn)
        def proxy(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            return _rpc(tool_name, dict(bound.arguments))

        return base(proxy)

    return wrap


# Lazy-spawn daemon on import in client mode so the first tool call is instant
if _CLIENT_MODE and not _daemon_alive():
    _spawn_daemon()


# ── Shared helpers ────────────────────────────────────────────────────────────

def _cache_key(query: str, sources: list, depth: str, model: str) -> str:
    import hashlib
    raw = f"{query}|{'_'.join(sorted(sources))}|{depth}|{model}"
    # blake2b for cache key: non-cryptographic, but avoids OWASP MD5 flag
    return hashlib.blake2b(raw.encode(), digest_size=16).hexdigest()

def _cache_get(key: str, ttl_hours: int = CACHE_TTL_HOURS) -> str | None:
    path = CACHE_DIR / f"{key}.txt"
    if not path.exists():
        return None
    age_hours = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    if age_hours > ttl_hours:
        return None
    return path.read_text(encoding="utf-8")

def _cache_set(key: str, result: str) -> None:
    (CACHE_DIR / f"{key}.txt").write_text(result, encoding="utf-8")


# Stash structured per-source results from the most recent _gather_and_extract call,
# keyed by the ORIGINAL inbound query (before enhance_query / year-append mutate it).
# research() reads from this to feed the corroboration / money / patterns pipeline.
_LAST_STRUCTURED: dict[str, dict] = {}


def _structured_to_items(results: dict) -> list[dict]:
    """Flatten per-source results dict into a flat list of finding items
    ready for _ingest_findings_for_topic."""
    import time as _time
    now = _time.time()
    items: list[dict] = []
    for src, pages in (results or {}).items():
        if not isinstance(pages, list):
            continue
        for p in pages:
            if not isinstance(p, dict):
                continue
            content = p.get("content") or p.get("snippet") or ""
            if not (p.get("title") or content):
                continue
            items.append({
                "title": p.get("title", "") or "",
                "url": p.get("url", "") or "",
                "content": content[:2000],
                "source": src,
                "captured_at": now,
            })
    return items


def _gather_and_extract(
    query: str,
    sources: list[str],
    depth: str = "quick",
    model: str = "haiku",
    use_cache: bool = True,
    free: bool = False,
    synthesize: bool = True,
) -> str:
    """When synthesize=False, returns raw aggregated source content with no Claude call ($0).
    When synthesize=True (default for CLI users), runs the full extraction pipeline."""
    _inbound_query = query  # preserved for _LAST_STRUCTURED key
    if use_cache:
        ck = _cache_key(query, sources + ([] if synthesize else ["RAW"]), depth, model)
        cached = _cache_get(ck)
        if cached:
            return f"[CACHED: {CACHE_TTL_HOURS}h]\n\n{cached}"

    is_youtube = bool(YOUTUBE_RE.search(query))

    budget = check_budget(model, sources, depth, is_youtube)
    if not budget["ok"]:
        return f"BUDGET LIMIT REACHED\n\n{budget['reason']}\n\nRun get_budget to see your usage."
    if budget["suggested_model"] != model:
        model = budget["suggested_model"]

    if not is_youtube:
        query   = enhance_query(query)
        sources = get_best_sources(sources)
    combined:  str       = ""
    used:      dict      = {}
    labels:    list[str] = []

    # year auto-append removed 2026-07-25: broke DDG/web/reddit sources for evergreen/forum topics;
    # freshness comes from source recency + recency_days, not from jamming the year into the query string.

    if not _is_crypto_topic(query):
        sources = [s for s in sources if s not in ("market", "tradingview")]

    if is_youtube:
        title, transcript = get_youtube_transcript(query)
        combined += f"=== YOUTUBE TRANSCRIPT: {title} ===\n{transcript}\n\n"
        used["youtube"] = title
        labels.append("youtube")
        base_query = f"{title} {CURRENT_YEAR}"
    else:
        base_query = query

    import concurrent.futures

    # Build a fetch plan: {source_name: callable} for everything in requested sources
    fetch_plan = {}

    if not is_youtube or "web" in sources:
        if free:
            fetch_plan["web"] = lambda q=base_query: free_web_search(q, num_results=10, fetch_content=True)
        else:
            fetch_plan["web"] = lambda q=base_query: exa_search(q, num_results=5, deep=(depth == "deep"))

    # Topic extraction: drop years + stopwords, keep first 2-3 meaningful terms.
    # Specialized APIs (HN/SO/GitHub/Trends) are exact-match heavy and choke on long queries.
    _STOP = {"the","and","for","with","from","that","this","what","best","tools","2024","2025","2026","2027"}
    def _topic(q: str, max_terms: int = 3) -> str:
        no_year = re.sub(r"\b20\d{2}\b", "", q).strip()
        terms = [w for w in re.findall(r"[A-Za-z]+", no_year) if len(w) > 2 and w.lower() not in _STOP]
        return " ".join(terms[:max_terms]) or no_year

    _SOURCE_FNS = {
        "brave":        lambda q: free_brave_search(q, num_results=8),
        "reddit":       lambda q: free_reddit_search(q, num_results=8),
        "hn":           lambda q: free_hn_search(_topic(q, 3), num_results=8),
        "twitter":      lambda q: free_twitter_search(q, num_results=10),
        "stackoverflow":lambda q: free_stackoverflow_search(_topic(q, 3), num_results=6),
        "papers":       lambda q: free_papers_search(q, top_k=4) or ([] if free else exa_search_papers(q, num_results=4)),
        "arxiv":        lambda q: free_arxiv_search(q, num_results=5),
        "github":       lambda q: fetch_github_repos(_topic(q, 2), num_results=5),
        "trends":       lambda q: free_trends_search(_topic(q, 2)),
        "news":         lambda q: free_news_search(q, num_results=6) or ([] if free else exa_search_news(q, num_results=6)),
        "appstore":     lambda q: free_appstore_search(_topic(q, 3), num_results=5),
        "wikipedia":    lambda q: fetch_wikipedia(_topic(q, 4), num_articles=2),
        "youtube_search":lambda q: fetch_youtube_search(_topic(q, 4), num_videos=2 if free else 3, with_transcripts=(depth == "deep")),
    }

    for src in sources:
        if src in _SOURCE_FNS:
            fetch_plan[src] = _SOURCE_FNS[src]
        elif src in SOURCE_DOMAINS and not free:
            domains = SOURCE_DOMAINS.get(src, [])
            if domains:
                fetch_plan[src] = lambda q=base_query, d=domains: exa_search(q, num_results=4, domains=d)

    if "market" in sources and _is_crypto_topic(query):
        fetch_plan["market"] = lambda q=query: [{"title": "Market Data", "url": "", "content": fetch_market_data(q)}]

    # Run all fetches in parallel with per-source timeout + visible failure logging
    import sys as _sys
    PER_SOURCE_TIMEOUT = 25 if depth == "deep" else 12
    results: dict[str, list] = {}
    source_status: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=14) as ex:
        futures = {ex.submit(fn, base_query): src for src, fn in fetch_plan.items()}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=PER_SOURCE_TIMEOUT + 5):
                src = futures[future]
                try:
                    payload = future.result(timeout=1) or []
                    results[src] = payload
                    source_status[src] = f"OK ({len(payload)})" if payload else "empty"
                except Exception as e:
                    results[src] = []
                    source_status[src] = f"ERROR: {type(e).__name__}: {str(e)[:80]}"
        except concurrent.futures.TimeoutError:
            pass
        # Capture sources that didn't complete in the outer window
        for fut, src in futures.items():
            if src not in source_status:
                results[src] = []
                source_status[src] = f"TIMEOUT (>{PER_SOURCE_TIMEOUT}s)"
                fut.cancel()
    # Log to stderr so users can see what died
    print(f"[jester] source status: {source_status}", file=_sys.stderr, flush=True)

    # Stash structured results under the ORIGINAL inbound query so research() can
    # ingest items into the corroboration/money/patterns pipeline without re-fetching.
    try:
        _LAST_STRUCTURED[_inbound_query] = {
            "results": results,
            "source_status": source_status,
        }
        # Bound cache to last ~16 queries to avoid unbounded growth.
        if len(_LAST_STRUCTURED) > 16:
            for k in list(_LAST_STRUCTURED.keys())[:-16]:
                _LAST_STRUCTURED.pop(k, None)
    except Exception:
        pass

    # Assemble combined in a stable source order
    SOURCE_ORDER = [
        "web", "brave", "reddit", "hn", "twitter", "stackoverflow",
        "papers", "arxiv", "github", "trends", "news", "appstore",
        "wikipedia", "youtube_search", "market",
    ] + [s for s in sources if s not in _SOURCE_FNS and s not in ("web", "market")]

    MAX_SOURCE_CHARS = 5500
    for src in SOURCE_ORDER:
        pages = results.get(src)
        if not pages:
            continue
        if src == "github":
            block = "\n".join(f"  {r['title']}: {r['content']}" for r in pages)
            block = block[:MAX_SOURCE_CHARS]
            combined += f"=== GITHUB REPOS ===\n{block}\n\n"
        elif src == "market":
            combined += f"{pages[0]['content'][:MAX_SOURCE_CHARS]}\n\n"
        else:
            label = src.upper()
            src_chars = 0
            for p in pages:
                remaining = MAX_SOURCE_CHARS - src_chars
                if remaining <= 200:
                    break
                content = p["content"]
                header = f"=== {label}: {p['title']} ({p.get('url','')}) ===\n"
                # Truncate content to fit remaining budget instead of skipping the whole chunk
                avail = remaining - len(header) - 2
                if avail < 100:
                    break
                if len(content) > avail:
                    content = content[:avail] + "…"
                chunk = f"{header}{content}\n\n"
                combined += chunk
                src_chars += len(chunk)
        used[src] = pages
        labels.append(src)


    if not combined.strip():
        return "No content gathered. Check your query or sources."

    # Personal memory: opt-in via JESTER_MEMORY=1 env var. Off by default so each user
    # starts with a clean slate (no stranger's research bleeds into theirs).
    from paths import memory_enabled
    if memory_enabled():
        try:
            for src_name, payload in used.items():
                if isinstance(payload, list):
                    _idx_add(payload, source=src_name, query=query)
        except Exception:
            pass

        memory_block = build_memory_block(query)
        if memory_block:
            disclaimer = (
                "⚠️  PERSONAL INDEX: HISTORICAL CONTEXT ONLY\n"
                "This is what Jester found in past research sessions. Niches, tools, and market conditions\n"
                "change daily. Treat this as a starting hypothesis. Verify with the fresh results below.\n\n"
            )
            combined = disclaimer + memory_block + combined

    # Fire-and-forget: feed the knowledge graph in a background thread.
    # Never blocks the response, never crashes if it fails.
    try:
        from digest import digest_async
        digest_async(query, used)
    except Exception:
        pass

    # Stale-topic auto-hint: if Jester has researched this before and it's gone stale,
    # surface a one-liner so the user knows what's likely changed since last time.
    stale_hint = ""
    try:
        import graph as _graph
        m = _graph.topic_mastery(query)
        if m.get("queried") and m.get("stale"):
            stale_hint = (
                f"📡  Refresh signal: you researched this **{m['query_count']}** time(s) before, "
                f"last **{m['days_since_last']:.0f} days ago**. Tools, prices, and adoption stats "
                f"change fast. Treat older facts as suspect.\n\n"
            )
    except Exception:
        pass

    if not synthesize:
        raw_out = (
            f"# Raw Jester Aggregation: {query}\n"
            f"*Sources: {', '.join(labels)}  |  {len(combined):,} chars  |  $0 to your Jester budget*\n"
            f"*Synthesize this in-conversation with your Claude tokens, or re-call with synthesize=True*\n\n"
            f"{stale_hint}{combined}"
        )
        if use_cache:
            _cache_set(_cache_key(query, sources + ['RAW'], depth, model), raw_out)
        return raw_out

    extraction = extract_intelligence(combined, labels, model=model)
    topic = used.get("youtube") or query
    report = build_report(topic, used, extraction)
    save_report(topic, report)
    refresh_index()
    record_spend(model, len(combined), len(extraction), labels, query)

    sd = score_report(extraction)
    optimize(query, extraction, labels, sd.get("quality_score", 50))

    if use_cache:
        _cache_set(_cache_key(query, sources, depth, model), extraction)
    return extraction


def _run_mode_tool(query: str, mode: str, model: str, sources: list[str], synthesize: bool = False) -> str:
    """When synthesize=False (default): return raw aggregated sources + the mode prompt template,
    so Claude can apply Jester's specialized analysis using the user's subscription tokens.
    When synthesize=True: Jester runs the full mode synthesis itself."""
    if not synthesize:
        raw = _gather_and_extract(query, sources, "quick", model, use_cache=False, synthesize=False)
        prompt_template = MODE_PROMPTS.get(mode, "")
        return (
            f"# Jester '{mode}' mode: raw evidence + analysis prompt\n"
            f"*$0 to your Jester budget. Apply the prompt below in-conversation*\n\n"
            f"## RAW EVIDENCE\n\n{raw}\n\n"
            f"---\n\n"
            f"## MODE PROMPT (apply this to the evidence above)\n\n"
            f"{prompt_template}\n\n"
            f"---\n\n"
            f"To have Jester run the synthesis itself instead, re-call with synthesize=True."
        )

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    from jester import MODEL_MAP
    budget = check_budget(model, sources, "quick", False)
    if not budget["ok"]:
        return f"BUDGET LIMIT\n\n{budget['reason']}"
    if budget["suggested_model"] != model:
        model = budget["suggested_model"]
    content  = _gather_and_extract(query, sources, "quick", model, use_cache=False, synthesize=True)
    model_id = MODEL_MAP.get(model, MODEL_MAP["haiku"])
    result   = run_mode(content, mode, model_id, ANTHROPIC_API_KEY)
    record_spend(model, len(content), len(result), sources, query)
    return result


# ── Tools ─────────────────────────────────────────────────────────────────────

@smart_tool()
def jester_status() -> str:
    """[FREE] Show what Jester knows. Returns entity / fact counts, tier distribution,
    DB size, last compaction. Use this to see how your knowledge graph is growing."""
    import graph as _graph
    s = _graph.status()
    lines = [
        f"# Jester Knowledge Graph Status",
        f"",
        f"**DB:** `{s['db_path']}`  ({s['db_size_mb']} MB)",
        f"**Last compaction:** {s['last_compaction']}",
        f"",
        f"## Entities  ({s['entities']:,} total, {s['total_mentions']:,} mentions)",
    ]
    for tier, n in sorted(s["entities_by_tier"].items()):
        lines.append(f"- {tier}: {n:,}")
    lines += [
        f"",
        f"## Facts  ({s['facts']:,} total)",
    ]
    for tier, n in sorted(s["facts_by_tier"].items()):
        lines.append(f"- {tier}: {n:,}")
    lines += [
        f"- stale (in hot but past TTL): {s['facts_stale_in_hot']:,}",
        f"",
        f"## Topics  ({s['topics_seen']:,} unique queries researched)",
    ]
    return "\n".join(lines)


@smart_tool()
def jester_topic_mastery(query: str) -> str:
    """[FREE] Check how well Jester knows a topic. Returns query count, days since last
    research, whether it's gone stale, and how many entities have been built around it."""
    import graph as _graph
    m = _graph.topic_mastery(query)
    if not m.get("queried"):
        return f"# Topic Mastery: '{query}'\n\n{m['message']}.\nRun `research_topic` to start building knowledge here."
    stale_tag = "  ⚠️  STALE: consider refreshing" if m["stale"] else ""
    return (
        f"# Topic Mastery: '{query}'\n\n"
        f"- Queried **{m['query_count']}** times\n"
        f"- First researched: {m['first_researched']}\n"
        f"- Last researched: {m['last_researched']}  ({m['days_since_last']} days ago){stale_tag}\n"
        f"- Sources averaged per run: {m['sources_average']}\n"
        f"- Entities built: {m['entities_built']:,}\n"
    )


@smart_tool()
def jester_recall(name: str, max_facts: int = 30, include_cold: bool = False) -> str:
    """[FREE] Retrieve everything Jester knows about an entity (tool, person, company, etc.).
    Searches by canonical name, alias, or partial match. Returns facts grouped by tier with
    source citations. Use this to query the knowledge graph directly without re-searching."""
    import graph as _graph
    r = _graph.recall_entity(name, max_facts=max_facts, include_cold=include_cold)
    if not r.get("found"):
        return f"# Recall: '{name}'\n\n{r['message']}\n\nTry researching the topic first."
    lines = [
        f"# Knowledge: {r['canonical']}",
        f"",
        f"**Type:** {r['type']}  |  **Tier:** {r['tier']}  |  **Mentions:** {r['mention_count']}",
        f"**First seen:** {r['first_seen']}  |  **Last seen:** {r['last_seen']}",
    ]
    if r["aliases"]:
        lines.append(f"**Aliases:** {', '.join(r['aliases'][:10])}")
    lines += [f"", f"## Facts ({len(r['facts'])})", ""]
    if not r["facts"]:
        lines.append("(no facts recorded yet)")
    for f in r["facts"]:
        stale_tag = " ⚠️ stale" if f["stale"] else ""
        lines.append(f"- **[{f['type']}]** {f['text']}  *(tier:{f['tier']}{stale_tag}, captured:{f['captured']})*")
        for s in f["sources"][:3]:
            lines.append(f"  - source ({s['kind']}): {s['url']}")
    return "\n".join(lines)


@smart_tool()
def jester_connections(topic_a: str, topic_b: str) -> str:
    """[FREE] Find entities that GENUINELY appear in both topics' research history.
    Real intersection (not heuristic). Uses the entity_topics linkage table populated
    on every research run. Run research_topic on both topics first to populate the graph."""
    import graph as _graph
    r = _graph.find_connections(topic_a, topic_b)
    lines = [f"# Connections: '{topic_a}' ↔ '{topic_b}'", ""]
    if not r["topic_a_known"] and not r["topic_b_known"]:
        return f"{lines[0]}\n\nNeither topic has been researched yet. Run `research_topic` on both first."
    if not r["topic_a_known"]:
        return f"{lines[0]}\n\n'{topic_a}' has not been researched yet. Run `research_topic` on it first."
    if not r["topic_b_known"]:
        return f"{lines[0]}\n\n'{topic_b}' has not been researched yet. Run `research_topic` on it first."
    if not r["connections"]:
        return f"{lines[0]}\n\nBoth topics researched, but no entities appear in both. Try researching each more deeply."
    lines.append(f"Found **{len(r['connections'])}** entities bridging both topics:\n")
    for c in r["connections"][:20]:
        lines.append(
            f"- **{c['entity']}** ({c['type']}): "
            f"{c['mentions_in_a']} mention(s) in '{topic_a}', "
            f"{c['mentions_in_b']} mention(s) in '{topic_b}'"
        )
    return "\n".join(lines)


@smart_tool()
def jester_trust_profile() -> str:
    """[FREE] Show which sources have produced the most durable knowledge for you.
    Sources whose facts stay hot/warm have higher trust scores. Use this to see
    which sources Jester's learned to rely on for your queries."""
    import graph as _graph
    profile = _graph.per_source_trust()
    if not profile:
        return "# Source Trust Profile\n\nNo source data yet. Run more queries to build up."
    lines = ["# Source Trust Profile", "", "_Trust = weighted ratio of facts still hot vs decayed._", ""]
    lines.append("| Source | Facts | Hot | Warm | Cold | Trust |")
    lines.append("|---|---|---|---|---|---|")
    sorted_sources = sorted(profile.items(), key=lambda kv: -kv[1]["trust_score"])
    for kind, d in sorted_sources:
        lines.append(f"| {kind} | {d['fact_count']} | {d['hot']} | {d['warm']} | {d['cold']} | {d['trust_score']} |")
    return "\n".join(lines)


@smart_tool()
def jester_compact() -> str:
    """[FREE] Manually trigger graph compaction. Demotes stale facts hot→warm→cold.
    Information is never deleted, just retiered. Compaction also runs automatically
    every 200 new entities/facts."""
    import graph as _graph
    r = _graph.compact_now()
    return (
        f"# Compaction Complete\n\n"
        f"- Facts demoted hot → warm: {r['facts_h2w']}\n"
        f"- Facts demoted warm → cold: {r['facts_w2c']}\n"
        f"- Entities demoted to cold: {r['entities_demoted']}\n\n"
        f"No data lost. Cold-tier facts remain queryable; they're just ranked lower."
    )


@smart_tool()
def research_topic(
    query: str,
    sources: str = "web reddit hn twitter stackoverflow papers arxiv github wikipedia news youtube_search",
    depth: str = "quick",
    model: str = "haiku",
    format: str = "markdown",
    cache: bool = True,
    free: bool = False,
    synthesize: bool = False,
) -> str:
    """[FREE, $0 by default] Aggregate research from multiple sources for any topic.
    Returns raw aggregated source content (titles + URLs + excerpts). Claude synthesizes
    in-conversation using your existing subscription tokens, no double billing.
    Pass synthesize=True for Jester's structured intelligence extraction (~$0.02 to $0.18 depending on model/sources).
    Free defaults: web+Reddit+HN+Twitter+StackOverflow+Papers+arXiv+GitHub+Wikipedia+News+YouTube.
    Opt-in extras: trends (Google rate-limits, flaky), brave (needs BRAVE_API_KEY), appstore.
    Paid adds: Exa deep crawl, paywalled sites, podcasts. sources='all' for everything.
    depth: quick|deep. model: haiku|sonnet|opus. format: markdown|json (json only when synthesize=True)."""
    FREE_SOURCE_SET = {
        "web", "brave", "reddit", "hn", "twitter", "stackoverflow",
        "papers", "arxiv", "github", "wikipedia", "news",
        "appstore", "youtube_search", "trends",
        # brave/searxng: require API key or self-hosted instance, off by default
    }

    if sources.strip().lower() == "all":
        requested = set(ALL_SOURCES)
    else:
        requested = set(sources.lower().split())

    # Lite mode: matches the public web engine, so force quick depth (no auto-transcripts)
    if LITE_MODE and depth == "deep":
        depth = "quick"
        synthesize = False

    if not is_paid():
        requested = requested & FREE_SOURCE_SET
        model = "haiku"
        if not requested:
            requested = FREE_SOURCE_SET

    if free:
        requested = requested & FREE_SOURCE_SET
        model = "haiku"
        if not requested:
            requested = FREE_SOURCE_SET

    src_list = list(requested)
    result   = _gather_and_extract(query, src_list, depth, model, use_cache=cache, free=free, synthesize=synthesize)

    if format == "json":
        import json as _json
        def _extract_section(text, header):
            m = re.search(rf"## {header}\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
            return m.group(1).strip() if m else ""
        def _extract_bullets(text, header):
            section = _extract_section(text, header)
            return [line.lstrip("- ").strip() for line in section.splitlines() if line.strip().startswith("-")]
        return _json.dumps({
            "query":    query,
            "sources":  src_list,
            "tldr":     _extract_section(result, "TL;DR"),
            "insights": _extract_bullets(result, "Key Insights"),
            "actions":  _extract_bullets(result, "Action Steps"),
            "tools":    _extract_bullets(result, "Tools & Platforms"),
            "warnings": _extract_bullets(result, "Red Flags"),
        }, indent=2)

    return result


@smart_tool()
def digest_youtube(url: str, synthesize: bool = False, also_web: bool = False) -> str:
    """[FREE, $0 by default] Extract full transcript from any YouTube video.
    Falls back to local Whisper transcription when no captions exist (still $0).
    By default returns the raw transcript with the title.
    Pass synthesize=True to also run Jester's structured intelligence extraction (~$0.02 Haiku call).
    also_web=True enriches with paid web search (paid mode only). Costs more, requires synthesize=True."""
    if also_web and not is_paid():
        also_web = False

    if not YOUTUBE_RE.search(url):
        return "Invalid YouTube URL. Please pass a youtube.com/watch?v=... or youtu.be/... link."

    title, transcript = get_youtube_transcript(url)

    if not synthesize and not also_web:
        return f"# Transcript: {title}\n{url}\n\n{transcript}"

    combined = f"=== YOUTUBE TRANSCRIPT: {title} ===\n{transcript}\n\n"
    labels   = ["youtube"]
    used     = {"youtube": title}

    if also_web:
        pages = exa_search(f"{title} {CURRENT_YEAR}", num_results=5)
        for p in pages:
            combined += f"=== WEB: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
        used["web"] = pages
        labels.append("web")

    extraction = extract_intelligence(combined, labels, model="haiku")
    report     = build_report(title, used, extraction)
    save_report(title, report)
    sd = score_report(extraction)
    save_metrics(
        topic=title, sources_count=len(labels), char_count=len(combined),
        score_data=sd, model="haiku", depth="quick",
        report_file=slugify(title) + ".md", active_sources=labels,
    )
    refresh_index()
    return extraction


@smart_tool()
def watch_topic(query: str, sources: str = "web reddit hn") -> str:
    """[PAID] Track a topic over time. First call saves baseline snapshot; subsequent calls diff and show exactly what's new, changed, or gone. Run weekly on competitors or trends."""
    if LITE_MODE:
        return LITE_UPGRADE_MSG
    if not is_paid():
        return UPGRADE_MSG

    src_list      = list(set(sources.lower().split()))
    extraction    = _gather_and_extract(query, src_list, "quick", "haiku")
    topic_slug    = slugify(query)
    prev_snapshot = load_snapshot(topic_slug)

    if prev_snapshot:
        diff   = build_watch_diff(prev_snapshot, extraction)
        output = f"{extraction}\n\n{diff}"
    else:
        output = f"Baseline saved for '{query}'. Run again next week to see what changed.\n\n{extraction}"

    save_snapshot(topic_slug, extraction)
    return output


@smart_tool()
def crawl_url(url: str, deep: bool = False, synthesize: bool = False, query: str = "") -> str:
    """[PAID retrieval, synthesis opt-in] Deep crawl any URL: competitor sites, pricing pages, product pages.
    deep=True crawls up to 8 pages. Requires FIRECRAWL_API_KEY (~$0.001/page).
    By default returns raw scraped markdown. Claude synthesizes in-conversation.
    Pass synthesize=True for Jester's structured extraction (+~$0.02 Haiku call)."""
    if not is_paid():
        return UPGRADE_MSG

    pages = firecrawl_url(url, deep=deep)
    if not pages:
        return "Could not crawl URL. Check FIRECRAWL_API_KEY in .env or verify the URL is accessible."

    combined = ""
    for p in pages:
        combined += f"=== FIRECRAWL: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"

    if not synthesize:
        return f"# Raw Crawl: {url}\n*{len(pages)} page(s), Firecrawl spend only, no Claude call*\n\n{combined}"

    return extract_intelligence(combined, ["firecrawl"], model="haiku")


@smart_tool()
def digest_playlist(url: str, max_videos: int = 20) -> str:
    """[FREE] Digest an entire YouTube playlist or newline-separated video URLs. Transcribes each, synthesizes individually, then produces a cross-video intelligence report. Max 20 videos."""
    max_vids = min(max(int(max_videos), 1), 20)

    if "\n" in url.strip():
        urls = [u.strip() for u in url.strip().splitlines() if u.strip()][:max_vids]
    elif "playlist" in url or "list=" in url:
        urls = fetch_playlist_urls(url, max_videos=max_vids)
    elif YOUTUBE_RE.search(url):
        urls = [url]
    else:
        return "Pass a YouTube playlist URL or newline-separated video URLs."

    if not urls:
        return "Could not extract video URLs. Check the playlist is public and yt-dlp is installed."

    summaries: list[str] = []
    failed:    list[str] = []
    for i, u in enumerate(urls, 1):
        try:
            title, transcript = get_youtube_transcript(u)
            combined   = f"=== YOUTUBE TRANSCRIPT: {title} ===\n{transcript}\n\n"
            extraction = extract_intelligence(combined, ["youtube"], model="haiku")
            save_report(title, build_report(title, {"youtube": title}, extraction))
            refresh_index()
            summaries.append(f"[{i}/{len(urls)}] {title}\n{extraction[:400]}…")
        except Exception as e:
            failed.append(f"[{i}] {u}: {e}")

    if not summaries:
        return f"All {len(urls)} videos failed.\n" + "\n".join(failed)

    meta_input = "\n\n".join(f"=== VIDEO {i+1} SUMMARY ===\n{s}" for i, s in enumerate(summaries))
    meta = extract_intelligence(meta_input, ["youtube"], model="haiku")

    lines = [
        f"Digested {len(summaries)}/{len(urls)} videos\n",
        "─" * 60,
        "CROSS-VIDEO SYNTHESIS",
        "─" * 60,
        meta,
    ]
    if failed:
        lines += ["\nFailed:", *failed]
    return "\n".join(lines)


@smart_tool()
def query_memory(query: str, top_k: int = 5) -> str:
    """[FREE] Search Jester's memory index to find what past research already covers. Use before research_topic to avoid duplicate spend."""
    top_k   = min(max(int(top_k), 1), 10)
    matches = recall(query, top_k=top_k, min_overlap=2)
    if not matches:
        return f"No past research found for '{query}'. Run research_topic to start building knowledge."

    lines = [f"Jester memory: '{query}' ({len(matches)} relevant reports found)\n"]
    for i, m in enumerate(matches, 1):
        lines.append("─" * 60)
        lines.append(f"[{i}] {m['filename']}  |  date: {m['date']}  |  relevance: {m['overlap']} keywords")
        if m["highlights"]:
            lines.append(m["highlights"])
    lines.append("─" * 60)
    lines.append("\nRun research_topic to update or deepen any of these topics.")
    return "\n".join(lines)


@smart_tool()
def find_niche(niche: str, synthesize: bool = False, model: str = "sonnet") -> str:
    """[FREE, $0 by default] Niche evaluation: GO/WAIT/AVOID for a digital product, YouTube channel, or SaaS.
    Returns raw evidence + Jester's niche-evaluation prompt. Claude applies the prompt in-conversation
    using your subscription tokens. Pass synthesize=True for Jester to run the analysis itself
    (~$0.11 Sonnet call). Free: 3 sources. Paid: 5 sources incl. medium + news."""
    if not is_paid():
        model = "haiku"
    sources = ["web", "reddit", "hn", "news", "medium"] if is_paid() else ["web", "reddit", "hn"]
    return _run_mode_tool(f"{niche} market opportunity monetization {CURRENT_YEAR}", "niche", model, sources, synthesize=synthesize)


@smart_tool()
def research_youtube(topic: str, synthesize: bool = False, model: str = "sonnet") -> str:
    """[FREE, $0 by default] YouTube content intelligence: what titles work, what gaps exist, hooks, first videos to make.
    Returns raw evidence + Jester's YouTube-intel prompt. Claude applies the prompt in-conversation.
    Pass synthesize=True for Jester to run the analysis itself (~$0.11 Sonnet call)."""
    if not is_paid():
        model = "haiku"
    sources = ["web", "reddit", "hn", "youtube_search", "medium"] if is_paid() else ["web", "reddit", "hn"]
    return _run_mode_tool(f"YouTube {topic} best videos titles trends {CURRENT_YEAR}", "youtube", model, sources, synthesize=synthesize)


@smart_tool()
def score_job(job_title: str, job_description: str, budget: str = "", synthesize: bool = False) -> str:
    """[FREE, $0 by default] Score a freelance job opportunity: BID/SKIP/RESEARCH MORE.
    Default: returns the job + Jester's job-scoring prompt. Claude applies it in-conversation
    using your subscription tokens. Pass synthesize=True for Jester to run it (~$0.015 Haiku call)."""
    query = f"freelance job: {job_title}\n\nDescription: {job_description}\n\nBudget: {budget}"

    if not synthesize:
        prompt_template = MODE_PROMPTS.get("job", "")
        return (
            f"# Job Score: raw evidence + scoring prompt\n"
            f"*$0 to your Jester budget. Apply the prompt below in-conversation*\n\n"
            f"## JOB POSTING\n\n{query}\n\n"
            f"---\n\n## JESTER JOB-SCORING PROMPT\n\n{prompt_template}"
        )

    sources = ["web", "reddit", "hn"]
    bchk = check_budget("haiku", sources, "quick", False)
    if not bchk["ok"]:
        return f"BUDGET LIMIT\n\n{bchk['reason']}"
    from jester import MODEL_MAP
    result = run_mode(query, "job", MODEL_MAP["haiku"], os.getenv("ANTHROPIC_API_KEY", ""))
    record_spend("haiku", len(query), len(result), sources, job_title)
    return result


@smart_tool()
def scan_competitor(target: str, synthesize: bool = False, model: str = "sonnet") -> str:
    """[PAID retrieval, synthesis opt-in] Deep competitor scan: pricing, complaints, positioning gap, verdict.
    Default: returns raw evidence + Jester's competitor-mode prompt. Claude applies it in-conversation.
    Pass synthesize=True for Jester to run the analysis itself (~$0.12 Sonnet call)."""
    if LITE_MODE:
        return LITE_UPGRADE_MSG
    if not is_paid():
        return UPGRADE_MSG
    sources = ["web", "reddit", "hn", "news", "medium", "quora"]
    return _run_mode_tool(f"{target} competitors pricing reviews complaints users {CURRENT_YEAR}", "competitor", model, sources, synthesize=synthesize)


@smart_tool()
def get_optimizer() -> str:
    """[FREE] Show Jester's self-optimization status: source scores, deprioritized sources, discovered domains, and query boost terms learned."""
    return get_optimizer_status()


@smart_tool()
def get_budget() -> str:
    """[FREE] Show Jester's API spend today and this month vs your limits. Check before running expensive research."""
    return get_budget_status()


@smart_tool()
def get_stats() -> str:
    """[FREE] Show Jester's growth stats: total reports, knowledge ingested, quality scores, conviction rates, and top sources."""
    records = load_all_metrics()
    if not records:
        return "No research runs recorded yet. Run research_topic to start building stats."

    total       = len(records)
    scores      = [r.get("quality_score", 0) for r in records]
    avg_sc      = sum(scores) / total if total else 0
    best        = max(records, key=lambda r: r.get("quality_score", 0))
    total_kb    = sum(r.get("char_count", 0) for r in records) / 1024

    conviction_counts = {"HIGH": 0, "MULTI": 0, "SINGLE": 0}
    for r in records:
        sd = r.get("score_data", {})
        conviction_counts["HIGH"]   += sd.get("high_conviction", 0)
        conviction_counts["MULTI"]  += sd.get("multi_source", 0)
        conviction_counts["SINGLE"] += sd.get("single_source", 0)

    source_freq: dict = {}
    for r in records:
        for s in r.get("active_sources", []):
            source_freq[s] = source_freq.get(s, 0) + 1
    top_sources = sorted(source_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    trend = [f"{r.get('quality_score',0):.0f}" for r in reversed(
        sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)[:10]
    )]

    lines = [
        "╔══════════════════════════════════════╗",
        "║      JESTER INTELLIGENCE: STATS      ║",
        "╚══════════════════════════════════════╝",
        "",
        f"  Total research runs : {total}",
        f"  Knowledge ingested  : {total_kb:,.1f} KB",
        f"  Avg quality score   : {avg_sc:.1f}/100",
        "",
        "  Conviction breakdown:",
        f"    [HIGH CONVICTION] : {conviction_counts['HIGH']}",
        f"    [MULTI SOURCE]    : {conviction_counts['MULTI']}",
        f"    [SINGLE SOURCE]   : {conviction_counts['SINGLE']}",
        "",
        "  Top sources used:",
        *[f"    {src:<20} {count} runs" for src, count in top_sources],
        "",
        "  Score trend (last 10 runs):",
        "    " + " → ".join(trend),
        "",
        f"  Best report ever : {best.get('report_file', 'unknown')}",
        f"                     Score {best.get('quality_score', 0):.0f}/100  |  {best.get('timestamp', '')[:10]}",
    ]
    return "\n".join(lines)


@smart_tool()
def quick_lookup(query: str, num_results: int = 3) -> str:
    """[FREE] Sub-2-second fact lookup. Single web hit, no synthesis, 24h cache.
    Use this when Claude needs a current fact without spending on a full research_topic run.
    Returns 3 ranked snippets with URLs. Free, instant, ideal for reflexive use during conversation."""
    num_results = min(max(int(num_results), 1), 5)
    cache_key = f"quick_{_cache_key(query, ['web'], 'quick', 'none')}"
    cached = _cache_get(cache_key, ttl_hours=QUICK_LOOKUP_TTL_HOURS)
    if cached:
        return f"[CACHED: {QUICK_LOOKUP_TTL_HOURS}h]\n\n{cached}"

    # year auto-append removed 2026-07-25: it zeroed DDG/web/reddit results for evergreen and
    # forum queries (nobody tags a "what does an NDE feel like" post with the year). Per the
    # Query Freshness rule, omit the year; freshness comes from source recency, not the query string.

    pages = free_web_search(query, num_results=num_results)
    if not pages:
        return f"No results for '{query}'. Try research_topic for deeper search."

    lines = [f"# Quick Lookup: {query}\n"]
    for i, p in enumerate(pages, 1):
        snippet = (p.get("content", "") or "")[:400].strip()
        lines.append(f"## {i}. {p['title']}\n{p['url']}\n\n{snippet}\n")
    out = "\n".join(lines)
    _cache_set(cache_key, out)
    return out


@smart_tool()
def digest_audio(url: str, max_minutes: int = 30, synthesize: bool = False, model: str = "haiku") -> str:
    """[FREE, $0 by default] Transcribe ANY audio or video URL with local Whisper.
    Works on YouTube without captions, Vimeo, podcast MP3s, Twitch VODs, direct audio URLs.
    By default returns the raw transcript ($0, pure local Whisper, no API call).
    Pass synthesize=True to also run Jester's structured intelligence extraction (~$0.02 Haiku call).
    Default cap 30 minutes; first run downloads ~150MB Whisper model."""
    import os as _os
    _os.environ["JESTER_WHISPER_MAX_SECONDS"] = str(int(max_minutes) * 60)

    try:
        transcript = whisper_transcribe_url(url)
    except Exception as e:
        return f"Audio extraction failed: {e}"

    if not transcript or len(transcript) < 50:
        return "Transcription too short / empty. Audio may be silent, music-only, or download failed."

    if not synthesize:
        return f"# Transcript: {url}\n\n{transcript}"

    bchk = check_budget(model, ["audio"], "quick", False)
    if not bchk["ok"]:
        return f"Transcript captured ({len(transcript)} chars) but budget hit:\n{bchk['reason']}\n\nRaw transcript:\n{transcript[:3000]}"

    combined = f"=== AUDIO TRANSCRIPT: {url} ===\n{transcript}\n\n"
    extraction = extract_intelligence(combined, ["audio"], model=model)
    record_spend(model, len(combined), len(extraction), ["audio"], url)

    save_report(f"audio-{url[-30:]}", build_report(url, {"audio": True}, extraction))
    refresh_index()
    return extraction


@smart_tool()
def compost_memory(days_back: int = 30, max_reports: int = 50, synthesize: bool = False, model: str = "haiku") -> str:
    """[FREE, $0 by default] Re-ingest your past Jester research.
    Default: returns concatenated highlights of all recent reports as raw text. Claude synthesizes
    cross-report patterns in-conversation using your subscription tokens.
    Pass synthesize=True for Jester to run its compost-engine prompt itself (~$0.02 Haiku call,
    saves a KNOWLEDGE_DIGEST report, refreshes memory index)."""
    days_back = min(max(int(days_back), 1), 365)
    max_reports = min(max(int(max_reports), 1), 200)

    if not synthesize:
        from memory import REPORTS_DIR, _extract_highlights
        from datetime import datetime as _dt
        cutoff = _dt.now().timestamp() - (days_back * 86400)
        reports = []
        for path in REPORTS_DIR.glob("*.md"):
            if path.name.startswith("KNOWLEDGE_DIGEST_"):
                continue
            if path.stat().st_mtime < cutoff:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                hi = _extract_highlights(text, max_chars=600)
                if hi:
                    reports.append(f"=== {path.name} ===\n{hi}")
            except Exception:
                continue
        if not reports:
            return f"No reports found in the last {days_back} days."
        return (
            f"# Raw Memory Compost: last {days_back} days, {len(reports)} reports\n"
            f"*$0 to your Jester budget. Synthesize in-conversation with your Claude tokens*\n\n"
            + "\n\n".join(reports)
        )

    bchk = check_budget(model, ["compost"], "quick", False)
    if not bchk["ok"]:
        return f"BUDGET LIMIT\n\n{bchk['reason']}"

    result = _compost_memory(days_back=days_back, max_reports=max_reports, model=model)
    if result["report_count"] == 0:
        return result["synthesis"]

    record_spend(model, 30000, len(result["synthesis"]), ["compost"], f"compost_{days_back}d")
    return (
        f"Composted {result['report_count']} reports from last {days_back} days.\n"
        f"Digest saved to: {result['digest_path']}\n\n"
        f"{result['synthesis']}"
    )


@smart_tool()
def estimate_cost(
    tool: str = "",
    model: str = "haiku",
    sources: str = "web reddit hn",
    depth: str = "quick",
) -> str:
    """[FREE] Get realistic per-call cost estimate for any Jester tool, in 2026 prices.
    Pass tool='' to see the full table for every tool. Pass tool=<name> + model + sources + depth
    for a custom estimate (e.g. estimate_cost('research_topic', 'sonnet', 'web reddit hn news papers', 'deep')).
    Costs based on current Anthropic + Exa + Firecrawl list prices."""
    paid = is_paid()
    if not tool:
        return format_cost_table(paid_mode=paid)

    tool_l = tool.lower().strip()
    rows = per_tool_cost_estimates(paid_mode=paid)
    matches = [r for r in rows if tool_l in r["tool"].lower()]
    if matches and not any(k in tool_l for k in ("research_topic", "crawl", "find_niche", "scan_competitor", "research_youtube")):
        out = [f"Cost estimates for tools matching '{tool}':", ""]
        for r in matches:
            cost_str = "FREE" if r["shown_cost"] == 0 else f"${r['shown_cost']:.4f}"
            out.append(f"  {r['tool']:<48}  {cost_str:>10}  {r['breakdown']}")
        return "\n".join(out)

    src_list = sources.lower().split() if sources else []
    cost = estimate_run_cost(model, src_list, depth, is_youtube=("youtube" in tool_l))
    return (
        f"Estimated cost for one '{tool}' call:\n"
        f"  model:   {model}\n"
        f"  sources: {' '.join(src_list) if src_list else '(none)'}\n"
        f"  depth:   {depth}\n"
        f"  ──────────────────────────────────────\n"
        f"  estimated total: ${cost:.4f}\n\n"
        f"Note: actual cost may differ ±30% based on retrieved content size."
    )


@smart_tool()
def search_amazon(query: str, synthesize: bool = False, model: str = "haiku") -> str:
    """[FREE, $0 by default] Search Amazon for product/book listings via DuckDuckGo site:amazon.com.
    Returns raw search results (titles + URLs + excerpts). Claude synthesizes in-conversation.
    Pass synthesize=True for Jester's structured extraction (~$0.02 Haiku call).
    For deeper Amazon BSR/review/category data, use the bookradar MCP (forthcoming)."""
    site_query = f"{query} site:amazon.com"
    pages = free_web_search(site_query, num_results=8)
    if not pages:
        return f"No Amazon results for '{query}'."

    combined = ""
    for p in pages:
        combined += f"=== AMAZON: {p['title']} ({p['url']}) ===\n{p.get('content', '')}\n\n"

    if not synthesize:
        return f"# Raw Amazon Search: {query}\n*$0 to your Jester budget*\n\n{combined}"

    bchk = check_budget(model, ["amazon"], "quick", False)
    if not bchk["ok"]:
        return f"Amazon results captured but budget hit:\n{bchk['reason']}\n\n{combined[:3000]}"

    extraction = extract_intelligence(combined, ["amazon"], model=model)
    record_spend(model, len(combined), len(extraction), ["amazon"], query)
    return extraction


@smart_tool()
def fetch_url(url: str, max_chars: int = 15000) -> str:
    """[FREE] Fetch any URL and return clean text. Plain HTTP + HTML→text strip.
    No Firecrawl needed for ~80% of pages. Free, fast, no Claude call.
    Use when Claude needs to read a specific article/page during conversation."""
    try:
        text = fetch_url_text(url, max_chars=max_chars)
    except Exception as e:
        return f"Fetch failed: {e}"
    return f"# {url}\n\n{text}"


@smart_tool()
def deep_search(query: str, num_results: int = 20) -> str:
    """[FREE] Larger DDG search: up to 20 raw results with snippets and URLs.
    For when quick_lookup's 3 isn't enough but you don't need full research_topic synthesis.
    Free, no Claude call. Claude synthesizes the results in-conversation."""
    num_results = min(max(int(num_results), 5), 30)
    # year auto-append removed 2026-07-25: it zeroed DDG/web/reddit results for evergreen and
    # forum queries (nobody tags a "what does an NDE feel like" post with the year). Per the
    # Query Freshness rule, omit the year; freshness comes from source recency, not the query string.
    pages = free_web_search(query, num_results=num_results)
    if not pages:
        return f"No results for '{query}'."
    lines = [f"# Deep Search: {query}\n*{len(pages)} results, $0 to your Jester budget*\n"]
    for i, p in enumerate(pages, 1):
        snippet = (p.get("content", "") or "")[:500].strip()
        lines.append(f"## {i}. {p['title']}\n{p['url']}\n\n{snippet}\n")
    return "\n".join(lines)


@smart_tool()
def read_pdf(url_or_path: str, max_chars: int = 30000) -> str:
    """[FREE] Download a PDF (URL) or read a local PDF, extract all text. Free, no Claude call.
    Research papers, datasheets, ebooks, reports. Claude can finally read PDFs cheaply."""
    try:
        text = fetch_pdf_text(url_or_path, max_chars=max_chars)
    except Exception as e:
        return f"PDF read failed: {e}"
    if not text.strip():
        return "PDF appears to be empty or scanned (image-only). Try extract_image_text instead."
    return f"# PDF: {url_or_path}\n\n{text}"


@smart_tool()
def bulk_transcribe(urls: str, max_minutes_each: int = 30) -> str:
    """[FREE] Transcribe a list of video/audio/podcast URLs (newline-separated).
    Returns all transcripts concatenated, raw. Claude synthesizes in-conversation.
    Killer free-tier tool: 'summarize these 8 videos for me' → batch transcripts → free synthesis."""
    import os as _os
    _os.environ["JESTER_WHISPER_MAX_SECONDS"] = str(int(max_minutes_each) * 60)

    url_list = [u.strip() for u in urls.strip().splitlines() if u.strip()]
    if not url_list:
        return "Pass newline-separated URLs (one per line)."

    parts = [f"# Bulk Transcribe: {len(url_list)} sources\n*$0 to your Jester budget*\n"]
    for i, u in enumerate(url_list, 1):
        try:
            if YOUTUBE_RE.search(u):
                title, text = get_youtube_transcript(u)
            else:
                text = whisper_transcribe_url(u)
                title = u
            parts.append(f"\n---\n## [{i}/{len(url_list)}] {title}\n{u}\n\n{text}\n")
        except Exception as e:
            parts.append(f"\n---\n## [{i}/{len(url_list)}] FAILED: {u}\n  {e}\n")
    return "\n".join(parts)


@smart_tool()
def read_github_repo(repo_url: str) -> str:
    """[FREE] Pull README + file tree (top 80) + last 5 commits for any GitHub repo.
    Free GitHub API (60 req/hr unauth). For deeper code search, use grep on a clone instead."""
    try:
        info = fetch_github_repo_info(repo_url)
    except Exception as e:
        return f"GitHub fetch failed: {e}"

    files_block = "\n".join(f"  {f}" for f in info["files"]) if info["files"] else "  (file tree unavailable)"
    commits_block = "\n".join(info["commits"]) if info["commits"] else "  (commit log unavailable)"
    return (
        f"# GitHub: {info['repo']}\n"
        f"{info['url']}\n\n"
        f"**Stars:** {info['stars']:,}  |  **Language:** {info['language']}  |  **Updated:** {info['updated']}\n\n"
        f"**Description:** {info['description']}\n\n"
        f"## Recent Commits\n```\n{commits_block}\n```\n\n"
        f"## File Tree (top 80)\n```\n{files_block}\n```\n\n"
        f"## README\n\n{info['readme']}"
    )


@smart_tool()
def fetch_image(url: str) -> str:
    """[FREE] Download an image from URL (or copy from local path) into Jester's cache.
    Returns the absolute path. Claude can pass that path to its built-in Read tool to see
    the image natively (no separate vision API needed). Free, no Claude call."""
    try:
        path = fetch_image_to_path(url)
    except Exception as e:
        return f"Image fetch failed: {e}"
    size_kb = path.stat().st_size / 1024
    return (
        f"# Image cached: {path.name}\n"
        f"**Source:** {url}\n"
        f"**Local path:** {path}\n"
        f"**Size:** {size_kb:.1f} KB\n\n"
        f"Read this path with your Read tool to see the image natively."
    )


@smart_tool()
def extract_video_frames(url: str, count: int = 10) -> str:
    """[FREE] Download a video and extract N evenly-spaced keyframes via ffmpeg.
    Returns paths to the frames. Claude can Read each one to 'see' the video silently.
    Combine with digest_audio on the same URL for full visual + auditory comprehension.
    Free, local CPU only. Defaults to 10 frames."""
    count = min(max(int(count), 2), 30)
    try:
        frames = extract_video_keyframes(url, count=count)
    except Exception as e:
        return f"Frame extraction failed: {e}"
    if not frames:
        return "No frames extracted."
    lines = [
        f"# Video Frames: {url}\n*{len(frames)} keyframes, $0 to your Jester budget*\n",
        "Read each path with your Read tool to see the frame natively:\n",
    ]
    for i, fp in enumerate(frames, 1):
        lines.append(f"  {i}. {fp}")
    lines.append("\nTip: pair with digest_audio(url) on the same URL for full video comprehension.")
    return "\n".join(lines)


@smart_tool()
def neural_search(query: str, source: str = "web", num_candidates: int = 30, top_k: int = 5) -> str:
    """[FREE] On-the-fly semantic re-ranking: Jester's home-grown Exa.
    Pulls num_candidates raw results from a free source (web/reddit/hn), embeds them with a local
    model, and returns the top_k by semantic similarity to the query (not just keyword match).
    Free, ~3-5s, $0 to your Jester budget. Replaces ~80% of paid Exa calls for queries DDG can surface.
    Source: 'web', 'reddit', or 'hn'."""
    src = source.lower().strip()
    num_candidates = min(max(int(num_candidates), 5), 50)
    top_k = min(max(int(top_k), 1), 15)

    if src == "reddit":
        candidates = free_reddit_search(query, num_results=num_candidates)
    elif src == "hn":
        candidates = free_hn_search(query, num_results=num_candidates)
    else:
        # year auto-append removed 2026-07-25 (zeroed evergreen/forum web results; omit the year)
        candidates = free_web_search(query, num_results=num_candidates)
        src = "web"

    if not candidates:
        return f"No candidates for '{query}' on {src}."

    ranked = cosine_rerank(query, candidates, top_k=top_k)

    # Auto-grow personal index from this run too
    try:
        _idx_add(ranked, source=f"neural_{src}", query=query)
    except Exception:
        pass

    lines = [
        f"# Neural Search: {query}",
        f"*{src} | re-ranked {len(candidates)} → top {len(ranked)} by semantic similarity | $0*\n",
    ]
    for i, r in enumerate(ranked, 1):
        snippet = (r.get("content", "") or "")[:400].strip()
        score = r.get("_neural_score", 0)
        lines.append(f"## {i}. [{score:.3f}] {r.get('title', '(no title)')}\n{r.get('url', '')}\n\n{snippet}\n")
    return "\n".join(lines)


@smart_tool()
def find_similar(query_or_url: str, top_k: int = 5, source: str = "") -> str:
    """[FREE] Search YOUR personal Jester index: the corpus of everything Jester has ever retrieved for you.
    Pass a query (semantic search) or a URL (find pages similar to one already indexed).
    Optional source filter: 'web', 'reddit', 'hn', 'neural_web', etc.
    Free, instant, no Claude call. Cold-start empty; grows automatically with every retrieval call."""
    top_k = min(max(int(top_k), 1), 20)
    src_filter = source.strip() or None

    is_url = query_or_url.startswith("http")
    if is_url:
        results = _idx_similar(query_or_url, top_k=top_k)
    else:
        results = _idx_search(query_or_url, top_k=top_k, source=src_filter)

    if not results:
        return (
            f"No matches in your personal index for '{query_or_url[:80]}'.\n"
            f"Index grows automatically with every research_topic / neural_search call. "
            f"Run those a few times and try again."
        )

    lines = [
        f"# Personal Index Match: {'similar to URL' if is_url else 'semantic search'}",
        f"*{len(results)} hits from your private corpus | $0*\n",
    ]
    from datetime import datetime as _dt
    for i, r in enumerate(results, 1):
        when = _dt.fromtimestamp(r.get("created_at", 0)).strftime("%Y-%m-%d") if r.get("created_at") else "?"
        snippet = (r.get("content", "") or "")[:300].strip()
        lines.append(
            f"## {i}. [{r.get('score', 0):.3f}] {r.get('title', '(no title)')}\n"
            f"{r.get('url', '')}\n"
            f"*indexed: {when} | source: {r.get('source', '?')} | original query: {r.get('query', '?')[:60]}*\n\n"
            f"{snippet}\n"
        )
    return "\n".join(lines)


@smart_tool()
def search_substack(query: str, top_k: int = 5, num_candidates: int = 15) -> str:
    """[FREE] Search Substack newsletters via DDG site:substack.com + neural re-rank.
    Returns top_k semantically relevant posts. Free, no Exa needed.
    Tip: pass a substack URL to fetch_substack_feed instead for the latest 5 posts of a known publication."""
    num_candidates = min(max(int(num_candidates), 5), 30)
    top_k = min(max(int(top_k), 1), 15)
    candidates = free_substack_search(query, num_results=num_candidates)
    if not candidates:
        return f"No Substack results for '{query}'."
    ranked = cosine_rerank(query, candidates, top_k=top_k)
    try:
        _idx_add(ranked, source="substack", query=query)
    except Exception:
        pass
    lines = [f"# Substack Search: {query}\n*re-ranked {len(candidates)} → top {len(ranked)} | $0*\n"]
    for i, r in enumerate(ranked, 1):
        snippet = (r.get("content", "") or "")[:400].strip()
        lines.append(f"## {i}. [{r.get('_neural_score', 0):.3f}] {r.get('title', '')}\n{r.get('url', '')}\n\n{snippet}\n")
    return "\n".join(lines)


@smart_tool()
def fetch_substack_feed(substack_url: str, max_items: int = 5) -> str:
    """[FREE] Fetch the most recent posts from any Substack via its RSS /feed endpoint.
    Pass any substack URL (the publication root, or any post on it). Returns latest N posts raw.
    Better than scraping for known publications. RSS is structured and rate-limit free."""
    max_items = min(max(int(max_items), 1), 20)
    items = free_substack_rss(substack_url, max_items=max_items)
    if not items:
        return f"No RSS items found for {substack_url}. Verify it's a valid Substack URL."
    try:
        _idx_add(items, source="substack_rss", query=substack_url)
    except Exception:
        pass
    lines = [f"# Substack RSS: {substack_url}\n*latest {len(items)} posts | $0*\n"]
    for i, it in enumerate(items, 1):
        lines.append(f"## {i}. {it.get('title', '')}\n{it.get('url', '')}\n\n{it.get('content', '')[:600]}\n")
    return "\n".join(lines)


@smart_tool()
def search_linkedin(query: str, top_k: int = 5, num_candidates: int = 15) -> str:
    """[FREE] Search LinkedIn public content via DDG site:linkedin.com + neural re-rank.
    Limited to public articles, company pages, and LinkedIn Newsletter posts (gated content
    is invisible to all scrapers including Exa). Free, no LinkedIn API needed."""
    num_candidates = min(max(int(num_candidates), 5), 30)
    top_k = min(max(int(top_k), 1), 15)
    candidates = free_linkedin_search(query, num_results=num_candidates)
    if not candidates:
        return f"No LinkedIn results for '{query}'. Try a more specific query."
    ranked = cosine_rerank(query, candidates, top_k=top_k)
    try:
        _idx_add(ranked, source="linkedin", query=query)
    except Exception:
        pass
    lines = [f"# LinkedIn Search: {query}\n*re-ranked {len(candidates)} → top {len(ranked)} | $0*\n"]
    for i, r in enumerate(ranked, 1):
        snippet = (r.get("content", "") or "")[:400].strip()
        lines.append(f"## {i}. [{r.get('_neural_score', 0):.3f}] {r.get('title', '')}\n{r.get('url', '')}\n\n{snippet}\n")
    return "\n".join(lines)


@smart_tool()
def search_papers(query: str, top_k: int = 5, num_candidates: int = 15) -> str:
    """[FREE] Search 200M+ research papers via Semantic Scholar API + neural re-rank.
    Falls back to OpenAlex if rate-limited. Returns title, authors, year, venue, citation count, abstract.
    Free, no API keys needed. Replaces Exa's research-paper category for ~99% of queries."""
    num_candidates = min(max(int(num_candidates), 5), 30)
    top_k = min(max(int(top_k), 1), 15)
    candidates = free_papers_search(query, num_results=num_candidates)
    if not candidates:
        return f"No papers for '{query}'. Try broader terms."
    ranked = cosine_rerank(query, candidates, top_k=top_k)
    try:
        _idx_add(ranked, source="papers", query=query)
    except Exception:
        pass
    lines = [f"# Research Papers: {query}\n*re-ranked {len(candidates)} → top {len(ranked)} | $0*\n"]
    for i, r in enumerate(ranked, 1):
        snippet = (r.get("content", "") or "")[:600].strip()
        lines.append(f"## {i}. [{r.get('_neural_score', 0):.3f}] {r.get('title', '')}\n{r.get('url', '')}\n\n{snippet}\n")
    return "\n".join(lines)


@smart_tool()
def index_stats() -> str:
    """[FREE] Show stats for your personal Jester index: total entries, source breakdown, age, size."""
    s = _idx_stats()
    if s["total"] == 0:
        return (
            "Personal index is empty.\n"
            "It grows automatically with every research_topic / neural_search / paid retrieval call.\n"
            "Once it has entries, use find_similar to search your own corpus semantically."
        )
    from datetime import datetime as _dt
    oldest = _dt.fromtimestamp(s["oldest"]).strftime("%Y-%m-%d") if s["oldest"] else "?"
    newest = _dt.fromtimestamp(s["newest"]).strftime("%Y-%m-%d") if s["newest"] else "?"
    src_lines = "\n".join(f"    {k:<20} {v}" for k, v in s["sources"].items())
    return (
        f"# Personal Index Stats\n\n"
        f"  Total entries : {s['total']:,}\n"
        f"  DB size       : {s['db_size_kb']:.1f} KB\n"
        f"  Oldest entry  : {oldest}\n"
        f"  Newest entry  : {newest}\n\n"
        f"  Source breakdown:\n{src_lines}\n\n"
        f"  DB path: {s['db_path']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# UPGRADE PACK: Strategic intelligence layer
# ─────────────────────────────────────────────────────────────────────────────
from creator_trust import (
    flag_creator_finding as _flag_creator,
    creator_trust_score as _creator_score,
    creator_trust_for_topic as _creators_for_topic,
    record_creator_observation as _record_creator,
    extract_creator_id as _extract_creator_id,
)
from corroborate import (
    add_findings as _add_findings,
    cluster_findings as _cluster_findings,
)
from bs_filter import filter_findings as _bs_filter, score as _bs_score
from money_flow import (
    ingest as _money_ingest,
    extract_money_claims as _money_extract,
    money_flow_summary as _money_summary,
)
from patterns import synthesize_patterns as _synthesize_patterns
from trends import score_velocity as _score_velocity, velocity_label as _velocity_label
from contradictions import detect as _detect_contradictions, format_for_report as _fmt_contradictions
from entity_graph import (
    ingest as _entity_ingest,
    top_entities as _top_entities,
    top_edges as _top_edges,
    entity_stats as _entity_stats,
    format_for_report as _fmt_entities,
)
from state_snapshots import (
    snapshot_state as _snapshot_state,
    checkpoint_diff as _checkpoint_diff,
    schedule_weekly_snapshot as _schedule_snapshot,
    list_schedule as _list_schedule,
)
import sources as _sources


def _ingest_findings_for_topic(topic: str, items: list[dict], source: str = "", relevance_threshold: float = 0.18) -> dict:
    """Shared pipeline: relevance filter, tag creator IDs, BS filter, push to findings + money + per-creator obs."""
    import relevance as _relevance
    enriched = []
    for it in items:
        if not it.get("creator_id"):
            it["creator_id"] = _extract_creator_id(it.get("url", ""), it.get("title", ""))
        enriched.append(it)
    rel_kept, rel_dropped = _relevance.filter_findings(topic, enriched, threshold=relevance_threshold)
    bs = _bs_filter(rel_kept)
    kept = bs["kept"]
    _add_findings(topic, kept, source=source)
    _money_ingest(kept, topic=topic)
    _entity_ingest(kept, topic=topic)
    for it in kept:
        if it.get("creator_id"):
            _record_creator(it["creator_id"], topic, signal="seen", delta=0.0)
    return {
        "ingested": len(kept),
        "relevance_dropped": len(rel_dropped),
        "bs_flagged": len(bs["flagged"]),
        "stats": bs["stats"],
    }


# ── 1. Creator/channel trust graph ───────────────────────────────────────────
@smart_tool()
def creator_trust_for_topic(topic: str, limit: int = 20, min_samples: int = 1) -> dict:
    """[FREE] Ranked creators (YT/Twitter/podcast/substack) for a topic by per-topic trust.
    Trust is per-(creator, topic). The same creator can be gold on X, trash on Y."""
    return {"topic": topic, "creators": _creators_for_topic(topic, limit=limit, min_samples=min_samples)}


@smart_tool()
def flag_creator_finding(creator_id: str, topic: str, valuable: bool, note: str = "") -> dict:
    """[FREE] Explicit feedback on a creator for a topic. valuable=True bumps score +0.10, False drops -0.15.
    creator_id format: 'yt:<handle>' | 'x:<handle>' | 'reddit:<user>' | 'substack:<sub>' | 'podcast:<host>'."""
    return _flag_creator(creator_id, topic, valuable, note=note)


@smart_tool()
def creator_score(creator_id: str, topic: str) -> dict:
    """[FREE] Look up trust score for a single (creator, topic) pair."""
    return _creator_score(creator_id, topic)


# ── 2. Cross-source corroboration ────────────────────────────────────────────
@smart_tool()
def cluster_findings(topic: str, similarity: float = 0.25, limit: int = 200) -> dict:
    """[FREE] Cluster recent findings for topic by content similarity. Returns ideas with
    corroborating_sources, n_creators, n_findings, weighted by source + creator diversity."""
    return {"topic": topic, "clusters": _cluster_findings(topic, similarity=similarity, limit=limit)}


# ── 2b. Top-N "5 things you should know" output (zero LLM cost) ──────────────
@smart_tool()
def top_findings(topic: str, n: int = 5, money_min_specificity: int = 60) -> dict:
    """[FREE] Compact "what you actually need to know about <topic>" output.
    Ranks clusters by corroboration breadth * creator trust * recency.
    Surfaces verified money claims, top creators, and one outlier.
    Returns structured (top_findings, money_verified, surprising_outlier, top_creators)
    so callers can present without further LLM synthesis.
    """
    import time as _time
    clusters = _cluster_findings(topic, limit=200) or []
    now = _time.time()

    def _score(cl: dict) -> float:
        n_s = max(1, int(cl.get("n_sources", 1)))
        n_c = max(1, int(cl.get("n_creators", 1)))
        n_f = max(1, int(cl.get("n_findings", 1)))
        members = cl.get("members", [])
        recencies = [m.get("captured_at", 0) for m in members if m.get("captured_at")]
        last_seen = max(recencies) if recencies else 0
        age_days = max(1.0, (now - last_seen) / 86400) if last_seen else 365.0
        return (n_s * 2.0 + n_c * 1.5 + n_f) / (age_days ** 0.5)

    ranked = sorted(clusters, key=_score, reverse=True)
    top = ranked[:n]
    # Outlier = high score but n_sources == 1 (unique perspective, single source)
    outlier = None
    for cl in ranked[n:]:
        if cl.get("n_sources", 1) == 1 and _score(cl) > 1.5:
            outlier = cl
            break

    money_claims = _money_extract(topic=topic, min_specificity=money_min_specificity) or []
    if isinstance(money_claims, dict):
        money_claims = money_claims.get("claims", [])

    creators = _creators_for_topic(topic, limit=5) or []

    return {
        "topic": topic,
        "top_findings": [
            {
                "idea": cl.get("idea", "")[:240],
                "n_sources": cl.get("n_sources", 1),
                "n_creators": cl.get("n_creators", 1),
                "n_findings": cl.get("n_findings", 1),
                "sample_url": cl.get("sample_url", ""),
                "corroborating_sources": cl.get("corroborating_sources", []),
            } for cl in top
        ],
        "surprising_outlier": (
            {
                "idea": outlier.get("idea", "")[:240],
                "sample_url": outlier.get("sample_url", ""),
                "why_outlier": "high signal from a single source, worth verifying",
            } if outlier else None
        ),
        "money_verified": money_claims[:5],
        "top_creators": creators[:5],
        "stats": {
            "total_clusters": len(clusters),
            "shown": len(top),
            "money_claims_total": len(money_claims),
        },
    }


# ── 3. Bullshit detector ─────────────────────────────────────────────────────
@smart_tool()
def bs_stats(topic: str) -> dict:
    """[FREE] Re-score all recent findings for a topic and show how much was filtered + why."""
    clusters = _cluster_findings(topic, limit=500)
    items = []
    for cl in clusters:
        for m in cl.get("members", []):
            items.append({"title": m.get("title", ""), "snippet": "", "url": m.get("url", ""),
                          "source": m.get("source", ""), "creator_id": ""})
    if not items:
        return {"topic": topic, "stats": {"total": 0}, "note": "No findings indexed yet."}
    r = _bs_filter(items)
    return {"topic": topic, "stats": r["stats"], "flagged_samples": r["flagged"][:5]}


@smart_tool()
def bs_score_text(title: str, content: str = "", source: str = "", url: str = "") -> dict:
    """[FREE] Score a single piece of text for bullshit (affiliate/AI-slop/clickbait/etc).
    Returns {score 0-100, flagged bool, reasons}."""
    return _bs_score({"title": title, "content": content, "source": source, "url": url})


# ── 4. Money-flow specificity ────────────────────────────────────────────────
@smart_tool()
def extract_money_claims(topic: str = "", min_specificity: int = 70, limit: int = 50) -> dict:
    """[FREE] Structured revenue claims (amount + frequency + method + stack + niche) with
    specificity score 0-100. Filters out 'growing fast' vague claims."""
    return {"topic": topic, "min_specificity": min_specificity,
            "claims": _money_extract(topic=topic, min_specificity=min_specificity, limit=limit)}


@smart_tool()
def money_flow_summary(topic: str = "", top_n: int = 5) -> dict:
    """[FREE] Top N ways people are making money in [topic] right now, grouped by stack + niche + method."""
    return _money_summary(topic=topic, top_n=top_n)


# ── 5. Pattern surfacing ─────────────────────────────────────────────────────
@smart_tool()
def synthesize_patterns(topic: str, max_patterns: int = 5,
                        include_contrarian: bool = True,
                        include_outlier: bool = True) -> dict:
    """[FREE/HAIKU] Compress raw clusters into N patterns everyone converges on,
    contrarian takes, and outlier signals. Uses Haiku when budget allows, rule-based fallback."""
    return _synthesize_patterns(topic, max_patterns=max_patterns,
                                include_contrarian=include_contrarian,
                                include_outlier=include_outlier)


# ── 6. Trend velocity ─────────────────────────────────────────────────────────
@smart_tool()
def trend_velocity(topic: str) -> dict:
    """[FREE] Score whether a topic is RISING, STABLE, or FALLING based on
    timestamp distribution and engagement signals across stored findings.
    Returns direction, velocity ratio, recent vs older count, and peak sources."""
    from corroborate import db_path as _find_db
    import sqlite3, time as _time
    try:
        conn = sqlite3.connect(str(_find_db()))
        rows = conn.execute(
            "SELECT title, snippet, source, captured_at FROM findings WHERE topic=? ORDER BY captured_at DESC LIMIT 300",
            (topic,),
        ).fetchall()
        conn.close()
    except Exception:
        rows = []
    findings = [{"title": r[0], "content": r[1], "source": r[2], "captured_at": r[3]} for r in rows]
    result = _score_velocity(findings)
    result["label"] = _velocity_label(result)
    return result


# ── 7. Contradiction detection ────────────────────────────────────────────────
@smart_tool()
def detect_contradictions(topic: str, limit: int = 100) -> dict:
    """[FREE] Surface opposing claims about a topic across different sources.
    Returns contradiction pairs with confidence scores and source attribution."""
    from corroborate import db_path as _find_db
    import sqlite3
    try:
        conn = sqlite3.connect(str(_find_db()))
        rows = conn.execute(
            "SELECT title, snippet, source, url FROM findings WHERE topic=? ORDER BY captured_at DESC LIMIT ?",
            (topic, limit),
        ).fetchall()
        conn.close()
    except Exception:
        rows = []
    findings = [{"title": r[0], "content": r[1], "source": r[2], "url": r[3]} for r in rows]
    contradictions = _detect_contradictions(findings)
    return {
        "topic": topic,
        "contradictions": contradictions,
        "count": len(contradictions),
        "markdown": _fmt_contradictions(contradictions),
    }


# ── 8. Entity graph ───────────────────────────────────────────────────────────
@smart_tool()
def entity_map(topic: str, limit: int = 20) -> dict:
    """[FREE] Return the top people, companies, products, and tickers appearing
    across all findings for a topic, plus their co-occurrence relationships."""
    ents = _top_entities(topic, limit=limit)
    edges = _top_edges(topic, limit=15)
    stats = _entity_stats()
    return {
        "topic": topic,
        "entities": ents,
        "edges": edges,
        "stats": stats,
        "markdown": _fmt_entities(topic, limit=limit),
    }



# ── 6. State-of-world snapshots + temporal diff ──────────────────────────────
@smart_tool()
def snapshot_state(topic: str) -> dict:
    """[FREE] Freeze the current state-of-world for a topic into a pack-exportable snapshot.
    Captures clusters, money patterns, top creators."""
    return _snapshot_state(topic)


@smart_tool()
def checkpoint_diff(topic: str, since_date: str) -> dict:
    """[FREE] Temporal diff: what's new, what died, what tools won, what got replaced
    between latest snapshot and the most recent one on/before since_date (YYYY-MM-DD)."""
    return _checkpoint_diff(topic, since_date)


@smart_tool()
def schedule_weekly_snapshot(topic: str, cadence: str = "weekly") -> dict:
    """[FREE] Queue a topic for recurring state snapshots (daily|weekly|monthly).
    [STUB] Stores intent; needs self_feed loop hook to auto-execute."""
    return _schedule_snapshot(topic, cadence=cadence)


@smart_tool()
def list_snapshot_schedule() -> dict:
    """[FREE] List all topics queued for recurring state snapshots."""
    return {"scheduled": _list_schedule()}


# ── 7. Underground source coverage ───────────────────────────────────────────
@smart_tool()
def list_underground_sources() -> dict:
    """[FREE] List underground source connectors and their implementation status."""
    return {"sources": _sources.list_sources()}


@smart_tool()
def fetch_underground(source_name: str, topic: str, max_results: int = 10,
                      deep: bool = False) -> dict:
    """[FREE/PARTIAL] Fetch from an underground source: indiehackers, newsletter_archive,
    podcast_transcripts (live); weibo, zhihu, japan_blogs, discord_public, telegram_public,
    substack_notes ([STUB]: return placeholders until API integration).
    deep=True pulls audio/video transcripts where supported (cost-heavy)."""
    items = _sources.fetch(source_name, topic, max_results=max_results)
    if items and not items[0].get("content", "").startswith("TODO"):
        ingest = _ingest_findings_for_topic(topic, items, source=source_name)
        return {"source": source_name, "topic": topic, "items": items[:max_results],
                "ingest": ingest}
    return {"source": source_name, "topic": topic, "items": items,
            "note": "Connector is a stub. No real results until API wired."}


@smart_tool()
def ingest_findings(topic: str, items: list, source: str = "manual") -> dict:
    """[FREE] Manually push findings into the trust + corroboration + money pipeline.
    Each item: {title, content, url, source, creator_id?}. Runs BS filter + money extract + creator obs."""
    return _ingest_findings_for_topic(topic, items, source=source)


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW MODES DISPATCHER: convenience layer over the strategic-intel tools.
# Modes are purely additive defaults. Every param is overridable via kwargs.
# Raw tools keep working standalone.
# ─────────────────────────────────────────────────────────────────────────────
from modes import (
    get_mode_defaults as _mode_defaults,
    list_workflow_modes as _list_wf_modes,
    classify_intent as _classify_intent,
    suggest_mode_for as _suggest_mode_for,
)
from datetime import datetime as _dt, timedelta as _td


def _research_quick(topic: str, sources: list, max_results: int) -> dict:
    raw = _gather_and_extract(
        query=topic, sources=sources, depth="quick", model="haiku",
        use_cache=True, free=True, synthesize=False,
    )
    return {"branch": "quick", "raw_preview": raw[:8000], "max_results": max_results}


@smart_tool()
def list_modes() -> dict:
    """[FREE] List workflow modes (alpha / quick / deep / research / checkpoint / pattern / auto)
    with default parameters. Every default is overridable via kwargs on `research()`.
    auto = classify intent and pick the best mode automatically."""
    return {"modes": _list_wf_modes()}


@smart_tool()
def suggest_mode(prompt: str) -> dict:
    """[FREE] Recommend a Jester mode for a research prompt WITHOUT executing it.
    Pure keyword classification (zero LLM cost). Returns suggested_mode + reasoning +
    alternatives + no_mode_option. Use this when chatting; use `research(mode='auto')`
    when you want it executed in one shot."""
    return _suggest_mode_for(prompt)


@smart_tool()
def classify_intent(prompt: str, allow_llm: bool = False) -> dict:
    """[FREE/HAIKU] Classify a research prompt into a mode. Keyword-only by default;
    set allow_llm=True to fall back to Haiku when keyword signal is ambiguous (budget-gated)."""
    return _classify_intent(prompt, allow_llm=allow_llm)


@smart_tool()
def research(
    topic: str,
    mode: str = "quick",
    deep: bool | None = None,
    recency_days: int | None = None,
    bs_threshold: float | None = None,
    include_patterns: bool | None = None,
    include_money: bool | None = None,
    include_clusters: bool | None = None,
    include_contrarian: bool | None = None,
    include_outlier: bool | None = None,
    include_papers: bool | None = None,
    include_sources: bool | None = None,
    include_diff: bool | None = None,
    since_days: int | None = None,
    max_results: int | None = None,
    max_patterns: int | None = None,
    sources: list | None = None,
) -> dict:
    """[FREE/HAIKU] Unified research dispatcher.
    mode ∈ {alpha, quick, deep, research, checkpoint, pattern}.
    Mode picks defaults; any kwarg overrides. Modes NEVER hard-block sources or features.
    They only tune defaults + which extractors run. Raw tools (research_topic, cluster_findings,
    extract_money_claims, synthesize_patterns, etc.) keep working standalone."""
    auto_resolution = None
    if mode == "auto":
        cls = _classify_intent(topic, allow_llm=True)
        auto_resolution = cls
        mode = cls["mode"]
    overrides = {k: v for k, v in {
        "deep": deep, "recency_days": recency_days, "bs_threshold": bs_threshold,
        "include_patterns": include_patterns, "include_money": include_money,
        "include_clusters": include_clusters, "include_contrarian": include_contrarian,
        "include_outlier": include_outlier, "include_papers": include_papers,
        "include_sources": include_sources, "include_diff": include_diff,
        "since_days": since_days, "max_results": max_results,
        "max_patterns": max_patterns,
    }.items() if v is not None}
    params = {**_mode_defaults(mode), **overrides}
    src = sources or params.get("sources_hint") or ["web", "reddit", "hn"]
    max_n = params.get("max_results", 20)
    out: dict = {"topic": topic, "mode": mode,
                 "params": {k: v for k, v in params.items() if k != "description"}}
    if auto_resolution is not None:
        out["auto_resolution"] = auto_resolution

    if mode == "checkpoint":
        since = (_dt.utcnow() - _td(days=params.get("since_days", 7))).strftime("%Y-%m-%d")
        diff = _checkpoint_diff(topic, since)
        if diff.get("error") and "No snapshot" in diff["error"]:
            out["fell_through_to"] = "quick"
            out["quick"] = _research_quick(topic, src, max_n)
            snap = _snapshot_state(topic)
            out["first_snapshot_created"] = {
                "snapshot_id": snap["snapshot_id"], "date": snap["snapshot_date"]
            }
        else:
            out["diff"] = diff
        return out

    if mode == "quick":
        out["quick"] = _research_quick(topic, src, max_n)
        out["top_creators"] = _creators_for_topic(topic, limit=max_n)
        return out

    if mode == "pattern":
        # Pattern mode needs findings in the DB to cluster on. If the topic was
        # never ingested, fetch fresh + ingest first so synthesize_patterns has data.
        existing = _cluster_findings(topic, limit=5)
        if not existing:
            raw_p = _gather_and_extract(
                query=topic, sources=src, depth="quick", model="haiku",
                use_cache=True, free=True, synthesize=False,
            )
            stash = _LAST_STRUCTURED.get(topic, {})
            items_p = _structured_to_items(stash.get("results", {}))
            if items_p:
                out["ingest"] = _ingest_findings_for_topic(topic, items_p, source="research")
            out["raw_chars"] = len(raw_p)
        out["patterns"] = _synthesize_patterns(
            topic,
            max_patterns=params.get("max_patterns", 5),
            include_contrarian=params.get("include_contrarian", True),
            include_outlier=params.get("include_outlier", True),
        )
        if params.get("include_clusters"):
            out["clusters"] = _cluster_findings(topic, limit=max_n)
        if params.get("include_sources"):
            out["sources"] = _research_quick(topic, src, max_n)
        return out

    depth = "deep" if params.get("deep") else "quick"
    raw = _gather_and_extract(
        query=topic, sources=src, depth=depth, model="haiku",
        use_cache=True, free=True, synthesize=False,
    )
    out["raw_chars"] = len(raw)
    out["raw_preview"] = raw[:6000]
    out["raw_truncated"] = len(raw) > 6000
    if len(raw) > 6000:
        # Persist full raw so caller can fetch the rest without re-running fetches.
        try:
            from paths import jester_home as _jh
            import time as _t, hashlib as _hl
            _rid = _hl.md5(f"{topic}|{_t.time()}".encode()).hexdigest()[:10]
            _raw_dir = _jh() / "raw_research"
            _raw_dir.mkdir(parents=True, exist_ok=True)
            _raw_path = _raw_dir / f"{_rid}.txt"
            _raw_path.write_text(raw, encoding="utf-8")
            out["raw_full_available_via"] = str(_raw_path)
        except Exception as _e:
            out["raw_full_available_via"] = f"(persist failed: {_e})"

    # Ingest the just-fetched structured items so clusters / money / patterns
    # have data to work with. Without this step the extractors return empty.
    stash = _LAST_STRUCTURED.get(topic, {})
    items = _structured_to_items(stash.get("results", {}))
    if not items:
        # cache hit short-circuited _gather_and_extract. Bypass cache once to populate.
        _ = _gather_and_extract(
            query=topic, sources=src, depth=depth, model="haiku",
            use_cache=False, free=True, synthesize=False,
        )
        stash = _LAST_STRUCTURED.get(topic, {})
        items = _structured_to_items(stash.get("results", {}))
    if items:
        out["ingest"] = _ingest_findings_for_topic(topic, items, source="research")
        out["items_count"] = len(items)
    else:
        out["ingest"] = {"ingested": 0, "flagged": 0, "note": "no structured items available"}

    if params.get("include_clusters"):
        out["clusters"] = _cluster_findings(topic, limit=max_n)
    if params.get("include_money"):
        out["money_flow"] = _money_summary(topic=topic, top_n=5)
        out["money_claims"] = _money_extract(topic=topic, min_specificity=60, limit=20)
    if params.get("include_patterns"):
        out["patterns"] = _synthesize_patterns(
            topic,
            max_patterns=params.get("max_patterns", 5),
            include_contrarian=params.get("include_contrarian", True),
            include_outlier=params.get("include_outlier", True),
        )
    out["top_creators"] = _creators_for_topic(topic, limit=10)
    return out


if __name__ == "__main__":
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_lib"))
        import bulletproof
        bulletproof.protect("jester")
    except Exception as _e:
        print(f"[jester] bulletproof unavailable: {_e}", file=sys.stderr)

    # Pick transport from env. Local installs use stdio (default).
    # Hosted Cloud Run / mcpize uses streamable-http on the PORT env var (canonical /mcp endpoint).
    _transport = os.environ.get("JESTER_TRANSPORT", "stdio").lower()
    if _transport in ("http", "streamable-http", "sse"):
        _port = int(os.environ.get("PORT", "8080"))
        _host = "0.0.0.0"
        _path = os.environ.get("JESTER_MCP_PATH", "/mcp")
        print(f"[jester] starting streamable-http on {_host}:{_port}{_path}", file=sys.stderr)
        mcp.run(transport="streamable-http", host=_host, port=_port, path=_path)
    else:
        mcp.run()
