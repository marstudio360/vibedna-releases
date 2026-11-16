# Jester: 20-Source Research MCP

One MCP tool, **20 research sources**, one aggregated result. Returns raw, full-page content (not search snippets) from across the dev/maker web (Reddit, Hacker News, IndieHackers, ProductHunt, Substack, GitHub, Dev.to, Medium, arXiv papers, YouTube, news outlets, Twitter/X, Quora, LinkedIn, and more) in a single call.

Built for vibecoders, indie hackers, and developers who want **deep, multi-source intelligence** without paying per-query for a search API.

> **Try it free first**: the same engine powers the public web search at **[vibedna.ai/jester](https://vibedna.ai/jester)**. Zero install, zero paywall. Then upgrade to the MCP for the full experience.

## The Jester model: your scraping is free, your synthesis is your own

**This is the cleanest deal in research tooling:**

1. **Scraping is free, forever.** Jester does the work no one else does: parallel-fetches 20 sources, runs semantic rerank with a local 30 MB model (model2vec, CPU-only, zero API calls), clusters, dedupes, surfaces contradictions and money signals. **Zero per-query cost. Zero API keys needed for the data path.**

2. **Synthesis uses YOUR existing Claude subscription.** Already pay for Claude Code / Claude API / Claude Pro? Plug your `ANTHROPIC_API_KEY` and Jester uses *your* tokens to write the analysis. **No double-billing, no monthly add-on, no per-query metering.** Your usage limits = your synthesis limits.

3. **You pick the depth.** Three modes, switch per query:

   | Mode | What it does | Cost |
   |---|---|---|
   | `raw` | Scrape + cluster + contradictions + money signals. No LLM. | $0 (your CPU only) |
   | `synth` | Above + Haiku/Sonnet/Opus writes a 3-bullet or full analysis. | Your Claude tokens |
   | `auto` | Multi-step agentic research: Jester chains queries, fetches deeper, drafts a full report. | Your Claude tokens |

**Why this matters:** every other "research AI" tool builds a subscription on top of LLM costs and marks them up 3-5x. Jester's value is the scraping pipeline. The LLM is your existing relationship with Anthropic. You already pay for it. Jester just routes it.

## Web vs MCP: the asymmetry

| Capability | Web (free) | MCP |
|---|---|---|
| Sources | 20 | 20 + Exa + Firecrawl + Brave |
| Results per search | 25 | 100+ |
| AI synthesis | Haiku only | Haiku / Sonnet / Opus |
| Rate limit | 20 syntheses/hr per IP | None (your API key) |
| Cache window | 1 hour | Permanent personal index |
| Search history | localStorage only | Searchable, grows over time |
| Watch mode | No | Topics + weekly digests |
| Trend velocity | No | Track changes across runs |
| Money signals | Current run only | Aggregated across full history |
| Deep crawl | No | Firecrawl + Exa neural |
| Entity graph | No | Cross-research relationships |
| YouTube transcripts | No | Auto-ingested in deep mode (free, no key) + local Whisper fallback for caption-less videos |
| Tools | Search + brief | 62 tools (research, digest, niche, scan, score, watch, more) |
| Runs on | shared vibedna.ai server | your machine |

**Bottom line**: the web is a teaser. The MCP is the actual research lab.

## What makes Jester different

- **Full article content, not snippets**: every web result is run through Jina Reader (free, no key), giving you the same depth as paid neural-search APIs from a free DuckDuckGo source list.
- **20 sources in parallel**: one call hits Reddit + HN + IndieHackers + ProductHunt + Substack + Dev.to + Medium + GitHub + Wikipedia + arXiv + News + YouTube + Twitter/X + Quora + LinkedIn + Amazon + Telegram + the open web, all in ~5-10 seconds.
- **Contradiction detection**: when Reddit says a niche is dying and HN says it's exploding, Jester flags it explicitly. No other research MCP does this.
- **YouTube transcripts auto-ingested in deep mode**: `research_topic(depth="deep")` and `digest_youtube(url)` pull full captions for free (no API key, `youtube-transcript-api`). Caption-less videos transcribed locally via Whisper (also free, runs on your machine: the `base` model ~75MB auto-downloads on first use). 99% of videos use the free caption path; Whisper only kicks in for the rare uncaptioned video.
- **Topic-aware query rewriting**: queries are reshaped per source (HN/GitHub need short, exact terms; news/web handle long queries).
- **Per-source timeouts + visible failure logs**: slow or rate-limited sources don't drag the whole run down.
- **Free by default**: synthesizes nothing on its own; returns the raw aggregated content for Claude to reason over using your existing subscription tokens. No double-billing.
- **Shared-daemon architecture (v1.0.0)**: one engine shared by N tabs. ~50MB per client instead of 600MB. Circuit breakers, RAM caps, graceful drain, structured JSONL logs. See [`DAEMON_README.md`](./DAEMON_README.md).

## Install (MCPize / standalone)

```bash
pip install -r requirements.txt
```

That single command installs everything. **No CLI tools (ffmpeg, OpenAI Whisper, etc.) need to be installed separately.** Disk footprint: ~250MB.

### What auto-installs and runs locally: $0, no keys, no setup

| Tool | What it does | First-run download |
|---|---|---|
| `faster-whisper` | Local Whisper for caption-less videos | ~75MB (`base` model) on first transcription |
| `model2vec` | Local semantic embedding model that powers rerank, dedup, clustering | ~30MB (`potion-base-8M`) on first search |
| `youtube-transcript-api` | Scrapes YouTube captions (99% of videos) | none |
| `trafilatura` | Free URL content extraction (powers `crawl_url` and the `web` source) | none |
| `pytrends` | Google Trends signals | none |
| All 20 sources (Reddit, HN, IndieHackers, ProductHunt, GitHub, etc.) | Public scraping | none |

All of the above runs on your machine, costs nothing, and needs no API key.

### What auto-installs but needs YOUR API key to do anything

These SDKs install with `pip install` but stay dormant until you set the matching env var. **No surprise charges. If the key isn't there, the tool is skipped silently.**

| SDK | Set this env var to unlock | Used for |
|---|---|---|
| `exa-py` | `EXA_API_KEY` | Exa neural search (the deep multi-source mode) |
| `firecrawl-py` | `FIRECRAWL_API_KEY` | Firecrawl deep crawl (full-page extraction) |
| `anthropic` | `ANTHROPIC_API_KEY` | Autonomous synthesis (`synthesize=True`), only if you want headless workflows. Default leaves synthesis to your Claude chat. |

**You don't need ANY of these to use the MCP.** The free defaults give you the same engine that powers vibedna.ai/jester. The BYOK keys are pure upgrades when you want extra source depth or autonomous synthesis.

### Opt-out if you want a leaner install

- `JESTER_WHISPER_MAX_SECONDS=0` → disables the local Whisper fallback path (saves ~75MB after first run; captions still work)

Place the Jester library somewhere the server can find it. The server resolves the library directory in this order:

1. `JESTER_LIB` env var (explicit path to the directory containing `jester.py`)
2. A `jester/` subfolder next to `server.py` (bundled distribution)
3. `../../../JESTER` relative to `server.py` (development monorepo layout)

## Environment variables

| Variable | Required? | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | for `synthesize=True` only | Claude API for structured intelligence extraction |
| `EXA_API_KEY` | for paid mode only | Enables Exa deep crawl, news, papers, podcasts |
| `FIRECRAWL_API_KEY` | optional | Better web scrape on `crawl_url` (otherwise free Jina path is used) |
| `LISTENNOTES_API_KEY` | optional | Podcast episode search |
| `TWITTER_BEARER_TOKEN` | optional | Real Twitter API (otherwise scrapes x.com via DDG) |
| `BRAVE_API_KEY` | optional | Brave Search index (different from DDG) |
| `JESTER_HOME` | optional | Where Jester stores reports / cache / index. Default: `~/.jester` |
| `JESTER_MEMORY` | optional | Set to `1` to inject your past research history into new queries. **Default: off** so each install starts clean. |
| `JESTER_DAILY_LIMIT` | optional | Hard cap on Claude API spend per day in USD. Default: `1.00` |
| `JESTER_MONTHLY_LIMIT` | optional | Hard cap per month. Default: `20.00` |
| `JESTER_WARN_PCT` | optional | Warn at this % of budget cap. Default: `80` |
| `JESTER_WHISPER_MODEL` | optional | Whisper model size for audio transcription (`base`, `small`, `medium`). Default: `base` |
| `JESTER_WHISPER_MAX_SECONDS` | optional | Max audio duration to transcribe in seconds. Default: `1800` (30 min) |
| `MCPIZE_LICENSE_KEY` | optional | Your JesterDNA Pro license key; unlocks the Pro tools. It starts with `vbd_`, arrives in your purchase email and is also in your library at https://vibedna.ai/library. Without it Jester runs its free tier. Get Pro at https://vibedna.ai/store. |

The free defaults work without any keys set.

## Tools

### `research_topic(query, sources?, depth?, free?, synthesize?)`
The main one. Aggregates from all configured sources and returns raw content + citations. With `synthesize=True`, also runs an intelligence-extraction pass (~$0.02 Haiku call) and saves a Markdown report.

### Other tools
- `digest_youtube(url)`: full transcript of any YouTube video
- `digest_playlist(url)`: bulk transcripts
- `find_niche(topic)`: niche discovery mode
- `research_youtube(topic)`: video-focused research
- `score_job(description)`: Upwork-style job evaluation
- `query_memory(query)`: search your past research index (only useful if `JESTER_MEMORY=1`)
- `get_stats` / `get_budget` / `get_optimizer`: telemetry

## Free vs Paid sources

**Free (no API keys):** web (DuckDuckGo + Jina full-content extraction), Reddit, Hacker News, Twitter (via x.com scrape fallback), StackOverflow, Google News, arXiv, GitHub, Wikipedia, YouTube.

**Paid (require keys):** Exa deep crawl, Exa news, Exa papers, Listen Notes podcasts, Firecrawl deep crawl, Brave Search, Twitter v2 API.

**Disabled by default:** Brave Search (needs `BRAVE_API_KEY`: public scrape returns 429), Google Trends (pytrends globally rate-limited).

## Performance notes

- Quick mode: ~5-10s, returns titles + descriptions + Jina-extracted full content for top 3 web results
- Deep mode: ~15-25s, also fetches YouTube transcripts in parallel
- Per-source hard timeout: 12s (quick) / 25s (deep). Slow sources get dropped, not the whole run

## What does NOT ship in this package

The Jester library accumulates personal data over time (research reports, cached pages, embeddings index, spend logs). All of that lives under `JESTER_HOME` (default `~/.jester/`), outside the package directory. **Nothing personal is bundled with this MCP.**

When packaging for distribution, exclude:

- `~/.jester/reports/`
- `~/.jester/personal_index.db`
- `~/.jester/metrics/`
- `~/.jester/budget/`
- `~/.jester/cache/`
- `~/.jester/snapshots/`
- `~/.jester/fetch_cache/`

## License

Brought to you by **VibeDNA**: generative art + builder tools.
