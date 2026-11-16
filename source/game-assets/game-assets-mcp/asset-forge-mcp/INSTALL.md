# Asset Forge MCP: Install Guide

A license-audited game-asset library as MCP tools. Discover free asset packs
(itch.io / OpenGameArt / Kenney), classify their licenses with an audit trail
(every verdict records the exact phrase that decided it), download + extract +
shelve packs by what the license actually permits, and export packs into game
projects with automatic `CREDITS.md` attribution.

Drop this whole file into any AI chat (Claude, etc.) and say "install this".
It contains everything needed.

## What you get

| Tool | Cost | What it does |
|---|---|---|
| `library_stats` | FREE | Packs per shelf, image/audio totals, disk state |
| `search_packs` | FREE | Search the library by title/author/tags/license |
| `pack_info` | FREE | Full manifest row + on-disk file counts for one pack |
| `classify_license` | FREE | Run the license classifier on any text; verdict + policy results |
| `discover` | FREE | List candidate packs from a source, no downloads |
| `harvest` | Heavy network + disk (no dollar cost) | Discover → license-read → download → extract → shelve → manifest |
| `export_pack` | FREE | Copy a pack into a project, policy-gated, auto-CREDITS.md |
| `rebuild_gallery` | FREE | Regenerate the browsable HTML gallery of the library |

The library is four shelves, sorted by what the license permits:

```
library/01-CLEAN-CC0/   ship anywhere, no paperwork
library/02-CREDIT/      ship, but the pack lands in CREDITS.md
library/03-CHECK/       tiered or unknown license: a human must read it
library/04-BLOCKED/     non-commercial / share-alike: prototype only
```

## Requirements

- Python 3.11+ with the `mcp` package: `pip install "mcp>=1.2,<2"` (the 1.x line: `mcp` 2.x removed `mcp.server.fastmcp`)
- The pipeline code (the `forge/` package + `gallery.py`) ships inside this
  folder, next to `server.py`, and is found automatically. To run a different
  copy, point `ASSET_FORGE_HOME` at the folder that holds it.
- Windows / macOS / Linux: pure standard-library pipeline, no compiled deps.

## Layout

```
<ASSET_FORGE_HOME>/
    forge/            the pipeline package (discover, licenses, packpage, fetch, itch_api)
    gallery.py        HTML gallery builder
<ASSET_FORGE_LIB>/    the library root, created on first harvest
    library/01..04/   the four shelves
    meta/manifest.json
    raw/  extracted/
```

## Environment variables

| Var | Required | Default | Meaning |
|---|---|---|---|
| `ASSET_FORGE_HOME` | optional | dir next to `server.py` if it holds `forge/`, else `~/.asset-forge` | Directory containing the `forge/` package and `gallery.py` |
| `ASSET_FORGE_LIB` | recommended | `~/.asset-forge/library-root` | Library root (shelves, manifest, downloads) |
| `ITCH_API_KEY` | only for itch harvests | none | itch.io API key (itch.io → Settings → API keys). itch downloads only work through the API |

## Register with Claude Code / Claude Desktop

Add to your project's `.mcp.json` (Claude Code) or
`claude_desktop_config.json` (Claude Desktop) under `mcpServers`:

```json
"asset-forge": {
  "type": "stdio",
  "command": "python",
  "args": ["<absolute path to>/asset-forge-mcp/server.py"],
  "env": {
    "ASSET_FORGE_LIB": "<absolute path to your library root>",
    "ITCH_API_KEY": "<your itch.io api key (optional)>"
  }
}
```

On Windows use double-backslash paths (`"D:\\game-assets"`). Restart the
Claude tab/app to load the server.

## Smoke test (no MCP client needed)

```
python -c "import os,sys,json,importlib.util; \
os.environ.setdefault('ASSET_FORGE_LIB', r'<library root>'); \
spec=importlib.util.spec_from_file_location('s', r'<path>/server.py'); \
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); \
print(m.classify_license('CC BY-NC 4.0'))"
```

Expected: a JSON verdict with `"commercial_ok": false`. The classifier
correctly blocks NonCommercial from ever reaching a sold game.

## Typical flow

1. `discover("itch", "pixel-art,rpg")`: see what's out there, zero downloads
2. `harvest("kenney")`: pull the curated CC0 seed list into the library
3. `library_stats()` / `search_packs("dungeon")`: browse what landed
4. `rebuild_gallery()`: visual gallery, one HTML page per shelf
5. `export_pack("kenney__Kenney__Tiny-Dungeon", "C:\\my-game\\assets")`:
   policy-gated copy; attribution packs get a CREDITS.md line automatically

## License-safety model (why this exists)

"Free" on itch.io means six different things legally. Every harvested pack
gets a structured verdict (`commercial_ok`, `attribution_required`,
`share_alike`, confidence, the matched phrase). Unknown or tiered-price
licenses are quarantined on `03-CHECK`, never guessed. `export_pack` refuses
to place a pack into a project unless its shelf clears the shipping policy
you ask for, so a non-commercial asset can never silently end up in a game
you sell.

Optional integration: the pipeline pairs well with a game-engine MCP (e.g. a
Godot scaffolding server): export packs straight into a project's asset dir.
No other product is required; this server is fully standalone.
