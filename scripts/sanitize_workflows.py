#!/usr/bin/env python3
"""
Prepare exported n8n workflows for a public repo.

Reads the raw export folder, keeps only the Nova Bank workflows, removes
test data and instance details, hides the ntfy topic and tunnel addresses,
and writes clean files to ./workflows/.

Usage:
  python3 scripts/sanitize_workflows.py exports-raw
"""
import json
import re
import sys
from pathlib import Path

KEEP_PREFIXES = ("Tool - ", "Vapi tools router", "Test agent (chat)", "KB - Load policies")
REPLACEMENTS = [
    (re.compile(r"https://ntfy\.sh/[A-Za-z0-9_\-]+"), "https://ntfy.sh/YOUR-NTFY-TOPIC"),
    (re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com"), "https://YOUR-TUNNEL.trycloudflare.com"),
]
DROP_KEYS = ("pinData", "staticData", "meta", "shared", "activeVersion", "versionId")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main(src):
    src = Path(src)
    out = Path(__file__).resolve().parent.parent / "workflows"
    out.mkdir(exist_ok=True)
    kept = 0
    for f in sorted(src.glob("*.json")):
        data = json.loads(f.read_text())
        items = data if isinstance(data, list) else [data]
        for wf in items:
            name = wf.get("name", "")
            if not name.startswith(KEEP_PREFIXES):
                continue
            for key in DROP_KEYS:
                wf.pop(key, None)
            text = json.dumps(wf, indent=2)
            for pattern, replacement in REPLACEMENTS:
                text = pattern.sub(replacement, text)
            (out / f"{slug(name)}.json").write_text(text + "\n")
            print(f"kept: {name}")
            kept += 1
    # Final safety scan of everything written
    warnings = 0
    for f in out.glob("*.json"):
        text = f.read_text()
        for word in ("x-vapi-secret\": \"", "bankpass", "apiKey", "password\": \""):
            if word in text:
                print(f"WARNING: check {f.name} for '{word}'")
                warnings += 1
    print(f"\n{kept} workflows written to {out}")
    print("No warnings." if not warnings else f"{warnings} warning(s): review before committing.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
