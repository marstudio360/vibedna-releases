#!/usr/bin/env python3
"""
Template library for the Social Content Studio.

A TEMPLATE is a named layer-stack builder: build(template, fields, brand, size) returns
a compositor DOCUMENT. Templates reference brand ROLES (accent/text/body/muted) so the
same template renders in any brand. `fields` is the per-post content; every field has a
default, so a template renders a complete example with no fields at all.

The library mirrors the web editor's templates one to one (same layers, same fields, same
defaults), so a post made here and one made in the editor look the same.

Photo fields (photo, before, after, photo1...) take a sample name (see SAMPLE_PHOTOS), an
image URL, or a path to your own file.

YOUR OWN TEMPLATES are saved documents, one JSON file each in ~/.content-studio/templates/
(or $CONTENT_STUDIO_HOME/templates/). The web editor's "Save as my template" downloads the
same file, so a template moves freely between the editor, this engine and other people.
"""
import base64
import copy
import io
import json
import mimetypes
import os
import re
import sys
import unicodedata
import urllib.parse
import zlib
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brands
import post_engine as pe
from post_engine import SIZES


def _font(b, role):
    """The brand's font for a role (display, body, mono, poster), or None for the engine's
    fallback. A brand file may carry no `fonts` block at all."""
    return (b.get("fonts") or {}).get(role)


def _f(fields, key, default):
    """A field's value, or the default when the field is missing (an empty string is kept)."""
    v = fields.get(key)
    return default if v is None else v


# --- The first templates: quote, name cover, thumbnail, release ---

def quote_card(fields, brand, size):
    b = brands.get_brand(brand); p = b["palette"]
    layers = brands.bg_layers(brand)
    if b.get("eyebrow"):
        layers.append({"type": "text", "text": b["eyebrow"], "mono": True, "size": 0.026,
                       "tracking": 8, "color": p["accent"], "y": 0.16, "font": _font(b, "mono")})
    layers.append({"type": "text", "text": _f(fields, "quote", _f(fields, "text", "Your line here")),
                   "size": 0.085, "color": p["text"], "y": 0.5, "shadow": True, "glow": 8,
                   "font": _font(b, "display")})
    tail = fields.get("handle") or b.get("handle") or b.get("cta")
    if tail:
        layers.append({"type": "text", "text": tail, "mono": True, "size": 0.028,
                       "color": p["muted"], "y": 0.92, "font": _font(b, "mono")})
    return {"size": size, "layers": layers}


def motiv(fields, brand, size):
    """A big quote over a background: your own image (`image`), a fetched one (`query` +
    `source`), one from your library, or the brand background. Graded and vignetted so the
    line reads."""
    b = brands.get_brand(brand); p = b["palette"]
    layers = []
    if fields.get("image"):
        layers.append({"type": "image", "source": "file", "path": fields["image"], "fit": "cover"})
    elif fields.get("library") or fields.get("source") == "library":
        layers.append({"type": "image", "source": "library", "library": fields.get("library"),
                       "query": fields.get("query", ""), "fit": "cover"})
    elif fields.get("query"):
        layers.append({"type": "image", "source": fields.get("source", "openverse"),
                       "query": fields["query"], "fit": "cover"})
    else:
        layers = brands.bg_layers(brand)
    layers.append({"type": "grade", "brightness": 0.72, "saturation": 0.95})
    layers.append({"type": "vignette", "amount": 0.5})
    layers.append({"type": "text", "text": _f(fields, "quote", _f(fields, "text", "Rise, quietly")),
                   "size": 0.1, "color": p["text"], "y": 0.5, "shadow": True,
                   "font": _font(b, "display")})
    tail = fields.get("handle") or b.get("handle")
    if tail:
        layers.append({"type": "text", "text": tail, "mono": True, "size": 0.03,
                       "color": p["accent"], "y": 0.93, "font": _font(b, "mono")})
    return {"size": size, "layers": layers}


def name_cover(fields, brand, size):
    """A cover where the name IS the title, with optional hero art behind it."""
    b = brands.get_brand(brand); p = b["palette"]
    layers = brands.bg_layers(brand)
    if fields.get("image"):
        layers.append({"type": "image", "source": "file", "path": fields["image"], "fit": "cover", "opacity": 0.9})
        layers.append({"type": "duotone", "dark": p["bg_bottom"], "light": p["accent"], "opacity": 0.5})
        layers.append({"type": "vignette", "amount": 0.5})
    if b.get("eyebrow"):
        layers.append({"type": "text", "text": b["eyebrow"], "mono": True, "size": 0.024,
                       "tracking": 10, "color": p["accent"], "y": 0.12, "font": _font(b, "mono")})
    layers.append({"type": "text", "text": str(_f(fields, "name", _f(fields, "title", "Velvet"))).upper(),
                   "size": 0.14, "color": p["text"], "y": 0.5, "tracking": 2, "shadow": True,
                   "font": _font(b, "display")})
    if fields.get("subtitle"):
        layers.append({"type": "text", "text": fields["subtitle"], "size": 0.04, "color": p["muted"],
                       "y": 0.63, "font": _font(b, "body")})
    return {"size": size, "layers": layers}


def genre_thumb(fields, brand, size):
    """Video thumbnail: a wide scene with the GENRE set large over it, on two lines.

    The genre is the biggest element, not the track name or the brand: that is what reads at
    thumbnail size in a crowded results page. fields: genre (use '|' to break the line by
    hand), image (the cover or a background), sub (a small label under the genre).
    """
    b = brands.get_brand(brand); p = b["palette"]
    genre = str(_f(fields, "genre", "Ambient Focus"))
    if "|" in genre:
        lines = [x.strip().upper() for x in genre.split("|")]
    else:
        w = genre.upper().split(" ")
        lines = [" ".join(w[:-1]), w[-1]] if len(w) > 2 else ([w[0], w[1]] if len(w) == 2 else w)
    layers = []
    if fields.get("image"):
        layers.append({"type": "image", "source": "file", "path": fields["image"], "fit": "cover"})
    else:
        layers = brands.bg_layers(brand)
    # The veil rises from the bottom and leaves the top third clean, where the subject of a
    # cover usually sits.
    layers.append({"type": "gradient", "kind": "linear", "angle": 90,
                   "stops": [[0.0, [4, 11, 15, 0]], [0.30, [4, 11, 15, 0]], [1.0, [4, 11, 15, 238]]]})
    # The longest line is fitted to 90% of the width (never above 0.115), and capitals are set
    # tight: the line step follows that size, so lines neither wrap nor overlap whatever the
    # canvas shape. The last line keeps its place.
    W, H = _dims(size)
    probe = pe._load_font(_font(b, "poster"), 200)
    widest = max([probe.getlength(ln) for ln in lines if ln] or [1.0])
    tsize = min(0.115, 0.90 * 200 / widest)
    step = tsize * W * 0.86 / H
    last = 0.755 if len(lines) > 1 else 0.70
    for i, ln in enumerate(lines):
        layers.append({"type": "text", "text": ln, "size": tsize, "color": p["text"], "wrap": 0.94,
                       "x": 0.052, "y": last - step * (len(lines) - 1 - i), "align": "left",
                       "font": _font(b, "poster")})
    layers.append({"type": "text", "text": fields.get("sub", "INSTRUMENTAL"), "size": 0.026,
                   "tracking": 4, "color": p["accent"], "x": 0.055, "y": last + 0.155,
                   "align": "left", "font": _font(b, "mono")})
    layers.append({"type": "text", "text": b.get("eyebrow", ""), "size": 0.024,
                   "tracking": 4, "color": p["accent"], "x": 0.948, "y": 0.93,
                   "align": "right", "font": _font(b, "mono")})
    return {"size": size, "layers": layers}


