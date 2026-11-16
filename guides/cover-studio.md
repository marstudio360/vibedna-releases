---
name: cover-studio-install
description: Install Cover Studio MCP, which lets your AI drive a cover studio that runs on your own computer. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes and installs it. You start the studio and run the register line yourself, so neither the studio token nor your licence key passes through the chat.
---

# Cover Studio MCP: Install Guide

This guide matches version 1.1.6.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` runs, list the 14 files and read them all: `START-HERE.md`; in `mcp/`, `INSTALL.md`, `MANUAL.md`, `START_PROMPT.md`, `requirements.txt`, `server.py` and `license_gate.py`; in `server/`, `requirements.txt` and the six `.py` files the studio runs (`cover_editor_api.py`, `cover_gen.py`, `cover_gen_pro.py`, `cover_styles.py`, `cover_fx.py`, `cover_filters.py`). Say in plain words what they do. Ask before anything is written. Never ask for the token or the licence key in the chat. Ask again before `add_cover_effect` (it stores Python code that the studio then runs), `add_font` (it downloads a file), `delete_cover_effect` and any tool that changes a project.

## What it is

Two parts, both on your own computer. The studio (`server/`) is a small web service that composes square covers from your art, text layers, style presets, print finishes and code-drawn art; it calls no image service. The MCP server (`mcp/server.py`, 21 tools, every one locked without your licence key) lets your AI drive it: open projects, apply a preset or a finish, generate art, render the 3000x3000 master. It imports nothing from `server/`: it reaches the studio over HTTP at `COVER_STUDIO_URL`.

## Trust box

- **File:** `cover-studio-mcp-1.1.6.zip`, 77,761 bytes, 14 files: `START-HERE.md` at the root, the MCP server and its licence check (`license_gate.py`) in `mcp/`, the studio's code in `server/`.
- **SHA-256:** `b17231fe49fda084606166f07f62dd9e0ae018948a499f148c6938fa0117568a`. Check before unzipping; stop if it differs. Linux: `sha256sum cover-studio-mcp-1.1.6.zip`. macOS: `shasum -a 256 cover-studio-mcp-1.1.6.zip`. Windows PowerShell: `Get-FileHash cover-studio-mcp-1.1.6.zip`.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/cover-studio-mcp-1.1.6.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents:** `INSTALL.md` in the zip (in `mcp/`, like `MANUAL.md`) is this guide (the same text as https://vibedna.ai/installs/cover-studio.md without the zip's own size and checksum; if they ever differ, follow the online one). `MANUAL.md` is the product's own older document, kept for what this guide does not repeat (the tool list, how a custom effect is written, the optional studio settings). Where it shows another way to install (a plain `pip install`, a settings entry written by hand with the token in it), follow this guide. `START-HERE.md` is a short start note.
- **Dependencies:** the MCP server has 1, pinned to the exact tested version: `mcp==1.30.0`; the licence check (`license_gate.py`) uses only Python's standard library. The studio has 2, in `server/requirements.txt`, given as ranges that stop before the next major version, not as exact pins: `Pillow>=10.0.0,<13` and `numpy>=1.26,<3`. So `pip` installs the newest release inside each range; tested with Pillow 12.3.0 and numpy 2.5.5.
- **Settings it reads:** MCP server: `COVER_STUDIO_TOKEN` and `MCPIZE_LICENSE_KEY` (both required) and, optional, `COVER_STUDIO_URL` (default `http://127.0.0.1:8798`) and `VIBEDNA_HOME` (moves the licence permit file; `license_gate.py` also reads `VIBEDNA_PRODUCT_SLUG` and `VIBEDNA_PRODUCT_NAME`, which change nothing in this product). Studio: `COVER_EDITOR_TOKEN` (required, it refuses to start without it) and, optional, `COVER_STUDIO_HOME`, `COVER_EDITOR_PORT`, `COVER_EDITOR_HOST`, `COVER_STUDIO_FONTS`, `COVER_STUDIO_LOGO`, `COVER_GEN_CACHE`.
- **Files it writes:** the studio keeps its data under `~/.cover-studio/` (or `COVER_STUDIO_HOME`): `projects/` with `_history/`, `art/`, `renders/`, `thumb_cache/`, `fonts/`, `gen_cache/` (or `COVER_GEN_CACHE`), `custom_fx.json`, `custom_fonts.json`. The MCP server writes on `export_art` (into `~/.cover-studio/art/`, or to the `out_path` you name) and `~/.vibedna/license_permits.json` (under `VIBEDNA_HOME` if set), for the licence: the signed permit and when it was last asked, not the key itself (the permit holds only a short hash of it); owner-only on macOS and Linux. In the unzipped folder: `.venv/` and Python's `__pycache__` folders. The studio's editor page keeps the token in your browser's storage if you open it with `?token=`.
- **Network:** the MCP server calls the studio at `COVER_STUDIO_URL`, with the token in a header (and in the address on `export_art`). Its one other call is the licence check, to vibedna.ai: an HTTPS POST to `https://vibedna.ai/api/license/validate` with your licence key, the product name (`cover-studio`) and a 16-character machine id (a one-way hash of the computer's name, system and network card number; it cannot be read back), and nothing else: nothing about your covers or projects. It is made on the first tool call, then again on a tool call once 12 hours have passed, while the machine is online. With no key set, or one that does not start with `vbd_`, no call is made and the tools stay locked. The site answers with a signed permit, which `license_gate.py` checks with the public key it carries. Offline, the tools keep working until the permit expires: the site sets that, about three days for a membership key, about a year for a key bought once. The studio listens on port 8798 on this computer only (`127.0.0.1`), over plain HTTP, unless you start it with `COVER_EDITOR_HOST=0.0.0.0`, which opens it to your network; its one outgoing call is `add_font`, which downloads the address you give. It answers without the token only on `/` and `/studio` (its editor page) and `/health` (counts of projects, art and fonts). pypi.org is contacted once, by `pip`, at install.
- **Never:** it logs in to no account, publishes nothing and takes no payment. The one key it reads is your licence key, sent only to vibedna.ai to check it.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. The real risk is the studio. `add_cover_effect` stores Python code, and the studio runs it with your user's rights and no sandbox: once as a trial when it is added, then on every preview or render that uses it. The studio answers only on this computer, so what can reach it is a program running here that has the token. If you start it with `COVER_EDITOR_HOST=0.0.0.0`, anyone on your network who has the token can do the same. So choose a long random token, leave `COVER_EDITOR_HOST` unset unless you need another machine to reach the studio, never expose it to the internet, and have your AI show you an effect's code before adding it. `apply_preset` rebuilds a project's layers, `render_cover` replaces that project's earlier render, and `export_art` overwrites the file at the path you name.

## Keys

Two values, both typed by you in your own terminal, never in the chat:

- `MCPIZE_LICENSE_KEY` (required): your Vibedna licence key, it starts with `vbd_`. Cover Studio is not sold on its own: it comes with the AI Music Label System, whose buyers get one key per tool in their purchase email from Vibedna, and with the Ultra membership, whose key is in the email that welcomed you to the plan and works while the plan is active. Every tool needs it. The server reads no `.env` file, so the key goes in the register line as `-e MCPIZE_LICENSE_KEY=...` (step 3).
- The studio token, made by you: a long random string (40 or more letters and digits), not an account key. It goes in two places that must hold the same value: `COVER_EDITOR_TOKEN` when you start the studio (step 2) and `-e COVER_STUDIO_TOKEN=...` in the register line (step 3).

## Install

Needs Python 3.10 or newer.

1. Check the hash, then unzip into a new folder with a stable path.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip cover-studio-mcp-1.1.6.zip -d ~/vibedna/cover-studio
   cd ~/vibedna/cover-studio/mcp
   ```
   Windows PowerShell:
   ```powershell
   Expand-Archive cover-studio-mcp-1.1.6.zip -DestinationPath "$env:USERPROFILE\vibedna\cover-studio"
   cd "$env:USERPROFILE\vibedna\cover-studio\mcp"
   ```

   Now your AI reads the files (the note at the top) and tells you what they do. After your yes, in that same folder (the last line is for the studio):

   macOS/Linux:
   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m pip install -r ../server/requirements.txt
   ```
   Windows PowerShell:
   ```powershell
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m pip install -r ..\server\requirements.txt
   ```

2. You, in your own terminal, in that folder: start the studio and leave the window open.

   macOS/Linux:
   ```bash
   export COVER_EDITOR_TOKEN=YOUR_TOKEN
   .venv/bin/python ../server/cover_editor_api.py
   ```
   Windows PowerShell:
   ```powershell
   $env:COVER_EDITOR_TOKEN = "YOUR_TOKEN"
   .venv\Scripts\python.exe ..\server\cover_editor_api.py
   ```
   It prints `COVER EDITOR API on 127.0.0.1:8798`. It does not start by itself: run these two lines again after a reboot.

3. You, in your own terminal: register the MCP server in Claude Code at user scope, with full paths, the same token and your licence key in place of `YOUR_LICENCE_KEY`.

   macOS/Linux:
   ```bash
   claude mcp add cover-studio -s user -e COVER_STUDIO_TOKEN=YOUR_TOKEN -e MCPIZE_LICENSE_KEY=YOUR_LICENCE_KEY -- "$HOME/vibedna/cover-studio/mcp/.venv/bin/python" "$HOME/vibedna/cover-studio/mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add cover-studio -s user -e COVER_STUDIO_TOKEN=YOUR_TOKEN -e MCPIZE_LICENSE_KEY=YOUR_LICENCE_KEY "--" "$env:USERPROFILE\vibedna\cover-studio\mcp\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\cover-studio\mcp\server.py"
   ```
   On Windows keep the quotes around `--` (PowerShell can drop it and the line fails). The line stays in your shell history, and Claude Code stores the token and the key as plain text.

4. Other MCP apps, in their MCP settings, with the token and the key typed by you:
   ```json
   { "mcpServers": { "cover-studio": {
       "command": "<full path>/cover-studio/mcp/.venv/bin/python",
       "args": ["<full path>/cover-studio/mcp/server.py"],
       "env": { "COVER_STUDIO_TOKEN": "", "MCPIZE_LICENSE_KEY": "" } } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

5. Coming from an earlier install: earlier versions had the studio listen on every network interface, and this one listens on this computer only, so stop the old studio and start this one (step 2). `MANUAL.md` and `START-HERE.md` had you write the entry by hand in a `.mcp.json` file with the system `python`, and that entry can keep an old copy running. Check with `claude mcp get cover-studio`, then remove the old entry (`claude mcp remove cover-studio -s project` from that folder, or delete it from that file).

6. Restart Claude Code: close it and open a new session.

## Check it works

1. `claude mcp get cover-studio` shows it connected.
2. Ask your AI to call `generate_art` with `family` set to `flow` and no project id. It needs your licence key, but no studio token and no running studio, and changes no project. A good answer is `{"ok": true, "ref": "gen:flow?seed=7", "applied": false}`. Without a valid key every tool answers with an error that says `Cover Studio needs a valid licence key, and this copy has none the site accepts.` and where to put the key.
3. With the studio running, `list_presets` returns a `presets` list, each entry with an `id` and a `what`.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md`, next to `INSTALL.md`, and at https://vibedna.ai/prompts/cover-studio.md.

## Uninstall

1. Stop the studio (Ctrl+C in its window).
2. `claude mcp remove cover-studio -s user`
3. Copy out what you want to keep, then delete `~/.cover-studio/` and, if you set them, the `COVER_STUDIO_HOME` and `COVER_GEN_CACHE` folders: your projects, art, renders, fonts and effects.
4. Delete the unzipped `cover-studio` folder and any file `export_art` saved to an `out_path` elsewhere. If you opened the editor page with `?token=`, clear that site's data in your browser. Remove `~/.vibedna/license_permits.json` (in the `VIBEDNA_HOME` folder if you set it) unless another Vibedna tool still uses it. Nothing else was written.

## If something fails

- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **A tool answers "Cover Studio needs a valid licence key":** the register line has no `MCPIZE_LICENSE_KEY`, the key is mistyped, the site does not accept it (for a membership key: the plan has ended), or the first check could not reach vibedna.ai. Run `claude mcp remove cover-studio -s user`, repeat step 3 yourself, restart.
- **A tool answers with an `error` about a refused connection:** the studio is not running. Do step 2.
- **A tool answers `http 403` with "bad token":** the two tokens differ, or the entry has none. Run `claude mcp remove cover-studio -s user`, repeat step 3 yourself, restart.
- **The studio stops as soon as it starts:** "COVER_EDITOR_TOKEN is not set" means the variable is missing in that terminal; "No module named" `PIL` or `numpy` means the last install line of step 1 did not run.
- **Old tools or an old path still show:** an earlier entry is still registered. See step 5.
