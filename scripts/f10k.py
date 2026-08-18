#!/usr/bin/env python3
"""First-to-10-kills: which team first reaches 10 hero kills.

Not who claimed global kill #10. Valve/Liquipedia do not store this field.

Usage:
  python3 scripts/f10k.py 8948533452
"""
from __future__ import annotations

import json
import sys
import urllib.request


def fetch_match(match_id: int) -> dict:
    req = urllib.request.Request(
        f"https://api.opendota.com/api/matches/{match_id}",
        headers={"User-Agent": "TI15Analyzer/0.1"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def first_to_ten(match: dict) -> dict:
    events = []
    for player in match.get("players") or []:
        side = "radiant" if player.get("isRadiant") else "dire"
        for kill in player.get("kills_log") or []:
            key = str(kill.get("key") or "")
            if not key.startswith("npc_dota_hero_"):
                continue
            events.append(
                {
                    "time": int(kill["time"]),
                    "side": side,
                    "killer_hero_id": player.get("hero_id"),
                    "killer_slot": player.get("player_slot"),
                    "killer": player.get("name") or player.get("personaname"),
                }
            )
    events.sort(key=lambda e: (e["time"], e["killer_slot"] or 0))
    counts = {"radiant": 0, "dire": 0}
    for event in events:
        counts[event["side"]] += 1
        if counts[event["side"]] == 10:
            team = match.get("radiant_name") if event["side"] == "radiant" else match.get("dire_name")
            return {
                "ok": True,
                "match_id": match.get("match_id"),
                "radiant": match.get("radiant_name"),
                "dire": match.get("dire_name"),
                "f10k_side": event["side"],
                "f10k_team": team,
                "time_s": event["time"],
                "score_when_hit": dict(counts),
                "definition": "哪支队伍先获得10次英雄击杀",
            }
    return {
        "ok": False,
        "reason": "neither_team_reached_10",
        "hero_kills_logged": len(events),
        "parsed": match.get("version") is not None,
        "definition": "哪支队伍先获得10次英雄击杀",
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: f10k.py <match_id>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(first_to_ten(fetch_match(int(sys.argv[1]))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
