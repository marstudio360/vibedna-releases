"""Underground source connectors.

Each module exposes:
    _disabled: bool
    fetch(topic: str, max_results: int = 10) -> list[dict]

Standard return schema per item:
    {title, url, content, source, creator_id, captured_at}
"""

from . import (
    weibo, zhihu, japan_blogs, discord_public, telegram_public,
    indiehackers, newsletter_archive, substack_notes, podcast_transcripts,
    twitter_x, youtube_transcripts,
)

REGISTRY = {
    "weibo": weibo,
    "zhihu": zhihu,
    "japan_blogs": japan_blogs,
    "discord_public": discord_public,
    "telegram_public": telegram_public,
    "indiehackers": indiehackers,
    "newsletter_archive": newsletter_archive,
    "substack_notes": substack_notes,
    "podcast_transcripts": podcast_transcripts,
    "twitter_x": twitter_x,
    "youtube_transcripts": youtube_transcripts,
}


def fetch(source_name: str, topic: str, max_results: int = 10) -> list[dict]:
    mod = REGISTRY.get(source_name)
    if not mod:
        return []
    if getattr(mod, "_disabled", True):
        return [{"title": f"[{source_name}] not yet implemented",
                 "url": "", "content": "TODO connector stub",
                 "source": source_name, "creator_id": ""}]
    return mod.fetch(topic, max_results=max_results)


def list_sources() -> list[dict]:
    return [
        {"name": name, "disabled": getattr(mod, "_disabled", True),
         "note": getattr(mod, "_note", "")}
        for name, mod in REGISTRY.items()
    ]
