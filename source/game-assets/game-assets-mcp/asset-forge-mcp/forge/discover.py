"""Stage 1 -- DISCOVER.

Walks free-asset listings and emits candidate packs. Discovery only records
what a page *claims*; nothing here decides whether a pack is usable. The
license verdict comes from stage 2 reading the actual pack page.

Sources are pluggable. itch.io is the deep one (biggest catalogue of pixel
packs); OpenGameArt and Kenney are added as separate adapters because their
listing markup is nothing alike.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"

# itch rate-limits aggressively on burst. One request every 1.2s keeps us
# under it without needing backoff logic.
POLITE_DELAY = 1.2


@dataclass
class Candidate:
    source: str            # "itch" | "opengameart" | "kenney"
    title: str
    url: str
    author: str = ""
    tags: list[str] = field(default_factory=list)
    thumb: str = ""
    claimed_free: bool = True
    # itch browse cells carry data-game_id; the API needs it and nothing else
    # exposes it, so capture it during discovery or lose it.
    game_id: int = 0

    def key(self) -> str:
        return f"{self.source}:{self.url}"

    def as_dict(self) -> dict:
        return asdict(self)


def _get(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# itch.io
# ---------------------------------------------------------------------------

# Browse pages accept ?format=json and return {"content": "<html>", "num_items": N}.
# The embedded HTML is the same .game_cell markup as the normal page, so one
# parser covers both paths.
# Attribute order in itch markup is NOT stable: the cell div is
# `<div dir="auto" class="game_cell ...">` and the title anchor is
# `<a tabindex="-1" href="..." ... class="title game_link">` -- href before
# class. Verified against live markup 2026-08-09. Every pattern here is
# order-agnostic for that reason; anchoring on attribute position silently
# yields zero rows.
_ITCH_TITLE = re.compile(r'<a([^>]*\bclass="title game_link"[^>]*)>([^<]*)</a>')
_ITCH_HREF = re.compile(r'\bhref="([^"]+)"')
_ITCH_AUTHOR = re.compile(r'class="game_author[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>')
_ITCH_THUMB = re.compile(r'data-lazy_src="([^"]+)"')
_ITCH_TAG = re.compile(r'<a[^>]*href="/game-assets/[^"]*tag-([a-z0-9\-]+)"')
_ITCH_GAME_ID = re.compile(r'data-game_id="(\d+)"')


def itch_browse(tag: str, pages: int = 2, classification: str = "game-assets",
                free_only: bool = True) -> list[Candidate]:
    """Browse one itch.io asset tag.

    ONE tag per request, verified 2026-08-09: the stacked form
    ``/game-assets/free/tag-pixel-art/tag-rpg`` returns 403, while the single
    form returns 200. Intersect client-side via ``itch_browse_tags`` instead of
    asking itch to AND them.
    """
    path = f"/{classification}"
    if free_only:
        path += "/free"
    path += f"/tag-{tag}"

    tags = [tag]
    out: list[Candidate] = []
    for page in range(1, pages + 1):
        url = f"https://itch.io{path}?page={page}&format=json"
        try:
            raw = _get(url)
        except Exception as e:                                  # noqa: BLE001
            print(f"  ! itch page {page} failed: {e}")
            break

        try:
            html = json.loads(raw).get("content", "")
        except json.JSONDecodeError:
            html = raw   # some paths return HTML directly

        found = _parse_itch_cells(html, tags)
        if not found:
            break
        out.extend(found)
        time.sleep(POLITE_DELAY)

    return out


def itch_browse_tags(tags: list[str], pages: int = 2, mode: str = "any",
                     **kw) -> list[Candidate]:
    """Query several itch tags separately, then combine.

    mode="any"  -> union (broad harvest)
    mode="all"  -> only packs that showed up under every tag (tight targeting)
    """
    per_tag: dict[str, dict[str, Candidate]] = {}
    for t in tags:
        found = itch_browse(t, pages=pages, **kw)
        per_tag[t] = {c.url: c for c in found}
        print(f"  itch tag-{t}: {len(found)}")

    if mode == "all" and per_tag:
        common = set.intersection(*(set(d) for d in per_tag.values()))
    else:
        common = set().union(*(set(d) for d in per_tag.values())) if per_tag else set()

    merged: dict[str, Candidate] = {}
    for t, d in per_tag.items():
        for url in common:
            if url not in d:
                continue
            if url in merged:
                merged[url].tags = sorted(set(merged[url].tags) | set(d[url].tags))
            else:
                merged[url] = d[url]
    return list(merged.values())


def _parse_itch_cells(html: str, query_tags: list[str]) -> list[Candidate]:
    cells: list[Candidate] = []
    # Cell boundaries are not reliably nested, so split on the class attribute
    # itself rather than on a full opening tag -- the tag carries other
    # attributes before `class` and their order changes.
    chunks = html.split('class="game_cell')
    for chunk in chunks[1:]:
        m = _ITCH_TITLE.search(chunk)
        if not m:
            continue
        href_m = _ITCH_HREF.search(m.group(1))
        if not href_m:
            continue
        url, title = href_m.group(1), m.group(2).strip()
        author_m = _ITCH_AUTHOR.search(chunk)
        thumb_m = _ITCH_THUMB.search(chunk)
        gid_m = _ITCH_GAME_ID.search(chunk)
        tags = sorted(set(_ITCH_TAG.findall(chunk)) | set(query_tags))
        cells.append(Candidate(
            source="itch",
            title=title,
            url=url,
            author=(author_m.group(1).strip() if author_m else ""),
            tags=tags,
            thumb=(thumb_m.group(1) if thumb_m else ""),
            game_id=int(gid_m.group(1)) if gid_m else 0,
        ))
    return cells


# ---------------------------------------------------------------------------
# OpenGameArt
# ---------------------------------------------------------------------------

_OGA_ROW = re.compile(r'<a href="(/content/[^"]+)"[^>]*>([^<]+)</a>')


# OGA links every page in its chrome, so the nav has to be excluded by name
# or every search "finds" the FAQ.
_OGA_CHROME = {"faq", "about", "contact", "credits", "donate", "terms"}


def opengameart_search(query: str, art_type: str = "9", pages: int = 2) -> list[Candidate]:
    """Search OpenGameArt.

    No license facet: passing ``field_art_licenses_tid[0]=cc0`` returns zero
    rows (verified 2026-08-09 -- OGA wants numeric term ids there, not slugs).
    Dropping it returns real results, and stage 2 reads the license off each
    content page anyway, which is the more trustworthy source.

    art_type "9" is 2D art.
    """
    out: list[Candidate] = []
    for page in range(pages):
        params = {"keys": query, "page": str(page), "field_art_type_tid[]": art_type,
                  "sort_by": "count", "sort_order": "DESC"}
        url = "https://opengameart.org/art-search-advanced?" + urllib.parse.urlencode(params)
        try:
            html = _get(url)
        except Exception as e:                                  # noqa: BLE001
            print(f"  ! oga page {page} failed: {e}")
            break

        seen_here = 0
        known = {c.url for c in out}
        for href in re.findall(r'href="(/content/[a-z0-9\-]+)"', html):
            slug = href.rsplit("/", 1)[-1]
            if slug in _OGA_CHROME:
                continue
            full = "https://opengameart.org" + href
            if full in known:
                continue
            known.add(full)
            out.append(Candidate(source="opengameart",
                                 title=slug.replace("-", " ").title(),
                                 url=full, tags=[query]))
            seen_here += 1
        if not seen_here:
            break
        time.sleep(POLITE_DELAY)
    return out


# ---------------------------------------------------------------------------
# Kenney -- every pack is CC0, so this is the highest-yield source per request
# ---------------------------------------------------------------------------

#   LIMITATION, stated rather than hidden:
#   Kenney has no machine-readable pack index. The /assets grid renders
#   client-side (22 KB of nav chrome, zero pack links), /sitemap.xml is 404,
#   and /robots.txt is 404 -- all verified 2026-08-09. So this is a curated
#   seed list, NOT full coverage of Kenney's catalogue.
#
#   Slugs are candidates only: stage 2 fetches each page, and one that 404s
#   drops out. Nothing here is asserted as existing.
KENNEY_SEED_SLUGS = [
    # top-down / medieval / RPG-shaped, which is what this game needs
    "tiny-dungeon", "tiny-town", "tiny-battle", "tiny-ski",
    "1-bit-pack", "micro-roguelike", "roguelike-rpg-pack",
    "roguelike-caves-dungeons", "roguelike-modern-city", "roguelike-indoors",
    "medieval-rts", "pixel-platformer", "pixel-line-platformer",
    "bit-pack", "generic-items", "board-game-icons",
    "game-icons", "game-icons-expansion", "ui-pack", "ui-pack-rpg-expansion",
    "fantasy-ui-borders", "cursor-pack", "input-prompts-pixel-16",
]


def kenney_index(limit: int = 0, slugs: list[str] | None = None) -> list[Candidate]:
    """Emit Kenney pack candidates from the curated seed list.

    Every Kenney pack is CC0, but that is deliberately NOT hardcoded here --
    stage 2 reads the license off each page, so if Kenney ever changes terms
    the pipeline notices instead of trusting a stale constant.
    """
    picked = (slugs or KENNEY_SEED_SLUGS)[: limit or None]
    return [
        Candidate(
            source="kenney",
            title=slug.replace("-", " ").title(),
            url=f"https://kenney.nl/assets/{slug}",
            author="Kenney",
            tags=["kenney"],
        )
        for slug in picked
    ]


# ---------------------------------------------------------------------------

def dedupe(cands: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in cands:
        if c.key() in seen:
            continue
        seen.add(c.key())
        out.append(c)
    return out


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "itch"
    if which == "itch":
        res = itch_browse_tags(["pixel-art", "rpg"], pages=1, mode="all")
    elif which == "oga":
        res = opengameart_search("medieval tileset", pages=1)
    else:
        res = kenney_index(limit=40)
    print(f"{which}: {len(res)} candidates")
    for c in res[:12]:
        print(f"  {c.title[:44]:<46} {c.author[:16]:<18} {c.url}")
