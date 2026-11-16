"""Telegram public channels: auth-free HTML scrape via t.me/s/<channel>.

Avoids Telethon auth dance entirely. Each public channel exposes its recent
messages at https://t.me/s/<channel>, which is rendered HTML we parse.
Channel list is curated per-topic via a small registry. Extend as needed.
"""
import re
import time

_disabled = False
_note = "Auth-free t.me/s/<channel> HTML scrape. No Telethon. Curated channel registry per topic."

# Curated public channels by topic keyword. Lowercase keys. Each value is a list of channel handles.
_CHANNEL_REGISTRY = {
    "ai": ["aiagents", "ai_machinelearning_big_data", "data_science_official", "llm_under_hood"],
    "crypto": ["solana", "binance_announcements", "cryptosignals", "the_block_official"],
    "solana": ["solana", "solana_es", "QuickNode", "helius_dev"],
    "indie": ["indiehackers", "saas_news", "buildinpublic"],
    "founder": ["YC_News", "founders_network", "indiehackers"],
    "tools": ["product_hunt", "uses_this", "mkbhd"],
    "default": ["indiehackers", "aiagents", "ai_machinelearning_big_data"],
}

_MSG_RE = re.compile(
    r'<div[^>]*class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_DATE_RE = re.compile(r'datetime="([^"]+)"')
_LINK_RE = re.compile(r'<a class="tgme_widget_message_date"\s+href="([^"]+)"')


def _channels_for(topic: str) -> list[str]:
    t = topic.lower()
    hits = []
    for key, channels in _CHANNEL_REGISTRY.items():
        if key in t:
            hits.extend(channels)
    if not hits:
        hits = _CHANNEL_REGISTRY["default"]
    return list(dict.fromkeys(hits))[:5]


def _strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _fetch_channel(channel: str, topic: str, max_results: int) -> list[dict]:
    try:
        import httpx
    except ImportError:
        return []
    try:
        r = httpx.get(f"https://t.me/s/{channel}", timeout=15, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0 (jester-bot)"})
        if r.status_code != 200:
            return []
    except Exception:
        return []
    html = r.text
    blocks = re.split(r'<div class="tgme_widget_message_wrap', html)[1:]
    now = time.time()
    topic_lower = topic.lower()
    out = []
    for blk in blocks[-30:]:
        text_match = _MSG_RE.search(blk)
        if not text_match:
            continue
        text = _strip_html(text_match.group(1))
        if not text or topic_lower not in text.lower():
            continue
        date = ""
        d = _DATE_RE.search(blk)
        if d:
            date = d.group(1)
        link = ""
        m = _LINK_RE.search(blk)
        if m:
            link = m.group(1)
        out.append({
            "title": text[:120],
            "url": link or f"https://t.me/{channel}",
            "content": text[:1500],
            "source": "telegram",
            "creator_id": f"tg:{channel}",
            "captured_at": now,
            "published_at": date,
        })
        if len(out) >= max_results:
            break
    return out


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    channels = _channels_for(topic)
    per = max(2, max_results // len(channels))
    out = []
    for ch in channels:
        out.extend(_fetch_channel(ch, topic, per))
        if len(out) >= max_results:
            break
    return out[:max_results]
