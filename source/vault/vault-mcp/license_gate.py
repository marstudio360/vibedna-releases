"""Licence gate for Vibedna MCP servers. One source, copied into each package.

WHY A COPY PER PACKAGE AND NOT AN IMPORT: every MCP we sell has to run on its own, on a
machine that has nothing else of ours. A shared install would be one more thing that can
be missing. So this file is the canonical one and the packager copies it in; the rule is
that nobody edits the copy, they edit this and repackage.

WHAT IT CAN AND CANNOT DO, stated plainly so nobody builds a strategy on top of a wish:
this runs on the buyer's machine, so anyone who opens the file can delete the check. It
stops casual sharing, not a determined copy. The only thing a copy cannot take is what
lives on our side, so the valuable calls belong there, not here.

ONE KEY, SEVERAL PRODUCTS: this asks the site "does this key open <my slug>", and the site
answers. A one-time key opens its own product. A membership key (`vibedna-pro`,
`vibedna-ultra`) opens a set, and the site decides which. Nothing here needs to know the
tiers, which is the point: the price list can change without shipping a new MCP.

BEHAVIOUR THAT MATTERS:
  · A yes is cached for a day. A NO IS NEVER CACHED. Somebody who just paid, whose key
    is minted a few seconds after the webhook lands, must not be told "unlicensed" for an
    hour because of a cached refusal. We have paid for that mistake once already.
  · Offline with a previous yes keeps working. Offline with no history stays free, so a
    made-up key never unlocks anything just by pulling the network cable.
  · Legacy keys with no `vbd_` prefix are accepted. They predate the current flow and
    those buyers must not wake up locked out.

USAGE:
    from license_gate import is_paid, UPGRADE_MSG
    if not is_paid():
        return UPGRADE_MSG
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

# Set by each server before importing, or via env. Must match the slug the key was
# issued for: the endpoint binds a key to its product.
PRODUCT_SLUG = os.environ.get("VIBEDNA_PRODUCT_SLUG", "").strip()
PRODUCT_NAME = os.environ.get("VIBEDNA_PRODUCT_NAME", "").strip() or "this product"
SITE = (os.environ.get("VIBEDNA_SITE") or "https://vibedna.ai").rstrip("/")

_CACHE_FILE = Path(os.environ.get("VIBEDNA_HOME", str(Path.home() / ".vibedna"))) / "license_cache.json"
_CACHE_TTL = 24 * 60 * 60

UPGRADE_MSG = (
    f"This tool needs a licence for {PRODUCT_NAME}. Get it at {SITE}/store, then paste "
    "the key from your purchase email into your .env as MCPIZE_LICENSE_KEY. Your key is "
    f"also in your library at {SITE}/library."
)


def _cache() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass


def _ask(key: str, slug: str, timeout: float = 6.0):
    """True, False, or None when the network is the problem rather than the key."""
    try:
        req = urllib.request.Request(
            f"{SITE}/api/license/validate",
            data=json.dumps({"license_key": key, "slug": slug}).encode(),
            method="POST",
            headers={"Content-Type": "application/json",
                     "User-Agent": f"vibedna-license/{slug or 'mcp'}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return bool(json.loads(r.read().decode("utf-8", "replace")).get("valid"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None


def check_tier(slug: str = "") -> str:
    key = os.environ.get("MCPIZE_LICENSE_KEY", "").strip()
    if not key:
        return "free"
    if not key.startswith("vbd_"):
        return "paid"          # predates this flow; never lock those buyers out

    slug = slug or PRODUCT_SLUG
    c = _cache()
    entry = c.get(key) or {}
    now = time.time()
    if entry.get("valid") and (now - entry.get("ts", 0) < _CACHE_TTL):
        return "paid"

    answer = _ask(key, slug)
    if answer is True:
        c[key] = {"valid": True, "ts": now, "slug": slug}
        _save(c)
        return "paid"
    if answer is False:
        # Deliberately NOT cached. A refusal is the one answer that must be re-asked,
        # because the common cause is a key that exists and has not landed yet.
        return "free"
    # Network problem: honour a previous yes, never invent one.
    return "paid" if entry.get("valid") else "free"


def is_paid(slug: str = "") -> bool:
    return check_tier(slug) == "paid"
