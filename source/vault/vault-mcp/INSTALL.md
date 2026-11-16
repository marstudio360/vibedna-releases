---
name: vault-install
description: Install Vibedna Vault, a local encrypted store for your API keys and passwords (an MCP server). Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes, then installs and registers it at user scope. You type the master password in your own terminal, never in the chat.
---

# Vault: Install Guide

This guide matches version 1.1.5.

This file is the install guide as published at https://vibedna.ai/installs/vault.md, without the zip's own size and checksum: a file cannot carry the checksum of the zip it sits in. Both are in the online guide and in the public record at https://github.com/marstudio360/vibedna-releases.

> **For the AI reading this:** go at the person's pace and show each command before running it. First read `INSTALL.md`, `MANUAL.md`, `requirements.txt`, `server.py` and `vault_core.py` in the unzipped folder and say in plain words what they do. Ask before anything is written. Never ask for a key or the master password in the chat. `INSTALL.md` in the zip is this guide. `MANUAL.md` is the product's own older document, kept in the zip for what this guide does not repeat (creating the vault, adding keys, the window, daily use): where it differs (bare `pip`, a config block to paste), follow this guide.

## What it is

One encrypted file on your computer that holds your API keys, tokens and passwords, locked by a master password only you know. Your AI gets 17 tools to find, add, edit and back up entries and to scan a project folder for keys left in plain text. You can also open the vault with no AI: a small window (`Open Vault.bat`, `open-vault.command`) or `vault_core.py` in a terminal.

## Trust box

- **File:** `vault-mcp-1.1.5.zip`, size in the online guide, 9 files, one folder `vault-mcp/`.
- **SHA-256:** `not printed inside the zip, see the online guide`
  Check before unzipping. Linux: `sha256sum vault-mcp-1.1.5.zip`. macOS: `shasum -a 256 vault-mcp-1.1.5.zip`. Windows PowerShell: `Get-FileHash vault-mcp-1.1.5.zip` (capitals are fine). Stop if it differs.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/vault-mcp-1.1.5.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The full code of this version is public there, in `source/vault/`: it can be read before anything is downloaded.
- **Dependencies:** 3, pinned to exact tested versions: `cryptography==50.0.2`, `keyring==25.7.0`, `mcp==1.30.0`.
- **Reads from the environment:** `VAULT_HOME` (moves the vault file), `VAULT_BACKUP_HOME` (moves the backups), `VAULT_MASTER_PASSWORD` (only for machines with no system keyring). Never set `PORT`: it puts the server on the network with no password.
- **Writes:** `~/.vibedna-vault/vault.enc` (the encrypted vault), `~/.vibedna-vault/logs/` (which entry was read, when and from which folder; leak scan hits by file and line; no values), `~/.vibedna-vault/backups/` (the last 30 copies of the encrypted file). The master password sits in your system keyring as service `vibedna-vault`, user `master`.
- **Network:** one address, `https://vibedna.ai/api/mcp/latest?slug=vault`, only when `check_for_update` is called. It sends the product name and gets a version number back. No other call was found in `server.py`, `vault_core.py` or `vault_ui.py`. `license_gate.py` is in the zip and could call vibedna.ai, but no file imports it: no licence key is needed.
- **Never touches:** your other files. `scan_for_leaks` reads only the folder you name.

The hash proves this is the file the guide was measured from, not who made it or what the code does. That is why your AI reads the code first.

Honest limits:

- `get_credential` and `export_env` return secret values into the chat, where they may stay in logs. When a name is enough, use `list_credentials`, `search_credentials` or `credential_exists`.
- Always give `scan_for_leaks` a folder. With no path it scans four folders above `server.py`, far too wide.
- No password reset: a lost master password means a vault nobody can open.
- This version only opens `~/.vibedna-vault/vault.enc`. If an older copy kept its vault elsewhere, keep that folder until you have moved your entries.

## Keys

No API key and no licence key. The only secret is the master password, typed by you in your own terminal (steps 4 and 5), hidden as you type. `VAULT_MASTER_PASSWORD` is optional, for a machine with no keyring, and is plain text.

