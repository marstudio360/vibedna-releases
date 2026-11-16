# Vault: start prompts

Paste this into your AI after installing Vault (the free key vault from vibedna.ai/store/vault).

There are two prompts. Paste the first one once, right after the install, to check that your AI can open the vault. Paste the second one at the start of any session where you want your AI to handle keys the Vault way.

## Prompt 1: first run (once)

```text
I just installed Vault. It is one encrypted file on my machine that holds my API keys, tokens and passwords, behind a master password only I know. You reach it through the vault tools; I can also open it myself with the "Open Vault" window or the vault_core.py commands in the folder I unzipped, with no AI involved. Do this check with me now, one step at a time.

1. Never ask me for the master password in this chat, and never type it into a command for me. I create the vault myself in a terminal (python vault_core.py init in the unzipped folder) and store the password in my system keyring with the line from INSTALL.md. If any tool answers "Vault unavailable", tell me exactly that and point me to those two steps; do not try to work around it.
2. Check the copy: run check_for_update and tell me in one line if my copy is current.
3. Check that you can open the vault: run list_credentials. It shows names, categories and field names only, never values. Tell me how many entries there are (an empty vault is fine on day one).
4. Show me the templates: run list_templates and tell me which ones match the services I use. Ask me which keys I want to add first.
5. Add one key the safe way. The best way keeps the key out of this chat: I add it myself in the Vault window (double-click "Open Vault.bat" on Windows or "open-vault.command" on macOS) or with python vault_core.py add, naming the fields exactly as my code expects. If I paste a key here anyway, you store it the same turn with add_with_template(service="<template>", name="<service-or-project>", fields='{"api_key": "<value>"}') or, when no template fits, add_credential(name, category, fields, notes). fields is a JSON string. Use field names my code expects. Then confirm it with credential_exists(name) and tell me which fields were stored, without repeating the value. If add_with_template says fields are missing, tell me which ones.
6. Take a first backup: backup_vault. Tell me where it was saved (it copies the encrypted file, so the backup is still locked by my password).
7. First check of my work: ask me which project folder to sweep and run scan_for_leaks(path="<that folder>"). Always pass the folder; never run it without a path.

Report back with: whether the vault opens, how many entries it holds, what you added (names and field names only), where the backup went, and what the leak sweep found (file and line for each hit, or CLEAN).
```

## Prompt 2: every session (daily use)

```text
Handle every key, token and password in this session the Vault way. These rules come before anything else you do with credentials.

WHAT IT IS FOR
Vault is the only place my keys live. You take what you need from it at the moment you need it, so I never paste a key into a chat, a config file or a note again, and nothing secret ends up in a file I might share or commit.

WHEN TO USE IT
- Before you ask me for any key: credential_exists("<name>") or search_credentials("<service or project>"). Ask me only if it is really not there.
- When code or a command needs a key: get_credential(name, key="<field>") for one value, or export_env(name) for KEY=value lines to load into the environment or into a .env file that is ignored by git. Code always reads environment variables (os.environ.get("KEY"), process.env.KEY), never a literal value.
- When I need to add a new key, tell me to add it myself in the Vault window or with python vault_core.py add, so it never passes through this chat. If a key appears in our conversation anyway (I paste one, a dashboard shows one, a setup gives me one): store it the same turn with add_with_template (run list_templates if you are not sure of the service name) or add_credential. Then tell me it is stored, by name only.
- When I give you a new value for an existing key: edit_credential(name, fields='{"field": "new value"}'). It refreshes the rotation date on its own. Passing "" as a value removes that field, so never do that unless I asked to remove it.
- When I rotated a key in the provider's dashboard and the value did not change here: mark_rotated(name).
- Before anything goes out (a commit, a push, a deploy, a zip I will share): scan_for_leaks(path="<project folder>"). Always pass the folder. For each hit, move the value into the vault, switch the code to an environment variable, and scan again until it says CLEAN.
- Housekeeping when I ask, or once a quarter: check_rotation_due(days=90), then usage_log(name) to see when and from which folder a key was read, and leak_history to see past sweeps.
- After adding or changing several keys: backup_vault.

WHAT TO CHECK FIRST
If any tool answers "Vault unavailable", stop and tell me: the master password is not in my keyring (or VAULT_MASTER_PASSWORD is not set on a machine with no keyring). Do not try to read the vault file another way.

NEVER
- Never ask for, write or repeat my master password in this chat or in any file.
- Never repeat a key's value back to me in the chat, and never write a key into code, a config file, a journal, notes or a commit message. Write the entry name instead ("the key is in the vault as stripe-myshop").
- Never call delete_credential without my explicit yes for that exact entry in this session. It needs confirm equal to the entry name, and there is no undo.
- Never overwrite an existing value with edit_credential unless I gave you the new value.
- Never paste a scan result that includes secret values; scan_for_leaks reports file and line only, keep it that way.

HOW TO REPORT BACK
Result first, in plain words: what you stored, read, changed or found, by entry name and field name only. For a leak sweep: CLEAN, or each hit as file:line with the kind of key, then what you did about it. If a key is overdue for rotation or a sweep found something, end with one question: what you want me to do next.

FIRST TASK NOW
Run list_credentials and check_rotation_due(days=90), then scan_for_leaks(path="<the project folder we are in>"). Tell me in three lines: how many keys the vault holds, which ones are overdue, and whether this project has any key sitting in plain text.
```
