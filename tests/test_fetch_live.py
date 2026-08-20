#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_live import compact_game, pick_game, ti_games  # noqa: E402


def sample_live(**over):
    game = {
        "match_id": "8955188505",
        "league_id": 19719,
        "series_id": 1132142,
        "game_time": -14,
        "delay": 60,
        "spectators": 0,
        "radiant_score": 0,
        "dire_score": 0,
        "radiant_lead": 0,
        "team_id_radiant": 7119388,
        "team_id_dire": 10150413,
        "team_name_radiant": "Team Spirit",
        "team_name_dire": "Iron Wing",
        "players": [
            {"account_id": 1, "hero_id": 0, "team": 0, "team_slot": 1, "name": "Yatoro"},
            {"account_id": 2, "hero_id": 0, "team": 1, "team_slot": 1, "name": "Pure"},
        ],
    }
    game.update(over)
    return game


def test_picks_iw_spirit_by_team_id() -> None:
    games = [sample_live(), {"league_id": 0, "team_id_radiant": 1, "team_id_dire": 2}]
    hit = pick_game(games, "Iron Wing", "Team Spirit")
    assert hit is not None
    assert str(hit["match_id"]) == "8955188505"
    hit = pick_game(games, "Team Spirit", "Iron Wing")
    assert hit is not None


def test_ignores_pubs_and_other_series() -> None:
    games = [
        sample_live(team_id_radiant=2163, team_id_dire=9247354, match_id="9"),  # Liquid vs Falcons
        sample_live(),
    ]
    hit = pick_game(games, "Iron Wing", "Team Spirit")
    assert str(hit["match_id"]) == "8955188505"
    assert pick_game(games, "TEAM VISION", "BoomBoys") is None


def test_ti_games_keeps_league_and_eight() -> None:
    raw = [
        sample_live(),
        {"league_id": 0, "team_id_radiant": 0, "team_id_dire": 0, "match_id": "pub", "players": []},
    ]
    out = ti_games(raw)
    assert len(out) == 1
    assert out[0]["radiant"]["name"] == "Team Spirit"
    assert out[0]["dire"]["name"] == "Iron Wing"
    assert compact_game(sample_live())["players"][0]["name"] == "Yatoro"


if __name__ == "__main__":
    test_picks_iw_spirit_by_team_id()
    test_ignores_pubs_and_other_series()
    test_ti_games_keeps_league_and_eight()
    print("test_fetch_live ok")