def release_square(fields, brand, size):
    """A release post: the cover alone, filling the square. The cover already carries the
    title and the artwork, and the words belong in the caption."""
    layers = []
    if fields.get("image"):
        layers.append({"type": "image", "source": "file", "path": fields["image"], "fit": "cover"})
    else:
        layers = brands.bg_layers(brand)
    return {"size": size, "layers": layers}


def quote_over_image(fields, brand, size):
    """Quote card: an atmospheric background, the line set large, and an optional logo.

    fields: text (the line), image (background), logo (a PNG with transparency, optional).
    """
    b = brands.get_brand(brand); p = b["palette"]
    layers = []
    if fields.get("image"):
        layers.append({"type": "image", "source": "file", "path": fields["image"], "fit": "cover"})
    else:
        layers = brands.bg_layers(brand)
    layers.append({"type": "grade", "brightness": 0.82, "saturation": 0.92})
    layers.append({"type": "gradient", "kind": "linear", "angle": 90,
                   "stops": [[0.0, [4, 11, 15, 120]], [0.5, [4, 11, 15, 60]], [1.0, [4, 11, 15, 190]]]})
    layers.append({"type": "text", "text": _f(fields, "text", "Your line here"), "size": 0.072,
                   "color": p["text"], "y": 0.46, "wrap": 0.84,
                   "font": _font(b, "poster"), "shadow": True})
    if fields.get("logo"):
        layers.append({"type": "image", "source": "file", "path": fields["logo"],
                       "fit": "contain", "box": [0.44, 0.845, 0.56, 0.925]})
    return {"size": size, "layers": layers}


# --- THE LIBRARY: what a small business or a creator actually posts ---
# One template per real Instagram format, drawn in role colours so any pack restyles it. Boxes
# are fractions of the canvas, text sizes are fractions of the width, and text `y` is the
# CENTRE of the block, so a line the user adds grows both ways instead of running off the bottom.

SANS = brands.SANS
SERIF = brands.SERIF
# Symbol glyphs (the heart) come from a symbol face: a text face may not carry them.
SYMBOL = "'Segoe UI Symbol', 'Apple Symbols', 'Noto Sans Symbols 2', sans-serif"
SAMPLE_URL = "https://vibedna.ai/content-studio/samples/"
SAMPLE_PHOTOS = ["coffee-window", "kitchen-table", "laptop-desk", "linen-texture",
                 "notebooks-flatlay", "ocean-horizon", "plant-light", "shelf-after",
                 "shelf-before", "street-dusk", "vase-stone"]
INK = [20, 20, 22]
WHITE = [255, 255, 255]
BLACK = [0, 0, 0]


def _jround(x):
    """Round half up, like the editor's Math.round (Python's round() rounds half to even)."""
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def _mix(a, b, t):
    return [_jround(a[i] + (b[i] - a[i]) * t) for i in range(3)]


def _lum(c):
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


def _apart(a, b):
    return abs(_lum(a) - _lum(b))


def _fade(c, a):
    return [c[0], c[1], c[2], _jround(a * 255)]


def _look(brand):
    """Every role the library draws with. A pack you wrote may only carry the basics, so the
    rest is derived, and each derived colour is checked against what it sits on."""
    b = brands.get_brand(brand); p = b["palette"]; fonts = b.get("fonts") or {}
    bg = list(p["bg_top"]); text = list(p["text"]); accent = list(p["accent"])
    muted = list(p.get("muted") or text)
    light = _lum(bg) > 0.5
    surface = list(p.get("surface") or _mix(bg, text, 0.04 if light else 0.09))
    card_light = _lum(surface) > 0.5
    # text on a card: the pack's ink where it reads, plain ink or white where it does not
    text_on_card = card_light == (_lum(text) < 0.5)
    card_ink = text if text_on_card else (INK if card_light else WHITE)
    return SimpleNamespace(
        bg=bg, bg2=list(p.get("bg_bottom") or bg), ink=text, body=list(p.get("body") or text),
        muted=muted, accent=accent, surface=surface, light=light, card_ink=card_ink,
        card_muted=muted if text_on_card else _mix(card_ink, surface, 0.45),
        on_accent=list(p.get("on_accent") or (_mix(accent, BLACK, 0.85) if _lum(accent) > 0.6 else WHITE)),
        # the accent as type on a card: a pale accent (lime) hands over to the background colour
        card_accent=accent if _apart(accent, surface) > 0.35 else (bg if _apart(bg, surface) > 0.35 else card_ink),
        rule=_mix(bg, text, 0.2 if light else 0.3),
        display=fonts.get("display") or SERIF, sans=fonts.get("body") or SANS, k=fonts.get("scale") or 1,
        name=b.get("eyebrow") or "", handle=b.get("handle") or "@yourbrand", site=b.get("cta") or "yourbrand.com",
    )


def _tx(text, **o):
    return {"type": "text", "text": text, **o}


def _rect(box, color, width=0):
    layer = {"type": "shape", "kind": "rect", "box": box, "color": color}
    if width:
        layer["width"] = width
    return layer


def _line(box, color, width=2):
    return {"type": "shape", "kind": "line", "box": box, "color": color, "width": width}


def _photo(value, box=None):
    """An image layer from a photo field: a sample name, an image URL or a local path.
    An empty field draws nothing, like an empty photo slot in the editor."""
    v = str(value or "").strip()
    if not v:
        return None
    src = SAMPLE_URL + v + ".jpg" if re.fullmatch(r"[A-Za-z0-9_-]+", v) else v
    layer = {"type": "image", "src": src, "fit": "cover"}
    if box:
        layer["box"] = box
    return layer


def _ground(L):
    return {"type": "gradient", "kind": "linear", "angle": 90, "stops": [[0, L.bg], [1, L.bg2]]}


def _dims(size):
    if isinstance(size, str):
        return SIZES.get(size, SIZES["square"])
    return (int(size[0]), int(size[1]))


def _dot(size, cx, cy, d, color, width=0):
    """A circle `d` pixels wide centred on (cx, cy): the box is in fractions, so it needs the canvas."""
    W, H = _dims(size)
    layer = {"type": "shape", "kind": "circle",
             "box": [cx - d / 2 / W, cy - d / 2 / H, cx + d / 2 / W, cy + d / 2 / H], "color": color}
    if width:
        layer["width"] = width
    return layer


def _actions(size, y, xs, color):
    """The four post actions (reply, repost, like, share) drawn in strokes, about 34 px each."""
    W, H = _dims(size)

    def seg(cx, a, b, c, d):
        return _line([cx + a / W, y + b / H, cx + c / W, y + d / H], color, 3)

    r, p, l, s = xs
    return [
        _dot(size, r, y, 34, color, 3), seg(r, -10, 13, -17, 21),
        seg(p, -16, -6, 14, -6), seg(p, 14, -6, 8, -12), seg(p, 14, -6, 8, 0),
        seg(p, 16, 6, -14, 6), seg(p, -14, 6, -8, 0), seg(p, -14, 6, -8, 12),
        _tx("\u2661", font=SYMBOL, size=56 / W, color=color, x=l, y=y + 2 / H),
        seg(s, 0, -17, 0, 5), seg(s, 0, -17, -7, -10), seg(s, 0, -17, 7, -10),
        seg(s, -13, -2, -13, 14), seg(s, -13, 14, 13, 14), seg(s, 13, 14, 13, -2),
    ]


