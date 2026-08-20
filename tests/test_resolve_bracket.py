#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import resolve_bracket as rb  # noqa: E402


def test_liquipedia_2_1_fills_next_round_before_opendota() -> None:
    matches = [
        {
            "id": "ubqf2",
            "teamA": "TEAM VISION",
            "teamB": "BoomBoys",
            "format": "Bo3",
            "status": "live",
            "score": "1-1",
            "mapsPlayed": 2,
            "winnerTo": "ubsf1",
            "loserTo": "lbr1a",
        },
        {
            "id": "ubsf1",
            "teamA": "Team Spirit",
            "teamB": {"from": "ubqf2", "as": "winner"},
            "status": "awaiting",
        },
        {
            "id": "lbr1a",
            "teamA": "Iron Wing",
            "teamB": {"from": "ubqf2", "as": "loser"},
            "status": "awaiting",
        },
    ]
    live = {"matches": {"ubqf2": {"score": "2-1", "matchIds": ["1", "2", "3"]}}}
    # games.json still only has G1+G2 — OpenDota has not parsed Game 3.
    games = [
        {"match_id": 1, "winner": "TEAM VISION", "radiant": "TEAM VISION", "dire": "BoomBoys", "start_time": 1787200000},
        {"match_id": 2, "winner": "BoomBoys", "radiant": "TEAM VISION", "dire": "BoomBoys", "start_time": 1787205000},
    ]
    rb.apply_results(matches, games)
    assert matches[0]["score"] == "1-1"
    rb.apply_live_results(matches, live)
    rb.fill_feeders(matches)
    assert matches[0]["winner"] == "TEAM VISION"
    assert matches[0]["loser"] == "BoomBoys"
    assert matches[0]["status"] == "completed"
    assert matches[1]["teamB"] == "TEAM VISION"
    assert matches[1]["status"] == "scheduled"
    assert matches[2]["teamB"] == "BoomBoys"


def test_live_1_1_does_not_uncomplete_a_finished_series() -> None:
    matches = [
        {
            "id": "ubqf1",
            "teamA": "Iron Wing",
            "teamB": "Team Spirit",
            "format": "Bo3",
            "status": "completed",
            "score": "0-2",
            "mapsPlayed": 2,
            "winner": "Team Spirit",
            "loser": "Iron Wing",
        }
    ]
    live = {"matches": {"ubqf1": {"score": "0-1"}}}
    assert rb.apply_live_results(matches, live) is False
    assert matches[0]["winner"] == "Team Spirit"


if __name__ == "__main__":
    test_liquipedia_2_1_fills_next_round_before_opendota()
    test_live_1_1_does_not_uncomplete_a_finished_series()
    print("test_resolve_bracket ok")
