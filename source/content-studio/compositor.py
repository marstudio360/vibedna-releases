#!/usr/bin/env python3
"""
Social Content Studio: the PRO layer-stack compositor.

This is the professional-suite core: a post is a DOCUMENT, a document is an ordered
stack of LAYERS, and each layer is a typed primitive or effect with its own params,
blend mode, and opacity. One compositor renders the stack to an image. The editor
(the studio UI) and the MCP both drive the same document model, so anything the
editor can do, chat can do, and vice versa.

Image layers pull from these input sources, all first-class (no AI generation here):
  - "src"              -> a web address, a local file path, a data: URL, or a sample photo name
  - source "file"      -> IMPORT YOUR OWN INPUT (e.g. a background you made)
  - source "openverse"/"pexels"/"unsplash"/"pixabay"/"url" -> fetch
  - source "library"   -> your local image library

Content layers paint onto the canvas; ADJUSTMENT layers transform everything below
them (like a real editor's adjustment layers). Pillow only, no GPU.

Document shape:
  {
    "size": "square" | "portrait" | "story" | [w, h],
    "layers": [
      {"type": "gradient", "kind": "linear", "angle": 90,
       "stops": [[0, [14,16,34]], [1, [4,5,14]]]},
      {"type": "image", "source": "file", "path": "bg.png", "fit": "cover", "opacity": 1},
      {"type": "duotone", "dark": [10,12,30], "light": [230,220,255], "opacity": 0.8},
      {"type": "grain", "amount": 0.25},
      {"type": "vignette", "amount": 0.5},
      {"type": "text", "text": "Small steps, every day", "size": 0.11,
       "color": [240,242,250], "y": 0.5, "tracking": 0, "shadow": true, "glow": 12},
    ]
  }
"""
from __future__ import annotations
import ast
import builtins as _builtins
import importlib
import os
import re
import sys
import types
import zlib
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_engine as pe  # reuse SIZES, fonts, fetch/library sources, wrap


def _dims(size):
    if isinstance(size, str):
        return pe.SIZES.get(size, pe.SIZES["square"])
    return (int(size[0]), int(size[1]))


def _rgba(c, default_a=255):
    if c is None:
        return (0, 0, 0, 0)
    if len(c) == 4:
        return tuple(int(x) for x in c)
    return (int(c[0]), int(c[1]), int(c[2]), default_a)


# --- CONTENT layers: return a full-canvas RGBA image ---

def _l_solid(layer, dims):
    img = Image.new("RGBA", dims, (0, 0, 0, 0))
    img.paste(_rgba(layer.get("color", [0, 0, 0])), (0, 0, *dims))
    return img


def _l_gradient(layer, dims):
    w, h = dims
    stops = layer.get("stops", [[0, [14, 16, 34]], [1, [4, 5, 14]]])
    stops = sorted(([float(t), _rgba(c)] for t, c in stops), key=lambda s: s[0])

    def sample(t):
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(4))
        return tuple(stops[-1][1])

    if layer.get("kind") == "radial":
        cx, cy = layer.get("center", [0.5, 0.42])
        rad = float(layer.get("radius", 0.7)) * max(w, h)
        cxp, cyp = cx * w, cy * h
        mask = Image.new("L", dims, 0)
        base = Image.new("RGBA", dims, sample(1.0))
        # build ring gradient by stacking translucent ellipses
        steps = 48
        d = ImageDraw.Draw(base)
        for i in range(steps, 0, -1):
            r = rad * i / steps
            # stop 0 belongs at the CENTER: the biggest ellipse takes the outermost stop and
            # each smaller one painted over it steps toward stop 0.
            col = sample(i / steps)
            d.ellipse([cxp - r, cyp - r, cxp + r, cyp + r], fill=col)
        return base
    # linear
    strip = Image.new("RGBA", (1, h))
    for y in range(h):
        strip.putpixel((0, y), sample(y / max(1, h - 1)))
    img = strip.resize(dims)
    angle = float(layer.get("angle", 90))
    if abs(angle - 90) > 1:  # 90 = top->bottom (default); rotate for other angles
        img = img.rotate(90 - angle, resample=Image.BICUBIC, expand=False)
    return img


_SRC_CACHE = {}


