#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_finished as inf  # noqa: E402
import daily_briefing as db  # noqa: E402


def test_skips_already_parsed_and_keeps_new_id() -> None:
    live = {
        "games": [],
        "matches": {
            "ubqf2": {
                "score": "1-0",
                "matchIds": ["8955304019"],
                "maps": [{"n": 1, "winner": 1}],
            }
        },
    }
    games = {
        "games": [
            {"match_id": 8955197224, "winner": "Team Spirit", "parsed": True, "start_time": 1787180000},
        ]
    }
    launch = {"newMapIds": ["8955304019"]}
    ids = inf.ids_to_ingest(live, launch, games)
    assert ids == [8955304019]
    games["games"].append({"match_id": 8955304019, "winner": "TEAM VISION", "parsed": True, "draft": {}})
    assert inf.ids_to_ingest(live, launch, games) == []


def test_merge_replaces_same_id() -> None:
    games = [{"match_id": 1, "winner": "A", "start_time": 1}, {"match_id": 2, "winner": "B", "start_time": 2}]
    out = inf.merge_game(games, {"match_id": 1, "winner": "C", "start_time": 1})
    assert [g["winner"] for g in out if g["match_id"] == 1] == ["C"]
    assert len(out) == 2


if __name__ == "__main__":
    test_skips_already_parsed_and_keeps_new_id()
    test_merge_replaces_same_id()
    print("test_ingest_finished ok")
