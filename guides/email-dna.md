---
name: email-dna-install
description: Install Email DNA, the MCP your AI uses to run a store's email safely: one send gate where every mail is checked, previewed and sent only after your approval, list hygiene, a campaign calendar, automations, a support inbox with buyer context, results with sales per mail, and monitoring of complaints, bounces, your domain and Gmail's spam rate. Paste this file into your AI chat and ask it to install it. Your AI follows the steps below, shows every change first, and asks before it writes anything.
---

# Email DNA: Install Drop

> **For the AI assistant reading this:**
>
> The user bought Email DNA. This file is the install handbook. It is one Python MCP server that runs on the user's
> machine and talks only to their own email provider (Resend today), their own database or mailbox if they connect
> one, public DNS, Google Postmaster Tools if they set it up, and vibedna.ai to check the licence key. Walk the user through the steps at THEIR pace and
> show each command before you run it. The user writes every key themselves: never ask for a key in the chat and
> never print the settings file. Nothing is ever sent during the install. Every action is reversible (see the
> table). If anything looks wrong or the user wants to stop, stop.

You bought Email DNA. This single `.md` is everything your AI needs to install it. The download also carries
`INSTALL.md` with every setting in full, `START_PROMPT.md`, `license_gate.py` (the licence check), and the tests.

Not bought yet? Get it at https://vibedna.ai/store/email-dna.

## Start prompt

After installing, paste the start prompt into your AI: https://vibedna.ai/prompts/email-dna.md

---

## TL;DR: what this product is

**Every store mail checked and approved by you before it leaves, then watched for spam and bounces.**

1. **One gate for every mail:** it checks each recipient (unsubscribed, bounced, marked an earlier mail as spam,
   already mailed today, invalid) and the mail itself (unfilled placeholders, broken links, missing unsubscribe
   link, untracked offer links), writes a phone and desktop preview, and sends only after a human approves it.
   It never sends the same mail twice to one person.
2. **Everything around it:** list hygiene (typos, role, throwaway and bot addresses, people who never open), a
   campaign calendar with clash checks and a simulation of who gets each mail, one call that tells you the last list mail that went out and the next one
   (it can also read a calendar your own scheduler keeps), automations (welcome, abandoned
   checkout, win-back, after purchase), a support inbox with what each buyer bought, results per mail with the
   sales after it, and monitoring against the Gmail and Yahoo limits.

| | |
|---|---|
| **Price** | $47 one time, updates included |
| **Where it runs** | On your machine (a Python MCP server), or from a terminal or cron without an AI app |
| **What it talks to** | Your email provider (Resend today), public DNS, vibedna.ai to check your licence key, and only if you set them: your database or mailbox (read only), Stripe (read only), Google Postmaster Tools |
| **What it changes** | It sends the mails you approve, and suppresses or unsubscribes people only when you say so. Nothing else |
| **Needs** | Python 3.10+, your Vibedna licence key, a Resend account (free plan works) with your sending domain |
| **Touch surface** | One MCP server entry in your AI app, `~/.email-dna/` (settings, local store, previews), `~/.vibedna/license_permits.json` (the licence permit) |

---

## Install (let your AI do it)

