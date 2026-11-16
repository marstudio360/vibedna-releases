#!/usr/bin/env python3
"""
Vibe Game Assets MCP: engine-agnostic AI asset generation for game dev.

Produces files on disk that any game engine (or an engine MCP) can import.

Provider-abstracted: image / video / audio generation behind a registry so
adding a new model = one config entry. Current providers:

  IMAGE:  flux (fal.ai, primary)  ·  imagen (Gemini, fallback)
  VIDEO:  veo3 (fal.ai)  ·  kling (fal.ai)  ·  luma (fal.ai)
  AUDIO:  elevenlabs-sfx (fal.ai)

Tools (10, all FREE; cost is API metering on the provider side):
  list_providers          -- what's wired and what API key each needs
  generate_image          -- text -> PNG (writes to a target directory)
  generate_sprite_sheet   -- N consistent frames for AnimatedSprite2D / SpriteFrames
  generate_tileset        -- grid of tile variations for TileMap
  generate_pixel_art      -- low-res, palette-locked, stylized for retro look
  generate_ui_element     -- buttons, icons, frames with transparency
  generate_video          -- text/image -> short MP4 (intros, transitions, cutscenes)
  generate_audio_sfx      -- text -> short SFX clip (collect, hit, jump)
  remove_background       -- alpha-cut existing image for sprite cleanup
  describe_image          -- vision -> text (so engine MCPs can prompt off an existing asset)

Path-agnostic: every tool accepts any absolute output path.
HTTP transport via uvicorn direct.
"""

import base64
import json
import os
import re
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("vibe-game-assets")

