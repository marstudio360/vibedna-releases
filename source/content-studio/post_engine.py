#!/usr/bin/env python3
"""
Social Content Studio: the card engine (programmatic social-post renderer).

Makes on-brand, post-ready images by CODE. No image-generation model, no GPU, no
per-image fee. Your AI writes the words; this draws the pixels. Two modes:

  card   : 100% code-drawn: gradient + radial glow + procedural texture + your text.
  stock  : fetch a license-clean stock photo (Openverse, keyless) OR use your own
           image, then composite a branded scrim + your text on top.

Both run on a normal laptop. Output feeds any poster (e.g. the Social Brain MCP's
publish_* / drip_* tools).

CLI:
  python post_engine.py card  --text "Your line here" --handle "@brand" --out out.jpg
  python post_engine.py stock --text "Your line" --query "night sky" --out out.jpg
  python post_engine.py stock --text "Your line" --image ./mine.jpg --out out.jpg
  python post_engine.py card  --text "..." --size portrait --preset clean --out out.jpg

Library:
  from post_engine import render_card, render_stock, STYLES
  render_card("Your line", "out.jpg", handle="@brand", size="square")
"""
from __future__ import annotations
import argparse
import io
import os
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

# --- Sizes ---
SIZES = {
    "square":   (1080, 1080),
    "portrait": (1080, 1350),
    "story":    (1080, 1920),
}

# --- Style presets ---
# Colors are RGB. Provide your own font files for good typography; the engine
# falls back to common system fonts, then PIL's built-in bitmap font.
STYLES = {
    "night": {
        "bg_top": (14, 16, 34),
        "bg_bottom": (4, 5, 14),
        "glow": (86, 74, 160),
        "glow_strength": 0.75,
        "text": (240, 242, 250),
        "accent": (150, 200, 210),
        "particles": (150, 160, 210),
        "scrim": (4, 5, 14, 150),      # for stock mode overlay
        "title_font": None,             # path to a .ttf; None = auto-resolve
        "mono_font": None,
    },
    "clean": {
        "bg_top": (245, 246, 250),
        "bg_bottom": (222, 226, 236),
        "glow": (255, 255, 255),
        "glow_strength": 0.6,
        "text": (24, 26, 38),
        "accent": (90, 110, 130),
        "particles": (120, 130, 150),
        "scrim": (245, 246, 250, 120),
        "title_font": None,
        "mono_font": None,
    },
    "warm": {
        "bg_top": (46, 26, 30),
        "bg_bottom": (16, 8, 10),
        "glow": (210, 120, 80),
        "glow_strength": 0.8,
        "text": (250, 244, 238),
        "accent": (232, 176, 120),
        "particles": (210, 160, 120),
        "scrim": (16, 8, 10, 150),
        "title_font": None,
        "mono_font": None,
    },
}

# Common system fonts to try when a style gives no explicit path.
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/Georgia.ttf", "C:/Windows/Fonts/constan.ttf",
    "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_SANS_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_MONO_CANDIDATES = [
    "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
# The generic family a CSS-style font list ends with, and the files that stand in for it.
_GENERIC_FAMILIES = {"serif": _FONT_CANDIDATES, "sans-serif": _SANS_CANDIDATES,
                     "system-ui": _SANS_CANDIDATES, "monospace": _MONO_CANDIDATES}
_FONT_EXTS = (".ttf", ".otf", ".ttc")


def _fonts_dir():
    """User font library: drop any .ttf/.otf here (or have your AI download one) and use
    it by NAME in a text layer's `font`. Override with POST_ENGINE_FONTS."""
    return os.environ.get("POST_ENGINE_FONTS", str(Path.home() / ".post-engine" / "fonts"))


def _os_font_dirs():
    """Where the operating system keeps its installed fonts. Searching here lets a BRAND
    name its real typeface ("Cinzel-Bold") and have it resolve on any machine where the
    font is installed, instead of carrying somebody's absolute path around."""
    home = Path.home()
    return [d for d in (
        os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"),
        str(home / "AppData/Local/Microsoft/Windows/Fonts"),
        "/usr/share/fonts", "/usr/local/share/fonts", str(home / ".fonts"),
        str(home / ".local/share/fonts"), "/Library/Fonts", "/System/Library/Fonts",
        str(home / "Library/Fonts"),
    ) if os.path.isdir(d)]


def _font_file(name):
    """An absolute path, or <name>.ttf/.otf/.ttc in the font library or the OS font dirs."""
    if os.path.isfile(name):
        return name
    for root in [_fonts_dir()] + _os_font_dirs():
        for ext in ("", ".ttf", ".otf", ".ttc", ".TTF", ".OTF"):
            cand = os.path.join(root, name + ext)
            if os.path.isfile(cand):
                return cand
    return None


