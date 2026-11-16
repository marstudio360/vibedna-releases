---
name: measure-dna-install
description: Install Measure DNA, the MCP your AI uses to read your store's real sales, payment drop-off, A/B tests, email leads, list mails, ads and who is on the site. Paste this file into your AI chat and ask it to install it. Your AI follows the steps below, shows every change first, and asks before it writes anything.
---

# Measure DNA: Install Drop

> **For the AI assistant reading this:**
>
> The user bought Measure DNA. This file is the install handbook. It is one Python MCP server that only READS
> the user's store data (their own database, and their ad account if they want ad numbers), and asks vibedna.ai to check the licence key. Walk the user through
> the steps at THEIR pace and show each command before you run it. The user writes every key themselves (the licence key
> into the MCP entry, the others into the settings file): never ask for a key in the chat and never print the settings file. Every action is reversible (see the
> table). If anything looks wrong or the user wants to stop, stop: nothing here changes their store.

You bought Measure DNA. This single `.md` is everything your AI needs to install it. The download also carries
`INSTALL.md` with every setting in full, `START_PROMPT.md`, and `license_gate.py` (the licence check).

Not bought yet? Get it at https://vibedna.ai/store/measure-dna. It also comes inside the Store System.

## Start prompt

After installing, paste the start prompt into your AI: https://vibedna.ai/prompts/measure-dna.md

---

## TL;DR: what this product is

**Your AI reads your store every day: real sales next to ad spend, and where buyers leave.**

1. **Real numbers from your own data:** sales per day from your purchases table next to ad spend and what the ad
   platform claims, when and where your ad sales happen (week against week, each campaign, countries, weekday and
   hour), the step where each visitor leaves the payment and what each person who opened it actually did (with what
   your payment processor recorded: email typed, a payment tried, declined by the bank), which test version sells more (with an honest
   "too few to decide"), what happened to every email that did not buy, how a list mail did, and who is on the
   site right now.
2. **The same reading every time:** test visits and robots are left out, every number says where it came from, and
   any reading can start at the exact minute of a change.

| | |
|---|---|
| **Price** | $47 one time, updates included |
| **Where it runs** | On your machine (a Python MCP server: `server.py`, plus `license_gate.py` for the licence check) |
| **What it reads** | Your store's `events`, `purchases` and `mail_log` tables (Supabase or any PostgREST), and optionally your Meta ad account, your Resend audience and your Stripe subscriptions |
| **What it changes** | Nothing. It only reads |
| **Needs** | Python 3.10+, your Vibedna licence key, a store that writes those tables (the Store System kit does; any store with the same columns works) |
| **Touch surface** | One MCP server entry in your AI app, `~/.measure-dna/config.json`, `~/.vibedna/license_permits.json` (the licence permit) |

---

## Install (let your AI do it)

