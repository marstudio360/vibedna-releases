"""
Jester Specialized Intelligence Modes
Each mode = same engine, different extraction lens + structured output.

Modes:
  find_niche:       GO/WAIT/AVOID niche scoring
  research_youtube: YouTube content intelligence
  score_job:        Job/bid opportunity scoring
  competitor_scan:  Deep competitor breakdown
  self_feed:        Extract follow-up topics from past reports
"""

import re
from datetime import datetime

CURRENT_YEAR = datetime.now().year


# ─────────────────────────────────────────────────────────────────────────────
# NICHE FINDER: GO / WAIT / AVOID
# ─────────────────────────────────────────────────────────────────────────────

NICHE_PROMPT = """
You are Jester, a ruthless niche evaluation engine for a solo digital product builder.

RESEARCH DATA:
{content}

TASK: Score this niche across every dimension that matters for building a profitable digital product or YouTube channel. Be brutally honest. No padding.

Output EXACTLY this structure:

## VERDICT
[GO / WAIT / AVOID] (one word, one line)

## Score: X/100
(weight: 25% monetization + 20% demand + 20% competition + 20% trend + 15% entry)

## Why [GO/WAIT/AVOID]
2-3 sentences. The core reason. Be direct.

## Dimensions

### Demand (X/10)
- Search volume / community size evidence
- Pain point intensity (are people desperate or just curious?)
- Buying intent signals

### Monetization (X/10)
- YouTube CPM estimate (cite sources if found)
- Affiliate/product revenue potential
- Price point people already pay in this niche
- Best monetization vector: [Ads / Affiliate / SaaS / Course / MCP / Agency]

### Competition (X/10)
- Saturation level: [LOW / MEDIUM / HIGH / BRUTAL]
- Who owns this niche right now?
- What they're missing (the gap)
- Can a solo builder rank or get traction?

### Trend Direction (X/10)
- Rising / Stable / Declining (with evidence)
- Time horizon: peaking in X months or multi-year?
- What's driving it?

### Entry Barriers (X/10)
- Technical skill required
- Capital required to start
- Time to first $100

## Fastest Path to Revenue
The single most direct way to make the first dollar in this niche. Be specific.

## What to Build First
If GO: exact product, exact title, exact price point.
If WAIT: what trigger to watch for before entering.
If AVOID: what adjacent niche is better.

## Red Flags
Any signals this is a trap, fad, or already dead.
"""


# ─────────────────────────────────────────────────────────────────────────────
# YOUTUBE INTELLIGENCE MODE
# ─────────────────────────────────────────────────────────────────────────────

YOUTUBE_INTEL_PROMPT = """
You are Jester, a YouTube content intelligence engine for a solo creator building a channel.

RESEARCH DATA:
{content}

TASK: Extract everything a creator needs to dominate this niche on YouTube right now. Output actionable intelligence, not general advice.

Output EXACTLY this structure:

## Topic Verdict
[HOT / GROWING / SATURATED / DEAD] (with one-line reason)

## Top Performing Title Formulas
List 5-7 title patterns currently getting views in this niche.
Format: "Pattern: [X] → Example: [Y] → Why it works: [Z]"

## Content Gaps (What Nobody Is Making)
3-5 specific video ideas that have demand but no good existing content.
For each: title idea + why it's a gap + estimated search demand (high/medium/low)

## Hook Formulas That Work
3 specific hook structures (first 30 seconds) that perform in this niche.

## Optimal Video Structure
- Ideal length: X minutes (evidence-based)
- Best upload frequency
- Thumbnail style that works

## Top Channels in This Niche
For each channel found: name + subscriber count + what they do well + their weakness

## Keyword Opportunities
5-10 keywords/phrases with clear demand but low competition. Mark HIGH/MEDIUM/LOW opportunity.

## Monetization Path
- CPM estimate for this niche
- Best affiliate programs to weave in
- At what subscriber count does this become meaningful revenue?

## First 3 Videos to Make
Exact titles, exact angles. The fastest path to the algorithm noticing you.
"""


# ─────────────────────────────────────────────────────────────────────────────
# JOB / BID SCORER
# ─────────────────────────────────────────────────────────────────────────────

