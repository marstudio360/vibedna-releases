---
name: youtubedna-install
description: Install YouTubeDNA, the Vibedna MCP for YouTube research and for managing your own channel from your AI chat. Paste this file into your AI chat and ask it to install it. Your AI checks the download, reads the code, and after your yes installs it in its own virtual environment with one register command. Keys go in the product's own .env file, never in the chat.
---

# YouTubeDNA: Install Guide

This guide matches version 1.0.6.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, read `INSTALL.md`, `requirements.txt` and `server.py` and say in plain words what they do before installing anything. Ask before anything is written. Never ask for a key or password in the chat, and never open or print `.env`, `token.json` or `client_secrets.json`. Ask again before any tool that uploads or changes something on the channel.

## What it is

A Python MCP server that runs on your computer. Your AI can research a niche (what is ranking, which angles are open, whether a topic is worth making), turn videos into text, and, if you connect your channel, read your numbers, upload videos and edit titles, tags, visibility and banner. It has 34 tools. It is a paid product: every tool except `vibedna_info` asks for your licence key.

## Trust box

- **File:** `youtubedna-mcp-1.0.6.zip`, 30,660 bytes, 5 files, all inside one `youtube-mcp/` folder.
- **SHA-256:** `4b34a86ed4a0ce8741da12a51d0c548263555faea54c85d6d22bda69c5762522`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum youtubedna-mcp-1.0.6.zip`
  - macOS: `shasum -a 256 youtubedna-mcp-1.0.6.zip`
  - Windows PowerShell: `Get-FileHash youtubedna-mcp-1.0.6.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/youtubedna-mcp-1.0.6.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Dependencies, held to tested versions (exact, or a range where shown):** `anthropic==2.8.0`, `fastmcp==3.4.11`, `google-api-python-client==2.202.0`, `google-auth==2.62.2`, `google-auth-httplib2==0.4.4`, `google-auth-oauthlib==1.5.0`, `httpx==0.28.1`, `mcp==1.30.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`, `yt-dlp`. Optional, not in the requirements file: `faster-whisper` and ffmpeg, only to transcribe audio that has no captions. `yt-dlp` is left unpinned on purpose: it has to stay current to keep working.
- **Settings it reads** (from `.env` next to `server.py`, or the environment): `YOUTUBEDNA_LICENSE`, and optionally `YOUTUBE_API_KEY`, `ANTHROPIC_API_KEY`, `YOUTUBEDNA_ACCOUNTS` and `VIBEDNA_HOME`.
- **Files it writes:** `token.json` next to `server.py` once you connect a channel (it reads `client_secrets.json` from the same folder), and `~/.vibedna/license_cache.json`. Audio it transcribes goes to a temporary folder, removed afterwards.
- **Network:** www.googleapis.com (YouTube Data API); youtube.com and any video address you give it, through yt-dlp; Google sign-in in your own browser when you connect a channel; the Anthropic API if you set that key (the AI tools send it transcripts and comments); vibedna.ai for the licence check, which sends your licence key and the product name.
- **Never:** no telemetry code was found, and it reads only the video or image files whose path you pass to an upload tool.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. What Google or vibedna.ai do with a request cannot be checked from the zip.

- Connecting a channel asks Google for permission to manage your YouTube account, upload included. The upload and edit tools act on the real channel; `upload_video` defaults to private.
- Leave `PORT` unset. With it the server becomes a web server open to your network, with no login.
- `vibedna_info` reports version `2.0.2`, the server's own number. The package is 1.0.6.

## Keys

Every key goes in a file named `.env` next to `server.py`, which the server loads itself, so no key goes in the chat or in the register command. Your AI creates it with these empty lines; you paste the values:

```env
YOUTUBEDNA_LICENSE=
YOUTUBE_API_KEY=
ANTHROPIC_API_KEY=
```

- `YOUTUBEDNA_LICENSE`: required, from your purchase email.
- `YOUTUBE_API_KEY`: optional, free from Google Cloud Console.
- `ANTHROPIC_API_KEY`: optional, only for the tools that read and judge with AI, billed to your own account.
- Your channel (optional): download the OAuth client file from Google Cloud Console, save it as `client_secrets.json` next to `server.py`, then ask your AI to run `youtube_auth`. It opens your browser once and saves `token.json`.

## Install

Needs Python 3.11 or newer (what the zip's `INSTALL.md` asks for).

1. Get the zip from your library at vibedna.ai/library, check the hash, unzip into a new folder with a stable path, install into a virtual environment.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip youtubedna-mcp-1.0.6.zip -d ~/vibedna/youtubedna
   cd ~/vibedna/youtubedna/youtube-mcp
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive youtubedna-mcp-1.0.6.zip -DestinationPath "$env:USERPROFILE\vibedna\youtubedna"
   cd "$env:USERPROFILE\vibedna\youtubedna\youtube-mcp"
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add youtubedna -s user -- "$HOME/vibedna/youtubedna/youtube-mcp/.venv/bin/python" "$HOME/vibedna/youtubedna/youtube-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add youtubedna -s user -- "$env:USERPROFILE\vibedna\youtubedna\youtube-mcp\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\youtubedna\youtube-mcp\server.py"
   ```

3. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "youtubedna": {
       "command": "<full path>/youtube-mcp/.venv/bin/python",
       "args": ["<full path>/youtube-mcp/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

4. Coming from an earlier install: older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get youtubedna`, remove the old entry (`claude mcp remove youtubedna -s project` from that folder, or delete it from that file), then restart. Steps 1 and 2 and the Keys section replace the install steps in the zip's `INSTALL.md`.

5. Restart Claude Code: close it and open a new session.

## Check it works

`claude mcp get youtubedna` shows it connected. Then ask your AI to call `vibedna_info`, which needs no key and makes no network call. A good answer names the product `youtube-dna` and `tools_total` 34. With your licence in `.env`, `search_videos` for any topic returns a list of videos with views, length and channel.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and at https://vibedna.ai/prompts/youtubedna.md.

## Uninstall

Run `claude mcp remove youtubedna -s user`, delete the unzipped folder (it holds `.env`, `token.json` and `client_secrets.json`) and `~/.vibedna/license_cache.json`. Delete nothing else. To end channel access, remove the app in your Google account.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.11** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **It does not connect:** the entry points at another Python (register again with the `.venv` one), or `PORT` is set in your environment (unset it).
- **"needs your licence key", or a tool asks for a key:** fill that line in `.env`, then restart.
- **Old tools still show:** an earlier entry is still registered. See step 4.
