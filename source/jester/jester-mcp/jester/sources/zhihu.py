"""Zhihu connector: Chinese Quora.
TODO: zhihu.com/search?type=content&q={topic}
Anti-scrape: requires cookies + sometimes captcha.
Path forward: Firecrawl with auth headers or zhihu_oauth python lib.
"""
_disabled = True
_note = "Needs cookies / proxy. Stub only."


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    return []
