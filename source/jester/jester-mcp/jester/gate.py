"""
Freemium gate for VibeDNA MCP servers.

Only VibeDNA keys (they start with `vbd_`) can unlock Pro. They are validated
against https://vibedna.ai/api/license/validate for the `jester` slug. Any other
value, or no key at all, is the free tier, with no network call.

A yes is cached on disk at ~/.jester/license_cache.json for 24h so we don't hit
the network on every tool call. A no is never cached: a key minted seconds after
payment must work on the next call. Offline, a previous yes is honoured and a
machine that never got a yes stays free.

Config:
    Set MCPIZE_LICENSE_KEY in .env. The key arrives in the purchase email and is
    also in the buyer's library at https://vibedna.ai/library.

Usage:
    from gate import is_paid, UPGRADE_MSG

    if not is_paid():
        return UPGRADE_MSG
"""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

UPGRADE_MSG = (
    "This tool requires JesterDNA Pro. Get it at https://vibedna.ai/store. "
    "Your license key starts with vbd_, arrives in your purchase email and is also "
    "in your library at https://vibedna.ai/library. "
    "Paste it into your .env as MCPIZE_LICENSE_KEY."
)

# Local cache so we don't validate over the network on every tool call.
_CACHE_DIR  = Path(os.environ.get("JESTER_HOME", str(Path.home() / ".jester")))
_CACHE_FILE = _CACHE_DIR / "license_cache.json"
_CACHE_TTL  = 24 * 60 * 60  # 24h

# Both fixed, not read from env: a slug override let a key issued for another
# product (including $0 ones) unlock Jester Pro, and a URL override let any
# server that answers "valid" do the same.
_PRODUCT_SLUG = "jester"
_VALIDATE_URL = "https://vibedna.ai/api/license/validate"


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        return
    try:
        # The cache holds the raw key.
        os.chmod(_CACHE_FILE, 0o600)
    except Exception:
        pass


def _remote_validate(key: str, slug: str, timeout: float = 6.0) -> bool | None:
    """Call vibedna.ai/api/license/validate. Returns True/False on a response,
    None on network failure (so caller can fall back to cache)."""
    try:
        body = json.dumps({"license_key": key, "slug": slug}).encode()
        req = urllib.request.Request(
            _VALIDATE_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "jester-mcp-license/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
            return bool(data.get("valid"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None  # offline / endpoint down: caller falls back to cache


def check_tier() -> str:
    key = os.environ.get("MCPIZE_LICENSE_KEY", "").strip()
    if not key:
        return "free"

    # VibeDNA key: validate against vibedna.ai
    if key.startswith("vbd_"):
        cache = _load_cache()
        entry = cache.get(key)
        now = time.time()
        # Fresh valid cache hit, use it
        if entry and entry.get("valid") and (now - entry.get("ts", 0) < _CACHE_TTL):
            return "paid"
        # Try remote validation
        result = _remote_validate(key, _PRODUCT_SLUG)
        if result is True:
            cache[key] = {"valid": True, "ts": now, "slug": _PRODUCT_SLUG}
            _save_cache(cache)
            return "paid"
        if result is False:
            # Never cache a no, but drop any earlier yes so a revoked or refunded
            # key does not keep working offline.
            if cache.pop(key, None) is not None:
                _save_cache(cache)
            return "free"
        # result is None: network failure. Use any previously-valid cache entry,
        # even if expired, to avoid bricking the user when they're offline.
        if entry and entry.get("valid"):
            return "paid"
        # No prior validation + offline: bias to free so we don't unlock untrusted keys.
        return "free"

    # Keys without the prefix used to pass as "paid" with no check, so any text
    # unlocked every tool. Every paying buyer holds a vbd_ key.
    return "free"


def is_paid() -> bool:
    return check_tier() == "paid"