_HERE = Path(__file__).parent
_CACHE_DIR = _HERE / "cache"
_CACHE_DIR.mkdir(exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_path(p: str) -> Path | None:
    if not p:
        return None
    path = Path(p)
    if not path.is_absolute():
        return None
    return path


def _ok(data: dict) -> str:
    return json.dumps({"ok": True, **data}, indent=2, ensure_ascii=False)


def _err(msg: str, **extra) -> str:
    return json.dumps({"ok": False, "error": msg, **extra}, indent=2, ensure_ascii=False)


def _key(name: str) -> str | None:
    return os.environ.get(name) or None


def _cache_key(prompt: str, **kwargs) -> str:
    """Stable hash for caching: same prompt + params = same output file."""
    import hashlib
    blob = json.dumps({"prompt": prompt, **kwargs}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _post_json(url: str, headers: dict, body: dict, timeout: int = 120) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _get_json(url: str, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _download_to(url: str, dest: Path, timeout: int = 120) -> int:
    """Download a URL to dest. Returns bytes written."""
    req = urllib.request.Request(url, headers={"User-Agent": "vibe-game-assets/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = resp.read()
        dest.write_bytes(data)
        return len(data)


# ── Provider registry ────────────────────────────────────────────────────────

PROVIDERS = {
    # IMAGE
    "flux-pro": {
        "kind": "image", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/flux-pro/v1.1-ultra", "default": True,
    },
    "flux-schnell": {
        "kind": "image", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/flux/schnell", "default": False,
        "note": "fastest, ~1s, good for iteration",
    },
    "flux-dev": {
        "kind": "image", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/flux/dev", "default": False,
    },
    "imagen-4": {
        "kind": "image", "via": "gemini", "env": "GEMINI_API_KEY",
        "endpoint": "imagen-4.0-generate-001", "default": False,
        "note": "Google Imagen: good for photoreal, weaker for pixel art",
    },
    "recraft-v3": {
        "kind": "image", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/recraft-v3", "default": False,
        "note": "strongest for vector / clean illustration / UI icons",
    },
    # VIDEO
    "veo-3": {
        "kind": "video", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/veo3", "default": True,
        "note": "Google Veo 3: best quality, slowest",
    },
    "kling-2-5": {
        "kind": "video", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/kling-video/v2.5-turbo/pro", "default": False,
    },
    "luma-ray2": {
        "kind": "video", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/luma-dream-machine/ray-2", "default": False,
    },
    # AUDIO
    "elevenlabs-sfx": {
        "kind": "audio", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/elevenlabs/sound-effects", "default": True,
    },
    # UTILITY
    "rembg": {
        "kind": "bgremove", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/imageutils/rembg", "default": True,
    },
    # IMAGE EDITING (Flux Kontext: character/pose preservation via natural language edits)
    "kontext-pro": {
        "kind": "edit", "via": "fal.ai", "env": "FAL_KEY",
        "endpoint": "fal-ai/flux-pro/kontext", "default": True,
        "note": "Flux Kontext: edit existing image via prompt (rotate, repose, modify) while preserving character identity. ~$0.04/edit.",
    },
}


def _pick_provider(kind: str, preferred: str | None) -> tuple[str, dict] | None:
    if preferred and preferred in PROVIDERS and PROVIDERS[preferred]["kind"] == kind:
        return preferred, PROVIDERS[preferred]
    for name, cfg in PROVIDERS.items():
        if cfg["kind"] == kind and cfg.get("default"):
            return name, cfg
    return None


# ── Provider implementations ─────────────────────────────────────────────────

def _fal_run(endpoint: str, payload: dict, poll_seconds: int = 180) -> dict:
    """Submit a job to fal.ai's queue API and wait for the result.

    fal.ai pattern:
      POST https://queue.fal.run/{endpoint}        -> {request_id, status_url, response_url}
      GET  {status_url}                            -> {status: IN_QUEUE|IN_PROGRESS|COMPLETED}
      GET  {response_url}                          -> actual result
    """
    key = _key("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY not set. Add your fal.ai key as FAL_KEY in the env block of this MCP, then restart it.")
    headers = {"Authorization": f"Key {key}"}
    submit = _post_json(f"https://queue.fal.run/{endpoint}", headers, payload)
    status_url = submit.get("status_url")
    response_url = submit.get("response_url")
    if not response_url:
        # Some endpoints return the result inline.
        return submit
    deadline = time.time() + poll_seconds
    while time.time() < deadline:
        st = _get_json(status_url, headers)
        if st.get("status") == "COMPLETED":
            return _get_json(response_url, headers)
        if st.get("status") in {"FAILED", "ERROR"}:
            raise RuntimeError(f"fal.ai job failed: {st}")
        time.sleep(2)
    raise TimeoutError(f"fal.ai job {endpoint} did not complete within {poll_seconds}s")


def _gemini_imagen(prompt: str, aspect: str = "1:1", count: int = 1) -> list[bytes]:
    """Call Gemini Imagen. Returns list of PNG bytes."""
    key = _key("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={key}"
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": count, "aspectRatio": aspect},
    }
    out = _post_json(url, {}, body, timeout=180)
    pngs: list[bytes] = []
    for pred in out.get("predictions", []):
        b64 = pred.get("bytesBase64Encoded")
        if b64:
            pngs.append(base64.b64decode(b64))
    if not pngs:
        raise RuntimeError(f"Imagen returned no images: {out}")
    return pngs


def _provider_generate_image(provider_name: str, cfg: dict, prompt: str,
                              out_path: Path, width: int, height: int,
                              negative_prompt: str = "") -> dict:
    """Dispatch to the right backend for an image provider."""
    via = cfg["via"]
    aspect = f"{width}:{height}" if width != height else "1:1"
    if via == "fal.ai":
        payload = {
            "prompt": prompt,
            "image_size": _fal_image_size(width, height),
            "output_format": "png",   # critical: Godot rejects format/extension mismatches
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        res = _fal_run(cfg["endpoint"], payload)
        images = res.get("images") or []
        if not images:
            raise RuntimeError(f"{provider_name} returned no images: {res}")
        first = images[0]
        if isinstance(first, dict) and first.get("url"):
            bytes_written = _download_to(first["url"], out_path)
        elif isinstance(first, str):
            bytes_written = _download_to(first, out_path)
        else:
            raise RuntimeError(f"unrecognized image format from {provider_name}: {first}")
        # Defensive: verify magic bytes match the requested extension. fal.ai
        # ignores output_format on some pipelines and returns JPEG anyway.
        magic = out_path.read_bytes()[:8]
        is_jpeg = magic.startswith(b"\xff\xd8\xff")
        is_png = magic.startswith(b"\x89PNG\r\n\x1a\n")
        if out_path.suffix.lower() == ".png" and is_jpeg and not is_png:
            # Convert JPEG -> PNG to honor the requested extension.
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(out_path.read_bytes()))
                # If background was a flat fill, force white -> transparent via alpha
                # threshold (cheap removal; for proper alpha use the rembg tool).
                img = img.convert("RGBA")
                img.save(out_path, format="PNG")
                bytes_written = out_path.stat().st_size
            except ImportError:
                # No Pillow: rename so the extension matches the content. Caller can decide.
                jpg_path = out_path.with_suffix(".jpg")
                out_path.rename(jpg_path)
                return {"file": str(jpg_path), "bytes": bytes_written, "provider": provider_name,
                        "warning": f"requested .png but provider returned JPEG; saved as .jpg (install Pillow to auto-convert)"}
        return {"file": str(out_path), "bytes": bytes_written, "provider": provider_name}
    elif via == "gemini":
        pngs = _gemini_imagen(prompt, aspect=aspect, count=1)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(pngs[0])
        return {"file": str(out_path), "bytes": len(pngs[0]), "provider": provider_name}
    else:
        raise RuntimeError(f"unknown image backend: {via}")


def _fal_image_size(w: int, h: int) -> str | dict:
    """fal.ai accepts presets or {width, height} object. Pick the right one."""
    presets = {
        (1024, 1024): "square_hd",
        (512, 512): "square",
        (768, 1024): "portrait_4_3",
        (576, 1024): "portrait_16_9",
        (1024, 768): "landscape_4_3",
        (1024, 576): "landscape_16_9",
    }
    return presets.get((w, h)) or {"width": w, "height": h}


# ── 1. list_providers ────────────────────────────────────────────────────────

@mcp.tool()
def list_providers() -> str:
    """[FREE] List available generation providers, their kind (image/video/audio/bgremove), and which env var each needs. Useful before calling generate_* to confirm what's wired."""
    rows = []
    for name, cfg in PROVIDERS.items():
        rows.append({
            "name": name,
            "kind": cfg["kind"],
            "via": cfg["via"],
            "env_var": cfg["env"],
            "env_set": bool(_key(cfg["env"])),
            "default": cfg.get("default", False),
            "note": cfg.get("note", ""),
        })
    return _ok({"providers": rows, "count": len(rows)})


# ── 2. generate_image ────────────────────────────────────────────────────────

@mcp.tool()
def generate_image(prompt: str, output_path: str, width: int = 1024, height: int = 1024,
                   provider: str = "", negative_prompt: str = "", cache: bool = True) -> str:
    """[PAID, provider-metered] Generate a single image from a text prompt and write it to `output_path` (absolute, .png recommended). Default provider is flux-pro via fal.ai; pass `provider` to override (call list_providers to see options). Width/height accept any value but providers often have presets; common values are 512, 768, 1024. `cache=true` (default) reuses a prior file if the same prompt+size+provider was generated before."""
    out = _resolve_path(output_path)
    if not out:
        return _err(f"output_path must be absolute: {output_path}")
    if not out.suffix:
        out = out.with_suffix(".png")

    picked = _pick_provider("image", provider or None)
    if not picked:
        return _err(f"No image provider available. Got provider='{provider}'. Try list_providers.")
    name, cfg = picked
    if not _key(cfg["env"]):
        return _err(f"Provider {name} needs env var {cfg['env']} (add it to the env block of this MCP, then restart it)")

    # Cache: skip generation if a previous identical request already wrote a file we can reuse.
    if cache:
        key = _cache_key(prompt, width=width, height=height, provider=name, negative_prompt=negative_prompt)
        cache_file = _CACHE_DIR / f"{key}.png"
        if cache_file.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(cache_file.read_bytes())
            return _ok({"file": str(out), "bytes": cache_file.stat().st_size,
                        "provider": name, "cached": True})

    try:
        result = _provider_generate_image(name, cfg, prompt, out, width, height, negative_prompt)
    except Exception as e:
        return _err(f"generation failed: {e}", provider=name)

    if cache:
        key = _cache_key(prompt, width=width, height=height, provider=name, negative_prompt=negative_prompt)
        cache_file = _CACHE_DIR / f"{key}.png"
        cache_file.write_bytes(out.read_bytes())

    return _ok({**result, "prompt": prompt, "size": [width, height], "cached": False})


# ── 3. generate_pixel_art ────────────────────────────────────────────────────

PIXEL_ART_NEG = "blur, gradient shading, anti-aliasing, photorealistic, 3d render, smooth, soft, painting"

@mcp.tool()
def generate_pixel_art(prompt: str, output_path: str, size: int = 64, palette_size: int = 16,
                        provider: str = "", cut_background: bool = True) -> str:
    """[PAID] Generate a pixel-art sprite, ready to drop into a game. Pipeline:
        1. Render at 1024×1024 via flux-schnell (or your chosen provider)
        2. Remove background via rembg (default ON: image generators ignore the 'transparent background' prompt about 80% of the time)
        3. Downsample to `size`×`size` using nearest-neighbor (correct for pixel art, preserves crisp edges)

    `size`: 16/24/32/48/64/96/128/192/256 (final canvas). `palette_size` is a prompt hint.
    Set `cut_background=False` if you DON'T want background removal (e.g. tile assets that fill the canvas).
    Background removal is an extra ~$0.003 call but saves you from manually alpha-cutting every sprite."""
    if size not in (16, 24, 32, 48, 64, 96, 128, 192, 256):
        return _err(f"size must be one of 16/24/32/48/64/96/128/192/256, got {size}")
    enhanced = (f"pixel art sprite, {prompt}, "
                f"clean pixel edges, no anti-aliasing, "
                f"{palette_size}-color limited palette, "
                f"transparent background, centered, 1-pixel outline, "
                f"retro game asset")
    # Step 1: render at high resolution for quality (downsampling later).
    res_str = generate_image(prompt=enhanced, output_path=output_path,
                              width=1024, height=1024,
                              provider=provider, negative_prompt=PIXEL_ART_NEG)
    res = json.loads(res_str)
    if not res.get("ok"):
        return res_str
    file_path = res.get("file")
    if not file_path:
        return res_str

    # Step 2: cut background while still at high resolution (rembg works better on bigger images).
    bg_cut = False
    if cut_background:
        bg_res_str = remove_background(input_path=file_path, output_path=file_path)
        bg_res = json.loads(bg_res_str)
        if bg_res.get("ok"):
            bg_cut = True
        else:
            res["background_removal_warning"] = bg_res.get("error")

    # Step 3: downsample to target size with nearest-neighbor.
    try:
        from PIL import Image
        img = Image.open(file_path).convert("RGBA")
        img_small = img.resize((size, size), Image.NEAREST)
        img_small.save(file_path, format="PNG")
        res["file"] = file_path
        res["bytes"] = Path(file_path).stat().st_size
        res["final_size"] = [size, size]
        res["pixel_art_downsampled"] = True
        res["background_cut"] = bg_cut
    except Exception as e:
        res["pixel_art_downsampled"] = False
        res["warning"] = f"downsample failed: {e}"
    return json.dumps(res, indent=2, ensure_ascii=False)


# ── 4. generate_sprite_sheet ─────────────────────────────────────────────────

@mcp.tool()
def generate_sprite_sheet(prompt: str, output_dir: str, frame_count: int = 4,
                           frame_size: int = 64, action: str = "idle", provider: str = "") -> str:
    """[PAID] Generate N consistent frames for AnimatedSprite2D / SpriteFrames. Writes `frame_0.png`...`frame_N-1.png` into `output_dir`. `action` should describe the motion ("walking right", "attacking", "idle bobbing"). Each frame is generated with a step-N-of-M hint so the provider produces plausible animation phases. NOTE: AI image models do NOT produce perfectly consistent frames. For production use, generate once and hand-touch in Aseprite. For prototyping this is fine."""
    out_dir = _resolve_path(output_dir)
    if not out_dir:
        return _err(f"output_dir must be absolute: {output_dir}")
    if not 2 <= frame_count <= 12:
        return _err(f"frame_count must be 2-12, got {frame_count}")
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[dict] = []
    for i in range(frame_count):
        phase = f"frame {i+1} of {frame_count}, {action}, animation phase {int(100 * i / max(1, frame_count-1))}%"
        framed_prompt = f"pixel art sprite, {prompt}, {phase}, transparent background, centered, clean edges"
        frame_path = out_dir / f"frame_{i:02d}.png"
        res_str = generate_image(prompt=framed_prompt, output_path=str(frame_path),
                                  width=512, height=512, provider=provider,
                                  negative_prompt=PIXEL_ART_NEG)
        res = json.loads(res_str)
        if not res.get("ok"):
            return _err(f"frame {i} failed: {res.get('error')}", frames_written=len(frames))
        frames.append({"frame": i, "file": str(frame_path)})

    return _ok({"output_dir": str(out_dir), "frame_count": frame_count, "frames": frames, "action": action})


# ── 5. generate_ui_element ───────────────────────────────────────────────────

@mcp.tool()
def generate_ui_element(prompt: str, output_path: str, kind: str = "icon",
                         size: int = 256, provider: str = "") -> str:
    """[PAID] Generate UI assets (icons, buttons, frames, badges) with transparent backgrounds. `kind` is one of: icon, button, frame, badge, hud_element. Defaults to recraft-v3 (best at clean vector-style UI), falls back to flux-pro. Use `remove_background` after if the provider sneaks a background in."""
    if kind not in {"icon", "button", "frame", "badge", "hud_element"}:
        return _err(f"unknown kind: {kind}. Use icon|button|frame|badge|hud_element.")
    style_hint = {
        "icon": "clean flat icon, centered, simple shapes, game UI style",
        "button": "rounded button, beveled edges, game UI",
        "frame": "ornate frame, hollow center, decorative border",
        "badge": "circular badge with emblem, game achievement style",
        "hud_element": "HUD element, futuristic or fantasy game UI",
    }[kind]
    enhanced = f"{prompt}, {style_hint}, transparent background, no text, high contrast, vector-style"
    chosen = provider or ("recraft-v3" if _key("FAL_KEY") else "")
    return generate_image(prompt=enhanced, output_path=output_path,
                           width=size, height=size, provider=chosen,
                           negative_prompt="photograph, photorealistic, 3d, blurry, low quality")


# ── 6. generate_tileset ──────────────────────────────────────────────────────

@mcp.tool()
def generate_tileset(theme: str, output_dir: str, tile_size: int = 64, tile_count: int = 9, provider: str = "") -> str:
    """[PAID] Generate a tileset for TileMap: N variations of `theme` tiles (grass, stone, water, etc.). Writes `tile_00.png`...`tile_NN.png` to `output_dir`. Tiles share style via consistent prompt prefix but vary in detail/orientation. tile_count typically 4-16. Tiles are NOT auto-tiled (no edge matching); use a TileSet editor afterward."""
    out_dir = _resolve_path(output_dir)
    if not out_dir:
        return _err(f"output_dir must be absolute: {output_dir}")
    if not 2 <= tile_count <= 32:
        return _err(f"tile_count must be 2-32, got {tile_count}")
    out_dir.mkdir(parents=True, exist_ok=True)

    variations = ["plain", "with cracks", "with grass tuft", "with stone", "with detail spot",
                  "edge variant", "weathered", "mossy", "clean center", "with shadow",
                  "highlight variant", "rough texture", "smooth", "broken", "decorated",
                  "with flower", "wet", "dry", "bright", "dark", "with debris", "with footprint",
                  "with crystal", "with mushroom", "with pebble", "ornate", "minimal", "patterned",
                  "with crack pattern", "speckled", "with gradient", "with center mark"]

    tiles = []
    for i in range(tile_count):
        variant = variations[i % len(variations)]
        prompt = f"top-down pixel art tile, {theme}, {variant}, seamless texture, square aspect"
        tile_path = out_dir / f"tile_{i:02d}.png"
        res = json.loads(generate_image(prompt=prompt, output_path=str(tile_path),
                                          width=512, height=512, provider=provider,
                                          negative_prompt=PIXEL_ART_NEG))
        if not res.get("ok"):
            return _err(f"tile {i} failed: {res.get('error')}", tiles_written=len(tiles))
        tiles.append({"index": i, "variant": variant, "file": str(tile_path)})

    return _ok({"output_dir": str(out_dir), "theme": theme, "tile_size": tile_size,
                "tile_count": tile_count, "tiles": tiles})


# ── 7. generate_video ────────────────────────────────────────────────────────

@mcp.tool()
def generate_video(prompt: str, output_path: str, duration_seconds: int = 5,
                    aspect_ratio: str = "16:9", provider: str = "",
                    seed_image_path: str = "") -> str:
    """[PAID, expensive, ~$0.50-2.00/clip] Generate a short video from text (optionally image-conditioned via `seed_image_path`). Writes MP4 to `output_path`. Default provider is veo-3 via fal.ai. duration_seconds typically 5-10. Use cases in games: cutscenes, intro animations, animated logos, screen transitions, ambient backdrops. NOT for in-game animation (use sprite sheets instead, orders of magnitude cheaper)."""
    out = _resolve_path(output_path)
    if not out:
        return _err(f"output_path must be absolute: {output_path}")
    if not out.suffix:
        out = out.with_suffix(".mp4")

    picked = _pick_provider("video", provider or None)
    if not picked:
        return _err(f"No video provider available. Try list_providers.")
    name, cfg = picked
    if not _key(cfg["env"]):
        return _err(f"Provider {name} needs env var {cfg['env']}")

    payload = {"prompt": prompt, "duration": str(duration_seconds), "aspect_ratio": aspect_ratio}
    if seed_image_path:
        seed = _resolve_path(seed_image_path)
        if seed and seed.exists():
            payload["image_url"] = f"data:image/png;base64,{base64.b64encode(seed.read_bytes()).decode()}"
    try:
        res = _fal_run(cfg["endpoint"], payload, poll_seconds=600)
    except Exception as e:
        return _err(f"video generation failed: {e}", provider=name)

    video = res.get("video") or res.get("output")
    video_url = video.get("url") if isinstance(video, dict) else video
    if not video_url:
        return _err(f"no video URL in response: {res}", provider=name)
    bytes_written = _download_to(video_url, out)
    return _ok({"file": str(out), "bytes": bytes_written, "provider": name,
                "duration_seconds": duration_seconds, "aspect_ratio": aspect_ratio})


# ── 8. generate_audio_sfx ────────────────────────────────────────────────────

@mcp.tool()
def generate_audio_sfx(prompt: str, output_path: str, duration_seconds: float = 1.5, provider: str = "") -> str:
    """[PAID] Generate a short sound effect from text. Writes audio file (mp3/wav depending on provider) to `output_path`. Good for: pickup chime, hit impact, jump, footstep, magic cast, UI click. Duration typically 0.5-3s for SFX; longer for ambient loops."""
    out = _resolve_path(output_path)
    if not out:
        return _err(f"output_path must be absolute: {output_path}")
    if not out.suffix:
        out = out.with_suffix(".mp3")

    picked = _pick_provider("audio", provider or None)
    if not picked:
        return _err("No audio provider available.")
    name, cfg = picked
    if not _key(cfg["env"]):
        return _err(f"Provider {name} needs env var {cfg['env']}")

    try:
        res = _fal_run(cfg["endpoint"], {"text": prompt, "duration_seconds": duration_seconds})
    except Exception as e:
        return _err(f"audio generation failed: {e}", provider=name)

    audio = res.get("audio") or res.get("audio_file")
    audio_url = audio.get("url") if isinstance(audio, dict) else audio
    if not audio_url:
        return _err(f"no audio URL in response: {res}", provider=name)
    bytes_written = _download_to(audio_url, out)
    return _ok({"file": str(out), "bytes": bytes_written, "provider": name,
                "duration_seconds": duration_seconds})


# ── 9. remove_background ─────────────────────────────────────────────────────

@mcp.tool()
def remove_background(input_path: str, output_path: str = "", provider: str = "") -> str:
    """[PAID, cheap] Remove the background from an existing image (alpha-cut). Critical for cleaning up sprites the image generator drew on a non-transparent background. If `output_path` is omitted, writes alongside input as `<name>_alpha.png`."""
    inp = _resolve_path(input_path)
    if not inp or not inp.exists():
        return _err(f"input not found: {input_path}")
    if not output_path:
        out = inp.with_name(f"{inp.stem}_alpha.png")
    else:
        out = _resolve_path(output_path)
        if not out:
            return _err(f"output_path must be absolute: {output_path}")

    picked = _pick_provider("bgremove", provider or None)
    if not picked:
        return _err("No bgremove provider available.")
    name, cfg = picked
    if not _key(cfg["env"]):
        return _err(f"Provider {name} needs env var {cfg['env']}")

    # Send image as data URL.
    image_url = f"data:image/png;base64,{base64.b64encode(inp.read_bytes()).decode()}"
    try:
        res = _fal_run(cfg["endpoint"], {"image_url": image_url})
    except Exception as e:
        return _err(f"bg removal failed: {e}", provider=name)

    out_img = res.get("image")
    out_url = out_img.get("url") if isinstance(out_img, dict) else out_img
    if not out_url:
        return _err(f"no image URL in response: {res}", provider=name)
    bytes_written = _download_to(out_url, out)
    return _ok({"file": str(out), "bytes": bytes_written, "provider": name})


# ── 10. describe_image ───────────────────────────────────────────────────────

@mcp.tool()
def describe_image(input_path: str, focus: str = "game-asset") -> str:
    """[PAID, Anthropic API metering] Describe an existing image using Claude vision. `focus` shapes the output: 'game-asset' = palette/style/genre fit; 'sprite-prompt' = ready-to-feed-back-into-generator prompt; 'plain' = pure description. Use this to seed prompts off an image the user pasted."""
    inp = _resolve_path(input_path)
    if not inp or not inp.exists():
        return _err(f"input not found: {input_path}")
    key = _key("ANTHROPIC_API_KEY")
    if not key:
        return _err("ANTHROPIC_API_KEY not set")

    instruction = {
        "game-asset": "Describe this image as a game asset: palette (hex colors), visual style, suggested genre fit, sprite/scene/UI category. Be terse.",
        "sprite-prompt": "Write a single concise image-gen prompt that would reproduce this asset in the same style. Output only the prompt, no preamble.",
        "plain": "Describe what you see in 2-3 sentences.",
    }.get(focus, "Describe.")

    b64 = base64.b64encode(inp.read_bytes()).decode()
    media_type = "image/png" if inp.suffix.lower() == ".png" else "image/jpeg"
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": instruction},
            ],
        }],
    }
    try:
        out = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            body, timeout=60,
        )
    except Exception as e:
        return _err(f"vision call failed: {e}")
    text = "".join(b.get("text", "") for b in out.get("content", []))
    return _ok({"description": text.strip(), "focus": focus, "input": str(inp)})


