> **Product manual.** This is the document this package shipped as `INSTALL.md` before the install guide moved into the zip. It is kept for what the install guide does not repeat: settings, accounts, tools and how to use them. To install, follow `INSTALL.md`. Where this file shows another way to install (a plain `pip install`, a settings entry written by hand, a key typed in the chat), `INSTALL.md` is the one to follow.

# Social Content Studio MCP: Install for Claude

**Paste this whole file into a chat with your AI and say "walk me through this".** It explains each step in plain words, asks before changing anything on your computer, and skips whatever you say no to.

The Social Content Studio MCP is a **programmatic content studio** you drive from chat: it renders
on-brand posts, carousels, stories, reels and thumbnails **by code**, with no image-generation
model, no GPU and no per-image cost. A post is a stack of layers; your AI composes it, renders it,
and hands you the file. It is also **extensible**: your AI can download any font and invent
brand-new effects at runtime.

**New in 1.3.4:** the `mcp` requirement is pinned to the 1.x line (`mcp>=1.2,<2`), because `mcp` 2.x removed `mcp.server.fastmcp`, which this server is built on.

**New in 1.3.3:** animation. Any layer can enter and leave with fade, slide, pop, zoom or wipe, and
text can type itself or arrive letter by letter or word by word. `animate_document` animates a whole
piece in one call (`studio_animate` does it in the live editor); the web editor plays it and exports
the MP4. Still renders show every layer in its final place.

**In 1.3.2:** bold text. Any text layer takes `"bold": true` and draws in that font's bold, the
same in the web editor (the Bold switch on a text layer) and here.

**In 1.3.1:** your own templates. Save any design as a template of yours (from chat, or with
"Save as my template" in the web editor), then reuse it with new words. See "Your own templates".

**In 1.3.0:** 16 ready-made templates for what small businesses and creators actually post
(feed posts, a 3-part carousel, collages, stories, a reel cover, a text-post card) and four
style packs to open them in (Editorial, Bold, Warm, Mono). `render_post`, `render_carousel` and
`render_reel` now take your own `brand`. Text over photos gets a veil sized to the photo.

---

## AI: how to run this

These rules come before every step below. They matter more than the steps.

1. **Ask before you change anything.** Before each step, explain in plain words what it is, why
   it is needed, and what exactly will change on their computer. Then ask "Do you want this?"
   and wait for a clear yes. If the answer is no, skip it, say you skipped it, and move on.
2. **Explain like they are new to this.** No jargon without a one-line explanation next to it.
3. **Say what a command does before you run it**, in one sentence. If they want to type it
   themselves, let them.
4. **One step at a time.** Do not bundle several steps behind one yes.
5. **Never ask them to paste a key or token into this chat.** When a key is needed, tell them
   which file to open and where to paste it themselves.

---

### Step 0. Look first (this changes nothing)

Tell them you will look around first and that looking changes nothing. Then check, and report
back in plain words:

- Which Python they have (`python --version`, 3.10 or newer is needed) and its full path.
- Whether `ffmpeg` is installed (`ffmpeg -version`). Only reels and video need it.
- Where their AI app keeps its MCP settings (for Claude Code, the `.mcp.json` of the project
  or the user settings; for Claude Desktop, `claude_desktop_config.json`).
- Whether a `post-engine-mcp` folder from an older version already exists. If it does, this
  is an update: say so, and plan to unzip over it (their own files stay, see "Updating").

### Step 1. Place the folder

**Explain it like this:** the studio is a folder of Python files that your AI app starts when it
needs it. It should live somewhere it will not be moved or deleted by accident.

