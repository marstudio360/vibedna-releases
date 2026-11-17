#!/usr/bin/env python3
"""
Social Content Studio MCP: make social posts, carousels, reels and videos from your AI chat.

Your assistant writes the words; this server renders the pixels by code (no image model,
no GPU) and returns the file path(s): posts, carousels, templates in your brand's look,
layer documents, reels, footage-to-vertical edits, and a bridge to the live web editor.
Hand the files to any poster to publish them.

Output goes to ~/.post-engine/out/ by default (POST_ENGINE_OUT), or an explicit path you pass.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# The engine ships alongside this server (standalone).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_engine as pe
import video_engine as ve
import compositor as comp
import brands as br
import templates as tpl
import finishes as fin

mcp = FastMCP("social-content-studio")

_OUT_DIR = Path(os.environ.get("POST_ENGINE_OUT", str(Path.home() / ".post-engine" / "out")))
_OUT_DIR.mkdir(parents=True, exist_ok=True)

# This copy's version. Bump it when packaging; check_for_update compares it against
# what the site currently publishes, so an installed copy can tell it is behind.
VERSION = "1.3.10"
PRODUCT_SLUG = "post-engine-mcp"


@mcp.tool()
def check_for_update() -> str:
    """Is this copy behind the published version?

    Your copy is a folder on your machine, so it stays exactly as it was the day you
    installed it while fixes keep shipping. This asks what is published now and tells
    you whether to update, and how. It sends nothing about you: just a version number
    comes back."""
    import json as _json
    import urllib.request as _url
    try:
        req = _url.Request(
            "https://vibedna.ai/api/mcp/latest?slug=" + PRODUCT_SLUG,
            headers={"Accept": "application/json"},
        )
        with _url.urlopen(req, timeout=15) as r:
            d = _json.loads(r.read() or b"{}")
    except Exception as e:
        return f"could not reach the update check ({type(e).__name__}). Your copy still works; try later."

    latest = str(d.get("version") or "")
    if not latest:
        return "the update service did not report a version. Nothing to do."

    def parts(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)

    if parts(latest) <= parts(VERSION):
        return f"up to date (you have {VERSION}, published is {latest})."

    return "\n".join([
        f"UPDATE AVAILABLE: you have {VERSION}, published is {latest}.",
        "",
        "To update, from the same email you got it with:",
        f"  1. Download: https://vibedna.ai/api/download?slug={PRODUCT_SLUG}&license=<your key>",
        "     (your key is in your purchase email, and in your library at vibedna.ai/library)",
        "  2. Unzip over your current folder, keeping your own files:",
        "     your .env stays as it is.",
        "  3. Restart your AI so it loads the new tools.",
        "",
        "Your work lives outside this folder: everything you rendered, the fonts you",
        f"added and the effects your AI invented are under {Path.home() / '.post-engine'},",
        "so an update never touches them.",
    ])


# --- Content Studio Pro: FREE installs, PRO unlocks the ceiling ($19/mo). ---
# Free tools always work. Pro tools (reels/video, add_font, add_effect) check an
# active subscription via CONTENT_STUDIO_LICENSE against {STUDIO_URL}/api/studio/license.
_PRO_CACHE = None
_PRO_CHECKED_AT = 0.0


def _check_pro() -> bool:
    """Return True if an active Content Studio Pro subscription is present. Fail-closed:
    any missing key, network error, or parse error returns False and never raises.

    ONLY A "YES" IS REMEMBERED FOREVER. A "no" is re-checked, at most once every 30s, so a
    licence that goes active while the server is running is picked up without a restart."""
    global _PRO_CACHE, _PRO_CHECKED_AT
    if _PRO_CACHE:
        return True
    if _PRO_CACHE is False and (time.time() - _PRO_CHECKED_AT) < 30:
        return False
    _PRO_CHECKED_AT = time.time()
    key = os.environ.get("CONTENT_STUDIO_LICENSE", "").strip()
    if not key:
        _PRO_CACHE = False
        return False
    try:
        import urllib.request, urllib.parse
        base = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")
        url = base + "/api/studio/license?key=" + urllib.parse.quote(key, safe="")
        req = urllib.request.Request(url, headers={"User-Agent": "VibeDNA-PostEngine/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read() or b"null")
        active = bool(data.get("active")) if isinstance(data, dict) else False
        _PRO_CACHE = active
        return active
    except Exception:
        return False


_FREE_NOTE = (
    "(Free render: 1080px with a small badge. Content Studio Pro removes the badge and "
    "exports at full resolution. Subscribe at https://vibedna.ai/content-studio and set "
    "CONTENT_STUDIO_LICENSE.)"
)


def _pro_upsell(feature: str) -> str:
    """A friendly one-paragraph upsell returned in place of a Pro tool's result."""
    return (
        f"{feature} is a Content Studio Pro feature. The free tier makes on-brand posts, "
        "carousels and templates at zero render cost. Pro ($19/mo) unlocks reels and video, "
        "custom fonts your AI downloads on demand, and brand-new effects your AI invents at "
        "runtime. Subscribe at https://vibedna.ai/content-studio, then set your key as the "
        "CONTENT_STUDIO_LICENSE environment variable in this MCP's config."
    )


def _slug(text: str, n: int = 40) -> str:
    s = "".join(c if c.isalnum() else "-" for c in (text or "post").lower()).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return (s[:n] or "post")


def _style(brand: str, preset: str):
    """What the card engine should paint with: a preset name, or a brand's own colors.

    A brand names the same roles a preset does (background, glow, text, accent, particles),
    so the preset is the base and the brand paints over it. Anything the brand leaves unsaid,
    like the scrim or the fonts, stays as the preset had it.
    """
    if not brand:
        return preset
    b = br.get_brand(brand)
    base = dict(pe.STYLES.get(preset or "night", pe.STYLES["night"]))
    for k, v in (b.get("palette") or {}).items():
        if k in base:
            base[k] = tuple(v) if isinstance(v, list) else v
    base["glow_strength"] = b.get("glow_strength", base.get("glow_strength", 0.6))
    fonts = b.get("fonts") or {}
    if fonts.get("display"):
        base["title_font"] = fonts["display"]
    if fonts.get("mono"):
        base["mono_font"] = fonts["mono"]
    return base


def _out(name: str, ext: str) -> str:
    # Deterministic-ish, collision-safe filename from the content (no timestamp:
    # Date/random are avoided so the same input maps to the same file).
    base = _slug(name)
    p = _OUT_DIR / f"{base}.{ext}"
    i = 2
    while p.exists():
        p = _OUT_DIR / f"{base}-{i}.{ext}"
        i += 1
    return str(p)


@mcp.tool()
def render_post(text: str, mode: str = "card", size: str = "square", preset: str = "night",
                handle: str = "", query: str = "", image_path: str = "", source: str = "openverse",
                out_path: str = "", brand: str = "") -> str:
    """Render ONE image post and return its file path.

    text:      the line(s) to display (your AI writes this).
    mode:      "card" = 100% code-drawn (gradient + glow + texture + text, no source image).
               "stock" = fetch a photo (see source) or use your own image, then composite a
               scrim + text. NO image generation either way.
    size:      "square" (1080x1080), "portrait" (1080x1350), or "story" (1080x1920).
    preset:    "night" (default), "clean", or "warm".
    handle:    optional @handle drawn at the bottom.
    query:     search terms (mode="stock", when no image_path). With source="url" it is a
               direct image URL.
    image_path: use your own image (mode="stock").
    source:    where the image comes from (mode="stock"): vibegen | openverse (keyless) |
               pexels | unsplash | pixabay | url | library.
               "vibegen" DRAWS the background instead of fetching one: the generative
               engines paint it, so the art is yours and nobody else is posting it. The
               query picks the engine and its look, e.g. "still-flow seed=11
               palette=deep_teal". Same engine and seed, same art forever, so a campaign
               can be reproduced instead of re-rolled. Engines: still-flow, still-meshgrad,
               still-geometry, still-waves. Add "fx=<look>" for an effects look on top
               (mandala, dream, tunnel, glitch, quilt, liquid) and "fx_<name>=<value>" to
               tune one effect, e.g. "still-waves seed=3 fx=mandala fx_bloom=0.9".
               pexels/unsplash/pixabay need the matching API key env var.
    out_path:  where to write; default ~/.post-engine/out/<slug>.jpg
    brand:     one of your installed brands (list_brands), so the post comes out in your own
               colors and fonts instead of the shipped preset. Empty = the preset alone.
    """
    if brand:
        missing = br.missing_brand_message(brand)
        if missing:
            return "error: " + missing
    style = _style(brand, preset)
    out = out_path or _out(text, "jpg")
    if mode == "stock":
        if not query and not image_path:
            return "error: mode='stock' needs a query (or a direct URL) or an image_path"
        result = pe.render_stock(text, out, query=query or None, image_path=image_path or None,
                                 source=source, handle=handle, size=size, preset=style)
    else:
        result = pe.render_card(text, out, handle=handle, size=size, preset=style)
    if not _check_pro():
        comp.apply_free_limits(result)
        return result + "\n" + _FREE_NOTE
    return result


@mcp.tool()
def fetch_image(query: str, source: str = "openverse", size: str = "square", out_path: str = "") -> str:
    """Fetch ONE image (no text overlay) and return its file path. Use it to grab a
    background you then pass to render_post as image_path, or to build a stock library.

    query:  search terms, or a direct image URL when source="url".
    source: vibegen (drawn, not fetched: the generative engines paint it and the art is
            yours) | openverse (keyless, license-clean) | pexels | unsplash | pixabay | url.
            With vibegen the query is the recipe, e.g. "still-waves seed=3 palette=glacier",
            plus an optional effects look: "fx=mandala" (dream, tunnel, glitch, quilt, liquid).
            pexels/unsplash/pixabay need PEXELS_API_KEY / UNSPLASH_ACCESS_KEY / PIXABAY_API_KEY.
    size:   square | portrait | story (guides the orientation of the fetch).
    """
    out = out_path or _out(query if source != "url" else "fetched", "jpg")
    try:
        return pe.fetch_image(query, out, source=source, size=size)
    except Exception as e:
        return f"error fetching image: {e}"