JOB_SCORE_PROMPT = """
You are Jester, a freelance intelligence engine for a solo developer/AI builder (VibeDNA).

SKILLS: Python, Next.js, Claude/AI integration, MCP servers, automation, web scraping, data pipelines, Playwright, Supabase, Stripe, Chrome extensions, trading bots.

RESEARCH DATA:
{content}

TASK: Analyze this job opportunity and tell the freelancer exactly what to do.

Output EXACTLY this structure:

## Match Score: X/100

## Verdict: [BID / SKIP / RESEARCH MORE]

## Why
2 sentences. Direct.

## Bid Amount
- Recommended bid: $X (or $/hr)
- Reasoning: what the market pays for this exact work
- What to anchor on in the proposal

## Winning Proposal Angle
The specific hook that wins this job. NOT generic. Based on the job signals.
First line of the proposal (write it):

## Red Flags
Any signals this client will be a nightmare, underpay, or ghost.

## Green Flags
Signals this is a good client / good job.

## Competitive Edge
What most bidders will say vs what YOU should say (the gap).

## Time Estimate
Realistic hours to deliver. Don't undersell.

## Similar Work That Pays Well
Related job types or adjacent skills to position for.
"""


# ─────────────────────────────────────────────────────────────────────────────
# COMPETITOR SCANNER
# ─────────────────────────────────────────────────────────────────────────────

COMPETITOR_PROMPT = """
You are Jester, a competitive intelligence engine.

RESEARCH DATA:
{content}

TASK: Produce a complete competitor breakdown for a solo builder deciding whether and how to compete.

Output EXACTLY this structure:

## Market Map
Who owns this space? List the top 3-5 players with:
- Name + URL
- Their core value prop (one sentence)
- Estimated revenue tier: [<$10K/mo / $10-100K/mo / $100K+/mo]
- Their biggest weakness

## Pricing Intelligence
- What do competitors charge?
- What tiers work?
- Where is the underpriced gap?

## Feature Gaps
What do users complain about? What's missing that people would pay for?
(Pull from Reddit/reviews/HN comments if found)

## Positioning Opportunity
The exact angle a solo builder can own that the big players can't.
One sentence positioning statement.

## Build vs Buy
What parts of this can be built in days vs what takes months?

## Entry Strategy
The fastest way to get first 10 paying customers in this space.

## Copy Intelligence
Notable copy, taglines, or messaging patterns that work in this market.

## Verdict
[ENTER / DIFFERENTIATE / AVOID] (with 2-sentence reason).
"""


# ─────────────────────────────────────────────────────────────────────────────
# SELF-FEED: Extract follow-up topics from a report
# ─────────────────────────────────────────────────────────────────────────────

