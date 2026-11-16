#!/usr/bin/env python3
"""
JesterDNA release script: one-command version bump + repackage + Polar update prep.

Usage:  python release.py 1.1.0          # explicit version
        python release.py --bump patch    # 1.0.0 -> 1.0.1
        python release.py --bump minor    # 1.0.0 -> 1.1.0
        python release.py --bump major    # 1.0.0 -> 2.0.0

Steps:
  1. Bump version in mcpize.yaml
  2. Run package_for_delivery.py → produces _releases/jester-mcp-v<ver>.zip
  3. Copy zip to vibedna-site/public/jester-mcp-v<ver>.zip
  4. Update thank-you page link to new version
  5. Print follow-ups (mcpize redeploy, Polar product description bump, Resend campaign command)

This does NOT auto-deploy. Run `mcpize deploy` and `vercel --prod` manually after reviewing.
"""
import os, re, sys, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_PUBLIC = (HERE.parent.parent.parent / "vibedna-site" / "public").resolve()
THANK_YOU = (HERE.parent.parent.parent / "vibedna-site" / "app" / "thank-you" / "jester" / "page.tsx").resolve()
WEBHOOK = (HERE.parent.parent.parent / "vibedna-site" / "app" / "api" / "polar" / "webhook" / "route.ts").resolve()

def read_version() -> str:
    yaml = (HERE / "mcpize.yaml").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*['\"]?([^'\"\s]+)", yaml, re.M)
    return m.group(1) if m else "1"

def write_version(new: str) -> None:
    p = HERE / "mcpize.yaml"
    txt = p.read_text(encoding="utf-8")
    txt = re.sub(r"^version:\s*.*$", f"version: {new}", txt, count=1, flags=re.M)
    p.write_text(txt, encoding="utf-8")

def bump(ver: str, kind: str) -> str:
    parts = ver.replace("v", "").split(".")
    while len(parts) < 3: parts.append("0")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if kind == "patch": patch += 1
    elif kind == "minor": minor, patch = minor + 1, 0
    elif kind == "major": major, minor, patch = major + 1, 0, 0
    else: raise SystemExit(f"unknown bump kind: {kind}")
    return f"{major}.{minor}.{patch}"

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    current = read_version()
    if sys.argv[1] == "--bump":
        if len(sys.argv) < 3: raise SystemExit("--bump needs patch|minor|major")
        new_ver = bump(current, sys.argv[2])
    else:
        new_ver = sys.argv[1]
    print(f"Bumping {current} -> {new_ver}")
    write_version(new_ver)

    # Repackage
    r = subprocess.run([sys.executable, str(HERE / "package_for_delivery.py"), new_ver], capture_output=True, text=True)
    print(r.stdout); print(r.stderr, file=sys.stderr)
    if r.returncode != 0: raise SystemExit("package_for_delivery failed")

    # Copy zip
    src = HERE.parent / "_releases" / f"jester-mcp-v{new_ver}.zip"
    if not src.exists(): raise SystemExit(f"missing {src}")
    if not SITE_PUBLIC.exists():
        print(f"WARN: site public dir not found at {SITE_PUBLIC}, skipping site copy");
    else:
        dst = SITE_PUBLIC / f"jester-mcp-v{new_ver}.zip"
        shutil.copy2(src, dst)
        print(f"copied -> {dst}")
        # Also overwrite the canonical "latest" link
        latest = SITE_PUBLIC / "jester-mcp-v1.zip"
        if latest != dst:
            shutil.copy2(src, latest)
            print(f"copied -> {latest}  (canonical /jester-mcp-v1.zip alias)")

    # Patch thank-you page version label (find existing v1 reference)
    if THANK_YOU.exists():
        txt = THANK_YOU.read_text(encoding="utf-8")
        new_txt = re.sub(r"jester-mcp-v[\d.]+\.zip", f"jester-mcp-v{new_ver}.zip", txt)
        if new_txt != txt:
            THANK_YOU.write_text(new_txt, encoding="utf-8")
            print(f"updated thank-you page download link to v{new_ver}")

    print("\n=== NEXT STEPS (manual) ===")
    print("1. Review the diff:  git diff")
    print("2. Push code:        cd ../../.. && git add -A && git commit -m 'jesterDNA v" + new_ver + "'")
    print("3. Redeploy mcpize:  npx mcpize deploy -y --notes 'v" + new_ver + "'")
    print("4. Redeploy Vercel:  cd ../../../vibedna-site && npx vercel --prod --yes")
    print("5. Resend campaign:  see scripts/announce-release.ts (TODO)")

if __name__ == "__main__":
    main()