def _doc(size, layers):
    return {"size": size, "layers": [x for x in layers if x]}


# --- Feed posts ---

def editorial_quote(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _tx(_f(f, "masthead", L.name or "THE WEEKLY NOTE"), font=L.sans, size=0.021, tracking=5, color=L.ink, align="left", x=0.08, y=0.07),
        _tx(_f(f, "issue", "No. 07"), font=L.display, size=0.03 * L.k, color=L.ink, align="right", x=0.92, y=0.07),
        _line([0.08, 0.096, 0.92, 0.096], L.ink, 2),
        _tx("\u201c", font=SERIF, size=0.3, color=L.accent, align="left", x=0.065, y=0.255),
        _tx(_f(f, "quote", "Good work is built in small steps, taken every single day."), font=L.display, size=0.08 * L.k, leading=1.18, color=L.ink, align="left", x=0.08, wrap=0.84, y=0.47),
        _rect([0.08, 0.715, 0.15, 0.719], L.accent),
        _tx(_f(f, "author", "Your Name"), font=L.sans, size=0.032, color=L.ink, align="left", x=0.08, y=0.76),
        _tx(_f(f, "role", "Founder, Your Studio"), font=L.sans, size=0.025, color=L.muted, align="left", x=0.08, y=0.8),
        _line([0.08, 0.9, 0.92, 0.9], L.rule, 1.5),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.022, color=L.muted, align="left", x=0.08, y=0.935),
        _tx(_f(f, "site", L.site), font=L.sans, size=0.022, color=L.muted, align="right", x=0.92, y=0.935),
    ])


def launch_announcement(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _rect([0.04, 0.04, 0.96, 0.96], L.ink, 3),
        _tx(_f(f, "kicker", "JUST LAUNCHED"), font=L.sans, size=0.022, tracking=6, color=L.ink, align="left", x=0.09, y=0.11),
        _tx(_f(f, "when", "FRIDAY, 10 AM"), font=L.sans, size=0.022, tracking=4, color=L.ink, align="right", x=0.91, y=0.11),
        _tx(_f(f, "title", "New drop"), font=L.display, size=0.2 * L.k, leading=0.98, color=L.accent, align="left", x=0.085, wrap=0.62, y=0.35),
        _tx(_f(f, "name", "The Weekend Collection"), font=L.display, size=0.052 * L.k, color=L.ink, align="left", x=0.09, wrap=0.82, y=0.685),
        _tx(_f(f, "detail", "Six new pieces, made in small batches."), font=L.sans, size=0.03, color=L.body, align="left", x=0.09, y=0.743),
        _rect([0.09, 0.8, 0.5, 0.885], L.accent),
        _tx(_f(f, "cta", "SHOP THE DROP"), font=L.sans, size=0.026, tracking=4, color=L.on_accent, x=0.295, y=0.8425),
        _tx(_f(f, "link", "Link in bio \u2192"), font=L.sans, size=0.028, color=L.ink, align="right", x=0.91, y=0.8425),
    ])


def tips_list(f, brand, size):
    L = _look(brand)
    items = [
        (_f(f, "tip1", "Pick one priority"), _f(f, "text1", "Write it down before you open your inbox.")),
        (_f(f, "tip2", "Batch the small tasks"), _f(f, "text2", "Answer messages twice a day, not all day.")),
        (_f(f, "tip3", "Plan tomorrow tonight"), _f(f, "text3", "Five minutes tonight saves an hour tomorrow.")),
    ]
    layers = [
        _ground(L),
        _tx(_f(f, "kicker", "QUICK GUIDE"), font=L.sans, size=0.021, tracking=5, color=L.accent, align="left", x=0.08, y=0.07),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.021, color=L.muted, align="right", x=0.92, y=0.07),
        _tx(_f(f, "title", "3 ways to start your week with focus"), font=L.display, size=0.08 * L.k, leading=1.12, color=L.ink, align="left", x=0.08, wrap=0.8, y=0.2),
        _line([0.08, 0.33, 0.92, 0.33], L.ink, 2),
    ]
    for i, (head, text) in enumerate(items):
        y = 0.44 + i * 0.175
        layers += [
            _tx("0%d" % (i + 1), font=L.display, size=0.06 * L.k, color=L.accent, align="left", x=0.08, y=y),
            _tx(head, font=L.sans, size=0.04, color=L.ink, align="left", x=0.24, wrap=0.68, y=y - 0.03),
            _tx(text, font=L.sans, size=0.03, leading=1.35, color=L.body, align="left", x=0.24, wrap=0.68, y=y + 0.024),
        ]
        if i < len(items) - 1:
            layers.append(_line([0.24, y + 0.095, 0.92, y + 0.095], L.rule, 1.5))
    layers += [
        _tx(_f(f, "footer", "Save this for your next Monday"), font=L.sans, size=0.026, color=L.ink, align="left", x=0.08, y=0.935),
        _tx(_f(f, "site", L.site), font=L.sans, size=0.022, color=L.muted, align="right", x=0.92, y=0.935),
    ]
    return _doc(size, layers)


def product_spotlight(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _photo(_f(f, "photo", "vase-stone"), [0, 0, 1, 0.62]),
        _rect([0.72, 0.585, 0.92, 0.655], L.accent),
        _tx(_f(f, "price", "$38"), font=L.display, size=0.05 * L.k, color=L.on_accent, x=0.82, y=0.62),
        _tx(_f(f, "kicker", "PRODUCT SPOTLIGHT"), font=L.sans, size=0.021, tracking=5, color=L.accent, align="left", x=0.08, y=0.7),
        _tx(_f(f, "name", "Stone Vase No. 2"), font=L.display, size=0.072 * L.k, color=L.ink, align="left", x=0.08, wrap=0.84, y=0.765),
        _tx(_f(f, "body", "Hand-thrown ceramic in a soft sand glaze. Holds a single stem or a full bunch."), font=L.sans, size=0.029, leading=1.4, color=L.body, align="left", x=0.08, wrap=0.8, y=0.845),
        _line([0.08, 0.905, 0.92, 0.905], L.rule, 1.5),
        _tx(_f(f, "cta", "Shop via the link in bio"), font=L.sans, size=0.024, color=L.ink, align="left", x=0.08, y=0.94),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.024, color=L.muted, align="right", x=0.92, y=0.94),
    ])


def event_date(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _rect([0.07, 0.07, 0.4, 0.56], L.accent),
        _tx(_f(f, "month", "OCT"), font=L.sans, size=0.04, tracking=8, color=L.on_accent, x=0.235, y=0.15),
        _tx(_f(f, "day", "24"), font=L.display, size=0.2 * L.k, color=L.on_accent, x=0.235, y=0.32),
        _tx(_f(f, "weekday", "FRIDAY"), font=L.sans, size=0.026, tracking=6, color=L.on_accent, x=0.235, y=0.48),
        _tx(_f(f, "kicker", "YOU ARE INVITED"), font=L.sans, size=0.022, tracking=5, color=L.accent, align="left", x=0.46, y=0.1),
        _tx(_f(f, "title", "Open Studio Night"), font=L.display, size=0.072 * L.k, leading=1.08, color=L.ink, align="left", x=0.46, wrap=0.47, y=0.25),
        _tx(_f(f, "time", "6 to 9 PM"), font=L.sans, size=0.034, color=L.ink, align="left", x=0.46, y=0.42),
        _tx(_f(f, "place", "Your address, Your city"), font=L.sans, size=0.028, color=L.muted, align="left", x=0.46, wrap=0.47, y=0.475),
        _line([0.07, 0.63, 0.93, 0.63], L.rule, 2),
        _tx(_f(f, "body", "Drinks, music and a first look at the new season. Free entry, bring a friend."), font=L.display, size=0.046 * L.k, leading=1.25, color=L.ink, align="left", x=0.07, wrap=0.86, y=0.755),
        _tx(_f(f, "cta", "RSVP via the link in bio"), font=L.sans, size=0.024, tracking=2, color=L.accent, align="left", x=0.07, y=0.9),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.024, color=L.muted, align="right", x=0.93, y=0.9),
    ])


