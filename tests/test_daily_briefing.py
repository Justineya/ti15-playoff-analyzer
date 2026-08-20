#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_briefing as db  # noqa: E402


def test_live_1_0_switches_briefing_to_game_2() -> None:
    match = {
        "id": "ubqf2",
        "teamA": "TEAM VISION",
        "teamB": "BoomBoys",
        "status": "scheduled",
        "score": None,
        "format": "Bo3",
    }
    live = {
        "matches": {
            "ubqf2": {
                "score": "1-0",
                "matchIds": ["8955304019", "8955383956"],
                "maps": [{"n": 1, "winner": 1}],
            }
        }
    }
    out = db.apply_live_overlay(match, live)
    assert out["score"] == "1-0"
    assert out["status"] == "live"
    assert out["mapsPlayed"] == 1
    assert db.winner_of_played_map(out, 1) == "TEAM VISION"
    headline, _ = db.compose(
        "next-map",
        {"game": 1, "winner": "TEAM VISION", "f10": None},
        {
            "game": 2,
            "lean": {"tag": "VSN", "p": 0.7, "breakEven": 1.43, "why": ""},
            "f10": {"tag": "VSN"},
        },
        {"tag": "VSN", "p": 0.79},
        None,
        None,
    )
    assert "第1局" in headline
    assert "第2局" in headline


if __name__ == "__main__":
    test_live_1_0_switches_briefing_to_game_2()
    print("test_daily_briefing ok")
