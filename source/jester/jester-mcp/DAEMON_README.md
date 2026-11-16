# Jester Daemon

Single persistent HTTP server for all 62 Jester MCP tools. Replaces the per-tab stdio model so N Claude Code tabs share ONE engine instead of each loading the full Jester library.

---

## Why this exists

Without the daemon, each Claude Code tab that loaded jester-mcp spawned its own Python process importing the full jester library (~600 MB per tab). 5 tabs = 3 GB just for jester.

With the daemon: one persistent process holds the library. Each tab runs a thin stdio MCP client that proxies tool calls via HTTP to the daemon. 5 tabs ≈ 500 MB total instead of 3 GB.

**Does NOT affect:**
- `JESTER/api_server.py` (port 7842): the website's live search engine. Untouched.
- `mcpize.yaml`: same product, same tools, same buyer experience.
- The 62 MCP tool signatures Claude sees.

---

## Architecture

```
N Claude tabs                One persistent daemon (port 7843)
┌─────────────┐              ┌──────────────────────────────────┐
│ jester-mcp/ │              │ jester-daemon.py                 │
│ server.py   │  HTTP POST → │  ├─ all 62 tool implementations  │
│ (proxy)     │  /rpc/<tool> │  ├─ full jester library load     │
│ ~100 MB     │              │  ├─ shared graph.db / caches     │
└─────────────┘              │  └─ /health /metrics /tools      │
                             └──────────────────────────────────┘
```

The daemon is lazy-spawned by `server.py` on first tool call. Port-bind singleton: only one can run.

---

## Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness probe. Does not count toward request stats. |
| `/version` | GET | `{"version": "1.0.3"}` |
| `/tools` | GET | Sorted list of tool names |
| `/metrics` | GET | Per-tool latency p50/p95/p99, error counts, circuit state |
| `/rpc/<tool>` | POST | Invoke a tool. JSON body = kwargs. |

All responses include `X-Jester-Daemon-Version`.

POST response codes:
- `200`: success, `{"result": <tool return>}`
- `400`: bad args (TypeError)
- `404`: unknown tool / unknown path
- `500`: tool raised, `{"error": ..., "type": ...}`
- `503`: daemon draining OR circuit open for this tool

---

## Self-protection

| Watcher | Trigger | Effect |
|---|---|---|
| Port-bind singleton | Two daemons race on startup | One wins; other exits cleanly |
| Heartbeat | Self-RPC to /health every 30s, 10s timeout | Catches hangs → graceful_exit |
| RAM cap | RSS > 800 MB | Recycle to dodge leaks |
| Idle timeout | 30 min no requests | Free RAM when no one's using |
| Max uptime | 1 hour running | Periodic clean recycle |
| Circuit breaker | 5 consecutive failures per tool | 60s open → half-open probe |

All exits go through `_graceful_exit()` which drains in-flight requests (up to 5s).

---

## Configuration

Defaults are fine for most. To tune, copy `config.example.toml` to `~/.jester/config.toml`:

```toml
[daemon]
port = 7843
ram_cap_mb = 800
circuit_failure_threshold = 5
# ... see config.example.toml for the full list
```

- Every key optional.
- Unknown keys ignored (forward-compatible).
- Bad TOML falls back to defaults with one stderr warning.
- BOM-prefixed UTF-8 files handled transparently.

---

## Operations

**Logs (structured JSONL):**
```
~/.jester/daemon.jsonl
```
Rotated once at 5 MB → `.jsonl.1`, then overwrites. Human-readable stderr too.

**Force restart:**
```powershell
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*jester-daemon*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```
Next client call spawns a fresh daemon.

**Health check:**
```powershell
Invoke-WebRequest http://127.0.0.1:7843/health
```

**Integration test:**
```powershell
python integration_test.py
```

---

## Files

| File | Role |
|---|---|
| `jester-daemon.py` | The HTTP daemon |
| `server.py` | Stdio MCP client (proxies to daemon when imported by Claude Code) |
| `config.example.toml` | Documented config template |
| `integration_test.py` | End-to-end stress test |
| `mcpize.yaml` | Product manifest (untouched by daemon migration) |

---

## License

See parent project. Same VibeDNA Personal License terms as the rest of the jester MCP.
