"""
Jester -- Knowledge Predator
Devours YouTube, Reddit, Twitter, GitHub, research papers, market data. Outputs pure intelligence.

Usage:
  python jester.py <youtube_url>                          # eat a video
  python jester.py "<topic query>"                        # eat the web
  python jester.py <youtube_url> --also-web               # video + web
  python jester.py "<topic>" --source reddit github       # add extra sources
  python jester.py "<topic>" --source all                 # eat everything
  python jester.py "<topic>" --depth deep                 # deep web research
  python jester.py "<topic>" --watch                      # track changes over time
  python jester.py "<topic>" --model sonnet               # upgrade synthesis model
  python jester.py --help
"""

import os
import re
import sys
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

load_dotenv()

ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
EXA_API_KEY          = os.getenv("EXA_API_KEY")
LISTENNOTES_API_KEY  = os.getenv("LISTENNOTES_API_KEY", "")
FIRECRAWL_API_KEY    = os.getenv("FIRECRAWL_API_KEY", "")

from paths import reports_dir, snapshots_dir, fetch_cache_dir, whisper_model_dir, youtube_debug_log_path
REPORTS_DIR   = reports_dir()
SNAPSHOTS_DIR = snapshots_dir()

MODEL_MAP = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-7",
}

YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
)

CURRENT_YEAR = datetime.now().year

# Source domains for Exa domain-scoped searches
SOURCE_DOMAINS = {
    "reddit":       ["reddit.com"],
    "twitter":      ["twitter.com", "x.com"],
    "hn":           ["news.ycombinator.com"],
    "producthunt":  ["producthunt.com"],
    "substack":     ["substack.com"],
    "tradingview":  ["tradingview.com"],
    "linkedin":     ["linkedin.com"],
    "podcast":      ["open.spotify.com", "podcasts.apple.com", "anchor.fm", "buzzsprout.com", "podchaser.com"],
    "quora":        ["quora.com"],
    "medium":       ["medium.com"],
    "indiehackers": ["indiehackers.com"],
    "devto":        ["dev.to"],
    "news":         [],  # handled via Exa news category, no domain filter needed
    "amazon":       ["amazon.com"],
    "appstore":     ["apps.apple.com", "play.google.com"],
}
# Special sources handled by dedicated functions (not domain-scoped Exa):
# papers, github, market, youtube_search, listenotes, wikipedia, firecrawl
ALL_SOURCE_NAMES = list(SOURCE_DOMAINS.keys()) + [
    "papers", "github", "market", "youtube_search", "listenotes", "wikipedia"
]

CRYPTO_KEYWORDS = {
    "crypto", "bitcoin", "btc", "eth", "ethereum", "defi", "nft", "token",
    "blockchain", "solana", "sol", "trading", "bot", "binance", "coinbase",
    "altcoin", "chart", "candle", "forex", "futures", "options", "exchange",
}

def _is_crypto_topic(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & CRYPTO_KEYWORDS)


# ── YouTube ───────────────────────────────────────────────────────────────────

def get_youtube_transcript(url: str) -> tuple[str, str]:
    """Returns (title, transcript_text)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

    match = YOUTUBE_RE.search(url)
    if not match:
        raise ValueError(f"Not a valid YouTube URL: {url}")
    video_id = match.group(1)

    title = video_id
    try:
        import subprocess, shutil
        ytdlp = shutil.which("yt-dlp") or "yt-dlp"
        result = subprocess.run(
            [ytdlp, "--skip-download", "--print", "title", url],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            title = result.stdout.strip()
    except Exception:
        pass

    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        return title, " ".join(chunk.text for chunk in fetched)
    except (NoTranscriptFound, TranscriptsDisabled, Exception):
        pass

    try:
        for t in api.list(video_id):
            return title, " ".join(chunk.text for chunk in t.fetch())
    except Exception:
        pass

    # No captions available, fall back to local Whisper transcription
    try:
        return title, whisper_transcribe_url(url)
    except Exception as e:
        raise RuntimeError(f"No transcript available for {video_id} (captions missing, Whisper fallback failed: {e})")


# ── Whisper local audio transcription ────────────────────────────────────────

WHISPER_MODEL_DIR = whisper_model_dir()
_WHISPER_MODEL = None  # lazy-loaded singleton


def _get_whisper_model(size: str = "base"):
    """Lazy-load faster-whisper model. First call downloads ~150MB (base) on demand."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        size = os.getenv("JESTER_WHISPER_MODEL", size)
        _WHISPER_MODEL = WhisperModel(
            size,
            device="cpu",
            compute_type="int8",
            download_root=str(WHISPER_MODEL_DIR),
        )
    return _WHISPER_MODEL


def whisper_transcribe_url(url: str, max_seconds: int = 1800) -> str:
    """Download audio from any URL via yt-dlp, transcribe with local Whisper. Returns text.

    Caps at 30 min by default (safety against 3-hour podcasts melting the CPU).
    Override via JESTER_WHISPER_MAX_SECONDS env var.
    """
    import subprocess, tempfile

    max_seconds = int(os.getenv("JESTER_WHISPER_MAX_SECONDS", max_seconds))

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "audio.m4a"
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "--no-playlist",
            "-o", str(audio_path),
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0 or not audio_path.exists():
            raise RuntimeError(f"yt-dlp failed: {result.stderr[-300:]}")

        model = _get_whisper_model()
        segments, _info = model.transcribe(
            str(audio_path),
            language="en",
            vad_filter=True,
            beam_size=1,
        )
        text_parts = []
        elapsed = 0.0
        for seg in segments:
            if seg.end > max_seconds:
                break
            text_parts.append(seg.text)
            elapsed = seg.end
        return " ".join(t.strip() for t in text_parts).strip()


def fetch_playlist_urls(playlist_url: str, max_videos: int = 20) -> list[str]:
    """Extract individual video URLs from a YouTube playlist using yt-dlp."""
    import subprocess, shutil
    ytdlp = shutil.which("yt-dlp") or "yt-dlp"
    try:
        result = subprocess.run(
            [ytdlp, "--flat-playlist", "--print", "url",
             "--playlist-end", str(max_videos), playlist_url],
            capture_output=True, text=True, timeout=30
        )
        urls = [u.strip() for u in result.stdout.strip().splitlines() if u.strip()]
        return urls[:max_videos]
    except Exception:
        return []


# ── Exa Web Search ────────────────────────────────────────────────────────────

def _exa_client():
    from exa_py import Exa
    return Exa(api_key=EXA_API_KEY)


def exa_search(query: str, num_results: int = 5, deep: bool = False,
               domains: list[str] | None = None, no_date_filter: bool = False) -> list[dict]:
    """General Exa search. Uses 'deep' type for deep mode, 'auto' otherwise (neural deprecated Apr 2026).
    no_date_filter=True drops the published-date cutoff, needed for evergreen and forum content
    (most reddit threads on a topic are older than a year, so the cutoff was returning nothing)."""
    exa = _exa_client()
    days_back = 90 if deep else 365
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    kwargs: dict = {
        "num_results": 8 if deep else num_results,
        "type": "deep" if deep else "auto",
        "contents": {"text": {"maxCharacters": 3000 if deep else 2000}},
    }
    if not no_date_filter:
        kwargs["start_published_date"] = cutoff
    if domains:
        kwargs["include_domains"] = domains

    results = exa.search(query, **kwargs)
    pages = []
    for r in results.results:
        pages.append({
            "title": r.title or "Untitled",
            "url": r.url,
            "content": r.text if hasattr(r, "text") and r.text else "",
        })
    return pages


def exa_search_papers(query: str, num_results: int = 5) -> list[dict]:
    """Research papers via Exa category filter."""
    exa = _exa_client()
    results = exa.search(
        query,
        num_results=num_results,
        category="research paper",
        contents={"text": {"maxCharacters": 2000}},
    )
    pages = []
    for r in results.results:
        pages.append({
            "title": r.title or "Untitled",
            "url": r.url,
            "content": r.text if hasattr(r, "text") and r.text else "",
        })
    return pages


def exa_search_news(query: str, num_results: int = 6) -> list[dict]:
    """Recent news articles via Exa news category (last 30 days)."""
    exa = _exa_client()
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = exa.search(
        query,
        num_results=num_results,
        category="news",
        start_published_date=cutoff,
        contents={"text": {"maxCharacters": 2000}},
    )
    pages = []
    for r in results.results:
        pages.append({
            "title": r.title or "Untitled",
            "url": r.url,
            "content": r.text if hasattr(r, "text") and r.text else "",
        })
    return pages


