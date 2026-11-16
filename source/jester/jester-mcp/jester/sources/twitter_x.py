"""Twitter/X public posts via Nitter mirrors.

No API keys, no auth. Uses public Nitter RSS feeds. Mirror list rotates
because individual mirrors go down regularly. Extracts tweets matching topic
with author, content, engagement signals where parseable.
"""
import re
import time
import xml.etree.ElementTree as ET

_disabled = False
_note = "Auth-free Twitter via Nitter RSS mirrors. Rotates mirrors on failure."

NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.tiekoetter.com",
    "https://nitter.kavin.rocks",
]

_USER_RE = re.compile(r"@(\w+)")


def _strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _try_mirror(mirror: str, topic: str, max_results: int) -> list[dict]:
    try:
        import httpx
    except ImportError:
        return []
    try:
        url = f"{mirror}/search/rss"
        r = httpx.get(
            url,
            params={"f": "tweets", "q": topic},
            timeout=12,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (jester-bot)"},
        )
        if r.status_code != 200 or not r.content:
            return []
        root = ET.fromstring(r.content)
    except Exception:
        return []

    now = time.time()
    items = root.findall(".//item")
    out = []
    for it in items[:max_results]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        desc = _strip_html(it.findtext("description") or "")
        pub = it.findtext("pubDate") or ""
        author = ""
        if "@" in title:
            m = _USER_RE.search(title)
            if m:
                author = m.group(1)
        elif link:
            try:
                slug = link.replace(f"{mirror}/", "").split("/")[0]
                author = slug
            except Exception:
                pass
        if not author:
            creator_match = it.findtext("dc:creator", "", {"dc": "http://purl.org/dc/elements/1.1/"})
            if creator_match:
                author = creator_match.lstrip("@")
        out.append({
            "title": title[:280] or desc[:120],
            "url": link.replace(mirror, "https://twitter.com") if link.startswith(mirror) else link,
            "content": desc[:1500],
            "source": "twitter",
            "creator_id": f"x:{author}" if author else "",
            "captured_at": now,
            "published_at": pub,
        })
    return out


def fetch(topic: str, max_results: int = 15) -> list[dict]:
    for mirror in NITTER_MIRRORS:
        results = _try_mirror(mirror, topic, max_results)
        if results:
            return results
    return []
