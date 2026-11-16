---
name: spotify-manager-install
description: Install Spotify Manager MCP, the server that lets your AI read your Spotify for Artists numbers, draft editorial pitches and manage your own playlists. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes and installs it. Your Spotify values go in the tool's own config file, which you fill in yourself.
---

# Spotify Manager MCP: Install Guide

This guide matches version 1.2.4.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` runs, list the 10 files, read `INSTALL.md`, `MANUAL.md`, `requirements.txt`, `server.py` and the other `.py` files it loads (`session.py`, `web_api.py`, `s4a.py`, `pitch.py`, `pitch_queue.py`), and say in plain words what they do. Ask before anything is written. Never ask for a key, token or password in the chat; never open or print `config.json` or `session.json`. Ask again before any tool that changes a playlist or the artist profile, and before `authorize_account`: it opens Spotify's consent page in the browser and saves a token to `config.json` (its answer does not show the token).

## What it is

A Python MCP server that runs on your computer. Your AI reads your Spotify for Artists panel (followers, listeners, streams, audience, what each release still needs), drafts the text of an editorial pitch, searches the catalog and manages your own playlists. 27 tools. It writes pitches; it does not submit them.

## Trust box

- **File:** `spotify-manager-mcp-1.2.4.zip`, 51,684 bytes, 10 files, all inside one `spotify-manager-mcp/` folder.
- **SHA-256:** `ed36dd746bbb40fcc80c1fb56d067f18aea3cc83e026813ec94466ccb11a9ab2`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum spotify-manager-mcp-1.2.4.zip`
  - macOS: `shasum -a 256 spotify-manager-mcp-1.2.4.zip`
  - Windows PowerShell: `Get-FileHash spotify-manager-mcp-1.2.4.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/spotify-manager-mcp-1.2.4.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents in the zip:** `INSTALL.md` in the zip is this guide (the same text as https://vibedna.ai/installs/spotify-manager.md without the zip's own size and checksum; if they ever differ, follow the online one). `MANUAL.md` is the product's own older document, kept for what this guide does not repeat (creating your Spotify app, what each tool needs, the pitching rules). Where it shows another way to install (a plain `pip install`, a settings entry written by hand with the keys in it), follow this guide. The zip holds no other document.
- **Dependencies, pinned to exact tested versions:** `mcp==1.30.0`, `websockets==17.4`. `server.py` also tries to import `keyring` and `vault_core` (an optional password vault). They are not installed and not needed: the import sits inside a `try`, and without them values come from the environment or the config file.
- **Settings it reads, all optional:** the account values `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` (search, public catalog, playlists), `SPOTIFY_REFRESH_TOKEN` (your playlists), `SPOTIFY_ARTIST_ID` (default artist; `label_status` needs it) and `SPOTIFY_REDIRECT_URI`; for the browser `SPOTIFY_MANAGER_CHROME`, `_PROFILE`, `_PORT`, `_BROWSER_HOME`, `_BROWSER_PORT`; for the vault `SPOTIFY_MANAGER_VAULT_PATH`, `_VAULT_SERVICE`, `_VAULT_ENTRY`, `VAULT_MASTER_PASSWORD`; the fallbacks `SPOTIFY_SP_DC`, `SPOTIFY_SP_KEY`, `SPOTIFY_S4A_BEARER`. All are read from the environment; the account values also from `~/.spotify-manager/config.json`.
- **Files it writes:** `~/.spotify-manager/session.json` (your Spotify session cookies and a short-lived panel token, plain JSON; owner-only on macOS and Linux, not on Windows) and `~/.spotify-manager/chrome-profile/` (the profile of the Chrome it starts, or the `SPOTIFY_MANAGER_PROFILE` folder). `authorize_account` writes the refresh token into `~/.spotify-manager/config.json` and keeps the other values in it (owner-only on macOS and Linux, not on Windows); if that file cannot be written, the token goes to `~/.spotify-manager/refresh_token.txt` and the tool's answer names that path. Nothing else writes `config.json`.
- **Network:** `api.spotify.com` (catalog, search, playlists); `accounts.spotify.com` (app tokens, and the consent page `authorize_account` opens in your browser); `artists.spotify.com` (panel reads with your session cookie; the page its Chrome opens to get the panel token); `generic.wg.spotify.com` (audience analytics and `set_artist_pick`). On your own machine: `127.0.0.1` ports 9222 to 9226, 9231 and 9234 (looking for a Chrome with remote debugging) and `127.0.0.1:8888` (listening up to two minutes for Spotify's answer during `authorize_account`). `developer.spotify.com` is only text in an error message. Nothing goes to vibedna.ai. pypi.org is contacted once, by `pip`, at install.
- **The browser it starts:** when no Chrome answers on those ports, it starts your installed Google Chrome without a window, with debugging port 9234 open to this computer. It closes that Chrome when the read ends, whether the read worked or not. A Chrome it did not start (one already answering on those ports) is used and left open.
- **Changes your account at once, with no confirmation step:** `create_playlist`, `add_to_playlist`, `remove_from_playlist`, `edit_playlist`, `set_playlist_cover` (uploads the JPEG you name) and `set_artist_pick` (pins a release on your public artist profile). `pitch_watch` with `act=True` submits nothing: it answers with an error text.
- **Never:** it does not ask for or store your Spotify password, submits no pitch, publishes no music and spends no money.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. The panel tools use the addresses Spotify's own panel uses, not a public API: they can stop working, and whether Spotify's terms allow this cannot be checked from the zip. `session.json` lets whoever reads it act as you in the panel. For the seconds the windowless Chrome runs, any program on your computer can drive it. A Chrome already open with remote debugging is asked for all its cookies; the tool keeps the two Spotify ones. `server.py` adds a folder named `vault-mcp` beside the unzipped folder to Python's import path: keep it absent unless it is your own vault.

## Keys

Every value goes in `~/.spotify-manager/config.json` (Windows: `C:\Users\<you>\.spotify-manager\config.json`). Your AI creates it with empty values, you fill it in an editor:

```json
{ "SPOTIFY_CLIENT_ID": "", "SPOTIFY_CLIENT_SECRET": "", "SPOTIFY_REFRESH_TOKEN": "", "SPOTIFY_ARTIST_ID": "" }
```

- **Client id and secret:** from a free app you create at developer.spotify.com (`MANUAL.md` step 1; redirect URI exactly `http://127.0.0.1:8888/callback`).
- **Refresh token:** only for playlists. Ask for `authorize_account` and accept in your browser. The tool saves the token to `config.json` itself and its answer does not show it, so it does not pass through the chat. It lasts 180 days: redo this about twice a year. If `SPOTIFY_REFRESH_TOKEN` is also set in the environment, that value wins and the tool's answer says so.
- **Artist id:** the last part of `open.spotify.com/artist/<id>`. Restart Claude Code after changing it.