@mcp.tool()
def render_carousel(slides: list, handle: str = "", size: str = "portrait", preset: str = "night",
                    mode: str = "card", query: str = "", source: str = "openverse", out_dir: str = "",
                    brand: str = "") -> str:
    """Render a multi-slide carousel and return the slide paths (one per slide).

    slides:  list of strings, first = cover. Each slide gets an i/N counter; the
             handle goes on the last slide as the call to action.
    size:    default "portrait" (the carousel size the feed favors).
    mode:    "card" draws every slide; "stock" pulls a photo per slide (query + source).
    source:  where each slide's image comes from when mode="stock": vibegen (draws it with
             the generative engines, one fresh piece per slide) | openverse | pexels |
             unsplash | pixabay | url | library.
    out_dir: default ~/.post-engine/out/<slug>-carousel/
    brand:   one of your installed brands (list_brands), so every slide comes out in your own
             colors and fonts instead of the shipped preset. Empty = the preset alone.
    """
    if not slides:
        return "error: carousel needs at least one slide"
    if brand:
        missing = br.missing_brand_message(brand)
        if missing:
            return "error: " + missing
    d = out_dir or str(_OUT_DIR / f"{_slug(slides[0])}-carousel")
    paths = pe.render_carousel(list(slides), d, handle=handle, size=size, preset=_style(brand, preset),
                               mode=mode, query=query or None, source=source)
    result = f"{len(paths)} slides:\n" + "\n".join(paths)
    if not _check_pro():
        for p in paths:
            comp.apply_free_limits(p)
        result += "\n" + _FREE_NOTE
    return result


@mcp.tool()
def render_reel(beats: list, music: str = "", secs_per: float = 0, size: str = "story",
                preset: str = "night", mode: str = "card", query: str = "", source: str = "openverse",
                out_path: str = "", brand: str = "") -> str:
    """[PRO] Render a vertical reel from text beats and return the .mp4 path.

    beats:    list of short lines, first = the hook (the opening seconds decide reach).
              Each beat becomes a card with a slow zoom.
    music:    optional path to a music bed. It never shortens the reel: the bed repeats to
              cover the video and fades out at the end.
    secs_per: 0 (default) gives each card the time its own text needs to be read, so a long
              card is not gone before it can be read. A number forces every card to that length.
    mode:     "card" (code-drawn) or "stock" (fetched photo per beat via query + source).
    source:   where each beat's image comes from when mode="stock": vibegen (drawn by the
              generative engines) | openverse | pexels | unsplash | pixabay | url | library.
    size:     default "story" (1080x1920). Needs ffmpeg (set FFMPEG_BIN if not on PATH).
    brand:    one of your installed brands (list_brands), so every beat comes out in your own
              colors and fonts instead of the shipped preset. Empty = the preset alone.
    """
    if not _check_pro():
        return _pro_upsell("Reels")
    if not beats:
        return "error: reel needs at least one beat"
    if brand:
        missing = br.missing_brand_message(brand)
        if missing:
            return "error: " + missing
    out = out_path or _out(beats[0], "mp4")
    try:
        return pe.render_reel(list(beats), out, music=music or None, secs_per=float(secs_per),
                              size=size, preset=_style(brand, preset), mode=mode,
                              query=query or None, source=source)
    except Exception as e:
        return f"error rendering reel: {e}"


@mcp.tool()
def list_styles() -> str:
    """List the available presets, sizes, and modes."""
    return (
        "presets: " + ", ".join(pe.STYLES.keys()) + "\n"
        "sizes:   " + ", ".join(f"{k} ({v[0]}x{v[1]})" for k, v in pe.SIZES.items()) + "\n"
        "modes:   card (code-drawn), stock (fetch/own/library photo + text)\n"
        "sources: " + ", ".join(list(pe._SOURCES) + ["file"]) + "\n"
        "output:  " + str(_OUT_DIR)
    )


# --- PRO layer-stack tools: the professional suite (documents, templates, brands) ---

@mcp.tool()
def render_template(template: str, fields: dict, brand: str = "", size: str = "", out_path: str = "") -> str:
    """Render a named TEMPLATE in a BRAND's look and return the file path. This is the
    fast path: pick a template + a brand, fill the fields, get a finished post.

    template: one of list_templates() (quote-card, editorial-quote, tips-list, carousel-cover,
              story-question, ...: call list_templates for all of them with their fields).
    fields:   the per-post content, e.g. {"quote": "..."} or {"title": "New drop"}. Every field
              has a default, so leave out what you do not need. Photo fields (photo, before,
              after, photo1...) take a sample name, an image URL or a path to your own file.
              For motiv / name-cover / quote-over-image / release-square / genre-thumb, an
              imported background is {"image": "/path/to/your.png"}; motiv also takes
              {"query":"...","source":"openverse"} to fetch, or
              {"source":"library","library":"/path/to/folder","query":"tag"} for your library.
    brand:    any brand from `list_brands` (default = the template's own pack). The library
              templates open in a style pack (editorial, bold, warm, mono); pass your own brand
              to restyle them. Your brands live in ~/.content-studio/brands/<name>.json.
    size:     square | portrait | story (default = the template's default).

    YOUR OWN TEMPLATES (the ones list_templates marks "yours") work here too, by id or name.
    Their fields are text1, text2... (list_templates shows the text each one had when saved),
    plus any photo field the template has. A field you leave out keeps its saved text. `size`
    re-renders the same layout at another size. They keep the colours they were saved with,
    so `brand` does not change them.
    """
    fields = fields or {}
    notes = []
    try:
        mine = None if template in tpl.TEMPLATES else tpl.find_user_template(template)
        if mine:
            unknown = [k for k in fields if k not in
                       {f["key"] for f in mine["fields"]} | set(tpl.photo_fields(mine["doc"]))]
            if unknown:
                keys = [f["key"] for f in mine["fields"]] + tpl.photo_fields(mine["doc"])
                notes.append(f"note: ignored fields this template does not have: {', '.join(unknown)} "
                             f"(it has {', '.join(keys) or 'none'})")
            if brand:
                notes.append("note: your own templates keep the colours they were saved with, so "
                             "brand was not applied (to get one in another brand, save a new "
                             "template with save_template(from_template=..., brand=...))")
            doc = tpl.build_user(mine, fields, size=size or None)
            first = next((str(v) for v in fields.values() if v), "post")
            label = f"{mine['slug']}-{first}"
        else:
            doc = tpl.build(template, fields, brand=brand or None, size=size or None)
            label = f"{template}-{fields.get('name') or fields.get('quote') or 'post'}"
    except Exception as e:
        return f"error building template: {e}"
    out = out_path or _out(label, "jpg")
    try:
        result = comp.render_document(doc, out)
    except Exception as e:
        return f"error rendering: {e}"
    if not _check_pro():
        comp.apply_free_limits(result)
        notes.append(_FREE_NOTE)
    return "\n".join([result] + notes)


@mcp.tool()
def render_document(document: dict, out_path: str = "") -> str:
    """Render a raw layer-stack DOCUMENT and return the file path. This is the full pro
    control: you pass the exact {size, layers:[...]} stack. Use list_layer_types() for the
    layer kinds + params. Content layers (solid/gradient/image/particles/shape/text) paint;
    adjustment layers (duotone/tint/grade/posterize/grain/scanlines/vignette/blur/bloom/
    chromatic) transform everything below them. Each layer takes optional opacity + blend. A
    text layer takes `"bold": true` for the font's bold."""
    if not document or "layers" not in document:
        return "error: document needs a 'layers' list (see list_layer_types)"
    out = out_path or _out("document", "jpg")
    try:
        result = comp.render_document(document, out)
    except Exception as e:
        return f"error rendering document: {e}"
    if not _check_pro():
        comp.apply_free_limits(result)
        return result + "\n" + _FREE_NOTE
    return result


@mcp.tool()
def render_reel_docs(documents: list, music: str = "", secs_per: float = 0,
                     size: str = "story", out_path: str = "") -> str:
    """[PRO] Render a vertical REEL from a list of layer DOCUMENTS (each a {size,layers} beat,
    first = the hook). Each beat is composited by the full engine, then shown with a slow zoom
    and concatenated, with an optional music bed. Needs ffmpeg.

    secs_per: 0 (default) holds each beat for the time its own text needs to be read.
    music:    never shortens the reel. The bed repeats to cover it and fades out at the end."""
    if not _check_pro():
        return _pro_upsell("Reels")
    if not documents:
        return "error: need at least one document"
    out = out_path or _out("reel", "mp4")
    try:
        return comp.render_reel(list(documents), out, music=music or None, secs_per=float(secs_per), size=size)
    except Exception as e:
        return f"error rendering reel: {e}"


@mcp.tool()
def render_template_reel(template: str, beats: list, brand: str = "", music: str = "",
                         secs_per: float = 0, size: str = "story", out_path: str = "") -> str:
    """[PRO] Render a REEL by building one document per beat from a TEMPLATE + BRAND. `beats` is
    a list of field dicts (one per beat), e.g. [{"quote": "Small steps, every day"},
    {"quote": "Done beats perfect"}]. First beat = the hook. One of the user's own templates
    works too, with its text1... fields per beat.

    secs_per: 0 (default) holds each beat for the time its own text needs to be read.
    music:    never shortens the reel. The bed repeats to cover it and fades out at the end."""
    if not _check_pro():
        return _pro_upsell("Reels")
    if not beats:
        return "error: need at least one beat (a list of field dicts)"
    try:
        docs = [tpl.build(template, b or {}, brand=brand or None, size=size) for b in beats]
    except Exception as e:
        return f"error building beats: {e}"
    out = out_path or _out(f"{template}-reel", "mp4")
    try:
        return comp.render_reel(docs, out, music=music or None, secs_per=float(secs_per), size=size)
    except Exception as e:
        return f"error rendering reel: {e}"


@mcp.tool()
def list_templates() -> str:
    """List the templates: id -> readable label, Instagram format, fields, photo fields and
    default brand/size. Photo fields take a sample name (coffee-window, kitchen-table,
    laptop-desk, linen-texture, notebooks-flatlay, ocean-horizon, plant-light, shelf-after,
    shelf-before, street-dusk, vase-stone), an image URL, or a path to your own file.

    The user's own templates are in the same list with "yours": true. Their fields are
    text1, text2..., and "saved_text" shows what each one said when it was saved, so you can
    tell which is the headline and which is the date. They live in the folder shown in "file"."""
    import json
    return json.dumps(tpl.list_templates(), indent=2, ensure_ascii=False)


def _layer_notes(doc):
    """Warnings for layer types this studio cannot draw (an effect not added on this machine)."""
    if not comp._EFFECTS_LOADED[0]:
        try:
            comp.load_effects()
        except Exception as e:
            comp.EFFECTS_REPORT.append(f"FAILED to read the effects file: {e}")
        comp._EFFECTS_LOADED[0] = True
    known = set(comp.CONTENT) | set(comp.ADJUST) | set(comp._CUSTOM_CONTENT) | set(comp._CUSTOM_ADJUST)
    return [f"warning: layer {i} is a '{l['type']}', which this studio cannot draw yet (add it "
            "with add_effect or remove the layer), so rendering will fail until then"
            for i, l in enumerate(doc["layers"], 1) if l.get("type") not in known]


