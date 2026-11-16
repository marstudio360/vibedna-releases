---
name: viz-studio-install
description: Install Viz Studio MCP, the server that lets your AI write music visualizer presets, turn songs into visualizer projects and render them to mp4. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes and installs it in its own virtual environment. No key is needed; rendering is an extra step you choose.
---

# Viz Studio MCP: Install Guide

This guide matches version 1.1.4.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` runs, list the 7 files, read `INSTALL.md`, `MANUAL.md`, `requirements.txt`, `server.py` and `render_async_runner.py` (the only other `.py` file), and say in plain words what they do. Ask before anything is written. Never ask for a key in the chat. Ask again before the first render (the song goes to a web page, see Network) and before `viz_delete_preset`, `viz_delete_project`, `delete_viz_effect`, `add_viz_effect`, `add_font` and `viz_sync_all`.

## What it is

A Python MCP server that runs on your computer. Your AI writes visualizer looks as plain settings, imports songs as projects and renders them to mp4 with a browser engine in headless Chromium. 25 tools. Presets and projects work right after install; rendering needs the optional step 2.

## Trust box

- **File:** `viz-studio-mcp-1.1.4.zip`, 35,470 bytes, 7 files at the zip root (no folder inside: unzip it into its own new folder).
- **SHA-256:** `9cde9e3cb01c4c2823965eccfbb77bd0a0f3ab6327b6f654b3bfb170f0d81e93`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum viz-studio-mcp-1.1.4.zip`
  - macOS: `shasum -a 256 viz-studio-mcp-1.1.4.zip`
  - Windows PowerShell: `Get-FileHash viz-studio-mcp-1.1.4.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/viz-studio-mcp-1.1.4.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents in the zip:** `INSTALL.md` in the zip is this guide (the same text as https://vibedna.ai/installs/viz-studio.md without the zip's own size and checksum; if they ever differ, follow the online one). `MANUAL.md` is the product's own older document, kept for what this guide does not repeat (each setting and its default, what the shared store uploads and who can read it, what a render hands to the render page, what your own render page or render box must provide, the tools). Where it shows another way to install (a plain `pip install`, a `.mcp.json` entry written by hand with `python`), follow this guide. The zip holds no other document.
- **Dependencies:** 1, pinned to an exact tested version: `mcp==1.30.0`. Rendering on this computer also needs `playwright` and its Chromium, which `requirements.txt` does not install and this package does not pin. `server.py` imports it only inside the local render function: the server starts and every other tool works without it.
- **Settings it reads, all optional:** `VIZ_STUDIO_HOME`, `VIZ_PRESETS_FILE`, `VIZ_RENDER_URL`, `VIZ_RENDER_WHERE`, `VIZ_GL_LOCAL`; for your own render box `VIZ_BOX_SSH`, `VIZ_BOX_RENDER_JS`, `VIZ_BOX_NODE_PATH`, `VIZ_GL`; for a shared store `VIZ_SUPABASE_URL`, `VIZ_SUPABASE_KEY`, `VIZ_SUPABASE_BUCKET`, `VIZ_SUPABASE_FX_BUCKET`.
- **Files it writes:** `~/.viz-studio/`, created at the first start (or `VIZ_STUDIO_HOME`; the folder version 1.1.0 used stays in use while `~/.viz-studio` does not exist, see "The private folder" in `MANUAL.md`): `projects.json`, `user-presets.json` (or `VIZ_PRESETS_FILE`), `audio/` (a copy of each song you import), `renders/` (the mp4s) and `render-tasks/` (one status file per background render). A render given `out_path` or `out_dir` writes the mp4 there and replaces a file of the same name. Each background render leaves one small `tmp*.json` file in the system temp folder.
- **Network:** a local render opens the page in `VIZ_RENDER_URL`, by default `https://vibedna.ai/render/viz` (an address that forwards the browser to another domain, where the maker hosts the page: `curl -sI https://vibedna.ai/render/viz` shows which), in headless Chromium and hands it the whole song, the logo and background images you named and the settings; the mp4 comes back from that page. Only with both Supabase values set: your Supabase host, where every project you create or edit is uploaded (the whole song, the background image and the settings; not the logo) to the bucket named in `VIZ_SUPABASE_BUCKET`, which the code and `MANUAL.md` expect to be public. Anyone who has a file's address can download a song from a public bucket without a key, and no tool removes an uploaded song: to keep a song private, leave `VIZ_SUPABASE_URL` or `VIZ_SUPABASE_KEY` unset, and nothing is uploaded. `add_font` downloads the URL you give and uploads the file to the `VIZ_SUPABASE_FX_BUCKET` bucket. Only with `VIZ_BOX_SSH` set: `ssh` and `scp` to your own box, run with `StrictHostKeyChecking=accept-new` (the first connection to a box accepts and remembers its host key without asking, so connect once by hand first if you want to check that key; a key that later changes is refused), and leaving the song and the other work files in `/tmp` there. pypi.org once, by `pip`, at install; Playwright's download servers if you do step 2.
- **Deletes and uploads:** `viz_delete_preset`; `viz_delete_project` (also deletes the stored copy of the song, not a copy already uploaded); `delete_viz_effect` (removes a file from your bucket). `add_viz_effect` stores JavaScript in your bucket; by its own description that code later runs in the render page.
- **Never:** it asks for no key for local use and has no licence check. An import copies the song and leaves your original file as it is.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. The default render page is reached through vibedna.ai on every render (that address forwards to another domain of the maker) and its code is not in the zip: it receives your audio, and what it does with it cannot be checked from here. Set `VIZ_RENDER_URL` to your own page to avoid that, or to an empty value to turn rendering off. Any path passed as `audio_path`, `logo_path` or `bg_path` is read and handed on, so your AI passes only media files you named. On a local render `viz_set_clip` sends only the clip length: the cut at a start time happens only on a render box.