# Where common families live on Windows, macOS and Linux, so they resolve without reading
# every installed font file (that index is the slow last resort).
_FAMILY_FILES = {
    "segoe ui": ["segoeui.ttf"], "segoe ui black": ["seguibl.ttf"],
    "segoe ui symbol": ["seguisym.ttf"],
    "arial": ["arial.ttf", "Supplemental/Arial.ttf", "truetype/liberation/LiberationSans-Regular.ttf"],
    "arial black": ["ariblk.ttf", "Supplemental/Arial Black.ttf"],
    "georgia": ["georgia.ttf", "Supplemental/Georgia.ttf"],
    "times new roman": ["times.ttf", "Supplemental/Times New Roman.ttf",
                        "truetype/liberation/LiberationSerif-Regular.ttf"],
    "palatino linotype": ["pala.ttf"], "palatino": ["Palatino.ttc"],
    "book antiqua": ["BKANT.TTF", "bkant.ttf"],
    "helvetica neue": ["HelveticaNeue.ttc"], "helvetica": ["Helvetica.ttc"],
    "apple symbols": ["Apple Symbols.ttf"],
    "noto sans symbols 2": ["truetype/noto/NotoSansSymbols2-Regular.ttf"],
    "courier new": ["cour.ttf", "Supplemental/Courier New.ttf"],
    "dejavu sans": ["truetype/dejavu/DejaVuSans.ttf"], "dejavu serif": ["truetype/dejavu/DejaVuSerif.ttf"],
}


def _known_family_file(family):
    for rel in _FAMILY_FILES.get(family.strip().lower(), []):
        for root in _os_font_dirs():
            cand = os.path.join(root, rel)
            if os.path.isfile(cand):
                return cand
    return None


_FAMILY_INDEX = []


def _family_file(family):
    """The regular face of an installed font FAMILY ("Segoe UI", "Arial Black"), read from the
    names inside the font files, so a family resolves even when its file is "seguibl.ttf".
    The index is built once per process, the first time a family is not found by file name."""
    if not _FAMILY_INDEX:
        import glob
        index = {}
        for root in [_fonts_dir()] + _os_font_dirs():
            for f in glob.glob(os.path.join(root, "**", "*"), recursive=True):
                if os.path.splitext(f)[1].lower() not in _FONT_EXTS:
                    continue
                try:
                    fam, style = ImageFont.truetype(f, 12).getname()
                except Exception:
                    continue
                index.setdefault((fam or "").lower(), {}).setdefault((style or "").lower(), f)
        _FAMILY_INDEX.append(index)
    styles = _FAMILY_INDEX[0].get(family.strip().lower())
    if not styles:
        return None
    for s in ("regular", "normal", "book", "roman", "medium", ""):
        if s in styles:
            return styles[s]
    return next(iter(styles.values()))


_RESOLVED = {}


def _resolve_font(path):
    """Resolve a text layer's `font`:

    - an absolute path;
    - a NAME looked up in the font library (POST_ENGINE_FONTS) and then the OS font
      directories, as <name>.ttf/.otf/.ttc, then as a fuzzy filename match, then as an
      installed family name;
    - a CSS-style LIST, as the web editor writes it: "'Helvetica Neue', 'Segoe UI', Arial,
      sans-serif". The first family installed here wins; a generic family at the end
      (serif, sans-serif, monospace) picks a common system face, so the same document
      renders on any machine.
    """
    if not path:
        return None
    if path in _RESOLVED:
        return _RESOLVED[path]
    found = None
    if "," in path or path.strip().lower() in _GENERIC_FAMILIES or path.strip()[:1] in "'\"":
        fams = [p.strip().strip("'\"").strip() for p in path.split(",")]
        named = [f for f in fams if f and f.lower() not in _GENERIC_FAMILIES]
        generic = [f for f in fams if f and f.lower() in _GENERIC_FAMILIES]
        # quick lookups first (file name, known location), then the font index, then the
        # generic family, so a missing first choice never costs a scan when a later one is here
        found = (next((x for x in (_font_file(f) or _known_family_file(f) for f in named) if x), None)
                 or next((x for x in (_family_file(f) for f in named) if x), None)
                 or next((c for g in generic for c in _GENERIC_FAMILIES[g.lower()] if os.path.isfile(c)), None))
    else:
        found = _font_file(path) or _known_family_file(path)
        if not found:
            import glob
            low = path.lower()
            for root in [_fonts_dir()] + _os_font_dirs():
                for f in glob.glob(os.path.join(root, "**", "*"), recursive=True):
                    if (os.path.isfile(f) and low in os.path.basename(f).lower()
                            and os.path.splitext(f)[1].lower() in _FONT_EXTS):
                        found = f
                        break
                if found:
                    break
        found = found or _family_file(path)
    if found:
        # only a hit is remembered: a font added later (add_font) must still be found
        _RESOLVED[path] = found
    return found