def _saved_report(slug, path, t, notes, verb="saved"):
    lines = [f"{verb} '{t['name']}' as your template '{slug}' ({t['format']}, "
             f"{t['size'] if isinstance(t['size'], str) else '%dx%d' % tuple(t['size'])})",
             f"  file: {path}", "  fields (key = text it has now):"]
    lines += [f"    {f['key']} = {f['label']!r}" for f in t["fields"]] or ["    (no text layers)"]
    photos = tpl.photo_fields(t["doc"])
    if photos:
        lines.append("  photo fields: " + ", ".join(photos))
    example = t["fields"][0]["key"] if t["fields"] else "text1"
    lines.append(f"  render it: render_template(\"{slug}\", {{\"{example}\": \"...\"}})")
    return "\n".join(lines + notes + _layer_notes(t["doc"]))


@mcp.tool()
def save_template(name: str, template: dict = None, from_template: str = "", fields: dict = None,
                  brand: str = "", size: str = "", replace: bool = False) -> str:
    """Save a TEMPLATE of the user's own, so they can reuse a design with new words. It goes to
    ~/.content-studio/templates/<id>.json (or $CONTENT_STUDIO_HOME/templates/), the same file
    the web editor's "Save as my template" downloads, and then works in render_template,
    render_template_reel and studio_apply_template by its id or name.

    Two ways to give it the design:
    template:      a template file's contents ({"kind": "vibedna-template", "version": 1, "name",
                   "format", "size", "doc": {size, layers}, "fields"}) or just a document
                   {size, layers} like render_document takes. Every text layer becomes an
                   editable field, text1, text2... in layer order (a layer that already has a
                   "field" keeps it). To make a photo swappable too, give its image layer
                   "field": "photo1". Photos on this computer are embedded in the file, so the
                   template works anywhere, including the web editor.
    from_template: start from an existing template instead, built-in or yours, filled with
                   `fields` and drawn in `brand` at `size`. This is how to make "tips-list in my
                   colours, saved as Weekly tips": save_template("Weekly tips",
                   from_template="tips-list", brand="<their brand>", fields={"title": "..."}).

    fields:  with from_template, that template's fields; with `template`, new values by key
             (text1...) to put in before saving.
    replace: an existing template of theirs with the same name is only overwritten when True.
    Built-in names are reserved. Returns the id, the file and each field with its text."""
    if not name or not str(name).strip():
        return "error: give the template a name"
    try:
        size = tpl._check_size(size) if size else ""
        if from_template:
            if template:
                return "error: pass either template or from_template, not both"
            data = {"name": name, "doc": tpl.build(from_template, fields or {}, brand=brand or None,
                                                   size=size or None)}
            base = tpl.TEMPLATES.get(from_template)
            if base:
                data["format"] = base.get("format", "Feed post")
            else:
                mine = tpl.find_user_template(from_template)
                data["format"] = mine["format"] if mine else None
            slug, path, t, notes = tpl.save_user_template(name, data, replace=replace)
        else:
            if not template:
                return "error: pass the design as template (a template file or a {size, layers} document) or name one with from_template"
            data = dict(template)
            if size:
                if isinstance(data.get("doc"), dict):
                    data["doc"] = dict(data["doc"], size=size)
                    data.pop("size", None)
                else:
                    data["size"] = size  # a bare document
            slug, path, t, notes = tpl.save_user_template(name, data, replace=replace, fields=fields)
    except Exception as e:
        return f"error: {e}"
    return _saved_report(slug, path, t, notes)


@mcp.tool()
def import_template(path: str, name: str = "", replace: bool = False) -> str:
    """Add a template FILE to the user's templates: what they do after "Download" in the web
    editor, or with a template someone shared. `path` is the .json file. It is checked, its
    photos are kept inside it, and it is copied into ~/.content-studio/templates/, so the
    download can be deleted afterwards. `name` renames it; `replace` overwrites one of theirs
    with the same name."""
    import json
    src = os.path.expanduser(str(path or "").strip().strip('"'))
    if not os.path.isfile(src):
        return f"error: file not found: {src}"
    try:
        if os.path.getsize(src) > tpl._MAX_TEMPLATE_BYTES:
            return "error: this file is over 40 MB, too big for a template"
        with open(src, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        return f"error: this file is not a template (could not read it as JSON: {e})"
    stem = os.path.splitext(os.path.basename(src))[0]
    if not name and not (isinstance(data, dict) and data.get("name")):
        name = stem
    folder = os.path.normcase(os.path.abspath(tpl.templates_dir()))
    target = tpl.template_slug(name or data.get("name"))
    if (os.path.normcase(os.path.dirname(os.path.abspath(src))) == folder
            and target.lower() == stem.lower()):
        return f"'{src}' is already in your templates folder (list_templates shows it)"
    try:
        slug, out, t, notes = tpl.save_user_template(name, data, replace=replace,
                                                     base_dir=os.path.dirname(os.path.abspath(src)))
    except Exception as e:
        return f"error: {e}"
    return _saved_report(slug, out, t, notes, verb="imported")


@mcp.tool()
def delete_template(name: str) -> str:
    """Delete one of the user's own templates (by id or name). Built-in templates cannot be
    deleted. The file is removed for good, so confirm with the user first."""
    try:
        path = tpl.delete_user_template(name)
    except Exception as e:
        return f"error: {e}"
    return f"deleted your template '{name}' ({path})"


@mcp.tool()
def list_brands() -> str:
    """List the brand packs (their look drives any template)."""
    import json
    return json.dumps(br.list_brands(), indent=2, ensure_ascii=False)


@mcp.tool()
def list_layer_types() -> str:
    """List the compositor's layer kinds (content + adjustment) + image sources, for
    building raw documents with render_document."""
    import json
    return json.dumps(comp.layer_types(), indent=2)


# --- EXTENSIBILITY: no limits. Add fonts + brand-new effects per project. ---

@mcp.tool()
def list_fonts() -> str:
    """List the fonts in the user font library (usable by NAME in a text layer's `font`)."""
    return json.dumps(pe.list_fonts(), indent=2, ensure_ascii=False)


# What the render engine can load (post_engine._resolve_font / list_fonts), and the first
# bytes each real font file starts with.
_FONT_EXTS = (".ttf", ".otf", ".ttc")
_FONT_MAGIC = {b"\x00\x01\x00\x00": ".ttf", b"true": ".ttf", b"OTTO": ".otf", b"ttcf": ".ttc"}
_FONT_MAX_BYTES = 20 * 1024 * 1024


@mcp.tool()
def add_font(url: str, name: str = "", share: bool = False) -> str:
    """[PRO] Download a .ttf/.otf/.ttc font from an http(s) URL into the local font library
    and make it usable by NAME in a text layer's `font`. This is 'the AI grabs the exact font
    the user wants'.

    The download must really be a font (its first bytes are checked) and at most 20 MB,
    otherwise nothing is saved. `name` only names the file inside the font library.

    share: False (default) keeps the font on this machine only. True ALSO uploads it to the
           browser studio (STUDIO_URL, vibedna.ai by default) so the live editor preview can
           load it. Only share a font whose licence allows redistribution; many commercial
           fonts forbid it."""
    if not _check_pro():
        return _pro_upsell("Custom fonts")
    import base64, re, urllib.parse, urllib.request
    if urllib.parse.urlsplit(url or "").scheme.lower() not in ("http", "https"):
        return "error: add_font needs an http:// or https:// URL"
    root = pe._fonts_dir(); os.makedirs(root, exist_ok=True)
    raw_name = name or urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    stem, ext = os.path.splitext(os.path.basename(raw_name.replace("\\", "/")))
    ext = ext.lower()
    if ext and ext not in _FONT_EXTS:
        return f"error: '{ext}' is not a font this engine loads (use {', '.join(_FONT_EXTS)})"
    stem = re.sub(r"[^A-Za-z0-9 ._-]", "_", stem).strip(" .")
    if not stem:
        return "error: could not work out a file name; pass name='MyFont'"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VibeDNA-PostEngine/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if int(r.headers.get("Content-Length") or 0) > _FONT_MAX_BYTES:
                return "error: that file is over 20 MB, which is not a font. Nothing was saved."
            raw = r.read(_FONT_MAX_BYTES + 1)
    except Exception as e:
        return f"error downloading font: {e}"
    if len(raw) > _FONT_MAX_BYTES:
        return "error: that file is over 20 MB, which is not a font. Nothing was saved."
    kind = _FONT_MAGIC.get(raw[:4])
    if not kind:
        return ("error: that URL did not return a TrueType/OpenType font (checked its first "
                "bytes). Nothing was saved.")
    ext = ext or kind
    font_name = stem
    dest = os.path.join(root, stem + ext)
    if os.path.dirname(os.path.abspath(dest)) != os.path.abspath(root):
        return "error: that name points outside the font library"
    try:
        with open(dest, "wb") as f:
            f.write(raw)
    except Exception as e:
        return f"error saving font: {e}"
    msg = f"downloaded -> {dest}. Use it with font='{font_name}' in a text layer."
    if not share:
        return msg + (" Kept on this machine only (share=True would also upload it to the "
                      "browser studio, if its licence allows redistribution).")
    try:
        b64 = base64.b64encode(raw).decode()
        studio = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")
        data = json.dumps({"name": font_name, "ext": ext.lstrip("."), "b64": b64}).encode()
        req = urllib.request.Request(studio + "/api/studio/fonts", method="POST", data=data,
                                     headers={"Content-Type": "application/json",
                                              "x-studio-token": os.environ.get("STUDIO_TOKEN", "")})
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        msg += " Also uploaded to the editor (shows in the live preview when connected)."
    except Exception as e:
        msg += f" (editor upload failed: {e})"
    return msg


@mcp.tool()
def list_effects() -> str:
    """List every layer type, including custom project effects added via add_effect, and any
    saved effect code that was refused by the safety check or failed to load."""
    if not comp._EFFECTS_LOADED[0]:
        try:
            comp.load_effects()
        except Exception as e:
            comp.EFFECTS_REPORT.append(f"FAILED to read the effects file: {e}")
        comp._EFFECTS_LOADED[0] = True
    lt = comp.layer_types()
    lt["custom_content"] = list(comp._CUSTOM_CONTENT)
    lt["custom_adjust"] = list(comp._CUSTOM_ADJUST)
    if comp.EFFECTS_REPORT:
        lt["not_loaded"] = list(comp.EFFECTS_REPORT)
    return json.dumps(lt, indent=2)


@mcp.tool()
def add_effect(name: str, kind: str, python: str, js: str = "") -> str:
    """[PRO] Add a BRAND-NEW effect (a new layer type) that shows in BOTH the final render (Python)
    AND the live editor preview (JS twin). The no-limits hook: if the 16 built-in effects
    can't do what the user wants, write it.

    name:   the layer type, e.g. "sepia" (use it as {"type":"sepia"} in a document). Letters,
            digits and underscores, starting with a letter.
    kind:   "content" (paints a layer) or "adjust" (transforms everything below it).
    python: the function BODY only. adjust args = (base, layer, dims) and RETURN an RGBA
            Image. content args = (layer, dims) and RETURN an RGBA Image. In scope: Image,
            ImageDraw, ImageFilter, ImageOps, ImageChops, ImageEnhance, load_font(name, size),
            basic builtins, and `import math` / `random` / `colorsys`. Example body for a
            sepia adjust: `return ImageOps.colorize(base.convert('L'),(40,22,12),(255,232,196)).convert('RGBA')`
    js:     (recommended) the editor twin, a function EXPRESSION. adjust: (data,W,H,layer)
            that mutates the RGBA Uint8ClampedArray in place. content: (W,H,layer) returning
            a canvas or ImageData. Without a twin the effect still renders in the Python/MCP
            path but won't appear in the browser editor's live preview.

    SAFETY: effect code is image math only. Before it is saved, and again every time the
    effects file loads, it is checked: no other imports, no file, network or system access,
    no eval/exec/open/getattr, no names starting with an underscore after a dot. Code that
    fails the check is refused and never runs. Persists + auto-loads."""
    if not _check_pro():
        return _pro_upsell("Custom effects")
    import re
    if kind not in ("content", "adjust"):
        return "error: kind must be 'content' or 'adjust'"
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}", name or ""):
        return "error: name must be letters, digits and underscores, starting with a letter"
    sig = "base, layer, dims" if kind == "adjust" else "layer, dims"
    body = "\n".join("    " + ln for ln in (python or "").splitlines()) or "    pass"
    snippet = f"def _fx_{name}({sig}):\n{body}\nregister_effect({name!r}, _fx_{name}, {kind!r})\n"
    problems = comp.validate_effect_source(snippet)
    if problems:
        return ("error: effect refused by the safety check, nothing was saved. Effect code may "
                "use Pillow, load_font, math, random and colorsys only, with no file, network or "
                "system access. Problems (line 1 is the def line):\n  " + "\n  ".join(problems))
    eff = os.environ.get("POST_ENGINE_EFFECTS") or str(Path.home() / ".post-engine" / "effects.py")
    os.makedirs(os.path.dirname(eff), exist_ok=True)
    try:
        with open(eff, "a", encoding="utf-8") as f:
            f.write(f"\n\n# --- add_effect: {name} ---\n" + snippet)
        comp.load_effects(eff)
        comp._EFFECTS_LOADED[0] = True
    except Exception as e:
        return f"error registering Python effect: {e}"
    if name not in (comp._CUSTOM_ADJUST if kind == "adjust" else comp._CUSTOM_CONTENT):
        return (f"error: effect '{name}' was saved to {eff} but did not load:\n  "
                + "\n  ".join(comp.EFFECTS_REPORT))
    msg = (f"effect '{name}' ({kind}) passed the safety check (image math only: no imports "
           f"beyond math, random, colorsys and Pillow, no file, network or system access), "
           f"was saved to {eff} and is loaded. It is re-checked every time that file loads.")
    if comp.EFFECTS_REPORT:
        msg += ("\nOther code in that file was NOT loaded:\n  " + "\n  ".join(comp.EFFECTS_REPORT))
    if js:
        try:
            import urllib.request
            base = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")
            data = json.dumps({"name": name, "kind": kind, "js": js}).encode()
            req = urllib.request.Request(base + "/api/studio/effects", method="POST", data=data,
                                         headers={"Content-Type": "application/json",
                                                  "x-studio-token": os.environ.get("STUDIO_TOKEN", "")})
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read()
            msg += " JS twin pushed to the editor (it shows live when the editor is connected)."
        except Exception as e:
            msg += f" (JS twin push failed: {e})"
    return msg


