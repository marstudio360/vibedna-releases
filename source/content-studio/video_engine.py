#!/usr/bin/env python3
"""
Video engine for the content suite.

The rest of post-engine paints STILLS and animates them with a zoom. This module is the
other half: it takes EXISTING FOOTAGE and turns it into a vertical piece that survives a
feed. It is brand-aware like everything else here: swap the brand, keep the recipe.

WHY THIS IS CODE AND NOT A CHECKLIST
Each rule below came from measuring a finished piece and finding it wrong. As a checklist
it gets skipped; as code it cannot be.

  1. SEAMLESS LOOP. On Reels and Shorts replays count as watch time, so a clip that
     returns to its first frame invisibly gets watched several times before the viewer
     notices. Recipe: take D+X seconds and crossfade the TAIL onto the HEAD, so the
     output's first and last frames are the same instant of the source.

  2. MOTION MUST BE BAKED, NOT EXPRESSED. ffmpeg's `overlay` ROUNDS its position to whole
     pixels, so a slow drift of ~0.03 px/frame sits still for twenty frames and then
     jumps one pixel, and the slower the motion the worse it gets. The drift is rendered
     into a PNG sequence with PIL's AFFINE transform, which interpolates, and ffmpeg only
     pastes it at a fixed integer position with nothing left to round.

  3. THE VEIL IS COMPUTED PER SHOT, NOT SET ONCE. Text tuned against one shot fails
     contrast on the others. Moving the text per shot would break the series' look, so the
     composition stays identical and each background gets exactly the veil it needs,
     derived from its measured luminance.

  4. COMPOSE ON THE OPTICAL CENTRE, NOT THE DARKEST BAND. Chasing darkness pushes
     everything against the bottom edge, where the apps' own UI covers it. The marks sit
     at the centre of the VISIBLE area and rule 3 buys their legibility.

  5. THE SHADOW SCALES WITH THE TYPE. A fixed 12 px blur is right at 44 pt and leaves a
     70 pt letter with no bed at all.

Only PIL + ffmpeg are needed, like the rest of the suite. numpy and OpenCV are never
imported, so this ships anywhere the still engine ships.
"""

import json
import math
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from brands import get_brand

try:
    from post_engine import _load_font, _ffmpeg
except ImportError:                                    # standalone use
    def _ffmpeg():
        return os.environ.get("FFMPEG_BIN", "ffmpeg")

    def _load_font(path, size, mono=False):
        return ImageFont.truetype(path, size)


# --- the apps' own furniture ---
# Instagram and YouTube paint their interface over the clip: caption, account, audio and
# the action rail. No mark may sit under it.
SAFE_TOP, SAFE_BOTTOM = 150, 1440
CANVAS = (1080, 1920)
PAD = 78                       # breathing room inside a sprite so the drift cannot clip


def _ffprobe_bin():
    """FFPROBE_BIN, or the ffprobe next to the ffmpeg in use (only the file name is swapped,
    so a folder called ffmpeg in the path stays as it is)."""
    if os.environ.get("FFPROBE_BIN"):
        return os.environ["FFPROBE_BIN"]
    head, tail = os.path.split(_ffmpeg())
    return os.path.join(head, tail.replace("ffmpeg", "ffprobe")) if head else tail.replace("ffmpeg", "ffprobe")


