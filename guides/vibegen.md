---
name: vibegen-mcp-install
description: Install the VibeGen MCP, which lets your AI drive the Vibedna generative art studio. Paste this file into your AI chat and ask it to install it. Your AI checks the download, reads the code, and after your yes installs it in its own virtual environment with one register command. Your token never goes in the chat.
---

# VibeGen MCP: Install Guide

This guide matches version 1.1.3.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `MANUAL.md`, `requirements.txt` and `server.py` and say in plain words what they do before installing anything. `INSTALL.md` in the zip is this guide. `MANUAL.md` is the product's own older document, kept in the zip for what this guide does not repeat (settings, the live view, the tool reference). Ask before anything is written. Never ask for a token or password in the chat, and never print one.

## What it is

A small Python MCP server that connects your AI to VibeGen, the generative art studio of Vibedna. Your AI can read the live canvas, switch engines, move sliders, save presets, rewrite an engine's code, and render a PNG, an MP4 or an MP4 that moves to your song. It has 17 tools.

## Trust box

- **File:** `vibegen-mcp-1.1.3.zip`, 18,389 bytes, 5 files, with no top folder inside: unzip into a new folder.
- **SHA-256:** `44b85c622a4e7347975bb5969d085646cbfe75009ed393a6d71d8226088172f4`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum vibegen-mcp-1.1.3.zip`
  - macOS: `shasum -a 256 vibegen-mcp-1.1.3.zip`
  - Windows PowerShell: `Get-FileHash vibegen-mcp-1.1.3.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/vibegen-mcp-1.1.3.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The full code of this version is public there, in `source/vibegen/`: it can be read before anything is downloaded.
- **Dependencies, held to tested versions (exact, or a range where shown):** `fastmcp>=3.2.0,<5`, `requests==2.34.2`. Optional, not pinned: Playwright 1.45 or newer, only for `list_catalog` and the render tools; it downloads Chromium. Where the version we tested needs a Python newer than 3.10, the library is held below its next major version instead of one exact version, so an older Python still gets a build that fits.
- **Settings it reads from the environment:** `STUDIO_URL` (the studio to drive, default `http://localhost:3000`), `STUDIO_TOKEN` (optional), and the optional render settings `STUDIO_CHROME_ARGS` and `STUDIO_RENDER_TIMEOUT`.
- **Files it writes:** nothing in your home folder. It writes a file only at a path you pass to a tool (`save_to`, `out_path`). Presets and engine code are saved by the studio, through its API.
- **Network:** the address in `STUDIO_URL`, for every tool except `vibedna_info`; your token, if set, goes with each request as the `x-studio-token` header. vibedna.ai for `check_for_update`, which asks for a version number. The render tools open `<STUDIO_URL>/embed` in a headless browser on your machine and hand it the song or picture you name. No other address is called.
- **Never:** no licence check or telemetry code was found, and it reads only the song or picture whose path you pass.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. The studio's own code is not in the zip, so what the studio does with a request, a song or a picture cannot be checked here (the zip's `MANUAL.md` says rendering happens on your GPU). Your token is sent to whatever `STUDIO_URL` names: point it only at a studio you trust. `write_engine_source` replaces an engine's whole source file in the studio.

## Keys

One, and it is optional: `STUDIO_TOKEN`, your subscription token. Per the zip, with no token you can read the canvas and move every engine and slider; rewriting engines and rendering from the hosted studio need an Ultra token, and a studio you run yourself needs none. Subscribers get the token at vibedna.ai/studio ("Set up in your AI"); if that page hands you a file with the token inside, keep it out of the chat. You add the token yourself with `-e` in the register command (step 2), typed in your own terminal.

## Install

Needs Python 3.10 or newer and a studio to drive: the hosted one at `https://studio.vibedna.ai`, or one you run yourself.

1. Get the zip (https://vibedna.ai/api/free-download?slug=vibegen), check the hash, unzip into a new folder with a stable path, install into a virtual environment.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip vibegen-mcp-1.1.3.zip -d ~/vibedna/vibegen
   cd ~/vibedna/vibegen
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive vibegen-mcp-1.1.3.zip -DestinationPath "$env:USERPROFILE\vibedna\vibegen"
   cd "$env:USERPROFILE\vibedna\vibegen"
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
   Only for the render tools, after a yes to the browser download: `.venv/bin/python -m pip install playwright`, then `.venv/bin/python -m playwright install chromium` (Windows: `.venv\Scripts\python.exe`).

2. Register it in Claude Code at user scope, with full paths. This drives the hosted studio; leave out `-e STUDIO_URL=...` for a studio on `http://localhost:3000`.

   macOS/Linux:
   ```bash
   claude mcp add vibegen -s user -e STUDIO_URL=https://studio.vibedna.ai -- "$HOME/vibedna/vibegen/.venv/bin/python" "$HOME/vibedna/vibegen/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add vibegen -s user -e STUDIO_URL=https://studio.vibedna.ai -- "$env:USERPROFILE\vibedna\vibegen\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\vibegen\server.py"
   ```
   With a token, run the same line yourself in your own terminal with `-e STUDIO_TOKEN=<your token>` added before the `--`, so it never passes through the chat. If already registered, run `claude mcp remove vibegen -s user` first.

3. Other MCP apps: the same command, args and env in the app's MCP settings.
   ```json
   { "mcpServers": { "vibegen": {
       "command": "<full path>/vibegen/.venv/bin/python",
       "args": ["<full path>/vibegen/server.py"],
       "env": { "STUDIO_URL": "https://studio.vibedna.ai" } } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

4. Coming from an earlier install: older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get vibegen`, remove the old entry (`claude mcp remove vibegen -s project` from that folder, or delete it from that file), then restart. Steps 1 and 2 replace the install steps in the zip's `MANUAL.md`.

5. Restart Claude Code: close it and open a new session.

## Check it works

`claude mcp get vibegen` shows it connected. Then ask your AI to call `vibedna_info`, which needs no token and makes no network call. A good answer names `studio-mcp`, version `1.1.3`, the `studio_url` you set and 16 tools (it leaves itself out). Then `get_state` reads the canvas; "Cannot reach studio" means `STUDIO_URL` is wrong or the studio is not running.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and at https://vibedna.ai/prompts/vibegen.md.

## Uninstall

Run `claude mcp remove vibegen -s user` and delete the unzipped folder. The product has no data folder of its own. Delete nothing else.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **"No module named fastmcp":** the entry points at another Python. Register again with the `.venv` one.
- **401, or "needs an Ultra license":** the studio wants a token. Add `STUDIO_TOKEN` yourself (step 2).
- **Old tools still show:** an earlier entry is still registered. See step 4.
