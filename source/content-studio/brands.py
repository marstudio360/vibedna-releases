#!/usr/bin/env python3
"""
Brand packs.

A BRAND is the fixed identity (palette by role, fonts, background recipe, eyebrow +
CTA strings, particle color). Templates reference brand ROLES (accent, text, body,
muted, glow...) not raw colors, so the SAME template renders in any brand's look.
Swap the brand, keep the template = the whole point.

Your brands live in `~/.content-studio/brands/<name>.json`, one file each, and load on
import. This module ships neutral packs only: a `default` so a fresh install renders
something before you have configured anything, and four style packs (editorial, bold,
warm, mono) that the template library opens in. Fonts set to None fall back to a system
face; point them at your own .ttf (by file name or path) once you have the files.
"""

# Font lists in the style packs are written the way the web editor writes them (a CSS
# font-family list): the first family installed on this machine wins, and the generic
# family at the end (serif, sans-serif) always resolves to a common system face.
SANS = "'Helvetica Neue', 'Segoe UI', Arial, sans-serif"
SERIF = "Georgia, 'Times New Roman', serif"

#: Neutral packs only. Your own brands are config, not code: they live outside the product
#: in ~/.content-studio/brands/<name>.json and load on import (a file with the same name as
#: a pack below replaces it).
BRANDS = {
    "default": {
        "label": "Default",
        # bg_top/bg_bottom are what the background gradient actually reads. `bg` alone is not
        # enough: bg_layers() and the templates ask for both ends of the gradient by name, and
        # a fresh install with no brands of its own lands here on the very first render.
        "palette": {"bg": [14, 16, 20], "bg_top": [14, 16, 20], "bg_bottom": [8, 9, 12],
                    "accent": [120, 200, 190], "text": [242, 246, 247],
                    "body": [200, 210, 214], "muted": [140, 152, 158], "glow": [120, 200, 190],
                    "particles": [120, 200, 190]},
        "fonts": {"display": None, "body": None, "mono": None, "poster": None},
        "glow_strength": 0.5,
        "eyebrow": "", "cta": "", "handle": "",
    },
    # Style packs: the same template reads as a magazine page, a poster, a shop or a gallery
    # wall. Extra roles: `surface` is a card on the background, `on_accent` is text sitting on
    # the accent colour. `fonts.scale` evens out how wide a display face runs, so a heavy sans
    # and a serif fill the same box.
    "editorial": {
        "label": "Editorial",
        "palette": {"bg_top": [243, 239, 231], "bg_bottom": [237, 232, 222], "glow": [243, 239, 231],
                    "text": [26, 25, 23], "body": [64, 61, 56], "accent": [168, 52, 40],
                    "muted": [128, 121, 110], "particles": [176, 166, 150],
                    "surface": [252, 250, 245], "on_accent": [250, 246, 238]},
        "fonts": {"display": SERIF, "body": SANS, "mono": None, "poster": None},
        "glow_strength": 0,
        "eyebrow": "", "cta": "yourbrand.com", "handle": "@yourbrand",
    },
    "bold": {
        "label": "Bold",
        "palette": {"bg_top": [38, 54, 218], "bg_bottom": [31, 45, 192], "glow": [96, 116, 255],
                    "text": [255, 255, 255], "body": [226, 231, 255], "accent": [214, 255, 72],
                    "muted": [178, 189, 252], "particles": [214, 255, 72],
                    "surface": [255, 255, 255], "on_accent": [18, 22, 44]},
        "fonts": {"display": "'Arial Black', 'Segoe UI Black', 'Helvetica Neue', Arial, sans-serif",
                  "body": SANS, "mono": None, "poster": None, "scale": 0.84},
        "glow_strength": 0.25,
        "eyebrow": "", "cta": "yourbrand.com", "handle": "@yourbrand",
    },
    "warm": {
        "label": "Warm",
        "palette": {"bg_top": [241, 229, 213], "bg_bottom": [233, 219, 199], "glow": [241, 229, 213],
                    "text": [62, 42, 31], "body": [100, 76, 60], "accent": [186, 90, 52],
                    "muted": [150, 125, 106], "particles": [188, 150, 122],
                    "surface": [250, 243, 233], "on_accent": [255, 247, 238]},
        "fonts": {"display": "'Palatino Linotype', Palatino, 'Book Antiqua', Georgia, serif",
                  "body": SANS, "mono": None, "poster": None},
        "glow_strength": 0,
        "eyebrow": "", "cta": "yourbrand.com", "handle": "@yourbrand",
    },
    "mono": {
        "label": "Mono",
        "palette": {"bg_top": [245, 245, 243], "bg_bottom": [239, 239, 237], "glow": [245, 245, 243],
                    "text": [14, 14, 14], "body": [54, 54, 54], "accent": [14, 14, 14],
                    "muted": [122, 122, 122], "particles": [150, 150, 150],
                    "surface": [255, 255, 255], "on_accent": [245, 245, 243]},
        "fonts": {"display": SANS, "body": SANS, "mono": None, "poster": None, "scale": 0.94},
        "glow_strength": 0,
        "eyebrow": "", "cta": "yourbrand.com", "handle": "@yourbrand",
    },
}