def list_fonts():
    """List the fonts in the user font library (POST_ENGINE_FONTS), usable by name."""
    import glob
    root = _fonts_dir()
    if not os.path.isdir(root):
        return {"root": root, "exists": False, "fonts": []}
    fonts = sorted(os.path.splitext(os.path.basename(f))[0]
                   for f in glob.glob(os.path.join(root, "**", "*"), recursive=True)
                   if os.path.isfile(f) and os.path.splitext(f)[1].lower() in _FONT_EXTS)
    return {"root": root, "exists": True, "fonts": fonts}


# How the bold file of a face is usually named next to the regular one: Windows (arial.ttf ->
# arialbd.ttf, georgia.ttf -> georgiab.ttf), Linux (DejaVuSans.ttf -> DejaVuSans-Bold.ttf) and
# macOS ("Arial.ttf" -> "Arial Bold.ttf").
_BOLD_SUFFIXES = ("bd", "b", "-Bold", "_Bold", " Bold", "Bold", "-bold", "_bold")
_HEAVY_NAME = re.compile(r"black|blk|heavy|bold|bd\.", re.I)


def _bold_sibling(path: str) -> str | None:
    stem, ext = os.path.splitext(path)
    for suffix in _BOLD_SUFFIXES:
        cand = stem + suffix + ext
        if os.path.exists(cand):
            return cand
    if stem.endswith("-Regular"):
        cand = stem[: -len("-Regular")] + "-Bold" + ext
        if os.path.exists(cand):
            return cand
    return None


def _truetype(p: str, size):
    try:
        return ImageFont.truetype(p, size)
    except TypeError:  # Pillow before 10.1 takes whole pixel sizes only
        return ImageFont.truetype(p, max(1, int(round(size))))


def _load_font(path: str | None, size: int, mono: bool = False, bold: bool = False):
    """A Pillow font for `path` (a file, a font name or a CSS-style family list) at `size`
    pixels, falling back to common system faces and finally Pillow's built-in font. With
    `bold`, the face's bold file is used when the machine has one; the returned font then
    carries `_is_bold = True` so the caller knows it does not have to thicken it."""
    resolved = _resolve_font(path)
    tries = ([resolved] if resolved else []) + (_MONO_CANDIDATES if mono else _FONT_CANDIDATES)
    for p in tries:
        try:
            if p and os.path.exists(p):
                if bold:
                    heavy = _bold_sibling(p)
                    f = _truetype(heavy or p, size)
                    # A face that is heavy by itself (Arial Black) is already what bold asks for,
                    # the same way the browser draws it.
                    if heavy or _HEAVY_NAME.search(os.path.basename(p)):
                        f._is_bold = True
                    return f
                return _truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)          # Pillow >= 10 accepts size
    except Exception:
        return ImageFont.load_default()


def _vertical_gradient(size, top, bottom) -> Image.Image:
    """Smooth vertical gradient without numpy: build a 1xH strip, resize up."""
    w, h = size
    strip = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        strip.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((w, h))


def _radial_glow(size, color, strength: float) -> Image.Image:
    """A soft off-center radial light, drawn as stacked blurred ellipses."""
    w, h = size
    glow = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(glow)
    cx, cy = int(w * 0.5), int(h * 0.42)
    rmax = int(max(w, h) * 0.62)
    steps = 16
    for i in range(steps):
        r = int(rmax * (1 - i / steps))
        val = int(255 * strength * (i / steps) ** 1.4)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=val)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(max(w, h) * 0.06)))
    tint = Image.new("RGB", (w, h), color)
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(tint, black, glow)


def _particles(base: Image.Image, color, seed_text: str, count: int = 220):
    """Deterministic procedural specks: same text always renders the same."""
    import zlib
    # crc32, not hash(): str hashes are salted per process, so hash() broke the promise above.
    rnd = random.Random(zlib.crc32(str(seed_text).encode("utf-8")))
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(count):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.choice([1, 1, 1, 2, 2, 3])
        a = rnd.randint(10, 60)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*color, a))
    return Image.alpha_composite(base.convert("RGBA"), layer)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _draw_centered_text(img, text, style, size_key, shadow=True):
    w, h = img.size
    draw = ImageDraw.Draw(img)
    margin = int(w * 0.12)
    max_w = w - 2 * margin
    # size the title to the text length, within bounds
    fsize = int(w * (0.11 if len(text) < 60 else 0.085 if len(text) < 120 else 0.065))
    font = _load_font(style.get("title_font"), fsize)
    lines = _wrap(draw, text, font, max_w)
    # shrink if the block is too tall
    while len(lines) * (fsize * 1.28) > h * 0.62 and fsize > 22:
        fsize = int(fsize * 0.92)
        font = _load_font(style.get("title_font"), fsize)
        lines = _wrap(draw, text, font, max_w)
    line_h = fsize * 1.28
    total_h = len(lines) * line_h
    y = (h - total_h) / 2
    for ln in lines:
        tw = draw.textlength(ln, font=font)
        x = (w - tw) / 2
        if shadow:
            draw.text((x + 2, y + 3), ln, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), ln, font=font, fill=style["text"])
        y += line_h
    return draw


