"""itch.io API adapter.

Why this exists: itch's free-download link is NOT in the page HTML. The button
is `<a class="direct_download_btn" href="">` with an empty href that JS fills
in, so no amount of scraping reaches it. The API is the only path a headless
harvester can take, and it is the sanctioned one.

Flow (verified 2026-08-09 against api.itch.io):
    GET /profile                       -> auth check
    GET /games/<game_id>/uploads       -> [{id, filename, size, type}, ...]
    GET /uploads/<upload_id>/download  -> streams the file directly
                                          (200 application/x-zip-compressed)

game_id comes free from discovery: itch browse cells carry data-game_id.

The key is read from the environment (ITCH_API_KEY), so this module never
holds a literal. Create one at itch.io: Settings, API keys.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

API = "https://api.itch.io"
UA = "AssetForge/1.0 (+license-audited game asset harvesting)"

# Upload types worth pulling for a 2D game. itch also serves windows/linux/mac
# executables and HTML builds under the same game -- those are not assets.
ASSET_TYPES = {"graphical_assets", "audio_assets", "soundtrack", "book", "other", "default"}
SKIP_EXT = (".exe", ".dmg", ".apk", ".deb", ".msi")


class ItchAuthError(RuntimeError):
    pass


def api_key() -> str:
    k = os.environ.get("ITCH_API_KEY", "").strip()
    if not k:
        raise ItchAuthError(
            "ITCH_API_KEY not set. Create a key at itch.io (Settings, API keys) "
            "and set it in the environment before running the harvester.")
    return k


def _headers() -> dict:
    return {"Authorization": f"Bearer {api_key()}", "User-Agent": UA}


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Drop Authorization when a redirect crosses to another host.

    /uploads/<id>/download answers 302 to a CDN host. urllib re-sends every
    header on the redirect, so the CDN receives an itch Bearer token it never
    asked for and answers 400 Bad Request. Browsers and PowerShell strip
    credentials on cross-origin redirects automatically; urllib does not.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        if urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            for key in [k for k in new.headers if k.lower() == "authorization"]:
                del new.headers[key]
            new.unredirected_hdrs.pop("Authorization", None)
        return new


_opener = urllib.request.build_opener(_StripAuthOnRedirect)


def _get_json(path: str, timeout: int = 45) -> dict:
    req = urllib.request.Request(API + path, headers=_headers())
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


@dataclass
class Upload:
    id: int
    filename: str
    size: int
    type: str

    @property
    def is_asset(self) -> bool:
        if self.filename.lower().endswith(SKIP_EXT):
            return False
        return self.type in ASSET_TYPES

    @property
    def is_project(self) -> bool:
        """A shipped engine project (Godot/Unity source) -- gold for reference."""
        n = self.filename.lower()
        return "godot" in n or "unity" in n or "project" in n


def whoami() -> str:
    return _get_json("/profile").get("user", {}).get("username", "?")


def uploads(game_id: int) -> list[Upload]:
    try:
        data = _get_json(f"/games/{game_id}/uploads")
    except Exception:                                           # noqa: BLE001
        return []
    out = []
    for u in data.get("uploads", []):
        out.append(Upload(id=u.get("id", 0), filename=u.get("filename", ""),
                          size=u.get("size", 0) or 0, type=u.get("type", "") or ""))
    return out


def download_url(upload_id: int) -> str:
    """The endpoint streams the file directly when given the Bearer header."""
    return f"{API}/uploads/{upload_id}/download"


def fetch_upload(upload_id: int, dest, max_bytes: int = 400 * 1024 * 1024) -> int:
    """Stream one upload to disk. Returns bytes written, 0 on skip/failure."""
    req = urllib.request.Request(download_url(upload_id), headers=_headers())
    total = 0
    try:
        with _opener.open(req, timeout=300) as r:
            length = int(r.headers.get("Content-Length") or 0)
            if length > max_bytes:
                return 0
            with open(dest, "wb") as f:
                while chunk := r.read(1 << 16):
                    total += len(chunk)
                    if total > max_bytes:
                        f.close()
                        dest.unlink(missing_ok=True)
                        return 0
                    f.write(chunk)
    except Exception:                                           # noqa: BLE001
        try:
            dest.unlink(missing_ok=True)
        except Exception:                                       # noqa: BLE001
            pass
        return 0
    return total


if __name__ == "__main__":
    print("auth as:", whoami())
    for u in uploads(932677):
        tag = "ASSET" if u.is_asset else "     "
        proj = " [PROJECT]" if u.is_project else ""
        print(f"  {tag} {u.id:>10} {u.size/1024/1024:>7.1f} MB  {u.type:<18} {u.filename}{proj}")
