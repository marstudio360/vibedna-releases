"""
Jester daemon: single persistent HTTP server for all Jester MCP tools.

Replaces the per-MCP-tab stdio model. All tabs proxy via HTTP to this one
process, which owns the full Jester library import (~600 MB) ONCE instead
of N times.

Port-bind singleton: only one daemon can run (port 7843 is exclusive).
Lazy-spawned by server.py client mode on first MCP call.

This file does NOT modify server.py. It imports server.py, which auto-registers
all 62 tools into the FastMCP `mcp` object via @mcp.tool() decorators. We then
expose each tool via HTTP for client tabs to proxy to.

(c) 2026 VibeDNA
"""

import os
os.environ["JESTER_ROLE"] = "daemon"  # for future use; server.py doesn't read it yet

import sys
import json
import time
import threading
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

__version__ = "1.0.3"

# ── Config loader ────────────────────────────────────────────────────────────
# All knobs have safe defaults; ~/.jester/config.toml is optional. Bad TOML
# falls back to defaults with a stderr warning. Never crashes the daemon.
# BOM-tolerant (Notepad/PowerShell-friendly).
_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 7843,
    "idle_timeout_s": 30 * 60,
    "max_uptime_s": 60 * 60,
    "ram_cap_mb": 800,           # higher than Hive: jester legitimately uses more RAM
    "drain_timeout_s": 5.0,
    "circuit_failure_threshold": 5,
    "circuit_cooldown_s": 60.0,
    "heartbeat_interval_s": 30,
    "heartbeat_timeout_s": 10,
    "log_max_bytes": 5 * 1024 * 1024,
    "metrics_window": 100,
}


def _load_config() -> dict:
    cfg = dict(_DEFAULTS)
    path = Path.home() / ".jester" / "config.toml"
    if not path.exists():
        return cfg
    try:
        import tomllib  # stdlib 3.11+
        text = path.read_bytes().decode("utf-8-sig")  # strip BOM if present
        raw = tomllib.loads(text)
        section = raw.get("daemon", raw)
        for k, v in section.items():
            if k in cfg:
                cfg[k] = v
    except Exception as e:
        print(f"[jester-daemon] config.toml parse failed ({e}), using defaults", file=sys.stderr)
    return cfg


_CFG = _load_config()

JESTER_HOST = _CFG["host"]
# Honor Cloud Run / PaaS PORT env var (overrides config), required for hosted deployments
_env_port = os.environ.get("PORT")
JESTER_PORT = int(_env_port) if (_env_port and _env_port.isdigit()) else _CFG["port"]
# When running in Cloud Run, bind 0.0.0.0 so the container is reachable
if _env_port:
    JESTER_HOST = "0.0.0.0"
IDLE_TIMEOUT_SECONDS = _CFG["idle_timeout_s"]
MAX_UPTIME_SECONDS = _CFG["max_uptime_s"]
DRAIN_TIMEOUT_S = _CFG["drain_timeout_s"]

# ── Structured logging ───────────────────────────────────────────────────────
_LOG_PATH = Path.home() / ".jester" / "daemon.jsonl"
_LOG_MAX_BYTES = _CFG["log_max_bytes"]
_log_lock = threading.Lock()
try:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


def _log(level: str, event: str, **fields):
    record = {
        "ts": time.time(),
        "level": level,
        "event": event,
        "version": __version__,
        "pid": os.getpid(),
        **fields,
    }
    line = json.dumps(record, default=str, ensure_ascii=False)
    human = f"[jester-daemon {level}] {event}"
    if fields:
        human += " " + " ".join(f"{k}={v}" for k, v in fields.items())
    print(human, file=sys.stderr, flush=True)
    try:
        with _log_lock:
            if _LOG_PATH.exists() and _LOG_PATH.stat().st_size > _LOG_MAX_BYTES:
                rotated = _LOG_PATH.with_suffix(".jsonl.1")
                try:
                    if rotated.exists():
                        rotated.unlink()
                    _LOG_PATH.rename(rotated)
                except Exception:
                    pass
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


# ── Port-bind singleton ──────────────────────────────────────────────────────
try:
    _bound_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _bound_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    _bound_socket.bind((JESTER_HOST, JESTER_PORT))
except OSError:
    _log("warn", "port_already_bound", port=JESTER_PORT)
    sys.exit(0)


# ── Import server.py: this loads all 62 tools into FastMCP ───────────────────
_log("info", "loading_server_module")
import server as _server
_log("info", "server_module_loaded")

# Grab the FastMCP-registered tools.
# Note: jester uses the standalone `fastmcp` library (not mcp.server.fastmcp),
# which exposes tools via async _list_tools() rather than _tool_manager._tools.
TOOLS = {}
try:
    import asyncio as _asyncio
    _tool_list = _asyncio.run(_server.mcp._list_tools())
    for tool_obj in _tool_list:
        fn = getattr(tool_obj, "fn", None) or getattr(tool_obj, "func", None)
        if fn:
            TOOLS[tool_obj.name] = fn
except Exception as e:
    _log("error", "tool_extraction_failed", err=str(e))
    raise

