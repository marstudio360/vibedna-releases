---
name: post-engine-install
description: Install Post Engine, a one-file Python library your AI uses to draw social post images, carousels and short reels by code on your own computer. Paste this file into your AI chat: it checks the zip, reads the code, waits for your yes and installs it. No account, no key, nothing is posted.
---

# Post Engine: Install Guide

This guide matches version 1.0.2.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` runs, list the 4 files and read them all: `INSTALL.md`, `README.md`, `requirements.txt` and `post_engine.py`. Say in plain words what they do. Ask before anything is written. Ask again before a `stock` call with `--query` (it goes online, and the photo may need a credit you cannot give), and before writing over a file. This library never posts: if you later hand its output to a tool that posts or schedules, show the person the image and the caption first and wait for a yes.

## What it is

One Python file, `post_engine.py`, used from the command line or imported. It draws post images with Pillow, with no image model: `card` (gradient, glow, specks and your text), `stock` (a photo under a scrim with your text), `carousel` (numbered slides in a folder) and `reel` (cards joined into a vertical `.mp4` by `ffmpeg`). Sizes are 1080x1080, 1080x1350 and 1080x1920. It is not an MCP server: nothing is registered, and nothing runs between calls.

## Trust box

- **File:** `post-engine-1.0.2.zip`, 13,749 bytes, 4 files, all inside one `post-engine/` folder: `post_engine.py`, `README.md`, `requirements.txt`, `INSTALL.md`.
- **SHA-256:** `d152126ac5b39db0606257c05b0aaca09c739b4b52a925559dac51ba75db885f`. Check before unzipping; stop if it differs. Linux: `sha256sum post-engine-1.0.2.zip`. macOS: `shasum -a 256 post-engine-1.0.2.zip`. Windows PowerShell: `Get-FileHash post-engine-1.0.2.zip`.
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/post-engine-1.0.2.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents:** `INSTALL.md` in the zip is this guide (the same text as https://vibedna.ai/installs/post-engine.md without the zip's own size and checksum; if they ever differ, follow the online one). `README.md` is the product's own document: the modes, the commands, the library calls, styling. Where it shows a plain `pip install`, follow this guide.
- **Dependencies:** 1, given as a range that stops before the next major version, not as an exact pin: `Pillow>=10.0.0,<13`. So `pip` installs the newest release inside the range; tested with Pillow 12.2.0 on Python 3.14.4, on Windows. Reels also need the `ffmpeg` program with the `libx264` encoder (and `aac` when you add music); this guide does not install it.
- **Settings it reads:** one optional environment variable, `FFMPEG_BIN`, the path to `ffmpeg` (default: `ffmpeg` on your PATH). No key, no token, no settings file.
- **Files it reads:** the image you pass, the music file you pass (handed to `ffmpeg`), the fonts you name in a style, and the system fonts it tries when you name none (Georgia, Segoe UI, Arial, Consolas, Menlo, DejaVu and a few more).
- **Files it writes:** only the output you name: the `--out` file, or `slide_01.jpg`, `slide_02.jpg`... in the carousel folder. Missing folders in that path are created. A reel also makes a `reel_...` folder in your system's temp folder and deletes it when it ends. In the unzipped folder: `.venv/` and, if you import the library, Python's `__pycache__` folder.
- **Programs it starts:** `ffmpeg`, for reels only, started directly and not through a shell. Nothing else.
- **Network:** only `stock` with a query. It sends your search words to `https://api.openverse.org/v1/images/` (no key, no account), then downloads the photo from the address in the answer, which is the server of the site hosting that photo. Card mode, your own image and reels made from cards make no network call. It makes no licence check and no call to vibedna.ai. pypi.org is contacted once, by `pip`, at install.
- **Never:** no account, no login, no publishing, no payment, no background process.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. Four things can bite. First, stock photos: the search asks only for photos that allow commercial use and changes, but many of those licences require you to name the author, and the engine keeps no record of the author, the licence or the page of the photo it used. Publishing one without credit can break its licence, so for anything you publish use your own image with `--image`. Second, the file at `--out` is replaced without asking. Third, a reel ends where the shorter of video and music ends, so a short music file cuts your last beats, and a music path that does not exist gives a silent reel with no error. Fourth, the specks land differently on every run, so the same text gives a slightly different image each time (a comment in the code says otherwise).

## Install

Needs Python 3 with `venv` (tested on 3.14.4 only).

1. Check the hash, then unzip. The zip holds one `post-engine/` folder.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip post-engine-1.0.2.zip -d ~/vibedna
   cd ~/vibedna/post-engine
   ```
   Windows PowerShell:
   ```powershell
   Expand-Archive post-engine-1.0.2.zip -DestinationPath "$env:USERPROFILE\vibedna"
   cd "$env:USERPROFILE\vibedna\post-engine"
   ```

2. Now your AI reads the files (the note at the top) and tells you what they do. After your yes, in that same folder:

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

3. Only if you want reels: `ffmpeg -version` must answer in your terminal. If `ffmpeg` is installed but not on your PATH, set `FFMPEG_BIN` to its full path before a reel.

4. Your AI uses the library by running `post_engine.py` with the Python inside `.venv`, from this folder, as in the check below. There is nothing to register or restart.

5. Coming from 1.0.2: it kept nothing outside its folder, so delete the old folder and do steps 1 and 2.

## Check it works

1. A call that changes nothing (no file, no network):

   macOS/Linux:
   ```bash
   .venv/bin/python post_engine.py --help
   ```
   Windows PowerShell:
   ```powershell
   .venv\Scripts\python.exe post_engine.py --help
   ```
   A good answer starts with `usage: post_engine.py [-h] {card,stock,carousel,reel} ...`.

2. Then, with your yes, a first image. It stays offline and writes one file, `first-card.jpg`, in this folder (on Windows start the line with `.venv\Scripts\python.exe`):
   ```bash
   .venv/bin/python post_engine.py card --text "It works" --out first-card.jpg
   ```
   It prints `rendered first-card.jpg`: a 1080x1080 image with your line in the middle.

## Uninstall

1. Copy out the images and videos you want to keep.
2. Delete the unzipped `post-engine` folder (`.venv/` is inside it).
3. Delete any output you wrote elsewhere. If a reel was stopped by force, a `reel_...` folder may be left in your system's temp folder: delete it. Nothing else was written.

## If something fails

- **`No module named 'PIL'`:** the command ran with another Python. Use the one inside `.venv`, or repeat step 2.
- **`ffmpeg not found`:** install `ffmpeg`, or set `FFMPEG_BIN` to its full path (step 3).
- **A reel stops with `CalledProcessError`:** `ffmpeg` refused a step. The engine does not print `ffmpeg`'s own message; ask your AI to catch the error and show its `stderr`.
- **The reel is shorter than your beats:** the music is shorter than the video.
- **`no stock results`, `could not download any stock image`, `HTTP Error` or `URLError`:** Openverse gave nothing usable, refused the request or could not be reached. The engine does not retry: change the words, or use your own image.
- **`render_stock needs either query= or image_path=`:** pass `--query` or `--image`; a stock carousel or reel needs `--query`.
- **`unknown file extension`:** `--out` needs an ending such as `.jpg` or `.png`.
- **The font is not the one you named:** a font path that does not exist falls back to a system font with no warning.
