---
name: content-studio-install
description: Install the Content Studio MCP of Vibedna Motion DNA, which lets your AI render on-brand posts, carousels and reels as files from chat. Paste this file into your AI chat and ask it to install it. Your AI checks the download, reads the code, and after your yes installs it in its own virtual environment with one register command. Keys never go in the chat.
---

# Motion DNA Content Studio MCP: Install Guide

This guide matches version 1.3.8.

This file is the install guide as published at https://vibedna.ai/installs/content-studio.md, without the zip's own size and checksum: a file cannot carry the checksum of the zip it sits in. Both are in the online guide and in the public record at https://github.com/marstudio360/vibedna-releases.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `MANUAL.md`, `requirements.txt` and `server.py` and say in plain words what they do before installing anything. `INSTALL.md` in the zip is this guide. `MANUAL.md` is the product's own older document, kept in the zip for what this guide does not repeat (the templates, your own templates, the tools, feeding a poster). Ask before anything is written. Never ask for a key or password in the chat, and never print one.

## What it is

A Python MCP server that runs on your computer. It draws posts, carousels, stories, reels and thumbnails by code, with no image model, and returns the file paths. It has 42 tools. It makes files and posts nothing. New in this version: `campaign_render` draws every piece of a Motion DNA campaign on your machine (reels as video, posts as images) and writes the calendar file a poster reads.

The free tier renders at 1080px with a small badge. A Pro key removes the badge and unlocks reels and video, custom fonts and custom effects (the zip's `MANUAL.md` lists Pro at $19/mo; check current plans at https://vibedna.ai/content-studio). The package keeps earlier names: type `post-engine` and `CONTENT_STUDIO_LICENSE` exactly as shown.

## Trust box

- **File:** `social-content-studio-mcp-1.3.8.zip`, size in the online guide, 11 files, with no top folder inside: unzip into a new folder.
- **SHA-256:** `not printed inside the zip, see the online guide`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum social-content-studio-mcp-1.3.8.zip`
  - macOS: `shasum -a 256 social-content-studio-mcp-1.3.8.zip`
  - Windows PowerShell: `Get-FileHash social-content-studio-mcp-1.3.8.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/social-content-studio-mcp-1.3.8.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The full code of this version is public there, in `source/content-studio/`: it can be read before anything is downloaded.
- **Dependencies, held to tested versions (exact, or a range where shown):** `mcp==1.30.0`, `Pillow>=10.0.0,<14`. Optional, not in the requirements file: ffmpeg (reels, video) and Playwright (generative backgrounds, `studio_render_video`, `campaign_render`; a reel is encoded by Google Chrome when it is installed, or by the browser named in `STUDIO_RENDER_BROWSER`). Where the version we tested needs a Python newer than 3.10, the library is held below its next major version instead of one exact version, so an older Python still gets a build that fits.
- **Settings it reads from the environment, all optional:** `CONTENT_STUDIO_LICENSE` (Pro key); `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`, `PIXABAY_API_KEY` (stock photos); `MOTION_DNA_KEY` (read in place of the Pro key by the campaign tool, when set); `STUDIO_URL`, `STUDIO_TOKEN`, `STUDIO_RENDER_URL`, `STUDIO_RENDER_BROWSER` (a hosted web editor and the browser that renders); folder overrides `POST_ENGINE_OUT`, `POST_ENGINE_FONTS`, `POST_ENGINE_LIBRARY`, `POST_ENGINE_EFFECTS`, `CONTENT_STUDIO_HOME`; `FFMPEG_BIN`, `FFPROBE_BIN`.
- **Files it writes:** `~/.post-engine/` (renders in `out/`, created at start; fonts, image library, `effects.py`), `~/.content-studio/` (your brands and templates), and any output path you pass to a tool.
- **Network:** vibedna.ai for `check_for_update` (asks for a version number), sample photos, the `studio_*` tools (with your `STUDIO_TOKEN`) and, only when a Pro key is set, the licence check, which sends that key. `campaign_render` and `studio_render_video` read your own pieces from vibedna.ai/api/motion/v1 and send that same key in a header to do it; the page that draws them is vibedna.ai/studio-render, opened in a browser with no window. api.openverse.org for stock photos without a key; api.pexels.com, api.unsplash.com and pixabay.com only with your own key. studio.vibedna.ai for generative backgrounds, through Playwright. Any image or font address you give a tool.
- **Never:** no code was found that posts to a social account. It reads system fonts and files whose path you pass.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. What vibedna.ai does with a request cannot be checked from the zip.

- `add_effect` (Pro) saves Python your AI writes into `~/.post-engine/effects.py` and runs it on renders. It is checked first (no other imports, no file, network or system access), but treat it as code running on your machine.
- The licence key is sent to the address in `STUDIO_URL` (vibedna.ai by default): leave `STUDIO_URL` unset unless you run your own editor.
- `POST_ENGINE_BOX_SSH` makes the batch video tool run over ssh on a machine you name: leave it unset.

## Keys

The free tier needs no key. Optional: the Pro key (`CONTENT_STUDIO_LICENSE`, from your purchase email or vibedna.ai/library) and the stock photo keys. The server reads keys only from its environment. You put them there yourself with `-e` in the register command (step 2), typed in your own terminal, or in your MCP app's settings file. Never in the chat.

## Install

Needs Python 3.10 or newer.

1. Check the hash, unzip into a new folder with a stable path, install into a virtual environment.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip social-content-studio-mcp-1.3.8.zip -d ~/vibedna/content-studio
   cd ~/vibedna/content-studio
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive social-content-studio-mcp-1.3.8.zip -DestinationPath "$env:USERPROFILE\vibedna\content-studio"
   cd "$env:USERPROFILE\vibedna\content-studio"
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add post-engine -s user -- "$HOME/vibedna/content-studio/.venv/bin/python" "$HOME/vibedna/content-studio/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add post-engine -s user -- "$env:USERPROFILE\vibedna\content-studio\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\content-studio\server.py"
   ```
   With a Pro key, run the same line yourself in your own terminal with `-e CONTENT_STUDIO_LICENSE=<your key>` right after `-s user`, so the key never passes through the chat. If it is already registered, run `claude mcp remove post-engine -s user` first.

3. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "post-engine": {
       "command": "<full path>/content-studio/.venv/bin/python",
       "args": ["<full path>/content-studio/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

4. Coming from an earlier install: older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get post-engine`, remove the old entry (`claude mcp remove post-engine -s project` from that folder, or delete it from that file), then restart. Steps 1 and 2 replace the plain `pip install` and the hand-written settings entry in the zip's `MANUAL.md`.

5. Restart Claude Code: close it and open a new session.

## Check it works

`claude mcp get post-engine` shows it connected. Then ask your AI to call `list_templates`, which needs no key and only reads. A good answer is a JSON list of templates such as `editorial-quote` and `quote-card`, each with its fields. For a first image, `render_template("editorial-quote", {"quote": "Hello"})` writes one file into `~/.post-engine/out/`.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and at https://vibedna.ai/prompts/content-studio.md. The file holds two prompts: Prompt 2 is the one for this MCP.

## Uninstall

Run `claude mcp remove post-engine -s user`, delete the unzipped folder, then `~/.post-engine/` (renders, fonts, effects) and `~/.content-studio/` (brands, templates). Delete nothing else.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **"No module named mcp" or "PIL":** the entry points at another Python. Register again with the `.venv` Python.
- **A Pro tool answers with how to subscribe:** the key is not in the entry. Add it again with `-e` (step 2).
- **Old tools still show:** an earlier entry is still registered. See step 4.
