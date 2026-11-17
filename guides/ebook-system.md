---
name: ebook-system-install
description: Install Ebook System, the Ebook Forge MCP server plus the system's start files, so your AI can write, audit and cover books on your own computer. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes and installs it. Keys go in the product's own .env file, never in the chat.
---

# Ebook System: Install Guide

This guide matches version 1.2.5.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` runs, list the 64 files, read `START-HERE.txt` at the root, then in `ebook-forge-mcp/` read `INSTALL.md`, `MANUAL.md`, `requirements.txt`, `server.py`, `license_gate.py` and the other `.py` files the install will run (in `audit/`, `writers/`, `critic/`, `covers/`, `storage/`, `audiobook/`, `shelfscout/`), and say in plain words what they do. Ask before anything is written. Never ask for a key in the chat, never open or print `.env`. Ask again before any tool that spends money, rewrites a book file or removes saved data.

## What it is

The Ebook Forge MCP server, which runs on your computer, plus the system's own start files. Your AI outlines and writes a book chapter by chapter with a critic pass, scores the text for machine-sounding prose, composes a cover, and checks the result against the store policy files in the zip. Audiobook narration is an optional extra. 94 tools; all but `license_status` and `check_for_update` need your licence key.

## Trust box

- **File:** `Ebook-System-1.2.5.zip`, 257,344 bytes, 64 files: three documents at the zip root, the server in `ebook-forge-mcp/`.
- **SHA-256:** `0ce33d2c902508304234604f8c11a637abf1971b20f2d15307d25138cd858aef`. Check before unzipping; stop if it differs. Linux: `sha256sum Ebook-System-1.2.5.zip`. macOS: `shasum -a 256 Ebook-System-1.2.5.zip`. Windows PowerShell: `Get-FileHash Ebook-System-1.2.5.zip`.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/Ebook-System-1.2.5.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents:** `INSTALL.md` in the zip (in `ebook-forge-mcp/`, like `MANUAL.md`) is this guide (the same text as https://vibedna.ai/installs/ebook-system.md without the zip's own size and checksum; if they ever differ, follow the online one). `MANUAL.md` is the product's own older document, kept for what this guide does not repeat (each key in detail, the first book, the audiobook flow). Where it shows another way to install (a plain `pip install`, a settings entry written by hand), follow this guide. At the root: `START-HERE.txt` (a pointer to the parts), `START_PROMPT.md` and `publish-ebooks-on-autopilot.md` (the field journal, reading only). In `ebook-forge-mcp/`: `README.md`, `workflow.md` (the order of work), `shelfscout/README.md`, 12 templates in `genres/`, and three `skills/*/SKILL.md` instruction files: one for a writing session, two on filling Draft2Digital and KDP forms with a separate browser tool, which this server never does.
- **Dependencies:** 5, pinned to tested versions (exact, or a range below the next major version where the tested one needs a newer Python): `fastmcp>=0.4.0,<5`, `anthropic==2.8.0`, `python-dotenv==1.2.4`, `Pillow>=10.0.0,<14`, `requests==2.34.2`.
- **Settings it reads** (from `.env` in its folder, or the environment): `MCPIZE_LICENSE_KEY` (required; an older name the setting keeps, it holds your Vibedna licence key). Optional: `ANTHROPIC_API_KEY`; for covers `GEMINI_API_KEY`, `FAL_KEY`, `EBOOK_FONT_DIR`; for the niche scout `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `NICHE_JESTER_PATH`, `SHELFSCOUT_PATH`; for audiobooks `ELEVENLABS_API_KEY`, `ELEVENLABS_CHUNK_CHARS`, `ELEVENLABS_USD_PER_1K_CHARS`, `FFMPEG_BIN`, `FFPROBE_BIN`, `AUDIOBOOK_SSH_HOST`, `AUDIOBOOK_BOX_SCRIPTS`, `AUDIOBOOK_BOX_WORK`, `AUDIOBOOK_BOX_PY`; and `VIBEDNA_HOME`, `VIBEDNA_SITE`, `VIBEDNA_PRODUCT_SLUG`, `VIBEDNA_PRODUCT_NAME`.
- **Files it writes:** in the unzipped folder, `.env` (made by you), `.venv/`, Python's `__pycache__` folders and your saved data in `storage/` (`learning.db`, `imprints.json`, `pen_names.json`, `profiles.json`). In each book folder you name: `outline.json`, `_state.json`, `book.md`, `audit_summary.json`, `POLISH_REPORT.md`, `INTEGRITY_REPORT.md`, the cover JPEG with its `_bg.jpg`, and an `audiobook/` subfolder. In your home folder: `~/.vibedna/license_permits.json` (the signed licence permit and when it was last asked; it holds a short hash of your key, never the key itself; under `VIBEDNA_HOME` if set).
- **Network:** vibedna.ai for the licence check (sends your licence key, the product name and a 16 character machine id, a one-way hash made from the computer's name, system and network card number that cannot be read back; the site answers with a signed permit, asked again when a tool checks the key and the last answer is over 12 hours old; offline the tools keep working until the permit expires, about three days on a subscription key and about a year on a key bought once) and for `check_for_update` (asks for a version number; `VIBEDNA_SITE` would move that one call, leave it unset). The Anthropic API, through the `anthropic` package, when a tool writes, critiques or proposes niches. generativelanguage.googleapis.com or queue.fal.run, plus the image link fal returns, only on `generate_cover`. api.elevenlabs.io only for the ElevenLabs audiobook tools. `ssh` and `scp` to the machine in `AUDIOBOOK_SSH_HOST`, run by `make_audiobook`, `audiobook_status` and `audiobook_fetch`. completion.amazon.com and, with an Exa key, api.exa.ai, only on `pipeline_propose_niches` (and Google Trends, only if `pytrends` from the scout's requirements is installed in the same `.venv`). That tool only checks that `FIRECRAWL_API_KEY` or `NICHE_JESTER_PATH` is set: it never calls Firecrawl and never loads what `NICHE_JESTER_PATH` points at. pypi.org once, by `pip`, at install.
- **Optional second server, not installed by this guide:** `shelfscout/` is the niche scout. `pipeline_propose_niches` loads two of its functions; its own tools exist only if you register `shelfscout/server.py` yourself. Only then does it call www.reddit.com, api.firecrawl.dev, www.amazon.com and seven other Amazon country sites, images-na.ssl-images-amazon.com and www.audible.com, write `~/.claude/shelfscout/index.db` and a `benchmark/` folder where you name it, and need `shelfscout/requirements.txt`, where every line has a version or a range (`pytrends`, which calls Google Trends, is held below its next major version: `pytrends>=4.9.2,<5`). Its Exa and Firecrawl keys then go in `shelfscout/.env`, which that server loads at start, before it reads them. Make that file from `shelfscout/.env.example` and replace both placeholder values or delete their lines: a placeholder left in is sent to Exa or Firecrawl as if it were a key. Keys passed as `-e NAME=value` in a register line keep working and come first. With the second server registered, the Firecrawl key and the reader at `NICHE_JESTER_PATH` are used by its page-reading tools; that reader is a Python file in the folder you name, outside this zip, and it runs as code, so set the path only to a folder you trust.
- **Never:** it does not log in to, upload to or publish on any store.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. These tools spend money on your own accounts: the writing, critique and niche tools in their default API mode (Anthropic), `generate_cover` (Google or fal), `audiobook_preview_voice` (at once, a short sample) and `audiobook_narrate_byok` (shows the cost, waits for `confirm=True`). `make_audiobook` runs `sudo systemd-run` on your own machine over ssh and expects a narration script that is not in the zip. `apply_polish_fixes` rewrites `book.md` in place; `delete_profile`, `deactivate_imprint`, `deactivate_lesson` and the rename tools change saved data. Your AI asks before each. `license_status` shows only the last 4 characters of your key in the chat. Neither `server.py` nor `shelfscout/server.py` loads code from outside the unzipped folder at start.

## Keys

Every key of this server goes in `.env` inside `ebook-forge-mcp/`, which `server.py` loads itself: none in the chat, none in the register command. Your AI names the line; you paste the value in your own editor.

- `MCPIZE_LICENSE_KEY` (required): starts with `vbd_`, from your purchase email (with a membership: the email that welcomed you to the plan).
- `ANTHROPIC_API_KEY` (optional): for the tools that write or critique through the API, billed to your own account. Without it, `start_book` with `writer_mode="session"` has the AI in your chat write.
- The other optional keys (covers, niche scout, audiobooks): `MANUAL.md`, "Before you start".

## Install

Needs Python 3.10 or newer, and ffmpeg only for audiobooks.

1. Check the hash, then unzip into a new folder with a stable path.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip Ebook-System-1.2.5.zip -d ~/vibedna/ebook-system
   cd ~/vibedna/ebook-system/ebook-forge-mcp
   ```
   Windows PowerShell:
   ```powershell
   Expand-Archive Ebook-System-1.2.5.zip -DestinationPath "$env:USERPROFILE\vibedna\ebook-system"
   cd "$env:USERPROFILE\vibedna\ebook-system\ebook-forge-mcp"
   ```

   Now your AI reads the files (the note at the top) and tells you what they do. After your yes, in that same folder:

   macOS/Linux:
   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell:
   ```powershell
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Make the key file: `cp .env.example .env` (Windows: `Copy-Item .env.example .env`), then fill it in as "Keys" says.

3. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add ebook-forge -s user -- "$HOME/vibedna/ebook-system/ebook-forge-mcp/.venv/bin/python" "$HOME/vibedna/ebook-system/ebook-forge-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add ebook-forge -s user -- "$env:USERPROFILE\vibedna\ebook-system\ebook-forge-mcp\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\ebook-system\ebook-forge-mcp\server.py"
   ```

4. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "ebook-forge": {
       "command": "<full path>/ebook-forge-mcp/.venv/bin/python",
       "args": ["<full path>/ebook-forge-mcp/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

5. Coming from an earlier install: `MANUAL.md` and `README.md` had you write the entry by hand in a `.mcp.json` file, and that entry can keep an old copy running. Check with `claude mcp get ebook-forge`, remove the old entry (`claude mcp remove ebook-forge -s project` from that folder, or delete it from that file).

6. Restart Claude Code: close it and open a new session.

## Check it works

`claude mcp get ebook-forge` shows it connected. Then ask your AI to call `license_status`, which works without a licence and touches no book. With no key set, a good answer has `"licensed": false` and `"key_present": false`. With a valid key it asks vibedna.ai and answers `"licensed": true`.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and at https://vibedna.ai/prompts/ebook-system.md. Its first prompt repeats the install: skip what this guide already did. The scout tools it names (`scout_niche`, `category_gate_check` and others) exist only with the optional second server of the trust box, which it asks to wire: your choice.

## Uninstall

1. `claude mcp remove ebook-forge -s user`
2. Copy out what you want to keep from `storage/` (the four data files).
3. Delete the unzipped `ebook-system` folder and `~/.vibedna/license_permits.json` (in the `VIBEDNA_HOME` folder if you set it; with `license_cache.json` beside it if an earlier version left one). If you registered the scout yourself, also its entry, `~/.claude/shelfscout/` and any `benchmark/` folder it made. The book folders you named hold your books and covers: keep or delete them yourself. Nothing else was written.

## If something fails

- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** install a current one, delete `.venv`, repeat step 1.
- **A tool answers with a purchase link:** `MCPIZE_LICENSE_KEY` is missing or mistyped in `.env`. Fix the line, restart, call `license_status`.
- **"ANTHROPIC_API_KEY not set":** fill that line in `.env` and restart, or use the session mode named under Keys.
- **Old tools or an old path still show:** an earlier entry is still registered. See step 5.