1. Get the download. With the Vibedna connector, ask your AI: "get the download for Measure DNA". Otherwise open
   your library at https://vibedna.ai/library. Unzip it somewhere stable, for example `~/vibedna/measure-dna/`
   (Mac/Linux) or `C:\Users\<you>\vibedna\measure-dna\` (Windows).
2. Open your AI app **in that folder**. Paste **this whole file** in, then say:

   > "Install Measure DNA from this folder. Show me each command first, and tell me which settings I need."

3. Your AI runs these steps (on Windows `.venv/bin/` is `.venv\Scripts\` and `python3` is `py`):

   **Step 1. A private Python for the tool**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   **Step 2. The settings file.** Create `~/.measure-dna/config.json`. Your AI tells you which keys you need and where
   to find each value (`INSTALL.md` section 2); you write the values yourself. The minimum:
   ```json
   {
     "supabase_url": "https://YOUR-PROJECT.supabase.co",
     "supabase_key": "YOUR-SERVICE-ROLE-KEY",
     "utc_offset_hours": -3,
     "thankyou_prefix": "/library"
   }
   ```
   Add `meta_token` and `meta_ad_account` for ad numbers, `test_email_patterns` for the emails you test with, and
   `access_lookup` / `access_labels` if you sell plans or memberships (so `who_is_here` can say what each person holds).

   **Step 3. Add it to your AI app, with your licence key.** Your Vibedna licence key: it starts with `vbd_` and is in your purchase email from Vibedna; with a membership it is in the email that welcomed you to the plan, and it works while the plan is active. The tool reads it from `MCPIZE_LICENSE_KEY` in the entry's `env`; you type it yourself, in your own editor or terminal, never in the chat. In the app's MCP config, with the `.venv` Python by its full path:
   ```json
   { "mcpServers": { "measure-dna": { "command": "<folder>/.venv/bin/python", "args": ["<folder>/server.py"],
     "env": { "MCPIZE_LICENSE_KEY": "vbd_..." } } } }
   ```
   In Claude Code, you run this line yourself: `claude mcp add measure-dna -e MCPIZE_LICENSE_KEY=vbd_... -- <folder>/.venv/bin/python <folder>/server.py`.

   **Step 4. Restart the AI app** so the server loads.

---

## Verify the install

- Every tool needs your licence key. Without a valid one, each answers only with an error that starts "Measure DNA needs a valid licence key" and says where to put it.
- Ask your AI to run `setup_status`. The database says `ok`; every optional source you set says `ok` or `set`.
- Ask: `sales_by_day(days=7)`. It answers with your real sales per day.
- Without an AI app: `.venv/bin/python server.py --ask setup_status` prints the same answer once `MCPIZE_LICENSE_KEY` is set in that terminal, typed by you (`export MCPIZE_LICENSE_KEY=vbd_...`; Windows PowerShell: `$env:MCPIZE_LICENSE_KEY="vbd_..."`). The `env` of the MCP entry does not reach a terminal.

If something is missing: did you restart the AI app after step 3? Is `config.json` valid JSON (a broken file stops
the tools with an error that names it)? Is the `.venv` Python the one in the config? Is `MCPIZE_LICENSE_KEY` in the `env` of the entry?

---

## Reversible-actions table

| Step | What it does | How to undo |
|---|---|---|
| Unzip | A folder with `server.py`, `license_gate.py`, `INSTALL.md`, `START_PROMPT.md` and `tools/pay_robot.py` | Delete the folder |
| `.venv` + `pip install -r requirements.txt` | A private Python inside that folder | Delete `.venv` |
| `config.json` | Your settings and keys in `~/.measure-dna/` | Delete `~/.measure-dna/` |
| Licence permit | `~/.vibedna/license_permits.json`: the signed answer from vibedna.ai that your key is valid (not the key itself, only a short one-way hash of it) | Delete the file (other Vibedna products may use it too) |
| MCP config entry | The `measure-dna` server in your AI app, with your licence key | Remove the entry (`claude mcp remove measure-dna` in Claude Code) |
| Payment robot (optional) | `pip install playwright` and its browsers, then test purchases on your store in test mode | `pip uninstall playwright`; refund or delete the test purchases in your test account |

**No service accounts of ours. No telemetry.** It talks only to your own database and the services you set keys for, plus one licence check.

**The licence check** (`license_gate.py`). It reads your key from `MCPIZE_LICENSE_KEY` and asks `https://vibedna.ai/api/license/validate` (HTTPS POST) when a tool first runs, then again every 12 hours while the machine is online. It sends your licence key, the product name and a 16 character machine id (a one-way hash made from the computer's name, system and network card number; it cannot be read back), nothing else: nothing about your store, your sales or your buyers. The site answers with a signed permit that the file checks with the public key it carries, stored in `~/.vibedna/license_permits.json` (not the key itself, only a short one-way hash of it; `VIBEDNA_HOME` moves that folder). Offline, the tools keep working until that permit expires: about three days for a key that lives on a subscription, about a year for a key bought once.

---

## Uninstall

Remove the `measure-dna` entry from your AI app's MCP config, then delete the folder, `~/.measure-dna/` and, unless another Vibedna product still uses it,
`~/.vibedna/license_permits.json`. Nothing else was changed on your machine or in your store.

## Support

- `admin@vibedna.ai`
- https://vibedna.ai

Latest version and install drop: https://vibedna.ai/installs/measure-dna.md

Vibedna, 2026