def studio_home():
    """The folder that holds your own brands and templates: CONTENT_STUDIO_HOME when it is
    set, else ~/.content-studio. It sits outside the product, so an update never touches it."""
    import os
    return os.environ.get("CONTENT_STUDIO_HOME") or os.path.join(os.path.expanduser("~"), ".content-studio")


def _load_operator_brands():
    """Read the operator's own brands from ~/.content-studio/brands/*.json.

    Config, not code: a brand is the user's identity and has no business living in a program
    they bought. Each file is one brand, named by its filename. Absent directory = just the
    neutral packs, which is the correct first run for someone who has not set theirs up.
    """
    import json, os, glob
    d = os.path.join(studio_home(), "brands")
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                BRANDS[os.path.splitext(os.path.basename(f))[0]] = json.load(fh)
        except Exception:
            continue


_load_operator_brands()


def find_brand(name):
    """The installed brand key matching `name`, ignoring case (BISO.json answers to "biso"),
    or None when no such pack is installed. Empty name = "default"."""
    want = (name or "default").strip().lower()
    for k in BRANDS:
        if k.lower() == want:
            return k
    return None


def missing_brand_message(name):
    """One line saying a requested brand pack is not installed, or "" when it is."""
    if find_brand(name):
        return ""
    import os
    folder = os.path.join(studio_home(), "brands")
    return (f"brand pack '{name}' not found in {folder} (installed: "
            f"{', '.join(sorted(BRANDS))})")


def get_brand(name):
    """Fall back to the neutral default, never to a brand that may not be installed.
    The operator's brands live outside the product, so any name here can be missing:
    callers that take a brand from the user check missing_brand_message() first, so the
    fallback is never silent."""
    return BRANDS.get(find_brand(name) or "default") or BRANDS["default"]


def list_brands():
    """Name -> label. A brand file the operator wrote may carry no label, and that is fine:
    the name is the label then. Requiring the field took the whole tool down."""
    return {k: (v.get("label") or k) for k, v in BRANDS.items()}


def bg_layers(brand_name, glow=True, particles=True):
    """The brand's signature background as compositor layers: a vertical gradient, an
    off-center radial glow, and a procedural particle field. Prepend these to a template."""
    b = get_brand(brand_name)
    p = b["palette"]
    layers = [
        {"type": "gradient", "kind": "linear", "angle": 90,
         "stops": [[0, p["bg_top"]], [1, p.get("bg_bottom", p["bg_top"])]]},
    ]
    if glow:
        glow_color = p.get("glow", p["bg_top"])
        layers.append({"type": "gradient", "kind": "radial", "center": [0.5, 0.42], "radius": 0.72,
                       "stops": [[0, [*glow_color, int(255 * b.get("glow_strength", 0.6))]],
                                 [1, [*glow_color, 0]]], "blend": "screen"})
    if particles:
        layers.append({"type": "particles", "count": 200, "color": p.get("particles", p["text"]),
                       "seed": find_brand(brand_name) or brand_name})
    return layers
