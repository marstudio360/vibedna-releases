"""Centralized writable-path resolution for Jester.

All persistent state (reports, caches, indexes, models, budgets, logs) lives under
JESTER_HOME, which defaults to ~/.jester/ but is overridable via the JESTER_HOME env var.

This keeps the package directory read-only-safe so Jester works in:
- Site-packages installs (pip install jester)
- MCPize / sandboxed deployments
- Multi-user systems
- Read-only container layers
"""

import os
from pathlib import Path


def jester_home() -> Path:
    """Root for all writable Jester state. Created if missing."""
    base = os.environ.get("JESTER_HOME")
    if base:
        root = Path(base).expanduser().resolve()
    else:
        root = Path.home() / ".jester"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sub(name: str) -> Path:
    p = jester_home() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_dir()       -> Path: return _sub("reports")
def snapshots_dir()     -> Path: return _sub("snapshots")
def metrics_dir()       -> Path: return _sub("metrics")
def cache_dir()         -> Path: return _sub("cache")
def fetch_cache_dir()   -> Path: return _sub("fetch_cache")
def budget_dir()        -> Path: return _sub("budget")
def whisper_model_dir() -> Path: return _sub("whisper_models")
def embed_model_dir()   -> Path: return _sub("embedding_models")
def logs_dir()          -> Path: return _sub("logs")


def memory_index_path() -> Path:
    return jester_home() / "memory_index.json"


def personal_index_db() -> Path:
    return jester_home() / "personal_index.db"


def optimizer_state_path() -> Path:
    return jester_home() / "optimizer_state.json"


def learned_domains_path() -> Path:
    return jester_home() / "learned_domains.json"


def self_feed_state_path() -> Path:
    return jester_home() / "self_feed_state.json"


def self_feed_log_path() -> Path:
    return logs_dir() / "self_feed.log"


def youtube_debug_log_path() -> Path:
    return logs_dir() / "youtube_debug.log"


def memory_enabled() -> bool:
    """Whether to inject historical research context into new query results.
    Default: OFF (each user's index starts empty; opt in via JESTER_MEMORY=1)."""
    return os.environ.get("JESTER_MEMORY", "").lower() in {"1", "true", "yes", "on"}
