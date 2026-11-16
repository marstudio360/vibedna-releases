# JesterDNA: start prompts

Paste this into your AI after installing JesterDNA (the research MCP from vibedna.ai/store/jester; the free web search at vibedna.ai/jester needs no install).

There are two prompts. Paste the first one once, right after the install, to check what your copy can do with the keys you have. Paste the second one at the start of any session where you want your AI to research with JesterDNA.

## Prompt 1: first run (once)

```text
I just installed JesterDNA. It is a research engine on my machine: it searches many open sources at once (web, Reddit, Hacker News, papers, GitHub, news, YouTube and more), filters out spam, and keeps what it finds in a local memory that grows every time we use it. Do this check with me now, one step at a time.

1. Check the copy: run check_for_update and jester_status. Tell me in one line if my copy is current and how much is already in its memory.
2. Check my keys, without ever showing them. Look at which of these are set in the .env file next to server.py and tell me only "set" or "missing" for each:
   - MCPIZE_LICENSE_KEY: my Pro licence key from my purchase (it starts with vbd_ and is also in my library at vibedna.ai/library). Without it Jester runs on the free open sources only, and watch_topic, scan_competitor and crawl_url refuse.
   - FIRECRAWL_API_KEY (optional): needed by crawl_url to read whole websites.
   - EXA_API_KEY (optional): adds a paid search source.
   - ANTHROPIC_API_KEY (optional): only for synthesize=True, when Jester writes the analysis itself instead of you. Most people leave it empty: you read the evidence and write the analysis here.
   - BRAVE_API_KEY (optional): adds the Brave source.
   If I want to add a key, I paste it into .env myself. Never ask me to paste a key into this chat.
3. Check spending: run get_budget and estimate_cost(tool="") and tell me in two lines what costs money on my setup and what is free. Everything is free unless a paid key is set and used.
4. First proof, free: quick_lookup(query="<a topic I name>"), then find_niche(niche="<an idea I name>"). find_niche returns evidence plus a scoring guide: apply it yourself and give me GO, WAIT or AVOID with the three strongest pieces of evidence and their links.

Report back with: version, memory size, which keys are set or missing (never the values), what costs money, and the verdict from step 4. End with one question if something needs my decision.
```

## Prompt 2: every session (daily use)

```text
Use JesterDNA for research in this session. These rules come before anything else you do when you look things up.

WHAT IT IS FOR
Answering real questions with evidence before I spend time or money: is there a market for this idea, who already sells it and what people complain about, who is making money in a subject and how, what a video or podcast actually says, and what changed in a topic since last month. It reports what the sources say; a verdict is evidence, not a promise.

WHEN TO USE IT
When I ask you to research, check, compare, validate an idea, look at a competitor, summarize a video, or "find out if...". Use it before you answer from memory on anything that may have changed recently.

WHICH TOOLS, BY JOB
- Not sure which tool fits: suggest_mode(prompt="<my request>") or list_modes.
- Fast facts: quick_lookup(query) for 3 results; deep_search(query, num_results=20) for more; neural_search(query, source="web" | "reddit" | "hn") to rank results by meaning.
- Full research on a topic: research_topic(query, depth="quick" or "deep") pulls many sources at once and returns the raw evidence for you to read; research(topic, mode="quick" | "deep" | "research" | "alpha" | "pattern" | "checkpoint") is the all in one version that also filters spam and adds money, pattern and contradiction sections.
- Read one thing: fetch_url(url), read_pdf(url_or_path), read_github_repo(repo_url), fetch_substack_feed(substack_url), search_papers(query), search_substack(query), search_linkedin(query), search_amazon(query).
- Decide: find_niche(niche) for GO, WAIT or AVOID on a product, channel or service idea; research_youtube(topic) for what videos work in a subject; score_job(job_title, job_description, budget) for BID or SKIP on a freelance posting; scan_competitor(target) for pricing, complaints and the gap (needs my Pro key). These return evidence plus a scoring guide: you apply the guide and give me the verdict.
- Video and audio to text: digest_youtube(url) for one video (it transcribes on my machine when there are no captions); digest_audio(url, max_minutes) for a podcast or audio link; bulk_transcribe(urls) for several; extract_video_frames(url, count) when you need to see the video; digest_playlist(url, max_videos) for a whole playlist (it writes per video summaries itself, so it needs the AI provider key in .env).
- Make sense of what was gathered on a topic: top_findings(topic), extract_money_claims(topic, min_specificity=70), money_flow_summary(topic), detect_contradictions(topic), trend_velocity(topic) (rising, stable or falling), entity_map(topic), cluster_findings(topic), creator_trust_for_topic(topic). Run research(topic) on the topic first so there is something to analyze.
- Check a single text for spam, affiliate bait or machine filler: bs_score_text(title, content).
- Memory: jester_recall(name) and query_memory(query) answer from what Jester already learned, without a new search; jester_topic_mastery(query) says how well a topic is covered.
- Over time: snapshot_state(topic) today, checkpoint_diff(topic, since_date) later to see what is new and what died; watch_topic(query) does both in one call (needs my Pro key); crawl_url(url, deep=true) reads up to 8 pages of a site (needs my Pro key and a Firecrawl key).

WHAT TO CHECK FIRST
- If a tool answers that it needs JesterDNA Pro, tell me in one line which tool and continue with the free tools.
- Before anything that can spend money (synthesize=True, crawl_url, a paid source), run estimate_cost for that call and get_budget, tell me the cost, and wait for my yes.
- Prefer jester_recall or query_memory before a fresh search on a topic we already researched.

NEVER
- Never pass synthesize=True or also_web=True without my yes: it spends my own API key. By default you read the raw evidence and write the analysis here.
- Never ask for, print or repeat any key. Keys live in .env; I add them myself.
- Never present a verdict, a trend or a money claim as a guarantee. Say how many sources back it and link them.
- Never present a result from a source that came back as a placeholder: only indiehackers, newsletter_archive and podcast_transcripts are live in fetch_underground.
- Never tell me schedule_weekly_snapshot runs on its own: it only saves the topic to the list; I still have to run the snapshot.

HOW TO REPORT BACK
Result first: the answer or the verdict in one or two lines. Then the evidence: the three to five strongest points, each with its source link, and where sources disagree. Say what it cost (or that it was free). End with one question if the next step needs my decision.

FIRST TASK NOW
Ask me for one idea or topic I am thinking about. Run find_niche on it, then research(topic, mode="quick") and trend_velocity on the same topic, and give me GO, WAIT or AVOID with the evidence, in five lines or fewer.
```
