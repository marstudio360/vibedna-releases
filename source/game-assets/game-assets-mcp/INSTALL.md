# Game Assets MCP: install

ONE door for game assets: search a harvested FREE library first, generate by AI (paid) only when nothing free fits.

This server **composes** two standalone MCPs at import time (no code duplication):
- **asset-forge-mcp**: harvest free packs (itch.io / OpenGameArt / Kenney) with a license classifier + gated export
- **vibe-game-assets-mcp**: ~20 generation tools via paid APIs (fal.ai / Gemini / ElevenLabs)

Both ship inside this folder (`asset-forge-mcp/` with its `forge/` pipeline and `gallery.py`, and `vibe-game-assets-mcp/`) and are found automatically. To run other copies, point the env vars below at them.

**New in 1.0.3:** the free-library pipeline (`forge/` and `gallery.py`) ships inside `asset-forge-mcp/`, so `library_stats`, `search_packs`, `classify_license`, `discover`, `harvest`, `export_pack` and `rebuild_gallery` work right after install.

## Install the Python packages

```bash
pip install -r vibe-game-assets-mcp/requirements.txt
```

The requirement is pinned to the `mcp` 1.x line (`mcp>=1.2,<2`), because `mcp` 2.x removed `mcp.server.fastmcp`.

## Register with Claude Code
```json
"game-assets": {
  "type": "stdio",
  "command": "python",
  "args": ["/path/to/game-assets-mcp/server.py"],
  "env": {
    "ASSET_FORGE_LIB": "/path/to/asset-library"
  }
}
```

## Config (env)
| Var | What |
|---|---|
| `ASSET_FORGE_LIB` | library root (default `~/.asset-forge/library-root`) |
| `ASSET_FORGE_HOME` | optional: another copy of the pipeline code (default: the `forge/` inside `asset-forge-mcp/`) |
| `FAL_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, ... | generation-lane provider keys (only the providers you use) |
| `GAME_ASSETS_FORGE_DIR` / `GAME_ASSETS_GEN_DIR` | override where the two composed servers live |

## Tools
All 8 harvest tools + all ~20 generation tools mount under one namespace, plus:

| Tool | What |
|---|---|
| `lanes_status()` | which lanes mounted, tool lists, import errors |
| `find_or_generate(query, asset_type, output_dir, allow_paid)` | **the router**: free library first; on miss returns the exact paid call it would make (never spends unless `allow_paid=True`) |

A lane that fails to import doesn't kill the server; its tools are absent and `lanes_status()` explains why.

## Smoke test
Ask Claude: *"lanes status"* → *"find or generate: dungeon tileset"* (should hit the free library if you've harvested).