# --- STUDIO BRIDGE: drive the live web editor from chat (same document model) ---
# The editor at vibedna.ai/content-studio and these tools share one document via
# /api/studio/state. Config: STUDIO_URL (default https://vibedna.ai) + STUDIO_TOKEN.

def _studio_url():
    return os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/") + "/api/studio/state"


def _studio_req(method, body=None):
    import urllib.request, urllib.error
    tok = os.environ.get("STUDIO_TOKEN", "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_studio_url(), method=method, data=data,
                                 headers={"Content-Type": "application/json", "x-studio-token": tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"null")


@mcp.tool()
def studio_get() -> str:
    """Read the current Content Studio document (the live editor's layer stack)."""
    try:
        return json.dumps(_studio_req("GET"), indent=2, ensure_ascii=False)
    except Exception as e:
        return f"error: {e} (set STUDIO_TOKEN, and STUDIO_URL if not vibedna.ai)"


@mcp.tool()
def studio_set(document: dict) -> str:
    """Replace the live editor document. document = {size, layers:[...]} (list_layer_types)."""
    if not document or "layers" not in document:
        return "error: document needs a 'layers' list"
    try:
        r = _studio_req("POST", {"document": document})
        return f"editor updated, version {r.get('version')}"
    except Exception as e:
        return f"error: {e}"


ANIMATIONS = ("fade", "slide-up", "slide-down", "slide-left", "slide-right", "pop", "zoom", "wipe",
              "typewriter", "letters", "words")


def _animate(document: dict) -> dict:
    """The editor's "Animate this post", as data: backgrounds stay put, every other visible layer
    enters in order (the biggest text letter by letter), and the piece becomes a short video."""
    content = {"solid", "gradient", "image", "video", "particles", "shape", "text"}
    layers = [dict(l) for l in document.get("layers", [])]

    def background(l):
        return not l.get("box") and l.get("type") in ("gradient", "solid", "particles", "image", "video")

    head, biggest = -1, 0.0
    for i, l in enumerate(layers):
        if l.get("type") == "text" and l.get("visible", True) is not False and float(l.get("size") or 0) > biggest:
            head, biggest = i, float(l.get("size") or 0)
    k = 0
    for i, l in enumerate(layers):
        if l.get("visible", True) is False or l.get("type") not in content or background(l):
            continue
        l["at"] = round(0.2 + 0.18 * k, 2)
        k += 1
        kind = ("letters" if i == head else "slide-up" if l["type"] == "text"
                else "zoom" if l["type"] in ("image", "video") else "wipe")
        l["anim"] = {"in": {"type": kind, "dur": 1.1 if i == head else 0.6}}
    out = dict(document, layers=layers)
    out["duration"] = max(float(document.get("duration") or 0), 6.0, 0.2 + 0.18 * k + 2.5)
    out.setdefault("fps", 30)
    return out


@mcp.tool()
def animate_document(document: dict) -> str:
    """Give a document entrance animations, the way the web editor's "Animate this post" does,
    and return it as JSON: backgrounds stay put, every other layer enters in order, the biggest
    text letter by letter, and the piece becomes a 6+ second video. Open the result in the web
    editor (studio_set, or import it as a template file) to play it and export the MP4.

    To animate one layer by hand, give it `anim` = {"in": {"type": T, "dur": seconds},
    "out": {"type": T, "dur": seconds}} and optionally `at` (the second it appears). T is one of
    fade, slide-up, slide-down, slide-left, slide-right, pop, zoom, wipe, or for text only
    typewriter, letters, words. Animation plays in a video piece (one with `duration`); still
    renders (render_document) show every layer in its final place."""
    if not document or "layers" not in document:
        return "error: document needs a 'layers' list"
    return json.dumps(_animate(document), ensure_ascii=False)


@mcp.tool()
def studio_animate() -> str:
    """Animate the document open in the live editor (same as its "Animate this post" button)."""
    try:
        doc = (_studio_req("GET").get("document")) or {}
        if not doc.get("layers"):
            return "error: the editor has no layers to animate"
        r = _studio_req("POST", {"document": _animate(doc)})
        return f"editor document animated, version {r.get('version')}. Press play in the editor to see it."
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def studio_set_layer(index: int, patch: dict) -> str:
    """Patch ONE layer (by index) in the live editor document. To animate it, patch `anim`
    (see animate_document for the format) and `at`."""
    try:
        doc = (_studio_req("GET").get("document")) or {"size": "square", "layers": []}
        layers = doc.get("layers", [])
        if index < 0 or index >= len(layers):
            return f"error: index {index} out of range (0..{len(layers) - 1})"
        layers[index] = {**layers[index], **(patch or {})}
        r = _studio_req("POST", {"document": doc})
        return f"layer {index} patched, version {r.get('version')}"
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def studio_add_layer(layer: dict) -> str:
    """Append a layer to the live editor document."""
    try:
        doc = (_studio_req("GET").get("document")) or {"size": "square", "layers": []}
        doc.setdefault("layers", []).append(layer)
        r = _studio_req("POST", {"document": doc})
        return f"layer added ({len(doc['layers'])} total), version {r.get('version')}"
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def list_finishes() -> str:
    """The named looks you can put on top of a piece, and what each one does."""
    return "\n".join("%-8s %s" % (k, v) for k, v in fin.describe().items())


@mcp.tool()
def apply_finish(name: str, replace: bool = True) -> str:
    """Put a named look on the live editor document: glitch, vhs, neon, elegant.

    A finish is a STACK of mild adjustments in a deliberate order, not one filter, and for a
    piece with time it MOVES: the glitch stack hits hard and briefly every few seconds instead
    of sitting there. `replace=True` clears any previous finish first, which is what you want
    while trying looks: stacking two of them just muddies the piece and looks like a bug.
    """
    try:
        doc = (_studio_req("GET").get("document")) or {"size": "square", "layers": []}
        layers = doc.setdefault("layers", [])
        adjust_types = {"chromatic", "scanlines", "grain", "bloom", "posterize", "vignette", "tint", "grade", "blur"}
        if replace:
            layers = [c for c in layers if c.get("type") not in adjust_types]
        layers = layers + fin.apply(name, doc.get("duration") or 0)
        doc["layers"] = layers
        r = _studio_req("POST", {"document": doc})
        return "finish '%s' applied (%d layers), version %s" % (name, len(layers), r.get("version"))
    except Exception as e:
        return f"error: {e}"


# --- PROJECTS: a saved, named piece that can be reopened ---
# The live editor holds ONE document. A project gives a piece a stable id, so it can be
# reopened and edited later instead of rebuilt from an exported file.

def _projects_url():
    return os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/") + "/api/studio/projects"


def _projects_req(method, body=None, query=""):
    import urllib.request
    tok = os.environ.get("STUDIO_TOKEN", "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_projects_url() + query, method=method, data=data,
                                 headers={"Content-Type": "application/json", "x-studio-token": tok})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read() or b"null")