def before_after(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _tx(_f(f, "kicker", "SHELF REFRESH"), font=L.sans, size=0.021, tracking=5, color=L.accent, align="left", x=0.06, y=0.065),
        _tx(_f(f, "title", "Before and after"), font=L.display, size=0.068 * L.k, color=L.ink, align="left", x=0.06, wrap=0.88, y=0.125),
        _photo(_f(f, "before", "shelf-before"), [0.06, 0.18, 0.495, 0.86]),
        _photo(_f(f, "after", "shelf-after"), [0.505, 0.18, 0.94, 0.86]),
        _rect([0.085, 0.79, 0.24, 0.835], L.ink),
        _tx(_f(f, "left", "BEFORE"), font=L.sans, size=0.022, tracking=4, color=L.bg, x=0.1625, y=0.8125),
        _rect([0.53, 0.79, 0.66, 0.835], L.accent),
        _tx(_f(f, "right", "AFTER"), font=L.sans, size=0.022, tracking=4, color=L.on_accent, x=0.595, y=0.8125),
        _tx(_f(f, "caption", "Styled in one afternoon with pieces from the shop"), font=L.sans, size=0.028, color=L.ink, align="left", x=0.06, wrap=0.88, y=0.905),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.022, color=L.muted, align="left", x=0.06, y=0.95),
        _tx(_f(f, "site", L.site), font=L.sans, size=0.022, color=L.muted, align="right", x=0.94, y=0.95),
    ])


def text_post_card(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        {"type": "solid", "color": L.accent},
        _rect([0.083, 0.212, 0.933, 0.812], _fade(BLACK, 0.16)),
        _rect([0.075, 0.2, 0.925, 0.8], L.surface),
        _dot(size, 0.169, 0.294, 96, L.ink if L.light else L.accent),
        _tx(_f(f, "initial", "Y"), font=L.display, size=0.04 * L.k, color=L.bg if L.light else L.on_accent, x=0.169, y=0.294),
        _tx(_f(f, "name", "Your Name"), font=L.sans, size=0.034, color=L.card_ink, align="left", x=0.24, y=0.278),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.028, color=L.card_muted, align="left", x=0.24, y=0.318),
        _tx(_f(f, "text", "The best marketing we ever did was answering every message like it mattered."), font=L.sans, size=0.048, leading=1.3, color=L.card_ink, align="left", x=0.125, wrap=0.75, y=0.5),
        _tx(_f(f, "time", "9:41 AM \u00b7 Oct 12"), font=L.sans, size=0.024, color=L.card_muted, align="left", x=0.125, y=0.655),
        _line([0.125, 0.69, 0.875, 0.69], _mix(L.surface, L.card_ink, 0.15), 1.5),
        *_actions(size, 0.745, [0.16, 0.38, 0.6, 0.82], L.card_muted),
    ])


# --- Carousel: one system across cover, content and closing ---

def _carousel_frame(L, f, n, total):
    x1 = 0.08 + 0.84 * (n / total)
    return [
        _ground(L),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.022, color=L.ink, align="left", x=0.08, y=0.065),
        _tx("%d / %d" % (n, total), font=L.sans, size=0.022, tracking=2, color=L.muted, align="right", x=0.92, y=0.065),
        _line([0.08, 0.945, 0.92, 0.945], L.rule, 4),
        _line([0.08, 0.945, x1, 0.945], L.accent, 4),
    ]


def carousel_cover(f, brand, size):
    L = _look(brand)
    return _doc(size, _carousel_frame(L, f, 1, 5) + [
        _rect([0.08, 0.2, 0.22, 0.243], L.accent),
        _tx(_f(f, "kicker", "GUIDE"), font=L.sans, size=0.022, tracking=5, color=L.on_accent, x=0.15, y=0.2215),
        _tx(_f(f, "title", "5 habits that grew our small business"), font=L.display, size=0.118 * L.k, leading=1.04, color=L.ink, align="left", x=0.08, wrap=0.84, y=0.45),
        _tx(_f(f, "sub", "What we changed in our first year of business, and what each change gave back."), font=L.sans, size=0.035, leading=1.4, color=L.body, align="left", x=0.08, wrap=0.74, y=0.71),
        _tx(_f(f, "cta", "Swipe to read"), font=L.sans, size=0.028, color=L.ink, align="left", x=0.08, y=0.87),
        _tx("\u2192", font=L.sans, size=0.06, color=L.accent, align="right", x=0.92, y=0.866),
    ])


def carousel_slide(f, brand, size):
    L = _look(brand)
    return _doc(size, _carousel_frame(L, f, 2, 5) + [
        _tx(_f(f, "number", "02"), font=L.display, size=0.2 * L.k, color=L.accent, align="left", x=0.075, y=0.215),
        _tx(_f(f, "title", "Post less, but on a steady schedule"), font=L.display, size=0.08 * L.k, leading=1.1, color=L.ink, align="left", x=0.08, wrap=0.8, y=0.405),
        _tx(_f(f, "body", "Two planned posts a week beat seven rushed ones. Pick your days, batch the work, and protect that time like a meeting."), font=L.sans, size=0.037, leading=1.45, color=L.body, align="left", x=0.08, wrap=0.8, y=0.585),
        _rect([0.08, 0.735, 0.92, 0.865], L.surface),
        _rect([0.08, 0.735, 0.089, 0.865], L.accent),
        _tx(_f(f, "tip", "Try this: block two mornings a week only for content, and keep them."), font=L.sans, size=0.031, leading=1.4, color=L.card_ink, align="left", x=0.125, wrap=0.74, y=0.8),
    ])


def carousel_closing(f, brand, size):
    L = _look(brand)
    return _doc(size, _carousel_frame(L, f, 5, 5) + [
        _tx(_f(f, "kicker", "THANKS FOR READING"), font=L.sans, size=0.022, tracking=5, color=L.accent, y=0.315),
        _tx(_f(f, "title", "Found this useful?"), font=L.display, size=0.095 * L.k, leading=1.08, color=L.ink, wrap=0.8, y=0.415),
        _tx(_f(f, "body", "Save it for later and send it to a friend who is building something of their own."), font=L.sans, size=0.034, leading=1.45, color=L.body, wrap=0.72, y=0.545),
        _rect([0.2, 0.665, 0.8, 0.735], L.accent),
        _tx(_f(f, "cta", "Follow %s" % _f(f, "handle", L.handle)), font=L.sans, size=0.032, color=L.on_accent, y=0.7),
        _tx(_f(f, "site", L.site), font=L.sans, size=0.026, color=L.muted, y=0.785),
    ])


# --- Collages ---

