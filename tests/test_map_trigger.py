#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import map_trigger as mt  # noqa: E402


def test_g2_lobby_marks_g1_finished() -> None:
    live = {
        "games": [
            {
                "matchId": "8955304019",
                "gameTime": 4524,
                "deactivateTime": 0,
                "radiant": {"id": 8255888},
                "dire": {"id": 9572001},
            },
            {
                "matchId": "8955383956",
                "gameTime": -10,
                "deactivateTime": 0,
                "radiant": {"id": 9572001},
                "dire": {"id": 8255888},
            },
        ],
        "matches": {
            "ubqf2": {
                "matchIds": ["8955304019", "8955383956"],
                "score": "1-0",
                "maps": [{"n": 1, "winner": 1}],
            }
        },
    }
    finished, series = mt.collect_finished(live, {"games": []}, {"matches": []})
    assert "8955304019" in finished
    assert "8955383956" not in finished
    assert series["ubqf2"] == "1-0"


def test_does_not_relaunch_known_ingest_ids() -> None:
    finished = {"8955197224", "8955247801"}
    state = {"mapIds": [8955197224, 8955247801]}
    out = mt.decide(state, finished, {"ubqf1": "0-2"})
    assert out["launch"]["launch"] is False
    assert out["launch"]["newMapIds"] == []


def test_new_g1_id_launches_then_second_map_launches_again() -> None:
    state = {"mapIds": [8955197224, 8955247801], "finishedMatchIds": ["8955197224", "8955247801"]}
    first = mt.decide(state, {"8955197224", "8955247801", "8955304019"}, {"ubqf2": "1-0"})
    assert first["launch"]["launch"] is True
    assert first["launch"]["fresh"] is True
    assert first["launch"]["newMapIds"] == ["8955304019"]
    retry = mt.decide(first["state"], {"8955197224", "8955247801", "8955304019"}, {"ubqf2": "1-0"})
    assert retry["launch"]["launch"] is True
    assert retry["launch"]["fresh"] is False
    launched = mt.mark_launched(first["state"])
    assert launched["pendingLaunch"] == []
    assert "8955304019" in launched["finishedMatchIds"]
    second = mt.decide(launched, {"8955197224", "8955247801", "8955304019", "8955383956"}, {"ubqf2": "1-1"})
    assert second["launch"]["launch"] is True
    assert second["launch"]["newMapIds"] == ["8955383956"]


def test_group_stage_maps_do_not_fire() -> None:
    games = {
        "games": [
            {"match_id": 8942993144, "winner": "Team Spirit", "start_time": 1786000000, "source": "opendota"},
            {"match_id": 8955197224, "winner": "Team Spirit", "start_time": 1787180000, "source": "opendota"},
        ]
    }
    finished, _ = mt.collect_finished({"games": [], "matches": {}}, games, {"matches": []})
    assert "8942993144" not in finished
    assert "8955197224" in finished


def test_lp_score_without_match_id_still_fires() -> None:
    live = {"games": [], "matches": {"ubqf2": {"matchIds": [], "score": "1-0", "maps": [{"n": 1, "winner": 1}]}}}
    finished, series = mt.collect_finished(live, {"games": []}, {"matches": []})
    assert "ubqf2:map1" in finished
    assert series["ubqf2"] == "1-0"
    out = mt.decide({"mapIds": [8955197224]}, finished, series)
    assert out["launch"]["launch"] is True


if __name__ == "__main__":
    test_g2_lobby_marks_g1_finished()
    test_does_not_relaunch_known_ingest_ids()
    test_new_g1_id_launches_then_second_map_launches_again()
    test_lp_score_without_match_id_still_fires()
    test_group_stage_maps_do_not_fire()
    print("test_map_trigger ok")
