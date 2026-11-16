"""Build a browsable HTML gallery of the harvested library.

Answers one question visually: which of these can we actually use?
Packs are grouped by license shelf, each showing real sprite previews so the
art can be judged on sight rather than by filename.

    python gallery.py            -> <ASSET_FORGE_LIB>/gallery.html
"""

from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forge.fetch import LIB_ROOT, LIBRARY, META, SHELVES        # noqa: E402

THUMBS_PER_PACK = 8
MAX_THUMB_BYTES = 120_000
# One page per shelf. A single file covering 800+ packs with inlined base64
# thumbnails runs to hundreds of MB and no browser opens it.
SPLIT_BY_SHELF = True

SHELF_META = {
    "01-CLEAN-CC0": ("Ship anywhere", "No credit needed, no strings. Safest tier.", "#22c55e"),
    "02-CREDIT":    ("Ship with credit", "Usable in a game you sell; the pack goes in CREDITS.md.", "#38bdf8"),
    "03-CHECK":     ("Needs a human read", "Tiered pricing or no license stated. Do not ship until confirmed.", "#f59e0b"),
    "04-BLOCKED":   ("Prototype only", "Non-commercial or share-alike. Never ships in a sold game.", "#ef4444"),
}

# Sprite sheets and character art read better as previews than a UI atlas or a
# single giant tilemap, so rank filenames by how likely they are to show off
# the pack's actual style.
PREFER = ("character", "hero", "player", "sprite", "tile", "enemy", "monster",
          "item", "weapon", "sword", "npc", "town", "dungeon", "preview", "sample")

HTML_SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0b0f14; color:#e6edf3;
  font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
