---
name: unreal-install
description: Install the Vibedna Unreal Vibe MCP. Paste this file into your AI chat and ask it to install: it checks the download hash, reads the bundled files and tells you what they do, and after your yes installs into a private virtual environment and registers the server in Claude Code at user scope.
---

# Unreal Vibe MCP: Install Guide

This guide matches version 1.0.4.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `MANUAL.md`, `requirements.txt` and `server.py` in the folder and say in plain words what they do before installing anything. Ask before anything is written. Never ask for a key or password in the chat (this tool needs none). `INSTALL.md` in the zip is this guide. `MANUAL.md` is the product's own older document, kept in the zip for what this guide does not repeat (wiring the editor, the tools). It still describes an older manual way to install (plain `pip`, a hand-written settings entry): where it differs, follow this guide.

## What it is

A Python MCP server that runs on your machine and gives your AI 16 tools for Unreal Engine 5 C++ projects. It creates a project skeleton, writes C++ classes with the engine macros in the right places, adds components, properties, Blueprint events and Enhanced Input actions, checks C++ for common engine mistakes, writes packaging scripts and, if the engine is installed, boots the editor headless to read its errors. Needs Python 3.10 or newer. Unreal Engine itself is optional and not in the zip.

## Trust box

- **File:** `unreal-vibe-mcp-1.0.4.zip`, 29,708 bytes, 5 files (`INSTALL.md`, `MANUAL.md`, `README.md`, `requirements.txt`, `server.py`).
- **SHA-256:** `e17c5db7aadf546c0ee76a0e359eac79c3ab83ca66bafc9cffa190d00e2679e2`
  - Linux: `sha256sum unreal-vibe-mcp-1.0.4.zip`
  - macOS: `shasum -a 256 unreal-vibe-mcp-1.0.4.zip`
  - Windows PowerShell: `Get-FileHash unreal-vibe-mcp-1.0.4.zip` (prints capitals, same value)
  - Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/unreal-vibe-mcp-1.0.4.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Dependencies,** pinned to the exact versions tested: `fastmcp==3.4.11`, `mcp==1.30.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`.
- **Reads from the environment:** `UE_BIN` (optional, full path to the editor executable) or `UE_ROOT` (optional, your engine folder), and a `.env` file in its folder or a parent folder if one exists. Leave `PORT` unset: with it the server listens over HTTP on all network interfaces instead of talking only to your AI app.
- **Writes:** an empty `data` folder inside the unzipped folder, and files inside the project folders you name (the `.uproject`, `Source/`, `Config/`, `Content/`, a `.gitignore`, and packaging scripts in the project root). Nothing in your home folder.
- **Looks for the engine in:** `UE_BIN`, `UE_ROOT`, PATH, then the `Epic Games` folders on Windows and `~/UnrealEngine`. It only reads there. The search knows Windows and Linux layouts, so on macOS set `UE_BIN` or pass `ue_bin`.
- **Network:** none found. `server.py` was searched for network code and web addresses.
- **Programs it starts:** only your Unreal editor, for `run_smoke_test_ue5` and `run_playtest_ue5`. A first start can compile for a long time.
- **Never touches:** keys, accounts or logins (it has none), and no telemetry was found.

Honest limits:

- The hash proves your download is the same file this guide describes. It does not prove who made it or that the code is safe, which is why your AI reads the files and you say yes first.
- It cannot write the engine's binary files. Levels, input actions and imported images, audio and video are written as Python recipes under `Content/Python`, and they become real assets only when the editor runs them.
- `MANUAL.md` and `README.md` in the zip use names that are not in `server.py`: the variable `UNREAL_EDITOR_BIN` (the code reads `UE_BIN` and `UE_ROOT`) and tools such as `run_smoke_test_unreal` and `lint_ue_cpp` (real names: `run_smoke_test_ue5`, `lint_cpp_ue5`). The count of 16 comes from a real start of the server.
- The tools write into whatever folder you point them at, so try them in a new, empty folder before using a project you care about.

## Keys

None. `UE_BIN` and `UE_ROOT` are paths, not secrets. To set one, add `-e UE_ROOT=<full path to your engine folder>` right after `-s user` in the register line of step 3.

## Install

1. **Check the hash** (Trust box), then unzip to a stable place. Rename any older `unreal-vibe-mcp` folder there first.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip unreal-vibe-mcp-1.0.4.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive unreal-vibe-mcp-1.0.4.zip -DestinationPath $HOME\vibedna`

   You get `~/vibedna/unreal-vibe-mcp` or `C:\Users\<you>\vibedna\unreal-vibe-mcp`.

2. **Make a private Python environment** inside that folder.

   macOS/Linux:
   ```bash
   cd ~/vibedna/unreal-vibe-mcp
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell:
   ```powershell
   cd $HOME\vibedna\unreal-vibe-mcp
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. **Register it in Claude Code,** at user scope, with full paths. The server needs no extra arguments.

   macOS/Linux:
   ```bash
   claude mcp add unreal -s user -- "$HOME/vibedna/unreal-vibe-mcp/.venv/bin/python" "$HOME/vibedna/unreal-vibe-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add unreal -s user -- "$HOME\vibedna\unreal-vibe-mcp\.venv\Scripts\python.exe" "$HOME\vibedna\unreal-vibe-mcp\server.py"
   ```

4. **Other MCP apps:** put the same command and args in that app's own MCP settings.
   ```json
   {"mcpServers": {"unreal": {
     "command": "/home/<you>/vibedna/unreal-vibe-mcp/.venv/bin/python",
     "args": ["/home/<you>/vibedna/unreal-vibe-mcp/server.py"]}}}
   ```
   On Windows the command is `C:/Users/<you>/vibedna/unreal-vibe-mcp/.venv/Scripts/python.exe` (forward slashes are fine in JSON).

5. **Coming from an earlier install:** older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get unreal`, then remove the old entry (`claude mcp remove unreal -s project` from that folder, or delete it from that file).

6. **Restart Claude Code:** close it and open a new session.

## Check it works

`claude mcp get unreal` should show it connected, with the `.venv` Python as its command. Then make a new empty folder and ask your AI: "Run `lint_cpp_ue5` on <full path of that folder>". It only reads. A good answer has `"ok": true`, `"files_scanned": 0` and `"total_findings": 0`.

## Uninstall

1. `claude mcp remove unreal -s user`
2. Delete the unzipped folder (`~/vibedna/unreal-vibe-mcp`), which holds `.venv` and `data`.

Delete nothing else. `~/UnrealEngine`, if you have it, is your engine and was not made by this tool. Your projects live in their own folders and stay yours.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** check with `python3 --version` (Windows: `py --version`, or `python` if `py` is missing). Install 3.10 or newer, delete `.venv` and repeat step 2.
- **`ModuleNotFoundError`:** the server is running with another Python. `claude mcp get unreal` must show the `.venv` one. If not, remove the entry and repeat step 3.
- **"Unreal Editor binary not found":** generating and linting work without the engine. To boot the editor, install Unreal Engine 5 and set `UE_ROOT` or `UE_BIN`, or pass `ue_bin` to the tool.
- **Old tool list after updating:** an earlier entry is still registered. See step 5.

Support: `admin@vibedna.ai`
