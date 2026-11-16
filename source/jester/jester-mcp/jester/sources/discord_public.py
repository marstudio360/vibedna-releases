"""Discord public channel scraping.
TODO: Discord ToS forbids unauth scraping. Legit paths:
  - Bot account joined to public servers, reading via discord.py
  - discord-self-bot (ToS-violating, do NOT ship to users)
  - DiscoSearch (third-party indexer) HTTP API
Wire via bot token only, never user token.
"""
_disabled = True
_note = "Requires bot token + server membership. Stub."


def fetch(topic: str, max_results: int = 10) -> list[dict]:
    return []
