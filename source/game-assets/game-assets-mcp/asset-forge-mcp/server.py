#!/usr/bin/env python3
"""
Asset Forge MCP -- a license-audited game-asset library as MCP tools.

Wraps the ASSET FORGE harvesting pipeline: discover free asset packs
(itch.io / OpenGameArt / Kenney), classify their licenses with an audit
trail (the exact phrase that decided the verdict), download + extract +
shelve them by what the license actually permits, and export packs into
game projects with automatic CREDITS.md attribution.

Library layout (under ASSET_FORGE_LIB):
    library/01-CLEAN-CC0/   ship anywhere, no paperwork
    library/02-CREDIT/      ship, but the pack lands in CREDITS.md
    library/03-CHECK/       tiered/unknown license -- human must read it
    library/04-BLOCKED/     non-commercial or share-alike -- prototype only
    meta/manifest.json      one row per harvested pack
    raw/  extracted/        downloads and unpacked contents

8 tools:
  library_stats     -- shelves, pack counts, image/audio totals            [FREE]
  search_packs      -- search the manifest by title/author/tags/license    [FREE]
  pack_info         -- full manifest row + on-disk file counts             [FREE]
  classify_license  -- run the license classifier on any text              [FREE]
  discover          -- list candidate packs from a source (no downloads)   [FREE]
  harvest           -- discover + download + verdict + shelve + manifest   [PAID-ish]
  export_pack       -- copy a pack into a project, policy-gated + credits  [FREE]
  rebuild_gallery   -- regenerate the browsable HTML gallery               [FREE]

Config (env vars -- no personal paths live in this file):
  ASSET_FORGE_HOME  dir containing the forge/ package (and gallery.py).
                    Default: this server's own dir if it holds forge/,
                    else ~/.asset-forge
  ASSET_FORGE_LIB   library root. Default: ~/.asset-forge/library-root
  ITCH_API_KEY      itch.io API key, passed through to the itch adapter
                    (required only for harvesting itch packs)
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("asset-forge")

_HERE = Path(__file__).resolve().parent


# -- Config ------------------------------------------------------------------

def _default_home() -> Path:
    if (_HERE / "forge").is_dir():
        return _HERE
    return Path.home() / ".asset-forge"


_home = os.environ.get("ASSET_FORGE_HOME", "").strip()
FORGE_HOME = Path(_home) if _home else _default_home()
# Accept pointing directly at the forge/ package instead of its parent.
if FORGE_HOME.name == "forge" and (FORGE_HOME / "licenses.py").exists():
    FORGE_HOME = FORGE_HOME.parent

_lib = os.environ.get("ASSET_FORGE_LIB", "").strip()
LIB_ROOT = Path(_lib) if _lib else Path.home() / ".asset-forge" / "library-root"

sys.path.insert(0, str(FORGE_HOME))

_IMPORT_ERROR = ""
try:
    from forge import discover as _discover          # noqa: E402
    from forge import fetch as _fetch                # noqa: E402
    from forge import licenses as _licenses          # noqa: E402
    from forge import packpage as _packpage          # noqa: E402

    # The pipeline computes its dirs from LIB_ROOT at import time. Re-point
    # every one of them at the configured root BEFORE anything else (gallery)
    # imports them by value.
    _fetch.LIB_ROOT = LIB_ROOT
    _fetch.RAW = LIB_ROOT / "raw"
    _fetch.EXTRACT = LIB_ROOT / "extracted"
    _fetch.LIBRARY = LIB_ROOT / "library"
    _fetch.META = LIB_ROOT / "meta"
except Exception as e:                               # noqa: BLE001
    _IMPORT_ERROR = (
        f"cannot import the forge pipeline from {FORGE_HOME}: "
        f"{type(e).__name__}: {e}. Set ASSET_FORGE_HOME to the directory "
        f"that contains the forge/ package."
    )


# -- Helpers -----------------------------------------------------------------

def _ok(data: dict) -> str:
    return json.dumps({"ok": True, **data}, indent=2, ensure_ascii=False)


def _err(msg: str, **extra) -> str:
    return json.dumps({"ok": False, "error": msg, **extra}, indent=2, ensure_ascii=False)


def _guard() -> str | None:
    if _IMPORT_ERROR:
        return _err(_IMPORT_ERROR)
    return None


@contextlib.contextmanager
def _mute_stdout():
    """The pipeline prints progress to stdout; on a stdio MCP server that
    would corrupt the JSON-RPC stream. Capture it and return it as data."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