**Ask:** "Can I put the studio in `<the folder you propose>`?" Suggest macOS/Linux
`~/.local/share/post-engine-mcp/` or Windows `%LOCALAPPDATA%\post-engine-mcp\`. Unzip the
package into that folder (the files sit directly inside it, next to `server.py`).

**Check:** `server.py`, `templates.py`, `brands.py`, `compositor.py`, `post_engine.py`,
`video_engine.py`, `finishes.py`, `requirements.txt` and this file are in the folder. Remember
its absolute path.

### Step 2. Install the two Python packages it needs

**Explain it like this:** the studio needs two free Python libraries: `mcp` (so your AI app can
talk to it) and `Pillow` (the image library that draws every post). Installing them adds them
to this Python; nothing else on the computer changes.

**Ask:** "Can I install `mcp` and `Pillow` for this Python?" If yes, from inside the folder:

```bash
pip install -r requirements.txt
```

**Optional extras, ask about each one separately:**
- **ffmpeg**, for reels and video (`render_reel`, `render_vertical` and the other video tools).
  Explain that it is a free video tool installed system-wide; if they do not make reels, skip it.
  If it is installed somewhere not on PATH, the path goes in `FFMPEG_BIN` (Step 3).
- **Playwright**, only for drawn generative backgrounds (`source="vibegen"`) and for
  `studio_render_video`. It is a library that runs a browser with no window:
  `pip install playwright` then `playwright install chromium` (a browser download). Skip it unless
  they want those two features; everything else works without it.

**Check:** `python -c "import mcp, PIL; print('ok')"` prints `ok`.

### Step 3. Connect it to your AI app

**Explain it like this:** your AI app keeps a list of tools it may start. Adding the studio to
that list is what lets you ask for posts in chat. This edits one settings file; nothing else.

**Ask:** "Can I add the studio to your AI app's MCP settings?" If yes, add this under
`mcpServers` (absolute paths, the Python from Step 0):

```json
{
  "mcpServers": {
    "post-engine": {
      "type": "stdio",
      "command": "<absolute path to python>",
      "args": ["<absolute path to>/post-engine-mcp/server.py"]
    }
  }
}
```

That runs the free tier. **If they have a Content Studio Pro key**, add an `env` block with a
placeholder and tell them to open the file and replace the placeholder with their key
themselves (it is in their purchase email and in their library at vibedna.ai/library):

```json
      "env": { "CONTENT_STUDIO_LICENSE": "PASTE-YOUR-KEY-HERE" }