# ════════════════════════════════════════════════════════════════════════════
#            HIGHER-LEVEL GENERATORS (RPG content scaffolding)
# ════════════════════════════════════════════════════════════════════════════


# ── 11. generate_background ──────────────────────────────────────────────────

@mcp.tool()
def generate_background(prompt: str, output_path: str, width: int = 1024, height: int = 576,
                         provider: str = "flux-pro") -> str:
    """[PAID, ~$0.04 with flux-pro] Generate a high-quality landscape/environment background image. Uses Flux Pro by default (best quality for environments). Common sizes: 1024×576 (16:9), 1920×1080 (full HD), 1024×1024 (square). NO pixel-art downsampling, NO background removal: backgrounds are meant to fill the canvas. Works well as a parallax layer in any engine."""
    return generate_image(prompt=f"{prompt}, cinematic game environment, detailed background art, no characters, no UI",
                           output_path=output_path, width=width, height=height,
                           provider=provider,
                           negative_prompt="characters, people, text, watermark, UI, low quality, blurry")


# ── 12. generate_character_portrait ──────────────────────────────────────────

@mcp.tool()
def generate_character_portrait(prompt: str, output_path: str, size: int = 512,
                                  provider: str = "flux-pro", cut_background: bool = True) -> str:
    """[PAID, ~$0.04 + ~$0.003 for bg removal] Generate a head-and-shoulders character portrait for dialog boxes and character select screens. Default 512×512, transparent background. Style guidance: "fantasy knight with red hair", "stoic merchant, old man, white beard", "young mage, blue robes". For pixel-art-style sprites use generate_pixel_art instead."""
    if size not in (256, 384, 512, 768, 1024):
        return _err(f"size must be 256/384/512/768/1024, got {size}")
    enhanced = f"character portrait, {prompt}, head and shoulders, looking forward, neutral background, RPG game art style"
    res_str = generate_image(prompt=enhanced, output_path=output_path, width=size, height=size,
                              provider=provider, negative_prompt="full body, multiple people, weapon focus, text")
    res = json.loads(res_str)
    if not res.get("ok"):
        return res_str
    if cut_background:
        file_path = res.get("file", "")
        bg_str = remove_background(input_path=file_path, output_path=file_path)
        bg = json.loads(bg_str)
        res["background_cut"] = bg.get("ok", False)
    return json.dumps(res, indent=2, ensure_ascii=False)


