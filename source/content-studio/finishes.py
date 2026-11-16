#!/usr/bin/env python3
"""
Finishes: named LOOKS built out of the adjustment layers the engine already has.

A finish is not a new effect. It is a STACK: the difference between a piece that looks
home-made and one that looks paid-for is almost never one filter, it is three or four mild
ones layered in the right order, and knowing that order is the part nobody wants to redo per
piece. `apply(name, duration)` returns the layers to put ON TOP of a document.

Two rules the stacks follow:

  1. MILD AND STACKED beats one strong filter. A single heavy grain reads as a broken file;
     grain at 0.06 under a soft vignette under a slight grade reads as film.
  2. A finish for a VIDEO has to MOVE. A constant chromatic on a still frame is a look; on
     twenty seconds of footage it becomes wallpaper the eye stops seeing. The glitch stack
     pulses: short, strong, far apart, so it lands as an event instead of a texture.

Anything with time is expressed with `at`/`dur`/`fade`, the same fields a layer already
understands, so preview and export stay the same function.
"""


#
# EACH EFFECT USES THE FIELD NAME ITS RENDERER READS, NOT A GENERIC ONE.
#
#   chromatic -> `shift` in pixels       (NOT `amount`)
#   posterize -> `bits`                  (NOT `levels`)
#   scanlines -> `gap` + `opacity`       (NOT `amount`)
#   bloom     -> `threshold`             (NOT `amount`)
#   grain / tint / vignette -> `amount`
#
# A wrong field name raises no error: the layer draws with its default value, or not at all,
# and the finish "applies" without changing anything on screen. `amount` is also sent as a
# harmless alias.


def _pulses(duration, every=3.4, length=0.16, shift=11, start=0.9):
    """The glitch hits. Short, strong and spaced out so they read as an event, not as a
    filter; constant hits would turn into background noise."""
    layers, t = [], start
    while t < duration - length:
        layers.append({"type": "chromatic", "shift": shift, "amount": shift / 32.0,
                       "at": round(t, 2), "dur": length, "fade": [0.02, 0.06]})
        layers.append({"type": "posterize", "bits": 3, "levels": 8,
                       "at": round(t, 2), "dur": length * 0.7, "fade": [0.02, 0.05]})
        t += every
    return layers


def glitch(duration):
    """Bold, digital, broken on purpose. The base is mild and constant; the hits are events."""
    base = [
        {"type": "chromatic", "shift": 2, "amount": 0.06, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "scanlines", "gap": 4, "opacity": 0.10, "amount": 0.10, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "grain", "amount": 0.05, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "vignette", "amount": 0.34, "at": 0, "dur": duration, "fade": [1.2, 1.0]},
    ]
    return base + _pulses(duration)


def vhs(duration):
    """Worn tape: heavy scanlines, washed colour, dirty grain and closed edges."""
    return [
        {"type": "grade", "brightness": 0.94, "saturation": 0.82, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "chromatic", "shift": 4, "amount": 0.13, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "scanlines", "gap": 3, "opacity": 0.26, "amount": 0.26, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "grain", "amount": 0.13, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "tint", "color": [120, 90, 160], "amount": 0.10, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "vignette", "amount": 0.52, "at": 0, "dur": duration, "fade": [1.2, 1.0]},
    ] + _pulses(duration, every=5.0, length=0.10, shift=7)


def neon(duration):
    """Bleeding light. Bloom does the work; the contrast keeps it from going milky."""
    return [
        {"type": "grade", "brightness": 1.04, "saturation": 1.22, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "bloom", "threshold": 0.62, "strength": 0.5, "amount": 0.42, "at": 0, "dur": duration, "fade": [1.4, 1.0]},
        {"type": "chromatic", "shift": 3, "amount": 0.09, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "tint", "color": [40, 200, 210], "amount": 0.08, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "vignette", "amount": 0.44, "at": 0, "dur": duration, "fade": [1.2, 1.0]},
    ]


def elegant(duration):
    """The one you do not notice. For when the image is already good and an effect can only hurt it."""
    return [
        {"type": "grade", "brightness": 0.98, "saturation": 0.96, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "grain", "amount": 0.04, "at": 0, "dur": duration, "fade": [1.0, 1.0]},
        {"type": "vignette", "amount": 0.30, "at": 0, "dur": duration, "fade": [1.4, 1.2]},
    ]


FINISHES = {"glitch": glitch, "vhs": vhs, "neon": neon, "elegant": elegant}

DESCRIPTIONS = {
    "glitch": "Digital and broken on purpose: mild base, hard hits every few seconds.",
    "vhs": "Worn tape: heavy scanlines, washed colour, dirty grain, closed edges.",
    "neon": "Bleeding light: bloom carries it, contrast keeps it from going milky.",
    "elegant": "The one you do not notice. For art that is already good.",
}


def apply(name, duration=0):
    """The finish's layers. With no duration they come back static, which is right for a still:
    timed layers inside a piece without time would never be seen."""
    fn = FINISHES.get((name or "").lower())
    if not fn:
        raise ValueError("unknown finish %r; use one of %s" % (name, list(FINISHES)))
    layers = fn(float(duration or 0))
    if not duration:
        layers = [{k: v for k, v in c.items() if k not in ("at", "dur", "fade")} for c in layers]
        # without time, the glitch hits would all stack on the same frame: keep one per type
        seen, unique = set(), []
        for c in layers:
            if c["type"] in seen:
                continue
            seen.add(c["type"])
            unique.append(c)
        layers = unique
    return layers


def describe():
    return DESCRIPTIONS
