"""
Jester Query Expansion: broaden queries before fetching for better recall.

Expands a user query into 2-3 semantic variants using synonym maps
and lightweight topic detection. No LLM, no API, pure regex + dict.
"""

import re
from typing import Optional

# ── Synonym / expansion map ───────────────────────────────────────────────────
# Format: canonical_term -> [synonyms to add to query]

_EXPANSIONS: dict[str, list[str]] = {
    # AI / LLM
    "ai agents":        ["autonomous agents", "agentic AI", "agent frameworks"],
    "llm":              ["large language model", "foundation model", "claude openai"],
    "vibe coding":      ["AI-assisted coding", "cursor windsurf", "copilot coding"],
    "prompt":           ["prompt engineering", "system prompt", "llm instructions"],
    "rag":              ["retrieval augmented generation", "vector search", "embeddings"],
    "fine tuning":      ["finetuning", "model training", "lora qlora"],
    "mcp":              ["model context protocol", "claude mcp", "mcp server"],

    # SaaS / Business
    "saas":             ["software as a service", "b2b saas", "micro saas"],
    "mrr":              ["monthly recurring revenue", "arr revenue", "subscription revenue"],
    "niche":            ["micro niche", "underserved market", "niche product"],
    "passive income":   ["passive revenue", "automated income", "income streams"],
    "solo founder":     ["solopreneur", "indie hacker", "bootstrapped founder"],
    "churn":            ["customer churn", "retention", "cancellations"],

    # Crypto / DeFi
    "defi":             ["decentralized finance", "yield farming", "liquidity pool"],
    "nft":              ["non fungible token", "web3 nft", "nft market"],
    "solana":           ["SOL", "solana ecosystem", "solana defi"],
    "pump fun":         ["pump.fun", "meme coins", "solana launchpad"],
    "mev":              ["maximal extractable value", "sandwich attack", "arbitrage bot"],

    # Development
    "nextjs":           ["next.js", "react framework", "app router"],
    "typescript":       ["typescript", "ts types", "strongly typed javascript"],
    "api":              ["rest api", "webhook", "api integration"],
    "docker":           ["containerization", "kubernetes", "docker compose"],

    # Marketing
    "seo":              ["search engine optimization", "organic traffic", "google ranking"],
    "content marketing":["blog strategy", "content creation", "content distribution"],
    "viral":            ["viral marketing", "product virality", "word of mouth growth"],
}

_TOKEN_RE = re.compile(r"\b[a-z0-9][a-z0-9\s\-]{2,}\b", re.I)


def expand(query: str, max_variants: int = 3) -> list[str]:
    """
    Return a list of expanded query strings.
    Always includes the original query. Adds synonyms for matched terms.
    max_variants: total number of queries to return (including original).
    """
    q_lower = query.lower().strip()
    extras: list[str] = []

    for term, synonyms in _EXPANSIONS.items():
        if term in q_lower:
            extras.extend(synonyms)
            if len(extras) >= (max_variants - 1) * 3:
                break

    if not extras:
        # No direct match: try partial word overlap
        q_words = set(re.findall(r"\b[a-z]{4,}\b", q_lower))
        for term, synonyms in _EXPANSIONS.items():
            term_words = set(re.findall(r"\b[a-z]{4,}\b", term))
            if q_words & term_words:
                extras.extend(synonyms[:2])
                break

    # Build variant queries by appending synonyms to the original
    variants = [query]
    seen = {q_lower}
    for syn in extras:
        variant = f"{query} {syn}"
        if variant.lower() not in seen:
            seen.add(variant.lower())
            variants.append(variant)
        if len(variants) >= max_variants:
            break

    return variants
