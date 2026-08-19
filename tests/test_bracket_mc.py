#!/usr/bin/env python3
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from simulate_playoffs import finish_place, one_bracket, play_series  # noqa: E402


def test_bo3_stops_at_two() -> None:
    rng = random.Random(1)
    for _ in range(200):
        a_wins, score = play_series(0.5, "Bo3", rng)
        wa, wb = (int(x) for x in score.split("-"))
        assert max(wa, wb) == 2
        assert wa + wb in {2, 3}
        assert a_wins == (wa > wb)


def test_bo5_stops_at_three() -> None:
    rng = random.Random(2)
    a_wins, score = play_series(1.0, "Bo5", rng)
    assert a_wins and score == "3-0"
    _, score = play_series(0.0, "Bo5", rng)
    assert score == "0-3"


def test_locked_and_feeders() -> None:
    matches = [
        {
            "id": "ubqf1",
            "teamA": "Iron Wing",
            "teamB": "Team Spirit",
            "format": "Bo3",
            "status": "completed",
            "winner": "Iron Wing",
            "loser": "Team Spirit",
            "score": "2-1",
        },
        {
            "id": "ubqf2",
            "teamA": "TEAM VISION",
            "teamB": "BoomBoys",
            "format": "Bo3",
            "status": "scheduled",
        },
        {
            "id": "ubsf1",
            "teamA": {"from": "ubqf1", "as": "winner"},
            "teamB": {"from": "ubqf2", "as": "winner"},
            "format": "Bo3",
            "status": "awaiting",
        },
        {
            "id": "gf",
            "teamA": {"from": "ubsf1", "as": "winner"},
            "teamB": "Team Liquid",
            "format": "Bo5",
            "status": "awaiting",
        },
        {
            "id": "lbf",
            "teamA": "x",
            "teamB": "y",
            "format": "Bo3",
            "status": "scheduled",
        },
        {
            "id": "lbsf",
            "teamA": "x",
            "teamB": "y",
            "format": "Bo3",
            "status": "scheduled",
        },
    ]
    cache = {
        ("TEAM VISION", "BoomBoys"): 1.0,
        ("Iron Wing", "TEAM VISION"): 1.0,
        ("Iron Wing", "Team Liquid"): 1.0,
        ("x", "y"): 1.0,
    }
    state = one_bracket(matches, cache, random.Random(0))
    assert state["ubqf1"]["winner"] == "Iron Wing"
    assert state["ubqf2"]["winner"] == "TEAM VISION"
    assert state["ubsf1"]["winner"] == "Iron Wing"
    assert state["gf"]["winner"] == "Iron Wing"
    assert state["gf"]["score"] == "3-0"
    place = finish_place(state)
    assert place["Iron Wing"] == "1"
    assert place["Team Liquid"] == "2"


def main() -> None:
    test_bo3_stops_at_two()
    test_bo5_stops_at_three()
    test_locked_and_feeders()
    print("test_bracket_mc ok")


if __name__ == "__main__":
    main()
