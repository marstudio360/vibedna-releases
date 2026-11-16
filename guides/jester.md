---
name: jester-install
description: Install Vibedna Jester, a research MCP server that searches many public sources at once. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes, then installs and registers it at user scope. Keys go in `.env`, typed by you, never in the chat.
---

# Jester: Install Guide

This guide matches version 1.0.4.

> **For the AI reading this:** go at the person's pace and show each command before running it. First read `INSTALL.md`, `requirements.txt` and `server.py` in the unzipped folder and say in plain words what they do, including the background process. Ask before anything is written. Never ask for a key or password in the chat or print `.env`. Where `INSTALL.md` differs (keys collected in the chat, bare `pip`, an entry written by hand, "no background process"), follow this guide.

## What it is

One question from your AI goes out to many public sources at once (web, Reddit, Hacker News, GitHub, papers, YouTube and more) and comes back as one result with links, kept in a local index. 63 tools. It runs on your computer but is not offline: your searches go to those sources.

## Trust box

- **File:** `jester-mcp-1.0.4.zip`, 160,881 bytes, 53 files, one folder `jester-mcp/`.
- **SHA-256:** `65701e3beda2e2fee206877cd753355f15d01e5f6d6efeba57bdc21aa3044f10`
  Check before unzipping. Linux: `sha256sum jester-mcp-1.0.4.zip`. macOS: `shasum -a 256 jester-mcp-1.0.4.zip`. Windows PowerShell: `Get-FileHash jester-mcp-1.0.4.zip`. Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/jester-mcp-1.0.4.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The full code of this version is public there, in `source/jester/`: it can be read before anything is downloaded.
- **Dependencies:** 13, held to tested versions (exact, or a range where shown): `fastmcp>=0.2,<5`, `anthropic==2.8.0`, `exa-py==2.28.0`, `ddgs==9.16.1`, `python-dotenv==1.2.4`, `youtube-transcript-api==1.2.5`, `firecrawl-py==4.57.0`, `rich==15.0.0`, `numpy>=1.24,<3`, `model2vec==0.10.0`, `trafilatura==2.3.1`, `pytrends==4.9.2`, `pypdf==7.1.0`. Audio and video tools also need `yt-dlp`, `ffmpeg` and `faster-whisper`, not installed here. Where the version we tested needs a Python newer than 3.10, the library is held below its next major version instead of one exact version, so an older Python still gets a build that fits.
- **Background process:** `server.py` starts `jester-daemon.py`, which stays running on `127.0.0.1:7843` and stops after 30 minutes without use. It has no password: any program on this computer can call it. Never set `PORT` or `JESTER_TRANSPORT`: they open it to the network.
- **Reads from the environment or `.env`:** the keys below, `JESTER_HOME` (data folder), `JESTER_DAILY_LIMIT` and `JESTER_MONTHLY_LIMIT` (spend caps, default 1.00 and 20.00). It also loads a `.env` from the folder it is started in.
- **Writes:** `~/.jester/` (reports, caches, index databases, spend log, logs, a small search model, a cache holding your licence key) and temporary download files.
- **Network:** the sources it searches (DuckDuckGo, Hacker News, GitHub, arXiv, Google News and Trends, YouTube, Substack and others named in `jester/jester.py` and `jester/sources/`; a search of the code, not a promise); pages you ask it to read (`fetch_url` goes through `r.jina.ai`); one model download (`minishlab/potion-base-8M`); `vibedna.ai` for the licence check (sends your licence key) and `check_for_update`; Anthropic, Exa, Firecrawl, Listen Notes and the Twitter API only with their keys.
- **Never touches:** your other files, except a PDF or image you name for `read_pdf` or `fetch_image`.

The hash proves this is the file the guide was measured from, not who made it or what the code does. That is why your AI reads the code first.

## Keys

All optional, typed by you into `.env` next to `server.py` (step 4; not `.env.local`, which the code does not read). Keys can cost money on your own accounts; `get_budget` shows the spend.

