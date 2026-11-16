"""Stage 2b -- PACK PAGE.

Fetches each candidate's own page, pulls the license text and the download
links, and runs the classifier. This is where a candidate stops being "a thing
that appeared in a free listing" and becomes a pack with a verdict attached.

Every extractor here was written AFTER reading live markup. The three sources
agree on nothing:

  itch.io   double-quoted attrs, unstable attribute order, license lives in
            free prose inside the description, csrf_token needed to download
  OGA       double-quoted attrs, license is a structured taxonomy block
            (<div class='license-name'>CC0</div>) plus a license_images/<code>
            icon filename -- two independent machine-readable signals
  Kenney    SINGLE-quoted attrs (this is why an href="..." search finds
            nothing), license in a <td> pair, zip URL sits in a bare
            media/pages/assets/... path with no href at all
"""

from __future__ import annotations

import html as htmlmod
import re
import time
import urllib.request
from dataclasses import dataclass, field

from forge.discover import Candidate, UA, POLITE_DELAY
from forge.licenses import Verdict, classify, passes

_TAG = re.compile(r"<[^>]+>")


@dataclass
class Pack:
    candidate: Candidate
    license_text: str = ""
    verdict: Verdict | None = None
    downloads: list[str] = field(default_factory=list)
    itch_csrf: str = ""
    ok: bool = False
    error: str = ""

    @property
    def title(self) -> str:
        return self.candidate.title

    def gate(self, policy: str = "sellable_credited") -> tuple[bool, str]:
        if not self.verdict:
            return False, "no verdict (page not read)"
        return passes(self.verdict, policy)


