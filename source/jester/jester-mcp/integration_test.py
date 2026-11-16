"""
Jester daemon integration test.

Verifies:
  1. Daemon spawn (from a fresh state)
  2. All endpoints respond (/health, /tools, /metrics, /version)
  3. Real RPC call works (jester_status)
  4. Concurrent load handles cleanly (10 threads × 20 calls)
  5. Circuit breaker opens after threshold failures (bad-args calls)
  6. Daemon stays alive throughout

Run:
  python integration_test.py
"""
import urllib.request
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOST = "127.0.0.1"
PORT = 7843
BASE = f"http://{HOST}:{PORT}"


def kill_daemon():
    """Best-effort: kill any running jester-daemon."""
    try:
        subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command',
             """Get-CimInstance Win32_Process -Filter "Name='python.exe'" """
             """| Where-Object { $_.CommandLine -like '*jester-daemon*' } """
             """| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"""],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


def spawn_daemon():
    daemon = str(Path(__file__).parent / "jester-daemon.py")
    subprocess.Popen(
        [sys.executable, daemon],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32" else 0,
        close_fds=True,
    )
    for _ in range(300):  # up to 30s for cold-start jester library import
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def get_json(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())


def post_rpc(tool, args=None, expect_code=200):
    """Call tool, return (status, body)."""
    body = json.dumps(args or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/rpc/{tool}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def assert_eq(name, actual, expected):
    if actual == expected:
        print(f"  PASS  {name}: {actual}")
    else:
        print(f"  FAIL  {name}: got {actual}, expected {expected}")
        sys.exit(1)


def assert_true(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}{(': ' + detail) if detail else ''}")
    else:
        print(f"  FAIL  {name}{(': ' + detail) if detail else ''}")
        sys.exit(1)


def main():
    print("=== Jester Daemon Integration Test ===\n")

    print("[1] Kill any existing daemon + spawn fresh...")
    kill_daemon()
    time.sleep(1)
    t0 = time.time()
    ok = spawn_daemon()
    assert_true("daemon spawned within 30s", ok, f"took {time.time()-t0:.1f}s")

    print("\n[2] All endpoints respond...")
    h = get_json("/health")
    assert_eq("/health ok", h["ok"], True)
    assert_true("/health has version", "version" in h)

    v = get_json("/version")
    assert_true("/version returns version", "version" in v)

    t = get_json("/tools")
    assert_true("/tools returns >50 tools", len(t["tools"]) >= 50, f"got {len(t['tools'])}")

    m = get_json("/metrics")
    assert_true("/metrics has tool_stats", "tool_stats" in m)
    assert_true("/metrics has circuits_open", "circuits_open" in m)

    print("\n[3] Real tool call (jester_status)...")
    code, body = post_rpc("jester_status")
    assert_eq("status code", code, 200)
    assert_true("result is non-empty string", isinstance(body.get("result"), str) and len(body["result"]) > 50)

    print("\n[4] Concurrent load (10 threads x 20 calls)...")
    def call_once(i):
        try:
            code, _ = post_rpc("jester_status")
            return code == 200
        except Exception:
            return False
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(call_once, range(200)))
    elapsed = time.time() - t_start
    successes = sum(results)
    assert_eq("success rate (200 calls)", successes, 200)
    print(f"  INFO  throughput: {200/elapsed:.0f} req/s over {elapsed:.2f}s")

    print("\n[5] Circuit breaker opens on bad args...")
    bad_tool = "jester_status"  # we'll send a kwarg it doesn't accept
    # Reset state by calling /metrics to see current circuit state
    m_before = get_json("/metrics")
    # Find a tool that takes args: pick one likely to TypeError on garbage
    # Use jester_recall which requires `name` arg; send wrong kwarg
    for i in range(6):
        post_rpc("jester_recall", {"bogus_arg": "xyz"})
    code, body = post_rpc("jester_recall", {"bogus_arg": "xyz"})
    assert_eq("circuit-open returns 503", code, 503)
    assert_true("error mentions circuit", "circuit" in body.get("error", "").lower())

    print("\n[6] Daemon still alive...")
    h = get_json("/health")
    assert_eq("still healthy", h["ok"], True)
    m_after = get_json("/metrics")
    assert_true("metrics show jester_status calls",
                any(t["tool"] == "jester_status" and t["calls"] >= 200 for t in m_after["tool_stats"]))

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
