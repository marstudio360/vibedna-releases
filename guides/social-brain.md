---
name: social-brain-install
description: Install the Vibedna Social Brain MCP. Paste this file into your AI chat and ask it to install it. Your AI checks the download, reads the code, tells you what it does, and after your yes installs it in its own virtual environment and registers it with one command. Keys go in the product's own .env file, never in the chat.
---

# Social Brain MCP: Install Guide

This guide matches version 1.12.6.

> **For the AI reading this:** go at the person's pace and show each command before you run it. After unzipping, and before `pip` or any script runs, list the 37 files, read `INSTALL.md`, `MANUAL.md`, `requirements.txt`, `server.py` and the `*_auth.py` scripts you are going to run, look through the other `.py` files (the runners of the optional parts), and say in plain words what they do. Unzipping runs nothing. Ask before anything is written. Never ask for a key, token or password in the chat, and never open or print `.env` or a token file. Ask again before any tool that publishes, replies, deletes or schedules.

## What it is

A Python MCP server that runs on your computer. With it your AI can post to Instagram, Facebook, X, Threads and YouTube, read and answer comments, read account stats, and run scheduled posting from your own machine. It has 113 tools. Reading stats and comments, search and the setup tools work without a licence; publishing, AI captions, the content calendar, competitor analysis and content ideas need the key from your purchase email.

## Trust box

- **File:** `social-brain-mcp-1.12.6.zip`, 623,315 bytes, 37 files, all inside one `social-brain-mcp/` folder.
- **SHA-256:** `3851d715b00a342c1ce786598f56bad78270a278c6bf18a7b8a5e3e06db8cea2`. Check before unzipping; stop if it differs:
  - Linux: `sha256sum social-brain-mcp-1.12.6.zip`
  - macOS: `shasum -a 256 social-brain-mcp-1.12.6.zip`
  - Windows PowerShell: `Get-FileHash social-brain-mcp-1.12.6.zip`