# ── 13. generate_character_sheet ─────────────────────────────────────────────

@mcp.tool()
def generate_character_sheet(class_concept: str, output_path: str = "", portrait_path: str = "",
                               generate_portrait: bool = False) -> str:
    """[PAID, Claude API metering, +Flux if generate_portrait=True] Use Claude to generate a complete RPG class definition from a concept string ("dark mage who uses blood magic", "tank paladin"). Returns JSON with: id, name, description, starting_stats (HP/MP/STR/DEF/SPD/INT), abilities (3-5 starting skills with id/name/cost/description), portrait_prompt. If output_path is set, writes the JSON to disk. If generate_portrait=True and portrait_path is set, also generates the portrait via Flux."""
    key = _key("ANTHROPIC_API_KEY")
    if not key:
        return _err("ANTHROPIC_API_KEY not set")

    prompt = f"""Design an RPG character class for this concept: "{class_concept}"

Return ONLY a JSON object with these exact fields (no markdown, no preamble):
{{
  "id": "snake_case_id",
  "name": "Display Name",
  "description": "1-2 sentence flavor description",
  "starting_stats": {{
    "max_health": <int 60-150>,
    "max_mana": <int 20-100>,
    "strength": <int 5-20>,
    "defense": <int 3-15>,
    "speed": <int 5-15>,
    "intelligence": <int 5-20>
  }},
  "abilities": [
    {{"id": "ability_id", "name": "Ability Name", "cost": <int 1-3>, "requires": [], "description": "..." }}
  ],
  "portrait_prompt": "concise visual description for an image generator"
}}

Make stats consistent with the concept (e.g. a mage has high INT/MANA, low STR/DEF). 3-5 abilities."""

    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        out = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            body, timeout=60,
        )
    except Exception as e:
        return _err(f"Claude call failed: {e}")

    text = "".join(b.get("text", "") for b in out.get("content", []))
    # Strip any markdown code fences.
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        sheet = json.loads(text)
    except json.JSONDecodeError as e:
        return _err(f"Claude returned invalid JSON: {e}", raw=text[:400])

    portrait_result: dict | None = None
    if generate_portrait and portrait_path:
        portrait_prompt = sheet.get("portrait_prompt", class_concept)
        pr_str = generate_character_portrait(prompt=portrait_prompt, output_path=portrait_path)
        portrait_result = json.loads(pr_str)
        if portrait_result.get("ok"):
            sheet["portrait"] = f"res://{Path(portrait_path).name}" if not portrait_path.startswith("res://") else portrait_path

    if output_path:
        out_p = _resolve_path(output_path)
        if out_p:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(sheet, indent=2), encoding="utf-8")

    return _ok({"sheet": sheet, "portrait": portrait_result, "saved_to": output_path or None})