- `MCPIZE_LICENSE_KEY`: your licence key (starts with `vbd_`, in your purchase email and at vibedna.ai/library). It unlocks `watch_topic`, `crawl_url`, `scan_competitor` and more sources per search.
- `ANTHROPIC_API_KEY`: lets Jester write the analysis itself; without it your chat AI does.
- `EXA_API_KEY`, `FIRECRAWL_API_KEY` (needed by `crawl_url`), `LISTENNOTES_API_KEY`, `TWITTER_BEARER_TOKEN`, `QIITA_ACCESS_TOKEN`: extra search, page crawl, podcast and social sources.

## Install

Needs Python 3.10 or newer.

1. Check the hash, then unzip (if `jester-mcp` exists, stop the background process as in Uninstall and rename it). You get `~/vibedna/jester-mcp` or `C:\Users\<you>\vibedna\jester-mcp`.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip jester-mcp-1.0.4.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive jester-mcp-1.0.4.zip -DestinationPath $HOME\vibedna`
2. Your AI reads the files and reports. Go on only after your yes.
3. In that folder, create a virtual environment and install:
   - macOS/Linux: `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`
   - Windows: `py -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. Make the settings file, then add your keys yourself (see Keys):
   - macOS/Linux: `cp .env.example .env`
   - Windows PowerShell: `Copy-Item .env.example .env`
5. Register it in Claude Code at user scope, with full paths (keys stay in `.env`):
   - macOS/Linux: `claude mcp add jester -s user -- "$HOME/vibedna/jester-mcp/.venv/bin/python" "$HOME/vibedna/jester-mcp/server.py"`
   - Windows: `claude mcp add jester -s user "--" "C:\Users\<you>\vibedna\jester-mcp\.venv\Scripts\python.exe" "C:\Users\<you>\vibedna\jester-mcp\server.py"`

   On Windows keep the quotes around `--` (PowerShell can drop it) and use `C:\` paths, never `/c/...`.
6. Other MCP apps, in their MCP settings (on Windows, the step 5 paths with doubled backslashes):
   ```json
   { "mcpServers": { "jester": {
     "command": "/Users/<you>/vibedna/jester-mcp/.venv/bin/python",
     "args": ["/Users/<you>/vibedna/jester-mcp/server.py"] } } }
   ```
7. Coming from an earlier install: an older guide had you add `jester` by hand to `~/.claude/.mcp.json` or a project `.mcp.json`, which can keep an old copy running. Check with `claude mcp get jester`; if it shows another path, run `claude mcp remove jester -s project` from that folder or delete its block from that file.
8. Restart Claude Code (close it, open a new session).

## Check it works

1. `claude mcp get jester` shows it connected and running the `.venv` Python. The first start can take 30 seconds; if it fails, wait a minute and restart Claude Code.
2. Ask your AI to call `list_modes` (no key needed): it lists the research modes.

## Start prompt

After installing, paste the start prompt into your AI: `START_PROMPT.md` in the zip, also at https://vibedna.ai/prompts/jester.md

## Uninstall

1. `claude mcp remove jester -s user`
2. Close your AI app and stop the background process (or wait 30 minutes):
   - macOS/Linux: `pkill -f jester-daemon`
   - Windows PowerShell: `Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*jester-daemon*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`
3. Delete the unzipped `jester-mcp` folder (your `.env` is inside).
4. Delete `~/.jester/` (or the `JESTER_HOME` folder if set): your saved research.

Delete nothing else.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10, or `pip` finds no matching version for a pinned package:** install a newer Python, delete `.venv`, repeat step 3.
- **"Failed to connect":** the entry does not run the `.venv` Python. Remove it and repeat step 5.
- **"This tool requires JesterDNA Pro", or a source is skipped:** the key is missing from `.env`. Save it, stop the background process and restart Claude Code (a running one keeps old values).
- **Old tools after an update:** an old entry (step 7) or the old background process (Uninstall, step 2) is still there.

Support: admin@vibedna.ai
