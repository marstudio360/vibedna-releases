# Game Assets: start prompts

Paste this into your AI after installing Game Assets.

There are two prompts. Paste the first one once, right after the install, to check both halves of the tool. Paste the second one at the start of any session where your game needs art, sound or words.

## Prompt 1: first run (once)

```text
I just installed Game Assets. It finds free game art I am allowed to ship, checks the licence of every pack, and when nothing free fits it can make the piece with my own provider keys, always asking me first. Check it with me now, one step at a time.

1. Check both halves. Run lanes_status. It should show the free-library lane (8 tools) and the generation lane (20 tools) as loaded. If a lane is missing or shows an error, tell me the error in plain words: usually the folders inside game-assets-mcp were moved, or the app needs a restart.
2. Check the library. Run library_stats. It shows the four shelves: 01-CLEAN-CC0 (ships anywhere), 02-CREDIT (ships with a credit line), 03-CHECK (needs a person to read the licence), 04-BLOCKED (for testing only, never ship). It is empty until the first harvest.
3. Check which keys I have. Run list_providers and tell me which providers are ready and which key each one needs. Searching the free libraries needs no key. Making images, sound and video needs FAL_KEY (or GEMINI_API_KEY for the image fallback). The tools that write words or look at an image (describe_image, generate_character_sheet, generate_story_arc, generate_dialog_tree) need a separate text-AI key: if one answers that a key is not set, tell me the exact variable name it asks for. Harvesting from itch.io needs ITCH_API_KEY. I add keys myself to the env block of this tool in my AI app's settings. Never ask me to paste a key into the chat.
4. First task, to prove it works, without spending anything: run discover(source="kenney") and show me the first packs it lists with what each listing claims about its licence. Then ask me if I want to harvest a few of them (harvest is free in money but downloads files to my disk).

Report back with: which lanes loaded, what is in the library, which providers are ready, and one question about what to do next.
```

## Prompt 2: every session (daily use)

```text
Get art, sound and words for my game with Game Assets. These rules come before anything else you do in this session.

WHAT IT IS FOR
Finding free art I may legally ship, putting it into my game project with the credits written, and, only when nothing free fits and I say yes, making the missing piece with my own paid provider keys.

WHEN TO USE IT
- When my game needs a sprite, a tileset, a character, an interface piece, a background, a sound or music: look in the free library first.
- When I need the game's words (a character class, a story, a conversation): use the writing tools, after I said yes to their cost.
- Before you hand me any art: check its licence shelf.

WHICH TOOLS, IN WHICH ORDER
Orient
- lanes_status: first call if any tool seems missing. A lane that failed to load hides its tools.
- library_stats: what the library holds, shelf by shelf.
- list_providers: which paid providers are ready and which key each needs.
Find free (no money spent)
1. find_or_generate(query, asset_type, output_dir, allow_paid=False): searches the free library first. asset_type is pixel_art, sprite_sheet, tileset, ui, sfx, music, background or image. With allow_paid=False it never spends: when nothing free matches it returns the exact paid call it would make. Keep allow_paid=False unless I said yes to that paid call.
2. search_packs(query, shelf, license, limit) and pack_info(slug): look closer at a pack, including the licence verdict and the exact phrase that decided it.
3. To grow the library: discover(source, query_or_tag, pages) lists packs without downloading (source is "itch", "opengameart" or "kenney"). harvest(source, query_or_tag, pages, max_packs) downloads them, reads each licence and shelves each pack. Harvest costs no money but takes time, network and disk space: tell me how many packs before you start. itch.io needs ITCH_API_KEY.
4. classify_license(text): checks any licence text I paste and says which shelf it would land on.
5. export_pack(slug, dest_dir, policy): copies a pack into my game project (dest_dir is a full path) and adds the credit line to CREDITS.md when the licence asks for one. policy "sellable_clean" ships only the clean shelf, "sellable_credited" (default) adds the credit shelf, "prototype" lets anything through for testing.
6. rebuild_gallery: rebuilds the browsable gallery of my whole library so I can look at the art.
Make new (PAID, on my own keys, only after my yes for each call)
- Pictures: generate_pixel_art, generate_sprite_sheet (frames of one motion), generate_character_set (a base sprite and its poses), generate_pose_variant, generate_tileset, generate_ui_element, generate_background, generate_character_portrait, generate_image, edit_image (change an image in plain words), remove_background.
- Sound: generate_audio_sfx, generate_music_loop, generate_voice_line.
- Video: generate_video (the most expensive, about 0.50 to 2 dollars a clip).
- Words: generate_character_sheet (a class with stats and abilities), generate_story_arc (a story from one line), generate_dialog_tree (a branching conversation; its format feeds a dialogue-tree system such as the one Godot Vibe writes).
- Looking: describe_image (describes an image so you check what was made instead of assuming).
Each of these tools states its rough cost in its own description. Every output path you pass is a full path inside my project.

WHAT TO CHECK FIRST
- lanes_status shows both lanes loaded, or you tell me which half is missing.
- For a paid call: the provider key it needs is set (list_providers), and I said yes to this exact call and its cost.

NEVER
- Never spend money without asking. Before any generate_*, edit_image, remove_background, describe_image or find_or_generate with allow_paid=True, show me what you will make, which provider and key it uses, and the cost the tool states, then wait for my yes. One yes covers one call or the batch I approved, nothing more.
- Never ship a pack from 03-CHECK or 04-BLOCKED, and never use policy "prototype" for something I will publish or sell. If export_pack refuses, tell me the reason; do not copy the files by hand around it.
- Never delete or edit CREDITS.md lines the tool wrote.
- Never ask me to paste a key into the chat, and never write a key into a file other than my AI app's settings.
- Never present generated frames as perfectly consistent: check them (describe_image after my yes, or show them to me) before calling them done.

HOW TO REPORT BACK
Result first, in plain words: what you found or made, where it is in my project, its licence shelf and whether a credit line was added, and what any paid call cost. If nothing free fit, say so and show the paid call you would make, then ask one question: make it or not.

FIRST TASK NOW
Run lanes_status and library_stats, then ask me what my game needs right now. For that piece, run find_or_generate with allow_paid=False and show me what came back. Spend nothing.
```
