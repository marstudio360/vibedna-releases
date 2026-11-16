"""Game Assets MCP: ONE door for game assets, harvest-free + generate-paid.

Composes two standalone servers into a single namespace (no code duplication:
they stay independent products, this server mounts their tools at import time):

  · asset-forge-mcp:      harvest FREE packs (itch/OGA/Kenney), license-gated
                           library + export  (library_stats, search_packs,
                           pack_info, classify_license, discover, harvest,
                           export_pack, rebuild_gallery)
  · vibe-game-assets-mcp: GENERATE new assets via paid APIs (fal / Gemini /
                           ElevenLabs)  (generate_pixel_art, generate_tileset,
                           generate_audio_sfx, ... ~20 tools)

Plus the router this composition exists for:

  · find_or_generate(): search the free library FIRST; only fall through to
    paid generation when nothing free fits (and only if allow_paid=True).

Config (env):
  ASSET_FORGE_HOME / ASSET_FORGE_LIB: forwarded to the harvest lane
  provider keys (FAL_KEY, GEMINI_API_KEY, ELEVENLABS_API_KEY, ...): generation lane
  GAME_ASSETS_FORGE_DIR / GAME_ASSETS_GEN_DIR: override sibling server locations

A lane that fails to import doesn't kill the server; its tools are just absent
and `lanes_status()` tells you why.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_HERE = Path(__file__).resolve().parent
_SERVERS = _HERE.parent

mcp = FastMCP("game-assets")

_LANES: dict[str, dict] = {}


def _load_lane(label: str, env_var: str, default_dirname: str):
    """Import a sibling MCP server as a plain module and mount its tools here."""
    info = {"loaded": False, "error": None, "tools": [], "skipped": []}
    _LANES[label] = info
    try:
        # Where to look for the lane. The environment variable wins; otherwise look INSIDE this
        # folder first and only then next to it. Looking only next to it breaks on a buyer's
        # machine, where there are no sibling folders, just this one.
        env_dir = os.environ.get(env_var)
        candidates = [Path(env_dir)] if env_dir else [_HERE / default_dirname, _SERVERS / default_dirname]
        d = next((c for c in candidates if (c / "server.py").exists()), candidates[-1])
        f = d / "server.py"
        if not f.exists():
            info["error"] = f"server.py not found (looked in: {', '.join(str(c) for c in candidates)})"
            return None
        spec = importlib.util.spec_from_file_location(f"_lane_{label}", f)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"_lane_{label}"] = mod
        spec.loader.exec_module(mod)
        for tname, tool in mod.mcp._tool_manager._tools.items():
            if tname in mcp._tool_manager._tools:
                info["skipped"].append(tname)
                continue
            mcp.add_tool(tool.fn, name=tname, description=tool.description)
            info["tools"].append(tname)
        info["loaded"] = True
        return mod
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
        return None


_AF = _load_lane("harvest", "GAME_ASSETS_FORGE_DIR", "asset-forge-mcp")
_GEN = _load_lane("generate", "GAME_ASSETS_GEN_DIR", "vibe-game-assets-mcp")


def _ok(**data) -> str:
    return json.dumps({"ok": True, **data}, indent=2, ensure_ascii=False)


def _err(msg: str, **data) -> str:
    return json.dumps({"ok": False, "error": msg, **data}, indent=2, ensure_ascii=False)


@mcp.tool()
def lanes_status() -> str:
    """[FREE] Which asset lanes are mounted (harvest-free / generate-paid), their
    tool lists, and any import errors. Call this first if a tool seems missing."""
    return _ok(lanes={k: {"loaded": v["loaded"], "error": v["error"],
                          "tool_count": len(v["tools"]), "tools": v["tools"]}
                      for k, v in _LANES.items()})


# asset_type -> (generation function name, kwargs builder)
_GEN_MAP = {
    "pixel_art":    ("generate_pixel_art",   lambda q, o: {"prompt": q, "output_path": str(Path(o) / "asset.png")}),
    "sprite_sheet": ("generate_sprite_sheet", lambda q, o: {"prompt": q, "output_dir": o}),
    "tileset":      ("generate_tileset",     lambda q, o: {"theme": q, "output_dir": o}),
    "ui":           ("generate_ui_element",  lambda q, o: {"prompt": q, "output_path": str(Path(o) / "ui.png")}),
    "sfx":          ("generate_audio_sfx",   lambda q, o: {"prompt": q, "output_path": str(Path(o) / "sfx.mp3")}),
    "music":        ("generate_music_loop",  lambda q, o: {"prompt": q, "output_path": str(Path(o) / "music.mp3")}),
    "background":   ("generate_background",  lambda q, o: {"prompt": q, "output_path": str(Path(o) / "background.png")}),
    "image":        ("generate_image",       lambda q, o: {"prompt": q, "output_path": str(Path(o) / "image.png")}),
}


@mcp.tool()
def find_or_generate(query: str, asset_type: str = "pixel_art", output_dir: str = "",
                     allow_paid: bool = False, limit: int = 5) -> str:
    """The router: search the FREE harvested library first; only if nothing fits,
    fall through to paid generation. With allow_paid=False (default) it never
    spends: it returns the exact generate_* call it WOULD make instead.
    asset_type: pixel_art | sprite_sheet | tileset | ui | sfx | music | background | image."""
    hits = []
    if _AF is not None:
        try:
            res = json.loads(_AF.search_packs(query))
            hits = (res.get("results") or res.get("packs") or res.get("hits") or [])[:limit]
        except Exception as e:  # noqa: BLE001
            return _err(f"library search failed: {e}")
    if hits:
        return _ok(source="free_library", hits=hits,
                   next_step="export_pack(slug=<pick one>, dest_dir=<your game project>). "
                             "License gate + CREDITS.md handled automatically")
    if asset_type not in _GEN_MAP:
        return _err(f"unknown asset_type '{asset_type}'", valid=list(_GEN_MAP))
    fn_name, kw_builder = _GEN_MAP[asset_type]
    if _GEN is None or not hasattr(_GEN, fn_name):
        return _err(f"no free hits and generation lane unavailable (missing {fn_name})")
    if not allow_paid:
        return _ok(source="none_free", hits=[],
                   recommendation=f"{fn_name}({json.dumps(kw_builder(query, output_dir or '<output_dir>'))})",
                   note="nothing free matched; re-run with allow_paid=True and output_dir to generate (PAID)")
    if not output_dir:
        return _err("output_dir required when allow_paid=True")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    try:
        result = getattr(_GEN, fn_name)(**kw_builder(query, output_dir))
        return _ok(source="generated_paid", tool=fn_name, result=json.loads(result))
    except Exception as e:  # noqa: BLE001
        return _err(f"generation failed: {e}", tool=fn_name)


if __name__ == "__main__":
    mcp.run()