def collage_three(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _tx(_f(f, "kicker", "THIS WEEK AT THE STUDIO"), font=L.sans, size=0.021, tracking=5, color=L.accent, align="left", x=0.06, y=0.065),
        _tx(_f(f, "title", "Slow mornings, good work"), font=L.display, size=0.068 * L.k, color=L.ink, align="left", x=0.06, wrap=0.88, y=0.125),
        _photo(_f(f, "photo1", "coffee-window"), [0.06, 0.18, 0.6, 0.88]),
        _photo(_f(f, "photo2", "plant-light"), [0.62, 0.18, 0.94, 0.522]),
        _photo(_f(f, "photo3", "notebooks-flatlay"), [0.62, 0.538, 0.94, 0.88]),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.022, color=L.muted, align="left", x=0.06, y=0.935),
        _tx(_f(f, "site", L.site), font=L.sans, size=0.022, color=L.muted, align="right", x=0.94, y=0.935),
    ])


def collage_four(f, brand, size):
    L = _look(brand)
    a, b, c, d = 0.045, 0.4925, 0.5075, 0.955
    return _doc(size, [
        _ground(L),
        _photo(_f(f, "photo1", "kitchen-table"), [a, a, b, b]),
        _photo(_f(f, "photo2", "laptop-desk"), [c, a, d, b]),
        _photo(_f(f, "photo3", "linen-texture"), [a, c, b, d]),
        _photo(_f(f, "photo4", "vase-stone"), [c, c, d, d]),
        _rect([0.25, 0.425, 0.75, 0.575], L.bg),
        _tx(_f(f, "title", "A week in pictures"), font=L.display, size=0.05 * L.k, color=L.ink, wrap=0.46, y=0.483),
        _tx(_f(f, "kicker", "MONDAY TO FRIDAY"), font=L.sans, size=0.019, tracking=5, color=L.muted, y=0.535),
    ])


# --- Stories and reel covers (1080 x 1920: the top and bottom tenths sit under the app's UI) ---

def story_question(f, brand, size):
    L = _look(brand)
    ring = L.accent if L.light else L.bg
    return _doc(size, [
        _ground(L),
        _tx(_f(f, "title", "Ask us anything"), font=L.display, size=0.11 * L.k, leading=1.05, color=L.ink, wrap=0.84, y=0.315),
        _tx(_f(f, "sub", "We are answering every question this week."), font=L.sans, size=0.036, color=L.body, wrap=0.76, y=0.395),
        _rect([0.133, 0.473, 0.883, 0.693], _fade(BLACK, 0.18)),
        _rect([0.125, 0.465, 0.875, 0.685], WHITE),
        _rect([0.125, 0.465, 0.875, 0.6], L.accent),
        _dot(size, 0.5, 0.465, 132, WHITE),
        _dot(size, 0.5, 0.465, 108, ring),
        _tx(_f(f, "question", "What should we make next?"), font=L.sans, size=0.046, color=L.on_accent, wrap=0.64, y=0.5375),
        _rect([0.17, 0.617, 0.83, 0.668], [238, 238, 240]),
        _tx(_f(f, "placeholder", "Type something..."), font=L.sans, size=0.034, color=[150, 150, 156], y=0.6425),
        _tx(_f(f, "footer", "Send yours. We share the answers on Friday."), font=L.sans, size=0.032, leading=1.4, color=L.body, wrap=0.7, y=0.775),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.03, tracking=2, color=L.ink, y=0.86),
    ])


def story_countdown(f, brand, size):
    L = _look(brand)
    # a serif display sets old-style figures (the 3 and 4 drop below the line), wrong for a clock
    clock = L.sans if re.search(r"(^|,)\s*serif\s*$", L.display) else L.display
    digits = [(_f(f, "days", "03"), "DAYS", 0.3), (_f(f, "hours", "12"), "HOURS", 0.5),
              (_f(f, "minutes", "45"), "MINUTES", 0.7)]
    layers = [
        _photo(_f(f, "photo", "ocean-horizon")),
        {"type": "gradient", "kind": "linear", "angle": 90,
         "stops": [[0, _fade(BLACK, 0.4)], [0.38, _fade(BLACK, 0.05)], [0.62, _fade(BLACK, 0.05)], [1, _fade(BLACK, 0.6)]]},
        _tx(_f(f, "kicker", "SOMETHING NEW IS COMING"), font=L.sans, size=0.026, tracking=6, color=WHITE, y=0.2, shadow=True),
        _tx(_f(f, "title", "Coming soon"), font=L.display, size=0.14 * L.k, leading=1.02, color=WHITE, wrap=0.9, y=0.29, shadow=True),
        _rect([0.148, 0.428, 0.868, 0.628], _fade(BLACK, 0.22)),
        _rect([0.14, 0.42, 0.86, 0.62], WHITE),
        _tx(_f(f, "label", "LAUNCH DAY"), font=L.sans, size=0.024, tracking=6, color=L.card_accent, y=0.455),
        _tx(":", font=L.display, size=0.07, color=[170, 170, 176], x=0.4, y=0.522),
        _tx(":", font=L.display, size=0.07, color=[170, 170, 176], x=0.6, y=0.522),
    ]
    for n, label, x in digits:
        layers += [
            _tx(n, font=clock, size=0.1 * (1 if clock == L.sans else L.k), color=INK, x=x, y=0.528),
            _tx(label, font=L.sans, size=0.019, tracking=4, color=[120, 120, 126], x=x, y=0.585),
        ]
    layers += [
        _tx(_f(f, "date", "Friday, October 24"), font=L.sans, size=0.036, color=WHITE, y=0.68, shadow=True),
        _tx(_f(f, "footer", "Turn on notifications so you see it first"), font=L.sans, size=0.03, color=WHITE, wrap=0.7, y=0.83, shadow=True),
    ]
    return _doc(size, layers)


def story_new_post(f, brand, size):
    L = _look(brand)
    return _doc(size, [
        _ground(L),
        _tx(_f(f, "kicker", "NEW POST"), font=L.sans, size=0.03, tracking=8, color=L.accent, y=0.125),
        _rect([0.11, 0.182, 0.91, 0.772], _fade(BLACK, 0.14)),
        _rect([0.1, 0.17, 0.9, 0.76], L.surface),
        _dot(size, 0.145, 0.196, 60, L.card_accent),
        _tx(_f(f, "handle", L.handle), font=L.sans, size=0.027, color=L.card_ink, align="left", x=0.185, y=0.196),
        _dot(size, 0.825, 0.196, 8, L.card_ink), _dot(size, 0.845, 0.196, 8, L.card_ink), _dot(size, 0.865, 0.196, 8, L.card_ink),
        _photo(_f(f, "photo", "kitchen-table"), [0.1, 0.222, 0.9, 0.7]),
        *_actions(size, 0.73, [0.15, 0.24, 0.33, 0.85], L.card_ink),
        _tx(_f(f, "title", "Fresh on the feed"), font=L.display, size=0.075 * L.k, color=L.ink, wrap=0.84, y=0.835),
        _tx(_f(f, "cta", "Tap the post to see it \u2192"), font=L.sans, size=0.03, color=L.muted, y=0.885),
    ])