def fetch_youtube_search(query: str, num_videos: int = 3, with_transcripts: bool = False) -> list[dict]:
    """Search YouTube for top videos. Returns titles+descriptions by default (fast, ~5s).
    Pass with_transcripts=True to also fetch transcripts in parallel (slow, ~15-25s)."""
    # Direct HTTP scrape of YouTube search page: ~1s, avoids yt-dlp subprocess slowness in MCP threads
    q = urllib.parse.quote(query)
    req = urllib.request.Request(
        f"https://www.youtube.com/results?search_query={q}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    m = re.search(r"var ytInitialData = ({.*?});</script>", html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    videos: list[dict] = []
    seen: set = set()
    def _walk(obj):
        if len(videos) >= num_videos:
            return
        if isinstance(obj, dict):
            v = obj.get("videoRenderer")
            if v:
                vid_id = v.get("videoId", "")
                if vid_id and vid_id not in seen and len(vid_id) == 11:
                    seen.add(vid_id)
                    title_runs = v.get("title", {}).get("runs", [{}])
                    title = title_runs[0].get("text", "") if title_runs else ""
                    desc_runs = v.get("descriptionSnippet", {}).get("runs", [])
                    desc = "".join(r.get("text", "") for r in desc_runs)
                    views = v.get("viewCountText", {}).get("simpleText", "")
                    videos.append({
                        "title": title,
                        "url": f"https://youtube.com/watch?v={vid_id}",
                        "content": f"Views: {views}\n{desc}",
                        "_vid_id": vid_id,
                    })
            for val in obj.values():
                _walk(val)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
    _walk(data)

    if with_transcripts and videos:
        import concurrent.futures
        def _grab(v):
            try:
                _, transcript = get_youtube_transcript(v["url"])
                if transcript:
                    v["content"] = transcript[:3000]
            except Exception:
                pass
            v.pop("_vid_id", None)
            return v
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(videos))) as ex:
            videos = list(ex.map(_grab, videos))
    else:
        for v in videos:
            v.pop("_vid_id", None)
    return videos