- **Where the file comes from:** your library at https://vibedna.ai/library, after signing in with the email you bought or claimed it with. **Second place to check the hash, on another host:** the public record at https://github.com/marstudio360/vibedna-releases (the GitHub account of the maker of Vibedna) has this file's SHA-256 in `checksums.txt` and the SHA-256 of every file inside the zip in `manifests/social-brain-mcp-1.12.6.zip.sha256`. Every change there is a dated commit, so a swapped file would show. The code of this tool is not public: read it in your own copy before installing, as this guide asks.
- **Documents in the zip:** `INSTALL.md` is this guide (the same text as https://vibedna.ai/installs/social-brain.md without the zip's own size and checksum; if the two differ, stop and compare the version line and the hash before following either): it takes you from the download to connected accounts, and every required step is in it. `MANUAL.md` is about using it afterwards: scheduled posting, the optional lanes, updating and troubleshooting. `AUTH-GUIDE.md` (also as `.html` and `.pdf`) shows every click on each platform's pages, as a companion to Step 4. `SETUP-ASSISTANT.md` is a short sheet of platform facts for your AI (what each error means, how long each token lasts). `START_PROMPT.md` is the prompt you paste after installing.
- **Dependencies, pinned to exact tested versions:** `fastmcp==3.4.11`, `mcp==1.30.0`, `httpx==0.28.1`, `anthropic==2.8.0`, `python-dotenv==1.2.4`, `uvicorn==0.54.0`, `tweepy==4.17.0`, `google-api-python-client==2.202.0`, `google-auth==2.62.2`, `google-auth-oauthlib==1.5.0`.
- **Settings it reads** (from `.env` in its folder, or the environment): `MCPIZE_LICENSE_KEY` (an older name the setting keeps; it holds your Vibedna licence key), the `META_`, `TWITTER_` and `THREADS_` values, and optionally `ANTHROPIC_API_KEY`, `FFMPEG_BIN`, `SB_FFPROBE`, `STUDIO_TOKEN`, `SB_HOME` (state folder), `SB_DROP_DIR` (a folder of finished posts to pick up) and `VIBEDNA_HOME`. Only for the optional parts below: `RESEND_API_KEY`, `SB_ALERT_EMAIL` and `SB_ALERT_FROM` (alert and review mails), `SB_REVIEW_HOST` and `SB_REVIEW_PORT` (review page), `SB_CLAUDE_BIN` and `SB_CLAUDE_TOKEN_FILE` (content engine), `SB_PUBLISH_ASK` (the question before a post from a chat), `MCP_HTTP`, `MCP_HTTP_TOKEN`, `MCP_HOST` and `PORT` (web mode), and the `IG_BROWSER_`, `CHROME_SESSIONS` and `BROWSER_LOCK_` values (browser lanes).
- **Files it writes:** `.env`, `tokens/` and `client_secret.json` inside the unzipped folder; `~/.social-brain/` (schedules, settings, publish tasks, queues, what each lane posted); `~/.vibedna/license_cache.json`. `youtube_auth.py` copies the newest `client_secret*.json` from `~/Downloads`. Only when you call `bot_install` or `poster_install`: a crontab line or a Windows scheduled task, and its log files (`lane_*.log`, `engage_bot.log`, `drip_runner.log`) in your home folder, or in the state folder when you set `SB_HOME`. Only with a browser lane: small lock files in `BROWSER_LOCK_DIR` (default `/tmp/browser-locks`).
- **Network:** graph.facebook.com, rupload.facebook.com, graph.instagram.com, graph.threads.net, api.twitter.com, www.googleapis.com and oauth2.googleapis.com for your accounts; the Anthropic API if you set that key; vibedna.ai for the licence check (sends your licence key and the product name) and `check_for_update` (asks for a version number). The vibedna.ai panel is off until you say yes ("Optional: the panel on vibedna.ai" below lists what it sends). api.resend.com is called only if you set `RESEND_API_KEY`, to mail you. www.pinterest.com is read without login only by the Pinterest lane, to confirm a Pin on your public profile. api.ipify.org is called only when you set a `proxy_url` for an account, to check that the proxy works. ssh and scp run only when you give a tool a `host` of your own (to install a schedule on your own server with `bot_install` or `poster_install`, or to read libraries and videos you keep on another machine); leave it empty and they never run. pypi.org is contacted once, by `pip`, when the dependencies install.
- **Optional browser lanes** (likes, follows, DMs, TikTok, Pinterest) need Webloom, a separate tool, and stay off until you set them up. They act through that logged-in browser on each platform's own website, not through this server's own network calls, and each platform's rules on automated activity apply to them. They keep copies of that browser session's cookies in the state folder.
- **Optional content engine** (queues of posts for X and LinkedIn written from a library you fill in): it runs your own `claude` command line to write the drafts, on your own Claude login, only when you call those tools or schedule them. A scheduled run can hand that command your Claude login from a file, only if you name the file in `SB_CLAUDE_TOKEN_FILE`; no login file is opened otherwise. Drafts wait as pending and nothing is posted by the engine itself.
- **Optional review page:** `content_review_server.py` shows those pending drafts on `127.0.0.1:8831`. It has no login of its own, so leave `SB_REVIEW_HOST` unset: it then answers only on your own machine.
- **Optional alert mails:** `alert_runner.py` mails you when an account or a lane stops, only if you set `RESEND_API_KEY` and `SB_ALERT_EMAIL`. Without them it only prints.
- **Never:** it does not ask for platform passwords (you log in in your own browser). Installing posts, deletes and schedules nothing.

**Limits.** The hash proves your file is the one this guide describes, not that the code is safe: that is why your AI reads it first. What the platforms or vibedna.ai do with a request cannot be checked from the zip. The tools act on real accounts, and each platform's own rules apply to automated activity. The four tools that delete (`delete_post`, `delete_meta_comment`, `drip_delete`, `engage_delete`) do nothing without `confirm=True`, which your AI passes only after your yes; no tool deletes a whole account. The 19 tools that post or reply work the same way when your AI calls them from a chat: nothing goes out without `confirm=True`, passed only after your yes to that exact post. What a schedule, a lane or your own script sends is not asked again, because you approved it when you queued it. `SB_PUBLISH_ASK=0` turns the question off: leave it unset. `MCP_HTTP=1` starts a web server on your own machine and refuses to start without `MCP_HTTP_TOKEN`: leave it unset unless you need it.

## Keys

Every key goes in `.env` inside `social-brain-mcp/`, which the server loads itself, so no key goes in the chat or in the register command. Your AI creates `.env` with empty lines (Step 3 below) and names the line for each value; you paste.

- `MCPIZE_LICENSE_KEY`: starts with `vbd_`, from your purchase email or vibedna.ai/library. Needed for the paid tools.
- Platform values: only for the platforms you use (Step 4 below, `AUTH-GUIDE.md`).
- `ANTHROPIC_API_KEY`: optional, only for the AI writing tools, billed to your own account.

## Install

Needs Python 3.10 or newer, and ffmpeg only for Reels.

1. Check the hash, then unzip into a new folder with a stable path. Unzipping runs nothing.

   macOS/Linux:
   ```bash
   mkdir -p ~/vibedna
   unzip social-brain-mcp-1.12.6.zip -d ~/vibedna/social-brain
   cd ~/vibedna/social-brain/social-brain-mcp
   ```
   Windows PowerShell (`$env:USERPROFILE` is `C:\Users\<you>`):
   ```powershell
   Expand-Archive social-brain-mcp-1.12.6.zip -DestinationPath "$env:USERPROFILE\vibedna\social-brain"
   cd "$env:USERPROFILE\vibedna\social-brain\social-brain-mcp"
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
   claude mcp add social-brain -s user -- "$HOME/vibedna/social-brain/social-brain-mcp/.venv/bin/python" "$HOME/vibedna/social-brain/social-brain-mcp/server.py"
   ```
   Windows PowerShell:
   ```powershell
   claude mcp add social-brain -s user -- "$env:USERPROFILE\vibedna\social-brain\social-brain-mcp\.venv\Scripts\python.exe" "$env:USERPROFILE\vibedna\social-brain\social-brain-mcp\server.py"
   ```

   **If you use another MCP app instead of Claude Code:** the same command and args in the app's MCP settings.
   ```json
   { "mcpServers": { "social-brain": {
       "command": "<full path>/social-brain-mcp/.venv/bin/python",
       "args": ["<full path>/social-brain-mcp/server.py"] } } }
   ```
   On Windows the command ends in `.venv\Scripts\python.exe`.

   **Only if you installed an earlier version:** older guides had you add this server by hand to a `.mcp.json` file (home folder or a project) or to `~/.claude/.mcp.json`, and that entry can keep an old copy running. Check with `claude mcp get social-brain`, remove the old entry (`claude mcp remove social-brain -s project` from that folder, or delete it from that file), then restart. To update, unzip the new version over the same folder: `.env` and `tokens/` are not in the zip, so they stay.

## Connect your accounts

Steps 3, 4 and 5, in order, with nothing to skip. The panel at the end is optional.

### Two ways to connect your accounts

Each platform can be connected two ways. You can mix them, one per platform.

**Assisted (if you have WebLoom).** Your AI uses WebLoom, a separate browser tool (the Social System includes three months of WebLoom Pro), to walk each setup page for you. You log in once on each page and approve the permission screen; WebLoom fills in the developer console and writes the values into your local `.env`. Nothing you type is ever sent to the chat.

**Manual.** You click through the pages yourself and paste each value into `.env`, using the tables and steps further down. Always available, and the fallback if an assisted step gets stuck.

#### The assisted path, step by step (AI)

Do this only for a platform the person chose to connect the assisted way.

1. **Is WebLoom here?** If the `chrome_status` tool is not in this session, tell the person to install WebLoom once: open https://webloom.run/docs/install, or drop https://webloom.run/webloom-install.md into this chat, then restart the AI app. Stop until they confirm.
2. **Pair once.** Run `webloom_pair()`. It opens a tab; the person clicks approve. One time only.
3. **Per platform, install its recipe and let WebLoom drive.** Run `install_thread(domain="developers.facebook.com")` for Instagram and Facebook (Threads uses the same Meta app), `install_thread(domain="x.com")` for Twitter/X, and `install_thread(domain="console.cloud.google.com")` for YouTube. With WebLoom Pro, which the Social System includes, each returns `pro` and is free; if an answer names a price instead, tell the person and wait for their yes. Then, in your own words, tell the person: WebLoom is going to drive this browser to set up their own account on their own machine, it acts inside their own logged-in browser to create a developer app and save its keys to `.env`, nothing they type reaches the chat and they can stop it at any time, they log in once here with their password (and 2FA if they use it) and approve the permission screen when it appears, and you handle the rest. WebLoom then fills the developer console and saves the values into `.env`.
4. **What stays with the person.** Meta and Google require the account owner to click "create app" and "approve" themselves. WebLoom brings the page right up to those buttons. So on the assisted path the person only ever logs in once per page and approves.

These recipes are new, and Meta changes its console often. If an assisted step stalls, switch that platform to the Manual path below and finish it by hand. The Manual path is always complete and never removed.

With either path, your keys live only in your local `.env`, never in the chat.

### The manual path: who does what

#### What you do

You click in your browser and paste values into `.env`, a file in the Social Brain folder. Set up only the platforms you want.

| Platform | Clicks in your browser | Pastes into `.env` |
|---|---|---|
| Licence | none | 1 |
| Instagram + Facebook | about 20 | 3 |
| Twitter / X | about 15 | 5 |
| Threads | about 12 | 3 (plus 1 address into a Meta form) |
| YouTube | about 20 | none |
| Anthropic (optional) | about 3 | 1 |
| At the end | restart Social Brain once | |

#### What your AI does

- Checks Python, installs the packages, creates `.env` with empty lines, and connects Social Brain to your AI app.
- Tells you where each value is and which line of `.env` it goes on.
- Runs the three connection scripts: `meta_auth.py` (Instagram + Facebook), `threads_auth.py` (Threads) and `youtube_auth.py` (YouTube). They open approval pages in your own browser when needed, write the tokens into `.env`, and never print a token or a secret.
- After your restart, checks every platform and asks whether you want your numbers on the vibedna.ai panel.

### Rules for the assistant

1. **Run every command and script in this guide yourself, after showing it.** None of them prints a secret. `meta_auth.py`, `threads_auth.py` and `youtube_auth.py` hide tokens in everything they print and only report names, ids, and which values are missing.
2. **Never ask for a key, token, password, or app secret in the chat.** Say where the value is and which line of `.env` it goes on. The person pastes it.
3. **Never open, read, print, or summarize `.env` or any token file.** The scripts read `.env`; you read what the scripts print.
4. **On the manual path, never drive a logged-in browser to copy tokens or regenerate keys.** The scripts open approval pages in the person's own browser, and the person clicks. On the assisted path only WebLoom's recipe does that, after the person's yes.
5. If the person pastes a secret into the chat anyway, do not repeat it, and suggest they regenerate it on that platform.
6. You cannot restart Social Brain yourself. Ask the person once, after all values are in `.env` (in Claude Code: `/mcp` and reconnect social-brain, or exit and start `claude` again).

### Step 3: Create `.env` (AI)

If `social-brain-mcp/` has no `.env`, create it with this template. Every value is empty, so it holds no secret. If a `.env` already exists, leave it as it is and do not open it.

```env
# Licence (from your purchase email)
MCPIZE_LICENSE_KEY=

# Meta: paste these three; meta_auth.py fills the page values
META_APP_ID=
META_APP_SECRET=
META_USER_TOKEN=

# Twitter / X
TWITTER_BEARER_TOKEN=
TWITTER_CONSUMER_KEY=
TWITTER_CONSUMER_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=

# Threads: paste the app values; threads_auth.py fills the rest
THREADS_APP_ID=
THREADS_APP_SECRET=
THREADS_REDIRECT_RESULT=

# Optional: AI writing tools
ANTHROPIC_API_KEY=

# Optional: ffmpeg path if it is not on PATH
# FFMPEG_BIN=
```

### Step 4: Connect each platform

Run each connection script named below with the `.venv` Python, from the folder that holds `server.py`: `.venv/bin/python <script>` (Windows: `.venv\Scripts\python.exe <script>`).

Go one platform at a time. `AUTH-GUIDE.md` (also `AUTH-GUIDE.pdf`) has every click in detail, with the permissions each feature needs.

#### Licence

**You:** paste the key from your purchase email into `MCPIZE_LICENSE_KEY=`. It starts with `vbd_`, and it is also in your library at vibedna.ai/library. The free tools work without it.

#### Instagram + Facebook (about 20 clicks, 3 pastes)

Needs an Instagram Business or Creator account linked to a Facebook Page. No Facebook Page? Connect Instagram alone with an Instagram token instead: AUTH-GUIDE.md, "Connect an Instagram account without a Facebook Page" (your AI runs `python meta_auth.py --instagram-login`).

**You:**
1. developers.facebook.com: **My Apps > Create App**, pick **Other**, then **Business**, give it a name, **Create app**.
2. **App settings > Basic**: paste the **App ID** into `META_APP_ID=` and the **App Secret** (click Show) into `META_APP_SECRET=`.
3. **Tools > Graph API Explorer**: pick your app, set **User Token**, add the permissions `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` (and `pages_manage_posts` to post to Facebook too), click **Generate Access Token** and approve.
4. Copy the token from the Access Token field into `META_USER_TOKEN=`. It lasts about two hours, so tell your AI right away.

**Your AI:** runs `python meta_auth.py`. It turns the token into a permanent Page token and writes `META_PAGE_TOKEN`, `META_PAGE_ID` and `META_IG_ACCOUNT_ID` into `.env`. If the token manages several Pages, the script lists their names, ids and Instagram handles: ask which one, then run `python meta_auth.py --page <Page id>`. For a second account, add `--account <name>` (the tools then take `account="<name>"`).

#### Twitter / X (about 15 clicks, 5 pastes)

**You:**
1. developer.x.com (formerly developer.twitter.com): open or create your Project and App.
2. **User authentication settings > Set up**: **Read and Write**, type **Web App, Automated App or Bot**, callback `https://localhost/callback`, your website, **Save**. Do this before item 3 of this list: a token made while the app was read-only stays read-only.
3. **Keys and Tokens**: **Regenerate** the Consumer Keys, **Generate** the Access Token and Secret, and **Generate** the Bearer Token. Paste the five values into the five `TWITTER_` lines.

X charges for posting through its API: check the plan or credits under Billing in the developer console.

**Your AI:** nothing to run. After the restart it checks with `get_twitter_profile`.

#### Threads (about 12 clicks, 3 pastes into `.env` and 1 into a Meta form)

**You:**
1. Open threads.net once with your account, so the Threads profile exists.
2. In your Meta app: **Use cases > Add use case > Access the Threads API**. In its permissions, add `threads_content_publish`, `threads_manage_replies` and `threads_read_replies` (`threads_basic` is already there).
3. In that use case's **Settings**: paste `https://localhost:8765/threads-callback` under **Redirect Callback URLs** and save. Paste the Threads **App ID** and **App Secret** into `THREADS_APP_ID=` and `THREADS_APP_SECRET=`.
4. When your AI opens the approval page, approve. The browser then shows an error page; that is expected, nothing runs at that address. Copy the full address from the address bar into `THREADS_REDIRECT_RESULT=`.

**Your AI:** runs `python threads_auth.py start` (opens the approval page for item 4 above), waits for you to paste the address, then runs `python threads_auth.py finish`. That writes `THREADS_ACCESS_TOKEN` and `THREADS_USER_ID` and removes `THREADS_REDIRECT_RESULT`. The token lasts 60 days; `python threads_auth.py refresh` extends it.

#### YouTube (about 20 clicks, no pastes)

**You:**
1. console.cloud.google.com: **New Project**, name it, **Create**.
2. **APIs & Services > Library**: find **YouTube Data API v3**, **Enable**.
3. **OAuth consent screen**: user type **External**, an app name and your email, then add your own email as a **test user**.
4. **Credentials > Create credentials > OAuth client ID > Desktop app > Create > Download JSON.** Leave the file in your Downloads folder.
5. When your AI opens the Google approval page: pick the account that owns the channel, and approve. If Google says "This app isn't verified", click **Advanced**, then continue (it is your own app).

**Your AI:** runs `python youtube_auth.py`. It finds the file in Downloads, opens the approval page for item 5 above, and waits up to 10 minutes (give the command at least that long, or run it in the background). The token is saved to `tokens/token.json`; no `.env` line is needed. More channels: `python youtube_auth.py --account <name>`.

#### Anthropic (optional, about 3 clicks, 1 paste)

**You:** console.anthropic.com > **API Keys > Create Key**, paste it into `ANTHROPIC_API_KEY=`. Only the AI writing tools use it (`generate_caption`, `generate_content_ideas`, `research_trending`, `analyze_competitor_account` and similar).

### Step 5: Restart once, then check (you, then AI)

**You:** restart Social Brain so it loads `.env`: in Claude Code, run `/mcp` and reconnect social-brain, or exit and start `claude` again.

**Your AI, first:** `claude mcp get social-brain` shows it connected. Then it calls `get_project`, which needs no key and only reads local state: a good answer is a short JSON with `active_project` set to `(default/shared)` and a `state_dir` ending in `.social-brain`.

**Your AI, then:** checks each platform you set up:

- Instagram + Facebook: `get_account_stats` (and `get_account_stats(account="<name>")` for extra accounts)
- Twitter / X: `get_twitter_profile` with your handle
- Threads: `list_inbox_threads`
- YouTube: `get_youtube_stats`

Each answers with real numbers, or names the value that is missing or refused. Fix that platform in Step 4 and restart again.

### Optional: the panel on vibedna.ai (AI asks once)

Social Brain can show the bots' numbers in the owner's own account at vibedna.ai. **It is off until the owner says yes.** Until then, nothing about their accounts is sent to vibedna.ai. Ask plainly:

> *"Your bots run here, on your computer. If you want, their numbers can also show in your account at vibedna.ai. Nothing is sent unless you say yes. Turn it on?"*

- **Yes:** call `panel_connect(on=True, project="<project name>")`. It publishes once right away, so the owner can go and look.
- **No:** call `panel_connect(on=False)`. Everything else works the same, and the panel stays empty.

**What is sent when it is on**, for each project, and nothing more:

- the project name and the Instagram handle set in its engage config
- the niche tags
- the daily caps (engagement, follows, DMs, likes, cooldown days, follow ramp)
- each lane's schedule and the date it was installed
- counts per day for the last 14 days (actions, likes, follows)
- running totals (actions, people found and touched, likes, follows, DMs sent, followers seen)
- whether the follow counts have been checked against Instagram
- the time of the report and the name of the state file the numbers came from
- your licence key, in a request header, so the site knows which account the numbers belong to

Never sent: tokens, passwords, your computer's name, the handles of the people the bots interacted with, or the text of comments and DMs. The numbers are stored in the owner's account and are only visible when signed in to it. `panel_connect(on=False)` stops publishing at any time.

Separately from the panel, two things talk to vibedna.ai: the licence check sends your licence key and the product name to confirm the key, and `check_for_update` asks for the latest version number. Neither sends anything about your social accounts.

The Content Studio tools (`feed_publish_snapshot`, `drip_apply_feed_order`, `drip_apply_feed_captions`, `feed_pending_deletions`, `feed_apply_deletions`) talk to the studio only when you call them, with a studio token you set yourself (`STUDIO_TOKEN`). `feed_publish_snapshot` sends one drip's queue (each post's first caption line, time, status and channels, plus preview thumbnails) and the first caption line, thumbnail and link of your recent Instagram posts.