```

Then restart the AI app so it loads the new tools.

Optional settings (all have defaults, none are needed to start; add them to the same `env`
block only if they ask for what they do):
- `POST_ENGINE_OUT`: where renders are written (default `~/.post-engine/out/`).
- `POST_ENGINE_FONTS`: the font library folder (default `~/.post-engine/fonts/`).
- `POST_ENGINE_LIBRARY`: their own image library folder (default `~/.post-engine/library/`).
- `POST_ENGINE_EFFECTS`: the custom-effects file (default `~/.post-engine/effects.py`).
- `FFMPEG_BIN` / `FFPROBE_BIN`: ffmpeg and ffprobe paths if they are not on PATH.
- `PEXELS_API_KEY` / `UNSPLASH_ACCESS_KEY` / `PIXABAY_API_KEY`: optional stock photo sources.
- `STUDIO_URL` + `STUDIO_TOKEN`: only when connecting to a hosted web editor (see below).

### Step 4. Make a first post (this only writes an image file)

Call `list_templates`, then `render_template("editorial-quote", {"quote": "Hello"})`. It
returns a file path; open it with them. Then try one of their own words in another template,
for example `render_template("launch-announcement", {"title": "New drop", "name": "..."})`.

---

## Free vs Pro

The studio is free to install and free to use. The free tier makes on-brand posts, carousels,
templates (built-in and your own) and documents, plus every `list_*` tool, `fetch_image`, and the `studio_*` bridge
tools. Free renders are 1080px with a small badge.

Content Studio Pro ($19/mo) removes the badge, exports at full resolution, and unlocks:
- Reels and video (`render_reel`, `render_reel_docs`, `render_template_reel`, `render_vertical`,
  `render_vertical_batch`, `verify_vertical`, `check_distinct`, `render_thumbnail`).
- Custom fonts your AI downloads on demand (`add_font`).
- Brand-new effects your AI invents at runtime (`add_effect`).

Subscribe at https://vibedna.ai/content-studio, then set `CONTENT_STUDIO_LICENSE` as in Step 3.
Without it, the Pro tools return a short message explaining how to subscribe; every free tool
keeps working.

## The templates

`list_templates` shows every template with a readable label, its Instagram format, its fields
and its default size. Every field has a default, so a template renders a complete example even
with no fields; fill only what you want to change.

- **Feed posts:** `editorial-quote`, `launch-announcement`, `tips-list`, `product-spotlight`,
  `event-date`, `before-after`, `text-post-card`, plus `quote-card`, `motiv`, `name-cover`,
  `quote-over-image`, `release-square`.
- **Carousel:** `carousel-cover`, `carousel-slide`, `carousel-closing` (one system: cover,
  numbered slides, closing).
- **Collages:** `collage-three`, `collage-four`.
- **Stories:** `story-question`, `story-countdown`, `story-new-post`.
- **Reel cover:** `reel-cover`. **Video thumbnail:** `genre-thumb` (1280x720).

The library templates open in their own style pack (Editorial, Bold, Warm or Mono). Pass
`brand="<your brand>"` to render any of them in your colours and fonts. **Photo fields**
(`photo`, `before`, `after`, `photo1`...) take one of the sample photos by name
(`coffee-window`, `kitchen-table`, `laptop-desk`, `linen-texture`, `notebooks-flatlay`,
`ocean-horizon`, `plant-light`, `shelf-after`, `shelf-before`, `street-dusk`, `vase-stone`,
downloaded from vibedna.ai when used), an image URL, or a path to a photo on your computer.

## Your own templates

**Explain it like this:** a template of yours is a design you made once and want to reuse with
new words: same layout, colours and photos, different text. Each one is a single `.json` file in
`~/.content-studio/templates/`, outside the product, so updates never touch it. The file holds
its photos inside it, so you can copy it to another computer or send it to someone.

- **Make one from chat:** `save_template("Weekly tips", from_template="tips-list",
  brand="<your brand>", fields={"title": "..."})` saves a built-in in your colours under your own
  name. Your AI can also pass a whole layer document (`template={...}`), for example one it
  composed with `render_document`.
- **Make one in the web editor:** "Save as my template", then "Download". Ask your AI to
  `import_template("<path to the downloaded .json>")`; it is checked and copied into the folder,
  so the download can be deleted.
- **Use it:** `list_templates` shows yours with `"yours": true`. Their fields are `text1`,
  `text2`... in layer order, and `saved_text` shows what each one said when saved, so your AI
  knows which is the headline. `render_template("weekly-tips", {"text3": "New title"})` changes
  only what you pass; `size="story"` re-renders the same layout at another size. They keep the
  colours they were saved with (`brand` restyles the built-ins only).
- **Remove one:** `delete_template("weekly-tips")`. Built-in templates cannot be deleted.

Set `CONTENT_STUDIO_HOME` to keep your brands and templates in another folder (they then live in
`<that folder>/brands/` and `<that folder>/templates/`).

## The tools

**Generate:**
- `render_template(template, fields, brand, size)`: a finished post from a template + brand,
  built-in or yours.
- `save_template(name, template | from_template, fields, brand, size, replace)` /
  `import_template(path, name, replace)` / `delete_template(name)`: your own templates (see above).
- `render_post(text, mode, size, preset, handle, query, image_path, source, brand)`: one card
  or a photo composite. `mode` = `card` (code-drawn) or `stock`. `source` = openverse
  (keyless), pexels, unsplash, pixabay, url, library, or vibegen (draws a generative background
  from a recipe such as `"still-flow seed=11"`; needs Playwright), or use `image_path`.
- `render_carousel(slides, ..., brand)`: a numbered multi-slide carousel.
- `render_reel(beats, ..., brand)` / `render_reel_docs(documents, ...)` /
  `render_template_reel(template, beats, brand, ...)`: a vertical reel from text beats, from raw
  layer documents, or one template document per beat (ffmpeg).
- `fetch_image(query, source, size)`: grab one image (a background, or to build your library).
- `render_document(document)`: render a RAW `{size, layers}` stack (full control; see below).
- `list_templates()` / `list_brands()` / `list_layer_types()` / `list_styles()`: introspection.

**Finish the look:**
- `list_finishes()` / `apply_finish(name, replace)`: put a named look on the current piece.
  A finish is a stack of mild adjustments in a deliberate order, not a single filter.

**Video and thumbnails:**
- `render_vertical(source, title, line, brand, ...)`: turn existing footage into a feed-ready
  vertical (1080x1920 at 30 fps, the rate Instagram accepts for reels), and report every
  measurement it made.
- `render_vertical_batch(sources, ...)`: the same closing mark on many clips in one call.
- `verify_vertical(path)`: measure a finished vertical: how visible its loop's cut is and
  whether it carries sound at all.
- `check_distinct(paths)`: are these clips actually different scenes, or the same one
  repeating? Measured in colour, because grey gives false duplicates.
- `render_thumbnail(frame, title, brand, eyebrow)`: a thumbnail with a full-bleed image and a
  big centred title fitted to the width.

**Save and reopen your work (with a hosted web editor):**
- `studio_list_projects()` / `studio_save_project(name, ...)` / `studio_open_project(id)`:
  keep a piece as a named project and load it back onto the canvas.
- `studio_render_video(project_id, aspect, ...)`: render a saved piece to a video file.
- `campaign_render(campaign, account, out_dir, limit)`: render every piece of a Motion DNA campaign on this
  machine (reels as video, posts and slides as images) and write `<campaign>_drip.json`, the calendar
  with each file in place, ready for a poster such as Social Brain's `drip_schedule`. It reads your own
  studio space with your licence key (`CONTENT_STUDIO_LICENSE`), renders a few pieces a call (`limit`)
  and skips the ones already there, so call it again until it says every piece has a file. A still
  in that calendar is a file on your machine: Social Brain 1.12.9 or newer posts it to Instagram as
  it is for an account connected through a Facebook Page (an older one, or an account connected
  with Instagram Login, needs a public https link in the slot). Needs
  Playwright and, for reels, Google Chrome on the machine.
- `studio_feed_set(drip, view)` / `studio_feed_get()`: drive the feed grid from chat.

**Extend the studio:**
- `add_font(url, name, share)` / `list_fonts()`: download any `.ttf`/`.otf`/`.ttc` (checked to
  really be a font, 20 MB max) and use it by name in a text layer's `font`. The font stays on
  your machine; `share=True` also uploads it to the browser studio, so only use it for fonts
  whose licence allows redistribution.
- `add_effect(name, kind, python, js)` / `list_effects()`: register a BRAND-NEW effect (a new
  layer type). `kind` = `content` (paints) or `adjust` (transforms everything below). `python`
  is the function body (adjust: `(base, layer, dims)` -> RGBA Image; content: `(layer, dims)`
  -> RGBA Image; Pillow, `load_font`, `math`, `random` and `colorsys` are in scope). `js`
  (optional) is the browser-preview twin. Effect code is checked before it is saved and again
  every time it loads: no other imports and no file, network or system access. Code that fails
  the check never runs, and `list_effects` shows what was refused.

**Housekeeping:**
- `check_for_update()`: your copy is a folder on your machine, so it stays exactly as it was
  the day you installed it while fixes keep shipping. This asks what is published.

**The document model** (for `render_document`): `{ "size": "square|portrait|story", "layers": [ {type, ...params, opacity, blend, visible} ] }`.
Content types: solid, gradient, image, particles, shape, text. Adjustment types: duotone,
tint, grade, posterize, grain, scanlines, vignette, blur, bloom, chromatic. Sizes: square
1080x1080, portrait 1080x1350, story 1080x1920. A text layer's `font` can be a font name, a
file path, or a CSS-style list such as `"Georgia, serif"` (the first one installed wins), and
`"bold": true` draws it in that font's bold.

**Your brands live outside the product.** Drop one JSON file per brand into
`~/.content-studio/brands/<name>.json` and it loads on start, usable by name in any template.
A brand is a palette by role (`bg_top`, `bg_bottom`, `accent`, `text`, `body`, `muted`, `glow`,
`particles`, and optionally `surface` for cards and `on_accent` for text on the accent colour),
fonts by role (`display`, `body`, `mono`, `poster`), `glow_strength`, and your `eyebrow`, `cta`
and `handle` strings. Templates reference the roles, never raw colours or font files, so the
same template renders in any brand's look. Brand names are not case-sensitive (`BISO.json`
answers to `biso`), and asking for a brand that is not installed returns an error that lists the
installed ones. Out of the box there is a neutral `default` and the four style packs.

**Connect to a hosted web editor (optional):** if you run the Content Studio web editor, set
`STUDIO_URL` + `STUDIO_TOKEN` and the `studio_*` tools drive it live (`studio_apply_template`,
`studio_set`, `studio_set_layer`, `studio_add_layer`, `studio_get`, `studio_render`). Without
it, ignore these: the render tools above are fully standalone.

## Updating

Unzip the new version over the same folder. Your own files stay: everything you rendered, the
fonts you added and the effects your AI invented live under `~/.post-engine/`, and your brands
and templates under `~/.content-studio/`. Restart the AI app afterwards. Changes in 1.3.0 worth knowing:
the `genre-thumb` template's text field is now `genre`; the template names from version 1.1
that were kept as aliases are gone (use `genre-thumb`, `release-square` and `quote-over-image`,
which draw the same thing); and `studio_render_video` takes `aspect` instead of its old
parameter name.

## Feeding a poster

Every render returns a file path. Hand it to your poster (schedule + publish). This MCP makes
the content; the posting is a separate step.

Reply to the welcome email if anything is off.