def _ffprobe(path):
    out = subprocess.run(
        [_ffprobe_bin(), "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True).stdout
    d = json.loads(out or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    return {
        "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
        "fps": (float(num) / float(den or 1)) if den else 0.0,
        "duration": float(d.get("format", {}).get("duration") or 0),
        "has_audio": a is not None,
    }


# --- luminance, PIL only ---
# Contrast has to be judged on RELATIVE luminance (sRGB linearised), not on the "L"
# channel: "L" is a perceptual grey, and using it makes light text on a bright sky look
# acceptable when it measures 1.3:1 and is in fact unreadable.
_LIN = [(c / 255.0 / 12.92 if c / 255.0 <= 0.03928 else ((c / 255.0 + 0.055) / 1.055) ** 2.4)
        for c in range(256)]


def _luminance(img):
    """Relative luminance as an 8-bit image (0..255 maps to 0..1), without numpy.

    Each channel is linearised through the sRGB LUT first and only then weighted. PIL
    accepts a matrix on RGB->L but not on RGB->F, so the result is 8-bit; the quantisation
    moves a contrast ratio by well under a hundredth, which no eye and no threshold cares
    about."""
    r, g, b = img.convert("RGB").split()
    lut = [int(round(v * 255)) for v in _LIN]
    r, g, b = (ch.point(lut) for ch in (r, g, b))
    return Image.merge("RGB", (r, g, b)).convert("L", matrix=(0.2126, 0.7152, 0.0722, 0))


def _mean_where(fimg, mask):
    """Mean of an F image over a 1-bit mask. PIL's histogram is enough and stays fast."""
    stat = 0.0
    n = 0
    px, mx = fimg.load(), mask.load()
    w, h = fimg.size
    step = 2 if w * h > 400_000 else 1            # sampling: the answer moves < 0.5%
    for y in range(0, h, step):
        for x in range(0, w, step):
            if mx[x, y]:
                stat += px[x, y]
                n += 1
    return (stat / n / 255.0) if n else 0.0


def _ink_and_ring(alpha, reach=26):
    """The stroke, and the ring of background it competes against (`reach` sets how far
    the ring extends).

    Measuring the stroke against the WHOLE crop instead of this ring lets a line that is
    invisible to the eye score 8:1: that measures the landscape's dynamic range, not the
    letter against what surrounds it."""
    ink = alpha.point(lambda v: 255 if v > 210 else 0).convert("1")
    near = alpha.filter(ImageFilter.GaussianBlur(4)).point(lambda v: 255 if v > 8 else 0)
    far = alpha.filter(ImageFilter.GaussianBlur(reach)).point(lambda v: 255 if v > 8 else 0)
    ring = Image.composite(Image.new("L", alpha.size, 0), far, near).convert("1")
    return ink, ring


def contrast_ratio(frame, alpha, x0, y0):
    """Contrast of a sprite's ink against its immediate surroundings, on a real frame."""
    box = (x0, y0, x0 + alpha.size[0], y0 + alpha.size[1])
    lum = _luminance(frame.crop(box))
    ink, ring = _ink_and_ring(alpha)
    li, lf = _mean_where(lum, ink), _mean_where(lum, ring)
    hi, lo = max(li, lf), min(li, lf)
    return (hi + 0.05) / (lo + 0.05), li, lf


# --- type ---
def _tracked_mask(text, font, tracking):
    widths = [font.getlength(c) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    m = Image.new("L", (int(total) + 6, font.size * 3), 0)
    d = ImageDraw.Draw(m)
    x = 3.0
    for c, w in zip(text, widths):
        d.text((x, font.size), c, font=font, fill=255)
        x += w + tracking
    return m.crop(m.getbbox() or (0, 0, 1, 1))


def fit_size(text, font_path, tracking, avail, ceiling=200, floor=24):
    """Largest point size whose inked width fits. A fixed size leaves a title either
    touching both edges or lost in the frame."""
    for size in range(ceiling, floor - 1, -2):
        f = _load_font(font_path, size)
        if _tracked_mask(text, f, tracking).size[0] <= avail:
            return size
    return floor


def _paint_text(canvas, mask, x0, y0, color, size, shadow=0.80, halo=0.66):
    """Diffuse shadow + short halo + fill. The blur radii TRACK the point size (rule 5):
    the shadow is a LOCAL veil that gives the letter its own bed wherever it lands, which
    is what makes composing on the optical centre possible at all."""
    w, h = canvas.size
    s = Image.new("L", (w, h), 0)
    s.paste(mask, (x0, y0 + int(size * 0.18)))
    s = s.filter(ImageFilter.GaussianBlur(size * 0.42))
    canvas.paste(Image.new("RGBA", (w, h), (0, 0, 0, 255)), (0, 0),
                 s.point(lambda v: int(v * shadow)))
    g = Image.new("L", (w, h), 0)
    g.paste(mask, (x0, y0))
    g = g.filter(ImageFilter.GaussianBlur(size * 0.10))
    canvas.paste(Image.new("RGBA", (w, h), (0, 0, 0, 255)), (0, 0),
                 g.point(lambda v: int(min(255, v * 1.7) * halo)))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(Image.new("RGBA", mask.size, tuple(color) + (255,)), (x0, y0), mask)
    return Image.alpha_composite(canvas, layer)


def text_sprite(lines, font_path, size, tracking, color, leading=0.42):
    """A centred one-or-more-line sprite, plus its ink mask (needed to measure honestly)."""
    f = _load_font(font_path, size)
    masks = [_tracked_mask(t, f, tracking) for t in lines]
    gap = int(size * leading)
    w = max(m.size[0] for m in masks) + PAD * 2
    h = sum(m.size[1] for m in masks) + gap * (len(masks) - 1) + PAD * 2
    art = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ink = Image.new("L", (w, h), 0)
    y = PAD
    for m in masks:
        x = (w - m.size[0]) // 2
        art = _paint_text(art, m, x, y, color, size)
        ink.paste(m, (x, y))
        y += m.size[1] + gap
    return art, ink


def logo_sprite(logo_path, side, domain, font_path, size, color):
    """Brand mark over its own shadow, with the domain beneath it."""
    logo = Image.open(logo_path).convert("RGBA").resize((side, side), Image.LANCZOS)
    f = _load_font(font_path, size, mono=True)
    m = _tracked_mask(domain, f, 14) if domain else Image.new("L", (1, 1), 0)
    gap = 58
    w = max(side, m.size[0]) + PAD * 2
    h = side + gap + m.size[1] + PAD * 2
    art = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xl = (w - side) // 2
    s = Image.new("L", (w, h), 0)
    s.paste(logo.getchannel("A"), (xl, PAD + int(side * 0.05)))
    s = s.filter(ImageFilter.GaussianBlur(side * 0.11))
    art.paste(Image.new("RGBA", (w, h), (0, 0, 0, 255)), (0, 0), s.point(lambda v: int(v * 0.74)))
    art.alpha_composite(logo, (xl, PAD))
    ink = Image.new("L", (w, h), 0)
    ink.paste(logo.getchannel("A"), (xl, PAD))
    if domain:
        xm = (w - m.size[0]) // 2
        art = _paint_text(art, m, xm, PAD + side + gap, color, size)
        ink.paste(m, (xm, PAD + side + gap))
    return art, ink


# --- the drift ---
def _shift(img, dy, dx=0.0):
    """Sub-pixel shift on both axes. AFFINE maps output->input, hence the inverted signs."""
    return img.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy),
                         resample=Image.BILINEAR)


def _smootherstep(t):
    """Ken Perlin's curve: zero first AND second derivative at both ends. A linear fade
    starts and stops abruptly because its velocity jumps from 0 to full instantly; this one
    eases in and out of the movement itself, which is the difference between a mark that
    APPEARS and one that ARRIVES."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


def _drift_at(t, amp, period, phase, ratio=0.42):
    """A slow ELLIPTICAL drift, the only shape here that never stops.

    A purely vertical sine has zero velocity at each extreme, so the mark parks twice per
    period and reads as an animation that ended. Summing a second sine does not fix it: the
    sum still has instants where everything cancels.

    Two axes ninety degrees out of phase do fix it. Speed is
    w*sqrt(ay^2 cos^2 + ax^2 sin^2), which cannot reach zero while both axes have amplitude:
    when the vertical brakes at its extreme, the horizontal is at full speed.

    The horizontal swing is the smaller one, so it still reads as a vertical float, not a
    circle."""
    w = 2 * math.pi / period
    return amp * math.sin(w * t + phase), amp * ratio * math.cos(w * t + phase)


def _breath_at(t, period, depth=0.009):
    """A scale breath so slow it is felt rather than seen: nine parts in a thousand over
    the better part of half a minute. It is what keeps a still mark from looking pasted on
    top of moving footage."""
    return 1.0 + depth * math.sin(2 * math.pi * (t / period) + 1.3)


def bake_drift(art, out_dir, seconds, fps=30, amp=6.0, period=8.0, phase=0.0,
               rise=0.0, rise_secs=2.6, fade_in=2.4, fade_out=2.4, hold=0.0,
               breath=26.0):
    """Render the sprite's motion AND its opacity frame by frame (rule 2).

    No landing by default: the mark is ALREADY floating when it fades in and still floating
    when it fades out. Only the opacity comes and goes, never the movement; a mark that
    slides in and stops reads as "it arrived and parked".

    The opacity is baked too, not left to ffmpeg's `fade`, which ramps alpha LINEARLY and
    reads as a switch on a bright mark. A smootherstep lets the mark grow out of the image
    and sink back into it.

    `rise` (0 = off) adds an entrance that rises `rise` px and decelerates on a cubic before
    the endless drift. Give each mark a different period and phase, or they breathe in
    unison and look bolted to one bar."""
    os.makedirs(out_dir, exist_ok=True)
    n = int(seconds * fps)
    if hold <= 0:
        hold = max(0.0, seconds - fade_in - fade_out)
    for i in range(n):
        t = i / fps
        dy, dx = _drift_at(t, amp, period, phase)
        entry = rise * (1 - t / rise_secs) ** 3 if t < rise_secs else 0.0
        frame = art
        if breath:
            k = _breath_at(t, breath)
            if abs(k - 1.0) > 1e-4:
                w2, h2 = int(round(art.size[0] * k)), int(round(art.size[1] * k))
                big = art.resize((w2, h2), Image.BICUBIC)
                frame = Image.new("RGBA", art.size, (0, 0, 0, 0))
                frame.paste(big, ((art.size[0] - w2) // 2, (art.size[1] - h2) // 2))
        frame = _shift(frame, dy - entry, dx)
        if t < fade_in:
            a = _smootherstep(t / fade_in)
        elif t < fade_in + hold:
            a = 1.0
        else:
            a = _smootherstep(max(0.0, (seconds - t) / max(1e-6, fade_out)))
        if a < 0.999:
            alpha = frame.getchannel("A").point(lambda v, k=a: int(v * k))
            frame.putalpha(alpha)
        frame.save(os.path.join(out_dir, "f_%04d.png" % i))
    return n


# --- the veil ---
def veil_png(path, top=560, bottom=1020, falloff=250):
    """A full-width band of shade with a smootherstep falloff.

    FULL WIDTH and not an oval on purpose: a band reads as cloud shadow or as light
    falling away, an oval reads as a spotlight aimed at the text."""
    w, h = CANVAS
    col = Image.new("L", (1, h), 0)
    px = col.load()
    for y in range(h):
        if top <= y <= bottom:
            a = 1.0
        elif top - falloff < y < top:
            t = (y - (top - falloff)) / falloff
            a = t * t * t * (t * (t * 6 - 15) + 10)
        elif bottom < y < bottom + falloff:
            t = ((bottom + falloff) - y) / falloff
            a = t * t * t * (t * (t * 6 - 15) + 10)
        else:
            a = 0.0
        px[0, y] = int(a * 255)
    alpha = col.resize((w, h))
    Image.merge("RGBA", (Image.new("L", (w, h), 0),) * 3 + (alpha,)).save(path)
    return path


def veil_alpha(frame, alpha_mask, x0, y0, ink_reference=0.834, target=3.6, cap=0.55):
    """How much veil THIS background needs (rule 3).

    Compositing black over sRGB gives L_new = L_old * (1-a)^2.4, so the alpha that brings
    the background to the target ratio is 1 - (L_target/L_now)^(1/2.4). `ink_reference` is
    the measured luminance of the stroke over a dark bed (the harshest of the three marks),
    so the answer is conservative rather than optimistic."""
    box = (x0, y0, x0 + alpha_mask.size[0], y0 + alpha_mask.size[1])
    lum = _luminance(frame.crop(box))
    _, ring = _ink_and_ring(alpha_mask, reach=20)
    now = _mean_where(lum, ring)
    ceiling = (ink_reference + 0.05) / target - 0.05
    if now <= ceiling or now <= 0:
        return 0.0
    return round(max(0.0, min(cap, 1 - (ceiling / now) ** (1 / 2.4))), 3)


def grab_frame(src, when, crop=None, mirror=""):
    """One frame of the source, already cropped and mirrored, so the veil is measured on
    exactly what the viewer will see rather than on the raw footage."""
    tmp = tempfile.mktemp(suffix=".png")
    vf = _geometry(crop, mirror, 0, "g").rstrip(";").replace("[g]", "[v]")
    subprocess.run([_ffmpeg(), "-v", "error", "-ss", str(when), "-i", src, "-frames:v", "1",
                    "-filter_complex", vf, "-map", "[v]", "-y", tmp], check=True)
    img = Image.open(tmp).convert("RGB")
    img.load()
    os.remove(tmp)
    return img


def _geometry(crop, mirror, idx=0, tag="src", fps=30):
    """The crop-and-mirror half of the graph, shared by the measuring pass and the render
    so the veil can never be measured on a different picture than the one that ships.

    `idx` is the ffmpeg input this chain reads, because the render feeds it TWICE (see the
    note on splitting in render_ambient_vertical)."""
    w, h = CANVAS
    if mirror == "h-left":
        # Mirror the half-width strip just left of the vertical axis. Building the mirrored
        # look from the SOURCE, instead of cropping an already-mirrored film, keeps the
        # pixels pristine and avoids that film's own crossfades.
        half = w // 2
        # Crop the strip to the canvas's PROPORTIONAL height, not the full source height.
        # Cropping full ih and scaling squashes the picture and ffmpeg compensates with a
        # non-square SAR (8:9): the footage looks fine, but a round mark stamped afterwards
        # turns oval in every player that honours the flag. setsar=1 forces square pixels.
        strip_h = f"min(ih,round({half}*{2*h}/{w}/2)*2)"
        return (f"[{idx}:v]crop={half}:'{strip_h}':(iw/2-{half}):'(ih-{strip_h})/2',"
                f"split[{tag}a][{tag}b];"
                f"[{tag}b]hflip[{tag}f];[{tag}a][{tag}f]hstack=inputs=2,"
                f"scale={w}:{h}:flags=lanczos,setsar=1,fps={fps},format=yuv420p[{tag}];")
    if crop:
        cw, ch, cx, cy = crop
        return (f"[{idx}:v]crop={cw}:{ch}:{cx}:{cy},scale={w}:{h}:flags=lanczos,setsar=1,"
                f"fps={fps},format=yuv420p[{tag}];")
    return (f"[{idx}:v]crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})':(iw-ow)/2:(ih-oh)/2,"
            f"scale={w}:{h}:flags=lanczos,fps={fps},format=yuv420p[{tag}];")


# --- the piece ---
# Three moments, one job each, never two at once, with clean image between them. That gap
# stops the crowding; it is also the difference between an ad (sells in three seconds, so
# the text IS the product) and an organic piece (watched to the end, where text competes
# with the footage the viewer came for).
#
# FADES ARE LONG AND SMOOTH: 2.4 s here (never under ~1.5 s) on a smootherstep, not short
# and linear. A short linear fade reads as a switch: opacity speed jumps from zero to full
# in one frame and the eye catches those instants. A long smooth fade lets the mark grow
# out of the image and sink back into it.
#
# Each beat spans fade_in + hold + fade_out and ends BEFORE the next one starts; the last
# one ends before the piece does, or a mark half-faded on the final frame would pop in when
# the loop restarts. Three moments with 2.4 s fades do not fit in 15 s (the fades alone
# take 14.4 s), hence the 20 s default; other durations rescale (see _beats_for). Since
# the loop is invisible, viewers watch more than one pass anyway.
#
# ALL THREE RISE: one direction across the piece reads as a single current, while
# alternating made each moment feel like a restart. The drift PERIODS differ and are
# pairwise coprime (15, 17, 13 s), so the marks never breathe in unison, which would make
# them look bolted to one bar.
#
# THE PHASE IS COMPUTED, NOT CHOSEN. A sine is slow near its peaks and fast at its zero
# crossing, so a visible window that sits on a peak makes the mark crawl and look stuck.
# Centring the window on the ZERO CROSSING (see _centred_phase) runs the mark along the
# steepest stretch, and its speed never drops below ~30% of the maximum.
BEATS = [
    # key,   appears, span, amp, period, rising
    ("title",  0.8, 6.0, 20.0, 15.0, True),
    ("line",   7.4, 6.0, 18.0, 17.0, True),
    ("mark",  14.0, 5.6, 20.0, 13.0, True),
]


def _beats_for(duration):
    """The three moments, rescaled to the piece's real duration.

    Fixed seconds would silently drop marks from shorter pieces: the mark enters at 14.0 s
    and lasts 5.6 s, so on a 12 s cut it would never appear, with no error. The 20 s timings
    (0.8 / 7.4 / 14.0) are kept exactly and scale proportionally for any other duration
    (15 s gives 0.6 / 5.6 / 10.5). Drift AMPLITUDE and PERIOD are not scaled: they are the
    rhythm of the motion and do not depend on how long the piece is."""
    k = float(duration) / DURATION
    return [(key, appears * k, span * k, amp, period, rising)
            for key, appears, span, amp, period, rising in BEATS]


def _centred_phase(span, period, rising=True):
    """The phase that puts the zero crossing in the middle of the visible span, moving in
    the requested direction.

    Mind the sign: AFFINE maps output to input, so a POSITIVE `dy` moves the image DOWN.
    To rise, `dy` must go from positive to negative, i.e. cross zero with a NEGATIVE slope.
    That is phase = pi - half_sweep; without the pi it does exactly the opposite."""
    half_sweep = math.pi * span / period
    return (math.pi - half_sweep) if rising else -half_sweep


FADE = 2.4
DURATION = 20.0


def render_ambient_vertical(source, out_path, title="", line="", brand="default", logo="",
                            domain=None, bed="", bed_start=0.0, start=0.0, duration=DURATION,
                            crossfade=2.0, mirror="", crop=None, fps=30, crf=18,
                            title_size=0, line_size=0, logo_side=310, veil=None,
                            loudness=-16.0, workdir=None):
    """Footage in, feed-ready vertical out. Returns a report of everything it measured.

    fps=30 by default: Instagram rejects some vertical reels above 30 fps (the upload ends
    in ProcessingFailedError), so a feed vertical ships at 30. Pass fps=60 only for a
    destination known to accept it.

    veil=None measures each mark's own background and derives the shade itself; pass a
    float to force it. mirror="h-left" reproduces a mirrored film's look from the pristine
    source, without inheriting that film's crossfades."""
    _beats = _beats_for(duration)
    b = get_brand(brand)
    pal = b["palette"]
    fonts = b.get("fonts", {})
    if domain is None:
        domain = (b.get("cta") or "").upper()
    tmp = workdir or tempfile.mkdtemp(prefix="vert_")
    os.makedirs(tmp, exist_ok=True)
    report = {"source": source, "brand": brand, "out": out_path}

    info = _ffprobe(source)
    report["source_info"] = info
    need = start + duration + crossfade
    if info["duration"] and info["duration"] < need - 0.05:
        raise ValueError("source is %.1fs; the window needs %.1fs (start=%.1f)"
                         % (info["duration"], need, start))

    # --- the marks ---
    avail = int(CANVAS[0] * 0.83)          # 900 px of 1080: 90 a side
    sprites = {}
    if title:
        # The title accepts a LIST, like the line, so a long phrase can span two or three
        # lines and keep the title's size and colour. Sent through `line` instead, it would
        # be capped at 72 pt and painted in the body colour.
        title_parts = title if isinstance(title, list) else [title]
        size = title_size or fit_size(max(title_parts, key=len), fonts.get("display"), 14, avail, ceiling=96)
        art, ink = text_sprite(title_parts, fonts.get("display"), size, 14, pal["text"])
        sprites["title"] = (art, ink, size)
    if line:
        parts = line if isinstance(line, list) else [line]
        size = line_size or min(fit_size(max(parts, key=len), fonts.get("display"), 5,
                                         avail, ceiling=72), 72)
        art, ink = text_sprite(parts, fonts.get("display"), size, 5, pal["body"])
        sprites["line"] = (art, ink, size)
    if logo and os.path.exists(logo):
        art, ink = logo_sprite(logo, logo_side, domain, fonts.get("mono"), 46, pal["text"])
        sprites["mark"] = (art, ink, 46)
    if not sprites:
        raise ValueError("nothing to show: pass a title, a line or a logo")

    # --- where they sit ---
    # The centre of the VISIBLE area, not of the file (rule 4). What gets centred is the
    # INK, not the sprite (which carries padding) and not the block with its shadow.
    centre = (SAFE_TOP + SAFE_BOTTOM) // 2
    place = {}
    for k, (art, ink, _sz) in sprites.items():
        bb = ink.getbbox() or (0, 0, art.size[0], art.size[1])
        place[k] = {"y": centre - (bb[1] + bb[3]) // 2,
                    "x": (CANVAS[0] - art.size[0]) // 2,
                    "ink_w": bb[2] - bb[0], "ink_h": bb[3] - bb[1],
                    "slack": avail - (bb[2] - bb[0])}
    report["placement"] = place

    # --- how much veil ---
    # Measured on the WORST of the three moments: deriving it from just one lets the
    # others fall under the 3:1 bar.
    if veil is None:
        worst = 0.0
        for key, appears, span, _a, _p, _r in _beats:
            if key not in sprites:
                continue
            frame = grab_frame(source, start + appears + span / 2, crop, mirror)
            worst = max(worst, veil_alpha(frame, sprites[key][1],
                                          place[key]["x"], place[key]["y"]))
        veil = worst
    report["veil"] = veil
    veil_file = os.path.join(tmp, "veil.png")
    veil_png(veil_file)

    # --- bake the drift ---
    seqs = {}
    for key, appears, span, amp, period, rising in _beats:
        if key not in sprites:
            continue
        d = os.path.join(tmp, key)
        bake_drift(sprites[key][0], d, span, fps=fps, amp=amp, period=period,
                   phase=_centred_phase(span, period, rising), fade_in=FADE, fade_out=FADE)
        seqs[key] = d

    # --- the graph ---
    # TWO READS of the source, not a split. Splitting the video into body and tail forces
    # ffmpeg to BUFFER one whole branch while the other waits: 15 s of 1080x1920 at 60 fps
    # is ~7 GB and the filter dies with "Cannot allocate memory". Opening the same file
    # twice with different -ss costs nothing. The bed audio is read twice below for the
    # same kind of reason.
    args = [_ffmpeg(), "-y", "-loglevel", "error",
            "-ss", str(start), "-t", str(duration), "-i", source,
            "-ss", str(start + duration), "-t", str(crossfade), "-i", source]
    idx = 2
    use_bed = bool(bed) and os.path.exists(bed)
    if use_bed:
        # TWO separate reads of the bed rather than one asplit: acrossfade drains its first
        # input completely before touching the second, while the branches of a split must
        # advance together, so the split version emits NOTHING at all.
        args += ["-ss", str(bed_start), "-t", str(duration), "-i", bed,
                 "-ss", str(bed_start + duration), "-t", str(crossfade), "-i", bed]
        i_body, i_tail = idx, idx + 1
        idx += 2
    live = [k for k, *_r in _beats if k in seqs]
    seq_idx = {}
    for key in live:
        args += ["-framerate", str(fps), "-start_number", "0",
                 "-i", os.path.join(seqs[key], "f_%04d.png")]
        seq_idx[key] = idx
        idx += 1
    args += ["-loop", "1", "-framerate", str(fps), "-t", str(duration), "-i", veil_file]
    i_veil = idx

    g = [_geometry(crop, mirror, 0, "body", fps),
         _geometry(crop, mirror, 1, "tail", fps),
         # Tail over head: the output starts on the same source instant where it ends,
         # so the loop cut lands on identical material.
         "[tail][body]xfade=transition=fade:duration=%s:offset=0[loop];" % crossfade]
    if use_bed:
        g.append("[%d:a][%d:a]acrossfade=d=%s:c1=tri:c2=tri,"
                 "loudnorm=I=%s:TP=-1.5:LRA=11[a];" % (i_tail, i_body, crossfade, loudness))
    if veil > 0:
        g.append("[%d:v]format=rgba,colorchannelmixer=aa=%s,split=%d%s;"
                 % (i_veil, veil, len(live), "".join("[q%d]" % i for i in range(len(live)))))
    beats_live = [bt for bt in _beats if bt[0] in seqs]
    for n, (key, appears, span, _a, _p, _r) in enumerate(beats_live):
        if veil > 0:
            g.append("[q%d]fade=t=in:st=%s:d=%s:alpha=1,"
                     "fade=t=out:st=%s:d=%s:alpha=1[ve%d];"
                     % (n, appears, FADE, max(0.0, appears + span - FADE), FADE, n))
        # No `fade` on the mark: its opacity is already baked on a smooth curve. Chaining
        # ffmpeg's linear fade on top would bring back the hard edge.
        g.append("[%d:v]format=rgba,setpts=PTS+%s/TB[m%d];" % (seq_idx[key], appears, n))
    prev = "loop"
    for n, key in enumerate(live):
        if veil > 0:
            g.append("[%s][ve%d]overlay=0:0:format=auto[bv%d];" % (prev, n, n))
            prev = "bv%d" % n
        g.append("[%s][m%d]overlay=x=%d:y=%d:eof_action=pass:format=auto[bm%d];"
                 % (prev, n, place[key]["x"], place[key]["y"], n))
        prev = "bm%d" % n
    g.append("[%s]format=yuv420p[v]" % prev)

    args += ["-filter_complex", "".join(g), "-map", "[v]"]
    if use_bed:
        args += ["-map", "[a]"]
    elif info["has_audio"]:
        args += ["-map", "0:a?"]
    args += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-profile:v", "high",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-movflags", "+faststart", "-r", str(fps), "-t", str(duration), out_path]
    subprocess.run(args, check=True)

    report["result"] = _ffprobe(out_path)
    report["marks"] = verify_marks(out_path, sprites, place, seqs, fps, _beats)
    report["loop_seam"] = loop_seam(out_path)
    if not workdir:
        shutil.rmtree(tmp, ignore_errors=True)
    return report


# --- proof ---
def _frame_at(path, index):
    tmp = tempfile.mktemp(suffix=".png")
    subprocess.run([_ffmpeg(), "-v", "error", "-i", path,
                    "-vf", "select=eq(n\\," + str(index) + ")", "-vsync", "0",
                    "-frames:v", "1", "-y", tmp], check=True)
    img = Image.open(tmp).convert("RGB")
    img.load()
    os.remove(tmp)
    return img


def verify_marks(path, sprites, place, seqs, fps=30, beats=None):
    """Contrast of every mark against its immediate ring, on the FINISHED file.

    3:1 is the bar for large type. Measuring on a crop's percentiles instead of this ring
    measures the landscape's dynamic range, not the letter against what surrounds it, and
    can score 8:1 on a line that is invisible to the eye."""
    out = {}
    # Timings arrive as a parameter because they depend on the piece's duration; the
    # rescaled list lives in the caller, not in this scope.
    for key, appears, span, _a, _p, _r in (beats or BEATS):
        if key not in sprites:
            continue
        when = appears + span / 2                 # middle of the beat: the mark is fully opaque
        frame = _frame_at(path, int(when * fps))
        p = os.path.join(seqs[key], "f_%04d.png" % int(round((when - appears) * fps)))
        alpha = (Image.open(p).convert("RGBA").getchannel("A")
                 if os.path.exists(p) else sprites[key][1])
        r, li, lf = contrast_ratio(frame, alpha, place[key]["x"], place[key]["y"])
        out[key] = {"ratio": round(r, 2), "ink": round(li, 3), "backdrop": round(lf, 3),
                    "ok": r >= 3.0}
    return out


def loop_seam(path):
    """How visible the loop's cut is, against the only honest reference: the codec's own
    noise. Comparing it to the frame-to-frame change instead makes a perfect loop look
    five times too big, because two independently encoded frames differ by ~1.5 on their
    own even when they show the very same instant."""
    from PIL import ImageChops, ImageStat
    info = _ffprobe(path)
    n = int(info["duration"] * (info["fps"] or 60))

    def diff(a, b):
        return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]

    seam = diff(_frame_at(path, n - 1), _frame_at(path, 0))
    step = diff(_frame_at(path, n // 2), _frame_at(path, n // 2 + 1))
    # THE THRESHOLD ADAPTS TO THE MATERIAL. A fixed limit tuned on slow footage (0.4 change
    # between frames) flags fast footage such as breaking waves, where consecutive frames
    # already differ by 11. The loop cut only has to look like ANY other frame-to-frame cut,
    # plus the noise of two independent encodes.
    floor = 1.55
    budget = step + 2 * floor
    return {"seam": round(seam, 2), "frame_to_frame": round(step, 2),
            "codec_noise_floor": floor, "budget": round(budget, 2),
            "invisible": seam <= budget}


def distinctness(paths, at=7.0):
    """Are these pieces actually different scenes?

    IN COLOUR, never in grey. A misty meadow and a lavender field correlate at 0.84 in
    grey because they share the structure - bright sky above, texture below - and grey
    discards the hue, which is the only thing that separates them. Real duplicates score
    0.91 and up even in colour."""
    sigs = []
    for p in paths:
        # the clip's own frame rate: a fixed 60 reached past the end of a short 30 fps clip
        img = _frame_at(p, int(at * (_ffprobe(p)["fps"] or 30))).resize((96, 171)).convert("HSV")
        h = img.histogram()
        total = sum(h) or 1
        sigs.append([v / total for v in h])
    worst, pair = 0.0, None
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            a, b = sigs[i], sigs[j]
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
            den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
            r = num / den if den else 0.0
            if r > worst:
                worst, pair = r, (i, j)
    return {"worst_pair": pair, "worst_correlation": round(worst, 3),
            "all_distinct": worst <= 0.80,
            "note": "hue+saturation; grey gives false duplicates"}


# --- thumbnail ---
def render_film_thumbnail(frame_path, title, out_path, brand="default", eyebrow=None,
                          width=1280, height=720, saturation=1.22, contrast=1.10):
    """A YouTube thumbnail in a calm, cinematic idiom: full-bleed image, big centred title,
    open tracking. No arrows, no red circles. The image is the protagonist.

    Two things are measured rather than chosen: the POINT SIZE is fitted to the available
    width (a fixed size can run a title into both edges), and the TITLE'S BAND is the
    darkest strip of the upper third (white over a bright sky measures 1.3:1)."""
    b = get_brand(brand)
    pal, fonts = b["palette"], b.get("fonts", {})
    if eyebrow is None:
        eyebrow = b.get("eyebrow", "")
    avail = int(width * 0.80)

    base = Image.open(frame_path).convert("RGB").resize((width, height), Image.LANCZOS)
    grey = base.convert("L").convert("RGB")
    base = Image.blend(grey, base, saturation)
    base = Image.eval(base, lambda v: max(0, min(255, int((v - 128) * contrast + 128 + 4))))

    size = fit_size(title, fonts.get("display"), 12, avail, ceiling=190)
    block = size + 10
    col = base.convert("L").resize((1, height))
    px = col.load()
    best_y, best = 150, 1e9
    for y in range(70, 340, 10):
        v = sum(px[0, k] for k in range(y, min(height, y + block))) / block
        if v < best:
            best, best_y = v, y

    canvas = base.convert("RGBA")
    f = _load_font(fonts.get("display"), size)
    m = _tracked_mask(title, f, 12)
    x0 = (width - m.size[0]) // 2
    canvas = _paint_text(canvas, m, x0, best_y, pal["text"], size, shadow=0.58, halo=0.52)
    if eyebrow:
        e_size = max(22, size // 4)
        fe = _load_font(fonts.get("mono"), e_size, mono=True)
        me = _tracked_mask(eyebrow, fe, 18)
        canvas = _paint_text(canvas, me, (width - me.size[0]) // 2,
                             best_y + m.size[1] + max(30, size // 3),
                             pal["muted"], e_size, shadow=0.5, halo=0.44)
    final = canvas.convert("RGB")
    final.save(out_path, quality=94, subsampling=0)

    full = Image.new("L", (width, height), 0)
    full.paste(m, (x0, best_y))
    r, li, lf = contrast_ratio(final, full, 0, 0)
    return {"out": out_path, "size_pt": size, "ink_w": m.size[0], "avail": avail,
            "band_y": best_y, "band_luma": round(best, 1),
            "contrast": round(r, 2), "ok": r >= 3.0}