header.top {{ padding:26px 32px 16px; border-bottom:1px solid #1e2733; position:sticky; top:0;
  background:#0b0f14ee; backdrop-filter:blur(8px); z-index:5; }}
header.top h1 {{ margin:0 0 6px; font-size:21px; letter-spacing:-.01em; }}
header.top h1 a {{ color:inherit; text-decoration:none; }}
header.top p {{ margin:0; color:#8b98a8; font-size:13px; }}
header.top a {{ color:#7dd3fc; text-decoration:none; margin-right:6px; }}
.shelf {{ padding:28px 32px; border-bottom:1px solid #151d27; }}
.shelf-head h2 {{ margin:0 0 4px; font-size:17px; color:var(--accent); }}
.shelf-head h2 a {{ color:inherit; text-decoration:none; }}
.shelf-head p {{ margin:0 0 2px; color:#8b98a8; font-size:13px; }}
.shelf-head .count {{ color:#5d6b7d; font-size:12px; margin-bottom:16px; }}
.grid {{ display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); }}
.pack {{ background:#111823; border:1px solid #1e2733; border-left:3px solid var(--accent);
  border-radius:9px; padding:14px; }}
.pack h3 {{ margin:0 0 3px; font-size:14px; }}
.pack .meta {{ margin:0 0 10px; font-size:12px; color:#8b98a8; }}
.pack .lic {{ color:var(--accent); font-weight:600; }}
.thumbs {{ display:flex; flex-wrap:wrap; gap:7px; align-items:center; min-height:56px;
  background:#0a0e13; border-radius:6px; padding:9px; }}
.thumbs img {{ height:52px; width:auto; max-width:104px; object-fit:contain;
  image-rendering:pixelated; background:#161d28; border-radius:3px; padding:2px; }}
.empty {{ color:#4a5665; font-size:12px; }}
.pack footer {{ margin-top:10px; display:flex; justify-content:space-between; gap:8px;
  align-items:center; font-size:11px; }}
.pack code {{ color:#5d6b7d; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.pack a {{ color:#7dd3fc; text-decoration:none; flex-shrink:0; }}
.badge.zip {{ background:#1e3a5f; color:#7dd3fc; padding:1px 6px; border-radius:9px; font-size:10px; }}
</style></head><body>
<header class="top">
  <h1><a href="gallery.html">Asset Forge: harvested library</a></h1>
  <p>Grouped by what the license actually permits. Green ships anywhere; red never ships in a game you sell.</p>
  <p style="margin-top:8px">{nav}</p>
</header>
{body}
</body></html>"""


def pick_previews(pack_dir: Path, n: int = THUMBS_PER_PACK) -> list[Path]:
    imgs = [p for p in pack_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in (".png", ".gif")
            and p.stat().st_size <= MAX_THUMB_BYTES]

    def score(p: Path) -> tuple:
        name = p.name.lower()
        hit = next((i for i, k in enumerate(PREFER) if k in name), len(PREFER))
        return (hit, -p.stat().st_size)

    imgs.sort(key=score)
    return imgs[:n]


def data_uri(p: Path) -> str:
    mime = "image/gif" if p.suffix.lower() == ".gif" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def build() -> Path:
    manifest_path = META / "manifest.json"
    rows = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    by_slug = {r["slug"]: r for r in rows}

    parts: list[str] = []
    totals: dict[str, dict] = {}
    pages: dict[str, str] = {}

    for shelf in SHELVES.values():
        shelf_dir = LIBRARY / shelf
        if not shelf_dir.exists():
            continue
        packs = sorted([d for d in shelf_dir.iterdir() if d.is_dir()])
        if not packs:
            continue

        label, blurb, colour = SHELF_META.get(shelf, (shelf, "", "#888"))
        n_img = 0
        cards: list[str] = []

        for pd in packs:
            meta = by_slug.get(pd.name, {})
            previews = pick_previews(pd)
            count = sum(1 for p in pd.rglob("*")
                        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".gif"))
            n_img += count

            thumbs = "".join(
                f'<img src="{data_uri(p)}" alt="{html.escape(p.name)}" title="{html.escape(p.name)}">'
                for p in previews)

            title = html.escape(meta.get("title") or pd.name)
            author = html.escape(meta.get("author") or "")
            lic = html.escape(meta.get("license") or "?")
            url = html.escape(meta.get("url") or "")
            from_zip = ' <span class="badge zip">license read from zip</span>' if meta.get("verdict_from_archive") else ""

            cards.append(f"""
        <article class="pack">
          <header>
            <h3>{title}</h3>
            <p class="meta">{author} &middot; <span class="lic">{lic}</span> &middot; {count} images{from_zip}</p>
          </header>
          <div class="thumbs">{thumbs or '<span class="empty">no previewable images</span>'}</div>
          <footer>
            <code>{html.escape(pd.name)}</code>
            {f'<a href="{url}" target="_blank" rel="noopener">source</a>' if url else ''}
          </footer>
        </article>""")

        totals[shelf] = {"packs": len(packs), "images": n_img}
        section = f"""
    <section class="shelf" id="{shelf}" style="--accent:{colour}">
      <div class="shelf-head">
        <h2>{shelf}: {label}</h2>
        <p>{blurb}</p>
        <p class="count">{len(packs)} packs &middot; {n_img} images</p>
      </div>
      <div class="grid">{''.join(cards)}</div>
    </section>"""
        if SPLIT_BY_SHELF:
            pages[shelf] = section
        else:
            parts.append(section)

    def nav(active: str | None = None) -> str:
        bits = []
        for s, v in totals.items():
            href = f"gallery_{s}.html" if SPLIT_BY_SHELF else f"#{s}"
            mark = " style=\"font-weight:700\"" if s == active else ""
            bits.append(f'<a href="{href}"{mark}>{s}: {v["packs"]} packs / {v["images"]} imgs</a>')
        return " &middot; ".join(bits)

    summary = nav()

    def page(title: str, body: str, active: str | None = None) -> str:
        return HTML_SHELL.format(title=title, nav=nav(active), body=body)

    out_dir = LIB_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    if SPLIT_BY_SHELF:
        for shelf, section in pages.items():
            (out_dir / f"gallery_{shelf}.html").write_text(
                page(f"Asset Forge - {shelf}", section, shelf), encoding="utf-8")
        index_body = "".join(
            f'<section class="shelf" style="--accent:{SHELF_META.get(s, (s, "", "#888"))[2]}">'
            f'<div class="shelf-head"><h2><a href="gallery_{s}.html">{s}: '
            f'{SHELF_META.get(s, (s, "", "#888"))[0]}</a></h2>'
            f'<p>{SHELF_META.get(s, (s, "", "#888"))[1]}</p>'
            f'<p class="count">{v["packs"]} packs &middot; {v["images"]} images</p></div></section>'
            for s, v in totals.items())
        out = out_dir / "gallery.html"
        out.write_text(page("Asset Forge library", index_body), encoding="utf-8")
        return out

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asset Forge library</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0b0f14; color:#e6edf3;
  font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
header.top {{ padding:28px 32px 18px; border-bottom:1px solid #1e2733; position:sticky; top:0;
  background:#0b0f14ee; backdrop-filter:blur(8px); z-index:5; }}
header.top h1 {{ margin:0 0 6px; font-size:22px; letter-spacing:-.01em; }}
header.top p {{ margin:0; color:#8b98a8; font-size:13px; }}
header.top a {{ color:#7dd3fc; text-decoration:none; margin-right:4px; }}
.shelf {{ padding:30px 32px; border-bottom:1px solid #151d27; }}
.shelf-head h2 {{ margin:0 0 4px; font-size:17px; color:var(--accent); }}
.shelf-head p {{ margin:0 0 2px; color:#8b98a8; font-size:13px; }}
.shelf-head .count {{ color:#5d6b7d; font-size:12px; margin-bottom:16px; }}
.grid {{ display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); }}
.pack {{ background:#111823; border:1px solid #1e2733; border-left:3px solid var(--accent);
  border-radius:9px; padding:14px; }}
.pack h3 {{ margin:0 0 3px; font-size:14px; }}
.pack .meta {{ margin:0 0 10px; font-size:12px; color:#8b98a8; }}
.pack .lic {{ color:var(--accent); font-weight:600; }}
.thumbs {{ display:flex; flex-wrap:wrap; gap:7px; align-items:center; min-height:56px;
  background:#0a0e13; border-radius:6px; padding:9px; }}
.thumbs img {{ height:52px; width:auto; max-width:104px; object-fit:contain;
  image-rendering:pixelated; background:#161d28; border-radius:3px; padding:2px; }}
.empty {{ color:#4a5665; font-size:12px; }}
.pack footer {{ margin-top:10px; display:flex; justify-content:space-between; gap:8px;
  align-items:center; font-size:11px; }}
.pack code {{ color:#5d6b7d; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.pack a {{ color:#7dd3fc; text-decoration:none; flex-shrink:0; }}
.badge.zip {{ background:#1e3a5f; color:#7dd3fc; padding:1px 6px; border-radius:9px; font-size:10px; }}
</style></head><body>
<header class="top">
  <h1>Asset Forge: harvested library</h1>
  <p>Grouped by what the license actually permits. Green ships anywhere; red never ships in a game you sell.</p>
  <p style="margin-top:8px">{summary}</p>
</header>
{''.join(parts)}
</body></html>"""

    out = LIB_ROOT / "gallery.html"
    out.write_text(doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"gallery -> {p}  ({p.stat().st_size/1024/1024:.1f} MB)")