SELF_FEED_PROMPT = """
You are Jester's autonomous research director.

PAST RESEARCH:
{content}

TASK: You just read this intelligence report. Your job is to extract the 5 most valuable follow-up research topics that would compound this knowledge, topics that would complete the picture, verify the gaps, or unlock the next opportunity.

Output EXACTLY this structure:

## Follow-Up Research Queue

1. [TOPIC]
   Why: [one sentence on what new intelligence this unlocks]
   Sources: [best sources to use: web/reddit/youtube_search/papers/github/news]
   Priority: [HIGH/MEDIUM/LOW]

2. [TOPIC]
   Why: ...
   Sources: ...
   Priority: ...

(repeat for 5 topics)

## Emerging Opportunity
One specific opportunity or product idea this report hints at but doesn't fully explore.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Mode runner: takes content + mode, returns structured intelligence
# ─────────────────────────────────────────────────────────────────────────────

MODE_PROMPTS = {
    "niche":      NICHE_PROMPT,
    "youtube":    YOUTUBE_INTEL_PROMPT,
    "job":        JOB_SCORE_PROMPT,
    "competitor": COMPETITOR_PROMPT,
    "self_feed":  SELF_FEED_PROMPT,
}


def run_mode(
    content: str,
    mode: str,
    model_id: str,
    anthropic_api_key: str,
    max_tokens: int = 3000,
) -> str:
    import anthropic

    prompt_template = MODE_PROMPTS.get(mode)
    if not prompt_template:
        raise ValueError(f"Unknown mode: {mode}. Choose from: {list(MODE_PROMPTS)}")

    prompt = prompt_template.format(content=content[:22000])

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    message = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW MODES: convenience presets over the strategic-intel layer.
# Purely additive: every mode is just defaults; ALL params overridable.
# Modes never hard-block a source or feature. They only tune which extractors
# run by default and how results are weighted.
# ─────────────────────────────────────────────────────────────────────────────

WORKFLOW_MODES = {
    "alpha": {
        "description": "Money signals + builder intel. Strict BS filter, recent window, money + clusters. Patterns OFF by default (Haiku API cost); opt-in with include_patterns=True.",
        "deep": False,
        "recency_days": 90,
        "bs_threshold": 50,
        "include_money": True,
        "include_clusters": True,
        "include_patterns": False,
        "include_contrarian": False,
        "include_outlier": False,
        "include_papers": False,
        "creator_trust_weight": 1.0,
        "max_results": 30,
        "sources_hint": ["web", "reddit", "hn", "twitter_x", "indiehackers", "newsletter_archive"],
    },
    "quick": {
        "description": "Fast checkpoint. Written sources only, no LLM, trust-ranked top 10. Target <10s.",
        "deep": False,
        "recency_days": 180,
        "bs_threshold": 30,
        "include_money": False,
        "include_clusters": False,
        "include_patterns": False,
        "include_contrarian": False,
        "include_outlier": False,
        "include_papers": False,
        "creator_trust_weight": 0.6,
        "max_results": 10,
        "sources_hint": ["web", "reddit", "hn"],
    },
    "deep": {
        "description": "Full sources incl. YouTube/podcasts/papers/audio. Lenient BS filter, 18-month window. Patterns OFF by default (Haiku API cost); opt-in with include_patterns=True.",
        "deep": True,
        "recency_days": 540,
        "bs_threshold": 20,
        "include_money": True,
        "include_clusters": True,
        "include_patterns": False,
        "include_contrarian": False,
        "include_outlier": False,
        "include_papers": True,
        "creator_trust_weight": 0.5,
        "max_patterns": 8,
        "max_results": 80,
        "sources_hint": ["web", "reddit", "hn", "twitter_x", "papers", "arxiv", "youtube_search", "youtube_transcripts",
                         "podcast_transcripts", "newsletter_archive", "indiehackers"],
    },
    "research": {
        "description": "Ebook/topic synthesis. Widest net, no recency penalty, no BS filter, no dedup. Source-type diversity over similarity.",
        "deep": True,
        "recency_days": None,
        "bs_threshold": 0,
        "include_money": False,
        "include_clusters": False,
        "include_patterns": False,
        "include_contrarian": False,
        "include_outlier": False,
        "include_papers": True,
        "creator_trust_weight": 0.0,
        "diversity_sort": True,
        "max_results": 120,
        "sources_hint": ["web", "reddit", "hn", "twitter_x", "papers", "arxiv", "wikipedia",
                         "youtube_search", "youtube_transcripts", "podcast_transcripts", "newsletter_archive",
                         "substack", "indiehackers", "news"],
    },
    "checkpoint": {
        "description": "Temporal diff vs last snapshot. Falls through to quick + creates first snapshot if none exists.",
        "deep": False,
        "recency_days": 30,
        "bs_threshold": 30,
        "include_money": False,
        "include_clusters": False,
        "include_patterns": False,
        "include_diff": True,
        "since_days": 7,
        "max_results": 20,
        "sources_hint": ["web", "reddit", "hn"],
    },
    "pattern": {
        "description": "Patterns-first mode (Haiku API). EXPLICIT opt-in: this mode is the ONLY one where Haiku synthesis runs by default. Use when you want Jester to summarize, not when you want raw data.",
        "deep": False,
        "recency_days": 120,
        "bs_threshold": 35,
        "include_money": False,
        "include_clusters": True,
        "include_patterns": True,
        "include_contrarian": True,
        "include_outlier": True,
        "include_sources": False,
        "max_patterns": 5,
        "max_results": 25,
        "sources_hint": ["web", "reddit", "hn", "newsletter_archive", "podcast_transcripts"],
    },
}


WORKFLOW_MODES["auto"] = {
    "description": "auto: classify intent and pick the best mode automatically (keyword heuristics, Haiku fallback when ambiguous).",
    "delegates": True,
}


INTENT_KEYWORDS = {
    "alpha":      ["make money","monetize","revenue","how are people","best businesses",
                   "earn","mrr","arr","income","profitable","side hustle","passive income"],
    "research":   ["synthesis","for my book","everything about","comprehensive",
                   "deep dive into","exhaustive","write a book","ebook on","encyclopedic"],
    "checkpoint": ["checkpoint","since","what changed","diff","update","last time",
                   "what's new","since my last","catch me up"],
    "pattern":    ["patterns","themes","5 ways","what are people","common approaches",
                   "convergence","what do they all"],
    "deep":       ["scientific","academic","research papers","studies on","peer-reviewed",
                   "literature","journal","meta-analysis"],
    "quick":      ["quick","just check","tldr","summary","brief","short answer","fast"],
}


def _keyword_scores(text: str) -> dict:
    t = (text or "").lower()
    return {mode: sum(1 for kw in kws if kw in t) for mode, kws in INTENT_KEYWORDS.items()}


def classify_intent(topic_text: str, allow_llm: bool = True) -> dict:
    """Classify a research prompt → mode name. Heuristic-first, Haiku fallback when ambiguous.
    Returns {mode, confidence 0-1, method, matched_keywords, scores}."""
    scores = _keyword_scores(topic_text)
    total = sum(scores.values())
    if total == 0:
        return {"mode": "quick", "confidence": 0.5, "method": "default",
                "matched_keywords": [], "scores": scores}
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_mode, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    confidence = top_score / max(total, 1)
    matched = [kw for kw in INTENT_KEYWORDS[top_mode] if kw in (topic_text or "").lower()]

    if confidence >= 0.6 or (top_score - second_score) >= 2:
        return {"mode": top_mode, "confidence": round(confidence, 2),
                "method": "keyword", "matched_keywords": matched, "scores": scores}

    if not allow_llm:
        return {"mode": top_mode, "confidence": round(confidence, 2),
                "method": "keyword-ambiguous", "matched_keywords": matched, "scores": scores}

    try:
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("no api key")
        from budget import check_budget, record_spend
        budget = check_budget("haiku", ["classify"], "quick", False)
        if not budget["ok"]:
            raise RuntimeError("budget")
        from anthropic import Anthropic
        prompt = (
            "Classify this research prompt into ONE mode. Reply with ONLY the mode name.\n"
            "Modes: alpha (money/revenue), research (book/exhaustive), checkpoint (diff vs prior),\n"
            "pattern (themes/convergence), deep (scientific/academic), quick (fast tldr).\n\n"
            f"Prompt: {topic_text[:500]}\n\nMode:"
        )
        resp = Anthropic().messages.create(
            model="claude-haiku-4-5", max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.content[0].text if resp.content else "").strip().lower()
        record_spend("haiku", getattr(resp.usage, "input_tokens", 0),
                     getattr(resp.usage, "output_tokens", 0), sources=["intent-classify"])
        for m in INTENT_KEYWORDS:
            if m in text:
                return {"mode": m, "confidence": 0.8, "method": "haiku",
                        "matched_keywords": matched, "scores": scores}
    except Exception as e:
        return {"mode": top_mode, "confidence": round(confidence, 2),
                "method": f"keyword-fallback({type(e).__name__})",
                "matched_keywords": matched, "scores": scores}
    return {"mode": top_mode, "confidence": round(confidence, 2),
            "method": "keyword-ambiguous", "matched_keywords": matched, "scores": scores}


def suggest_mode_for(prompt: str) -> dict:
    cls = classify_intent(prompt, allow_llm=False)
    mode = cls["mode"]
    matched = cls["matched_keywords"]
    if matched:
        reasoning = f"Detected {mode} intent. Matched keywords: {', '.join(matched[:5])}."
    else:
        reasoning = "No strong intent keywords detected, defaulting to quick (cheapest, safest)."
    alt_map = {
        "alpha":      [("research", "if you want exhaustive sources, no recency penalty"),
                       ("deep", "if you want pattern detection across academic + indie sources")],
        "research":   [("deep", "if you also want pattern synthesis + contrarian takes"),
                       ("alpha", "if the goal is money intel, not topic synthesis")],
        "checkpoint": [("quick", "if you don't have a prior snapshot yet"),
                       ("alpha", "if you want fresh money signals along with the diff")],
        "pattern":    [("deep", "if you want patterns AND raw sources + papers"),
                       ("alpha", "if you want money-flow patterns specifically")],
        "deep":       [("research", "if you want widest possible source net, no filter"),
                       ("pattern", "if patterns matter more than raw sources")],
        "quick":      [("pattern", "if you want themes, not just raw hits"),
                       ("alpha", "if this is a money/builder question")],
    }
    alternatives = [{"mode": m, "when": w} for m, w in alt_map.get(mode, [])]
    return {
        "suggested_mode": mode,
        "reasoning": reasoning,
        "confidence": cls["confidence"],
        "method": cls["method"],
        "alternatives": alternatives,
        "no_mode_option": "Run open (no mode, default params) if the prompt is abstract or you want Jester to explore widely without preset bias.",
    }


def get_mode_defaults(name: str) -> dict:
    return dict(WORKFLOW_MODES.get(name, WORKFLOW_MODES["quick"]))


def list_workflow_modes() -> list[dict]:
    return [
        {"name": k, "description": v["description"],
         "defaults": {kk: vv for kk, vv in v.items() if kk != "description"}}
        for k, v in WORKFLOW_MODES.items()
    ]