## Keys

None for local use. For the optional shared store only: `VIZ_SUPABASE_KEY` goes in the register line as `-e VIZ_SUPABASE_KEY=...` next to `-e VIZ_SUPABASE_URL=...`, and you run that line yourself in your own terminal, never in the chat. The key is sent only to that URL.

## Install

Needs Python 3.10 or newer.

1. Check the hash, then unzip into a new folder with a stable path. Unzipping runs nothing.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna/viz-studio
   unzip viz-studio-mcp-1.1.4.zip -d ~/vibedna/viz-studio
   cd ~/vibedna/viz-studio
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive viz-studio-mcp-1.1.4.zip -DestinationPath "$env:USERPROFILE\vibedna\viz-studio"
   cd "$env:USERPROFILE\vibedna\viz-studio"
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

2. Optional, only to render on this computer, after a second yes (it downloads a Chromium build):

   macOS/Linux:
   ```bash
   .venv/bin/python -m pip install playwright
   .venv/bin/python -m playwright install chromium
   ```
   Windows PowerShell:
   ```powershell
   .venv\Scripts\python.exe -m pip install playwright
   .venv\Scripts\python.exe -m playwright install chromium
   ```

3. Register it in Claude Code at user scope, with full paths:

   macOS/Linux:
   ```bash
   claude mcp add viz-studio -s user -- "$HOME/vibedna/viz-studio/.venv/bin/python" "$HOME/vibedna/viz-studio/server.py"
   ```
   Windows PowerShell (keep the quotes around `--`):
   ```powershell
   claude mcp add viz-studio -s user "--" "$env:USERPROFILE\vibedna\viz-studio\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\viz-studio\server.py"
   ```

4. Other MCP apps: the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "viz-studio": {
       "command": "<full path>/viz-studio/.venv/bin/python",
       "args": ["<full path>/viz-studio/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

5. Coming from an earlier install: an old hand-made `.mcp.json` entry can keep an old copy running. Check with `claude mcp get viz-studio`, remove it (`claude mcp remove viz-studio -s project` from that folder, or delete its block from that file), then restart. Your projects stay: they live in the private folder.

6. Restart Claude Code: close it and open a new session.

## Check it works

`claude mcp get viz-studio` shows it connected. Then ask your AI to call `viz_manifest`, which needs no key and only reads. A good answer is a JSON with `manifest` (the controls and their ranges), `families` listing `2d`, `3d`, `butterchurn` and `cover`, a `render_url`, and a `home` ending in `.viz-studio`.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md`, next to `INSTALL.md`, and at https://vibedna.ai/prompts/viz-studio.md.

## Uninstall

1. `claude mcp remove viz-studio -s user`
2. If you did Install step 2: `.venv/bin/python -m playwright uninstall` (Windows: `.venv\Scripts\python.exe -m playwright uninstall`) removes the Chromium it put in Playwright's own cache folder.
3. Delete the unzipped folder `vibedna/viz-studio`.
4. Delete the private folder that `home` showed (`~/.viz-studio/` by default) after moving out the mp4s you want: it holds your projects, song copies and renders. Delete the `VIZ_PRESETS_FILE` file if you set one, and the `tmp*.json` files in the system temp folder.

Renders sent to another folder, files uploaded to your Supabase buckets and work files on your render box are yours to keep or delete. Nothing else was written.

## If something fails

- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **A render fails with `No module named 'playwright'`, or says the browser executable does not exist:** step 2 was skipped or half done. Run both commands of step 2 and render again.
- **A render answers "Rendering is off":** `VIZ_RENDER_URL` was set to an empty value. Remove the entry and register again without it.
- **Old tools or an old path still show:** an earlier entry is still registered. See step 5.
