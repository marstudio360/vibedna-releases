---
name: game-assets-install
description: Install the Vibedna Game Assets MCP, which finds free game art you may ship and makes new art with your own provider keys. Paste this file into your AI chat and ask it to install: it checks the download hash, explains the bundled files, and after your yes installs into a private virtual environment and registers the server in Claude Code at user scope.
---

# Game Assets MCP: Install Guide

This guide matches version 1.0.6.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `MANUAL.md`, `vibe-game-assets-mcp/requirements.txt` and the three `server.py` files and say in plain words what they do before installing. Ask before anything is written. Never ask for a key or password in the chat, and never open or print a file that holds keys. `INSTALL.md` in the zip is this guide. `MANUAL.md` is the product's own older document, kept in the zip for what this guide does not repeat (settings, the tools, a first test). It and `asset-forge-mcp/INSTALL.md` describe an older manual way to install: where they differ, follow this guide.

## What it is

A Python MCP server on your machine with 30 tools for game art and sound. The 8 free-library tools list packs on itch.io, OpenGameArt and Kenney, read each licence, shelve packs by what it allows and copy a pack into your game with a `CREDITS.md` line. The 20 generation tools make images, sprites, tilesets, sound, music, video and game text through paid services, with your own keys. `lanes_status` and `find_or_generate` join the two. Needs Python 3.10 or newer (3.11 preferred: the bundled free-library notes ask for it).

## Trust box

- **File:** `game-assets-mcp-1.0.6.zip`, 61,803 bytes, 15 files.
- **SHA-256:** `a481260d707b1561127f1678fa886253cfe04743f3832a3e27587537efa014d0`
  - Linux: `sha256sum game-assets-mcp-1.0.6.zip`
  - macOS: `shasum -a 256 game-assets-mcp-1.0.6.zip`
  - Windows PowerShell: `Get-FileHash game-assets-mcp-1.0.6.zip` (capitals, same value)
  - Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/game-assets-mcp-1.0.6.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The full code of this version is public there, in `source/game-assets/`: it can be read before anything is downloaded.
- **Dependencies,** pinned to the exact versions tested: `mcp==1.30.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`.
- **Reads from the environment:** `ASSET_FORGE_LIB` (where harvested packs are kept), the four keys below, and a `.env` file in `vibe-game-assets-mcp/` or a parent folder if one exists.
- **Writes:** a `cache` folder in `vibe-game-assets-mcp/` (copies of generated images); the library, by default `~/.asset-forge/library-root`, from the first harvest (downloads up to 300 MB per pack, four shelves, a manifest, gallery pages); the output paths you give the generate tools; the game folder you name in `export_pack`.
- **Network, only when you call the tools:** free-library lane: `itch.io`, `api.itch.io`, `opengameart.org`, `kenney.nl` and the download links those pages give. Generation lane: `queue.fal.run`, `generativelanguage.googleapis.com`, `api.anthropic.com` and the result files they return. Nothing else was found.
- **Never touches:** it starts no other programs, and no telemetry was found.

Honest limits:

- The hash proves your download is the file this guide describes, not who made it or that the code is safe. So your AI reads the files and you say yes first.
- **Spending:** `find_or_generate` only shows the paid call it would make unless called with `allow_paid=True`. The `generate_*` tools, `remove_background`, `edit_image` and `describe_image` call the paid service as soon as they run, billed to your provider account: tell your AI to ask before each one. With no key set, no paid call can go through.
- The licence check is rule-based text matching, not legal advice. Packs it cannot decide wait on the `03-CHECK` shelf for you to read.

## Keys

All optional: with none, Kenney and OpenGameArt harvests still work.

- `FAL_KEY`: images, video, sound, music, voice, background removal, image edits.
- `GEMINI_API_KEY`: one extra image provider.
- `ANTHROPIC_API_KEY`: `describe_image`, `generate_character_sheet`, `generate_story_arc`, `generate_dialog_tree`.
- `ITCH_API_KEY`: harvesting from itch.io.

