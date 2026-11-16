---
name: gumroad-dna-install
description: Install Vibedna GumroadDNA, the MCP server that lets your AI run your Gumroad store through Gumroad's own API. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes, then installs and registers it at user scope. You put your Gumroad token in the `.env` file yourself, never in the chat.
---

# GumroadDNA: Install Guide

This guide matches version 2.3.2.

This file is the install guide as published at https://vibedna.ai/installs/gumroad.md, without the zip's own size and checksum: a file cannot carry the checksum of the zip it sits in. Both are in the online guide and in the public record at https://github.com/marstudio360/vibedna-releases.

> **For the AI reading this:** go at the person's pace and show each command before running it. First read `INSTALL.md`, `requirements.txt` and `server.py` in the unzipped folder and say in plain words what they do. Ask before anything is written. Never ask for the token or a password in the chat, and never print the `.env` file. Where `INSTALL.md` differs (a git clone, bare `pip`, the system `python`, an entry written by hand), follow this guide. Before any tool call that changes the store, say what will change and wait for a yes.

## What it is

Your AI works on your Gumroad store without the browser: products, files and covers, sales, refunds, receipts, subscribers, licence keys, discount codes, stock limits, webhooks, and revenue for today, the week and the month. `scan_gumroad_niche` reads the public storefront for any keyword. 44 tools. It is free: the code checks no licence key.

## Trust box

- **File:** `gumroad-dna-2.3.2.zip`, size in the online guide, 11 files, one folder `gumroad-dna/`.
- **SHA-256:** `not printed inside the zip, see the online guide`
  Check before unzipping. Linux: `sha256sum gumroad-dna-2.3.2.zip`. macOS: `shasum -a 256 gumroad-dna-2.3.2.zip`. Windows PowerShell: `Get-FileHash gumroad-dna-2.3.2.zip` (capitals are fine). Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/gumroad-dna-2.3.2.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The full code of this version is public there, in `source/gumroad/`: it can be read before anything is downloaded.
- **Dependencies:** 4, pinned to exact tested versions: `mcp==1.30.0`, `requests==2.34.2`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`.
- **Reads from the environment:** `GUMROAD_ACCESS_TOKEN`, from your environment or a `.env` file next to `server.py`. Never set `PORT`: it puts the server on the network with no password.
- **Writes:** nothing in your home folder. `download_product_files` and `download_product_images` save into the folder you name. If Pillow is present (it is not in `requirements.txt`), `create_product` may save a square `.sq.jpg` next to your cover image.
- **Network:** `api.gumroad.com` with your token; the upload and download addresses Gumroad's API hands back for your files and images; `gumroad.com/discover` for niche scans, with no token; `vibedna.ai/api/mcp/latest` only when `check_for_update` is called (sends the word `gumroad`, gets a version number). No other call was found in `server.py`.
- **Never touches:** your other files. It reads only the files you name for an upload.

The hash proves this is the file the guide was measured from, not who made it or what the code does. That is why your AI reads the code first.

Honest limits:

- The token can act on your live store. These tools, among others, change real things: `refund_sale`, `archive_product`, `publish_product`, `create_product`, `update_product`, `update_stock`, `bump_stock`, `resend_receipt`, `mark_as_shipped`, `disable_license`, `decrement_license_uses`, the product file and image tools, and the create and delete tools for discount codes, custom fields and webhooks. Never try them as a test on a real sale.
- `sync_buyers_to_resend` only returns a list of buyer emails. It calls no email service.
- The zip carries a sample `.mcp.json` that runs the system `python`. If Claude Code offers to enable a server from that file, say no: the entry from step 5 is the one to use.

## Keys

One key, required for everything except `scan_gumroad_niche`, `vibedna_info` and `check_for_update`. Create it at app.gumroad.com/settings/advanced, under Applications: create an application, then generate an access token. After step 4, open `.env` in your own editor and paste the token after `GUMROAD_ACCESS_TOKEN=`. Your AI only checks that the file exists.

## Install

Needs Python 3.10 or newer.

1. Check the hash, then unzip (rename an existing `gumroad-dna` folder first). You get `~/vibedna/gumroad-dna` or `C:\Users\<you>\vibedna\gumroad-dna`.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip gumroad-dna-2.3.2.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive gumroad-dna-2.3.2.zip -DestinationPath $HOME\vibedna`
2. Your AI reads the files and reports. Go on only after your yes.
3. In that folder, create a virtual environment and install:
   - macOS/Linux: `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`
   - Windows: `py -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. Make the settings file, then add your token yourself (see Keys):
   - macOS/Linux: `cp .env.example .env`
   - Windows PowerShell: `Copy-Item .env.example .env`
5. Register it in Claude Code, at user scope, with full paths (the token is read from `.env`, not from this line):
   - macOS/Linux: `claude mcp add gumroad-dna -s user -- "$HOME/vibedna/gumroad-dna/.venv/bin/python" "$HOME/vibedna/gumroad-dna/server.py"`
   - Windows: `claude mcp add gumroad-dna -s user "--" "C:\Users\<you>\vibedna\gumroad-dna\.venv\Scripts\python.exe" "C:\Users\<you>\vibedna\gumroad-dna\server.py"`

   On Windows keep the quotes around `--` (PowerShell can drop it) and use `C:\` paths, never `/c/...`.
6. Other MCP apps: the same command and args in their MCP settings (on Windows, the step 5 paths with doubled backslashes).
   ```json
   { "mcpServers": { "gumroad-dna": {
     "command": "/Users/<you>/vibedna/gumroad-dna/.venv/bin/python",
     "args": ["/Users/<you>/vibedna/gumroad-dna/server.py"] } } }
   ```
7. Coming from an earlier install: an older guide had you add `gumroad-dna` by hand to `~/.claude/.mcp.json` or a project `.mcp.json`, which can keep an old copy running. Check with `claude mcp get gumroad-dna`. If it shows another path, run `claude mcp remove gumroad-dna -s project` from that folder, or delete the `gumroad-dna` block from that file.
8. Restart Claude Code (close it, open a new session).

## Check it works

1. `claude mcp get gumroad-dna` shows it connected, with the `.venv` Python as the command.
2. Ask your AI to call `vibedna_info`. It needs no token and answers with product `gumroad-dna`, version `2.3.2` and 44 tools.
3. With the token in place, ask for `get_account`. It reads your Gumroad profile and changes nothing: the token works.

## Start prompt

After installing, paste the start prompt into your AI: `START_PROMPT.md` in the zip, also at https://vibedna.ai/prompts/gumroad.md

## Uninstall

1. `claude mcp remove gumroad-dna -s user`
2. Delete the unzipped `gumroad-dna` folder. Your `.env` with the token is inside it.

The tool keeps no data folder of its own: delete nothing else. Your store stays as it is. To cancel the token, remove the application at app.gumroad.com/settings/advanced.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** install a newer one, delete `.venv`, repeat step 3.
- **"Failed to connect":** the entry does not run the `.venv` Python. Remove it and repeat step 5.
- **"GUMROAD_ACCESS_TOKEN not set":** the file must be named `.env`, sit next to `server.py`, and hold the token. Restart Claude Code after saving it. A 401 error means a revoked token: generate a new one.
- **Old tools or an old path still show:** an old entry is still registered. See step 7.

Support: admin@vibedna.ai