def reel_cover(f, brand, size):
    L = _look(brand)
    label = str(_f(f, "kicker", "EPISODE 03"))
    half = min(0.4, (len(label) * 0.0175 + 0.06) / 2)
    return _doc(size, [
        _photo(_f(f, "photo", "street-dusk")),
        {"type": "grade", "brightness": 1.25, "contrast": 1.05, "saturation": 1.08},
        {"type": "gradient", "kind": "linear", "angle": 90,
         "stops": [[0, _fade(BLACK, 0.2)], [0.25, _fade(BLACK, 0)], [0.45, _fade(BLACK, 0.05)], [1, _fade(BLACK, 0.7)]]},
        _rect([0.5 - half, 0.548, 0.5 + half, 0.584], L.accent),
        _tx(label, font=L.sans, size=0.024, tracking=5, color=L.on_accent, y=0.566),
        _tx(_f(f, "title", "A day at the studio"), font=L.display, size=0.12 * L.k, leading=1.04, color=WHITE, wrap=0.64, y=0.665, shadow=True),
        _tx(_f(f, "sub", "Watch to the end"), font=L.sans, size=0.032, color=[235, 235, 240], y=0.77, shadow=True),
    ])


# A template is LAYOUT, so it is named for what it draws, never for whose it is.
# `default_brand` is the pack it opens in: "default" (the neutral pack) for the first
# templates, and its own style pack for the library ones (`styled`), which keep that pack
# while you ask for "default" so they open looking designed. Any other brand you pass wins.
# Your own brands come from ~/.content-studio/brands/.
TEMPLATES = {
    "quote-card": {"fn": quote_card, "fields": ["quote", "handle"],
                   "default_brand": "default", "default_size": "square"},
    "motiv": {"fn": motiv, "fields": ["quote", "image", "library", "query", "source", "handle"],
              "default_brand": "default", "default_size": "portrait", "label": "Quote over photo"},
    "name-cover": {"fn": name_cover, "fields": ["name", "subtitle", "image"],
                   "default_brand": "default", "default_size": "square"},
    "quote-over-image": {"fn": quote_over_image, "fields": ["text", "image", "logo"],
                         "default_brand": "default", "default_size": "square"},
    "release-square": {"fn": release_square, "fields": ["image"],
                       "default_brand": "default", "default_size": "square", "label": "Release cover"},
    "genre-thumb": {"fn": genre_thumb, "fields": ["genre", "image", "sub"],
                    "default_brand": "default", "default_size": [1280, 720],
                    "format": "Video thumbnail", "label": "Genre thumbnail"},
    "editorial-quote": {"fn": editorial_quote, "default_brand": "editorial", "default_size": "portrait",
                        "format": "Feed post", "styled": True,
                        "fields": ["masthead", "issue", "quote", "author", "role", "handle", "site"]},
    "launch-announcement": {"fn": launch_announcement, "default_brand": "bold", "default_size": "square",
                            "format": "Feed post", "styled": True,
                            "fields": ["kicker", "when", "title", "name", "detail", "cta", "link"]},
    "tips-list": {"fn": tips_list, "default_brand": "warm", "default_size": "portrait",
                  "format": "Feed post", "label": "Tips list", "styled": True,
                  "fields": ["kicker", "handle", "title", "tip1", "text1", "tip2", "text2",
                             "tip3", "text3", "footer", "site"]},
    "product-spotlight": {"fn": product_spotlight, "default_brand": "warm", "default_size": "portrait",
                          "format": "Feed post", "styled": True, "photos": ["photo"],
                          "fields": ["photo", "price", "kicker", "name", "body", "cta", "handle"]},
    "event-date": {"fn": event_date, "default_brand": "bold", "default_size": "square",
                   "format": "Feed post", "label": "Event", "styled": True,
                   "fields": ["month", "day", "weekday", "kicker", "title", "time", "place", "body",
                              "cta", "handle"]},
    "before-after": {"fn": before_after, "default_brand": "mono", "default_size": "portrait",
                     "format": "Feed post", "label": "Before and after", "styled": True,
                     "photos": ["before", "after"],
                     "fields": ["kicker", "title", "before", "after", "left", "right", "caption",
                                "handle", "site"]},
    "carousel-cover": {"fn": carousel_cover, "default_brand": "editorial", "default_size": "portrait",
                       "format": "Carousel", "label": "Carousel: cover", "styled": True,
                       "fields": ["handle", "kicker", "title", "sub", "cta"]},
    "carousel-slide": {"fn": carousel_slide, "default_brand": "editorial", "default_size": "portrait",
                       "format": "Carousel", "label": "Carousel: numbered slide", "styled": True,
                       "fields": ["handle", "number", "title", "body", "tip"]},
    "carousel-closing": {"fn": carousel_closing, "default_brand": "editorial", "default_size": "portrait",
                         "format": "Carousel", "label": "Carousel: closing", "styled": True,
                         "fields": ["handle", "kicker", "title", "body", "cta", "site"]},
    "collage-three": {"fn": collage_three, "default_brand": "editorial", "default_size": "portrait",
                      "format": "Collage", "label": "Collage, 3 photos", "styled": True,
                      "photos": ["photo1", "photo2", "photo3"],
                      "fields": ["kicker", "title", "photo1", "photo2", "photo3", "handle", "site"]},
    "collage-four": {"fn": collage_four, "default_brand": "mono", "default_size": "square",
                     "format": "Collage", "label": "Collage, 4 photos", "styled": True,
                     "photos": ["photo1", "photo2", "photo3", "photo4"],
                     "fields": ["photo1", "photo2", "photo3", "photo4", "title", "kicker"]},
    "story-question": {"fn": story_question, "default_brand": "bold", "default_size": "story",
                       "format": "Story", "label": "Story: question box", "styled": True,
                       "fields": ["title", "sub", "question", "placeholder", "footer", "handle"]},
    "story-countdown": {"fn": story_countdown, "default_brand": "mono", "default_size": "story",
                        "format": "Story", "label": "Story: coming soon", "styled": True,
                        "photos": ["photo"],
                        "fields": ["photo", "kicker", "title", "label", "days", "hours", "minutes",
                                   "date", "footer"]},
    "story-new-post": {"fn": story_new_post, "default_brand": "warm", "default_size": "story",
                       "format": "Story", "label": "Story: new post", "styled": True,
                       "photos": ["photo"],
                       "fields": ["kicker", "handle", "photo", "title", "cta"]},
    "reel-cover": {"fn": reel_cover, "default_brand": "bold", "default_size": "story",
                   "format": "Reel cover", "styled": True, "photos": ["photo"],
                   "fields": ["photo", "kicker", "title", "sub"]},
    "text-post-card": {"fn": text_post_card, "default_brand": "mono", "default_size": "square",
                       "format": "Text post", "label": "Text post card", "styled": True,
                       "fields": ["initial", "name", "handle", "text", "time"]},
}


def template_label(name):
    """A readable name for a template id."""
    t = TEMPLATES.get(name) or {}
    return t.get("label") or (name[:1].upper() + name[1:]).replace("-", " ").replace("_", " ")


def build(template, fields=None, brand=None, size=None):
    t = TEMPLATES.get(template)
    if not t:
        mine = find_user_template(template)
        if mine:
            # your own template keeps the colours it was saved with, so `brand` does not apply
            return build_user(mine, fields, size=size)
        raise ValueError(f"unknown template '{template}'; use one of "
                         f"{list(TEMPLATES) + sorted(user_templates())}")
    if brand and not brands.find_brand(brand):
        raise ValueError(brands.missing_brand_message(brand))
    key = brands.find_brand(brand) if brand else None
    if t.get("styled") and key in (None, "default") and brands.find_brand(t["default_brand"]):
        key = brands.find_brand(t["default_brand"])
    return t["fn"](fields or {}, key or t["default_brand"], size or t["default_size"])