_log("info", "tools_loaded", count=len(TOOLS))


# ── HTTP RPC + metrics ───────────────────────────────────────────────────────
_START_TS = time.time()
_last_request = time.time()
_request_count = 0
_draining = False
_inflight = 0
_inflight_lock = threading.Lock()

_METRICS_WINDOW = _CFG["metrics_window"]
_metrics_lock = threading.Lock()
_tool_calls: dict = {}
_tool_errors: dict = {}
_tool_latencies_ms: dict = {}
_error_types: dict = {}

# ── Circuit breaker (per-tool) ───────────────────────────────────────────────
CIRCUIT_FAILURE_THRESHOLD = _CFG["circuit_failure_threshold"]
CIRCUIT_COOLDOWN_S = _CFG["circuit_cooldown_s"]
_circuit_state: dict = {}


def _circuit_record_failure(tool: str):
    """Must be called with _metrics_lock held."""
    st = _circuit_state.setdefault(tool, {"state": "closed", "consecutive_failures": 0, "opened_at": 0.0})
    st["consecutive_failures"] += 1
    if st["state"] != "open" and st["consecutive_failures"] >= CIRCUIT_FAILURE_THRESHOLD:
        st["state"] = "open"
        st["opened_at"] = time.time()
        _log("warn", "circuit_open", tool=tool, consecutive_failures=st["consecutive_failures"],
             cooldown_s=CIRCUIT_COOLDOWN_S)


def _circuit_record_success(tool: str):
    """Must be called with _metrics_lock held."""
    st = _circuit_state.setdefault(tool, {"state": "closed", "consecutive_failures": 0, "opened_at": 0.0})
    was = st["state"]
    st["consecutive_failures"] = 0
    st["state"] = "closed"
    st["opened_at"] = 0.0
    if was != "closed":
        _log("info", "circuit_closed", tool=tool, was=was)


def _circuit_check(tool: str):
    """Returns None if call may proceed, otherwise error string."""
    with _metrics_lock:
        st = _circuit_state.get(tool)
        if not st or st["state"] == "closed":
            return None
        if st["state"] == "open":
            if time.time() - st["opened_at"] >= CIRCUIT_COOLDOWN_S:
                st["state"] = "half_open"
                _log("info", "circuit_half_open", tool=tool)
                return None
            remaining = round(CIRCUIT_COOLDOWN_S - (time.time() - st["opened_at"]), 1)
            return f"circuit open for {tool} (retry in {remaining}s)"
        return None


def _record_call(tool: str, latency_ms: float, error_type):
    with _metrics_lock:
        _tool_calls[tool] = _tool_calls.get(tool, 0) + 1
        samples = _tool_latencies_ms.setdefault(tool, [])
        samples.append(latency_ms)
        if len(samples) > _METRICS_WINDOW:
            del samples[: len(samples) - _METRICS_WINDOW]
        if error_type:
            _tool_errors[tool] = _tool_errors.get(tool, 0) + 1
            _error_types[error_type] = _error_types.get(error_type, 0) + 1
            _circuit_record_failure(tool)
        else:
            _circuit_record_success(tool)


def _percentile(sorted_samples, p):
    if not sorted_samples:
        return 0
    k = max(0, min(len(sorted_samples) - 1, int(round((p / 100.0) * (len(sorted_samples) - 1)))))
    return sorted_samples[k]


def _metrics_snapshot() -> dict:
    with _metrics_lock:
        tools = []
        for name, count in sorted(_tool_calls.items()):
            samples = sorted(_tool_latencies_ms.get(name, []))
            cs = _circuit_state.get(name, {"state": "closed", "consecutive_failures": 0})
            tools.append({
                "tool": name,
                "calls": count,
                "errors": _tool_errors.get(name, 0),
                "p50_ms": round(_percentile(samples, 50), 1),
                "p95_ms": round(_percentile(samples, 95), 1),
                "p99_ms": round(_percentile(samples, 99), 1),
                "circuit": cs["state"],
                "consecutive_failures": cs["consecutive_failures"],
            })
        errors = dict(_error_types)
        circuits_open = sum(1 for st in _circuit_state.values() if st["state"] != "closed")
    return {
        "version": __version__,
        "uptime_s": round(time.time() - _START_TS, 1),
        "requests_total": _request_count,
        "tools_registered": len(TOOLS),
        "circuits_open": circuits_open,
        "draining": _draining,
        "inflight": _inflight,
        "tool_stats": tools,
        "error_types": errors,
    }


def _graceful_exit(reason: str, **fields):
    global _draining
    if _draining:
        return
    _draining = True
    _log("info", "draining", reason=reason, inflight=_inflight, **fields)
    t0 = time.time()
    while time.time() - t0 < DRAIN_TIMEOUT_S:
        if _inflight == 0:
            break
        time.sleep(0.1)
    _log("info", "exiting", reason=reason, waited_s=round(time.time() - t0, 2))
    os._exit(0)