@mcp.tool()
def studio_list_projects() -> str:
    """List the saved Content Studio projects, newest first."""
    try:
        ps = (_projects_req("GET") or {}).get("projects", [])
        if not ps:
            return "no saved projects yet. Save the live canvas with studio_save_project."
        return "\n".join("%-34s %s%s" % (p.get("id"), p.get("name"),
                                         "  [%s]" % p["kind"] if p.get("kind") else "")
                         for p in ps)
    except Exception as e:
        return f"error: {e} (set STUDIO_TOKEN, and STUDIO_URL if not vibedna.ai)"


@mcp.tool()
def studio_save_project(name: str, kind: str = "", origin: str = "", document: dict = None) -> str:
    """Save the live canvas as a named project, so the piece can be reopened later.

    Saving the CANVAS by default is deliberate: what you see is what gets kept. Pass `document`
    only when saving a piece you built without putting it on screen.

    `origin` records what produced it (a generator, a batch), so the trail back survives."""
    try:
        doc = document if (document and document.get("layers")) else \
            (_studio_req("GET") or {}).get("document")
        if not doc or not doc.get("layers"):
            return "error: the canvas is empty, so there is nothing to save"
        r = _projects_req("POST", {"name": name, "kind": kind, "origin": origin, "document": doc})
        if r.get("error"):
            return "error: %s" % r["error"]
        base = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")
        return ("saved '%s' as %s (%d projects)\n  reopen it at %s/content-studio?p=%s"
                % (r.get("name"), r.get("id"), r.get("total", 0), base, r.get("id")))
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def studio_open_project(id: str) -> str:
    """Load a saved project onto the live canvas, ready to edit."""
    import urllib.parse
    try:
        p = _projects_req("GET", query="?id=" + urllib.parse.quote(id))
        if p.get("error"):
            return "error: %s ('%s')" % (p["error"], id)
        doc = p.get("document") or {}
        if not doc.get("layers"):
            return "error: that project has no layers"
        _studio_req("POST", {"document": doc})
        return ("'%s' is on the canvas: %d layers, last saved %s"
                % (p.get("name"), len(doc["layers"]), (p.get("updated") or "")[:16]))
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def studio_apply_template(template: str, brand: str = "", fields: dict = None) -> str:
    """Load a TEMPLATE (in a BRAND) into the live editor as the current document. One of the
    user's own templates works too (by id or name, with text1... fields)."""
    try:
        doc = tpl.build(template, fields or {}, brand=brand or None)
        r = _studio_req("POST", {"document": doc})
        return f"template '{template}' loaded into the editor, version {r.get('version')}"
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def studio_feed_set(drip: str = "", view: str = "") -> str:
    """Drive the studio's FEED grid from chat: which project's queue is on screen and
    how it is read.

    drip: the project/queue name, e.g. "my-brand-feed". Empty leaves it as is.
    view: "instagram" (three per row, square), "pinterest" (columns of varying
          height), "tiktok" (three per row, tall) or "youtube" (the channel's
          videos tab: 16:9 with the title below, only slots going out to YouTube).
          Empty leaves it as is.

    Same shared state the Compose pane uses, so the editor keeps its document while
    the grid changes. The studio must have chat connected for it to land."""
    view = (view or "").strip().lower()
    if view and view not in ("instagram", "pinterest", "tiktok", "youtube"):
        return "error: view must be instagram, pinterest, tiktok or youtube"
    feed = {}
    if drip.strip():
        feed["drip"] = drip.strip()
    if view:
        feed["view"] = view
    if not feed:
        return "error: pass a drip and/or a view"
    try:
        r = _studio_req("POST", {"feed": feed})
        return f"studio feed set to {feed} (version {r.get('version')})"
    except Exception as e:
        return f"error: {e} (set STUDIO_TOKEN, and STUDIO_URL if not vibedna.ai)"


@mcp.tool()
def studio_feed_get() -> str:
    """Read what the studio's FEED grid is showing right now (project + view)."""
    try:
        st = _studio_req("GET") or {}
        feed = st.get("feed") or {}
        if not feed:
            return "the studio feed grid has no project selected yet"
        return json.dumps({"drip": feed.get("drip"), "view": feed.get("view"),
                           "state_version": st.get("version")}, indent=2)
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def studio_render(out_path: str = "") -> str:
    """Render the CURRENT editor document with the local engine so you can SEE it (returns
    the image path). Resolves programmatic/fetch/library/file layers; browser-imported
    images (object URLs) do not resolve outside the browser."""
    try:
        doc = _studio_req("GET").get("document")
    except Exception as e:
        return f"error reading editor state: {e}"
    if not doc:
        return "the editor is empty"
    out = out_path or _out("studio", "jpg")
    try:
        return comp.render_document(doc, out)
    except Exception as e:
        return f"error rendering: {e}"


# --- VIDEO: existing footage in, feed-ready vertical out ---
# The rest of this server paints stills and animates them with a zoom. These tools take
# FOOTAGE. Every default here comes from measuring real output; video_engine.py carries
# the reasoning next to the code that enforces it.

@mcp.tool()
def render_vertical(source: str, title: str = "", line: str = "", brand: str = "default",
                    logo: str = "", domain: str = "", bed: str = "", bed_start: float = 0.0,
                    start: float = 0.0, duration: float = 15.0, crossfade: float = 2.0,
                    mirror: str = "", veil: float = -1.0, out_path: str = "",
                    fps: int = 30) -> str:
    """[PRO] Turn existing footage into a feed-ready vertical, and report every measurement.

    Built for ambient/landscape pieces that have to survive a scroll:

      SEAMLESS LOOP - takes duration+crossfade seconds and crossfades the tail onto the
        head, so the first and last frames are the same instant. Replays count as watch
        time on Reels and Shorts, so an invisible loop is worth more than any overlay.
      THREE MOMENTS - title, then a line, then the brand mark, one at a time with clean
        image between them. Their motion is BAKED frame by frame in sub-pixel, because
        ffmpeg's overlay rounds to whole pixels and would make a slow drift stutter.
      ADAPTIVE VEIL - each background is measured and given exactly the shade its own
        luminance needs to clear 3:1. Pass veil>=0 to force it, veil=-1 to measure.

    source:   any video file. bed: optional audio (the piece takes a window of it, loops
              it to match, and normalises to -16 LUFS). Give each piece a different
              bed_start so a series does not sound identical.
    mirror:   "" or "h-left" (mirrors the half-strip left of the axis; reproduces a
              mirrored film's look from the pristine source instead of its render).
    line:     one string, or use " / " to split it into stacked lines.
    fps:      30 (default). Instagram rejects some vertical reels above 30 fps
              (ProcessingFailedError); use 60 only for a destination known to accept it.
    """
    if not _check_pro():
        return _pro_upsell("Video")
    if not os.path.exists(source):
        return f"error: no such source: {source}"
    parts = [p.strip() for p in line.split(" / ")] if " / " in line else (line or "")
    out = out_path or _out(title or os.path.basename(source), "mp4")
    try:
        rep = ve.render_ambient_vertical(
            source, out, title=title, line=parts, brand=brand, logo=logo,
            domain=(domain or None), bed=bed, bed_start=float(bed_start),
            start=float(start), duration=float(duration), crossfade=float(crossfade),
            mirror=mirror, veil=(None if veil < 0 else float(veil)), fps=int(fps))
    except Exception as e:
        return f"error rendering vertical: {e}"
    brand_note = br.missing_brand_message(brand)
    marks = " | ".join("%s %.2f:1%s" % (k, v["ratio"], "" if v["ok"] else " WEAK")
                       for k, v in rep["marks"].items())
    seam = rep["loop_seam"]
    return (f"{rep['out']}\n"
            f"  marks     {marks}   (3:1 is the bar for large type)\n"
            f"  veil      {rep['veil']}   (0 = the background needed none)\n"
            f"  loop      seam {seam['seam']} vs budget {seam['budget']} "
            f"(frame step {seam['frame_to_frame']} + codec noise)"
            f"  ->  {'invisible' if seam['invisible'] else 'VISIBLE, raise the crossfade'}\n"
            f"  video     {rep['result']['width']}x{rep['result']['height']} "
            f"@{rep['result']['fps']:.0f}fps  {rep['result']['duration']:.1f}s  "
            f"audio={'yes' if rep['result']['has_audio'] else 'NO'}"
            + (f"\n  brand     {brand_note}; used the neutral default look" if brand_note else ""))


# --- the same edit over many clips ---
# A series is ONE edit repeated over N clips: the same brand mark, the same closing
# domain, only the footage changes.
#
# WHERE IT RUNS. Footage is heavy and usually lives where it was rendered, not on the
# laptop driving the studio. `where="box"` runs the SAME engine on that machine over ssh,
# so nothing is copied back and forth. The host comes from POST_ENGINE_BOX_SSH and the
# engine's directory from POST_ENGINE_BOX_HOME; no default points at any machine.
def _box_ssh():
    # Settings come from the environment, falling back to ~/.post-engine/box.json, so the
    # box can be configured without restarting the MCP with new env vars. Env wins.
    host = os.environ.get("POST_ENGINE_BOX_SSH", "").strip()
    home = os.environ.get("POST_ENGINE_BOX_HOME", "").strip()
    py = os.environ.get("POST_ENGINE_BOX_PYTHON", "").strip()
    if not host or not home:
        f = Path(os.environ.get("POST_ENGINE_BOX_CONFIG",
                                str(Path.home() / ".post-engine" / "box.json")))
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            host = host or str(c.get("ssh", "")).strip()
            home = home or str(c.get("home", "")).strip()
            py = py or str(c.get("python", "")).strip()
        except Exception:
            pass
    return host, home, py or "python3"


_BATCH_REMOTE = r'''
import json, os, sys
sys.path.insert(0, %(home)r)
import video_engine as ve
plan = json.loads(sys.stdin.read())
for job in plan["jobs"]:
    try:
        # honour skip_done on the box too, so an interrupted remote run resumes instead of
        # redoing every clip.
        if plan.get("skip_done") and os.path.exists(job["out"]) and os.path.getsize(job["out"]) > 10000:
            print(json.dumps({"out": job["out"], "skipped": True}), flush=True)
            continue
        dur = job.get("duration") or 0
        if not dur:
            dur = round(ve._ffprobe(job["source"])["duration"] - plan["crossfade"] - 0.05, 2)
        rep = ve.render_ambient_vertical(
            job["source"], job["out"], brand=plan["brand"], logo=plan["logo"],
            domain=(plan["domain"] or None), duration=float(dur),
            crossfade=float(plan["crossfade"]), bed=plan["bed"],
            bed_start=float(job.get("bed_start") or 0),
            veil=(None if plan["veil"] < 0 else float(plan["veil"])),
            fps=int(plan.get("fps") or 30))
        print(json.dumps({"out": rep["out"], "secs": rep["result"]["duration"],
                          "audio": rep["result"]["has_audio"],
                          "loop_ok": rep["loop_seam"]["invisible"]}), flush=True)
    except Exception as e:
        print(json.dumps({"out": job["out"], "error": str(e)[:160]}), flush=True)
'''