def _get(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _text(fragment: str) -> str:
    return htmlmod.unescape(_TAG.sub(" ", fragment))


# ---------------------------------------------------------------------------
# itch.io
# ---------------------------------------------------------------------------

_ITCH_CSRF = re.compile(r'csrf_token"\s+value="([^"]+)"')
_ITCH_DESC = re.compile(
    r'class="formatted_description[^"]*"[^>]*>(.*?)</div>\s*(?:</div>|<div class="game_info)', re.S)
_ITCH_UPLOAD = re.compile(r'data-upload_id="(\d+)"')
# itch renders the license/terms of an asset pack as ordinary prose, so there
# is no structured field to read -- the whole description is the haystack.
_ITCH_INFO_ROW = re.compile(
    r'<td>\s*(?:License|Licence)\s*</td>\s*<td>(.*?)</td>', re.S | re.I)


def _read_itch(page: str) -> tuple[str, list[str], str]:
    csrf_m = _ITCH_CSRF.search(page)
    csrf = csrf_m.group(1) if csrf_m else ""

    chunks: list[str] = []
    row = _ITCH_INFO_ROW.search(page)
    if row:
        chunks.append(_text(row.group(1)))
    desc = _ITCH_DESC.search(page)
    if desc:
        chunks.append(_text(desc.group(1)))
    else:
        # Fall back to the whole page. Noisy, but the classifier quarantines
        # on no-match rather than guessing, so a noisy haystack is safer than
        # an empty one.
        chunks.append(_text(page))

    uploads = sorted(set(_ITCH_UPLOAD.findall(page)))
    return " ".join(chunks), uploads, csrf


# ---------------------------------------------------------------------------
# OpenGameArt
# ---------------------------------------------------------------------------

_OGA_LICENSE_NAME = re.compile(r"""class=['"]license-name['"]>([^<]+)<""")
_OGA_LICENSE_ICON = re.compile(r"license_images/([a-z0-9_\-]+)\.png")
_OGA_FILE = re.compile(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"')
# Drupal serves aggregated css/js out of the same files/ dir.
_OGA_SKIP = re.compile(r"/files/(?:css|js)/")

# The icon filename is a stable machine code; map it to canonical license text
# so the classifier sees a phrase it knows rather than a filename.
_OGA_ICON_TEXT = {
    "cc0": "CC0 public domain",
    "cc-by": "CC BY 3.0", "cc-by-30": "CC BY 3.0", "cc-by-40": "CC BY 4.0",
    "cc-by-sa": "CC BY-SA 3.0", "cc-by-sa-30": "CC BY-SA 3.0",
    "cc-by-sa-40": "CC BY-SA 4.0",
    "gpl": "GPL 3.0", "gpl2": "GPL 2.0", "gpl3": "GPL 3.0",
    "lgpl": "LGPL", "oga-by-30": "OGA-BY 3.0",
}


def _read_oga(page: str) -> tuple[str, list[str]]:
    names = [n.strip() for n in _OGA_LICENSE_NAME.findall(page)]
    icons = [_OGA_ICON_TEXT.get(c, c) for c in set(_OGA_LICENSE_ICON.findall(page))]
    # Both signals go in. OGA content is routinely multi-licensed, and the
    # classifier's ordering puts the most restrictive of them first.
    text = " ; ".join(dict.fromkeys(names + icons))

    files = [u for u in _OGA_FILE.findall(page) if not _OGA_SKIP.search(u)]
    return text, sorted(set(files))


# ---------------------------------------------------------------------------
# Kenney
# ---------------------------------------------------------------------------

# Kenney uses SINGLE quotes on attributes. Searching for href="..." returns
# nothing on this site -- that mistake cost a probe cycle on 2026-08-09.
_KENNEY_LICENSE = re.compile(
    r"""<td[^>]*>\s*License\s*</td>\s*<td[^>]*>(.*?)</td>""", re.S | re.I)
# The zip URL appears as a bare path, not inside an href.
_KENNEY_ZIP = re.compile(r"""https://kenney\.nl/media/pages/assets/[^"'<>\s]+\.zip""")


def _read_kenney(page: str) -> tuple[str, list[str]]:
    lic = _KENNEY_LICENSE.search(page)
    text = _text(lic.group(1)) if lic else ""
    zips = sorted(set(_KENNEY_ZIP.findall(page)))
    return text, zips


# ---------------------------------------------------------------------------

_READERS = {"itch": "itch", "opengameart": "oga", "kenney": "kenney"}


def read_pack(c: Candidate, delay: float = POLITE_DELAY) -> Pack:
    p = Pack(candidate=c)
    try:
        page = _get(c.url)
    except Exception as e:                                      # noqa: BLE001
        p.error = str(e)
        return p

    try:
        if c.source == "itch":
            p.license_text, _scraped, p.itch_csrf = _read_itch(page)
            # Upload ids are NOT in the page HTML -- the download button's href
            # is empty and filled by JS. The API is the only path, and it needs
            # the game_id that discovery captured from data-game_id.
            if c.game_id:
                from forge import itch_api
                for u in itch_api.uploads(c.game_id):
                    if u.is_asset or u.is_project:
                        p.downloads.append(f"itch:{u.id}:{u.filename}")
        elif c.source == "opengameart":
            p.license_text, p.downloads = _read_oga(page)
        elif c.source == "kenney":
            p.license_text, p.downloads = _read_kenney(page)
        else:
            p.error = f"no reader for source {c.source!r}"
            return p
    except Exception as e:                                      # noqa: BLE001
        p.error = f"parse failed: {e}"
        return p

    p.verdict = classify(p.license_text)
    p.ok = True
    if delay:
        time.sleep(delay)
    return p


def read_many(cands: list[Candidate], policy: str = "sellable_credited",
              verbose: bool = True) -> list[Pack]:
    out: list[Pack] = []
    for i, c in enumerate(cands, 1):
        p = read_pack(c)
        out.append(p)
        if not verbose:
            continue
        if not p.ok:
            print(f"{i:>3}. !! {c.title[:40]:<42} {p.error[:50]}")
            continue
        ok, reason = p.gate(policy)
        mark = "PASS" if ok else "SKIP"
        v = p.verdict
        print(f"{i:>3}. {mark} {c.title[:40]:<42} {v.license_id:<22} "
              f"{len(p.downloads)} dl  {'' if ok else reason[:44]}")
    return out


if __name__ == "__main__":
    import sys
    from forge import discover

    which = sys.argv[1] if len(sys.argv) > 1 else "kenney"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    if which == "itch":
        cands = discover.itch_browse_tags(["pixel-art", "rpg"], pages=1, mode="all")[:n]
    elif which == "oga":
        cands = discover.opengameart_search("medieval tileset", pages=1)[:n]
    else:
        cands = discover.kenney_index(limit=n)

    print(f"\nreading {len(cands)} {which} pack pages...\n")
    packs = read_many(cands)

    good = [p for p in packs if p.ok and p.gate()[0]]
    print(f"\n{len(good)}/{len(packs)} cleared sellable_credited")
    for p in good:
        print(f"  + {p.title[:44]:<46} {p.verdict.license_id}")
        if p.verdict.matched:
            print(f"      matched: {p.verdict.matched[:110]}")
