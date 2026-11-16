---
name: unity-install
description: Install the Vibedna Unity Vibe MCP. Paste this file into your AI chat and ask it to install: it checks the download hash, reads the bundled files and tells you what they do, and after your yes installs into a private virtual environment and registers the server in Claude Code at user scope.
---

# Unity Vibe MCP: Install Guide

This guide matches version 1.0.2.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `requirements.txt` and `server.py` in the folder and say in plain words what they do before installing anything. Ask before anything is written. Never ask for a key or password in the chat (this tool needs none). The `INSTALL.md` inside the zip still describes an older manual way (plain `pip`, a hand-written settings entry): where it differs, follow this guide.

## What it is

A Python MCP server that runs on your machine and gives your AI 17 tools for Unity 6 projects. It creates the project layout, writes scenes and prefabs as Unity YAML with their `.meta` files, writes C# scripts that use the Input System, checks C# for removed or renamed Unity calls, writes a batch build script and, if Unity is installed, boots the project in batch mode to read compile errors and run PlayMode tests. Needs Python 3.10 or newer. Unity itself is optional and not in the zip.

## Trust box

- **File:** `unity-vibe-mcp-1.0.2.zip`, 34,738 bytes, 4 files (`INSTALL.md`, `README.md`, `requirements.txt`, `server.py`).
- **SHA-256:** `c75c6a4086a91d88500553ecd2081c04750e80785246b6185da54bccbb8871bf`
  - Linux: `sha256sum unity-vibe-mcp-1.0.2.zip`
  - macOS: `shasum -a 256 unity-vibe-mcp-1.0.2.zip`
  - Windows PowerShell: `Get-FileHash unity-vibe-mcp-1.0.2.zip` (prints capitals, same value)
  - Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash:** https://vibedna.ai/installs/checksums.txt lists this file's SHA-256 too; compare it with the line above. Both are published by Vibedna, so this guards against a changed copy of this guide or of the zip, not against us.
- **Dependencies,** pinned to the exact versions tested: `fastmcp==3.4.11`, `mcp==1.30.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`.
- **Reads from the environment:** `UNITY_BIN` (optional, full path to your Unity editor executable), and a `.env` file in its folder or a parent folder if one exists. Leave `PORT` unset: with it the server listens over HTTP on all network interfaces instead of talking only to your AI app.
- **Writes:** an empty `data` folder inside the unzipped folder, and files inside the Unity project folders you name (`ProjectSettings/`, `Packages/manifest.json`, `Assets/` with scenes, scripts, prefabs, `.meta` files, `Assets/Editor/BuildScript.cs`, tests, and `test-results.xml` after a playtest). Nothing in your home folder.
- **Looks for Unity in:** `UNITY_BIN`, then PATH, then the Unity Hub folders on Windows. On macOS and Linux set `UNITY_BIN` or pass `unity_bin`, because the automatic search only knows Windows folders.
- **Network:** none found. `server.py` was searched for network code; the only web address in it is text in an error message (`unity.com/download`).
- **Programs it starts:** only your Unity editor, for `run_smoke_test_unity` and `run_playtest_unity`. Unity is its own program: when it runs it adds its cache folders to the project.
- **Never touches:** keys, accounts or logins (it has none), and no telemetry was found.

Honest limits:

- The hash proves your download is the same file this guide describes. It does not prove who made it or that the code is safe, which is why your AI reads the files and you say yes first.
- `README.md` and `INSTALL.md` in the zip name three tools that are not in `server.py` (`add_package_dependency`, `add_render_pipeline_settings`, `add_player_input_component`) and leave out two that are (`add_playtest_script_unity`, `run_playtest_unity`). The count of 17 comes from a real start of the server.
- New projects are written for editor version 6000.0.23f1 and get an application id under our name (`applicationIdentifier` in `ProjectSettings/ProjectSettings.asset`). Change both if you need to.
- The tools write into whatever folder you point them at, so try them in a new, empty folder before using a project you care about.

## Keys

None. `UNITY_BIN` is a path, not a secret. To set it, add `-e UNITY_BIN=<full path to Unity>` right after `-s user` in the register line of step 3.

## Install

1. **Check the hash** (Trust box), then unzip to a stable place. Rename any older `unity-vibe-mcp` folder there first.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip unity-vibe-mcp-1.0.2.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive unity-vibe-mcp-1.0.2.zip -DestinationPath $HOME\vibedna`

   You get `~/vibedna/unity-vibe-mcp` or `C:\Users\<you>\vibedna\unity-vibe-mcp`.

2. **Make a private Python environment** inside that folder.

   macOS/Linux:
   ```bash
   cd ~/vibedna/unity-vibe-mcp
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell:
   ```powershell
   cd $HOME\vibedna\unity-vibe-mcp
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. **Register it in Claude Code,** at user scope, with full paths. The server needs no extra arguments.

   macOS/Linux:
   ```bash
   claude mcp add unity -s user -- "$HOME/vibedna/unity-vibe-mcp/.venv/bin/python" "$HOME/vibedna/unity-vibe-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add unity -s user -- "$HOME\vibedna\unity-vibe-mcp\.venv\Scripts\python.exe" "$HOME\vibedna\unity-vibe-mcp\server.py"
   ```

4. **Other MCP apps:** put the same command and args in that app's own MCP settings.
   ```json
   {"mcpServers": {"unity": {
     "command": "/home/<you>/vibedna/unity-vibe-mcp/.venv/bin/python",
     "args": ["/home/<you>/vibedna/unity-vibe-mcp/server.py"]}}}
   ```
   On Windows the command is `C:/Users/<you>/vibedna/unity-vibe-mcp/.venv/Scripts/python.exe` (forward slashes are fine in JSON).

5. **Coming from an earlier install:** older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get unity`, then remove the old entry (`claude mcp remove unity -s project` from that folder, or delete it from that file).

6. **Restart Claude Code:** close it and open a new session.

## Check it works

`claude mcp get unity` should show it connected, with the `.venv` Python as its command. Then make a new empty folder and ask your AI: "Run `lint_csharp` on <full path of that folder>". It only reads. A good answer has `"ok": true`, `"files_scanned": 0` and `"total_findings": 0`.

## Uninstall

1. `claude mcp remove unity -s user`
2. Delete the unzipped folder (`~/vibedna/unity-vibe-mcp`), which holds `.venv` and `data`.

Delete nothing else. The projects you made live in their own folders and stay yours.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** check with `python3 --version` (Windows: `py --version`, or `python` if `py` is missing). Install 3.10 or newer, delete `.venv` and repeat step 2.
- **`ModuleNotFoundError`:** the server is running with another Python. `claude mcp get unity` must show the `.venv` one. If not, remove the entry and repeat step 3.
- **"Unity binary not found":** generating and linting work without Unity. To boot the project, install Unity 6 and set `UNITY_BIN`, or pass `unity_bin` to the tool.
- **Old tool list after updating:** an earlier entry is still registered. See step 5.

Support: `admin@vibedna.ai`
