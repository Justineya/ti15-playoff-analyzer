#!/usr/bin/env python3
"""Launch a Cursor cloud agent after new ranked games, if CURSOR_API_KEY is set."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / ".github" / "player-cursor-prompt.md"
LAUNCH = ROOT / "data" / "player-launch.json"
PLAYER = ROOT / "web" / "data" / "player.json"
BRIEF = ROOT / "web" / "data" / "player-briefing.json"
API = "https://api.cursor.com/v0/agents"
REPO = os.environ.get("EOD_REPO_URL") or "https://github.com/Justineya/ti15-playoff-analyzer"


def truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def snippet(path: Path, limit: int = 14000) -> str:
    if not path.exists():
        return ""
    return path.read_text()[:limit]


def main() -> int:
    key = os.environ.get("CURSOR_API_KEY") or ""
    if not key.strip():
        print("no CURSOR_API_KEY; skip player Cursor launch")
        return 0
    force = truthy("FORCE_CURSOR")
    trigger = json.loads(LAUNCH.read_text()) if LAUNCH.exists() else {}
    if not force and not trigger.get("launch"):
        print("no new ranked map; skip player Cursor bot", trigger.get("reason") or "")
        return 0
    prompt = PROMPT.read_text()
    prompt += "\n\n本次触发：\n```json\n" + json.dumps(trigger, ensure_ascii=False, indent=2)[:4000] + "\n```\n"
    if PLAYER.exists():
        prompt += "\n\n当前 web/data/player.json：\n```json\n" + snippet(PLAYER) + "\n```\n"
    if BRIEF.exists():
        prompt += "\n\n当前 web/data/player-briefing.json（可改写）：\n```json\n" + snippet(BRIEF, 6000) + "\n```\n"
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
    token = base64.b64encode(f"{key}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("player Cursor launch failed", e.code, e.read().decode()[:800], file=sys.stderr)
        return 0
    except Exception as e:  # noqa: BLE001
        print("player Cursor launch failed", e, file=sys.stderr)
        return 0
    agent_id = body.get("id") or body.get("agent", {}).get("id")
    url = body.get("target", {}).get("url") or (f"https://cursor.com/agents/{agent_id}" if agent_id else "")
    print("launched player Cursor bot", agent_id or body, url)
    if LAUNCH.exists():
        trigger["launch"] = False
        trigger["fresh"] = False
        trigger["reason"] = "launched"
        LAUNCH.write_text(json.dumps(trigger, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
