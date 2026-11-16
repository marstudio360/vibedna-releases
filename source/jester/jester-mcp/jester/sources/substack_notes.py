"""Substack Notes connector via free_web_search restricted to substack.com.

No API exists for Notes specifically. Best-effort: search-engine queries
constrained to substack.com pick up Notes URLs and short-form content.
Cheap (free_web_search), no new keys.
"""
import time

_disabled = False
_note = "free_web_search restricted to substack.com. Picks up posts + notes."


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    try:
        from jester import free_web_search
    except Exception:
        return []
    queries = [
        f"site:substack.com/notes {topic}",
        f"site:substack.com {topic}",
    ]
    now = time.time()
    seen = set()
    out = []
    per = max(3, max_results // len(queries))
    for q in queries:
        try:
            results = free_web_search(q, num_results=per, fetch_content=True) or []
        except Exception:
            continue
        for r in results:
            url = r.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            creator = ""
            try:
                host = url.split("//", 1)[1].split("/", 1)[0]
                if "." in host:
                    creator = f"substack:{host.split('.')[0]}"
            except Exception:
                pass
            is_note = "/notes/" in url or "/p/" not in url
            out.append({
                "title": r.get("title", ""),
                "url": url,
                "content": r.get("content", "") or r.get("snippet", ""),
                "source": "substack_notes" if is_note else "substack",
                "creator_id": creator,
                "captured_at": now,
            })
            if len(out) >= max_results:
                return out
    return out