def list_templates():
    out = {k: {"label": template_label(k), "format": v.get("format", "Feed post"),
               "fields": v["fields"], "photo_fields": v.get("photos", []),
               "default_brand": v["default_brand"], "default_size": v["default_size"]}
           for k, v in TEMPLATES.items()}
    for slug, t in user_templates().items():
        key = slug if slug not in out else slug + " (yours)"
        if "error" in t:
            out[key] = {"yours": True, "error": t["error"], "file": t["file"]}
            continue
        entry = {"label": t["name"], "format": t["format"], "yours": True,
                 "fields": [f["key"] for f in t["fields"]],
                 "saved_text": {f["key"]: _short(f["label"]) for f in t["fields"]},
                 "photo_fields": photo_fields(t["doc"]), "default_size": t["size"], "file": t["file"]}
        if key != slug:
            entry["error"] = "same name as a built-in template, so it cannot be used: rename the file"
        out[key] = entry
    return out


# --- Your own templates ---
#
# A user template is a saved DOCUMENT plus the list of its editable text. One JSON file per
# template, the same file the web editor writes when you "Save as my template":
#
#   {"kind": "vibedna-template", "version": 1, "name": "Launch card, green",
#    "format": "Feed post", "size": "portrait",
#    "doc": {"size": "portrait", "layers": [...]},
#    "fields": [{"key": "text1", "label": "NEW DROP"}, ...]}
#
# Every text layer carries "field": "text1", "text2"... in layer order, and `fields` lists them
# with the text they had when saved, so an AI can tell which is which. An image layer may also
# carry a `field` (photo1...) to make its picture swappable. Pictures travel inside the file as
# data: URLs, so a template works on any machine and in the browser.

TEMPLATE_KIND = "vibedna-template"
TEMPLATE_VERSION = 1
_MAX_TEMPLATE_BYTES = 40 * 1024 * 1024
_MAX_EMBED_BYTES = 15 * 1024 * 1024
_FIELD_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_SAMPLE_RE = re.compile(r"[A-Za-z0-9_-]+")
_IMAGE_MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif",
               "BMP": "image/bmp"}


def templates_dir():
    """Where your own templates live: $CONTENT_STUDIO_HOME/templates, else ~/.content-studio/templates."""
    return os.path.join(brands.studio_home(), "templates")


def template_slug(name):
    """A file-safe id for a template name: "Launch card, green" -> "launch-card-green"."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60].strip("-")
    # a name with no latin letters still needs a stable id
    return s or "template-%08x" % zlib.crc32(str(name).encode("utf-8"))


def _short(text, n=100):
    text = str(text)
    return text if len(text) <= n else text[:n - 3] + "..."


def _check_size(size):
    """square | portrait | story, [w, h], or "WxH"; anything else is refused with the options."""
    if isinstance(size, str):
        if size in SIZES:
            return size
        m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", size)
        if not m:
            raise ValueError(f"size '{size}' is not square, portrait, story or [width, height]")
        size = [m.group(1), m.group(2)]
    if isinstance(size, (list, tuple)) and len(size) == 2:
        try:
            w, h = int(size[0]), int(size[1])
        except (TypeError, ValueError):
            raise ValueError(f"size {size} needs two whole numbers, [width, height]")
        if not (16 <= w <= 8192 and 16 <= h <= 8192):
            raise ValueError(f"size {w}x{h} is out of range: each side goes from 16 to 8192 pixels")
        return [w, h]
    raise ValueError(f"size {size!r} is not square, portrait, story or [width, height]")


def number_fields(doc):
    """Give every text layer a `field` (text1, text2... in layer order). A layer that already
    has one keeps it; the others take the next free number."""
    layers = doc["layers"]
    used = {l.get("field") for l in layers if l.get("field")}
    n = 1
    for l in layers:
        if l.get("type") == "text" and not l.get("field"):
            while f"text{n}" in used:
                n += 1
            l["field"] = f"text{n}"
            used.add(l["field"])


def text_fields(doc, given=None):
    """The `fields` list of a template: one entry per text field, labelled with its current text.
    Extra keys a field entry may carry (from the editor) are kept."""
    extra = {f.get("key"): f for f in (given or []) if isinstance(f, dict)}
    out, seen = [], set()
    for l in doc["layers"]:
        k = l.get("field")
        if l.get("type") != "text" or not k or k in seen:
            continue
        seen.add(k)
        entry = dict(extra.get(k) or {})
        entry["key"] = k
        entry["label"] = str(l.get("text", ""))
        out.append(entry)
    return out


def photo_fields(doc):
    """The image layers you can swap by field name (the ones that carry a `field`)."""
    seen = []
    for l in doc["layers"]:
        if l.get("type") == "image" and l.get("field") and l["field"] not in seen:
            seen.append(l["field"])
    return seen


def apply_fields(doc, fields):
    """Put new values into a template document by field key. Text layers take the value as
    their text; image layers take it as their picture (a sample name, a URL or a path). A
    field you leave out keeps what was saved. Returns the keys the document does not have."""
    fields = fields or {}
    known = set()
    for l in doc["layers"]:
        k = l.get("field")
        if not k:
            continue
        known.add(k)
        if k not in fields or fields[k] is None:
            continue
        if l.get("type") == "text":
            l["text"] = str(fields[k])
        elif l.get("type") == "image":
            l["src"] = str(fields[k]).strip()
            l.pop("path", None)
    return [k for k in fields if k not in known]


def _image_format(data, where):
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format
            im.verify()
    except Exception:
        raise ValueError(f"{where}: the picture is damaged or is not an image")
    return fmt


def _local_file(src, base_dir):
    """An existing file for `src`: as given, else relative to the template file's folder."""
    if os.path.isfile(src):
        return os.path.abspath(src)
    if base_dir and not os.path.isabs(src):
        p = os.path.join(base_dir, src)
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def _check_images(doc, base_dir, notes):
    """Make the pictures travel with the template: a photo on this computer is embedded as a
    data: URL (a very large one stays a link, with a note). data: URLs are checked to really be
    images; web addresses, site paths and sample names are left as they are."""
    for i, l in enumerate(doc["layers"], 1):
        if l.get("type") != "image":
            continue
        where = f"layer {i} (image)"
        src = l.get("src")
        from_path = False
        if not src and l.get("source", "file") == "file" and l.get("path"):
            src, from_path = l["path"], True
        if not src:
            continue  # fetched or library pictures are looked up at render time
        if not isinstance(src, str):
            raise ValueError(f"{where}: src must be text")
        s = src.strip()
        low = s.lower()
        if low.startswith("data:"):
            head, _, body = s.partition(",")
            if not head.lower().startswith("data:image/"):
                raise ValueError(f"{where}: a data: URL here must hold an image (data:image/...)")
            try:
                raw = (base64.b64decode(body) if ";base64" in head.lower()
                       else urllib.parse.unquote_to_bytes(body))
            except Exception:
                raise ValueError(f"{where}: the embedded picture is not valid base64")
            _image_format(raw, where)
            continue
        if low.startswith("blob:"):
            raise ValueError(f"{where}: a blob: address only exists inside the browser tab that "
                             "made it; embed the picture as a data: URL")
        if low.startswith(("http://", "https://")):
            continue
        local = _local_file(s, base_dir)
        if local:
            if os.path.getsize(local) > _MAX_EMBED_BYTES:
                l["src"] = local
                notes.append(f"{where}: {local} is over 15 MB, so it stays a link to that file and "
                             "the template only works on this computer")
            else:
                with open(local, "rb") as f:
                    raw = f.read()
                fmt = _image_format(raw, where)
                mime = _IMAGE_MIME.get(fmt) or mimetypes.guess_type(local)[0] or "image/png"
                l["src"] = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
            if from_path:
                l.pop("path", None)
                l.pop("source", None)
            continue
        if s.startswith("/") and not s.startswith("//"):
            continue  # a path on the studio site, as the web editor writes it
        if _SAMPLE_RE.fullmatch(s):
            if s not in SAMPLE_PHOTOS:
                notes.append(f"{where}: '{s}' is not one of the sample photos ({', '.join(SAMPLE_PHOTOS)})")
            continue
        raise ValueError(f"{where}: picture not found: {s}")


