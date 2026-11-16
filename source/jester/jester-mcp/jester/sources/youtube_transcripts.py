"""YouTube transcript ingestion.

Search YouTube for the topic via free_web_search restricted to youtube.com,
extract video IDs from results, pull auto-generated transcripts via
youtube-transcript-api (no key required).

Each transcript becomes a finding with content = first ~3000 chars of the
transcript. Creator IDs use the channel handle when extractable.
"""
import re
import time

_disabled = False
_note = "youtube-transcript-api (no key). Transcripts from top search results, free."

_VID_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")
_CHANNEL_RE = re.compile(r"youtube\.com/(?:@([\w.-]+)|c/([\w.-]+)|channel/([\w-]+))")


def _video_id(url: str) -> str:
    m = _VID_RE.search(url or "")
    return m.group(1) if m else ""


def _channel(url: str) -> str:
    m = _CHANNEL_RE.search(url or "")
    if not m:
        return ""
    return m.group(1) or m.group(2) or m.group(3) or ""


def _fetch_transcript(vid: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return ""
    try:
        chunks = YouTubeTranscriptApi.get_transcript(vid, languages=["en", "es", "ja"])
    except Exception:
        try:
            chunks = YouTubeTranscriptApi.list_transcripts(vid).find_transcript(["en"]).fetch()
        except Exception:
            return ""
    if not chunks:
        return ""
    text = " ".join(c.get("text", "") for c in chunks)
    return re.sub(r"\s+", " ", text).strip()[:3500]


def fetch(topic: str, max_results: int = 5) -> list[dict]:
    try:
        from jester import free_web_search
    except Exception:
        return []
    queries = [
        f"site:youtube.com {topic}",
        f"site:youtube.com {topic} how to OR tutorial OR breakdown",
    ]
    seen = set()
    candidates = []
    per = max(3, max_results)
    for q in queries:
        try:
            results = free_web_search(q, num_results=per, fetch_content=False) or []
        except Exception:
            continue
        for r in results:
            url = r.get("url", "")
            vid = _video_id(url)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            candidates.append((vid, r))
            if len(candidates) >= max_results * 2:
                break
        if len(candidates) >= max_results * 2:
            break

    now = time.time()
    out = []
    for vid, r in candidates:
        if len(out) >= max_results:
            break
        transcript = _fetch_transcript(vid)
        if not transcript:
            continue
        url = r.get("url", f"https://youtube.com/watch?v={vid}")
        channel = _channel(url)
        out.append({
            "title": r.get("title", ""),
            "url": url,
            "content": transcript,
            "source": "youtube",
            "creator_id": f"yt:{channel}" if channel else "",
            "captured_at": now,
            "video_id": vid,
        })
    return out
