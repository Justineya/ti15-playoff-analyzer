#!/usr/bin/env python3
"""Launch a Cursor cloud agent after a playoff map finishes, if CURSOR_API_KEY is set."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / ".github" / "eod-cursor-prompt.md"
LAUNCH = ROOT / "data" / "cursor-launch.json"
DAILY = ROOT / "web" / "data" / "daily.json"
API = "https://api.cursor.com/v0/agents"
REPO = os.environ.get("EOD_REPO_URL") or "https://github.com/Justineya/ti15-playoff-analyzer"


def truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    key = os.environ.get("CURSOR_API_KEY") or ""
    if not key.strip():
        print("no CURSOR_API_KEY; skip Cursor bot launch")
        return 0
    force = truthy("FORCE_CURSOR")
    trigger = json.loads(LAUNCH.read_text()) if LAUNCH.exists() else {}
    if not force and not trigger.get("launch"):
        print("no new map; skip Cursor bot", trigger.get("reason") or "")
        return 0
    prompt = PROMPT.read_text()
    if DAILY.exists():
        prompt += "\n\n当前 web/data/daily.json：\n```json\n" + DAILY.read_text()[:8000] + "\n```\n"
    payload = {
        "prompt": {"text": prompt},
        "source": {"repository": REPO, "ref": "main"},
        "target": {"autoCreatePr": True},
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    import base64

    token = base64.b64encode(f"{key}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("Cursor launch failed", e.code, e.read().decode()[:800], file=sys.stderr)
        return 1
    agent_id = body.get("id") or body.get("agent", {}).get("id")
    url = body.get("target", {}).get("url") or (f"https://cursor.com/agents/{agent_id}" if agent_id else "")
    print("launched Cursor bot", agent_id or body, url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
