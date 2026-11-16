---
name: ai-company-system-install
description: Install the AI Company System, an MCP server that turns Claude Code sessions into the employees of a company you define, each with its own written manual. Paste this file into your AI chat: it checks the zip, reads the code, tells you what the tool can do on your machine, waits for your yes and installs it. No key is needed.
---

# AI Company System: Install Guide

This guide matches version 1.0.2.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` runs, list the 88 files, read `INSTALL.md`, `MANUAL.md` and `requirements.txt` in `engine/`, then `server.py` and the `.py` files it loads (`core.py`, `meter.py`, `remote.py`, `safe_sync.py`, `git_lock.py`, `tasks.py`, `genesis.py`, `rules.py`, `urgent.py`, `usage.py`, `status.py`, `server_setup.py`, `night_runner.py`), and say in plain words what they do. Before any optional part, read the script it runs. Ask before anything is written. Never ask for a key or token in the chat. Ask again before `night_shift` and before any `server_` tool.

## What it is

A Python MCP server that runs on your computer. Each Claude Code session can enter a role (Director, Research and others) of a company you create. The role lives in a markdown manual in one folder, with messages between roles, a task board and questions for you. 49 tools. Optional: a night shift, employees on your own server, a local web page.

## Trust box

- **File:** `ai-company-system-1.0.2.zip`, 325,517 bytes, 88 files, all inside one `ai-company-system/` folder; the server is in `ai-company-system/engine/`.
- **SHA-256:** `241c6b501d98d654fd640ab6441385e84ba33d5a734a836be018ec3e60c6a53d`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum ai-company-system-1.0.2.zip`
  - macOS: `shasum -a 256 ai-company-system-1.0.2.zip`
  - Windows PowerShell: `Get-FileHash ai-company-system-1.0.2.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/ai-company-system-1.0.2.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents in the zip:** `INSTALL.md` in the zip (in `engine/`) is this guide (the same text as https://vibedna.ai/installs/ai-company-system.md without the zip's own size and checksum; if they ever differ, follow the online one). `MANUAL.md`, next to it, is the product's own older document, kept for what this guide does not repeat (server mode, the owner app, the credit rules). At the zip root: `START_HERE.md` (older setup steps), `AI_COMPANY_SYSTEM_JOURNAL.md` (the field manual), `MANIFEST.md` (every file with its checksum) and `TEST.md` (the test run of version 1.0.0), `START_PROMPT.md`. Also `engine/EVENTS.md`, `skills/ai-director/SKILL.md` and the starter texts in `engine/template/`. Where any of them shows another way to install (copying the engine to `~/.ai-company`, `pip` in an activated venv), follow this guide; where they or a tool's answer name `~/.ai-company/<script>.py`, that script is in your `engine` folder: run it with the `.venv` Python.
- **Dependencies:** 1, pinned to an exact tested version: `mcp==1.30.0`. When a feature needs them it runs the `git`, `claude`, `tmux`, `ssh` and `scp` programs already on your machine.
- **Settings it reads, all optional:** `AI_COMPANY_HOME` (company folder, default `~/ai-company`), `AI_COMPANY_COMPANY`, `AI_COMPANY_ROLE`, `AI_COMPANY_STATE`, `AI_COMPANY_OUT`, `AI_COMPANY_JOURNALS_DIR`; for server mode `AI_COMPANY_SERVER_SSH`, `_SERVER_USER`, `_SERVER_DIR`, `_SERVER_TOKEN`. The engine reads about 70 names in all, most of them only in the optional scripts, which list theirs in their first lines.
- **Files the 49 tools write:** the company folder (`init` creates it; `~/ai-company` unless you name another): manuals, inboxes, `tasks.json`, `ROSTER.json`, `messages.md`, questions, the pipeline, `night/`. Outside it: `~/.ai-company/` (`control/answers.jsonl`, `control/urgent.json`, `control/urgent_log.jsonl`, `open_questions.json`), `~/state/tasks_covered_by.log` (on Linux also `git_lock.log`), and, when you change the call phrase, `~/.claude/skills/ai-director/SKILL.md` if it exists.
- **Reads outside its folders:** `~/.claude.json` and `.mcp.json` files (which MCP servers are configured), `~/.claude/projects` (session logs, to count tokens per role), `~/journals` if it exists, and the file named under Network.
- **Network:** `api.anthropic.com`: `spend` and the night shift read your Claude Code login token from `~/.claude/.credentials.json` and send it there to read your plan usage. Your git remote: if the company folder is a git repository, most saving tools commit their own files and, with a remote, fetch, merge and push. Your own server over `ssh` and `scp`, only in server mode. Nothing goes to vibedna.ai. pypi.org is contacted once, by `pip`, at install.
- **What it can do on your machine:**
  - `night_shift` starts a background program that outlives Claude Code. For each task line it runs `claude -p` with `--dangerously-skip-permissions` in the company folder, up to 30 minutes each, until the list ends, the plan budget you gave is reached or `stop_night` writes a `STOP` file. Such a session can run any command and change any file your user can, with no question asked. It also copies the settings of the MCPs a role lists, with any keys they hold, into `night/<plan>_mcp.json`.
  - `message` writes to another role's inbox; if that role runs here in a tmux session named `emp-...`, it also types the text into it and presses Enter (over `ssh` in server mode).
  - The `server_` tools run commands on your server with `sudo`. `server_prepare` creates a Linux user there, installs Claude Code (`npm`) and `mcp` (`pip`), copies your token file, the company folder and the engine, adds a hook and a cron line (the spending brake, every 5 minutes), and on this computer adds a git remote named `server` and pushes. `server_open` starts Claude Code there with `--dangerously-skip-permissions`; `server_say` types into it as if it were you.
  - No tool takes a shell command to run here, and none creates a scheduled task or cron line on this computer.
- **Optional scripts, never started by the 49 tools:** `install_guard.py` and `install_autosave.py` add hooks to `~/.claude/settings.json`; the second commits and pushes the whole company folder after every reply. `owner_app.py` serves a page on `127.0.0.1:8765`. `brake.py`, `status.py`, `foreman.py`, `routine.sh`, `local_worker.py` and `usage_box.py` are for cron on a Linux server: they close, reopen and start AI sessions, and the last calls api.anthropic.com. `ship_gate.py` resets a site checkout you name, runs your publish command and pushes. `check_access.py` tests keys from a separate vault at graph.facebook.com, api.stripe.com, api.resend.com, api.github.com, api.cloudflare.com or your Supabase URL.
- **Never:** no licence check, no key asked for, and starting the server writes nothing.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. The larger risk is what the sessions do: the night shift and server mode run AI sessions with permission prompts off, guided only by markdown manuals. The spending brake acts only on tmux sessions on Linux, from cron: on your own computer nothing stops a session at a budget except the night shift's check between tasks. The zip's own `TEST.md` says the test ran on Linux, the server tools were not run on a rented server, and Windows and macOS were not tested.

## Keys

None. Server mode only: a Claude Code token made with `claude setup-token`, which you save in a file yourself. You give `server_prepare` the path of that file, never the token; it is copied to your server.

## Install

Needs Python 3.10 or newer and Claude Code; `git` if you want the company folder versioned.

1. Check the hash, then unzip into a new folder with a stable path. Unzipping runs nothing.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip ai-company-system-1.0.2.zip -d ~/vibedna/ai-company-system
   cd ~/vibedna/ai-company-system/ai-company-system/engine
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive ai-company-system-1.0.2.zip -DestinationPath "$env:USERPROFILE\vibedna\ai-company-system"
   cd "$env:USERPROFILE\vibedna\ai-company-system\ai-company-system\engine"
   ```

   Now your AI reads the files (the note at the top) and tells you what they do. After your yes, in that same `engine` folder:

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

2. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add ai-company -s user -- "$HOME/vibedna/ai-company-system/ai-company-system/engine/.venv/bin/python" "$HOME/vibedna/ai-company-system/ai-company-system/engine/server.py"
   ```
   Windows PowerShell (keep the quotes around `--`):
   ```powershell
   claude mcp add ai-company -s user "--" "$env:USERPROFILE\vibedna\ai-company-system\ai-company-system\engine\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\ai-company-system\ai-company-system\engine\server.py"
   ```
   Only if your company folder will not be `~/ai-company`: add `-e AI_COMPANY_HOME="<folder>"` after `-s user`.

3. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "ai-company": {
       "command": "<full path>/engine/.venv/bin/python",
       "args": ["<full path>/engine/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

4. Coming from an earlier install: the older steps put the engine in `~/.ai-company` under the same name, and an old hand-made `.mcp.json` entry may exist; either can keep an old copy running. Check with `claude mcp get ai-company`. If it shows another path, run `claude mcp remove ai-company -s user` (or `-s project` from that folder), then step 2. Your company folder is not touched.

5. Restart Claude Code: close it and open a new session.

6. Create the company: after your yes, your AI calls `init`, then `create_company` with a name, a short code and a type (the questions are in `START_HERE.md` step 2). The optional parts (skill and key guard, server mode, owner app) are its steps 4, 7 and 8: one at a time, each after your AI read its script and you said yes, with your `engine` folder in place of `~/.ai-company`.

## Check it works

`claude mcp get ai-company` shows it connected. Then ask your AI to call `companies`, which needs no key and writes nothing. Before `init`, a good answer is the line `Company folder not found (no ai-director.json). Create it with init() or set AI_COMPANY_HOME.` After `init` it starts with `No companies yet.`

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` (zip root) and at https://vibedna.ai/prompts/ai-company-system.md. Its step 4 installs the engine again into `~/.ai-company`: tell your AI this guide already did that, in your `engine` folder.

## Uninstall

1. Stop what runs: `stop_night`, and the owner app if you started it. If you used server mode, remove on your server what `server_prepare` added (the cron line, the Linux user and its home, `/srv/ai-company.git`).
2. `claude mcp remove ai-company -s user`
3. If you installed them: delete the `key_guard.py` and `autosave.py` entries under `hooks` in `~/.claude/settings.json`, and the folder `~/.claude/skills/ai-director/`.
4. Delete the unzipped folder `vibedna/ai-company-system`, the folder `~/.ai-company/`, and in `~/state/` the files `tasks_covered_by.log` and `git_lock.log`, plus the logs of any optional script you ran.
5. The company folder (`~/ai-company` by default) is your company's work: keep it or delete it.

The 49 tools wrote nothing else.

## If something fails

- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **"Company folder not found" after `init`:** the folder is neither `~/ai-company` nor the one the session was opened in. Remove the entry and register again with `-e AI_COMPANY_HOME` (step 2).
- **Old tools or an old path still show:** an earlier entry is still registered. See step 4.
