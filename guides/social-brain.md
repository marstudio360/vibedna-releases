---
name: social-brain-install
description: Install the Vibedna Social Brain MCP. Paste this file into your AI chat and ask it to install it. Your AI checks the download, reads the code, tells you what it does, and after your yes installs it in its own virtual environment and registers it with one command. Keys go in the product's own .env file, never in the chat.
---

# Social Brain MCP: Install Guide

This guide matches version 1.11.17.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `requirements.txt` and `server.py` and say in plain words what they do before installing anything. Ask before anything is written. Never ask for a key, token or password in the chat, and never open or print `.env` or a token file. Ask again before any tool that publishes, replies, deletes or schedules.

## What it is

A Python MCP server that runs on your computer. With it your AI can post to Instagram, Facebook, X, Threads and YouTube, read and answer comments, read account stats, and run scheduled posting from your own machine. It has 96 tools. Some work without a licence; the rest need the key from your purchase email.

## Trust box

- **File:** `social-brain-mcp-1.11.17.zip`, 457,930 bytes, 31 files, all inside one `social-brain-mcp/` folder.
- **SHA-256:** `083b4c81d40f16b93507a7fcfb8468b72b0f619ed26ccf484bf11af762bdc709`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum social-brain-mcp-1.11.17.zip`
  - macOS: `shasum -a 256 social-brain-mcp-1.11.17.zip`
  - Windows PowerShell: `Get-FileHash social-brain-mcp-1.11.17.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/social-brain-mcp-1.11.17.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Dependencies, pinned to exact tested versions:** `fastmcp==3.4.11`, `mcp==1.30.0`, `httpx==0.28.1`, `anthropic==2.8.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`, `tweepy==4.17.0`, `google-api-python-client==2.202.0`, `google-auth==2.62.2`, `google-auth-oauthlib==1.5.0`.
- **Settings it reads** (from `.env` in its folder, or the environment): `MCPIZE_LICENSE_KEY`, the `META_`, `TWITTER_` and `THREADS_` values, and optionally `ANTHROPIC_API_KEY`, `FFMPEG_BIN`, `STUDIO_TOKEN`, `SB_HOME` (state folder) and `VIBEDNA_HOME`.
- **Files it writes:** `.env`, `tokens/` and `client_secret.json` inside the unzipped folder; `~/.social-brain/` (schedules, settings, publish tasks); `~/.vibedna/license_cache.json`. `youtube_auth.py` copies the newest `client_secret*.json` from `~/Downloads`. Only when you call `bot_install` or `poster_install`: a crontab line or a Windows scheduled task, and log files in your home folder.
- **Network:** graph.facebook.com, rupload.facebook.com, graph.threads.net, api.twitter.com, www.googleapis.com and oauth2.googleapis.com for your accounts; the Anthropic API if you set that key; vibedna.ai for the licence check (sends your licence key and the product name) and `check_for_update` (asks for a version number). The vibedna.ai panel is off until you say yes (`INSTALL.md` Step 8 lists what it sends). api.ipify.org is called only to test a proxy you declared; ssh and scp run only if you give a tool a host.
- **Optional browser lanes** (likes, follows, DMs, TikTok, Pinterest) need Webloom, a separate tool, and stay off until you set them up. They keep copies of that browser session's cookies in the state folder.
- **Never:** it does not ask for platform passwords (you log in in your own browser). Installing posts, deletes and schedules nothing.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. What the platforms or vibedna.ai do with a request cannot be checked from the zip. The tools act on real accounts, and each platform's own rules apply to automated activity. `wipe_account` deletes every post on a platform and refuses unless you set `SOCIAL_BRAIN_ALLOW_WIPE=1` and type a confirmation phrase: leave that unset. `MCP_HTTP=1` starts a web server with no login: leave it unset too.

## Keys

Every key goes in `.env` inside `social-brain-mcp/`, which the server loads itself, so no key goes in the chat or in the register command. Your AI creates `.env` with empty lines (`INSTALL.md` Step 4) and names the line for each value; you paste.

- `MCPIZE_LICENSE_KEY`: starts with `vbd_`, from your purchase email or vibedna.ai/library. Needed for the paid tools.
- Platform values: only for the platforms you use (`INSTALL.md` Step 6, `AUTH-GUIDE.md`).
- `ANTHROPIC_API_KEY`: optional, only for the AI writing tools, billed to your own account.

## Install

Needs Python 3.10 or newer, and ffmpeg only for Reels.

1. Check the hash, then unzip into a new folder with a stable path.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip social-brain-mcp-1.11.17.zip -d ~/vibedna/social-brain
   cd ~/vibedna/social-brain/social-brain-mcp
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive social-brain-mcp-1.11.17.zip -DestinationPath "$env:USERPROFILE\vibedna\social-brain"
   cd "$env:USERPROFILE\vibedna\social-brain\social-brain-mcp"
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add social-brain -s user -- "$HOME/vibedna/social-brain/social-brain-mcp/.venv/bin/python" "$HOME/vibedna/social-brain/social-brain-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add social-brain -s user -- "$env:USERPROFILE\vibedna\social-brain\social-brain-mcp\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\social-brain\social-brain-mcp\server.py"
   ```

3. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "social-brain": {
       "command": "<full path>/social-brain-mcp/.venv/bin/python",
       "args": ["<full path>/social-brain-mcp/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

4. Connect your accounts with `INSTALL.md` Steps 4, 6 and 8, running its scripts with the `.venv` Python (`.venv/bin/python meta_auth.py`, or `.venv\Scripts\python.exe meta_auth.py`). Where `INSTALL.md` shows a plain `pip install` or a settings entry written by hand, use steps 1 and 2 above instead.

5. Coming from an earlier install: older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get social-brain`, remove the old entry (`claude mcp remove social-brain -s project` from that folder, or delete it from that file), then restart.

6. Restart Claude Code: close it and open a new session.

## Check it works

`claude mcp get social-brain` shows it connected. Then ask your AI to call `get_project`, which needs no key and only reads local state. A good answer is a short JSON with `active_project` set to `(default/shared)` and a `state_dir` ending in `.social-brain`.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and at https://vibedna.ai/prompts/social-brain.md.

## Uninstall

1. Remove any schedules first with `bot_uninstall` and `poster_uninstall`.
2. `claude mcp remove social-brain -s user`
3. Delete the unzipped folder (it holds `.env` and `tokens/`), `~/.social-brain/` and `~/.vibedna/license_cache.json`. Delete nothing else.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **"No module named ...":** the entry points at another Python. Remove it and register again with the `.venv` Python.
- **A tool asks for a licence or names a missing value:** fill that line in `.env`, then restart.
- **Old tools still show:** an earlier entry is still registered. See step 5.
