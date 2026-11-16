"""Money-flow extractor.

Extracts revenue claims with structured fields + a specificity score 0-100.
"$3k MRR with Next.js + Stripe + AI dev tools niche" scores high.
"Growing fast" scores low.

Pure regex + heuristics. No LLM. Persists to money_claims.db.
Schema is pack-export friendly: versioned, no PII, portable.
"""

import re
import sqlite3
import time
from contextlib import contextmanager

from paths import jester_home


SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS money_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_version  INTEGER DEFAULT 1,
    topic           TEXT,
    amount_usd      REAL,
    frequency       TEXT,
    method          TEXT,
    stack           TEXT,
    niche           TEXT,
    source_url      TEXT,
    creator_id      TEXT,
    snippet         TEXT,
    specificity_score INTEGER,
    claimed_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mc_topic ON money_claims(topic);
CREATE INDEX IF NOT EXISTS idx_mc_score ON money_claims(specificity_score);
CREATE INDEX IF NOT EXISTS idx_mc_amount ON money_claims(amount_usd);
"""


def db_path():
    return jester_home() / "money_claims.db"


@contextmanager
def _conn():
    c = sqlite3.connect(db_path())
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


_AMOUNT_RX = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?\b",
    re.I,
)

_FREQ_RX = re.compile(
    r"\b(mrr|arr|/mo|per month|monthly|per year|/yr|annually|daily|/day|per day|"
    r"weekly|/wk|per week)\b",
    re.I,
)

_FREQ_MAP = {
    "mrr": "monthly", "/mo": "monthly", "per month": "monthly", "monthly": "monthly",
    "arr": "yearly", "/yr": "yearly", "per year": "yearly", "annually": "yearly",
    "daily": "daily", "/day": "daily", "per day": "daily",
    "weekly": "weekly", "/wk": "weekly", "per week": "weekly",
}

STACK_TOKENS = [
    "next.js","nextjs","react","vue","svelte","astro","remix","nuxt",
    "supabase","firebase","postgres","mysql","mongodb","redis",
    "stripe","gumroad","lemonsqueezy","paddle","shopify",
    "vercel","netlify","cloudflare","aws","render","railway","fly.io",
    "openai","anthropic","claude","gpt","llama","gemini","huggingface",
    "tailwind","typescript","python","django","fastapi","flask","node",
    "playwright","selenium","puppeteer",
]

METHOD_TOKENS = [
    "saas","subscription","one-time","newsletter","sponsorship","affiliate",
    "course","ebook","template","theme","plugin","extension","chrome extension",
    "agency","freelance","consulting","ads","adsense","youtube","tiktok",
    "amazon kdp","kdp","etsy","print on demand","pod","dropshipping","arbitrage",
    "mcp","api","b2b","b2c","enterprise","prosumer",
]

NICHE_HINTS = [
    "ai dev tools","developer tools","indie hacker","content creator",
    "real estate","healthcare","fitness","education","crypto","trading",
    "marketing","seo","ecommerce","accounting","legal","hr","recruiting",
    "no-code","low-code","gaming","esports","photography","design",
]


def _parse_amount(text: str) -> float | None:
    m = _AMOUNT_RX.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        v = float(raw)
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix in ("k", "thousand"):
        v *= 1000
    elif suffix in ("m", "million"):
        v *= 1_000_000
    return v


def _detect(text_low: str, candidates: list[str]) -> list[str]:
    return [c for c in candidates if c in text_low]


def extract_claim(text: str) -> dict | None:
    """Returns a structured claim dict if text contains a $-amount + at least
    one of (frequency, method, stack). Otherwise None."""
    if not text:
        return None
    amount = _parse_amount(text)
    if amount is None or amount < 10:
        return None
    text_low = text.lower()
    fq = _FREQ_RX.search(text_low)
    frequency = _FREQ_MAP.get(fq.group(1).lower(), fq.group(1).lower()) if fq else ""
    stack = _detect(text_low, STACK_TOKENS)
    method = _detect(text_low, METHOD_TOKENS)
    niche = _detect(text_low, NICHE_HINTS)

    specificity = 0
    specificity += 25 if amount > 0 else 0
    specificity += 20 if frequency else 0
    specificity += 20 if method else 0
    specificity += 20 if stack else 0
    specificity += 15 if niche else 0
    specificity = min(100, specificity)

    if specificity < 25:
        return None

    return {
        "amount_usd": amount,
        "frequency": frequency,
        "method": ", ".join(method[:3]),
        "stack": ", ".join(stack[:5]),
        "niche": ", ".join(niche[:3]),
        "specificity_score": specificity,
    }


def ingest(items: list[dict], topic: str = "") -> int:
    """Scan items for money claims, persist all with specificity >= 25."""
    if not items:
        return 0
    n = 0
    now = time.time()
    with _conn() as c:
        for it in items:
            text = " ".join([
                it.get("title", "") or "",
                it.get("content") or it.get("snippet") or "",
            ])
            claim = extract_claim(text)
            if not claim:
                continue
            c.execute(
                "INSERT INTO money_claims(schema_version, topic, amount_usd, frequency, method, "
                "stack, niche, source_url, creator_id, snippet, specificity_score, claimed_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (SCHEMA_VERSION, topic, claim["amount_usd"], claim["frequency"],
                 claim["method"], claim["stack"], claim["niche"],
                 it.get("url", "") or "", it.get("creator_id", "") or "",
                 text[:500], claim["specificity_score"], now),
            )
            n += 1
    return n


def extract_money_claims(topic: str = "", min_specificity: int = 70,
                         limit: int = 50) -> list[dict]:
    with _conn() as c:
        if topic:
            rows = c.execute(
                "SELECT amount_usd, frequency, method, stack, niche, source_url, "
                "specificity_score, snippet, claimed_at FROM money_claims "
                "WHERE topic=? AND specificity_score>=? "
                "ORDER BY specificity_score DESC, amount_usd DESC LIMIT ?",
                (topic, min_specificity, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT amount_usd, frequency, method, stack, niche, source_url, "
                "specificity_score, snippet, claimed_at FROM money_claims "
                "WHERE specificity_score>=? ORDER BY specificity_score DESC LIMIT ?",
                (min_specificity, limit),
            ).fetchall()
    return [
        {"amount_usd": r[0], "frequency": r[1], "method": r[2], "stack": r[3],
         "niche": r[4], "source_url": r[5], "specificity_score": r[6],
         "snippet": r[7], "claimed_at": r[8]}
        for r in rows
    ]


def money_flow_summary(topic: str = "", top_n: int = 5) -> dict:
    """Top N ways people make money in `topic`, grouped by method+stack+niche signature."""
    claims = extract_money_claims(topic=topic, min_specificity=50, limit=200)
    buckets: dict[tuple, dict] = {}
    for c in claims:
        key = (c["method"] or "?", c["stack"] or "?", c["niche"] or "?")
        b = buckets.setdefault(key, {"method": key[0], "stack": key[1], "niche": key[2],
                                     "n": 0, "amounts": [], "samples": []})
        b["n"] += 1
        b["amounts"].append(c["amount_usd"])
        if len(b["samples"]) < 3:
            b["samples"].append({"url": c["source_url"], "amount": c["amount_usd"],
                                  "freq": c["frequency"]})
    out = []
    for b in buckets.values():
        amts = sorted(b["amounts"])
        median = amts[len(amts) // 2] if amts else 0
        out.append({**b, "median_amount": median, "amounts": None})
        out[-1].pop("amounts", None)
    out.sort(key=lambda x: (x["n"], x["median_amount"]), reverse=True)
    return {"topic": topic, "top_patterns": out[:top_n], "total_claims": len(claims)}
