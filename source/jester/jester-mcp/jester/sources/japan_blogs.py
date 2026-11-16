"""Japanese tech blogs: Qiita REST API + Zenn RSS + Hatena Bookmark public JSON."""
import os
import time
import xml.etree.ElementTree as ET

_disabled = False
_note = "Qiita REST API (needs QIITA_ACCESS_TOKEN env), Zenn RSS, Hatena Bookmark public JSON."


def _fetch_qiita(topic: str, max_results: int) -> list[dict]:
    try:
        import httpx
    except ImportError:
        return []
    token = os.environ.get("QIITA_ACCESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = httpx.get(
            "https://qiita.com/api/v2/items",
            params={"query": topic, "per_page": min(max_results, 50)},
            headers=headers, timeout=15,
        )
        if r.status_code != 200:
            return []
        items = r.json() or []
    except Exception:
        return []
    now = time.time()
    return [{
        "title": it.get("title", ""),
        "url": it.get("url", ""),
        "content": (it.get("body", "") or "")[:1500],
        "source": "qiita",
        "creator_id": f"qiita:{(it.get('user') or {}).get('id', '')}",
        "captured_at": now,
        "likes": it.get("likes_count", 0),
        "published_at": it.get("created_at", ""),
    } for it in items[:max_results]]


def _fetch_zenn(topic: str, max_results: int) -> list[dict]:
    try:
        import httpx
    except ImportError:
        return []
    try:
        r = httpx.get(
            "https://zenn.dev/api/articles",
            params={"order": "latest", "topicname": topic.replace(" ", "-").lower(), "count": min(max_results, 48)},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        items = (r.json() or {}).get("articles", [])
    except Exception:
        return []
    now = time.time()
    return [{
        "title": it.get("title", ""),
        "url": f"https://zenn.dev{it.get('path', '')}",
        "content": it.get("title", ""),
        "source": "zenn",
        "creator_id": f"zenn:{(it.get('user') or {}).get('username', '')}",
        "captured_at": now,
        "likes": it.get("liked_count", 0),
        "published_at": it.get("published_at", ""),
    } for it in items[:max_results]]


def _fetch_hatena(topic: str, max_results: int) -> list[dict]:
    try:
        import httpx
    except ImportError:
        return []
    try:
        r = httpx.get(
            "https://b.hatena.ne.jp/search/tag",
            params={"q": topic, "users": 3, "mode": "rss"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
    except Exception:
        return []
    now = time.time()
    ns = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rss": "http://purl.org/rss/1.0/", "dc": "http://purl.org/dc/elements/1.1/"}
    items = root.findall(".//rss:item", ns) or root.findall(".//item")
    out = []
    for it in items[:max_results]:
        title = (it.findtext("rss:title", "", ns) or it.findtext("title", "")).strip()
        url = (it.findtext("rss:link", "", ns) or it.findtext("link", "")).strip()
        desc = (it.findtext("rss:description", "", ns) or it.findtext("description", "")).strip()
        date = it.findtext("dc:date", "", ns)
        if not url:
            continue
        out.append({
            "title": title,
            "url": url,
            "content": desc[:1500],
            "source": "hatena",
            "creator_id": "",
            "captured_at": now,
            "published_at": date,
        })
    return out


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    per = max(2, max_results // 3)
    return _fetch_qiita(topic, per) + _fetch_zenn(topic, per) + _fetch_hatena(topic, max_results - 2 * per)