def _draw_handle(draw, img, handle, style):
    if not handle:
        return
    w, h = img.size
    fsize = int(w * 0.028)
    font = _load_font(style.get("mono_font"), fsize, mono=True)
    tw = draw.textlength(handle, font=font)
    draw.text(((w - tw) / 2, h - int(h * 0.085)), handle, font=font, fill=style["accent"])


def _draw_counter(draw, img, counter, style):
    """A small 'i/n' marker in the top-right corner for carousel slides."""
    if not counter:
        return
    w, h = img.size
    label = f"{counter[0]}/{counter[1]}"
    fsize = int(w * 0.026)
    font = _load_font(style.get("mono_font"), fsize, mono=True)
    tw = draw.textlength(label, font=font)
    draw.text((w - tw - int(w * 0.06), int(h * 0.05)), label, font=font, fill=style["accent"])


def _resolve_style(preset):
    if isinstance(preset, dict):
        base = dict(STYLES["night"]); base.update(preset); return base
    return dict(STYLES.get(preset or "night", STYLES["night"]))


def render_card(text, out_path, handle="", size="square", preset="night", counter=None):
    """100% code-drawn post: gradient + radial glow + procedural texture + text."""
    style = _resolve_style(preset)
    dims = SIZES.get(size, SIZES["square"])
    img = _vertical_gradient(dims, style["bg_top"], style["bg_bottom"])
    glow = _radial_glow(dims, style["glow"], style["glow_strength"])
    img = ImageChops.screen(img.convert("RGB"), glow.convert("RGB"))
    img = _particles(img, style["particles"], text).convert("RGB")
    draw = _draw_centered_text(img, text, style, size)
    _draw_handle(draw, img, handle, style)
    _draw_counter(draw, img, counter, style)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path


# --- Image fetch: multiple sources + a direct URL. NO image generation, only fetch.
# openverse is keyless (license-clean). pexels/unsplash/pixabay need a free API key
# in the matching env var. "url" downloads a direct image URL you pass as the query.
_UA = {"User-Agent": "VibeDNA-PostEngine/1.0"}


