"""Newsletter archive scraping: Lenny's, Ben's Bites, Indie Bites.

Strategy: web-search restricted to each archive site for the topic.
Each known archive has a stable URL pattern; we let the search engine do the heavy lifting.
Firecrawl-friendly: when keys present, can hit each result with firecrawl_url for fuller text.
"""
import os
import time

_disabled = False
_note = "Free web search restricted to newsletter archive domains."

ARCHIVE_DOMAINS = [
    "lennysnewsletter.com",
    "bensbites.beehiiv.com",
    "bensbites.co",
    "indiebites.co",
    "newsletter.eng-leadership.com",
    "stratechery.com",
    "platformer.news",
]


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    try:
        from jester import free_web_search, firecrawl_url
    except Exception:
        return []
    site_clause = " OR ".join(f"site:{d}" for d in ARCHIVE_DOMAINS)
    q = f"({site_clause}) {topic}"
    try:
        results = free_web_search(q, num_results=max_results, fetch_content=True) or []
    except Exception:
        return []
    now = time.time()
    out = []
    use_firecrawl = bool(os.environ.get("FIRECRAWL_API_KEY"))
    for r in results:
        content = r.get("content", "") or r.get("snippet", "")
        url = r.get("url", "")
        if use_firecrawl and len(content) < 500 and url:
            try:
                fc = firecrawl_url(url)
                if fc:
                    content = (fc.get("content") or fc.get("markdown") or content)[:4000]
            except Exception:
                pass
        creator = ""
        for d in ARCHIVE_DOMAINS:
            if d in url:
                creator = f"newsletter:{d.split('.')[0]}"
                break
        out.append({
            "title": r.get("title", ""),
            "url": url,
            "content": content,
            "source": "newsletter_archive",
            "creator_id": creator,
            "captured_at": now,
        })
    return out