(`ELEVENLABS_API_KEY`, named in the bundled notes, is not read by the code.)

You put keys in yourself, never in the chat: either a `.env` file in `game-assets-mcp/vibe-game-assets-mcp/` with one `NAME=value` per line, or `-e NAME=value` after `-s user` in the register line, run by you in your own terminal. To check a key is set, `list_providers` answers `env_set` true or false, never the value.

## Install

1. **Check the hash** (Trust box), then unzip to a stable place, keeping the layout. Rename any older `game-assets-mcp` folder there first.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip game-assets-mcp-1.0.6.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive game-assets-mcp-1.0.6.zip -DestinationPath $HOME\vibedna`

   You get `~/vibedna/game-assets-mcp` or `C:\Users\<you>\vibedna\game-assets-mcp`.

2. **Make a private Python environment** inside that folder.

   macOS/Linux:
   ```bash
   cd ~/vibedna/game-assets-mcp
   python3 -m venv .venv
   .venv/bin/python -m pip install -r vibe-game-assets-mcp/requirements.txt
   ```
   Windows PowerShell:
   ```powershell
   cd $HOME\vibedna\game-assets-mcp
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r vibe-game-assets-mcp\requirements.txt
   ```

3. **Register it in Claude Code** at user scope with full paths. To keep the library elsewhere, add `-e ASSET_FORGE_LIB=<full path>` after `-s user`.

   macOS/Linux:
   ```bash
   claude mcp add game-assets -s user -- "$HOME/vibedna/game-assets-mcp/.venv/bin/python" "$HOME/vibedna/game-assets-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add game-assets -s user -- "$HOME\vibedna\game-assets-mcp\.venv\Scripts\python.exe" "$HOME\vibedna\game-assets-mcp\server.py"
   ```

4. **Other MCP apps:** put the same command and args in that app's own MCP settings.
   ```json
   {"mcpServers": {"game-assets": {
     "command": "/home/<you>/vibedna/game-assets-mcp/.venv/bin/python",
     "args": ["/home/<you>/vibedna/game-assets-mcp/server.py"]}}}
   ```
   Windows command: `C:/Users/<you>/vibedna/game-assets-mcp/.venv/Scripts/python.exe` (forward slashes work in JSON).

5. **Coming from an earlier install:** an older guide may have had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`. That entry can keep an old copy running. Check with `claude mcp get game-assets`, then remove it (`claude mcp remove game-assets -s project` from that folder, or delete it from that file).

6. **Restart Claude Code:** close it and open a new session.

## Check it works

`claude mcp get game-assets` should show it connected. Then ask your AI to run `lanes_status`, which only reads and needs no key. A good answer shows `harvest` with `"loaded": true` and `"tool_count": 8`, and `generate` with `"loaded": true` and `"tool_count": 20`. A lane showing an error means folders were moved: unzip again.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and online at https://vibedna.ai/prompts/game-assets.md (that copy can change, so read it first).

## Uninstall

1. `claude mcp remove game-assets -s user`
2. Delete the unzipped folder (`~/vibedna/game-assets-mcp`), which holds `.venv`, `cache` and your `.env`.
3. To also remove the harvested packs: delete `~/.asset-forge`, or the folder you set as `ASSET_FORGE_LIB`.

Delete nothing else.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python too old:** check with `python3 --version` (Windows: `py --version`, or `python` if `py` is missing). Install 3.11 or newer, delete `.venv` and repeat step 2.
- **`ModuleNotFoundError`:** the server runs with another Python. `claude mcp get game-assets` must show the `.venv` one. If not, remove the entry and repeat step 3.
- **"FAL_KEY not set"** (or another key): add it as Keys says, then restart Claude Code.
- **Old tool list after updating:** an earlier entry is still registered. See step 5.

Support: `admin@vibedna.ai`