def _log_tail(buf: io.StringIO, n: int = 30) -> list[str]:
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    return lines[-n:]


def _read_manifest() -> tuple[list[dict], str]:
    """Read manifest.json, tolerant of a concurrent harvest mid-write.
    Returns (rows, error). Empty rows + empty error = manifest absent."""
    p = LIB_ROOT / "meta" / "manifest.json"
    if not p.exists():
        return [], ""
    last = ""
    for attempt in range(2):
        try:
            return json.loads(p.read_text(encoding="utf-8")), ""
        except (json.JSONDecodeError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
            if attempt == 0:
                time.sleep(0.6)
    return [], f"manifest unreadable (possibly mid-write): {last}"


def _find_row(rows: list[dict], slug: str) -> dict | None:
    for r in rows:
        if r.get("slug") == slug:
            return r
    return None


def _close_slugs(rows: list[dict], slug: str, n: int = 5) -> list[str]:
    s = slug.lower()
    return [r["slug"] for r in rows if s in r.get("slug", "").lower()][:n]


def _norm_source(source: str) -> str:
    s = (source or "").strip().lower()
    if s in ("oga", "opengameart", "open-game-art"):
        return "opengameart"
    if s in ("itch", "itch.io", "itchio"):
        return "itch"
    if s == "kenney":
        return "kenney"
    return ""


def _run_discovery(source: str, query_or_tag: str, pages: int) -> list:
    """Shared by discover + harvest. Returns deduped Candidate list."""
    if source == "itch":
        tags = [t for t in re.split(r"[,\s]+", query_or_tag) if t]
        if not tags:
            raise ValueError("itch needs at least one tag, e.g. 'pixel-art' or 'pixel-art,rpg'")
        if len(tags) > 1:
            cands = _discover.itch_browse_tags(tags, pages=pages, mode="all")
        else:
            cands = _discover.itch_browse(tags[0], pages=pages)
    elif source == "opengameart":
        if not query_or_tag.strip():
            raise ValueError("opengameart needs a search query, e.g. 'medieval tileset'")
        cands = _discover.opengameart_search(query_or_tag.strip(), pages=pages)
    else:  # kenney
        slugs = [t for t in re.split(r"[,\s]+", query_or_tag) if t] or None
        cands = _discover.kenney_index(slugs=slugs)
    return _discover.dedupe(cands)


def _policy_shelves(policy: str) -> set[str]:
    """Which shelves clear a policy. Derived from the pipeline's own logic:
    shelf_for() already encoded passes() at shelving time, so the shelf IS
    the policy answer -- no re-classification needed."""
    sh = _fetch.SHELVES
    if policy == "sellable_clean":
        return {sh["clean"]}
    if policy == "sellable_credited":
        return {sh["clean"], sh["credit"]}
    return set(sh.values())  # prototype: everything is usable in a prototype


# -- Tools -------------------------------------------------------------------

@mcp.tool()
def library_stats() -> str:
    """[FREE] Library overview: packs per shelf, image/audio totals, disk state.

    Combines the manifest (what was harvested) with the filesystem (what is
    actually shelved on disk). Shelves: 01-CLEAN-CC0 ships anywhere,
    02-CREDIT ships with attribution, 03-CHECK needs a human read,
    04-BLOCKED is prototype-only."""
    if (g := _guard()):
        return g
    rows, m_err = _read_manifest()

    shelves: dict[str, dict] = {}
    for name in _fetch.SHELVES.values():
        shelves[name] = {"manifest_packs": 0, "images": 0, "audio": 0, "on_disk_packs": 0}
    for r in rows:
        s = r.get("shelf", "")
        if s not in shelves:
            shelves[s] = {"manifest_packs": 0, "images": 0, "audio": 0, "on_disk_packs": 0}
        c = r.get("contents") or {}
        shelves[s]["manifest_packs"] += 1
        shelves[s]["images"] += c.get("images", 0)
        shelves[s]["audio"] += c.get("audio", 0)

    lib_dir = LIB_ROOT / "library"
    for name, d in shelves.items():
        sd = lib_dir / name
        if sd.is_dir():
            d["on_disk_packs"] = sum(1 for p in sd.iterdir() if p.is_dir())

    out = {
        "library_root": str(LIB_ROOT),
        "manifest": str(LIB_ROOT / "meta" / "manifest.json"),
        "total_packs": len(rows),
        "total_images": sum(d["images"] for d in shelves.values()),
        "total_audio": sum(d["audio"] for d in shelves.values()),
        "shelves": shelves,
    }
    if m_err:
        out["warning"] = m_err
    return _ok(out)


@mcp.tool()
def search_packs(query: str, shelf: str = "", license: str = "", limit: int = 20) -> str:
    """[FREE] Search the harvested library manifest.

    query matches title / author / slug / url / tags (case-insensitive
    substring). Optional filters: shelf (full name like '01-CLEAN-CC0' or
    short form clean/credit/check/blocked) and license (substring of the
    license id, e.g. 'CC0', 'CC-BY', 'GPL'). Returns up to `limit` rows."""
    if (g := _guard()):
        return g
    rows, m_err = _read_manifest()
    if m_err:
        return _err(m_err)

    shelf_filter = ""
    if shelf.strip():
        s = shelf.strip().lower()
        shelf_filter = _fetch.SHELVES.get(s, "")
        if not shelf_filter:
            for name in _fetch.SHELVES.values():
                if s in name.lower():
                    shelf_filter = name
                    break
        if not shelf_filter:
            return _err(f"unknown shelf '{shelf}'",
                        valid=sorted(_fetch.SHELVES.values()) + sorted(_fetch.SHELVES))

    q = query.strip().lower()
    lic = license.strip().lower()
    hits = []
    for r in rows:
        if shelf_filter and r.get("shelf") != shelf_filter:
            continue
        if lic and lic not in (r.get("license") or "").lower():
            continue
        hay = " ".join([
            r.get("title", ""), r.get("author", ""), r.get("slug", ""),
            r.get("url", ""), " ".join(r.get("tags") or []),
        ]).lower()
        if q and q not in hay:
            continue
        c = r.get("contents") or {}
        hits.append({
            "slug": r.get("slug"), "title": r.get("title"),
            "author": r.get("author"), "source": r.get("source"),
            "shelf": r.get("shelf"), "license": r.get("license"),
            "images": c.get("images", 0), "audio": c.get("audio", 0),
            "url": r.get("url"),
        })

    return _ok({"query": query, "matches": len(hits), "shown": min(len(hits), limit),
                "packs": hits[:limit]})


@mcp.tool()
def pack_info(slug: str) -> str:
    """[FREE] Everything known about one pack: full manifest row (license
    verdict incl. the matched phrase), plus live on-disk state -- raw
    download dir, extracted dir with file/image counts, and the shelved
    library copy path."""
    if (g := _guard()):
        return g
    rows, m_err = _read_manifest()
    if m_err:
        return _err(m_err)
    row = _find_row(rows, slug)
    if not row:
        return _err(f"no pack with slug '{slug}' in the manifest",
                    similar=_close_slugs(rows, slug))

    raw_dir = LIB_ROOT / "raw" / slug
    ext_dir = LIB_ROOT / "extracted" / slug
    shelf_dir = LIB_ROOT / "library" / row.get("shelf", "") / slug

    disk = {
        "raw_dir": str(raw_dir) if raw_dir.is_dir() else None,
        "extracted_dir": str(ext_dir) if ext_dir.is_dir() else None,
        "library_dir": str(shelf_dir) if shelf_dir.is_dir() else None,
    }
    if ext_dir.is_dir():
        files = [p for p in ext_dir.rglob("*") if p.is_file()]
        disk["extracted_files"] = len(files)
        disk["extracted_images"] = sum(
            1 for p in files if p.suffix.lower() in _fetch.IMAGE_EXT)
        disk["extracted_audio"] = sum(
            1 for p in files if p.suffix.lower() in _fetch.AUDIO_EXT)

    return _ok({"pack": row, "disk": disk})


@mcp.tool()
def classify_license(text: str) -> str:
    """[FREE] Run the license classifier on any text (a page excerpt, a
    LICENSE.txt, a one-line grant). Returns the structured verdict --
    license id, commercial_ok, attribution_required, share_alike,
    confidence, and the EXACT phrase that decided it -- plus whether the
    verdict clears each shipping policy (sellable_clean /
    sellable_credited / prototype) and which shelf it would land on.
    Nothing is classified on vibes; UNKNOWN means quarantine."""
    if (g := _guard()):
        return g
    v = _licenses.classify(text)
    policies = {}
    for name in _licenses.POLICIES:
        ok, reason = _licenses.passes(v, name)
        policies[name] = {"passes": ok, "reason": reason}
    return _ok({
        "verdict": v.as_dict(),
        "policies": policies,
        "shelf": _fetch.SHELVES[_fetch.shelf_for(v)],
    })


@mcp.tool()
def discover(source: str, query_or_tag: str = "", pages: int = 1) -> str:
    """[FREE] List candidate packs from one source WITHOUT downloading
    anything. Network: listing pages only.

    source: 'itch' (query_or_tag = tag, or comma-separated tags which are
    intersected client-side, e.g. 'pixel-art,rpg'), 'opengameart' / 'oga'
    (query_or_tag = search query), or 'kenney' (query_or_tag empty for the
    curated seed list, or comma-separated pack slugs). Discovery records
    what a listing CLAIMS -- the license verdict only exists after
    harvest reads each pack page."""
    if (g := _guard()):
        return g
    src = _norm_source(source)
    if not src:
        return _err(f"unknown source '{source}'", valid=["itch", "opengameart", "kenney"])
    try:
        with _mute_stdout() as buf:
            cands = _run_discovery(src, query_or_tag, max(1, pages))
    except ValueError as e:
        return _err(str(e))
    except Exception as e:                           # noqa: BLE001
        return _err(f"discovery failed: {type(e).__name__}: {e}")
    return _ok({
        "source": src,
        "candidates": len(cands),
        "packs": [c.as_dict() for c in cands],
        "log": _log_tail(buf),
    })


@mcp.tool()
def harvest(source: str, query_or_tag: str = "", pages: int = 1, max_packs: int = 10) -> str:
    """[PAID-ish: heavy network + disk, no dollar cost] Full pipeline for one
    source: discover candidates, read each pack page for its license,
    download every reachable file (capped per pack), extract, re-verdict
    from any in-archive LICENSE file, shelve into the library by what the
    license permits, and merge results into manifest.json.

    Download policy is deliberately WIDE (grab it all) while shelving stays
    STRICT -- a blocked pack still lands on 04-BLOCKED for prototyping.
    itch source requires ITCH_API_KEY in the environment. Rate-limited to
    ~1 request / 1.2s per page read; expect max_packs * a few seconds plus
    download time."""
    if (g := _guard()):
        return g
    src = _norm_source(source)
    if not src:
        return _err(f"unknown source '{source}'", valid=["itch", "opengameart", "kenney"])
    if src == "itch" and not os.environ.get("ITCH_API_KEY", "").strip():
        return _err("ITCH_API_KEY is not set -- itch downloads go through the "
                    "itch.io API and need it. Set the env var and retry.")

    try:
        with _mute_stdout() as buf:
            cands = _run_discovery(src, query_or_tag, max(1, pages))
            if src == "itch":
                cands = [c for c in cands if c.game_id]  # API needs the game_id
            cands = cands[: max(1, max_packs)]

            _fetch._ensure_dirs()
            packs = _packpage.read_many(cands, verbose=False)

            seen: set[str] = set()
            rows: list[dict] = []
            failed: list[dict] = []
            for p in packs:
                if not p.ok:
                    failed.append({"title": p.title, "error": p.error[:200]})
                    continue
                rows.append(_fetch.harvest_pack(p, seen))
            manifest_path = _fetch.write_manifest(rows) if rows else None
    except ValueError as e:
        return _err(str(e))
    except Exception as e:                           # noqa: BLE001
        return _err(f"harvest failed: {type(e).__name__}: {e}")

    results = [{
        "slug": r["slug"], "title": r["title"], "shelf": r["shelf"],
        "license": r["license"],
        "verdict_from_archive": r["verdict_from_archive"],
        "files_extracted": r["files_extracted"],
        "images": (r.get("contents") or {}).get("images", 0),
        "audio": (r.get("contents") or {}).get("audio", 0),
        "download_errors": r.get("download_errors") or [],
    } for r in rows]

    by_shelf: dict[str, int] = {}
    for r in rows:
        by_shelf[r["shelf"]] = by_shelf.get(r["shelf"], 0) + 1

    return _ok({
        "source": src,
        "candidates_found": len(cands),
        "harvested": len(rows),
        "failed": failed,
        "by_shelf": by_shelf,
        "manifest": str(manifest_path) if manifest_path else None,
        "packs": results,
        "log": _log_tail(buf),
    })


@mcp.tool()
def export_pack(slug: str, dest_dir: str, policy: str = "sellable_credited") -> str:
    """[FREE] Copy a harvested pack into a game project directory, gated by
    shipping policy. REFUSES (with the reason and the license evidence) if
    the pack's shelf does not clear the policy:
      sellable_clean    -> only 01-CLEAN-CC0 (zero paperwork)
      sellable_credited -> 01-CLEAN-CC0 + 02-CREDIT
      prototype         -> any shelf (never ship a prototype-only pack!)
    For attribution-required packs it appends a credit line to
    CREDITS.md in dest_dir (deduped -- exporting twice adds one line).
    dest_dir must be an absolute path; files land in dest_dir/<slug>/."""
    if (g := _guard()):
        return g
    if policy not in _licenses.POLICIES:
        return _err(f"unknown policy '{policy}'", valid=sorted(_licenses.POLICIES))
    dest = Path(dest_dir)
    if not dest.is_absolute():
        return _err("dest_dir must be an absolute path")

    rows, m_err = _read_manifest()
    if m_err:
        return _err(m_err)
    row = _find_row(rows, slug)
    if not row:
        return _err(f"no pack with slug '{slug}' in the manifest",
                    similar=_close_slugs(rows, slug))

    shelf = row.get("shelf", "")
    allowed = _policy_shelves(policy)
    if shelf not in allowed:
        return _err(
            f"REFUSED: '{slug}' is on shelf {shelf} "
            f"(license {row.get('license')}); policy '{policy}' only accepts "
            f"{sorted(allowed)}",
            license=row.get("license"),
            license_name=row.get("license_name"),
            matched_phrase=row.get("matched", ""),
            hint="use policy='prototype' if this is for a non-shipping prototype",
        )

    src = LIB_ROOT / "library" / shelf / slug
    if not src.is_dir():
        src = LIB_ROOT / "extracted" / slug
    if not src.is_dir():
        return _err(f"pack '{slug}' is in the manifest but its files are not on "
                    f"disk (checked library/{shelf}/{slug} and extracted/{slug})")

    target = dest / slug
    try:
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, target, dirs_exist_ok=True)
    except OSError as e:
        return _err(f"copy failed: {e}")
    copied = sum(1 for p in target.rglob("*") if p.is_file())

    credit_added = False
    credits_path = dest / "CREDITS.md"
    needs_credit = (shelf == _fetch.SHELVES["credit"]
                    or row.get("attribution_required") is True)
    if needs_credit:
        v = _licenses.Verdict(
            license_id=row.get("license", "UNKNOWN"),
            name=row.get("license_name") or row.get("license", ""),
            commercial_ok=row.get("commercial_ok"),
            attribution_required=row.get("attribution_required"),
            share_alike=None, redistribute_ok=None, confidence=0.0,
        )
        line = _licenses.credit_line(
            row.get("title", slug), row.get("author") or "unknown",
            row.get("url", ""), v)
        existing = credits_path.read_text(encoding="utf-8") if credits_path.exists() else ""
        marker = row.get("url") or row.get("title") or slug
        if marker not in existing:
            if not existing:
                existing = "# Asset Credits\n\n"
            if not existing.endswith("\n"):
                existing += "\n"
            credits_path.write_text(existing + line + "\n", encoding="utf-8")
            credit_added = True

    return _ok({
        "slug": slug, "policy": policy, "shelf": shelf,
        "license": row.get("license"),
        "exported_to": str(target),
        "files_copied": copied,
        "credit_required": needs_credit,
        "credit_added": credit_added,
        "credits_file": str(credits_path) if needs_credit else None,
    })


@mcp.tool()
def rebuild_gallery() -> str:
    """[FREE] Regenerate the browsable HTML gallery of the whole library --
    one index page plus one page per shelf, with inlined sprite previews so
    the art can be judged on sight. Pages are written into the library
    root. Local disk work only; can take a minute on a large library."""
    if (g := _guard()):
        return g
    gallery_py = FORGE_HOME / "gallery.py"
    if not gallery_py.exists():
        return _err(f"gallery builder not found at {gallery_py}")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_asset_forge_gallery", gallery_py)
        mod = importlib.util.module_from_spec(spec)
        with _mute_stdout():
            spec.loader.exec_module(mod)
            index = mod.build()
    except Exception as e:                           # noqa: BLE001
        return _err(f"gallery build failed: {type(e).__name__}: {e}")

    pages = sorted(str(p) for p in Path(index).parent.glob("gallery*.html"))
    return _ok({"index": str(index), "pages": pages})


if __name__ == "__main__":
    mcp.run()