## Start prompt

After installing, paste the start prompt into your AI. It is in the zip as `START_PROMPT.md` and at https://vibedna.ai/prompts/social-brain.md.

## Uninstall

1. Remove any schedules first with `bot_uninstall` and `poster_uninstall`.
2. `claude mcp remove social-brain -s user`
3. Delete the unzipped folder (it holds `.env` and `tokens/`), `~/.social-brain/` and `~/.vibedna/license_cache.json`. If you installed schedules, also their log files (`lane_*.log`, `engage_bot.log`, `drip_runner.log` in your home folder); if you set `SB_HOME` or `SB_DROP_DIR`, those folders; if you used a browser lane, the lock folder (`/tmp/browser-locks` by default). Nothing else was written.

## If something fails

- **"Failed to connect" right after installing (mostly Windows):** the first start can take a minute or two while the antivirus reads the new files, longer than Claude Code waits; later starts take seconds. In the folder that holds `server.py`, load it once, `.venv\Scripts\python.exe -c "import server"` (macOS/Linux: `.venv/bin/python -c "import server"`), then restart Claude Code.
- **Python older than 3.10** (or `py` not found: try `python`): install a current one from python.org, delete `.venv`, repeat step 1.
- **"No module named ...":** the entry points at another Python. Remove it and register again with the `.venv` Python.
- **A tool asks for a licence or names a missing value:** fill that line in `.env`, then restart.
- **Old tools still show:** an earlier entry is still registered. See "Only if you installed an earlier version" under step 2.
