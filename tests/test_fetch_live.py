#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_live import compact_game, overlay_series, parse_lp_match, pick_game, ti_games  # noqa: E402


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
        "deactivate_time": 0,
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


def test_skips_deactivated_lobby() -> None:
    games = [sample_live(deactivate_time=99, match_id="old"), sample_live(match_id="new")]
    hit = pick_game(games, "Iron Wing", "Team Spirit")
    assert str(hit["match_id"]) == "new"


def test_lp_match_reads_kickoff_and_matchid() -> None:
    body = """
|opponent1={{TeamOpponent|Iron Wing}}
|date=August 20, 2026 - 10:30 {{Abbr/CST}}
|matchid1=8955197224
|map1={{Map
|t1h1=Hoodwink|t1h2=|t1h3=|t1h4=|t1h5=
|t2h1=Drow Ranger|t2h2=|t2h3=|t2h4=|t2h5=
|length=|winner=
}}
"""
    parsed = parse_lp_match(body)
    assert parsed["datetime"] == "2026-08-20 10:30"
    assert parsed["matchIds"] == ["8955197224"]
    assert parsed["maps"][0]["heroes1"] == ["Hoodwink"]
    assert parsed["maps"][0]["heroes2"] == ["Drow Ranger"]
    assert parsed["score"] is None


def test_lp_map1_winner_sets_score() -> None:
    body = """
|opponent1={{TeamOpponent|Iron Wing}}
|date=August 20, 2026 - 10:30 {{Abbr/CST}}
|matchid1=8955197224
|map1={{Map
|t1h1=Hoodwink|t1h2=|t1h3=|t1h4=|t1h5=
|t2h1=Drow Ranger|t2h2=|t2h3=|t2h4=|t2h5=
|length=48:12|winner=2
}}
|map2={{Map
|winner=
}}
"""
    parsed = parse_lp_match(body)
    assert parsed["score"] == "0-1"
    assert parsed["maps"][0]["winner"] == 2
    assert parsed["maps"][1]["winner"] is None


def test_lp_map1_iron_wing_win_is_1_0() -> None:
    body = """
|matchid1=1
|map1={{Map
|length=30:00|winner=1
}}
"""
    assert parse_lp_match(body)["score"] == "1-0"


def test_pick_game_skips_finished_g1_when_g2_is_live() -> None:
    g1 = sample_live(deactivate_time=99, match_id="8955197224")
    g2 = sample_live(
        match_id="8955247801",
        team_id_radiant=10150413,
        team_id_dire=7119388,
        team_name_radiant="Iron Wing",
        team_name_dire="Team Spirit",
        game_time=50,
    )
    hit = pick_game([g1, g2], "Iron Wing", "Team Spirit")
    assert str(hit["match_id"]) == "8955247801"
    assert pick_game([g1], "Iron Wing", "Team Spirit") is None


def test_overlay_series_sets_spirit_g1_win() -> None:
    games = [
        {"matchId": "8955197224", "deactivateTime": 9, "radiant": {"id": 7119388}, "dire": {"id": 10150413}},
        {"matchId": "8955247801", "deactivateTime": 0, "radiant": {"id": 10150413}, "dire": {"id": 7119388}},
    ]
    playoffs = {"matches": [{"id": "ubqf1", "teamA": "Iron Wing", "teamB": "Team Spirit"}]}
    out = overlay_series(games, {}, playoffs, local_winners={"8955197224": "Team Spirit"})
    assert out["ubqf1"]["score"] == "0-1"
    assert out["ubqf1"]["matchIds"] == ["8955197224", "8955247801"]


def test_overlay_keeps_lp_score_without_http() -> None:
    import fetch_live as fl

    orig = fl.get_json

    def boom(url: str):
        raise AssertionError(url)

    fl.get_json = boom
    try:
        games = [
            {"matchId": "8955197224", "deactivateTime": 9, "radiant": {"id": 7119388}, "dire": {"id": 10150413}},
            {"matchId": "8955247801", "deactivateTime": 0, "radiant": {"id": 10150413}, "dire": {"id": 7119388}},
        ]
        playoffs = {"matches": [{"id": "ubqf1", "teamA": "Iron Wing", "teamB": "Team Spirit"}]}
        lp = {"ubqf1": {"score": "0-1", "matchIds": ["8955197224"]}}
        out = overlay_series(games, lp, playoffs, local_winners={})
        assert out["ubqf1"]["score"] == "0-1"
    finally:
        fl.get_json = orig


if __name__ == "__main__":
    test_picks_iw_spirit_by_team_id()
    test_ignores_pubs_and_other_series()
    test_ti_games_keeps_league_and_eight()
    test_skips_deactivated_lobby()
    test_lp_match_reads_kickoff_and_matchid()
    test_lp_map1_winner_sets_score()
    test_lp_map1_iron_wing_win_is_1_0()
    test_pick_game_skips_finished_g1_when_g2_is_live()
    test_overlay_series_sets_spirit_g1_win()
    test_overlay_keeps_lp_score_without_http()
    print("test_fetch_live ok")
