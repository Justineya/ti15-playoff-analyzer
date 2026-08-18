#!/usr/bin/env python3
"""Ingest EWC 2026 maps where a playoff team played (league 19785, patch 7.41d)."""
from __future__ import annotations

import json
from pathlib import Path

from ingest_games import (
    EWC_EIGHT,
    EWC_LEAGUE,
    analyze_game,
    fetch_match,
    list_league_matches,
    load_heroes,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    heroes, npc_by_id = load_heroes()
    metas = list_league_matches(EWC_LEAGUE, set(EWC_EIGHT))
    games = []
    print(f"EWC in-scope rows {len(metas)}")
    for i, meta in enumerate(metas, 1):
        mid = int(meta["match_id"])
        print(f"[{i}/{len(metas)}] {mid}", flush=True)
        match = fetch_match(mid)
        games.append(
            analyze_game(
                meta,
                match,
                heroes,
                npc_by_id,
                team_map=EWC_EIGHT,
                source="ewc",
                patch="7.41d",
            )
        )

    out = {
        "asOf": "2026-08-17",
        "event": "Esports World Cup 2026",
        "leagueId": EWC_LEAGUE,
        "patch": "7.41d",
        "n": len(games),
        "sampleWeightInModel": 0.45,
        "note": "八强在 EWC 打过的全部地图（含对 VG/Aurora 等）。模型里按 45% 权重并进，TI15 7.41e 为 100%。",
        "games": games,
    }
    path = ROOT / "data" / "ewc_games.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote", path, "games", len(games))


if __name__ == "__main__":
    main()