def _http_json(url, headers=None, timeout=20):
    import urllib.request, json
    req = urllib.request.Request(url, headers={**_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _http_image(url, headers=None, timeout=25):
    import urllib.request
    req = urllib.request.Request(url, headers={**_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def _orient(dims):
    return "square" if dims[0] == dims[1] else ("portrait" if dims[1] > dims[0] else "landscape")


def _src_openverse(query, dims):
    import urllib.parse
    q = urllib.parse.urlencode({"q": query, "page_size": 8, "license_type": "commercial,modification",
                                "aspect_ratio": "square" if dims[0] == dims[1] else "tall", "mature": "false"})
    data = _http_json("https://api.openverse.org/v1/images/?" + q)
    for item in (data.get("results") or []):
        url = item.get("url") or item.get("thumbnail")
        if url:
            try:
                return _http_image(url)
            except Exception:
                continue
    raise RuntimeError(f"no Openverse results for '{query}'")


def _src_pexels(query, dims):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not set")
    import urllib.parse
    q = urllib.parse.urlencode({"query": query, "per_page": 1, "orientation": _orient(dims)})
    data = _http_json("https://api.pexels.com/v1/search?" + q, headers={"Authorization": key})
    photos = data.get("photos") or []
    if not photos:
        raise RuntimeError(f"no Pexels results for '{query}'")
    src = photos[0].get("src") or {}
    return _http_image(src.get("large2x") or src.get("large") or src.get("original"))


def _src_unsplash(query, dims):
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        raise RuntimeError("UNSPLASH_ACCESS_KEY not set")
    import urllib.parse
    q = urllib.parse.urlencode({"query": query, "per_page": 1,
                                "orientation": "squarish" if dims[0] == dims[1] else "portrait"})
    data = _http_json("https://api.unsplash.com/search/photos?" + q, headers={"Authorization": f"Client-ID {key}"})
    res = data.get("results") or []
    if not res:
        raise RuntimeError(f"no Unsplash results for '{query}'")
    return _http_image(res[0]["urls"]["regular"])


def _src_pixabay(query, dims):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("PIXABAY_API_KEY not set")
    import urllib.parse
    q = urllib.parse.urlencode({"key": key, "q": query, "per_page": 3, "image_type": "photo", "safesearch": "true"})
    data = _http_json("https://pixabay.com/api/?" + q)
    hits = data.get("hits") or []
    if not hits:
        raise RuntimeError(f"no Pixabay results for '{query}'")
    return _http_image(hits[0].get("largeImageURL") or hits[0].get("webformatURL"))


def _src_url(query, dims):
    return _http_image(query)  # the query IS the image URL


def _library_root():
    return os.environ.get("POST_ENGINE_LIBRARY", str(Path.home() / ".post-engine" / "library"))


def library_pick(query="", root=None):
    """Pick one image from a LOCAL library folder ('import your own library'):
    point `root` at ANY folder of your existing art (or a brand's), or leave it None to
    use POST_ENGINE_LIBRARY (default ~/.post-engine/library/). `query` is a category/tag
    (a subfolder) and/or a name fragment; empty = the whole folder. The pick is stable
    from the query so a re-render is reproducible. Returns a PIL RGB image."""
    import glob, zlib
    root = root or _library_root()
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    patterns = []
    if query:
        patterns += [os.path.join(root, query, "**", "*"), os.path.join(root, "**", f"*{query}*")]
    patterns += [os.path.join(root, "**", "*")]
    files = []
    for pat in patterns:
        files = sorted(f for f in glob.glob(pat, recursive=True)
                       if os.path.isfile(f) and os.path.splitext(f)[1].lower() in exts)
        if files:
            break
    if not files:
        raise RuntimeError(f"no images in library '{root}' for '{query or 'any'}' "
                           f"(point root at your art folder, or set POST_ENGINE_LIBRARY)")
    idx = (zlib.crc32((query or "").encode()) % len(files)) if query else 0
    im = Image.open(files[idx])
    has_alpha = ("A" in im.getbands()) or (im.mode == "P" and "transparency" in im.info)
    return im.convert("RGBA") if has_alpha else im.convert("RGB")


def library_list(root=None):
    """List the categories (subfolders) + image count of a local library folder."""
    import glob
    root = root or _library_root()
    if not os.path.isdir(root):
        return {"root": root, "exists": False, "categories": {}, "total": 0}
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    cats = {}
    total = 0
    for f in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if os.path.isfile(f) and os.path.splitext(f)[1].lower() in exts:
            total += 1
            rel = os.path.relpath(os.path.dirname(f), root)
            cats[rel] = cats.get(rel, 0) + 1
    return {"root": root, "exists": True, "categories": cats, "total": total}


def _src_library(query, dims):
    return library_pick(query)


#: Where the generative studio lives. Point it at your own copy if you host one.
VIBEGEN_URL = os.environ.get("VIBEGEN_STUDIO_URL", "https://studio.vibedna.ai").rstrip("/")

#: The generative engines the studio ships. The first word of the query picks one.
VIBEGEN_ENGINES = ("still-flow", "still-meshgrad", "still-geometry", "still-waves")


#: The studio's effects layer, by look name. Same names and values as the studio's own
#: one-click looks, so 'fx=mandala' here draws what the Mandala button draws there.
VIBEGEN_LOOKS = {
    "mandala": {"fx_kaleido": 8, "fx_kaleidoSpin": 0.25, "fx_kaleidoZoom": 1.4, "fx_bloom": 0.3, "fx_bloomThresh": 0.75, "fx_vignette": 0.5},
    "dream": {"fx_trails": 0.9, "fx_bloom": 0.9, "fx_bloomThresh": 0.45, "fx_hueDrift": 12, "fx_vignette": 0.4},
    "tunnel": {"fx_twist": 2.4, "fx_lens": "fisheye", "fx_lensAmt": 0.8, "fx_kaleido": 6, "fx_kaleidoSpin": -0.4, "fx_vignette": 0.7},
    "glitch": {"fx_slice": 0.55, "fx_sliceCount": 22, "fx_lens": "prism", "fx_lensAmt": 0.9, "fx_exposure": 0.4},
    "quilt": {"fx_tiles": 3, "fx_lens": "mirror", "fx_lensAmt": 0.3, "fx_bloom": 0.3},
    "liquid": {"fx_lens": "ripple", "fx_lensAmt": 0.8, "fx_trails": 0.7, "fx_bloom": 0.5, "fx_hue": 180},
}


def _vibegen_recipe(query):
    """Read a query like 'still-flow seed=11 palette=deep_teal fx=mandala fx_bloom=0.9' into a recipe.

    A recipe, not a prompt: the same engine with the same seed draws the same art forever,
    so a campaign can be reproduced instead of re-rolled. 'fx=<look>' turns on one of the
    studio's looks; any 'fx_<name>=<value>' sets one effect on top of it.
    """
    parts = (query or "").split()
    engine = parts[0] if parts and "=" not in parts[0] else VIBEGEN_ENGINES[0]
    if engine not in VIBEGEN_ENGINES:
        raise ValueError("unknown engine '%s'; use one of %s" % (engine, list(VIBEGEN_ENGINES)))
    seed, params, look, fx = 7, {}, {}, {}
    for p in parts:
        if "=" not in p:
            continue
        k, _, v = p.partition("=")
        try:
            value = float(v) if v.lstrip("-").replace(".", "", 1).isdigit() else v
        except ValueError:
            value = v
        if k == "seed":
            seed = int(float(v))
        elif k == "fx":
            if v not in VIBEGEN_LOOKS:
                raise ValueError("unknown look '%s'; use one of %s" % (v, sorted(VIBEGEN_LOOKS)))
            look = VIBEGEN_LOOKS[v]
        elif k.startswith("fx_"):
            fx[k] = value
        else:
            params[k] = value
    return engine, seed, params, dict(look, **fx)


def _src_vibegen(query, dims):
    """Draw a generative background with the studio's own engines, in a browser with no window.

    The page paints to a canvas, so there is no server render to call: the deep link is the
    only reliable way to choose the engine from a script (the state API applies params but
    never the engine).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "source='vibegen' needs Playwright: pip install playwright && playwright install chromium")
    import base64, json as _json, urllib.parse
    engine, seed, params, fx = _vibegen_recipe(query)
    side = max(dims)
    recipe = {"engineId": engine, "seedUrl": "",
              "params": dict(params, runSeed=seed, animate=False)}
    if fx:
        recipe["fx"] = dict(fx, fx_on=True)
    preset = base64.b64encode(_json.dumps(recipe).encode()).decode()
    url = "%s/studio?preset=%s&still=%d" % (VIBEGEN_URL, urllib.parse.quote(preset), side)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_function("window.__stillReady === true", timeout=120000, polling=500)
            # Wait until the canvas has the requested size AND real paint: the ready flag can
            # arrive a moment before the new frame is drawn.
            data = page.wait_for_function(
                """(side) => {
                    const c = document.querySelector('canvas');
                    if (!c || c.width !== side || c.height !== side) return null;
                    const s = document.createElement('canvas'); s.width = s.height = 32;
                    const g = s.getContext('2d'); g.drawImage(c, 0, 0, 32, 32);
                    const d = g.getImageData(0, 0, 32, 32).data;
                    let lit = 0;
                    for (let i = 0; i < d.length; i += 4) if (d[i]+d[i+1]+d[i+2] > 30) lit++;
                    return lit < 40 ? null : c.toDataURL('image/png');
                }""", arg=side, timeout=90000, polling=500).json_value()
        finally:
            browser.close()
    return Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))).convert("RGB")


_SOURCES = {"openverse": _src_openverse, "pexels": _src_pexels, "unsplash": _src_unsplash,
            "pixabay": _src_pixabay, "url": _src_url, "library": _src_library,
            "vibegen": _src_vibegen}


def _fetch_source(query, source, dims):
    fn = _SOURCES.get(source)
    if not fn:
        raise ValueError(f"unknown source '{source}'; use one of {list(_SOURCES)}")
    return fn(query, dims)


def fetch_image(query, out_path, source="openverse", size="square"):
    """Fetch one image (a stock source, or a direct URL when source='url') and save it.
    Returns the path. No AI image generation: stock sources download existing images and
    source='vibegen' draws one with the generative engines."""
    dims = SIZES.get(size, SIZES["square"])
    img = _fetch_source(query, source, dims)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path


def _reading_veil(base, style, dims):
    """The veil that keeps text readable, sized to the art underneath.

    A fixed veil is wrong both ways: too thin over busy bright art, and a needless grey
    wash over art that is already dark and calm. This one reads the band where the text
    lands (how bright it is and how much it varies) and adds only what that band needs.
    It is strongest across the middle and eases off toward the edges, so the art still shows.
    """
    from PIL import ImageStat
    w, h = dims
    band = base.convert("L").crop((0, int(h * 0.26), w, int(h * 0.74)))
    stats = ImageStat.Stat(band)
    brightness = stats.mean[0] / 255.0
    busy = min(1.0, (stats.stddev[0] / 255.0) * 3.4)
    color = tuple(style["scrim"][:3])
    floor = style["scrim"][3] / 255.0
    alpha = min(0.88, floor + 0.40 * busy + 0.42 * max(0.0, brightness - 0.30))

    mask = Image.new("L", (1, h))
    px = mask.load()
    for y in range(h):
        d = abs(y / (h - 1) - 0.5) * 2          # 0 at the centre, 1 at the edges
        px[0, y] = int(255 * alpha * (1.0 - 0.55 * d * d))
    mask = mask.resize((w, h))
    veil = Image.new("RGB", dims, color)
    return Image.composite(veil, base.convert("RGB"), mask)


def render_stock(text, out_path, query=None, image_path=None, handle="",
                 size="square", preset="night", counter=None, source="openverse"):
    """Fetch an image (stock source or your own), veil it, overlay text.
    source: openverse (keyless) | pexels | unsplash | pixabay | url | library | vibegen.
    With source='url' the query IS a direct image URL; with 'vibegen' it is the recipe."""
    style = _resolve_style(preset)
    dims = SIZES.get(size, SIZES["square"])
    if image_path:
        base = Image.open(image_path).convert("RGB")
    elif query:
        base = _fetch_source(query, source, dims)
    else:
        raise ValueError("render_stock needs either query= or image_path=")
    base = ImageOps.fit(base, dims, method=Image.LANCZOS)
    base = _reading_veil(base, style, dims)
    draw = _draw_centered_text(base, text, style, size)
    _draw_handle(draw, base, handle, style)
    _draw_counter(draw, base, counter, style)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    base.save(out_path, quality=92)
    return out_path


def render_carousel(slides, out_dir, handle="", size="portrait", preset="night",
                    mode="card", query=None, image_paths=None, source="openverse"):
    """Render a multi-slide carousel. `slides` is a list of strings (first = cover).
    Each slide gets an 'i/N' counter; the handle goes on the last slide (the CTA).
    mode='card' draws every slide; mode='stock' pulls a photo per slide (query, or a
    matching entry from image_paths). Writes slide_01.jpg..slide_0N.jpg to out_dir.
    Returns the list of file paths."""
    if not slides:
        raise ValueError("carousel needs at least one slide")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    n = len(slides)
    paths = []
    for i, text in enumerate(slides, 1):
        out = os.path.join(out_dir, f"slide_{i:02d}.jpg")
        h = handle if i == n else ""
        if mode == "stock":
            img_path = (image_paths[i - 1] if image_paths and i - 1 < len(image_paths) else None)
            render_stock(text, out, query=query, image_path=img_path, handle=h,
                         size=size, preset=preset, counter=(i, n), source=source)
        else:
            render_card(text, out, handle=h, size=size, preset=preset, counter=(i, n))
        paths.append(out)
    return paths


def _ffmpeg():
    return os.environ.get("FFMPEG_BIN", "ffmpeg")


def _ffprobe():
    return os.environ.get("FFPROBE_BIN", "ffprobe")


# How long a card stays up. A fixed number per card is the wrong unit: a three-word card sits there
# doing nothing while a twenty-word card is gone before it can be read. Seconds come from the text.
READ_WORDS_PER_SEC = 3.0
HOLD_MIN, HOLD_MAX = 2.70, 8.00


def secs_for_text(text, minimum=HOLD_MIN, maximum=HOLD_MAX, wps=READ_WORDS_PER_SEC):
    """Seconds this card needs so its text can actually be read, clamped to a sane range.

    Reading speed on a phone, with big type and no context, sits near three words a second. The
    floor keeps short cards from flashing past; the ceiling keeps a long one from stalling."""
    words = len(str(text or "").split())
    if not words:
        return minimum
    return max(minimum, min(maximum, words / float(wps)))


def video_seconds(path):
    """Length of a video file in seconds, or 0.0 if it cannot be read."""
    import subprocess
    try:
        r = subprocess.run([_ffprobe(), "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        return float((r.stdout or "0").strip().splitlines()[0])
    except Exception:
        return 0.0


def mux_music(silent, music, out_path, fade=1.5):
    """Attach a music bed WITHOUT letting it decide how long the video is.

    The obvious spelling of this is `-shortest`, and it is a trap: when the bed is shorter than the
    video, the video is silently cut down to the bed. A reel whose last card is the call to action
    loses exactly the part that matters, and the file looks fine. Here the video always wins: the
    bed repeats until it covers the video, is cut to the video's length, and fades out at the end.
    """
    import subprocess, shutil
    length = video_seconds(silent)
    if length <= 0:
        shutil.copyfile(silent, out_path)
        return out_path
    fade = min(float(fade), length / 2.0)
    graph = ("[1:a]afade=t=out:st=%.3f:d=%.2f,atrim=0:%.3f,asetpts=N/SR/TB[a]"
             % (max(0.0, length - fade), fade, length))
    subprocess.run([_ffmpeg(), "-y", "-i", str(silent), "-stream_loop", "-1", "-i", str(music),
                    "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-t", "%.3f" % length, str(out_path)], check=True, capture_output=True)
    return out_path


def render_reel(beats, out_path, music=None, secs_per=0, size="story",
                preset="night", mode="card", query=None, source="openverse"):
    """Programmatic reel: each beat (a short line) becomes a card with a slow Ken Burns zoom,
    concatenated into a vertical video, with an optional music bed. The first beat is the hook
    (the first 0.5s decides reach). Needs ffmpeg. NO image generation, the frames are code-drawn.

    secs_per=0 (the default) gives each card the time its own text needs to be read. Pass a
    number to force every card to the same length."""
    import subprocess, tempfile, shutil
    if isinstance(beats, str):
        beats = [beats]
    if not beats:
        raise ValueError("reel needs at least one beat")
    if not shutil.which(_ffmpeg()):
        raise RuntimeError(f"ffmpeg not found ('{_ffmpeg()}'); set FFMPEG_BIN or install ffmpeg")
    dims = SIZES.get(size, SIZES["story"])
    fps = 30
    tmp = tempfile.mkdtemp(prefix="reel_")
    segs = []
    try:
        for i, text in enumerate(beats):
            png = os.path.join(tmp, f"beat_{i:02d}.jpg")
            if mode == "stock":
                render_stock(text, png, query=query, size=size, preset=preset, source=source)
            else:
                render_card(text, png, size=size, preset=preset)
            seg = os.path.join(tmp, f"seg_{i:02d}.mp4")
            dur = float(secs_per) if float(secs_per) > 0 else secs_for_text(text)
            frames = int(dur * fps)
            vf = (
                f"scale={dims[0]}:{dims[1]}:force_original_aspect_ratio=increase,"
                f"crop={dims[0]}:{dims[1]},"
                f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={dims[0]}x{dims[1]}:fps={fps},"
                f"format=yuv420p"
            )
            subprocess.run(
                [_ffmpeg(), "-y", "-loop", "1", "-i", png, "-t", "%.3f" % dur,
                 "-r", str(fps), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", seg],
                check=True, capture_output=True,
            )
            segs.append(seg)
        # concat the segments
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for s in segs:
                f.write(f"file '{s.replace(os.sep, '/')}'\n")
        silent = os.path.join(tmp, "video.mp4")
        subprocess.run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", silent], check=True, capture_output=True)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if music and os.path.exists(music):
            mux_music(silent, music, out_path)
        else:
            shutil.copyfile(silent, out_path)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="Social Content Studio: programmatic post renderer")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("card", help="fully code-drawn card")
    c.add_argument("--text", required=True)
    c.add_argument("--handle", default="")
    c.add_argument("--size", default="square", choices=list(SIZES))
    c.add_argument("--preset", default="night", choices=list(STYLES))
    c.add_argument("--out", required=True)

    s = sub.add_parser("stock", help="fetched photo or your own image + text")
    s.add_argument("--text", required=True)
    s.add_argument("--query", default=None, help="search terms (or a direct URL when --source url)")
    s.add_argument("--image", default=None, help="path to your own image")
    s.add_argument("--source", default="openverse", choices=list(_SOURCES), help="fetch source")
    s.add_argument("--handle", default="")
    s.add_argument("--size", default="square", choices=list(SIZES))
    s.add_argument("--preset", default="night", choices=list(STYLES))
    s.add_argument("--out", required=True)

    cr = sub.add_parser("carousel", help="multi-slide carousel (split slides with ||)")
    cr.add_argument("--slides", required=True, help="slide texts separated by ||")
    cr.add_argument("--handle", default="")
    cr.add_argument("--size", default="portrait", choices=list(SIZES))
    cr.add_argument("--preset", default="night", choices=list(STYLES))
    cr.add_argument("--mode", default="card", choices=["card", "stock"])
    cr.add_argument("--query", default=None, help="stock query when --mode stock")
    cr.add_argument("--source", default="openverse", choices=list(_SOURCES))
    cr.add_argument("--out", required=True, help="output directory")

    rl = sub.add_parser("reel", help="programmatic reel (beats split with ||) + ffmpeg")
    rl.add_argument("--beats", required=True, help="beat texts separated by || (first = hook)")
    rl.add_argument("--music", default=None, help="path to a music bed (optional)")
    rl.add_argument("--secs", type=float, default=2.6, help="seconds per beat")
    rl.add_argument("--size", default="story", choices=list(SIZES))
    rl.add_argument("--preset", default="night", choices=list(STYLES))
    rl.add_argument("--mode", default="card", choices=["card", "stock"])
    rl.add_argument("--query", default=None, help="stock query when --mode stock")
    rl.add_argument("--source", default="openverse", choices=list(_SOURCES))
    rl.add_argument("--out", required=True, help="output .mp4")

    fe = sub.add_parser("fetch", help="fetch one image (no text overlay) and save it")
    fe.add_argument("--query", required=True, help="search terms (or a direct URL when --source url)")
    fe.add_argument("--source", default="openverse", choices=list(_SOURCES))
    fe.add_argument("--size", default="square", choices=list(SIZES))
    fe.add_argument("--out", required=True)

    a = p.parse_args(argv)
    if a.cmd == "card":
        out = render_card(a.text, a.out, handle=a.handle, size=a.size, preset=a.preset)
    elif a.cmd == "stock":
        out = render_stock(a.text, a.out, query=a.query, image_path=a.image, source=a.source,
                           handle=a.handle, size=a.size, preset=a.preset)
    elif a.cmd == "carousel":
        slides = [s.strip() for s in a.slides.split("||") if s.strip()]
        paths = render_carousel(slides, a.out, handle=a.handle, size=a.size,
                                preset=a.preset, mode=a.mode, query=a.query, source=a.source)
        out = f"{len(paths)} slides in {a.out}"
    elif a.cmd == "fetch":
        out = fetch_image(a.query, a.out, source=a.source, size=a.size)
    else:  # reel
        beats = [b.strip() for b in a.beats.split("||") if b.strip()]
        out = render_reel(beats, a.out, music=a.music, secs_per=a.secs, size=a.size,
                          preset=a.preset, mode=a.mode, query=a.query, source=a.source)
    print(f"rendered {out}")


if __name__ == "__main__":
    main()
