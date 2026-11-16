# JesterDNA: Install for Claude

**Hi Claude, this is a JesterDNA MCP installer. Read this whole file, then walk the user through the install. Do every step yourself with your tools. The user only types when they need to paste a key.**

JesterDNA is a 20-source research engine. The user just bought it. Your job is to get it running in their Claude Code in under 5 minutes.

---

## Before you start: quick environment check

Run these in parallel and tell the user the results:

1. `python --version` (or `python3 --version`): JesterDNA needs Python 3.10 or newer.
2. `pip --version`: confirm pip is on PATH.
3. Locate the user's Claude project root, the folder that contains (or should contain) a `.mcp.json` file. If unsure, ask: *"Which project folder do you want JesterDNA available in? Paste the full path."*

If Python is < 3.10 or pip is missing, **stop and tell the user** to install Python from python.org before continuing.

---

## Step 1: Place the JesterDNA folder

The buyer downloaded a zip. Inside is a folder called `jester-mcp/`. Help them put it somewhere stable.

**Recommended location:**
- macOS / Linux: `~/.local/share/jester-mcp/`
- Windows: `C:\Users\<name>\AppData\Local\jester-mcp\`

If they prefer somewhere else (e.g. inside their project repo), respect that. Just remember the absolute path. You'll wire it into `.mcp.json` in Step 4.

Confirm with the user where they unzipped it. Use that path going forward.

---

## Step 2: Install Python dependencies

From the `jester-mcp/` folder, run:

```bash
pip install -r requirements.txt
```

This installs ~250MB of dependencies. Show the user the tail of the install output so they can confirm it worked. **No CLI tools (ffmpeg, OpenAI Whisper, etc.) need to be installed separately**. `faster-whisper` ships its own decoder.

If `pip` complains about Python version, fall back to `python -m pip install -r requirements.txt`.

If they're in a managed-environment OS (e.g. Ubuntu with PEP 668), use a venv:

```bash
python -m venv venv
source venv/bin/activate     # macOS/Linux
# OR
venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
```

Remember the python binary path inside the venv. You'll use it in Step 4.

---

## Step 3: Collect API keys from the user

Ask the user for each of these. **Mark each as REQUIRED or OPTIONAL.** Don't prompt for them all at once. Ask one at a time so the user can grab each.

| Key | Status | What it does |
|---|---|---|
| `MCPIZE_LICENSE_KEY` | **REQUIRED** for Pro | The JesterDNA Pro license key. It starts with `vbd_`, arrives in the purchase email and is also in the user's library at https://vibedna.ai/library. Without it, Jester runs its free tier. |
| `ANTHROPIC_API_KEY` | OPTIONAL | Only needed for autonomous synthesis. Most users skip this: Claude in the chat does the synthesis on the user's existing subscription. |
| `EXA_API_KEY` | OPTIONAL | Unlocks Exa neural deep-search. Free tier at exa.ai. |
| `FIRECRAWL_API_KEY` | OPTIONAL | Unlocks Firecrawl deep page crawl. Free tier at firecrawl.dev. |

For each key the user provides, write it into a new `.env` file inside the `jester-mcp/` folder:

```
MCPIZE_LICENSE_KEY=<paste here>
ANTHROPIC_API_KEY=<optional>
EXA_API_KEY=<optional>
FIRECRAWL_API_KEY=<optional>
```

Set permissions to `600` on macOS/Linux (`chmod 600 .env`). On Windows, the file is already user-scoped.

**Never** paste any key back to the user once collected.

---

## Step 4: Wire into Claude's `.mcp.json`

Open the user's project `.mcp.json` (the one they pointed you at in the pre-flight). If the file doesn't exist, create it with:

```json
{ "mcpServers": {} }
```

Add JesterDNA inside `mcpServers`. Use the absolute path to the user's Python (or venv python) and to `server.py`:

```json
"jester": {
  "type": "stdio",
  "command": "<ABSOLUTE PATH TO PYTHON>",
  "args": [
    "<ABSOLUTE PATH TO jester-mcp/server.py>"
  ],
  "env": {
    "MCPIZE_LICENSE_KEY": "<the license key>"
  }
}
```

**Important:** on Windows, use double-backslashes in JSON strings (`C:\\Users\\name\\...`). On macOS/Linux, use forward slashes.

If the user is on a Mac and `which python3` returns something like `/usr/bin/python3` but they used a venv, use the venv path (`<jester-mcp>/venv/bin/python`). That's the one with all the deps.

Show the user the final `.mcp.json` before you write it so they can sanity-check.

---

## Step 5: Restart the Claude tab

Tell the user: **"Close this Claude Code tab completely and reopen it. The MCP only loads on session start."**

After they reopen, you (in the new session) won't have the install context anymore, but the user can just type `/whoami` or call any `mcp__jester__` tool to confirm JesterDNA loaded.

---

## Step 6: Smoke test in the new session

In the new session, ask the user to type:

```
Run a JesterDNA search on "best vibe coding tools"
```

If it works, they'll see 25 results with a systematic brief. **Tell them: "JesterDNA is live. Try `mcp__jester__research_topic("anything", depth="deep")` to see the full power."**

If it fails, the most common issues:
- License key missing or not valid → Jester still loads and runs its free tier: free tools work, Pro tools answer with an upgrade message. Check that `MCPIZE_LICENSE_KEY` holds the key from the purchase email (it starts with `vbd_`, and is also at https://vibedna.ai/library), then restart the tab.
- Python path wrong in `.mcp.json` → the MCP doesn't appear at all (run `claude mcp list` to confirm)
- Old Python (< 3.10) → import errors on FastMCP

---

## Updating to a new version

After unzipping a new version over the old folder, close the AI app and wait up to 30 minutes before reopening it: Jester's background process keeps running the old version until it exits on its own after 30 minutes without use (restarting the app alone does not stop it). To skip the wait, stop it with the "Force restart" command in `DAEMON_README.md` (Windows) or `pkill -f jester-daemon` (macOS/Linux).

---

## Optional polishes the user might want

- **Disable Whisper if they want a leaner install:** add `JESTER_WHISPER_MAX_SECONDS=0` to `.env`. Captions still work; only the local-Whisper-fallback path is disabled.
- **Pick a smaller embedding model:** add `JESTER_WHISPER_MODEL=tiny` to `.env` (default is `base`, ~75MB).
- **Cap daily synthesis spend** (only if they set `ANTHROPIC_API_KEY`): `JESTER_DAILY_LIMIT=1.00` (USD).

---

## When you're done

Send a clean summary to the user:

- ✅ JesterDNA installed at `<path>`
- ✅ Wired into `<.mcp.json>`
- ✅ License key set
- *(optional keys flagged)*
- 🎯 Restart Claude tab → run a test search

That's it. No background services, no port forwarding, no daemons the user has to manage. JesterDNA loads with the tab.

---

**One last thing for Claude (you):** If anything fails, don't loop. Stop, summarize what failed, ask the user one specific question, and wait. Bad installs become silent if you keep guessing.