@mcp.tool()
def render_vertical_batch(sources: list, logo: str = "", brand: str = "default",
                          domain: str = "", duration: float = 0.0, crossfade: float = 2.0,
                          out_dir: str = "", veil: float = -1.0, where: str = "local",
                          skip_done: bool = True, bed: str = "", bed_start: float = 0.0,
                          bed_step: float = 0.0, fps: int = 30) -> str:
    """[PRO] Put the SAME closing mark on many clips in one call, and report each one.

    A series is one edit over N clips. This runs `render_vertical`'s engine once per clip
    with identical settings, so a set of fifty comes out consistent by construction rather
    than by remembering the same numbers fifty times.

    sources:    list of video paths. Paths are read on whichever machine `where` picks.
    logo:       the mark to close on. Leave title/line out entirely: a clip competing in a
                feed is carried by its image, and the words belong in the caption.
    duration:   0 (default) fits EACH clip to its own length (source - crossfade), so a
                12s clip and a 20s clip both work in one run. A number forces all of them.
    where:      "local", or "box" to run on the machine that holds the footage, over ssh
                (POST_ENGINE_BOX_SSH + POST_ENGINE_BOX_HOME). Nothing is copied either way.
    skip_done:  leaves clips that already have an output alone, so a run that dies halfway
                resumes instead of redoing everything.
    bed:        music for clips that arrive silent. Footage cut without an audio track comes
                out mute, and a mute ambient clip is worthless: this is the difference
                between a series that can be published and one that cannot.
    bed_step:   seconds to advance the bed for EACH clip (bed_start + step * index). A set
                cut from one track and started at the same second sounds like the same clip
                over and over. Leave at 0 to start them all at bed_start.
    fps:        30 (default), the rate Instagram accepts for vertical reels; 60 only for a
                destination known to accept it.

    Returns one line per clip with its length, whether it kept its sound, and whether its
    loop is invisible. Read the sound column: silent output is the failure that looks like
    success.
    """
    if not _check_pro():
        return _pro_upsell("Video")
    if not sources:
        return "error: no sources given"
    # Paths are joined with the separator of the machine that WRITES the files, not this one:
    # os.path.join on Windows would build "folder\clip.mp4" names on a Linux box, and the run
    # would report success with every file in the wrong place.
    import posixpath
    pathmod = posixpath if where == "box" else os.path
    base = lambda p: p.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    dest = out_dir or pathmod.join(str(sources[0]).replace("\\", "/").rsplit("/", 1)[0], "sealed")
    jobs = [{"source": s, "out": pathmod.join(dest, base(s)), "duration": duration,
             "bed_start": bed_start + bed_step * i} for i, s in enumerate(sources)]

    if where == "box":
        host, home, py = _box_ssh()
        if not host or not home:
            return ("error: no box configured. Set POST_ENGINE_BOX_SSH (user@host or an ssh "
                    "config alias) and POST_ENGINE_BOX_HOME (the directory holding "
                    "video_engine.py there), or write them once to ~/.post-engine/box.json as "
                    '{"ssh": ..., "home": ..., "python": ...}')
        plan = {"jobs": jobs, "brand": brand, "logo": logo, "domain": domain,
                "crossfade": crossfade, "veil": veil, "bed": bed, "skip_done": bool(skip_done),
                "fps": int(fps)}
        prog = _BATCH_REMOTE % {"home": home}
        cmd = ["ssh", host, "mkdir -p %s && %s -c %s" % (shlex.quote(dest), shlex.quote(py),
                                                         shlex.quote(prog))]
        try:
            r = subprocess.run(cmd, input=json.dumps(plan), capture_output=True, text=True,
                               timeout=60 * 60 * 6)
        except Exception as e:
            return "error reaching the box: %s" % str(e)[:200]
        lines = [l for l in (r.stdout or "").splitlines() if l.startswith("{")]
        if not lines:
            return "error on the box: %s" % (r.stderr or "no output")[-400:]
        results = [json.loads(l) for l in lines]
    else:
        os.makedirs(dest, exist_ok=True)
        results = []
        for j in jobs:
            if skip_done and os.path.exists(j["out"]):
                results.append({"out": j["out"], "skipped": True})
                continue
            try:
                dur = j["duration"] or round(
                    ve._ffprobe(j["source"])["duration"] - crossfade - 0.05, 2)
                rep = ve.render_ambient_vertical(
                    j["source"], j["out"], brand=brand, logo=logo,
                    domain=(domain or None), duration=float(dur), crossfade=float(crossfade),
                    bed=bed, bed_start=float(j.get("bed_start") or 0),
                    veil=(None if veil < 0 else float(veil)), fps=int(fps))
                results.append({"out": rep["out"], "secs": rep["result"]["duration"],
                                "audio": rep["result"]["has_audio"],
                                "loop_ok": rep["loop_seam"]["invisible"]})
            except Exception as e:
                results.append({"out": j["out"], "error": str(e)[:160]})

    ok = [r for r in results if not r.get("error") and not r.get("skipped")]
    bad = [r for r in results if r.get("error")]
    out = ["%d done | %d failed | %d already there  ->  %s"
           % (len(ok), len(bad), len(results) - len(ok) - len(bad), dest)]
    brand_note = br.missing_brand_message(brand) if where != "box" else ""
    if brand_note:
        out.append("  brand   %s; used the neutral default look" % brand_note)
    for r in results:
        if r.get("error"):
            out.append("  FAILED  %s   %s" % (os.path.basename(r["out"]), r["error"]))
        elif r.get("skipped"):
            out.append("  kept    %s" % os.path.basename(r["out"]))
        else:
            out.append("  ok      %-40s %4.1fs  sound=%s  loop=%s"
                       % (os.path.basename(r["out"]), r["secs"],
                          "yes" if r["audio"] else "NO",
                          "invisible" if r["loop_ok"] else "VISIBLE"))
    return "\n".join(out)


@mcp.tool()
def verify_vertical(path: str) -> str:
    """[PRO] Measure a finished vertical: how visible its loop's cut is, and whether it
    carries sound at all.

    The loop is judged against the CODEC'S OWN NOISE, not against the frame-to-frame
    change: two independently encoded frames differ by ~1.5 even when they show the same
    instant, so comparing to the frame step makes a perfect loop look five times too big.
    """
    if not _check_pro():
        return _pro_upsell("Video")
    if not os.path.exists(path):
        return f"error: no such file: {path}"
    try:
        seam = ve.loop_seam(path)
        info = ve._ffprobe(path)
    except Exception as e:
        return f"error verifying: {e}"
    return (f"{path}\n"
            f"  loop      seam {seam['seam']} vs budget {seam['budget']} "
            f"(frame step {seam['frame_to_frame']} + codec noise)  ->  "
            f"{'invisible' if seam['invisible'] else 'VISIBLE'}\n"
            f"  video     {info['width']}x{info['height']} @{info['fps']:.0f}fps  "
            f"{info['duration']:.1f}s  audio={'yes' if info['has_audio'] else 'NO'}")


@mcp.tool()
def check_distinct(paths: list) -> str:
    """[PRO] Are these clips actually different scenes, or is the same one repeating?

    Measured IN COLOUR. Grey gives false duplicates: a misty meadow and a lavender field
    score 0.84 in grey because they share the structure (bright above, texture below) and
    grey throws away the hue that separates them. Real duplicates score 0.91 and up.

    Worth running before promising anyone a number of pieces: a ten-minute film usually
    REPEATS its shots to fill the length, so counting blocks is not counting scenes.
    """
    if not _check_pro():
        return _pro_upsell("Video")
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        return "error: missing files: " + ", ".join(missing)
    if len(paths) < 2:
        return "error: needs at least two clips to compare"
    try:
        d = ve.distinctness(list(paths))
    except Exception as e:
        return f"error comparing: {e}"
    i, j = d["worst_pair"]
    return (f"  closest pair: {os.path.basename(paths[i])} and {os.path.basename(paths[j])}"
            f"  ->  {d['worst_correlation']}\n"
            f"  {'all distinct (nothing above 0.80)' if d['all_distinct'] else 'THAT PAIR REPEATS'}")


@mcp.tool()
def render_thumbnail(frame: str, title: str, brand: str = "default", eyebrow: str = "",
                     out_path: str = "") -> str:
    """[PRO] A YouTube thumbnail in the brand's idiom: full-bleed image, big centred serif,
    open tracking, no arrows and no red circles.

    Two things are measured rather than chosen: the POINT SIZE is fitted to the available
    width (so a long title never touches the edges), and the TITLE'S BAND is the darkest
    strip of the upper third (white over a bright sky can drop to 1.3:1 and vanish).

    frame: a still (pull the strongest one from the film first - most colour and most
    tonal range wins in a feed of competing thumbnails).
    """
    if not _check_pro():
        return _pro_upsell("Video")
    if not os.path.exists(frame):
        return f"error: no such frame: {frame}"
    out = out_path or _out(title, "jpg")
    try:
        r = ve.render_film_thumbnail(frame, title, out, brand=brand,
                                     eyebrow=(eyebrow or None))
    except Exception as e:
        return f"error rendering thumbnail: {e}"
    brand_note = br.missing_brand_message(brand)
    return (f"{r['out']}\n"
            f"  type      {r['size_pt']}pt   {r['ink_w']} px of {r['avail']} available\n"
            f"  band      y={r['band_y']} (darkest strip of the upper third, luma {r['band_luma']})\n"
            f"  contrast  {r['contrast']:.2f}:1  {'OK' if r['ok'] else 'WEAK, move or enlarge'}"
            + (f"\n  brand     {brand_note}; used the neutral default look" if brand_note else ""))


# --- RENDER ON YOUR OWN MACHINE ---
# Same engine as the web editor, without needing the browser open. This opens
# `/studio-render` in a headless browser, hands it the document, and the page draws it
# with the SAME code the editor's export button uses. The browser runs on this machine
# ("local"); every user renders on their own hardware.
import base64 as _b64
import urllib.parse
import urllib.request


def _studio_base():
    return os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")


def _motion_headers():
    """How this machine signs in to the Motion DNA API: the company token, else the person's own key."""
    tok = os.environ.get("STUDIO_TOKEN", "").strip()
    if tok:
        return {"x-studio-token": tok}
    key = (os.environ.get("MOTION_DNA_KEY") or os.environ.get("CONTENT_STUDIO_LICENSE") or "").strip()
    return {"Authorization": "Bearer " + key} if key else None


def _motion_api(path: str):
    """GET one Motion DNA API route as JSON. An API refusal comes back as its own message and hint."""
    import urllib.error
    h = _motion_headers()
    if h is None:
        raise RuntimeError("no key: set CONTENT_STUDIO_LICENSE to your licence key so this machine can read your Motion DNA pieces")
    url = _studio_base() + "/api/motion/v1" + path
    req = urllib.request.Request(url, headers={**h, "User-Agent": "Vibedna-PostEngine/" + VERSION})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode() or "{}")
        except Exception:
            j = {}
        raise RuntimeError(("%s %s" % (j.get("message") or ("the studio answered %d" % e.code), j.get("hint") or "")).strip())