def _src_bytes(src):
    """The bytes behind an image layer's `src`: a web address, a data: URL, a path on the
    studio site as the web editor writes it ("/content-studio/samples/x.jpg", resolved
    against STUDIO_URL), or a local file. A download is kept for the rest of the process,
    so a carousel or a reel that reuses a photo fetches it once."""
    import base64
    import urllib.parse
    import urllib.request
    src = str(src).strip()
    if src.startswith("data:"):
        head, _, body = src.partition(",")
        return base64.b64decode(body) if ";base64" in head else urllib.parse.unquote_to_bytes(body)
    if os.path.isfile(src):
        with open(src, "rb") as f:
            return f.read()
    if re.fullmatch(r"[A-Za-z0-9_-]+", src):
        # a sample photo by name ("coffee-window"), the way the templates take it
        src = "/content-studio/samples/" + src + ".jpg"
    if src.startswith("/") and not src.startswith("//"):
        src = os.environ.get("STUDIO_URL", "https://vibedna.ai").rstrip("/") + src
    scheme = urllib.parse.urlsplit(src).scheme.lower()
    if scheme == "blob":
        raise RuntimeError("image layer: a blob: address only exists inside the browser tab that "
                           "made it; embed the picture as a data: URL instead")
    if scheme not in ("http", "https"):
        raise RuntimeError(f"image layer: file not found: {src}")
    if src not in _SRC_CACHE:
        req = urllib.request.Request(src, headers={"User-Agent": "VibeDNA-ContentStudio/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(_SRC_CACHE) >= 48:
            _SRC_CACHE.clear()
        _SRC_CACHE[src] = data
    return _SRC_CACHE[src]


def _l_image(layer, dims):
    source = layer.get("source", "file")
    fit = layer.get("fit", "cover")
    src = layer.get("src")
    if src:
        # `src` is what makes a saved project portable: an address opens the same way in the
        # browser editor and in this engine, so preview and export stay the same image.
        import io as _io
        img = Image.open(_io.BytesIO(_src_bytes(src)))
    elif source == "file":
        path = layer.get("path")
        if not path or not os.path.exists(path):
            raise RuntimeError(f"image layer: file not found: {path}")
        img = Image.open(path)
    elif source == "library":
        # import-your-library: `library` points at ANY local art folder (else the default)
        img = pe.library_pick(layer.get("query", ""), root=layer.get("library"))
    else:
        img = pe._fetch_source(layer.get("query", ""), source, dims)
    # PRESERVE transparency: a logo / mark / cutout PNG must show what is below it, not
    # flatten to black. Only opaque images drop to RGB.
    has_alpha = ("A" in img.getbands()) or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA") if has_alpha else img.convert("RGB")
    # box = [x0, y0, x1, y1] in 0-1 places the image in a REGION of the canvas instead of the
    # whole canvas (photo on top, text below; collages), cropped to fill it like the editor.
    box = layer.get("box")
    if box:
        x0, y0 = int(box[0] * dims[0]), int(box[1] * dims[1])
        x1, y1 = int(box[2] * dims[0]), int(box[3] * dims[1])
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        inner = (ImageOps.contain(img, (bw, bh)) if fit == "contain"
                 else ImageOps.fit(img, (bw, bh), method=Image.LANCZOS))
        canvas = Image.new("RGBA", dims, (0, 0, 0, 0))
        canvas.paste(inner, (x0 + (bw - inner.width) // 2, y0 + (bh - inner.height) // 2),
                     inner if inner.mode == "RGBA" else None)
        return canvas
    if fit == "contain":
        img = ImageOps.contain(img, dims)
        canvas = Image.new("RGBA", dims, (0, 0, 0, 0))
        pos = ((dims[0] - img.width) // 2, (dims[1] - img.height) // 2)
        canvas.paste(img, pos, img if img.mode == "RGBA" else None)
        return canvas
    return ImageOps.fit(img, dims, method=Image.LANCZOS).convert("RGBA")


def _l_particles(layer, dims):
    seed = str(layer.get("seed", layer.get("text", "seed")))
    color = tuple(layer.get("color", [150, 160, 210]))
    count = int(layer.get("count", 220))
    img = Image.new("RGBA", dims, (0, 0, 0, 0))
    import random
    # crc32, not hash(): str hashes are salted per process, so the same seed drew a
    # different field on every run.
    rnd = random.Random(zlib.crc32(seed.encode("utf-8")))
    d = ImageDraw.Draw(img)
    w, h = dims
    for _ in range(count):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.choice([1, 1, 1, 2, 2, 3])
        a = rnd.randint(int(255 * 0.04), int(255 * 0.22))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*color, a))
    return img


_SS = 4  # supersampling factor for circles and lines


def _l_shape(layer, dims):
    w, h = dims
    img = Image.new("RGBA", dims, (0, 0, 0, 0))
    kind = layer.get("kind", "rect")
    col = _rgba(layer.get("color", [255, 255, 255]))
    box = layer.get("box", [0.1, 0.1, 0.9, 0.9])  # normalized
    x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    width = float(layer.get("width", 0) or 0)  # 0 = filled
    # An outline is centred on the edge, like a canvas stroke, so the same box draws the same
    # size in the web editor and here.
    half = width / 2.0 if (width and kind != "line") else 0.0
    if kind == "rect":
        d = ImageDraw.Draw(img)
        d.rectangle([x0 - half, y0 - half, x1 + half, y1 + half], fill=None if width else col,
                    outline=col if width else None, width=max(1, int(round(width))))
        return img
    if kind not in ("circle", "line"):
        return img
    # Circles and slanted lines are drawn 4x larger in their own patch and scaled down, so
    # their edges come out smooth instead of stair-stepped.
    lw = width or (3.0 if kind == "line" else 0.0)
    pad = lw + half + 2
    px0, py0 = int(min(x0, x1) - pad), int(min(y0, y1) - pad)
    px1, py1 = int(max(x0, x1) + pad) + 1, int(max(y0, y1) + pad) + 1
    pw, ph = max(1, px1 - px0), max(1, py1 - py0)
    mask = Image.new("L", (pw * _SS, ph * _SS), 0)
    md = ImageDraw.Draw(mask)
    s = lambda x, y: ((x - px0) * _SS, (y - py0) * _SS)
    if kind == "circle":
        a, b = s(x0 - half, y0 - half), s(x1 + half, y1 + half)
        md.ellipse([a[0], a[1], b[0], b[1]], fill=None if width else 255,
                   outline=255 if width else None, width=max(1, int(round(lw * _SS))))
    else:
        md.line([*s(x0, y0), *s(x1, y1)], fill=255, width=max(1, int(round(max(1.0, lw) * _SS))))
    mask = mask.resize((pw, ph), Image.BOX)
    if col[3] < 255:
        mask = mask.point(lambda v: v * col[3] // 255)
    patch = Image.new("RGBA", (pw, ph), col[:3] + (0,))
    patch.putalpha(mask)
    img.paste(patch, (px0, py0))
    return img


def _l_text(layer, dims):
    w, h = dims
    img = Image.new("RGBA", dims, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = str(layer.get("text", ""))
    color = _rgba(layer.get("color", [240, 242, 250]))
    size = float(layer.get("size", 0.10))
    fsize = max(1.0, size * w if size < 1 else size)  # fractional px, like the canvas
    bold = bool(layer.get("bold"))
    font = pe._load_font(layer.get("font"), fsize, mono=bool(layer.get("mono")), bold=bold)
    # A face with no bold file on this machine is thickened with a stroke of its own colour,
    # so `bold` still reads as bold instead of silently doing nothing.
    fake_bold = bold and not getattr(font, "_is_bold", False)
    thicken = max(1, int(round(fsize * 0.025))) if fake_bold else 0
    tracking = int(layer.get("tracking", 0))
    align = layer.get("align", "center")
    wrap_w = float(layer.get("wrap", 0.78)) * w
    cx = float(layer.get("x", 0.5)) * w
    cy = float(layer.get("y", 0.5)) * h
    # Lines sit on their BASELINE, the way the web editor's canvas draws them, so a document
    # lands in the same place in both. Pillow's built-in bitmap font has no baseline anchor.
    baseline = isinstance(font, ImageFont.FreeTypeFont)

    def put(x, y, s, fill):
        extra = {"stroke_width": thicken, "stroke_fill": fill} if thicken else {}
        if baseline:
            d.text((x, y), s, font=font, fill=fill, anchor="ls", **extra)
        else:
            d.text((x, y - fsize * 0.8), s, font=font, fill=fill, **extra)

    # Widths come from the same face at 8x, divided back: at the real size FreeType rounds
    # every advance to a whole pixel, which made lines up to 1% wider than the editor's and
    # broke them at different words.
    fine = pe._load_font(layer.get("font"), fsize * 8, mono=bool(layer.get("mono")), bold=bold) if baseline else None

    def adv(s):
        return d.textlength(s, font=fine) / 8.0 if fine is not None else d.textlength(s, font=font)

    def measure(s):
        if tracking:
            return sum(adv(ch) + tracking for ch in s) - tracking
        return adv(s)

    def draw_line(s, x, y, fill):
        if not tracking:
            put(x, y, s, fill)
            return
        cur = x
        for ch in s:
            put(cur, y, ch, fill)
            cur += adv(ch) + tracking

    # wrap
    words, lines, curline = text.split(), [], ""
    for wd in words:
        trial = (curline + " " + wd).strip()
        if measure(trial) <= wrap_w:
            curline = trial
        else:
            if curline:
                lines.append(curline)
            curline = wd
    if curline:
        lines.append(curline)
    lines = lines or [""]

    line_h = fsize * float(layer.get("leading", 1.28))
    total = len(lines) * line_h
    y = cy - total / 2 + fsize  # `y` is the centre of the block; this is the first baseline
    glow = int(layer.get("glow", 0))
    shadow = layer.get("shadow", False)
    stroke = layer.get("stroke")
    for ln in lines:
        tw = measure(ln)
        x = cx - tw / 2 if align == "center" else (float(layer.get("x", 0.1)) * w if align == "left" else cx - tw)
        if shadow:
            draw_line(ln, x + 2, y + 3, (0, 0, 0, 130))
        if stroke:
            sc = _rgba(stroke)
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                draw_line(ln, x + dx, y + dy, sc)
        draw_line(ln, x, y, color)
        y += line_h
    if glow:
        halo = img.filter(ImageFilter.GaussianBlur(glow))
        img = Image.alpha_composite(halo, img)
    return img


# --- ADJUSTMENT layers: transform the composite BELOW them ---

def _a_duotone(base, layer, dims):
    dark = tuple(layer.get("dark", [10, 12, 30]))
    light = tuple(layer.get("light", [235, 225, 255]))
    lum = base.convert("L")
    duo = ImageOps.colorize(lum, black=dark, white=light).convert("RGBA")
    duo.putalpha(base.getchannel("A"))
    return duo


def _a_tint(base, layer, dims):
    color = tuple(layer.get("color", [120, 90, 200]))
    amt = float(layer.get("amount", 0.3))
    tint = Image.new("RGBA", dims, (*color, 255))
    out = Image.blend(base.convert("RGBA"), tint, amt)
    out.putalpha(base.getchannel("A"))
    return out


def _a_grade(base, layer, dims):
    rgb = base.convert("RGB")
    if "brightness" in layer:
        rgb = ImageEnhance.Brightness(rgb).enhance(float(layer["brightness"]))
    if "contrast" in layer:
        rgb = ImageEnhance.Contrast(rgb).enhance(float(layer["contrast"]))
    if "saturation" in layer:
        rgb = ImageEnhance.Color(rgb).enhance(float(layer["saturation"]))
    out = rgb.convert("RGBA")
    out.putalpha(base.getchannel("A"))
    return out


def _a_posterize(base, layer, dims):
    bits = int(layer.get("bits", 3))
    out = ImageOps.posterize(base.convert("RGB"), bits).convert("RGBA")
    out.putalpha(base.getchannel("A"))
    return out


def _a_grain(base, layer, dims):
    amt = float(layer.get("amount", 0.2))
    noise = Image.effect_noise(dims, int(60 * amt)).convert("L")
    noise_rgba = Image.merge("RGBA", (noise, noise, noise, Image.new("L", dims, int(90 * amt))))
    return Image.alpha_composite(base, noise_rgba)


def _a_scanlines(base, layer, dims):
    w, h = dims
    gap = int(layer.get("gap", 3))
    op = int(255 * float(layer.get("opacity", 0.25)))
    col = tuple(layer.get("color", [0, 0, 0]))
    lines = Image.new("RGBA", dims, (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    for y in range(0, h, gap):
        d.line([0, y, w, y], fill=(*col, op), width=1)
    return Image.alpha_composite(base, lines)


def _a_vignette(base, layer, dims):
    w, h = dims
    amt = float(layer.get("amount", 0.5))
    col = tuple(layer.get("color", [0, 0, 0]))
    mask = Image.new("L", dims, 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w * 0.25, -h * 0.25, w * 1.25, h * 1.25], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(int(min(w, h) * 0.18)))
    dark = Image.new("RGBA", dims, (*col, int(255 * amt)))
    inv = ImageOps.invert(mask)
    dark.putalpha(inv)
    return Image.alpha_composite(base, dark)


def _a_blur(base, layer, dims):
    return base.filter(ImageFilter.GaussianBlur(float(layer.get("radius", 4))))


def _a_bloom(base, layer, dims):
    thr = int(255 * float(layer.get("threshold", 0.7)))
    rgb = base.convert("RGB")
    bright = rgb.point(lambda p: p if p > thr else 0)
    bright = bright.filter(ImageFilter.GaussianBlur(float(layer.get("radius", 18))))
    strength = float(layer.get("strength", 0.8))
    if strength != 1:
        bright = ImageEnhance.Brightness(bright).enhance(strength)
    out = ImageChops.screen(rgb, bright).convert("RGBA")
    out.putalpha(base.getchannel("A"))
    return out


def _a_chromatic(base, layer, dims):
    shift = int(layer.get("shift", 4))
    r, g, b, a = base.split()
    r = ImageChops.offset(r, shift, 0)
    b = ImageChops.offset(b, -shift, 0)
    return Image.merge("RGBA", (r, g, b, a))


CONTENT = {"solid": _l_solid, "gradient": _l_gradient, "image": _l_image,
           "particles": _l_particles, "shape": _l_shape, "text": _l_text}
ADJUST = {"duotone": _a_duotone, "tint": _a_tint, "grade": _a_grade, "posterize": _a_posterize,
          "grain": _a_grain, "scanlines": _a_scanlines, "vignette": _a_vignette,
          "blur": _a_blur, "bloom": _a_bloom, "chromatic": _a_chromatic}

# --- CUSTOM effects: the "no limits" hook. A project can register brand-new layer
# types (your AI can write them). Content fn(layer, dims)->RGBA; adjust fn(base, layer,
# dims)->RGBA. This is how the studio grows past the built-in 16 without editing core.
_CUSTOM_CONTENT = {}
_CUSTOM_ADJUST = {}
_EFFECTS_LOADED = [False]
# What the last load_effects() refused or failed on, one line each, for list_effects.
EFFECTS_REPORT = []


def register_effect(name, fn, kind="content"):
    """Register a new layer type. kind='content' (paints) or 'adjust' (transforms below)."""
    (_CUSTOM_ADJUST if kind == "adjust" else _CUSTOM_CONTENT)[name] = fn


# --- effect sandbox ---
# Effect code is written by an AI at runtime and re-executed on every start, so a prompt
# injection that reaches add_effect would otherwise become permanent code execution. Every
# effect is checked twice (when it is added and every time the file loads) against the
# rules below, then runs with a reduced set of builtins and read-only module views.
EFFECT_IMPORTS = {"math", "random", "colorsys"}
EFFECT_PIL = {"Image", "ImageDraw", "ImageFilter", "ImageOps", "ImageChops", "ImageEnhance"}
_EFFECT_BANNED = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib", "builtins",
    "eval", "exec", "compile", "open", "__import__", "getattr", "setattr", "delattr",
    "globals", "locals", "vars", "input", "breakpoint",
}
# Attribute-only bans: frame and code objects lead back to real module globals, and these
# Pillow members write files, start another program, or expose the raw C image
# (`im.save_ppm` writes any path).
_EFFECT_BANNED_ATTRS = _EFFECT_BANNED | {
    "gi_frame", "gi_code", "gi_yieldfrom", "cr_frame", "cr_code", "cr_await", "ag_frame",
    "ag_code", "f_back", "f_globals", "f_locals", "f_builtins", "f_code", "tb_frame",
    "tb_next", "save", "show", "im", "save_ppm", "ptr",
}
_EFFECT_BUILTIN_NAMES = (
    "abs", "all", "any", "bool", "bytes", "chr", "dict", "divmod", "enumerate", "filter",
    "float", "frozenset", "int", "isinstance", "iter", "len", "list", "map", "max", "min",
    "next", "ord", "pow", "range", "reversed", "round", "set", "slice", "sorted", "str",
    "sum", "tuple", "zip",
    "ArithmeticError", "Exception", "IndexError", "KeyError", "StopIteration", "TypeError",
    "ValueError", "ZeroDivisionError",
)


def validate_effect_source(src, filename="<effect>"):
    """Return a list of problems (empty = allowed) for a piece of effect code."""
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as e:
        return [f"line {e.lineno}: syntax error: {e.msg}"]
    bad = []
    for node in ast.walk(tree):
        ln = getattr(node, "lineno", "?")
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name not in EFFECT_IMPORTS:
                    bad.append(f"line {ln}: import '{a.name}' is not allowed "
                               f"(allowed: {', '.join(sorted(EFFECT_IMPORTS))})")
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names]
            if node.level or not (node.module in EFFECT_IMPORTS or node.module == "PIL") or "*" in names:
                bad.append(f"line {ln}: 'from {'.' * node.level}{node.module or ''} import ...' "
                           "is not allowed")
            elif node.module == "PIL" and not set(names) <= EFFECT_PIL:
                bad.append(f"line {ln}: from PIL only {', '.join(sorted(EFFECT_PIL))} may be imported")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in _EFFECT_BANNED_ATTRS:
                bad.append(f"line {ln}: attribute '.{node.attr}' is not allowed")
        elif isinstance(node, ast.Name):
            if node.id in _EFFECT_BANNED or node.id.startswith("__"):
                bad.append(f"line {ln}: name '{node.id}' is not allowed")
        elif isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Await)):
            bad.append(f"line {ln}: classes and async code are not allowed in an effect")
    return bad


class _ReadOnlyModule:
    """What effect code sees instead of a real module: public, non-module attributes only,
    so `Image.io`, `ImageOps.Image` and the like do not lead anywhere."""
    __slots__ = ("_mod",)

    def __init__(self, mod):
        object.__setattr__(self, "_mod", mod)

    def __getattr__(self, name):
        if name.startswith("_") or name in _EFFECT_BANNED_ATTRS:
            raise AttributeError(name)
        val = getattr(object.__getattribute__(self, "_mod"), name)
        if isinstance(val, types.ModuleType):
            raise AttributeError(name)
        return val

    def __setattr__(self, name, value):
        raise AttributeError("read-only")


def _effect_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name in EFFECT_IMPORTS:
        return _ReadOnlyModule(importlib.import_module(name))
    if level == 0 and name == "PIL" and fromlist and set(fromlist) <= EFFECT_PIL:
        return _ReadOnlyModule(types.SimpleNamespace(
            **{n: _ReadOnlyModule(importlib.import_module("PIL." + n)) for n in fromlist}))
    raise ImportError(f"import of '{name}' is not allowed in an effect")


def _effect_namespace():
    safe_builtins = {n: getattr(_builtins, n) for n in _EFFECT_BUILTIN_NAMES}
    safe_builtins["__import__"] = _effect_import
    fonts = _ReadOnlyModule(types.SimpleNamespace(
        load_font=pe._load_font, list_fonts=pe.list_fonts, SIZES=dict(pe.SIZES)))
    return {"__builtins__": safe_builtins, "__name__": "post_engine_effects",
            "register_effect": register_effect, "load_font": pe._load_font, "pe": fonts,
            "Image": _ReadOnlyModule(Image), "ImageDraw": _ReadOnlyModule(ImageDraw),
            "ImageFilter": _ReadOnlyModule(ImageFilter), "ImageOps": _ReadOnlyModule(ImageOps),
            "ImageChops": _ReadOnlyModule(ImageChops), "ImageEnhance": _ReadOnlyModule(ImageEnhance)}


_BLOCK_MARK = re.compile(r"^# --- add_effect: .*? ---[ \t]*$", re.M)


def load_effects(path=None):
    """Load a project effects .py whose blocks call register_effect(...). Each block written
    by add_effect is checked on its own with validate_effect_source(); a block that breaks
    the rules is NOT executed and is listed in EFFECTS_REPORT (and on stderr), the others
    still load. In scope: register_effect, Pillow (Image, ImageDraw, ImageFilter, ImageOps,
    ImageChops, ImageEnhance), load_font(name, size) (also pe.load_font), and imports of
    math, random and colorsys. Returns the custom count."""
    path = path or os.environ.get("POST_ENGINE_EFFECTS") or str(Path.home() / ".post-engine" / "effects.py")
    EFFECTS_REPORT.clear()
    if not path or not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        src = f.read()
    starts = [0] + [m.start() for m in _BLOCK_MARK.finditer(src)]
    ns = _effect_namespace()
    for i, a in enumerate(starts):
        block = src[a:starts[i + 1] if i + 1 < len(starts) else len(src)]
        if not block.strip():
            continue
        first = src.count("\n", 0, a) + 1
        label = f"{os.path.basename(path)} from line {first}"
        # pad with newlines so line numbers in errors match the file
        problems = validate_effect_source("\n" * (first - 1) + block, path)
        if problems:
            EFFECTS_REPORT.append(f"REFUSED, not run: {label}: " + "; ".join(problems))
            continue
        try:
            exec(compile("\n" * (first - 1) + block, path, "exec"), ns)
        except Exception as e:
            EFFECTS_REPORT.append(f"FAILED: {label}: {type(e).__name__}: {e}")
    for line in EFFECTS_REPORT:
        print("post-engine effects:", line, file=sys.stderr)
    return len(_CUSTOM_CONTENT) + len(_CUSTOM_ADJUST)


def _apply_opacity(img, opacity):
    if opacity >= 1:
        return img
    a = img.getchannel("A").point(lambda p: int(p * opacity))
    out = img.copy()
    out.putalpha(a)
    return out


def _composite(base, top, blend):
    if blend == "screen":
        merged = ImageChops.screen(base.convert("RGB"), top.convert("RGB")).convert("RGBA")
        merged.putalpha(base.getchannel("A"))
        # respect the top layer's alpha as a mask
        return Image.composite(merged, base, top.getchannel("A"))
    if blend == "multiply":
        merged = ImageChops.multiply(base.convert("RGB"), top.convert("RGB")).convert("RGBA")
        return Image.composite(merged, base, top.getchannel("A"))
    return Image.alpha_composite(base, top)


def layer_types():
    return {"content": sorted(CONTENT), "adjustment": sorted(ADJUST),
            "image_sources": list(pe._SOURCES) + ["file"]}


def apply_free_limits(path: str, cap: int = 1080, mark: str = "vibedna.ai/content-studio") -> None:
    """Downscale a rendered image so its longest side is <= `cap` and stamp a
    small watermark. Used for FREE-tier output; Pro output is left untouched.
    Idempotent enough for a one-shot post-process. Overwrites `path` in place,
    preserving the original format."""
    try:
        img = Image.open(path)
        fmt = img.format
        if not fmt:
            ext = os.path.splitext(path)[1].lower()
            fmt = "JPEG" if ext in (".jpg", ".jpeg") else "PNG"
        img.load()  # force read before we overwrite the same path
        w, h = img.size

        if max(w, h) > cap:
            scale = cap / float(max(w, h))
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
            w, h = img.size

        # watermark, bottom-right
        fsize = max(12, int(h * 0.022))
        font = pe._load_font(None, fsize)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        try:
            l, t, r, b = d.textbbox((0, 0), mark, font=font)
            tw, th = r - l, b - t
        except Exception:
            tw, th = int(d.textlength(mark, font=font)), fsize
        pad = max(6, int(min(w, h) * 0.022))
        x, y = w - tw - pad, h - th - pad
        d.text((x + 1, y + 1), mark, font=font, fill=(0, 0, 0, 89))    # shadow ~35% alpha
        d.text((x, y), mark, font=font, fill=(255, 255, 255, 153))     # text  ~60% alpha

        if img.mode == "RGBA":
            img = Image.alpha_composite(img, overlay)
        else:
            merged = Image.alpha_composite(img.convert("RGBA"), overlay)
            img = merged.convert("RGB") if fmt == "JPEG" else merged

        if fmt == "JPEG":
            img.convert("RGB").save(path, "JPEG", quality=92)
        else:
            img.save(path, fmt)
    except Exception:
        # a failed watermark must never break a render; leave the file as-is
        return


def _doc_text(doc):
    """All the readable text in a beat, joined. Used to work out how long to hold it."""
    parts = []
    for layer in (doc or {}).get("layers", []) or []:
        if isinstance(layer, dict) and layer.get("text"):
            parts.append(str(layer["text"]))
    return " ".join(parts)


def render_reel(docs, out_path, music=None, secs_per=0, size="story"):
    """Render a list of DOCUMENTS into a vertical reel: each doc is a beat (the first is
    the hook), shown with a slow Ken Burns zoom, concatenated, with an optional music bed.
    Each beat is composited by the full layer engine, so a reel is just a sequence of the
    same documents the editor/MCP build. Needs ffmpeg.

    secs_per=0 (the default) gives each beat the time its own text needs to be read. Pass a
    number to force every beat to the same length."""
    import subprocess, tempfile, shutil
    if not docs:
        raise ValueError("reel needs at least one document")
    ff = pe._ffmpeg()
    if not shutil.which(ff):
        raise RuntimeError(f"ffmpeg not found ('{ff}'); set FFMPEG_BIN or install ffmpeg")
    W, H = _dims(size)
    fps = 30
    tmp = tempfile.mkdtemp(prefix="reeldoc_")
    segs = []
    try:
        for i, doc in enumerate(docs):
            d = dict(doc); d["size"] = size  # normalize each beat to the reel size
            jpg = os.path.join(tmp, f"beat_{i:02d}.jpg")
            render_document(d, jpg)
            seg = os.path.join(tmp, f"seg_{i:02d}.mp4")
            dur = float(secs_per) if float(secs_per) > 0 else pe.secs_for_text(_doc_text(d))
            frames = int(dur * fps)
            vf = (
                f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},format=yuv420p"
            )
            subprocess.run([ff, "-y", "-loop", "1", "-i", jpg, "-t", "%.3f" % dur, "-r", str(fps),
                            "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", seg],
                           check=True, capture_output=True)
            segs.append(seg)
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for s in segs:
                f.write(f"file '{s.replace(os.sep, '/')}'\n")
        silent = os.path.join(tmp, "video.mp4")
        subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", silent],
                       check=True, capture_output=True)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if music and os.path.exists(music):
            pe.mux_music(silent, music, out_path)
        else:
            shutil.copyfile(silent, out_path)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_document(doc, out_path):
    """Render a layer-stack document to an image file. Content layers paint; adjustment
    layers transform everything below; custom (project-registered) effects work too."""
    if not _EFFECTS_LOADED[0]:
        try:
            load_effects()
        except Exception as e:
            # stderr: on a stdio MCP server stdout is the protocol channel
            EFFECTS_REPORT.append(f"FAILED to read the effects file: {e}")
            print("post-engine: project effects failed to load:", e, file=sys.stderr)
        _EFFECTS_LOADED[0] = True
    dims = _dims(doc.get("size", "square"))
    base = Image.new("RGBA", dims, _rgba(doc.get("background", [0, 0, 0]), 255))
    for layer in doc.get("layers", []):
        if not layer.get("visible", True):
            continue
        t = layer.get("type")
        opacity = float(layer.get("opacity", 1))
        blend = layer.get("blend", "normal")
        content_fn = CONTENT.get(t) or _CUSTOM_CONTENT.get(t)
        adjust_fn = ADJUST.get(t) or _CUSTOM_ADJUST.get(t)
        if content_fn:
            top = _apply_opacity(content_fn(layer, dims), opacity)
            base = _composite(base, top, blend)
        elif adjust_fn:
            adjusted = adjust_fn(base, layer, dims)
            base = Image.blend(base, adjusted, opacity) if opacity < 1 else adjusted
        else:
            known = sorted(list(CONTENT) + list(ADJUST) + list(_CUSTOM_CONTENT) + list(_CUSTOM_ADJUST))
            raise ValueError(f"unknown layer type '{t}'; known: {known}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, quality=94)
    return out_path