def normalize_template(data, name="", deep=True, base_dir=None, notes=None):
    """Check a template and return it in the shared file format. `data` is a whole template
    file, or a bare document ({size, layers}) to wrap. `name` renames it. With `deep`, local
    photos are embedded and embedded pictures are checked (saving and importing); reading a
    file that is already in the folder skips that."""
    notes = notes if notes is not None else []
    if not isinstance(data, dict):
        raise ValueError("a template is a JSON object: a template file, or a document {size, layers}")
    if "doc" not in data and "layers" in data:
        wrap, doc = {}, data
    else:
        wrap, doc = data, data.get("doc")
        kind = wrap.get("kind")
        if kind not in (None, TEMPLATE_KIND):
            raise ValueError(f"this file is a '{kind}', not a template ({TEMPLATE_KIND})")
        version = wrap.get("version", TEMPLATE_VERSION)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError(f"version must be a whole number, got {version!r}")
        if version > TEMPLATE_VERSION:
            raise ValueError(f"this template was made by a newer studio (format version {version}); "
                             "update this MCP (check_for_update) to open it")
    if not isinstance(doc, dict) or not isinstance(doc.get("layers"), list) or not doc["layers"]:
        raise ValueError("the template needs a document with a non-empty 'layers' list")
    doc = copy.deepcopy(doc)
    for i, l in enumerate(doc["layers"], 1):
        if not isinstance(l, dict) or not isinstance(l.get("type"), str) or not l["type"]:
            raise ValueError(f"layer {i} needs a 'type' (see list_layer_types)")
        f = l.get("field")
        if f is not None and not (isinstance(f, str) and _FIELD_RE.fullmatch(f)):
            raise ValueError(f"layer {i}: field {f!r} must be 1 to 40 letters, digits, - or _")
        if l["type"] == "text":
            t = l.get("text", "")
            if isinstance(t, (dict, list)) or isinstance(t, bool):
                raise ValueError(f"layer {i}: a text layer's text must be text")
            l["text"] = "" if t is None else str(t)
    size = _check_size(doc.get("size") or wrap.get("size") or "square")
    doc["size"] = size
    number_fields(doc)
    if deep:
        _check_images(doc, base_dir, notes)
    nm = str(name or wrap.get("name") or "").strip()
    if not nm:
        raise ValueError("the template needs a name")
    fmt = str(wrap.get("format") or ("Story" if size == "story" else "Feed post"))
    return {"kind": TEMPLATE_KIND, "version": TEMPLATE_VERSION, "name": nm[:80], "format": fmt,
            "size": size, "doc": doc, "fields": text_fields(doc, wrap.get("fields"))}


def _read_user_template(path):
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    stem = os.path.splitext(os.path.basename(path))[0]
    t = normalize_template(data, name=(data.get("name") if isinstance(data, dict) else "") or stem,
                           deep=False)
    t["slug"], t["file"] = stem, path
    return t


def user_templates():
    """Your saved templates, id -> template (id = the file name without .json). A file that
    cannot be read shows up with an `error` instead of disappearing."""
    d = templates_dir()
    out = {}
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            out[fn[:-5]] = _read_user_template(p)
        except Exception as e:
            out[fn[:-5]] = {"error": f"cannot read this template: {e}", "file": p}
    return out


def find_user_template(name):
    """Your template by id, by its name, or by the id its name makes (case does not matter).
    None when there is no such template; an error when the file is there but broken."""
    d = templates_dir()
    if not name or not os.path.isdir(d):
        return None
    want = str(name).strip().lower()
    p = os.path.join(d, template_slug(name) + ".json")
    if os.path.isfile(p):
        return _read_user_template(p)
    files = [fn for fn in sorted(os.listdir(d)) if fn.lower().endswith(".json")]
    for fn in files:
        if fn[:-5].lower() == want:
            return _read_user_template(os.path.join(d, fn))
    for fn in files:
        try:
            t = _read_user_template(os.path.join(d, fn))
        except Exception:
            continue
        if t["name"].strip().lower() == want:
            return t
    return None


def build_user(t, fields=None, size=None):
    """A render-ready document from one of your templates: the saved document with `fields`
    put in, at its saved size or at `size` (the layout is in fractions, so it re-flows)."""
    doc = copy.deepcopy(t["doc"])
    apply_fields(doc, fields)
    if size:
        doc["size"] = _check_size(size)
    return doc


def save_user_template(name, data, replace=False, base_dir=None, fields=None):
    """Check `data`, put in `fields`, and write it to the templates folder. Returns
    (id, file path, template, notes). A built-in template's name is refused, and an existing
    template of yours is only replaced with replace=True."""
    notes = []
    t = normalize_template(data, name=name, deep=True, base_dir=base_dir, notes=notes)
    if fields:
        unknown = apply_fields(t["doc"], fields)
        if unknown:
            notes.append("ignored fields this template does not have: " + ", ".join(unknown))
        _check_images(t["doc"], base_dir, notes)
        t["fields"] = text_fields(t["doc"], t["fields"])
    slug = template_slug(t["name"])
    if slug in TEMPLATES or str(name).strip() in TEMPLATES:
        raise ValueError(f"'{slug}' is the name of a built-in template; pick another name")
    d = templates_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, slug + ".json")
    if os.path.exists(path) and not replace:
        raise FileExistsError(f"you already have a template called '{slug}'; pass replace=True "
                              "to overwrite it, or pick another name")
    body = json.dumps(t, indent=2, ensure_ascii=False)
    if len(body.encode("utf-8")) > _MAX_TEMPLATE_BYTES:
        raise ValueError("this template is over 40 MB with its pictures; use smaller photos")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, path)
    return slug, path, t, notes


def delete_user_template(name):
    """Delete one of your templates and return its file path. Built-ins cannot be deleted."""
    if name in TEMPLATES:
        raise ValueError(f"'{name}' is a built-in template; built-ins cannot be deleted")
    d = templates_dir()
    path = None
    if name and os.path.isdir(d):
        # by file first, without reading it, so a damaged template can still be removed
        want = str(name).strip().lower()
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".json") and fn[:-5].lower() in (want, template_slug(name)):
                path = os.path.join(d, fn)
                break
        if not path:
            t = find_user_template(name)
            path = t and t["file"]
    if not path:
        mine = ", ".join(sorted(user_templates())) or "none yet"
        raise ValueError(f"no template of yours called '{name}' (yours: {mine})")
    os.remove(path)
    return path


# Optional: a templates_local.py next to this file can add templates of your own (it adds
# entries to TEMPLATES). It is not part of the package, so updates never overwrite it.
try:
    import templates_local  # noqa: F401
except ModuleNotFoundError as _e:
    if _e.name != "templates_local":
        raise
except Exception as _e:
    print("templates_local.py failed to load:", _e, file=sys.stderr)