def _studio_doc(project_id: str, aspect: str = "9:16"):
    """Fetch a saved piece's document in the requested aspect ratio."""
    import urllib.request
    tok = os.environ.get("STUDIO_TOKEN", "")
    if not tok and _motion_headers():
        # a person's own piece lives in their own studio space: it is read with their key through the Motion DNA API
        j = _motion_api("/pieces/%s?full=1" % urllib.parse.quote(project_id)) or {}
        p, doc = j.get("piece") or {}, j.get("document") or {}
        if aspect and aspect != "9:16":
            doc = (doc.get("formats") or {}).get(aspect) or doc
        return p, doc
    url = _projects_url() + "?id=" + urllib.parse.quote(project_id)
    req = urllib.request.Request(url, headers={"x-studio-token": tok} if tok else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        p = json.loads(r.read().decode())
    p = p.get("project") or p
    doc = p.get("document") or {}
    if aspect and aspect != "9:16":
        doc = (doc.get("formats") or {}).get(aspect) or doc
    return p, doc


@mcp.tool()
def studio_render_video(project_id: str, aspect: str = "9:16", out_path: str = "",
                        where: str = "local") -> str:
    """Render a saved Motion DNA piece to a video file, using the studio's own engine.

    project_id: the piece id (the one in /content-studio?p=<id>)
    aspect:     "9:16" or "1:1", the same toggles the editor shows
    out_path:   where to write it. Empty = the output folder (~/.post-engine/out/ or
                POST_ENGINE_OUT), named after the piece
    where:      "local" (this machine). Rendering on another machine is not available in
                this version: run this MCP on the machine that should do the work.

    The frames are drawn by the SAME code as the live preview, so the file cannot drift from
    what you approved. It renders frame by frame (exactly fps x duration frames, each at n / fps), so it
    takes longer than the piece itself on a busy machine but never drops or repeats a frame. Needs playwright with
    chromium (pip install playwright, then: playwright install chromium).
    """
    if (where or "local") != "local":
        return f"error: where='{where}' is not available in this version; only 'local' renders"
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return ("error: playwright is missing in this Python "
                "(pip install playwright, then: playwright install chromium)")

    try:
        project, doc = _studio_doc(project_id, aspect)
    except Exception as e:
        return "error: could not fetch the piece -> %s" % str(e)[:160]
    if not doc.get("duration"):
        return "error: that format of the piece has no duration, so there is no video to record"

    tok = os.environ.get("STUDIO_TOKEN", "")
    base = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")
    render_base = os.environ.get("STUDIO_RENDER_URL", base).rstrip("/")   # same meaning as in _with_render_page
    page_url = render_base + "/studio-render"
    file_stem = "%s_%s" % (_slug(project_id, 40), aspect.replace(":", "x"))

    def _host(u):
        p = urllib.parse.urlsplit(u)
        return p.scheme, (p.netloc or "").lower().removeprefix("www.")

    # The token goes in a header, and only to the studio's own media route on the studio's
    # own host: never in a URL (logs, history) and never to a third-party host.
    def _is_studio_art(u):
        return _host(u) in (_host(base), _host(render_base)) and urllib.parse.urlsplit(u).path.startswith("/api/studio/art")

    def _with_token(route, request):
        u = request.url
        if render_base != base and u.startswith(render_base):
            route.fulfill(response=route.fetch(url=base + u[len(render_base):],
                                               headers={**request.headers, "x-studio-token": tok}))
            return
        route.continue_(headers={**request.headers, "x-studio-token": tok})

    media = set()

    def _collect(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "src" and isinstance(v, str):
                    media.add(urllib.parse.urljoin(page_url, v).split("?", 1)[0])
                else:
                    _collect(v)
        elif isinstance(o, list):
            for x in o:
                _collect(x)

    _collect(doc)

    def _run_render():
        failures = []
        hints = {}   # stripped address -> the file names in its query (?f=, ?key=), so a warning can name the file

        def _hint(u):
            base, _, q = u.partition("?")
            for part in q.split("&"):
                k, _, v = part.partition("=")
                if k in ("f", "key", "name", "file") and v:
                    hints.setdefault(base, set()).add(urllib.parse.unquote(v)[:80])
            return base
        with sync_playwright() as pw:
            # No --disable-web-security: the page loads every medium with
            # crossOrigin="anonymous", so the canvas stays readable without it, and the flag
            # would let any script on the page read other sites and this machine's local
            # services while it records.
            # Google Chrome, not Playwright's own Chromium: the export encodes H.264 + AAC, and the
            # open-source build has neither, so it fails with "Unsupported codec type" (2026-10-16).
            # STUDIO_RENDER_BROWSER = a Chrome executable; else the installed Chrome; else Chromium.
            args = ["--autoplay-policy=no-user-gesture-required"]
            exe = os.environ.get("STUDIO_RENDER_BROWSER", "")
            try:
                b = (pw.chromium.launch(executable_path=exe, args=args) if exe
                     else pw.chromium.launch(channel="chrome", args=args))
            except Exception:
                b = pw.chromium.launch(args=args)
            try:
                ctx = b.new_context(accept_downloads=True)
                if tok:
                    ctx.route(_is_studio_art, _with_token)
                pg = ctx.new_page()
                downloads = []
                pg.on("download", lambda d: downloads.append(d))
                pg.on("requestfailed", lambda r: failures.append(_hint(r.url)))
                pg.on("response", lambda r: r.status >= 400 and failures.append(
                    "%s (HTTP %d)" % (_hint(r.url), r.status)))
                pg.goto(page_url, wait_until="load", timeout=90000)
                pg.wait_for_function("() => window.studioRenderReady === true", timeout=60000)
                # frame by frame, each short clip stopped on its exact frame: on a busy machine a 17 s
                # piece took 2 min 10 s (2026-10-16), so the wait grows with the piece, with room
                wait_ms = int((doc.get("duration") or 20) * 15000) + 180000
                # evaluate() takes no timeout, so the job is started and then waited on.
                pg.evaluate("""(d) => { window.studioRenderOut = undefined;
                    Promise.resolve(window.studioRenderJob(d)).then(
                      r => { window.studioRenderOut = {ok: r == null ? "" : String(r)}; },
                      e => { window.studioRenderOut = {err: String(e)}; }); }""", doc)
                # Wait while the page keeps moving, not a fixed time: a heavy code-layer piece (26.5 s, 4 layers with
                # big shadows) needed more than duration x 15 s + 3 min and was cut at 99% (2026-11-04). The page
                # shows "frame by frame N%"; every 3 min the percent must have grown, with a far ceiling for safety.
                import re as _re
                def _pct():
                    try:
                        m = _re.search(r"(\d+)%", pg.evaluate("() => document.body.innerText") or "")
                        return int(m.group(1)) if m else -1
                    except Exception:
                        return -1
                deadline, last = time.time() + max(wait_ms / 1000, (doc.get("duration") or 20) * 120 + 600), -1
                while True:
                    try:
                        pg.wait_for_function("() => window.studioRenderOut !== undefined",
                                             timeout=min(wait_ms, 180000), polling=500)
                        break
                    except Exception:
                        now_pct = _pct()
                        if now_pct <= last or time.time() > deadline:
                            return {"err": "the render stalled at %s%% (no progress for 3 min)" % now_pct
                                    if now_pct <= last else "the render passed its time ceiling at %s%%" % now_pct}
                        last = now_pct
                res = pg.evaluate("() => window.studioRenderOut") or {}
                if res.get("err"):
                    hint = (" (this browser cannot encode H.264: install Google Chrome or set STUDIO_RENDER_BROWSER"
                            " to a Chrome executable)") if "codec" in str(res["err"]).lower() else ""
                    return {"err": "the page failed: %s%s" % (res["err"][:200], hint)}
                payload = res.get("ok") or ""
                if payload.startswith("data:") and "," in payload:
                    ext = ".webm" if "webm" in payload[:40] else ".mp4"
                    dest_path = out_path or str(_OUT_DIR / (file_stem + ext))
                    raw = _b64.b64decode(payload.split(",", 1)[1])
                    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(dest_path, "wb") as f:
                        f.write(raw)
                    return {"path": dest_path, "failures": failures, "hints": hints}
                # The page hands the file over as a download, not as a return value.
                if not downloads:
                    try:
                        downloads.append(pg.wait_for_event("download", timeout=30000))
                    except Exception:
                        return {"err": "the page returned no file"}
                ext = os.path.splitext(downloads[0].suggested_filename or "")[1] or ".mp4"
                dest_path = out_path or str(_OUT_DIR / (file_stem + ext))
                Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
                downloads[0].save_as(dest_path)
                return {"path": dest_path, "failures": failures, "hints": hints}
            finally:
                b.close()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        # sync Playwright cannot run inside the MCP's event loop, so it gets its own thread
        try:
            r = pool.submit(_run_render).result()
        except Exception as e:
            return "error: the render did not finish -> %s" % str(e)[:200]
    if r.get("err"):
        return "error: " + r["err"]
    dest_path = r["path"]
    # A browser without an AAC encoder (Chrome on Linux) writes the sound as Opus. Instagram wants
    # AAC, so the sound alone is converted; the picture is copied as it came out of the editor.
    try:
        codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "stream=codec_name", "-of", "csv=p=0", dest_path],
                               capture_output=True, text=True, timeout=60).stdout.strip()
        if codec and codec != "aac":
            fixed = dest_path + ".aac.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", dest_path, "-c:v", "copy", "-c:a", "aac",
                            "-b:a", "192k", "-movflags", "+faststart", fixed], check=True, timeout=600)
            os.replace(fixed, dest_path)
    except (OSError, subprocess.SubprocessError):
        pass  # no ffmpeg here: the file is still a valid video, with its sound in Opus
    mb = round(os.path.getsize(dest_path) / 1e6, 2)
    msg = ("rendered with the studio's own engine\n  piece: %s (%s)\n  file: %s (%s MB)\n  "
           "the frames come from the same function that draws the preview"
           % (project.get("name") or project_id, aspect, dest_path, mb))
    missing_media = sorted({f for f in r["failures"] if f.split(" (HTTP", 1)[0] in media})
    if missing_media:
        def _named(f):
            base = f.split(" (HTTP", 1)[0]
            names = sorted(r.get("hints", {}).get(base, ()))
            return f + (" [file: " + ", ".join(names[:3]) + "]" if names else "")
        msg += ("\n  WARNING: %d media file(s) of this piece did not load and are missing from "
                "the video (a host that does not allow cross-origin reads, or a bad link): %s"
                % (len(missing_media), ", ".join(_named(f) for f in missing_media[:5])))
    return msg