# ── 14. generate_story_arc ───────────────────────────────────────────────────

@mcp.tool()
def generate_story_arc(premise: str, output_path: str = "", chapters: int = 5) -> str:
    """[PAID, Claude API metering] Use Claude to generate a complete game story arc from a one-line premise ("vampire kingdom invades human village", "lost prince must reclaim throne"). Returns JSON with: title, world_bible, main_characters[], chapters[] (each with id/title/setting/objective/key_events/boss_encounter). `chapters` is 3-10 typical. Output is data: feed it to your dialog_tree, quest_manager, level scaffold."""
    key = _key("ANTHROPIC_API_KEY")
    if not key:
        return _err("ANTHROPIC_API_KEY not set")
    if not 3 <= chapters <= 10:
        return _err(f"chapters must be 3-10, got {chapters}")

    prompt = f"""Design a complete game story arc for this premise: "{premise}"

Return ONLY a JSON object with these fields (no markdown, no preamble):
{{
  "title": "Game Title",
  "logline": "1-sentence pitch",
  "world_bible": "3-4 sentences describing the world, tone, and core conflict",
  "main_characters": [
    {{"id": "snake_case", "name": "Name", "role": "protagonist|villain|ally|mentor", "description": "...", "portrait_prompt": "..."}}
  ],
  "chapters": [
    {{
      "id": "ch_01_intro",
      "title": "Chapter Title",
      "setting": "where it happens",
      "objective": "what the player must do",
      "key_events": ["event 1", "event 2", "event 3"],
      "boss_encounter": {{"name": "Boss Name", "description": "...", "portrait_prompt": "..."}} or null
    }}
  ]
}}

Generate exactly {chapters} chapters. Make the arc rise-climax-fall. 3-5 main characters."""

    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        out = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            body, timeout=90,
        )
    except Exception as e:
        return _err(f"Claude call failed: {e}")

    text = "".join(b.get("text", "") for b in out.get("content", []))
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        arc = json.loads(text)
    except json.JSONDecodeError as e:
        return _err(f"Claude returned invalid JSON: {e}", raw=text[:400])

    if output_path:
        out_p = _resolve_path(output_path)
        if out_p:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(arc, indent=2), encoding="utf-8")

    return _ok({"arc": arc, "chapters": len(arc.get("chapters", [])), "saved_to": output_path or None})


