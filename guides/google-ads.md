---
name: google-ads-dna-install
description: Install Google Ads DNA, the MCP server that lets your AI read and run your own Google Ads account. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes and installs it. You run the register line yourself, so your Google keys never pass through the chat.
---

# Google Ads DNA: Install Guide

This guide matches version 1.0.6.

> **For the AI reading this:** go at the person's pace and show each command before running it. First read `INSTALL.md`, `MANUAL.md`, `requirements.txt` and `server.py` in the unzipped folder and say in plain words what they do. Ask before anything is written. Never ask for a key, secret or password in the chat. `INSTALL.md` in the zip is this guide. `MANUAL.md` is the product's own older document, kept in the zip for what this guide does not repeat (the Google Cloud steps, connecting your Google account, the tools, safety): where it differs (bare `pip`, system `python`, local scope), follow this guide; its Google Cloud steps still apply. Before any change to the account, name the campaign, old value and new value, and wait for a yes. The three tools that change the account also refuse until they are called with that yes (`confirm=True`, or `owner_said_yes=True` on `set_campaign_status`): pass it only after the person said yes to that exact change, never on your own.

## What it is

Your AI works on your own Google Ads account: campaign results, custom reports, audience interests, new YouTube video campaigns (Google's Demand Gen type), daily budgets, and pause, turn on or remove. 11 tools. It uses your own Google Ads API access (a Google Cloud project you set up once).

## Trust box

- **File:** `google-ads-dna-1.0.6.zip`, 21,346 bytes, 5 files, one folder `google-ads-dna/`.
- **SHA-256:** `2e9ddcc54cc35e5aaea2239f47014ea3279d149b786005fe693036920bdc3e9b`
  Check before unzipping. Linux: `sha256sum google-ads-dna-1.0.6.zip`. macOS: `shasum -a 256 google-ads-dna-1.0.6.zip`. Windows PowerShell: `Get-FileHash google-ads-dna-1.0.6.zip` (capitals are fine). Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/google-ads-dna-1.0.6.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Dependencies:** 2, pinned to exact tested versions: `mcp==1.30.0`, `httpx==0.28.1`.
- **Reads from the environment:** `GOOGLE_ADS_CLIENT_ID` and `GOOGLE_ADS_CLIENT_SECRET` (required). Optional: `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_MAX_DAILY_BUDGET`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_DEVELOPER_TOKEN` (only for older setups that still use a developer token: a new setup needs none, and none is built into the code), `GOOGLE_ADS_API_VERSION`, `GOOGLE_ADS_DNA_HOME`, `GOOGLE_ADS_ASK` (`0` turns off the question before each change).
- **Writes:** `~/.google-ads-dna/credentials.json` (client id, client secret and Google refresh token, plain JSON; owner-only on macOS and Linux, not on Windows) and `~/.google-ads-dna/actions.jsonl` (one line per change made).
- **Network:** `googleads.googleapis.com` (your account) and `oauth2.googleapis.com` (sign-in tokens); a logo given as a web link is downloaded. To approve, you open an `accounts.google.com` link while it listens on `127.0.0.1` (random port) for Google's answer. `server.py` calls only the hosts named here, none of them vibedna.ai (the `www.googleapis.com/auth/adwords` text in it is the name of the permission it asks Google for, not a call); your AI can confirm it by listing every URL in the file.
- **Never touches:** your other files, except a local logo image you name for a campaign.

The hash proves this is the file the guide was measured from, not who made it or what the code does. That is why your AI reads the code first.

Safety in the code, and its limits:

- Campaigns are always created paused, and `create_youtube_campaign` is a dry run until called with `dry_run=False`.
- Turning one on needs `confirm="ENABLE <campaign id>"`, removing one `confirm="REMOVE <campaign id>"`. Your AI passes that phrase: it slows a mistake down, it locks nothing.
- A daily budget above the cap (50 in the account's currency by default) is refused.
- Started from your AI app, `create_youtube_campaign` (with `dry_run=False`), `set_daily_budget` and `set_campaign_status` (pausing included) change nothing on the first call: they answer `NOT DONE` with what they would change, and act only when called again with `confirm=True` (`owner_said_yes=True` on `set_campaign_status`). Your AI passes that yes, as it passes the phrase: it makes your AI stop and show you the change, it is not a lock your AI cannot open. `GOOGLE_ADS_ASK=0` turns the question off, and a script of your own that imports `server.py` is not asked.
- `run_query`, `campaign_stats`, `list_accounts` and `find_interests` only read.

## Keys

They go into the step 4 line, which you run yourself.

- **Client id and client secret** (required). You create them once in your own Google Cloud account. The tool's own messages and the start prompt call this "INSTALL.md step 2"; these are the steps (`MANUAL.md` step 2 has the same ones):
  1. At console.cloud.google.com create a project (any name).
  2. APIs and services, Library: search "Google Ads API" and enable it.
  3. The first time you use it Google asks for an access level: choose Explorer. It is approved automatically, and no developer token is needed.
  4. APIs and services, OAuth consent screen: type External, and add your own Google account as a test user.
  5. APIs and services, Credentials, Create credentials, OAuth client ID, type Desktop app. Copy the client id and the client secret: they go into the step 4 line below, typed by you in your own terminal, never in the chat.
- **Account id** (optional): the 10-digit number at the top right of ads.google.com. Without it, each call must name the account.

You sign in to Google in your browser; the refresh token goes to `credentials.json`, never to the chat. Never type the id or secret into the chat.

## Install

Needs Python 3.10 or newer.

1. Check the hash, then unzip (rename an existing `google-ads-dna` folder first). You get `~/vibedna/google-ads-dna` or `C:\Users\<you>\vibedna\google-ads-dna`.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip google-ads-dna-1.0.6.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive google-ads-dna-1.0.6.zip -DestinationPath $HOME\vibedna`
2. Your AI reads the files and reports. Go on only after your yes.
3. In that folder, create a virtual environment and install:
   - macOS/Linux: `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`
   - Windows: `py -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. You, in your own terminal, register it in Claude Code at user scope. Replace the `YOUR_` values; if you skip the account id, leave out the `-e GOOGLE_ADS_CUSTOMER_ID=YOUR_ACCOUNT_ID` part.

   macOS/Linux:
   ```
   claude mcp add google-ads-dna -s user -e GOOGLE_ADS_CLIENT_ID=YOUR_CLIENT_ID -e GOOGLE_ADS_CLIENT_SECRET=YOUR_CLIENT_SECRET -e GOOGLE_ADS_CUSTOMER_ID=YOUR_ACCOUNT_ID -- "$HOME/vibedna/google-ads-dna/.venv/bin/python" "$HOME/vibedna/google-ads-dna/server.py"
   ```
   Windows:
   ```
   claude mcp add google-ads-dna -s user -e GOOGLE_ADS_CLIENT_ID=YOUR_CLIENT_ID -e GOOGLE_ADS_CLIENT_SECRET=YOUR_CLIENT_SECRET -e GOOGLE_ADS_CUSTOMER_ID=YOUR_ACCOUNT_ID "--" "C:\Users\<you>\vibedna\google-ads-dna\.venv\Scripts\python.exe" "C:\Users\<you>\vibedna\google-ads-dna\server.py"
   ```
   On Windows keep the quotes around `--` (PowerShell can drop it and the line fails) and use `C:\` paths, never `/c/...`. The line stays in your shell history; Claude Code stores the values as plain text.
5. Other MCP apps, in their MCP settings, with the values typed by you (the account id is optional) (on Windows, the step 4 paths with doubled backslashes):
   ```json
   { "mcpServers": { "google-ads-dna": {
     "command": "/Users/<you>/vibedna/google-ads-dna/.venv/bin/python",
     "args": ["/Users/<you>/vibedna/google-ads-dna/server.py"],
     "env": { "GOOGLE_ADS_CLIENT_ID": "", "GOOGLE_ADS_CLIENT_SECRET": "", "GOOGLE_ADS_CUSTOMER_ID": "" } } } }
   ```
6. Coming from an earlier install: the older install steps registered it with `-s local`, and a hand-made `.mcp.json` entry may exist; either can keep an old copy running. Check with `claude mcp get google-ads-dna`. If it shows another path or scope, run `claude mcp remove google-ads-dna -s local` (or `-s project`) from that folder, or delete its block from that file.
7. Restart Claude Code (close it, open a new session).
8. Connect Google once: ask your AI for `authorize_start` (no values), open the link on this computer, sign in as the owner of the ads account, approve, then ask for `authorize_finish`.

## Check it works

1. `claude mcp get google-ads-dna` shows it connected and running the `.venv` Python.
2. Ask your AI to call `setup_status`. It works with no key set and shows `configured` as true or false per item, never the values. After step 8 it adds `"connected": true` and your account ids.

## Start prompt

After installing, paste the start prompt into your AI: `START_PROMPT.md` in the zip, also at https://vibedna.ai/prompts/google-ads.md

## Uninstall

1. `claude mcp remove google-ads-dna -s user`
2. Delete the unzipped `google-ads-dna` folder.
3. Delete `~/.google-ads-dna/` (or the `GOOGLE_ADS_DNA_HOME` folder if set): your Google access and the change log.

Delete nothing else. To cut access at Google too, remove the app under third-party access in your Google Account.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** install a newer one, delete `.venv`, repeat step 3.
- **Still "Failed to connect" after that:** the entry does not run the `.venv` Python (you can check with `claude mcp get google-ads-dna`). Remove it and repeat step 4.
- **`setup_status` shows `client_id` or `client_secret` false:** remove the entry, run the step 4 line again yourself, restart, then step 8.
- **Old tools or an old path still show:** an old entry is still registered. See step 6.

Support: admin@vibedna.ai
