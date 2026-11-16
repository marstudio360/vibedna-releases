"""Podcast transcript ingestion: My First Million, Lenny's, Acquired.

Strategy: web-search restricted to known podcast transcript hosts + leverage
existing whisper_transcribe_url when an audio URL is the only artifact.
Cheapest path uses search results only (no transcription cost).
"""
import time

_disabled = False
_note = "Web search across known podcast transcript domains. Whisper fallback for audio-only URLs."

PODCAST_DOMAINS = [
    "shows.acast.com",
    "mfmpod.com",
    "podscripts.co",
    "happyscribe.com/public",
    "rev.com/blog/transcripts",
    "lennyspodcast.com",
    "acquired.fm",
    "stevenbartlett.co.uk",
]


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    try:
        from jester import free_web_search
    except Exception:
        return []
    site_clause = " OR ".join(f"site:{d}" for d in PODCAST_DOMAINS)
    q = f"({site_clause}) transcript {topic}"
    try:
        results = free_web_search(q, num_results=max_results, fetch_content=True) or []
    except Exception:
        return []
    now = time.time()
    out = []
    for r in results:
        url = r.get("url", "")
        host = ""
        for d in PODCAST_DOMAINS:
            if d in url:
                host = d.split(".")[0]
                break
        out.append({
            "title": r.get("title", ""),
            "url": url,
            "content": r.get("content", "") or r.get("snippet", ""),
            "source": "podcast_transcripts",
            "creator_id": f"podcast:{host}" if host else "",
            "captured_at": now,
        })
    return out