# ── 15. generate_dialog_tree ─────────────────────────────────────────────────

@mcp.tool()
def generate_dialog_tree(scene_context: str, output_path: str = "", branches: int = 3) -> str:
    """[PAID, Claude API metering] Use Claude to generate a branching dialog tree JSON ready to feed to a dialog-tree component in your engine. `scene_context` describes the situation ("guard at gate, player is wanted", "shopkeeper, first meeting"). Output matches the DialogTree JSON format: {node_id: {speaker, text, choices:[{label,next}], end, signal}}. `branches` is rough conversation depth (2-5)."""
    key = _key("ANTHROPIC_API_KEY")
    if not key:
        return _err("ANTHROPIC_API_KEY not set")

    prompt = f"""Write a branching dialog tree for this scene: "{scene_context}"

Output ONLY JSON (no markdown). Format:
{{
  "node_id": {{
    "speaker": "Name",
    "text": "What they say",
    "choices": [{{"label": "player option", "next": "next_node_id"}}],
    "end": false,
    "signal": "optional_event_name"
  }}
}}

Rules:
- Start node must be id "start"
- Each leaf node has "end": true and no "choices"
- 3-{branches} branch points, 6-12 nodes total
- Natural, terse dialog (no Shakespeare)
- Include at least one consequential choice (good/bad outcome split)"""

    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        out = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            body, timeout=60,
        )
    except Exception as e:
        return _err(f"Claude call failed: {e}")

    text = "".join(b.get("text", "") for b in out.get("content", []))
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        tree = json.loads(text)
    except json.JSONDecodeError as e:
        return _err(f"Claude returned invalid JSON: {e}", raw=text[:400])

    if "start" not in tree:
        return _err("dialog tree missing 'start' node", got_keys=list(tree.keys()))

    if output_path:
        out_p = _resolve_path(output_path)
        if out_p:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(tree, indent=2), encoding="utf-8")

    return _ok({"tree": tree, "node_count": len(tree), "saved_to": output_path or None})