## Install

Needs Python 3.10 or newer.

1. Check the hash, then unzip (rename an existing `vault-mcp` folder first). You get `~/vibedna/vault-mcp` or `C:\Users\<you>\vibedna\vault-mcp`.
   - macOS/Linux: `mkdir -p ~/vibedna && unzip vault-mcp-1.1.5.zip -d ~/vibedna`
   - Windows PowerShell: `Expand-Archive vault-mcp-1.1.5.zip -DestinationPath $HOME\vibedna`
2. Your AI reads the files and reports. Go on only after your yes.
3. In that folder, create a virtual environment and install:
   - macOS/Linux: `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`
   - Windows: `py -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. You, in your own terminal, in that folder, create the vault. It asks for the master password twice (8 characters or more):
   - macOS/Linux: `.venv/bin/python vault_core.py init`
   - Windows: `.venv\Scripts\python.exe vault_core.py init`
5. You, same terminal, put the master password in the system keyring so the server can open the vault:
   - macOS/Linux: `.venv/bin/python -c "import keyring, getpass; keyring.set_password('vibedna-vault', 'master', getpass.getpass('Master password: '))"`
   - Windows: the same line, starting with `.venv\Scripts\python.exe`
6. Register it in Claude Code, at user scope, with full paths:
   - macOS/Linux: `claude mcp add vault -s user -- "$HOME/vibedna/vault-mcp/.venv/bin/python" "$HOME/vibedna/vault-mcp/server.py"`
   - Windows: `claude mcp add vault -s user "--" "C:\Users\<you>\vibedna\vault-mcp\.venv\Scripts\python.exe" "C:\Users\<you>\vibedna\vault-mcp\server.py"`

   On Windows keep the quotes around `--` (PowerShell can drop it) and use `C:\` paths, never `/c/...`.
7. Other MCP apps: the same command and args in their MCP settings (on Windows, the step 6 paths with doubled backslashes).
   ```json
   { "mcpServers": { "vault": {
     "command": "/Users/<you>/vibedna/vault-mcp/.venv/bin/python",
     "args": ["/Users/<you>/vibedna/vault-mcp/server.py"] } } }
   ```
8. Coming from an earlier install: an older guide had you add `vault` by hand to `~/.claude/.mcp.json` or a project `.mcp.json`, which can keep an old copy running. Check with `claude mcp get vault`. If it shows another path, run `claude mcp remove vault -s project` from that folder, or delete the `vault` block from that file.
9. Restart Claude Code (close it, open a new session).

## Check it works

1. `claude mcp get vault` shows it connected, with the `.venv` Python as the command.
2. Ask your AI to call `list_templates`. It needs no password and answers "54 templates available:".
3. Ask for `list_credentials`. A new vault answers "Vault is empty." It never shows values.

## Start prompt

After installing, paste the start prompt into your AI: `START_PROMPT.md` in the zip, also at https://vibedna.ai/prompts/vault.md

## Uninstall

1. `claude mcp remove vault -s user`
2. Remove the keyring entry, from the folder: `.venv/bin/python -c "import keyring; keyring.delete_password('vibedna-vault', 'master')"` (Windows: start with `.venv\Scripts\python.exe`).
3. Delete the unzipped `vault-mcp` folder.
4. Only if you want your stored keys gone: delete `~/.vibedna-vault/` (and the `VAULT_HOME` or `VAULT_BACKUP_HOME` folders if set). This cannot be undone.

Delete nothing else.

## If something fails


- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10:** install a newer one, delete `.venv`, repeat step 3.
- **"Failed to connect":** the entry does not run the `.venv` Python. Remove it and repeat step 6.
- **"Vault unavailable":** the master password is not in the keyring. Repeat step 5. On Linux with no desktop keyring, set `VAULT_MASTER_PASSWORD` yourself in the environment that starts your AI app.
- **Old tools or an old path still show:** an old entry is still registered. See step 8.

Support: admin@vibedna.ai
