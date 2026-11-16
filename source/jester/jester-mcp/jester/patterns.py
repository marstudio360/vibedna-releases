"""Pattern surfacing: convert raw clusters into themes, contrarians, outliers.

Uses Haiku (cheap) via budget.py to synthesize. Falls back to a deterministic
rule-based pass if no API key / over budget. Returns a structured dict. No
markdown rendering, that's the caller's job.
"""

import json
import os
from typing import Any

from corroborate import cluster_findings
from budget import check_budget, record_spend


SYNTH_PROMPT = """You are condensing raw research findings into strategic patterns for a builder.

Topic: {topic}

Clusters (each = one idea found across multiple sources):
{clusters_json}

Return STRICT JSON with these keys:
{{
  "patterns": [up to {max_patterns} strings: themes everyone converges on],
  "contrarian": [up to 2 strings: credible-looking opposing views],
  "outliers": [up to 1 string: something only one source noticed but looks important],
  "tldr": "one sentence: the state of the world on this topic right now"
}}

Be specific. No fluff. Quote concrete tools / numbers / approaches when present.
"""


def _rule_based(clusters: list[dict], max_patterns: int = 5) -> dict:
    """Cheap fallback, no LLM call. Pure ranking heuristic."""
    sorted_cl = sorted(clusters, key=lambda c: (c.get("n_creators", 0), c.get("n_sources", 0)), reverse=True)
    patterns = [c["idea"] for c in sorted_cl[:max_patterns] if c.get("n_creators", 0) >= 2]
    if not patterns:
        patterns = [c["idea"] for c in sorted_cl[:max_patterns]]
    outliers = [c["idea"] for c in sorted_cl if c.get("n_creators", 0) == 1 and c.get("n_findings", 0) >= 2][:1]
    return {
        "patterns": patterns,
        "contrarian": [],
        "outliers": outliers,
        "tldr": f"{len(sorted_cl)} ideas across {sum(c['n_sources'] for c in sorted_cl)} source mentions.",
        "_method": "rule-based",
    }


def synthesize_patterns(topic: str, max_patterns: int = 5,
                        include_contrarian: bool = True,
                        include_outlier: bool = True) -> dict:
    clusters = cluster_findings(topic)
    if not clusters:
        return {"patterns": [], "contrarian": [], "outliers": [],
                "tldr": "No findings indexed for this topic yet.", "_method": "empty"}

    budget = check_budget("haiku", ["web"], "quick", False)
    if not budget["ok"] or not os.environ.get("ANTHROPIC_API_KEY"):
        return _rule_based(clusters, max_patterns=max_patterns)

    try:
        from anthropic import Anthropic
    except ImportError:
        return _rule_based(clusters, max_patterns=max_patterns)

    compact = [
        {"idea": c["idea"], "n_creators": c.get("n_creators", 0),
         "n_sources": c.get("n_sources", 0),
         "sources": c.get("corroborating_sources", [])[:5]}
        for c in clusters[:25]
    ]
    prompt = SYNTH_PROMPT.format(
        topic=topic,
        clusters_json=json.dumps(compact, indent=2),
        max_patterns=max_patterns,
    )
    try:
        client = Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else ""
        in_tok = getattr(resp.usage, "input_tokens", 0)
        out_tok = getattr(resp.usage, "output_tokens", 0)
        record_spend("haiku", in_tok, out_tok, sources=["pattern-synth"])
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start:end + 1])
            if not include_contrarian:
                data["contrarian"] = []
            if not include_outlier:
                data["outliers"] = []
            data["_method"] = "haiku"
            return data
    except Exception as e:
        return {**_rule_based(clusters, max_patterns=max_patterns),
                "_llm_error": str(e)[:120]}

    return _rule_based(clusters, max_patterns=max_patterns)
