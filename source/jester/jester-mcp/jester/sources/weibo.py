"""Weibo connector: Chinese AI Twitter.
TODO: Weibo has aggressive anti-scraping. Options:
  1. Official open API (requires Chinese phone + dev review)
  2. weibo-search GitHub project (cookie-based, fragile)
  3. Firecrawl on s.weibo.com/weibo?q={topic} (may need residential proxy from CN)
"""
_disabled = True
_note = "Needs Chinese-IP scraping or API key. Stub only."


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    return []
