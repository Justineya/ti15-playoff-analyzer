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
LIVE = ROOT / "web" / "data" / "live.json"
STATE = ROOT / "data" / "briefing-state.json"
API = "https://api.cursor.com/v0/agents"
REPO = os.environ.get("EOD_REPO_URL") or "https://github.com/Justineya/ti15-playoff-analyzer"

sys.path.insert(0, str(ROOT / "scripts"))
import map_trigger  # noqa: E402


def truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def snippet(path: Path, limit: int = 8000) -> str:
    if not path.exists():
        return ""
    return path.read_text()[:limit]


def mark_success() -> None:
    if not STATE.exists():
        return
    state = json.loads(STATE.read_text())
    updated = map_trigger.mark_launched(state)
    STATE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
    trigger = json.loads(LAUNCH.read_text()) if LAUNCH.exists() else {}
    trigger["launch"] = False
    trigger["fresh"] = False
    trigger["reason"] = "launched"
    LAUNCH.write_text(json.dumps(trigger, ensure_ascii=False, indent=2) + "\n")


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
    prompt += "\n\n本次触发：\n```json\n" + json.dumps(trigger, ensure_ascii=False, indent=2)[:4000] + "\n```\n"
    if DAILY.exists():
        prompt += "\n\n当前 web/data/daily.json：\n```json\n" + snippet(DAILY) + "\n```\n"
    if LIVE.exists():
        live = json.loads(LIVE.read_text())
        slim = {
            "asOf": live.get("asOf"),
            "matches": live.get("matches"),
            "games": [
                {
                    "matchId": g.get("matchId"),
                    "gameTime": g.get("gameTime"),
                    "deactivateTime": g.get("deactivateTime"),
                    "radiant": g.get("radiant"),
                    "dire": g.get("dire"),
                    "radiantScore": g.get("radiantScore"),
                    "direScore": g.get("direScore"),
                }
                for g in live.get("games") or []
            ],
        }
        prompt += "\n\n当前 web/data/live.json（精简）：\n```json\n" + json.dumps(slim, ensure_ascii=False)[:8000] + "\n```\n"
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
        return 0
    except Exception as e:  # noqa: BLE001
        print("Cursor launch failed", e, file=sys.stderr)
        return 0
    agent_id = body.get("id") or body.get("agent", {}).get("id")
    url = body.get("target", {}).get("url") or (f"https://cursor.com/agents/{agent_id}" if agent_id else "")
    print("launched Cursor bot", agent_id or body, url)
    mark_success()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