def fetch_listenotes(query: str, num_results: int = 5) -> list[dict]:
    """Podcast episode search via Listen Notes API (requires LISTENNOTES_API_KEY in .env)."""
    if not LISTENNOTES_API_KEY:
        return []
    q = urllib.parse.quote(query)
    url = (
        f"https://listen-api.listennotes.com/api/v2/search"
        f"?q={q}&type=episode&page_size={num_results}&language=English&sort_by_date=0"
    )
    req = urllib.request.Request(url, headers={
        "X-ListenAPI-Key": LISTENNOTES_API_KEY,
        "User-Agent": "Jester-Research/1.0",
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read())
    episodes = []
    for ep in data.get("results", []):
        desc = ep.get("description_original") or ep.get("description") or ""
        episodes.append({
            "title": ep.get("title_original") or ep.get("title") or "Untitled",
            "url": ep.get("listennotes_url") or ep.get("audio") or "",
            "content": desc[:2500],
        })
    return episodes


# ── Wikipedia ────────────────────────────────────────────────────────────────

def fetch_wikipedia(query: str, num_articles: int = 2) -> list[dict]:
    """Background context from Wikipedia: free, no key needed.
    Uses opensearch (page-title autocomplete) for relevance, then fetches extracts.
    Skips fuzzy matches that don't share meaningful terms with the query."""
    # opensearch returns ranked page titles: much better relevance than full-text search
    open_url = (
        f"https://en.wikipedia.org/w/api.php"
        f"?action=opensearch&search={urllib.parse.quote(query)}&limit={num_articles*2}&format=json"
    )
    try:
        req = urllib.request.Request(open_url, headers={"User-Agent": "Jester-Research/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            odata = json.loads(resp.read())
        candidate_titles = odata[1] if len(odata) > 1 else []
    except Exception:
        candidate_titles = []

    # Relevance filter: title must share at least one ≥4-char term with the query
    query_terms = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", query)}
    _STOP = {"with", "from", "this", "that", "tools", "best", "guide", "what", "much", "more"}
    query_terms -= _STOP
    relevant_titles = [
        t for t in candidate_titles
        if any(term in t.lower() for term in query_terms)
    ][:num_articles]

    if not relevant_titles:
        return []

    pages = []
    # Fetch extracts for the relevant page titles
    titles_param = "|".join(urllib.parse.quote(t) for t in relevant_titles)
    extract_url = (
        f"https://en.wikipedia.org/w/api.php"
        f"?action=query&prop=extracts&exintro=true&explaintext=true"
        f"&titles={titles_param}&format=json"
    )
    try:
        req2 = urllib.request.Request(extract_url, headers={"User-Agent": "Jester-Research/1.0"})
        with urllib.request.urlopen(req2, timeout=8) as resp2:
            edata = json.loads(resp2.read())
        for page in edata.get("query", {}).get("pages", {}).values():
            extract = page.get("extract", "")
            title = page.get("title", "")
            if not extract or len(extract) < 100:
                continue
            safe_title = urllib.parse.quote(title.replace(" ", "_"))
            pages.append({
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{safe_title}",
                "content": extract[:3000],
            })
    except Exception:
        pass
    return pages

def _fetch_wikipedia_legacy(query: str, num_articles: int = 2) -> list[dict]:
    """Legacy implementation, kept for reference. Used full-text search which returned fuzzy matches."""
    search_q = urllib.parse.quote(query)
    search_url = (
        f"https://en.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={search_q}&format=json&srlimit={num_articles}"
    )
    req = urllib.request.Request(search_url, headers={"User-Agent": "Jester-Research/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    pages = []
    for item in data.get("query", {}).get("search", [])[:num_articles]:
        page_id = item["pageid"]
        title = item["title"]
        extract_url = (
            f"https://en.wikipedia.org/w/api.php"
            f"?action=query&prop=extracts&exintro=true&explaintext=true"
            f"&pageids={page_id}&format=json"
        )
        req2 = urllib.request.Request(extract_url, headers={"User-Agent": "Jester-Research/1.0"})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            edata = json.loads(resp2.read())
        extract = list(edata["query"]["pages"].values())[0].get("extract", "")
        safe_title = urllib.parse.quote(title.replace(" ", "_"))
        pages.append({
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/{safe_title}",
            "content": extract[:3000],
        })
    return pages


# ── Free Source Fetchers (no API key, no Exa) ────────────────────────────────

def free_reddit_search(query: str, num_results: int = 8) -> list[dict]:
    """Reddit search, free, no auth, no Exa. reddit.com/search.json now 403s unauthenticated
    scrapers, so we reach reddit through the ddgs library (which handles DuckDuckGo's vqd/anti-bot
    that the raw endpoints block) using a site:reddit.com filter."""
    try:
        from ddgs import DDGS
        with DDGS() as ddg:
            raw = list(ddg.text(f"{query} site:reddit.com", max_results=min(num_results * 3, 25)))
    except Exception:
        return []
    posts = []
    for r in raw:
        if len(posts) >= num_results:
            break
        url = r.get("href") or r.get("url") or ""
        if "reddit.com" not in url:
            continue
        posts.append({
            "title":   r.get("title", "") or url,
            "url":     url,
            "content": (r.get("body") or "")[:1500],
        })
    return posts


def free_hn_search(query: str, num_results: int = 8) -> list[dict]:
    """Hacker News search via Algolia API: zero cost, no auth."""
    q = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={num_results}"
    req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        posts = []
        for hit in data.get("hits", [])[:num_results]:
            points      = hit.get("points", 0)
            comments    = hit.get("num_comments", 0)
            story_text  = hit.get("story_text") or ""
            content     = f"Points: {points} | Comments: {comments}\n{story_text[:1800]}"
            posts.append({
                "title":   hit.get("title", ""),
                "url":     f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "content": content,
            })
        return posts
    except Exception:
        return []


def free_web_search(query: str, num_results: int = 6, fetch_content: bool = False) -> list[dict]:
    """Free web search, no API key, no Exa. Uses the ddgs library, which handles DuckDuckGo's
    vqd/anti-bot protection that our raw lite.duckduckgo.com scrape can no longer get past.
    fetch_content=True auto-fetches full page text for the top results (slower but richer)."""
    # Domains covered by dedicated free fetchers (reddit/hn/etc), skipped here to avoid duplication
    _SKIP_DOMAINS = {
        "reddit.com", "news.ycombinator.com", "substack.com",
        "linkedin.com", "medium.com", "producthunt.com",
        "indiehackers.com", "quora.com", "dev.to", "x.com", "twitter.com",
        "developers.reddit.com", "business.reddit.com",
    }
    try:
        from ddgs import DDGS
        with DDGS() as ddg:
            raw = list(ddg.text(query, max_results=min(num_results * 3, 30)))
    except Exception:
        return []
    pages = []
    for r in raw:
        if len(pages) >= num_results:
            break
        real_url = r.get("href") or r.get("url") or ""
        domain   = urllib.parse.urlparse(real_url).netloc.lstrip("www.")
        if domain in _SKIP_DOMAINS:
            continue
        pages.append({
            "title":   r.get("title", "") or real_url,
            "url":     real_url,
            "content": (r.get("body") or "")[:1500],
        })

    if fetch_content and pages:
        import concurrent.futures
        def _fetch(page):
            try:
                full = fetch_url_text(page["url"], max_chars=4000)
                if full and len(full) > len(page["content"]):
                    page["content"] = full
            except Exception:
                pass
            return page
        top_n = min(3, len(pages))
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            enriched = list(ex.map(_fetch, pages[:top_n]))
        pages = enriched + pages[top_n:]

    return pages


# ── Firecrawl Deep Crawl ──────────────────────────────────────────────────────

def firecrawl_url(url: str, deep: bool = False) -> list[dict]:
    """Scrape or crawl a URL using Firecrawl. Requires FIRECRAWL_API_KEY in .env."""
    if not FIRECRAWL_API_KEY:
        return []
    from firecrawl import FirecrawlApp
    fc = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    if deep:
        result = fc.crawl_url(url, limit=8, scrape_options={"formats": ["markdown"]})
        pages = []
        for page in (result.data or [])[:6]:
            md = getattr(page, "markdown", None) or ""
            meta = getattr(page, "metadata", {}) or {}
            pages.append({
                "title": meta.get("title") or url,
                "url":   getattr(page, "url", url),
                "content": md[:3000],
            })
        return pages
    else:
        result = fc.scrape_url(url, formats=["markdown"])
        md = getattr(result, "markdown", None) or ""
        meta = getattr(result, "metadata", {}) or {}
        return [{
            "title":   meta.get("title") or url,
            "url":     url,
            "content": md[:5000],
        }]


# ── Universal free retrieval helpers (return raw, no Claude calls) ───────────

JESTER_CACHE_DIR = fetch_cache_dir()


def fetch_url_text(url: str, max_chars: int = 15000) -> str:
    """Full article extraction via Jina Reader (free, no key) with Trafilatura fallback."""
    # 1. Try Jina Reader: returns clean markdown of any webpage, no API key needed
    try:
        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(jina_url, headers={
            "User-Agent": "Mozilla/5.0 (Jester-Research/2.0)",
            "Accept": "text/plain, text/markdown, */*",
            "X-Return-Format": "markdown",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            text = resp.read().decode("utf-8", errors="ignore").strip()
        if text and len(text) > 200:
            return text[:max_chars]
    except Exception:
        pass

    # 2. Trafilatura fallback: best local article extractor, strips nav/ads/footers
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
            if text and len(text) > 200:
                return text[:max_chars]
    except Exception:
        pass

    # 3. Last resort: crude HTML strip (original behavior)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Jester-Research/2.0)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style\b[^>]*>.*?</style>",   " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


def fetch_pdf_text(url_or_path: str, max_chars: int = 30000) -> str:
    """Download a PDF (URL) or read local path, extract text via pypdf. Free."""
    from pypdf import PdfReader
    from io import BytesIO
    if url_or_path.startswith("http"):
        req = urllib.request.Request(url_or_path, headers={"User-Agent": "Jester-Research/2.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        reader = PdfReader(BytesIO(data))
    else:
        reader = PdfReader(url_or_path)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(f"--- Page {i+1} ---\n{page.extract_text() or ''}")
        except Exception:
            continue
    return "\n\n".join(pages)[:max_chars]


def fetch_github_repo_info(repo_url: str) -> dict:
    """README + file tree + last 5 commits for any GitHub repo. Free (60 req/hr unauth)."""
    m = re.search(r"github\.com/([^/]+)/([^/?#]+)", repo_url)
    if not m:
        raise ValueError(f"Not a GitHub repo URL: {repo_url}")
    owner, repo = m.group(1), m.group(2).rstrip(".git")
    base = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Jester-Research/2.0"}

    def _get(u):
        req = urllib.request.Request(u, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())

    info = _get(base)
    try:
        readme_meta = _get(f"{base}/readme")
        import base64 as _b64
        readme = _b64.b64decode(readme_meta.get("content", "")).decode("utf-8", errors="ignore")
    except Exception:
        readme = "(no README found)"
    try:
        commits = _get(f"{base}/commits?per_page=5")
        commit_lines = [
            f"  {c['sha'][:7]}  {c['commit']['author']['date'][:10]}  {c['commit']['message'].splitlines()[0][:80]}"
            for c in commits
        ]
    except Exception:
        commit_lines = []
    try:
        tree = _get(f"{base}/git/trees/{info.get('default_branch', 'main')}?recursive=1")
        files = sorted([n["path"] for n in tree.get("tree", []) if n["type"] == "blob"])[:80]
    except Exception:
        files = []

    return {
        "repo":        f"{owner}/{repo}",
        "description": info.get("description", ""),
        "stars":       info.get("stargazers_count", 0),
        "language":    info.get("language", ""),
        "updated":     info.get("updated_at", "")[:10],
        "url":         info.get("html_url", repo_url),
        "readme":      readme[:8000],
        "commits":     commit_lines,
        "files":       files,
    }


def fetch_image_to_path(url: str) -> Path:
    """Download an image (or copy if already local) into the fetch_cache. Returns absolute path
    Claude can pass to its Read tool to see the image natively."""
    import hashlib, shutil
    if not url.startswith("http"):
        src = Path(url)
        if not src.exists():
            raise FileNotFoundError(url)
        dest = JESTER_CACHE_DIR / src.name
        shutil.copy(src, dest)
        return dest
    ext = url.rsplit(".", 1)[-1].split("?")[0].lower()
    if ext not in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
        ext = "img"
    h = hashlib.blake2b(url.encode(), digest_size=8).hexdigest()[:10]
    dest = JESTER_CACHE_DIR / f"img_{h}.{ext}"
    if dest.exists():
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        dest.write_bytes(resp.read())
    return dest


def extract_video_keyframes(url: str, count: int = 10, max_seconds: int = 1800) -> list[Path]:
    """Download video via yt-dlp, extract `count` keyframes evenly spaced via ffmpeg.
    Returns list of frame paths. Claude can read each natively to 'see' the video.
    Free, local CPU only."""
    import subprocess, tempfile, hashlib, shutil
    h = hashlib.blake2b(url.encode(), digest_size=8).hexdigest()[:10]
    out_dir = JESTER_CACHE_DIR / f"frames_{h}"
    if out_dir.exists() and any(out_dir.iterdir()):
        return sorted(out_dir.glob("frame_*.jpg"))
    out_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        video_path = Path(tmp) / "video.mp4"
        cmd_dl = [
            sys.executable, "-m", "yt_dlp",
            # Frames need no audio. YouTube often serves only split streams now,
            # so a combined-only selector fails with "Requested format is not available".
            "-f", "best[height<=480]/bv*[height<=720][ext=mp4]/bv*[height<=720]/bv*/best",
            "--no-playlist",
            "-o", str(video_path),
            url,
        ]
        r = subprocess.run(cmd_dl, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not video_path.exists():
            raise RuntimeError(f"yt-dlp failed: {r.stderr[-300:]}")

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video_path)],
            capture_output=True, text=True, timeout=30,
        )
        try:
            duration = min(float(probe.stdout.strip()), float(max_seconds))
        except Exception:
            duration = float(max_seconds)
        if duration <= 0:
            raise RuntimeError("Video duration unavailable")
        interval = duration / max(count, 1)

        cmd_ff = [
            "ffmpeg", "-loglevel", "error", "-i", str(video_path),
            "-vf", f"fps=1/{interval},scale=640:-1",
            "-frames:v", str(count),
            str(out_dir / "frame_%02d.jpg"),
        ]
        r2 = subprocess.run(cmd_ff, capture_output=True, text=True, timeout=180)
        if r2.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {r2.stderr[-300:]}")

    return sorted(out_dir.glob("frame_*.jpg"))


# ── Free replacements for Exa-only sources ───────────────────────────────────



def free_substack_rss(substack_url: str, max_items: int = 5) -> list[dict]:
    """Pull the most recent N posts from any Substack via its /feed RSS endpoint."""
    base = substack_url.rstrip("/")
    if not base.endswith("/feed"):
        if "substack.com" not in base:
            return []
        base = base.split("/p/")[0].rstrip("/") + "/feed"
    req = urllib.request.Request(base, headers={"User-Agent": "Jester-Research/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml = resp.read().decode("utf-8", errors="ignore")
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
        out = []
        for it in items[:max_items]:
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.DOTALL)
            link_m  = re.search(r"<link>(.*?)</link>", it, re.DOTALL)
            desc_m  = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", it, re.DOTALL)
            cdesc = re.sub(r"<[^>]+>", " ", desc_m.group(1) if desc_m else "")
            cdesc = re.sub(r"\s+", " ", cdesc).strip()[:1500]
            out.append({
                "title":   (title_m.group(1) if title_m else "").strip(),
                "url":     (link_m.group(1)  if link_m  else "").strip(),
                "content": cdesc,
            })
        return out
    except Exception:
        return []




def free_papers_search(query: str, num_results: int = 8) -> list[dict]:
    """Research papers via Semantic Scholar (200M+ papers, all disciplines, free, no auth).
    Falls back to OpenAlex if Semantic Scholar is rate-limited."""
    q = urllib.parse.quote(query)

    # Try Semantic Scholar first
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={q}&limit={num_results}&fields=title,abstract,year,authors,venue,url,citationCount,openAccessPdf"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        out = []
        for p in data.get("data", []):
            authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
            year = p.get("year", "")
            venue = p.get("venue", "")
            cites = p.get("citationCount", 0)
            abstract = (p.get("abstract") or "")[:1500]
            pdf = (p.get("openAccessPdf") or {}).get("url", "")
            out.append({
                "title":   p.get("title", "Untitled"),
                "url":     p.get("url", "") or pdf,
                "content": f"[{year}] {authors} | {venue} | cites: {cites}\n{abstract}",
            })
        if out:
            return out
    except Exception:
        pass

    # Fallback: OpenAlex
    url2 = f"https://api.openalex.org/works?search={q}&per-page={num_results}"
    try:
        contact = os.environ.get("JESTER_CONTACT_EMAIL", "").strip() or "admin@vibedna.ai"
        req2 = urllib.request.Request(url2, headers={"User-Agent": f"Jester-Research/2.0 (mailto:{contact})"})
        with urllib.request.urlopen(req2, timeout=15) as resp:
            data = json.loads(resp.read())
        out = []
        for w in data.get("results", []):
            authors = ", ".join((a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])[:3])
            year = w.get("publication_year", "")
            cites = w.get("cited_by_count", 0)
            abstract_idx = w.get("abstract_inverted_index") or {}
            # Reconstruct abstract from OpenAlex's inverted index
            if abstract_idx:
                positions: dict[int, str] = {}
                for word, idxs in abstract_idx.items():
                    for i in idxs:
                        positions[i] = word
                abstract = " ".join(positions[i] for i in sorted(positions))[:1500]
            else:
                abstract = ""
            out.append({
                "title":   w.get("title", "Untitled"),
                "url":     w.get("doi") or w.get("id", ""),
                "content": f"[{year}] {authors} | cites: {cites}\n{abstract}",
            })
        return out
    except Exception:
        return []


# ── More free source fetchers ────────────────────────────────────────────────

def _ddg_site_search(query: str, site: str, num_results: int = 6, domain_filter: str = "") -> list[dict]:
    """Generic DDG site: search helper used by multiple free fetchers."""
    q = urllib.parse.quote(f"{query} site:{site}")
    url = f"https://lite.duckduckgo.com/lite?q={q}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Jester-Research/2.0) AppleWebKit/537.36",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        enc_urls = re.findall(r"uddg=([^&\"]+)", html)
        titles   = re.findall(r"class='result-link'[^>]*>([^<]+)<", html)
        snippets = re.findall(r"class='result-snippet'>(.*?)</td>", html, re.DOTALL)
        out = []
        for i in range(min(num_results * 2, len(enc_urls))):
            if len(out) >= num_results:
                break
            real_url = urllib.parse.unquote(enc_urls[i])
            if domain_filter and domain_filter not in real_url:
                continue
            title   = titles[i].strip() if i < len(titles) else real_url
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()[:1500] if i < len(snippets) else ""
            out.append({"title": title, "url": real_url, "content": snippet})
        return out
    except Exception:
        return []




def free_news_search(query: str, num_results: int = 6) -> list[dict]:
    """Recent news via Google News RSS: free, no API key."""
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml = resp.read().decode("utf-8", errors="ignore")
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
        out = []
        for it in items[:num_results]:
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.DOTALL)
            link_m  = re.search(r"<link>(.*?)</link>", it, re.DOTALL)
            desc_m  = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", it, re.DOTALL)
            desc = re.sub(r"<[^>]+>", " ", desc_m.group(1) if desc_m else "").strip()[:1500]
            out.append({
                "title":   (title_m.group(1) if title_m else "").strip(),
                "url":     (link_m.group(1)  if link_m  else "").strip(),
                "content": desc,
            })
        return out
    except Exception:
        return []


def free_brave_search(query: str, num_results: int = 10) -> list[dict]:
    """SearXNG meta-search: hits Google+Bing+DDG simultaneously via public instance.
    NOTE: Most public SearXNG instances block non-browser requests (429/403).
    For reliable use: set SEARXNG_BASE_URL in .env pointing to your own instance,
    OR swap this for the Brave Search API (BRAVE_API_KEY, free tier 2000 req/mo at api.search.brave.com).
    Currently disabled from default source list for this reason."""
    # Public SearXNG instances, tried in order until one responds
    _INSTANCES = [
        "https://searx.be",
        "https://search.mdosch.de",
        "https://searxng.site",
    ]
    q = urllib.parse.quote(query)
    _SKIP = {"developers.reddit.com", "business.reddit.com"}
    for base in _INSTANCES:
        try:
            url = f"{base}/search?q={q}&format=json&categories=general&language=en"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Jester-Research/2.0)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            results = data.get("results", [])
            out = []
            for r in results:
                if len(out) >= num_results:
                    break
                u = r.get("url", "")
                domain = urllib.parse.urlparse(u).netloc.lstrip("www.")
                if domain in _SKIP:
                    continue
                out.append({
                    "title":   r.get("title", u),
                    "url":     u,
                    "content": r.get("content", "")[:1500],
                })
            if out:
                return out
        except Exception:
            continue
    return []

def free_stackoverflow_search(query: str, num_results: int = 8) -> list[dict]:
    """Stack Overflow/Exchange search via free API. Returns questions + accepted answers with vote counts."""
    q = urllib.parse.quote(query)
    url = (
        f"https://api.stackexchange.com/2.3/search/advanced"
        f"?q={q}&answers=1&order=desc&sort=relevance&site=stackoverflow"
        f"&filter=withbody&pagesize={num_results}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0", "Accept-Encoding": "gzip"})
    try:
        import gzip
        with urllib.request.urlopen(req, timeout=14) as resp:
            raw = resp.read()
            try:
                data = json.loads(gzip.decompress(raw))
            except Exception:
                data = json.loads(raw)
        out = []
        for item in data.get("items", []):
            body = re.sub(r"<[^>]+>", " ", item.get("body", ""))
            body = re.sub(r"\s+", " ", body).strip()[:2000]
            tags = ", ".join(item.get("tags", []))
            out.append({
                "title":   item.get("title", ""),
                "url":     item.get("link", ""),
                "content": (
                    f"Score: {item.get('score',0)} | Answers: {item.get('answer_count',0)} | Tags: {tags}\n{body}"
                ),
            })
        return out
    except Exception:
        return []


def free_arxiv_search(query: str, num_results: int = 6) -> list[dict]:
    """arXiv API: 2M+ papers in CS, AI, physics, math, economics. Full abstracts, free, no auth."""
    q = urllib.parse.quote(query)
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=all:{q}&start=0&max_results={num_results}"
        f"&sortBy=relevance&sortOrder=descending"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=14) as resp:
            xml = resp.read().decode("utf-8", errors="ignore")
        entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
        out = []
        for e in entries:
            title_m   = re.search(r"<title>(.*?)</title>", e, re.DOTALL)
            id_m      = re.search(r"<id>(.*?)</id>", e, re.DOTALL)
            summary_m = re.search(r"<summary>(.*?)</summary>", e, re.DOTALL)
            published = re.search(r"<published>(.*?)</published>", e)
            authors   = re.findall(r"<name>(.*?)</name>", e)
            title   = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
            url_    = (id_m.group(1).replace("abs", "pdf") if id_m else "").strip()
            summary = re.sub(r"\s+", " ", summary_m.group(1)).strip()[:2000] if summary_m else ""
            year    = published.group(1)[:4] if published else ""
            auth    = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            out.append({
                "title":   title,
                "url":     url_,
                "content": f"[{year}] {auth}\n{summary}",
            })
        return out
    except Exception:
        return []


def free_trends_search(query: str) -> list[dict]:
    """Google Trends via pytrends. Returns interest-over-time + related queries. Unique signal."""
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pt.build_payload([query[:100]], timeframe="today 3-m")
        iot = pt.interest_over_time()
        related = pt.related_queries()
        lines = []
        if not iot.empty:
            avg   = int(iot[query[:100]].mean()) if query[:100] in iot.columns else 0
            trend = "rising" if iot[query[:100]].iloc[-1] > iot[query[:100]].iloc[0] else "declining"
            lines.append(f"Search interest (last 90 days): avg={avg}/100, trend={trend}")
        rq = related.get(query[:100], {})
        top = rq.get("top")
        rising = rq.get("rising")
        if top is not None and not top.empty:
            top_list = ", ".join(top["query"].head(5).tolist())
            lines.append(f"Top related queries: {top_list}")
        if rising is not None and not rising.empty:
            rising_list = ", ".join(rising["query"].head(5).tolist())
            lines.append(f"Breakout/rising queries: {rising_list}")
        if lines:
            return [{"title": f"Google Trends: {query}", "url": "", "content": "\n".join(lines)}]
    except Exception:
        pass
    return []


def free_twitter_search(query: str, num_results: int = 10) -> list[dict]:
    """Twitter/X search via v2 API (bearer token) with DDG site:x.com fallback.
    Bearer token loaded from env TWITTER_BEARER_TOKEN or vault at runtime."""
    import os
    bearer = os.environ.get("TWITTER_BEARER_TOKEN", "")

    if bearer:
        try:
            q = urllib.parse.quote(f"{query} -is:retweet lang:en")
            url = (
                f"https://api.twitter.com/2/tweets/search/recent"
                f"?query={q}&max_results={min(num_results, 10)}"
                f"&tweet.fields=text,author_id,created_at,public_metrics"
                f"&expansions=author_id&user.fields=name,username"
            )
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {bearer}",
                "User-Agent": "Jester-Research/2.0",
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())

            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            out = []
            for tw in data.get("data", []):
                author = users.get(tw.get("author_id", ""), {})
                metrics = tw.get("public_metrics", {})
                handle = author.get("username", "unknown")
                name   = author.get("name", "")
                likes  = metrics.get("like_count", 0)
                reposts = metrics.get("retweet_count", 0)
                out.append({
                    "title":   f"@{handle} ({name})",
                    "url":     f"https://x.com/{handle}/status/{tw['id']}",
                    "content": f"Likes: {likes} | RTs: {reposts}\n{tw['text']}",
                })
            if out:
                return out
        except Exception:
            pass

    # Fallback: DDG site:x.com
    return _ddg_site_search(query, "x.com", num_results, domain_filter="x.com")


def free_appstore_search(query: str, num_results: int = 5) -> list[dict]:
    """iOS App Store search via iTunes Search API: free, no auth."""
    q = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={q}&entity=software&limit={num_results}"
    req = urllib.request.Request(url, headers={"User-Agent": "Jester-Research/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        out = []
        for app in data.get("results", []):
            out.append({
                "title":   app.get("trackName", ""),
                "url":     app.get("trackViewUrl", ""),
                "content": (
                    f"Price: {app.get('formattedPrice','Free')} | "
                    f"Rating: {app.get('averageUserRating','N/A')} ({app.get('userRatingCount',0)} reviews) | "
                    f"Category: {app.get('primaryGenreName','')} | "
                    f"{app.get('description','')[:800]}"
                ),
            })
        return out
    except Exception:
        return []


# ── GitHub ────────────────────────────────────────────────────────────────────

def fetch_github_repos(query: str, num_results: int = 5) -> list[dict]:
    """Top starred GitHub repos matching the query."""
    q = urllib.parse.quote(f"{query} {CURRENT_YEAR}")
    url = (
        f"https://api.github.com/search/repositories"
        f"?q={q}&sort=stars&order=desc&per_page={num_results}"
    )
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Jester-Research/1.0",
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read())

    repos = []
    for item in data.get("items", []):
        repos.append({
            "title": item["full_name"],
            "url": item["html_url"],
            "content": (
                f"Stars: {item['stargazers_count']} | "
                f"Language: {item.get('language') or 'N/A'} | "
                f"Updated: {item['updated_at'][:10]} | "
                f"Forks: {item.get('forks_count', 0)} | "
                f"{item.get('description') or 'No description'}"
            ),
        })
    return repos


# ── CoinGecko Market Data ─────────────────────────────────────────────────────

def fetch_market_data(topic: str) -> str:
    """Live global crypto market stats + top trending coins from CoinGecko (free, no key)."""
    lines = [f"=== LIVE MARKET DATA (CoinGecko, {datetime.now().strftime('%Y-%m-%d %H:%M')}) ==="]

    # Global stats
    try:
        req = urllib.request.Request(
            "https://api.coingecko.com/api/v3/global",
            headers={"User-Agent": "Jester-Research/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            g = json.loads(resp.read())["data"]
        lines += [
            f"Total market cap: ${g['total_market_cap'].get('usd', 0)/1e12:.2f}T",
            f"24h volume: ${g['total_volume'].get('usd', 0)/1e9:.1f}B",
            f"BTC dominance: {g['market_cap_percentage'].get('btc', 0):.1f}%",
            f"ETH dominance: {g['market_cap_percentage'].get('eth', 0):.1f}%",
            f"Active cryptos: {g.get('active_cryptocurrencies', 'N/A')}",
            f"Market change 24h: {g.get('market_cap_change_percentage_24h_usd', 0):.2f}%",
        ]
    except Exception as e:
        lines.append(f"Global stats unavailable: {e}")

    # Trending coins
    try:
        req = urllib.request.Request(
            "https://api.coingecko.com/api/v3/search/trending",
            headers={"User-Agent": "Jester-Research/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            trend_data = json.loads(resp.read())
        lines.append("\nTrending coins (right now):")
        for coin in trend_data.get("coins", [])[:7]:
            c = coin["item"]
            lines.append(
                f"  #{c.get('market_cap_rank','?')} {c['name']} ({c['symbol'].upper()}) "
                f"-- 24h: {c.get('data', {}).get('price_change_percentage_24h', {}).get('usd', 0):.1f}%"
            )
    except Exception as e:
        lines.append(f"Trending data unavailable: {e}")

    # Try to find specific coin mentioned in topic
    try:
        keywords = [w for w in topic.lower().split() if len(w) > 2
                    and w not in {"bot", "trading", "strategy", "best", "top", "for", "the", "and"}]
        if keywords:
            search_q = urllib.parse.quote(keywords[0])
            req = urllib.request.Request(
                f"https://api.coingecko.com/api/v3/search?query={search_q}",
                headers={"User-Agent": "Jester-Research/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                sdata = json.loads(resp.read())
            coins = sdata.get("coins", [])[:3]
            if coins:
                lines.append(f"\nCoins matching '{keywords[0]}':")
                for c in coins:
                    lines.append(f"  {c['name']} ({c['symbol']}) -- Rank #{c.get('market_cap_rank','?')}")
    except Exception:
        pass

    return "\n".join(lines)


# ── Claude Extraction ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are Jester -- a ruthless intelligence extractor. Current year: {CURRENT_YEAR}.
You receive raw content from multiple sources (YouTube, Reddit, Twitter, GitHub, research papers, market data).
Be precise. Extract only what is stated. No padding. No hallucination.
If something isn't in the source, omit rather than guess.
Flag any data/prices/stats from before {CURRENT_YEAR} as [POTENTIALLY OUTDATED]."""


def _build_extraction_prompt(current_year: int, active_sources: list[str]) -> str:
    community_section = ""
    if any(s in active_sources for s in ["reddit", "twitter", "hn", "producthunt"]):
        community_section = """
## Community Sentiment
What are real users saying? Consensus view, complaints, what's praised, hidden gems. Be specific about source (Reddit/HN/Twitter).
"""

    linkedin_section = ""
    if "linkedin" in active_sources:
        linkedin_section = """
## LinkedIn Intelligence
What professionals and founders are saying. Trends, hiring signals, B2B use cases, authority voices in the space.
"""

    podcast_section = ""
    if any(s in active_sources for s in ["podcast", "listenotes"]):
        podcast_section = """
## Podcast Intelligence
Key insights from podcast episodes and show notes. Guest expertise, recurring themes, what hosts keep circling back to.
"""

    youtube_section = ""
    if "youtube_search" in active_sources:
        youtube_section = """
## Video Intelligence
Key insights from YouTube videos. What creators are teaching, what techniques they demonstrate, viewer signals.
"""

    quora_section = ""
    if "quora" in active_sources:
        quora_section = """
## Quora Expertise
Expert answers and practitioner experience. Real-world case studies, nuanced takes, specific how-tos.
"""

    medium_section = ""
    if "medium" in active_sources:
        medium_section = """
## Long-Form Perspectives
Insights from Medium articles. Analysis, opinion, case studies, and deep dives from practitioners.
"""

    indiehackers_section = ""
    if "indiehackers" in active_sources:
        indiehackers_section = """
## Indie Hacker Intelligence
Revenue numbers, traction stories, what bootstrapped founders tried, what worked/failed. Specific MRR figures if stated.
"""

    news_section = ""
    if "news" in active_sources:
        news_section = """
## Breaking News
Most recent developments (last 30 days). What just happened, who announced what, emerging shifts.
"""

    github_section = ""
    if "github" in active_sources:
        github_section = """
## Open Source Activity
Top repos: name, stars, language, what it does. Real developer adoption signal.
"""

    market_section = ""
    if "market" in active_sources:
        market_section = """
## Market Data Snapshot
Live numbers: market cap, dominance, trending assets, 24h changes.
"""

    producthunt_section = ""
    if "producthunt" in active_sources:
        producthunt_section = """
## Product Hunt Discoveries
New/trending products in this space. Name, upvotes if stated, what it does, who it's for.
"""

    papers_section = ""
    if "papers" in active_sources:
        papers_section = """
## Academic Evidence
What research papers say. Methodology, findings, limitations. Only if papers present in source.
"""

    amazon_section = ""
    if "amazon" in active_sources:
        amazon_section = """
## Amazon / App Store Reviews
Real buyer complaints, praise, and unmet needs. What people wish the product did. Patterns across reviews.
"""

    wikipedia_section = ""
    if "wikipedia" in active_sources:
        wikipedia_section = """
## Background Context
Key definitions, history, market size from Wikipedia. Use as grounding, not primary signal.
"""

    firecrawl_section = ""
    if "firecrawl" in active_sources:
        firecrawl_section = """
## Deep Site Intelligence
Extracted content from crawled URL(s). Key claims, pricing, positioning, features found on the page.
"""

    return f"""You are Jester, an elite intelligence extraction engine. Today: {current_year}.

ROLE: Senior research analyst. Your job is to extract maximum signal from raw source content.
CONTEXT: Sources come from multiple independent channels. Weight claims by how many sources agree.
FORMAT: Structured markdown report.
CRITERIA: Every claim needs a source citation. Numbers beat opinions. Contradictions must be flagged.

Sources are labeled: === REDDIT: title (url) ===, === WEB: title (url) ===, etc.

STAGE 1 (BIG PICTURE): What is the core claim across ALL sources? What is the proof?
STAGE 2 (DEEP DIVE): What specific facts, numbers, tools, names emerged? Where do sources agree or conflict?
STAGE 3 (CONTRADICTION RESOLUTION): Where sources disagree, which is more credible and why?

Output EXACTLY this format:

## TL;DR
3 sentences. Core claim across all sources. Best proof found. Most actionable takeaway.

## Key Insights
For EACH insight, prefix with conviction level:
- [HIGH CONVICTION]: 3+ independent sources confirm this
- [MULTI SOURCE]: 2 independent sources confirm this
- [SINGLE SOURCE]: only 1 source mentions this
Cite source after every factual claim: [via source-name]. Include numbers, names, prices, percentages exactly as stated.

## Action Steps
Numbered. Concrete. Specific tools, URLs, prices, commands where found. Skip generic advice.

## Tools & Platforms
| Tool | What it does | Cost | Source |
|------|-------------|------|--------|
Every tool mentioned. URL in Source column.
{community_section}{linkedin_section}{podcast_section}{youtube_section}{quora_section}{medium_section}{indiehackers_section}{news_section}{producthunt_section}{github_section}{market_section}{papers_section}{amazon_section}{wikipedia_section}{firecrawl_section}
## People & Brands
- Name: role, why relevant, source

## Business Model
Revenue model, price points, margins. Only what sources explicitly state.

## What to Build
Synthesize gaps and complaints found across ALL sources:
- **The Gap:** specific unmet need with evidence from sources
- **Product:** 1 product idea with a name
- **Target user:** exact persona
- **Revenue model:** price + model + why it works
- **Time to build:** honest estimate
- **First-month revenue target:** realistic number with reasoning

## Red Flags / Warnings
Contradictions between sources. Debunked claims. Vendor bias. Flag any data from before {current_year} as [POTENTIALLY OUTDATED].

## Best Quotes
2-3 verbatim quotes that capture something surprising or counter-intuitive. Omit section if none found.

---
SOURCE CONTENT:
{{content}}
"""


def _claude_call(prompt: str, model_id: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _chunk_by_sources(content: str, target_chars: int = 15000) -> list[str]:
    """Split combined content on '=== SOURCE ===' boundaries into ~target_chars chunks.
    Preserves source-block integrity so Claude never sees a half-chunked source."""
    blocks = re.split(r"(?=^=== [A-Z_]+(?:\: |\n))", content, flags=re.MULTILINE)
    blocks = [b for b in blocks if b.strip()]
    chunks: list[str] = []
    current = ""
    for b in blocks:
        if len(current) + len(b) > target_chars and current:
            chunks.append(current)
            current = b
        else:
            current += b
    if current:
        chunks.append(current)
    return chunks


def extract_intelligence(content: str, active_sources: list[str], model: str = "haiku") -> str:
    """Multi-pass synthesis: chunks content by source-block when over the single-call budget,
    extracts intel from each chunk, then meta-synthesizes. Fixes the 20k-char truncation
    that was producing 0 HIGH-CONVICTION findings."""
    model_id = MODEL_MAP.get(model, MODEL_MAP["haiku"])
    max_tokens = 4000 if model in ("sonnet", "opus") else 2500
    base_prompt = _build_extraction_prompt(CURRENT_YEAR, active_sources)

    SINGLE_PASS_BUDGET = 18000

    if len(content) <= SINGLE_PASS_BUDGET:
        return _claude_call(base_prompt.format(content=content), model_id, max_tokens)

    chunks = _chunk_by_sources(content, target_chars=15000)
    if len(chunks) == 1:
        return _claude_call(base_prompt.format(content=chunks[0][:SINGLE_PASS_BUDGET]), model_id, max_tokens)

    partials = []
    for i, chunk in enumerate(chunks):
        partial_prompt = base_prompt.format(content=chunk[:SINGLE_PASS_BUDGET])
        partial = _claude_call(partial_prompt, model_id, max_tokens)
        partials.append(f"=== PARTIAL EXTRACTION {i+1}/{len(chunks)} ===\n{partial}")

    meta_input = "\n\n".join(partials)[:SINGLE_PASS_BUDGET]
    meta_prompt = base_prompt.format(content=meta_input) + (
        "\n\nNOTE: The source content above is itself a set of partial extractions from a larger corpus. "
        "Merge and dedupe insights. Promote insights that appear in multiple partials to [HIGH CONVICTION]. "
        "Resolve any contradictions between partials in the Red Flags section."
    )
    return _claude_call(meta_prompt, model_id, max_tokens)


# ── Report Builder ─────────────────────────────────────────────────────────────

def build_report(topic: str, sources_used: dict, extraction: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Jester Report: {topic}", f"*Generated: {now}*", ""]

    if sources_used.get("youtube"):
        lines += [f"**YouTube:** {sources_used['youtube']}", ""]

    for sname, pages in sources_used.items():
        if sname == "youtube" or not isinstance(pages, list):
            continue
        if pages:
            label = sname.upper()
            lines += [f"**{label} Sources:**"]
            for p in pages:
                lines.append(f"- [{p['title']}]({p['url']})")
            lines.append("")

    if sources_used.get("market"):
        lines += ["**Live Market Data:** CoinGecko", ""]

    lines += ["---", "", extraction]
    return "\n".join(lines)


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-")[:60]


def save_report(topic: str, content: str) -> Path:
    slug = slugify(topic)
    path = REPORTS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ── Watch Mode ────────────────────────────────────────────────────────────────

def save_snapshot(topic_slug: str, extraction: str) -> Path:
    path = SNAPSHOTS_DIR / f"{topic_slug}.json"
    data = {
        "topic_slug": topic_slug,
        "date": datetime.now().isoformat(),
        "extraction": extraction,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshot(topic_slug: str) -> dict | None:
    path = SNAPSHOTS_DIR / f"{topic_slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_watch_diff(prev: dict, current_extraction: str) -> str:
    import difflib
    prev_lines = prev["extraction"].splitlines(keepends=True)
    curr_lines = current_extraction.splitlines(keepends=True)
    diff = list(difflib.unified_diff(prev_lines, curr_lines, lineterm=""))

    added   = [l[1:].strip() for l in diff if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:].strip() for l in diff if l.startswith("-") and not l.startswith("---")]

    added   = [l for l in added   if l and not l.startswith("##")]
    removed = [l for l in removed if l and not l.startswith("##")]

    prev_date = prev["date"][:10]
    lines = [f"\n## Changes Since {prev_date}"]
    if added:
        lines.append("\n**New / Changed:**")
        lines.extend(f"+ {l}" for l in added[:15])
    if removed:
        lines.append("\n**No Longer Mentioned:**")
        lines.extend(f"- {l}" for l in removed[:10])
    if not added and not removed:
        lines.append("No significant changes since last run.")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Jester -- ruthless knowledge predator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", nargs="?", default="", help="YouTube URL or topic query")
    parser.add_argument("--also-web", action="store_true",
                        help="Also search general web (for YouTube inputs)")
    parser.add_argument("--depth", choices=["quick", "deep"], default="quick",
                        help="Web research depth (quick=1yr, deep=90d)")
    parser.add_argument("--web-results", type=int, default=5,
                        help="General web results count (default 5)")
    parser.add_argument("--source", nargs="+",
                        choices=ALL_SOURCE_NAMES + ["all"],
                        metavar="SOURCE",
                        help=f"Extra sources: {', '.join(ALL_SOURCE_NAMES)}, all")
    parser.add_argument("--watch", action="store_true",
                        help="Track changes: saves snapshot, diffs against previous run")
    parser.add_argument("--model", choices=["haiku", "sonnet", "opus"], default="haiku",
                        help="Synthesis model (haiku=fast/cheap, sonnet=balanced, opus=max quality)")
    parser.add_argument("--crawl", metavar="URL", nargs="+",
                        help="Deep crawl one or more URLs with Firecrawl and digest the content")
    parser.add_argument("--crawl-deep", action="store_true",
                        help="Crawl entire site (up to 8 pages) instead of single page")
    parser.add_argument("--stats", action="store_true",
                        help="Show Jester growth stats dashboard and exit")
    parser.add_argument("--free", action="store_true",
                        help="Zero-cost mode: Reddit JSON + HN Algolia + DuckDuckGo (default)")
    parser.add_argument("--paid", action="store_true",
                        help="Paid Exa mode: full multi-source quality search")
    args = parser.parse_args()

    # Free is the default. Use --paid to explicitly opt into Exa
    if not args.paid:
        args.free = True

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.stats:
        from metrics import print_stats
        print_stats()
        return

    is_youtube = bool(YOUTUBE_RE.search(args.input))
    current_year = datetime.now().year

    # Expand 'all'
    active_extra = set(args.source or [])
    if "all" in active_extra:
        active_extra = set(ALL_SOURCE_NAMES)

    # In free mode, auto-add reddit + hn (they're free) if no explicit source list given
    if args.free and not args.source:
        active_extra.update(["reddit", "hn"])

    # Auto-drop market data for non-crypto topics
    if "market" in active_extra and not _is_crypto_topic(args.input):
        active_extra.discard("market")
        print("  --  Market data skipped (non-crypto topic)")
    # Auto-drop tradingview for non-trading topics
    if "tradingview" in active_extra and not _is_crypto_topic(args.input):
        active_extra.discard("tradingview")
        print("  --  TradingView skipped (non-trading topic)")

    # Auto-append year to topic queries
    query_input = args.input
    if not is_youtube and not re.search(r"\b20\d{2}\b", query_input):
        query_input = f"{query_input} {current_year}"

    # Count total expected sources for progress bar
    expected_sources = 1 if (not is_youtube or args.also_web) else 0  # web
    if is_youtube:
        expected_sources += 1  # youtube
    expected_sources += sum(1 for s in active_extra if s in SOURCE_DOMAINS)
    expected_sources += sum(1 for s in ["papers", "github", "market", "youtube_search", "listenotes", "wikipedia"] if s in active_extra)
    if args.crawl:
        expected_sources += len(args.crawl)
    expected_sources = max(expected_sources, 1)

    free_label = "  [bold green]★ FREE MODE[/]" if args.free else ""
    console.print()
    console.print(Panel(
        f"[bold cyan]Ingesting:[/] [white]{args.input[:80]}[/]{free_label}\n"
        f"[dim]Sources: {len(active_extra) + 1} | Depth: {args.depth} | Model: {args.model.upper()} | Cost: {'$0.00' if args.free else 'Exa + Claude'}[/]",
        title="[bold magenta]JESTER[/] [dim]Knowledge Predator[/]",
        border_style="magenta", padding=(0, 2)
    ))
    console.print()

    source_rows: list[tuple] = []   # (label, count, chars, status)

    combined_content = ""
    sources_used: dict = {}
    active_source_labels: list[str] = []

    def _log_source(label: str, count: int, chars: int, ok: bool = True):
        icon  = "[bold green]✓[/]" if ok else "[bold red]✗[/]"
        cstr  = f"[dim]{chars:,} chars[/]" if chars else "[dim]-[/]"
        console.print(f"  {icon}  [bold]{label:<16}[/]  {count} results  {cstr}")
        source_rows.append((label, count, chars, ok))

    # ── YouTube ──
    if is_youtube:
        console.print(f"  [cyan]⟳[/]  [bold]youtube[/]       devouring...")
        try:
            title, transcript = get_youtube_transcript(args.input)
            combined_content += f"=== YOUTUBE TRANSCRIPT: {title} ===\n{transcript}\n\n"
            sources_used["youtube"] = title
            active_source_labels.append("youtube")
            _log_source("youtube", 1, len(transcript))
        except Exception as e:
            console.print(f"  [red]✗[/]  youtube: {e}")
            sys.exit(1)

    # Base query for all searches
    base_query = (
        f"{sources_used.get('youtube', '')} {current_year}".strip()
        if is_youtube
        else query_input
    )

    # ── General web ──
    if not is_youtube or args.also_web:
        if args.free:
            console.print(f"  [cyan]⟳[/]  [bold]web[/]            searching... [dim](DuckDuckGo, free)[/]")
        else:
            console.print(f"  [cyan]⟳[/]  [bold]web[/]            searching...")
        try:
            if args.free:
                pages = free_web_search(base_query, num_results=args.web_results)
            else:
                pages = exa_search(base_query, num_results=args.web_results,
                                    deep=(args.depth == "deep"))
            chars = sum(len(p["content"]) for p in pages)
            for p in pages:
                combined_content += f"=== WEB: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
            sources_used["web"] = pages
            active_source_labels.append("web")
            _log_source("web", len(pages), chars)
        except Exception as e:
            console.print(f"  [red]✗[/]  web: {e}")
            if not is_youtube:
                sys.exit(1)

    # Exa-only sources (require paid API key, skip gracefully in free mode)
    _EXA_ONLY_SOURCES = {
        "twitter", "producthunt", "substack", "tradingview", "linkedin",
        "podcast", "quora", "medium", "indiehackers", "devto", "news",
        "amazon", "appstore",
    }

    # ── Domain-scoped sources ──
    for source_name, domains in SOURCE_DOMAINS.items():
        if source_name not in active_extra:
            continue

        # In free mode: use native free APIs for reddit/hn, skip Exa-only sources
        if args.free:
            if source_name == "reddit":
                console.print(f"  [cyan]⟳[/]  [bold]{source_name:<16}[/]  fetching... [dim](JSON API, free)[/]")
                try:
                    pages = free_reddit_search(base_query, num_results=8)
                    chars = sum(len(p["content"]) for p in pages)
                    if pages:
                        for p in pages:
                            combined_content += f"=== REDDIT: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
                        sources_used["reddit"] = pages
                        active_source_labels.append("reddit")
                        _log_source("reddit", len(pages), chars)
                    else:
                        console.print(f"  [dim]-[/]  [dim]reddit[/]           no results")
                except Exception as e:
                    console.print(f"  [red]✗[/]  reddit: {e}")
                continue
            elif source_name == "hn":
                console.print(f"  [cyan]⟳[/]  [bold]{source_name:<16}[/]  fetching... [dim](Algolia, free)[/]")
                try:
                    pages = free_hn_search(base_query, num_results=8)
                    chars = sum(len(p["content"]) for p in pages)
                    if pages:
                        for p in pages:
                            combined_content += f"=== HN: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
                        sources_used["hn"] = pages
                        active_source_labels.append("hn")
                        _log_source("hn", len(pages), chars)
                    else:
                        console.print(f"  [dim]-[/]  [dim]hn[/]               no results")
                except Exception as e:
                    console.print(f"  [red]✗[/]  hn: {e}")
                continue
            elif source_name in _EXA_ONLY_SOURCES:
                console.print(f"  [dim]-[/]  [dim]{source_name:<16}[/]  skipped (requires Exa, use paid mode)")
                continue

        console.print(f"  [cyan]⟳[/]  [bold]{source_name:<16}[/]  fetching...")
        try:
            if source_name == "news":
                pages = exa_search_news(base_query, num_results=6)
            elif domains:
                fetch_n = 12 if source_name == "reddit" else 4
                pages = exa_search(base_query, num_results=fetch_n, domains=domains)
                # filter Reddit noise: drop posts with no keyword overlap
                if source_name == "reddit":
                    keywords = {w.lower() for w in base_query.split() if len(w) > 3}
                    pages = [
                        p for p in pages
                        if not keywords or any(
                            kw in (p.get("title", "") + " " + p.get("content", "")).lower()
                            for kw in keywords
                        )
                    ][:4]
            else:
                pages = []
            chars = sum(len(p["content"]) for p in pages)
            if pages:
                for p in pages:
                    combined_content += f"=== {source_name.upper()}: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
                sources_used[source_name] = pages
                active_source_labels.append(source_name)
                _log_source(source_name, len(pages), chars)
            else:
                console.print(f"  [dim]-[/]  [dim]{source_name}[/]           no results")
        except Exception as e:
            console.print(f"  [red]✗[/]  {source_name}: {e}")

    # ── Research papers ──
    if "papers" in active_extra and args.free:
        console.print(f"  [dim]-[/]  [dim]papers[/]           skipped (requires Exa, use paid mode)")
    elif "papers" in active_extra:
        console.print(f"  [cyan]⟳[/]  [bold]papers[/]          fetching...")
        try:
            pages = exa_search_papers(base_query, num_results=4)
            chars = sum(len(p["content"]) for p in pages)
            if pages:
                for p in pages:
                    combined_content += f"=== PAPER: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
                sources_used["papers"] = pages
                active_source_labels.append("papers")
                _log_source("papers", len(pages), chars)
            else:
                console.print("  [dim]-[/]  [dim]papers[/]           no results")
        except Exception as e:
            console.print(f"  [red]✗[/]  papers: {e}")

    # ── GitHub repos ──
    if "github" in active_extra:
        topic_for_gh = args.input if not is_youtube else sources_used.get("youtube", args.input)
        console.print(f"  [cyan]⟳[/]  [bold]github[/]          fetching...")
        try:
            repos = fetch_github_repos(topic_for_gh, num_results=5)
            chars = sum(len(r["content"]) for r in repos)
            if repos:
                block = "\n".join(f"  {r['title']}: {r['content']}" for r in repos)
                combined_content += f"=== GITHUB REPOS ===\n{block}\n\n"
                sources_used["github"] = repos
                active_source_labels.append("github")
                _log_source("github", len(repos), chars)
            else:
                console.print("  [dim]-[/]  [dim]github[/]           no results")
        except Exception as e:
            console.print(f"  [red]✗[/]  github: {e}")

    # ── CoinGecko market data ──
    if "market" in active_extra:
        console.print(f"  [cyan]⟳[/]  [bold]market[/]          live data...")
        try:
            market_block = fetch_market_data(args.input)
            combined_content += f"{market_block}\n\n"
            sources_used["market"] = True
            active_source_labels.append("market")
            _log_source("market", 1, len(market_block))
        except Exception as e:
            console.print(f"  [red]✗[/]  market: {e}")

    # ── YouTube topic search + bulk transcripts ──
    if "youtube_search" in active_extra and not is_youtube:
        raw_topic = re.sub(r"\b20\d{2}\b", "", args.input).strip()
        console.print(f"  [cyan]⟳[/]  [bold]youtube_search[/]   searching + transcribing...")
        try:
            vids = fetch_youtube_search(raw_topic, num_videos=3)
            chars = sum(len(v["content"]) for v in vids)
            if vids:
                for v in vids:
                    combined_content += f"=== YOUTUBE_SEARCH: {v['title']} ({v['url']}) ===\n{v['content']}\n\n"
                sources_used["youtube_search"] = vids
                active_source_labels.append("youtube_search")
                _log_source("youtube_search", len(vids), chars)
            else:
                console.print("  [dim]-[/]  [dim]youtube_search[/]   no transcripts found")
        except Exception as e:
            console.print(f"  [red]✗[/]  youtube_search: {e}")

    # ── Wikipedia background context ──
    if "wikipedia" in active_extra:
        raw_topic = re.sub(r"\b20\d{2}\b", "", args.input).strip()
        console.print(f"  [cyan]⟳[/]  [bold]wikipedia[/]       fetching...")
        try:
            articles = fetch_wikipedia(raw_topic, num_articles=2)
            chars = sum(len(a["content"]) for a in articles)
            if articles:
                for a in articles:
                    combined_content += f"=== WIKIPEDIA: {a['title']} ({a['url']}) ===\n{a['content']}\n\n"
                sources_used["wikipedia"] = articles
                active_source_labels.append("wikipedia")
                _log_source("wikipedia", len(articles), chars)
            else:
                console.print("  [dim]-[/]  [dim]wikipedia[/]        no articles found")
        except Exception as e:
            console.print(f"  [red]✗[/]  wikipedia: {e}")

    # ── Firecrawl URL crawl ──
    if args.crawl:
        if not FIRECRAWL_API_KEY:
            console.print("  [dim]-[/]  [dim]firecrawl[/]        skipped (add FIRECRAWL_API_KEY to .env)")
        else:
            crawl_pages = []
            for crawl_url in args.crawl:
                console.print(f"  [cyan]⟳[/]  [bold]firecrawl[/]       {'deep' if args.crawl_deep else 'single page'}...")
                try:
                    pages = firecrawl_url(crawl_url, deep=args.crawl_deep)
                    crawl_pages.extend(pages)
                    chars = sum(len(p["content"]) for p in pages)
                    _log_source("firecrawl", len(pages), chars)
                except Exception as e:
                    console.print(f"  [red]✗[/]  firecrawl: {e}")
            if crawl_pages:
                for p in crawl_pages:
                    combined_content += f"=== FIRECRAWL: {p['title']} ({p['url']}) ===\n{p['content']}\n\n"
                sources_used["firecrawl"] = crawl_pages
                active_source_labels.append("firecrawl")

    # ── Listen Notes podcast search ──
    if "listenotes" in active_extra and args.free:
        console.print(f"  [dim]-[/]  [dim]listenotes[/]       skipped (requires API key, use paid mode)")
    elif "listenotes" in active_extra:
        if not LISTENNOTES_API_KEY:
            console.print("  [dim]-[/]  [dim]listenotes[/]       skipped (add LISTENNOTES_API_KEY to .env)")
        else:
            raw_topic = re.sub(r"\b20\d{2}\b", "", args.input).strip()
            console.print(f"  [cyan]⟳[/]  [bold]listenotes[/]      searching podcasts...")
            try:
                episodes = fetch_listenotes(raw_topic, num_results=5)
                chars = sum(len(ep["content"]) for ep in episodes)
                if episodes:
                    for ep in episodes:
                        combined_content += f"=== PODCAST: {ep['title']} ({ep['url']}) ===\n{ep['content']}\n\n"
                    sources_used["listenotes"] = episodes
                    active_source_labels.append("listenotes")
                    _log_source("listenotes", len(episodes), chars)
                else:
                    console.print("  [dim]-[/]  [dim]listenotes[/]       no episodes found")
            except Exception as e:
                console.print(f"  [red]✗[/]  listenotes: {e}")

    if not combined_content.strip():
        console.print("\n[red]Nothing to digest. Exiting.[/]")
        sys.exit(1)

    # ── Memory: inject past knowledge ──
    from memory import build_memory_block, recall
    memory_block = build_memory_block(args.input)
    if memory_block:
        matches = recall(args.input, top_k=3, min_overlap=3)
        console.print(f"  [bold yellow]◈[/]  [bold]memory[/]          {len(matches)} past report(s) recalled")
        combined_content = memory_block + combined_content

    total_chars  = len(combined_content)
    source_count = sum(
        len(v) if isinstance(v, list) else (1 if v else 0)
        for v in sources_used.values()
    )

    # ── Extract ──
    topic = sources_used.get("youtube") or args.input
    console.print()
    console.print(f"  [magenta]⟳[/]  [bold]Extracting intelligence[/] from {source_count} sources + memory [{args.model.upper()}]  [dim]({total_chars:,} chars)[/]")
    extraction = extract_intelligence(combined_content, active_source_labels, model=args.model)

    # ── Watch mode diff ──
    watch_diff = ""
    if args.watch:
        topic_slug = slugify(topic)
        prev_snapshot = load_snapshot(topic_slug)
        if prev_snapshot:
            watch_diff = build_watch_diff(prev_snapshot, extraction)
            console.print(f"  [green]✓[/]  Watch diff vs [dim]{prev_snapshot['date'][:10]}[/]")
        else:
            console.print("  [dim]-[/]  Watch: baseline saved (run again to see changes)")
        save_snapshot(topic_slug, extraction)

    # ── Save ──
    full_extraction = extraction + watch_diff if watch_diff else extraction
    report = build_report(topic, sources_used, full_extraction)
    path = save_report(topic, report)

    # ── Score + Metrics ──
    from metrics import score_report, save_metrics, print_quality_panel
    from memory import refresh_index
    score_data = score_report(full_extraction)
    save_metrics(
        topic=topic,
        sources_count=source_count,
        char_count=total_chars,
        score_data=score_data,
        model=args.model,
        depth=args.depth,
        report_file=path.name,
        active_sources=active_source_labels,
    )

    # ── Output ──
    console.print()
    console.rule("[bold cyan]INTELLIGENCE REPORT[/]")
    console.print()
    console.print(full_extraction)
    console.print()
    console.rule()
    console.print()
    print_quality_panel(score_data, source_count, total_chars, args.model)
    console.print(f"[dim]Report saved:[/] {path}")
    refresh_index()
    console.print(f"[dim]Run [bold]jester --stats[/] to see growth over time.[/]")
    console.print()

    # ── Upgrade prompt (free runs only, not in self-feed/subprocess chains) ──
    if args.free and sys.stdin.isatty():
        _prompt_upgrade(args, topic)


def _prompt_upgrade(args, topic: str):
    """After a free run, offer to re-run with Exa for deeper intelligence."""
    import subprocess as _sp
    console.print(Panel(
        "[bold]Want deeper intelligence?[/]  Exa multi-source search gives higher-conviction findings.\n\n"
        "  [bold cyan][h][/]  Haiku:   fast, cheap   [dim]~$0.05 to $0.10[/]\n"
        "  [bold yellow][s][/]  Sonnet:  balanced     [dim]~$0.15 to $0.25[/]\n"
        "  [bold green][Enter][/] skip: you're done",
        title="[bold magenta]JESTER[/] [dim]Upgrade?[/]",
        border_style="dim cyan",
        padding=(0, 2),
    ))
    try:
        choice = input("  > ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Skipped.[/]")
        return

    if choice not in ("h", "haiku", "s", "sonnet"):
        console.print("[dim]Staying free. Done.[/]\n")
        return

    model = "sonnet" if choice in ("s", "sonnet") else "haiku"
    depth = "deep" if model == "sonnet" else "quick"

    # Build the paid re-run command
    cmd = [sys.executable, __file__, args.input, "--paid", "--model", model, "--depth", depth]
    if args.source:
        cmd += ["--source"] + list(args.source)
    else:
        cmd += ["--source", "reddit", "hn"]   # add social sources to Exa baseline
    if getattr(args, "also_web", False):
        cmd.append("--also-web")
    if getattr(args, "watch", False):
        cmd.append("--watch")

    console.print(f"\n  [magenta]⟳[/]  Upgrading → Exa + {model.upper()} + Reddit + HN  [dim]({depth} depth)[/]\n")
    _sp.run(cmd, cwd=str(Path(__file__).parent))


if __name__ == "__main__":
    main()