1. Get the download. With the Vibedna connector, ask your AI: "get the download for Email DNA". Otherwise open
   your library at https://vibedna.ai/library. Unzip it somewhere stable, for example `~/vibedna/email-dna/`
   (Mac/Linux) or `C:\Users\<you>\vibedna\email-dna\` (Windows).
2. Open your AI app **in that folder**. Paste **this whole file** in, then say:

   > "Install Email DNA from this folder. Show me each command first, and tell me which settings I need."

3. Your AI runs these steps (on Windows `.venv/bin/` is `.venv\Scripts\` and `python3` is `py`):

   **Step 1. A private Python for the tool**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   **Step 2. Three keys, written by you.** `MCPIZE_LICENSE_KEY`, your Vibedna licence key. It starts with `vbd_` and is in your purchase email from Vibedna; with a membership it is in the email that welcomed you to the plan, and it works while the plan is active. Then `RESEND_API_KEY` from resend.com/api-keys, and `EMAIL_DNA_LINK_SECRET`, a
   long random string that signs your unsubscribe links. Make it once and keep it (links already sent stop working
   if it changes):
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   **Step 3. The settings file.** Create `~/.email-dna/config.json`. Your AI tells you which keys you need and
   where to find each value (`INSTALL.md` section 2). The minimum:
   ```json
   {
     "from_addr": "Your Store <hello@yourstore.com>",
     "reply_to": "hello@yourstore.com",
     "own_domains": ["yourstore.com"],
     "utc_offset_hours": 0,
     "audience_id": "<Resend audience id of your list>",
     "owner_email": "you@yourstore.com",
     "unsubscribe_url": "https://yourstore.com/unsubscribe?e={email}&t={token}"
   }
   ```
   Add the optional parts only when you want them: `tracking` (your click tracker), `inbox` (support mail, read
   only), `buyer_lookup` (purchases, for buyer context and sales per mail), `events_source`, `postmaster` (Gmail's
   spam rate) and `flows.json` (automations).

   **Step 4. Add it to your AI app.** In the app's MCP config, with the `.venv` Python and `server.py` by their
   full paths and your three keys in `env`, typed by you in your own editor or terminal, never in the chat:
   ```json
   { "mcpServers": { "email-dna": { "command": "<folder>/.venv/bin/python", "args": ["<folder>/server.py", "--stdio"],
     "env": { "MCPIZE_LICENSE_KEY": "vbd_...", "RESEND_API_KEY": "re_...", "EMAIL_DNA_LINK_SECRET": "<your secret>" } } } }
   ```
   In Claude Code, you run this line yourself: `claude mcp add email-dna -e MCPIZE_LICENSE_KEY=vbd_... -e RESEND_API_KEY=re_... -e EMAIL_DNA_LINK_SECRET=<your secret> -- <folder>/.venv/bin/python <folder>/server.py --stdio`.

   **Step 5. Restart the AI app** so the server loads.

---

## Verify the install

- Every tool in your AI app needs your licence key. Without a valid one, each answers only with an error that starts "Email DNA needs a valid licence key" and says where to put it.
- Ask your AI to run `vibedna_info`: every tool group under `modules_loaded`, nothing under `modules_failed`.
- Ask: `check_domain` for your sending domain, then `health_report(days=30)`. It answers with your domain records
  and your complaint and bounce rates against the limits.
- Ask it to `queue_mail` a TEST mail to your own address and show you the preview page. Do not approve it: you
  just proved nothing leaves without you.
- Without an AI app: `.venv/bin/python -m emaildna.cli mail_provider` prints the same kind of answer.
- The tests run offline: `.venv/bin/pip install pytest` then `.venv/bin/python -m pytest tests -q`.

If something is missing: did you restart the AI app after step 4? Is `config.json` valid JSON (a broken file stops
the tools with an error that names it)? Is the `.venv` Python the one in the config? Are all three keys in the `env`
of the entry?

---

## Reversible-actions table

| Step | What it does | How to undo |
|---|---|---|
| Unzip | A folder with `server.py`, `license_gate.py`, `emaildna/`, `INSTALL.md`, `START_PROMPT.md` and `tests/` | Delete the folder |
| `.venv` + `pip install -r requirements.txt` | A private Python inside that folder | Delete `.venv` |
| `config.json` and the local store | Your settings, the approval queue, previews and the sent log in `~/.email-dna/` | Delete `~/.email-dna/` |
| Licence permit | `~/.vibedna/license_permits.json`: the signed answer from vibedna.ai that your key is valid (not the key itself, only a short one-way hash of it) | Delete the file (other Vibedna products may use it too) |
| MCP config entry | The `email-dna` server in your AI app, with your three keys | Remove the entry (`claude mcp remove email-dna` in Claude Code) |
| Cron lines (optional) | `watch_mail` and `run_due_campaigns` on a schedule | Remove the lines |

**No service accounts of ours. No telemetry.** It talks only to your email provider and the services you set keys for, plus one licence check.

**The licence check** (`license_gate.py`). It reads your key from `MCPIZE_LICENSE_KEY` and asks `https://vibedna.ai/api/license/validate` (HTTPS POST) when a tool first runs, then again every 12 hours while the machine is online. It sends your licence key, the product name and a 16 character machine id (a one-way hash made from the computer's name, system and network card number; it cannot be read back), nothing else: nothing about your mail, your list or your buyers. The site answers with a signed permit that the file checks with the public key it carries, stored in `~/.vibedna/license_permits.json` (not the key itself, only a short one-way hash of it; `VIBEDNA_HOME` moves that folder). Offline, the tools keep working until that permit expires: about three days for a key that lives on a subscription, about a year for a key bought once.

---

## Uninstall

Remove the `email-dna` entry from your AI app's MCP config and any cron lines, then delete the folder,
`~/.email-dna/` and, unless another Vibedna product still uses it, `~/.vibedna/license_permits.json`. Your provider account, your list and your domain stay as they are.

## Support

- `admin@vibedna.ai`
- https://vibedna.ai

Latest version and install drop: https://vibedna.ai/installs/email-dna.md

Vibedna, 2026