# ── 16. generate_music_loop ──────────────────────────────────────────────────

@mcp.tool()
def generate_music_loop(prompt: str, output_path: str, duration_seconds: float = 30.0) -> str:
    """[PAID, ~$0.10] Generate a short loopable music track via fal.ai's Stable Audio. Good for: dungeon ambient, town theme, battle music, menu loop. duration_seconds 10-60 typical. NOT meant for full soundtracks: generate per-scene mood pieces and let MusicLayer crossfade them."""
    out = _resolve_path(output_path)
    if not out:
        return _err(f"output_path must be absolute: {output_path}")
    if not out.suffix:
        out = out.with_suffix(".mp3")
    if not _key("FAL_KEY"):
        return _err("FAL_KEY not set")
    try:
        res = _fal_run(
            "fal-ai/stable-audio",
            {"prompt": prompt, "seconds_total": int(duration_seconds)},
            poll_seconds=180,
        )
    except Exception as e:
        return _err(f"music generation failed: {e}")
    audio = res.get("audio_file") or res.get("audio")
    url = audio.get("url") if isinstance(audio, dict) else audio
    if not url:
        return _err(f"no audio URL: {res}")
    bytes_written = _download_to(url, out)
    return _ok({"file": str(out), "bytes": bytes_written, "duration_seconds": duration_seconds})


# ── 17. generate_voice_line ──────────────────────────────────────────────────

@mcp.tool()
def generate_voice_line(text: str, output_path: str, voice_id: str = "Rachel",
                          stability: float = 0.5, similarity_boost: float = 0.75) -> str:
    """[PAID, ~$0.02 per ~200 chars] Generate a voice line via ElevenLabs TTS through fal.ai. `voice_id` is a preset name like "Rachel", "Domi", "Bella", "Antoni", "Elli", "Josh", "Arnold", "Adam", "Sam". Use distinct voice_ids per character for consistent character voices. For background NPCs, generate once and cache."""
    out = _resolve_path(output_path)
    if not out:
        return _err(f"output_path must be absolute: {output_path}")
    if not out.suffix:
        out = out.with_suffix(".mp3")
    if not _key("FAL_KEY"):
        return _err("FAL_KEY not set")
    try:
        res = _fal_run(
            "fal-ai/elevenlabs/tts/turbo-v2.5",
            {"text": text, "voice": voice_id,
             "stability": stability, "similarity_boost": similarity_boost},
            poll_seconds=120,
        )
    except Exception as e:
        return _err(f"voice generation failed: {e}")
    audio = res.get("audio") or res.get("audio_file")
    url = audio.get("url") if isinstance(audio, dict) else audio
    if not url:
        return _err(f"no audio URL: {res}")
    bytes_written = _download_to(url, out)
    return _ok({"file": str(out), "bytes": bytes_written, "voice_id": voice_id, "chars": len(text)})


# ════════════════════════════════════════════════════════════════════════════
#        CONSISTENCY PACK: character-preserving edits via Flux Kontext
# ════════════════════════════════════════════════════════════════════════════
# These tools solve "same character, different pose/expression/angle", the
# hardest problem in AI sprite generation. Kontext is purpose-built for it.


# ── 18. edit_image ───────────────────────────────────────────────────────────

@mcp.tool()
def edit_image(input_path: str, edit_prompt: str, output_path: str = "",
                provider: str = "kontext-pro") -> str:
    """[PAID, ~$0.04] Edit an existing image with natural language. Examples: "rotate the character 180 degrees", "make the character smile", "open the mouth wide showing teeth", "change the background to red". Uses Flux Kontext by default, which preserves character identity while making the requested change. If output_path is omitted, writes alongside input as `<name>_edit.png`."""
    inp = _resolve_path(input_path)
    if not inp or not inp.exists():
        return _err(f"input_path not found: {input_path}")
    if output_path:
        out = _resolve_path(output_path)
        if not out:
            return _err(f"output_path must be absolute: {output_path}")
    else:
        out = inp.with_name(f"{inp.stem}_edit.png")
    if not out.suffix:
        out = out.with_suffix(".png")

    picked = _pick_provider("edit", provider or None)
    if not picked:
        return _err(f"No edit provider available. Got '{provider}'.")
    name, cfg = picked
    if not _key(cfg["env"]):
        return _err(f"Provider {name} needs env var {cfg['env']}")

    image_url = f"data:image/png;base64,{base64.b64encode(inp.read_bytes()).decode()}"
    try:
        res = _fal_run(cfg["endpoint"], {
            "image_url": image_url,
            "prompt": edit_prompt,
            "output_format": "png",
            "num_images": 1,
        }, poll_seconds=180)
    except Exception as e:
        return _err(f"edit failed: {e}", provider=name)

    # Kontext returns 'images': [{url, ...}] or sometimes 'image'.
    images = res.get("images") or ([res["image"]] if res.get("image") else [])
    if not images:
        return _err(f"no image in response: {res}", provider=name)
    first = images[0]
    img_url = first.get("url") if isinstance(first, dict) else first
    bytes_written = _download_to(img_url, out)
    return _ok({
        "input": str(inp),
        "output": str(out),
        "bytes": bytes_written,
        "provider": name,
        "edit_prompt": edit_prompt,
    })


# ── 19. generate_pose_variant ────────────────────────────────────────────────

