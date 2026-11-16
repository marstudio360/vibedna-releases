"""IndieHackers public milestones connector.

Uses the existing free_web_search to query site:indiehackers.com for the topic.
Cheapest possible implementation: leverages existing infra, no new keys needed.
"""
import time

_disabled = False
_note = "Uses free web search restricted to indiehackers.com."


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    try:
        from jester import free_web_search
    except Exception:
        return []
    q = f"site:indiehackers.com {topic}"
    try:
        results = free_web_search(q, num_results=max_results, fetch_content=True) or []
    except Exception:
        return []
    now = time.time()
    out = []
    for r in results:
        url = r.get("url", "")
        creator = ""
        if "/post/" in url or "/product/" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 5:
                creator = f"ih:{parts[3]}"
        out.append({
            "title": r.get("title", ""),
            "url": url,
            "content": r.get("content", "") or r.get("snippet", ""),
            "source": "indiehackers",
            "creator_id": creator,
            "captured_at": now,
        })
    return out
