---
name: godot-install
description: Install the Vibedna Godot Vibe MCP. Paste this file into your AI chat and ask it to install: it checks the download hash, reads the bundled files and tells you what they do, and after your yes installs into a private virtual environment and registers the server in Claude Code at user scope.
---

# Godot Vibe MCP: Install Guide

This guide matches version 1.1.4.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `requirements.txt` and `server.py` in the folder and say in plain words what they do before installing anything. Ask before anything is written. Never ask for a key or password in the chat (this tool needs none). The `INSTALL.md` inside the zip still describes an older manual way (plain `pip`, a hand-written settings entry): where it differs, follow this guide.

## What it is

A Python MCP server that runs on your machine and gives your AI 48 tools for Godot 4 games. It creates a project, writes scenes, scripts and shaders in Godot 4 syntax, drops in ready systems (inventory, dialogue, quests, battles, saving), checks GDScript for Godot 3 habits and, if Godot 4 is installed, boots the game and reads its errors. Needs Python 3.10 or newer. Godot itself is optional and not in the zip.

## Trust box

- **File:** `godot-vibe-mcp-1.1.4.zip`, 60,581 bytes, 5 files (`INSTALL.md`, `README.md`, `START_PROMPT.md`, `requirements.txt`, `server.py`).
- **SHA-256:** `5ac75720168fce5eaecf73935330910303729f6ac8a3083139c1e6c335dd8d8a`
  - Linux: `sha256sum godot-vibe-mcp-1.1.4.zip`
  - macOS: `shasum -a 256 godot-vibe-mcp-1.1.4.zip`
  - Windows PowerShell: `Get-FileHash godot-vibe-mcp-1.1.4.zip` (prints capitals, same value)
  - Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/godot-vibe-mcp-1.1.4.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Dependencies,** pinned to the exact versions tested: `fastmcp==3.4.11`, `mcp==1.30.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`. Not included: Pillow, which only `run_and_screenshot` (Windows only) and the slicing and upscaling options of `import_asset_pack` ask for.
- **Reads from the environment:** `GODOT_BIN` (optional, full path to your Godot 4 executable), and a `.env` file in its folder or a parent folder if one exists. Leave `PORT` unset: with it the server listens over HTTP on all network interfaces instead of talking only to your AI app.
- **Writes:** an empty `data` folder inside the unzipped folder; game files inside the project folders you name (`project.godot`, scenes, scripts, shaders, assets, `export_presets.cfg`); a screenshot where you ask for one; a temporary folder during `import_asset_pack`, removed afterwards.
- **On Windows, one more:** if a tool that runs the game has to search for Godot (PATH, then Downloads, Desktop, Program Files, `AppData` and `<drive>:\Godot`), it saves the path it found as your user variable `GODOT_BIN`. Set `GODOT_BIN` yourself or pass `godot_bin` to skip the search.
- **Network:** two calls found in `server.py`. `check_for_update` asks `vibedna.ai/api/mcp/latest` for the published version and sends only the product name. `import_asset_pack` downloads a zip when you give it a URL. Nothing else was found.
- **Programs it starts:** only your Godot executable, for `run_smoke_test`, `run_playtest`, `run_and_screenshot` and asset imports.
- **Never touches:** keys, accounts or logins (it has none), and no telemetry was found.

The hash proves your download is the same file this guide describes. It does not prove who made it or that the code is safe, which is why your AI reads the files and you say yes first. The tools write into whatever folder you point them at, so try them in a new, empty folder before using a project you care about.

## Keys

None. `GODOT_BIN` is a path, not a secret. To set it, add `-e GODOT_BIN=<full path to Godot>` right after `-s user` in the register line of step 3.

## Install

1. **Check the hash** (Trust box), then unzip to a stable place. Rename any older `godot-vibe-mcp` folder there first.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip godot-vibe-mcp-1.1.4.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive godot-vibe-mcp-1.1.4.zip -DestinationPath $HOME\vibedna`

   You get `~/vibedna/godot-vibe-mcp` or `C:\Users\<you>\vibedna\godot-vibe-mcp`.

2. **Make a private Python environment** inside that folder.

   macOS/Linux:
   ```bash
   cd ~/vibedna/godot-vibe-mcp
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell:
   ```powershell
   cd $HOME\vibedna\godot-vibe-mcp
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. **Register it in Claude Code,** at user scope, with full paths. The server needs no extra arguments.

   macOS/Linux:
   ```bash
   claude mcp add godot -s user -- "$HOME/vibedna/godot-vibe-mcp/.venv/bin/python" "$HOME/vibedna/godot-vibe-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add godot -s user -- "$HOME\vibedna\godot-vibe-mcp\.venv\Scripts\python.exe" "$HOME\vibedna\godot-vibe-mcp\server.py"
   ```

4. **Other MCP apps:** put the same command and args in that app's own MCP settings.
   ```json
   {"mcpServers": {"godot": {
     "command": "/home/<you>/vibedna/godot-vibe-mcp/.venv/bin/python",
     "args": ["/home/<you>/vibedna/godot-vibe-mcp/server.py"]}}}
   ```
   On Windows the command is `C:/Users/<you>/vibedna/godot-vibe-mcp/.venv/Scripts/python.exe` (forward slashes are fine in JSON).

5. **Coming from an earlier install:** older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get godot`, then remove the old entry (`claude mcp remove godot -s project` from that folder, or delete it from that file).

6. **Restart Claude Code:** close it and open a new session.

## Check it works

`claude mcp get godot` should show it connected, with the `.venv` Python as its command. Then make a new empty folder and ask your AI: "Run `lint_gdscript` on <full path of that folder>". It only reads. A good answer has `"ok": true`, `"files_scanned": 0` and `"total_findings": 0`.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` (covered by the hash) and online at https://vibedna.ai/prompts/godot.md (it can change, so read it first).

## Uninstall

1. `claude mcp remove godot -s user`
2. Delete the unzipped folder (`~/vibedna/godot-vibe-mcp`), which holds `.venv` and `data`.
3. Windows only, if `GODOT_BIN` was saved and you want it gone: `[Environment]::SetEnvironmentVariable("GODOT_BIN", $null, "User")`

Delete nothing else. The games you made live in their own folders and stay yours.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** check with `python3 --version` (Windows: `py --version`, or `python` if `py` is missing). Install 3.10 or newer, delete `.venv` and repeat step 2.
- **`ModuleNotFoundError`:** the server is running with another Python. `claude mcp get godot` must show the `.venv` one. If not, remove the entry and repeat step 3.
- **"Godot binary not found":** generating and linting work without Godot. To run the game, install Godot 4 and set `GODOT_BIN`, or pass `godot_bin` to the tool.
- **Old tool list after updating:** an earlier entry is still registered. See step 5.

Support: `admin@vibedna.ai`