class RPCHandler(BaseHTTPRequestHandler):
    server_version = f"JesterDaemon/{__version__}"
    sys_version = ""

    def log_message(self, *_):
        pass

    def do_GET(self):
        global _last_request, _request_count
        if self.path == "/health":
            self._json(200, {
                "ok": True,
                "version": __version__,
                "uptime_s": round(time.time() - _START_TS, 1),
                "requests": _request_count,
                "tools": len(TOOLS),
            })
            return
        _last_request = time.time()
        _request_count += 1
        if self.path == "/tools":
            self._json(200, {"tools": sorted(TOOLS.keys()), "version": __version__})
        elif self.path == "/metrics":
            self._json(200, _metrics_snapshot())
        elif self.path == "/version":
            self._json(200, {"version": __version__})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        global _last_request, _request_count, _inflight
        if _draining:
            self._json(503, {"error": "daemon draining, retry"})
            return
        _last_request = time.time()
        _request_count += 1
        if not self.path.startswith("/rpc/"):
            self._json(404, {"error": "not found"})
            return
        tool = self.path[len("/rpc/"):]
        fn = TOOLS.get(tool)
        if not fn:
            self._json(404, {"error": f"unknown tool: {tool}"})
            return
        breaker = _circuit_check(tool)
        if breaker:
            self._json(503, {"error": breaker, "type": "CircuitOpen"})
            return
        with _inflight_lock:
            _inflight += 1
        start = time.perf_counter()
        err_type = None
        try:
            length = int(self.headers.get("content-length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            args = json.loads(raw) if raw.strip() else {}
            result = fn(**args)
            self._json(200, {"result": result})
        except TypeError as e:
            err_type = "TypeError"
            self._json(400, {"error": f"bad args: {e}"})
        except Exception as e:
            err_type = type(e).__name__
            self._json(500, {"error": str(e), "type": err_type})
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            _record_call(tool, latency_ms, err_type)
            with _inflight_lock:
                _inflight -= 1

    def _json(self, code, body):
        try:
            data = json.dumps(body, default=str, ensure_ascii=False).encode("utf-8")
        except Exception as e:
            data = json.dumps({"error": f"json encode failed: {e}"}).encode("utf-8")
            code = 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Jester-Daemon-Version", __version__)
        self.end_headers()
        self.wfile.write(data)


def _idle_watcher():
    ram_cap_mb = _CFG["ram_cap_mb"]
    while True:
        try:
            time.sleep(60)
            idle = time.time() - _last_request
            if idle > IDLE_TIMEOUT_SECONDS:
                _graceful_exit("idle_exit", idle_s=int(idle))
            uptime = time.time() - _START_TS
            if uptime > MAX_UPTIME_SECONDS and (time.time() - _last_request) > 30:
                _graceful_exit("max_uptime_recycle", uptime_s=int(uptime))
            # RAM cap check (Windows via psapi)
            try:
                import ctypes
                from ctypes import wintypes
                class _PMC(ctypes.Structure):
                    _fields_ = [("cb", wintypes.DWORD),
                                ("PageFaultCount", wintypes.DWORD),
                                ("PeakWorkingSetSize", ctypes.c_size_t),
                                ("WorkingSetSize", ctypes.c_size_t),
                                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                                ("PagefileUsage", ctypes.c_size_t),
                                ("PeakPagefileUsage", ctypes.c_size_t)]
                pmc = _PMC()
                pmc.cb = ctypes.sizeof(_PMC)
                if ctypes.windll.psapi.GetProcessMemoryInfo(
                    ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb
                ):
                    rss_mb = pmc.WorkingSetSize / (1024 * 1024)
                    if rss_mb > ram_cap_mb and (time.time() - _last_request) > 10:
                        _graceful_exit("ram_cap_recycle", rss_mb=round(rss_mb), cap_mb=ram_cap_mb)
            except Exception:
                pass  # RAM check is opportunistic; never crash the watcher
        except Exception as e:
            _log("error", "idle_watcher_error", err=str(e))


def _heartbeat_watcher():
    import urllib.request
    import urllib.error
    interval = _CFG["heartbeat_interval_s"]
    timeout = _CFG["heartbeat_timeout_s"]
    time.sleep(60)  # startup grace
    while True:
        try:
            time.sleep(interval)
            try:
                with urllib.request.urlopen(
                    f"http://{JESTER_HOST}:{JESTER_PORT}/health", timeout=timeout
                ) as r:
                    if r.status != 200:
                        _graceful_exit("heartbeat_bad_status", status=r.status)
            except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
                _graceful_exit("heartbeat_failed", err_type=type(e).__name__, err=str(e))
        except Exception as e:
            _log("error", "heartbeat_watcher_error", err=str(e))


threading.Thread(target=_idle_watcher, daemon=True).start()
threading.Thread(target=_heartbeat_watcher, daemon=True).start()


class _JesterHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        self.socket = _bound_socket
        self.server_address = self.socket.getsockname()

    def server_activate(self):
        self.socket.listen(64)


_log("info", "listening", host=JESTER_HOST, port=JESTER_PORT,
     version=__version__, tools=len(TOOLS))
try:
    _JesterHTTPServer((JESTER_HOST, JESTER_PORT), RPCHandler).serve_forever()
except KeyboardInterrupt:
    _log("info", "interrupted")