@mcp.tool()
def generate_pose_variant(input_path: str, pose: str, output_path: str,
                            size: int = 64, cut_background: bool = True) -> str:
    """[PAID, ~$0.043] Generate a pose variant of an existing character sprite. Pipeline: Kontext edit ("show this creature from behind / walking / attacking") → rembg → nearest-neighbor downsample to `size`. Use for animation frames or alt views of the SAME creature. Common `pose` values: "back view facing away", "side profile walking", "attacking with mouth open", "jumping mid-air", "crouching", "victory pose". Output matches `size` exactly (16/24/32/48/64/96/128/192/256)."""
    inp = _resolve_path(input_path)
    if not inp or not inp.exists():
        return _err(f"input_path not found: {input_path}")
    out = _resolve_path(output_path)
    if not out:
        return _err(f"output_path must be absolute: {output_path}")
    if size not in (16, 24, 32, 48, 64, 96, 128, 192, 256):
        return _err(f"size must be one of 16/24/32/48/64/96/128/192/256, got {size}")

    edit_prompt = (f"Change this creature's pose: {pose}. "
                    f"Keep the same character, same colors, same art style. "
                    f"Pixel art, transparent background.")

    # Step 1: Kontext edit.
    edit_res_str = edit_image(input_path=str(inp), edit_prompt=edit_prompt, output_path=str(out))
    edit_res = json.loads(edit_res_str)
    if not edit_res.get("ok"):
        return edit_res_str

    # Step 2: cut background.
    if cut_background:
        bg_str = remove_background(input_path=str(out), output_path=str(out))
        bg_res = json.loads(bg_str)
        if not bg_res.get("ok"):
            edit_res["background_removal_warning"] = bg_res.get("error")

    # Step 3: downsample to target size (nearest-neighbor for pixel-art crispness).
    try:
        from PIL import Image
        img = Image.open(out).convert("RGBA")
        img_small = img.resize((size, size), Image.NEAREST)
        img_small.save(out, format="PNG")
        edit_res["final_size"] = [size, size]
        edit_res["bytes"] = out.stat().st_size
        edit_res["pixel_art_downsampled"] = True
    except Exception as e:
        edit_res["pixel_art_downsampled"] = False
        edit_res["warning"] = f"downsample failed: {e}"

    edit_res["pose"] = pose
    return json.dumps(edit_res, indent=2, ensure_ascii=False)


# ── 20. generate_character_set ───────────────────────────────────────────────

@mcp.tool()
def generate_character_set(prompt: str, output_dir: str, size: int = 64,
                             poses: str = "",
                             palette_size: int = 12) -> str:
    """[PAID, ~$0.18 for default 4-pose set] One-shot full character sprite set generator. Workflow: generates a base pixel-art creature/character from `prompt`, then creates pose variants via Kontext (back view + walking + attacking by default). All sprites saved to `output_dir` at the target `size`, ready to drop into a game. `poses` is an optional JSON array of {name, pose_prompt} dicts to override the default set. Returns paths to all generated sprites."""
    out_dir = _resolve_path(output_dir)
    if not out_dir:
        return _err(f"output_dir must be absolute: {output_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Default 4-pose set: idle/base, back, walk, attack: enough for a minimal monster-collector entry.
    default_poses = [
        {"name": "back",   "pose_prompt": "rotate this creature 180 degrees, show its back, view from behind"},
        {"name": "walk",   "pose_prompt": "walking pose, side profile, one foot lifted mid-step"},
        {"name": "attack", "pose_prompt": "aggressive attacking pose, mouth open showing teeth, leaning forward"},
    ]
    if poses:
        try:
            pose_list = json.loads(poses)
            assert isinstance(pose_list, list)
            for p in pose_list:
                assert "name" in p and "pose_prompt" in p
        except Exception:
            return _err("poses must be JSON array of {name, pose_prompt} dicts")
    else:
        pose_list = default_poses

    # Step 1: generate base via generate_pixel_art (already does bg-removal + downsample).
    base_path = out_dir / "base.png"
    base_str = generate_pixel_art(prompt=prompt, output_path=str(base_path),
                                    size=size, palette_size=palette_size,
                                    provider="flux-schnell", cut_background=True)
    base_res = json.loads(base_str)
    if not base_res.get("ok"):
        return _err(f"base generation failed: {base_res.get('error')}", base_response=base_res)

    # The downsampled base is too small for Kontext to work well on; Kontext works
    # better at higher resolution. So we keep an "edit master" at higher res.
    # Strategy: generate base with cut_background=False at 1024, then for edits use the 1024
    # version, downsample at the end.
    # Simpler approach: regenerate a non-downsampled "edit master" for Kontext input.
    edit_master = out_dir / "_edit_master.png"
    master_str = generate_image(
        prompt=f"pixel art sprite, {prompt}, clean pixel edges, transparent background, centered, retro game asset",
        output_path=str(edit_master), width=1024, height=1024,
        provider="flux-schnell",
        negative_prompt="blur, gradient shading, anti-aliasing, photorealistic, 3d render",
    )
    master_res = json.loads(master_str)
    if not master_res.get("ok"):
        # Fall back to the small base as the edit input.
        edit_master = base_path

    sprites: dict = {"base": str(base_path)}
    failures: list = []
    for entry in pose_list:
        name = entry["name"]
        pose_prompt = entry["pose_prompt"]
        out_path = out_dir / f"{name}.png"
        # Edit at high res, then downsample as part of generate_pose_variant.
        # generate_pose_variant downsamples + bg-removes already.
        # But its input is the high-res master, not the tiny downsampled base.
        variant_str = generate_pose_variant(
            input_path=str(edit_master),
            pose=pose_prompt,
            output_path=str(out_path),
            size=size,
            cut_background=True,
        )
        variant_res = json.loads(variant_str)
        if variant_res.get("ok"):
            sprites[name] = str(out_path)
        else:
            failures.append({"name": name, "error": variant_res.get("error")})

    # Clean up the high-res edit master (don't ship it in the asset folder).
    try:
        if edit_master.exists() and edit_master.name == "_edit_master.png":
            edit_master.unlink()
    except OSError:
        pass

    return _ok({
        "output_dir": str(out_dir),
        "size": size,
        "sprites": sprites,
        "pose_count": len(sprites) - 1,
        "failures": failures,
    })


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 0))
    if port:
        import uvicorn
        uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
