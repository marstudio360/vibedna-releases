"""Stage 3 -- FETCH, and stage 4 -- NORMALIZE.

Downloads everything reachable, then sorts it into the library by what the
license actually permits. Download policy is deliberately WIDE (grab it all)
while the shelving policy is STRICT -- you cannot decide what to use if you
never pulled it, but you must never lose track of what you may ship.

Library layout is the deliverable: the folder IS the answer to "which of these
can we use".

    <ASSET_FORGE_LIB>/library/
        01-CLEAN-CC0/     ship anywhere, no paperwork
        02-CREDIT/        ship, but lands in CREDITS.md
        03-CHECK/         TIERED or UNKNOWN -- a human must read it
        04-BLOCKED/       non-commercial or share-alike -- prototype only
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from forge.discover import UA
from forge.licenses import classify, passes

FORGE_HOME = Path(__file__).resolve().parent.parent
# Library root: ASSET_FORGE_LIB, else ~/.asset-forge/library-root (the MCP server re-points it too).
LIB_ROOT = Path(os.environ.get("ASSET_FORGE_LIB", "").strip() or (Path.home() / ".asset-forge" / "library-root"))
RAW = LIB_ROOT / "raw"
EXTRACT = LIB_ROOT / "extracted"
LIBRARY = LIB_ROOT / "library"
META = LIB_ROOT / "meta"

SHELVES = {
    "clean": "01-CLEAN-CC0",
    "credit": "02-CREDIT",
    "check": "03-CHECK",
    "blocked": "04-BLOCKED",
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".aseprite", ".ase"}
AUDIO_EXT = {".wav", ".ogg", ".mp3", ".flac"}
LICENSE_FILE = re.compile(r"(?i)\b(licen[sc]e|copying|readme|terms|credits?)\b")

# Some OGA rows are 100 MB+ art dumps. Cap so one pack can't eat the run.
MAX_BYTES = 300 * 1024 * 1024


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")[:80] or "pack"


# Windows rejects these outright, and trailing dots/spaces silently break too.
_BAD_CHARS = re.compile(r'[\x00-\x1f<>:"|?*\\/]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _safe_member(part: str) -> str:
    """Sanitise one path component of a zip member, preserving readability.

    Unlike _safe this keeps spaces and unicode -- artists name folders
    "Forest Pack" and mangling that makes the library hard to browse. It only
    removes what the filesystem actually refuses.
    """
    cleaned = _BAD_CHARS.sub("", part).rstrip(". ").strip()
    if not cleaned or cleaned in (".", ".."):
        return ""
    if cleaned.split(".")[0].upper() in _RESERVED:
        cleaned = "_" + cleaned
    return cleaned[:120]


def _ensure_dirs() -> None:
    for d in (RAW, EXTRACT, META, LIBRARY):
        d.mkdir(parents=True, exist_ok=True)
    for sub in SHELVES.values():
        (LIBRARY / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------

@dataclass
class Download:
    url: str
    path: Path | None = None
    sha256: str = ""
    bytes: int = 0
    skipped: str = ""
    error: str = ""


def download(url: str, dest_dir: Path, seen_hashes: set[str] | None = None) -> Download:
    d = Download(url=url)
    name = _safe(url.rsplit("/", 1)[-1].split("?")[0]) or "file.bin"
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / name

    if out.exists() and out.stat().st_size > 0:
        d.path, d.bytes = out, out.stat().st_size
        d.sha256 = _sha256(out)
        d.skipped = "already on disk"
        return d

    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            length = int(r.headers.get("Content-Length") or 0)
            if length > MAX_BYTES:
                d.skipped = f"too big ({length // 1024 // 1024} MB)"
                return d
            h = hashlib.sha256()
            total = 0
            with open(out, "wb") as f:
                while chunk := r.read(1 << 16):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        f.close()
                        out.unlink(missing_ok=True)
                        d.skipped = "exceeded size cap mid-stream"
                        return d
                    h.update(chunk)
                    f.write(chunk)
            d.path, d.bytes, d.sha256 = out, total, h.hexdigest()
    except Exception as e:                                      # noqa: BLE001
        d.error = str(e)
        out.unlink(missing_ok=True)
        return d

    if seen_hashes is not None:
        if d.sha256 in seen_hashes:
            out.unlink(missing_ok=True)
            d.path = None
            d.skipped = "duplicate content (sha256 already fetched)"
        else:
            seen_hashes.add(d.sha256)
    return d


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# extract + in-archive license re-check
# ---------------------------------------------------------------------------

def extract(archive: Path, dest: Path) -> tuple[int, str]:
    """Unzip and return (file_count, license_text_found_inside).

    The in-archive license text is the whole point: itch packs routinely state
    nothing on the page and ship a LICENSE.txt in the zip. A page-only verdict
    is provisional until this runs.
    """
    if archive.suffix.lower() != ".zip":
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / archive.name
        if not target.exists():
            shutil.copy2(archive, target)
        return 1, ""

    dest.mkdir(parents=True, exist_ok=True)
    found: list[str] = []
    count = 0
    try:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                # Refuse absolute paths and ../ traversal in archive members.
                rel = Path(info.filename)
                if rel.is_absolute() or ".." in rel.parts:
                    continue

                # Members are extracted one at a time with their names
                # sanitised, rather than via z.extract, because real archives
                # carry names Windows cannot create: trailing "\r" from macOS
                # resource forks, control characters, reserved characters.
                # z.extract raises OSError on those and one bad entry would
                # otherwise abort the whole harvest.
                safe_parts = [_safe_member(part) for part in rel.parts]
                safe_parts = [p for p in safe_parts if p]
                if not safe_parts:
                    continue
                target = dest.joinpath(*safe_parts)
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    count += 1
                except (OSError, zipfile.BadZipFile, RuntimeError):
                    continue    # skip the member, keep the pack

                if LICENSE_FILE.search(safe_parts[-1]) and info.file_size < 200_000:
                    try:
                        found.append(z.read(info).decode("utf-8", errors="replace"))
                    except Exception:                           # noqa: BLE001
                        pass
    except (zipfile.BadZipFile, OSError):
        return count, "\n".join(found)
    return count, "\n".join(found)


def scan_contents(root: Path) -> dict:
    imgs = auds = others = 0
    biggest: list[tuple[int, str]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXT:
            imgs += 1
            biggest.append((p.stat().st_size, str(p.relative_to(root))))
        elif ext in AUDIO_EXT:
            auds += 1
        else:
            others += 1
    biggest.sort(reverse=True)
    return {"images": imgs, "audio": auds, "other": others,
            "largest": [b[1] for b in biggest[:8]]}


# ---------------------------------------------------------------------------
# shelving
# ---------------------------------------------------------------------------

def shelf_for(verdict) -> str:
    if verdict.license_id in ("TIERED", "UNKNOWN"):
        return "check"
    if verdict.commercial_ok is not True:
        return "blocked"
    if verdict.share_alike:
        return "blocked"
    if verdict.attribution_required is False:
        return "clean"
    return "credit"


def harvest_pack(pack, seen_hashes: set[str]) -> dict:
    """Download every link on a pack, extract, re-verdict, shelve."""
    c = pack.candidate
    slug = _safe(f"{c.source}__{c.author or 'unknown'}__{c.title}")
    raw_dir = RAW / slug

    urls = [u for u in pack.downloads if not u.startswith("itch:")]
    itch_uploads = [u for u in pack.downloads if u.startswith("itch:")]

    dls = [download(u, raw_dir, seen_hashes) for u in urls]

    # itch goes through the API: the file streams straight off the download
    # endpoint with a Bearer header, so there is no URL to hand to download().
    for handle in itch_uploads:
        _, uid, fname = handle.split(":", 2)
        raw_dir.mkdir(parents=True, exist_ok=True)
        dest = raw_dir / _safe(fname)
        d = Download(url=handle)
        if dest.exists() and dest.stat().st_size > 0:
            d.path, d.bytes, d.skipped = dest, dest.stat().st_size, "already on disk"
        else:
            from forge import itch_api
            n = itch_api.fetch_upload(int(uid), dest)
            if n:
                d.path, d.bytes, d.sha256 = dest, n, _sha256(dest)
                if seen_hashes is not None:
                    if d.sha256 in seen_hashes:
                        dest.unlink(missing_ok=True)
                        d.path, d.skipped = None, "duplicate content"
                    else:
                        seen_hashes.add(d.sha256)
            else:
                d.error = "itch api download failed or over size cap"
        dls.append(d)

    got = [d for d in dls if d.path]

    ext_dir = EXTRACT / slug
    total_files = 0
    inzip_license = ""
    for d in got:
        n, lic = extract(d.path, ext_dir)
        total_files += n
        if lic:
            inzip_license += "\n" + lic

    # Re-verdict: an in-archive LICENSE beats a page guess.
    verdict = pack.verdict
    upgraded = False
    if inzip_license.strip():
        v2 = classify(inzip_license)
        if v2.license_id not in ("UNKNOWN",) and (
            verdict is None or verdict.license_id in ("UNKNOWN", "TIERED")
            or v2.confidence > verdict.confidence
        ):
            verdict, upgraded = v2, True

    shelf = shelf_for(verdict) if verdict else "check"
    contents = scan_contents(ext_dir) if ext_dir.exists() else {}

    if ext_dir.exists() and total_files:
        link_dir = LIBRARY / SHELVES[shelf] / slug
        if link_dir.exists():
            shutil.rmtree(link_dir, ignore_errors=True)
        shutil.copytree(ext_dir, link_dir)

    return {
        "slug": slug, "source": c.source, "title": c.title, "author": c.author,
        "url": c.url, "shelf": SHELVES[shelf],
        "license": verdict.license_id if verdict else "UNKNOWN",
        "license_name": verdict.name if verdict else "",
        "commercial_ok": verdict.commercial_ok if verdict else None,
        "attribution_required": verdict.attribution_required if verdict else None,
        "matched": (verdict.matched if verdict else "")[:300],
        "verdict_from_archive": upgraded,
        "files_extracted": total_files,
        "downloaded": len(got),
        "download_errors": [d.error for d in dls if d.error][:3],
        "itch_uploads": len(itch_uploads),
        "contents": contents,
    }


def write_manifest(rows: list[dict]) -> Path:
    """Merge into the existing manifest rather than replacing it.

    Sources are harvested in separate runs (sometimes concurrently), and a
    plain overwrite meant whichever finished last erased the others' rows.
    Keyed on slug; a re-harvest of the same pack wins.
    """
    _ensure_dirs()
    p = META / "manifest.json"
    merged: dict[str, dict] = {}
    if p.exists():
        try:
            for r in json.loads(p.read_text(encoding="utf-8")):
                merged[r["slug"]] = r
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    for r in rows:
        merged[r["slug"]] = r
    p.write_text(json.dumps(list(merged.values()), indent=2), encoding="utf-8")
    return p