NAMED_SIZE_PX = {"story": [1080, 1920], "square": [1080, 1080], "portrait": [1080, 1350]}


def with_pixel_size(doc: dict) -> dict:
    """The document with its size as [w, h] pixels. /studio-render gives code layers s.W x s.H from the
    size when it is an array, but from 9:16 (1080x1920) when it is a name (story, square, portrait), so
    a 1:1 or 4:5 preview squashed a 1080x1920 drawing into the frame (2026-10-28). The frame is the same."""
    size = doc.get("size")
    if isinstance(size, str) and size in NAMED_SIZE_PX:
        return {**doc, "size": list(NAMED_SIZE_PX[size])}
    return doc


def _with_render_page(job, timeout_ms: int = 120000):
    """Open /studio-render headless (installed Chrome, else Chromium; the studio token goes only to
    the studio's own media route, in a header) and run job(page). Runs in its own thread because
    sync Playwright cannot run inside the MCP's event loop."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        raise RuntimeError("playwright is missing in this Python (pip install playwright, then: playwright install chromium)")
    tok = os.environ.get("STUDIO_TOKEN", "")
    base = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/")
    # STUDIO_RENDER_URL: draw on another copy of the site (a build being tested) while pieces and media still come
    # from STUDIO_URL; a test copy has no storage keys of its own (2026-11-04 exporter fix, tested before shipping)
    render_base = os.environ.get("STUDIO_RENDER_URL", base).rstrip("/")
    page_url = render_base + "/studio-render"
    hosts = {urllib.parse.urlsplit(b).netloc.lower().removeprefix("www.") for b in (base, render_base)}

    def is_art(u):
        p = urllib.parse.urlsplit(u)
        return p.netloc.lower().removeprefix("www.") in hosts and p.path.startswith("/api/studio/art")

    def art_route(route, req):
        u = req.url
        if render_base != base and u.startswith(render_base):
            # a test copy over http asks for media the live site keeps: fetch it there (continue_ cannot change
            # http to https) and hand it to the page
            route.fulfill(response=route.fetch(url=base + u[len(render_base):],
                                               headers={**req.headers, "x-studio-token": tok}))
            return
        route.continue_(headers={**req.headers, "x-studio-token": tok})

    def run():
        with sync_playwright() as pw:
            args = ["--autoplay-policy=no-user-gesture-required"]
            exe = os.environ.get("STUDIO_RENDER_BROWSER", "")
            try:
                b = (pw.chromium.launch(executable_path=exe, args=args) if exe
                     else pw.chromium.launch(channel="chrome", args=args))
            except Exception:
                b = pw.chromium.launch(args=args)
            try:
                ctx = b.new_context()
                if tok:
                    ctx.route(is_art, art_route)
                pg = ctx.new_page()
                pg.set_default_timeout(timeout_ms)
                pg.goto(page_url, wait_until="load", timeout=90000)
                pg.wait_for_function("() => window.studioRenderReady === true", timeout=60000)
                return job(pg)
            finally:
                b.close()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run).result()


def _page_call(pg, fn: str, *args):
    """Call an async window function and wait for it (evaluate takes no timeout of its own)."""
    if not pg.evaluate("(n) => typeof window[n] === 'function'", fn):
        raise LookupError(fn)
    pg.evaluate("""([n, a]) => { window.__mcpOut = undefined;
        Promise.resolve(window[n](...a)).then(r => { window.__mcpOut = {ok: r}; },
                                              e => { window.__mcpOut = {err: String(e)}; }); }""", [fn, list(args)])
    pg.wait_for_function("() => window.__mcpOut !== undefined", polling=300)
    out = pg.evaluate("() => window.__mcpOut") or {}
    if "err" in out:
        raise RuntimeError(out["err"][:300])
    return out.get("ok")


def _render_still_in_page(document: dict, out: str) -> str:
    """One still of a document, drawn by /studio-render (studioFrames) at its `t` (default 0)."""
    d = with_pixel_size(dict(document))
    t = float(document.get("t") or 0)
    try:
        urls = _with_render_page(lambda pg: _page_call(pg, "studioFrames", d, [t], {"scale": 1}))
    except LookupError:
        raise RuntimeError("this site's /studio-render has no studioFrames yet (update the site)")
    u = (urls or [None])[0]
    if not (isinstance(u, str) and u.startswith("data:") and "," in u):
        raise RuntimeError("the studio page returned no frame")
    png = _b64.b64decode(u.split(",", 1)[1])
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        from io import BytesIO
        from PIL import Image
        Image.open(BytesIO(png)).convert("RGB").save(path, quality=95)
    else:
        path.write_bytes(png)
    return str(path)


# --- Motion DNA campaigns: render every piece on this machine and hand Social Brain a ready calendar ---
# The campaign maker lives in Motion DNA (vibedna.ai/api/motion/v1/campaigns). It plans, writes and makes the
# pieces in the person's own studio space. What it cannot do from the site is produce the files; that is this
# machine's job, with the same engine the editor uses, so the files cost nothing to anyone but the machine.

_PIECE_IN_SLOT = re.compile(r"<exported file of piece (.+?)>")


def _campaign_files(slots: list, files: dict):
    """The export's slots with every placeholder swapped for the rendered file; a slot is ready when all its pieces are."""
    ready, waiting = [], []
    for s in slots:
        out = json.loads(json.dumps(s))
        missing = []

        def swap(v):
            if isinstance(v, str):
                m = _PIECE_IN_SLOT.fullmatch(v)
                if not m:
                    return v
                f = files.get(m.group(1))
                if not f:
                    missing.append(m.group(1))
                return f or v
            if isinstance(v, list):
                return [swap(x) for x in v]
            return v

        out["content"] = {k: swap(v) for k, v in (out.get("content") or {}).items()}
        (waiting if missing else ready).append(out)
    return ready, waiting


def _local_stills(slots: list) -> int:
    """How many posts hold an image that is a file here and not a link."""
    def is_local_image(v):
        if isinstance(v, list):
            return any(is_local_image(x) for x in v)
        return (isinstance(v, str) and v.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                and not v.lower().startswith(("http://", "https://")))
    return sum(1 for s in slots if any(is_local_image(v) for v in (s.get("content") or {}).values()))


@mcp.tool()
def campaign_render(campaign: str, account: str = "", out_dir: str = "", limit: int = 3) -> str:
    """Render the pieces of a Motion DNA campaign on this machine and write the calendar Social Brain publishes.

    campaign: the campaign id (motion_campaign_list shows it; it is in the campaign's links too)
    account:  the account name in Social Brain, written into each channel ("ig_reel:<account>")
    out_dir:  where the files go. Empty = the output folder / the campaign id
    limit:    how many pieces to render in this call (a reel takes minutes: it is drawn frame by frame).
              Call again until it says every piece is rendered; files already there are not rendered twice.

    Videos come out as .mp4 and stills as .png, drawn by the SAME code as the editor's preview. When every piece
    of a post is rendered, the post goes into <out_dir>/<campaign>_drip.json with its file in place; hand its
    `slots` to Social Brain's drip_schedule(name, slots). Trial reels are already marked to stay off the grid.
    """
    cid = re.sub(r"[^a-z0-9-]", "", str(campaign or "").strip().lower())
    if not cid:
        return "error: give the campaign id (motion_campaign_list shows yours)"
    try:
        limit = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        return "error: limit must be a number from 1 to 20"
    try:
        q = ("?account=" + urllib.parse.quote(account)) if account else ""
        ex = _motion_api("/campaigns/%s/export%s" % (cid, q))
    except Exception as e:
        return "error: could not read the campaign -> %s" % str(e)[:240]
    slots = ((ex or {}).get("drip") or {}).get("slots") or []
    folder = Path(out_dir) if out_dir else _OUT_DIR / cid
    folder.mkdir(parents=True, exist_ok=True)
    pieces = []
    for s in slots:
        for pid in s.get("motion_pieces") or []:
            if pid not in pieces:
                pieces.append(pid)
    if not pieces:
        why = "; ".join("%s: %s" % (n.get("slot"), n.get("why")) for n in ((ex or {}).get("not_included") or [])[:4])
        return "nothing to render: the campaign has no made piece yet (motion_campaign_make first). %s" % why

    files, made_now, errors = {}, [], []
    for pid in pieces:
        done = next((str(p) for p in (folder / (pid + ".mp4"), folder / (pid + ".webm"), folder / (pid + ".png")) if p.exists() and p.stat().st_size > 0), "")
        if done:
            files[pid] = done
            continue
        if len(made_now) >= limit:
            continue
        try:
            doc = (_motion_api("/pieces/%s?full=1" % urllib.parse.quote(pid)) or {}).get("document") or {}
            if doc.get("duration"):
                r = studio_render_video(project_id=pid, out_path=str(folder / (pid + ".mp4")))
                if str(r).startswith("error"):
                    raise RuntimeError(str(r)[7:])
                path = next((str(p) for p in (folder / (pid + ".mp4"), folder / (pid + ".webm")) if p.exists()), "")
                if not path:
                    raise RuntimeError("the render reported no file")
            else:
                path = _render_still_in_page(doc, str(folder / (pid + ".png")))
            files[pid] = path
            made_now.append(pid)
        except Exception as e:
            errors.append("%s: %s" % (pid, str(e)[:200]))

    ready, waiting = _campaign_files(slots, files)
    drip = folder / (cid + "_drip.json")
    drip.write_text(json.dumps({"name": (ex.get("drip") or {}).get("name") or cid, "slots": ready,
                                "waiting_for_files": [w.get("id") for w in waiting]}, indent=1), encoding="utf-8")
    left = [p for p in pieces if p not in files]
    lines = ["rendered now: %d (%s)" % (len(made_now), ", ".join(made_now) or "none"),
             "pieces with a file: %d of %d" % (len(files), len(pieces)),
             "posts ready in the calendar: %d of %d -> %s" % (len(ready), len(slots), drip)]
    if errors:
        lines.append("could not render: " + " | ".join(errors[:4]))
    if _local_stills(ready):
        lines.append("images: %d post(s) carry a still as a file on this machine. Social Brain 1.12.9 or newer posts "
                     "it to Instagram as it is when the account is connected through a Facebook Page (the file goes "
                     "through that Page, unseen) or publishes through the logged-in browser. An older Social Brain, or "
                     "an account connected with Instagram Login, needs a public https link in the slot instead. Reels "
                     "publish from the file." % _local_stills(ready))
    lines.append("next: call campaign_render again (%d left)" % len(left) if left and not (errors and not made_now)
                 else "next: in Social Brain, drip_schedule(name, slots) with the name and slots of that file" if not left
                 else "next: fix what failed above, then call campaign_render again")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