## Install

Needs Python 3.10 or newer, and Google Chrome for the panel tools.

1. Check the hash, then unzip into a new folder with a stable path. Unzipping runs nothing.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip spotify-manager-mcp-1.2.4.zip -d ~/vibedna/spotify-manager
   cd ~/vibedna/spotify-manager/spotify-manager-mcp
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive spotify-manager-mcp-1.2.4.zip -DestinationPath "$env:USERPROFILE\vibedna\spotify-manager"
   cd "$env:USERPROFILE\vibedna\spotify-manager\spotify-manager-mcp"
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

2. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add spotify-manager -s user -- "$HOME/vibedna/spotify-manager/spotify-manager-mcp/.venv/bin/python" "$HOME/vibedna/spotify-manager/spotify-manager-mcp/server.py"
   ```
   Windows PowerShell (keep the quotes around `--`):
   ```powershell
   claude mcp add spotify-manager -s user "--" "$env:USERPROFILE\vibedna\spotify-manager\spotify-manager-mcp\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\spotify-manager\spotify-manager-mcp\server.py"
   ```

3. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "spotify-manager": {
       "command": "<full path>/spotify-manager-mcp/.venv/bin/python",
       "args": ["<full path>/spotify-manager-mcp/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

4. Coming from an earlier install: an old hand-made `.mcp.json` entry can keep an old copy running. Check with `claude mcp get spotify-manager`, remove it (`claude mcp remove spotify-manager -s project` from that folder, or delete its block from that file), then restart.

5. Restart Claude Code: close it and open a new session.

6. Panel login, once, before the first panel tool. A login in your everyday Chrome is not seen: the code reads only a Chrome with remote debugging, or its own profile folder. Start Chrome on that profile yourself, log in at artists.spotify.com (the password goes into Chrome, never the chat) and close it. This step follows from the code and was not run for this guide.
   - macOS: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --user-data-dir="$HOME/.spotify-manager/chrome-profile" https://artists.spotify.com`
   - Windows PowerShell: `& "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="$env:USERPROFILE\.spotify-manager\chrome-profile" https://artists.spotify.com`

## Check it works

`claude mcp get spotify-manager` shows it connected. Then ask your AI to call `diagnose`, which needs no key and changes nothing at Spotify. A good answer is a short JSON with five lines: `catalog_and_playlists`, `playlist_writing`, `default_artist`, `label_panel` and `deep_analytics`, each `ready` or naming what is missing. It looks for a Chrome and may start the windowless one.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md`, next to `INSTALL.md`, and at https://vibedna.ai/prompts/spotify-manager.md.

## Uninstall

1. `claude mcp remove spotify-manager -s user`
2. End the windowless Chrome if it still runs (a Chrome process with `--remote-debugging-port=9234`).
3. Delete the unzipped folder `vibedna/spotify-manager` and `~/.spotify-manager/` (your config, the session file and the Chrome profile). If you set `SPOTIFY_MANAGER_PROFILE`, delete that folder too. Nothing else was written.

## If something fails

- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **`label_panel` says there is no Spotify session, or a tool says the session is dead:** end the windowless Chrome (Uninstall step 2), repeat step 6, call `diagnose` again.
- **"Cannot find Chrome":** remove the entry and register again with `-e SPOTIFY_MANAGER_CHROME="<full path to Chrome>"` after `-s user`.
- **Old tools or an old path still show:** an earlier entry is still registered. See step 4.
