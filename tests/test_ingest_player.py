#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_player as ip  # noqa: E402
import launch_player_cursor as launch  # noqa: E402


def sample_match(account_id: int = 203557151, win: bool = True, hero_id: int = 90, lane: int = 2) -> dict:
    return {
        "match_id": 8977526658,
        "start_time": 1788266458,
        "duration": 2105,
        "radiant_win": win,
        "version": 22,
        "players": [
            {
                "account_id": account_id,
                "player_slot": 0,
                "hero_id": hero_id,
                "lane_role": lane,
                "party_size": 1,
                "kills": 13,
                "deaths": 7,
                "assists": 21,
                "gold_per_min": 653,
                "xp_per_min": 938,
                "last_hits": 284,
                "lane_efficiency": 0.89,
                "tower_damage": 3464,
                "hero_damage": 35454,
                "teamfight_participation": 0.63,
                "lh_t": [0] * 10 + [59],
                "gold_t": [0] * 10 + [4300],
                "purchase_log": [{"time": 43, "key": "boots"}],
                "benchmarks": {
                    "gold_per_min": {"pct_bracket": 0.83},
                    "tower_damage": {"pct_bracket": 0.98},
                    "deaths_per_min": {"pct_bracket": 0.33},
                    "hero_damage_per_min": {"pct_bracket": 0.93},
                    "last_hits_per_min": {"pct_bracket": 0.79},
                    "xp_per_min": {"pct_bracket": 0.90},
                },
            }
        ],
    }


def test_extract_mid_kotl() -> None:
    names = {90: "Keeper of the Light"}
    row = ip.extract_player(sample_match(), 203557151, names, {90: "keeper_of_the_light"})
    assert row is not None
    assert row["hero"] == "Keeper of the Light"
    assert row["heroFile"] == "keeper_of_the_light"
    assert row["role"] == "pos2"
    assert row["win"] is True
    assert row["gpmBr"] == 0.83
    assert row["lh10"] == 59
    assert row["boots"] == 43


def test_classify_meta_weak_and_did_not_close() -> None:
    weak = ip.classify_game({"win": False, "role": "pos3", "gpmBr": 0.94, "towerBr": 0.82}, {"wr": 0.449})
    assert weak == "meta_weak"
    close = ip.classify_game({"win": False, "role": "pos2", "gpmBr": 0.92, "towerBr": 0.36}, {"wr": 0.50})
    assert close == "did_not_close"
    role = ip.classify_game({"win": False, "role": "pos1", "gpmBr": 0.03, "towerBr": 0.15}, {"wr": 0.508})
    assert role == "wrong_role"


def test_stub_briefing_keeps_short_diagnosis() -> None:
    games = [
        {
            "matchId": 1,
            "hero": "Timbersaw",
            "heroFile": "shredder",
            "heroId": 98,
            "win": False,
            "role": "pos3",
            "partySize": 1,
            "gpmBr": 0.56,
            "towerBr": 0.31,
            "divine": {"wr": 0.449},
        },
        {
            "matchId": 2,
            "hero": "Keeper of the Light",
            "heroFile": "keeper_of_the_light",
            "heroId": 90,
            "win": True,
            "role": "pos2",
            "partySize": 1,
            "gpmBr": 0.89,
            "towerBr": 0.86,
            "divine": {"wr": 0.53},
        },
    ]
    summary = {
        "wins": 1,
        "losses": 1,
        "roles": {"pos2": {"games": 1, "wins": 1}, "pos3": {"games": 1, "wins": 0}},
        "party": {"1": {"games": 2, "wins": 1}},
        "winAvg": {"gpmBr": 0.89, "towerBr": 0.86},
        "lossAvg": {"gpmBr": 0.56, "towerBr": 0.31},
    }
    brief = ip.stub_briefing({}, games, summary, ["1"], [])
    assert brief["narrative"] == ""
    assert brief["sessionMatchIds"] == ["1"]
    assert brief["lede"].startswith("新1把全单排 0-1")
    assert any("Timbersaw" in p for p in brief["points"])
    assert not any("月骑" in p or "主中" in p for p in brief["points"])
    assert brief["focus"][0]["note"] == "版本坑"


def test_ingest_detects_new_ids() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        (tmp / "web" / "data").mkdir(parents=True)
        ip.CONFIG_PATH = tmp / "config.json"
        ip.STATE_PATH = tmp / "seen.json"
        ip.OUT_PATH = tmp / "player.json"
        ip.LAUNCH_PATH = tmp / "launch.json"
        ip.HEROES_PATH = ROOT / "data" / "heroes.json"
        ip.ROOT = tmp
        ip.CONFIG_PATH.write_text(
            '{"accountId": 203557151, "name": "QQT", "lobbyType": 7, "listLimit": 8, "parseLimit": 2, "formDays": 120}\n'
        )
        ip.STATE_PATH.write_text('{"matchIds": []}\n')
        orig_sleep = ip.time.sleep
        ip.time.sleep = lambda *_: None

        def fake_fetch(url: str):
            if url.endswith("/players/203557151"):
                return {"profile": {"personaname": "QQT"}, "rank_tier": 80, "leaderboard_rank": 736}
            if "wl?" in url:
                return {"win": 1555, "lose": 1253}
            if "/matches?" in url:
                return [
                    {
                        "match_id": 8977526658,
                        "player_slot": 0,
                        "radiant_win": True,
                        "hero_id": 90,
                        "start_time": int(datetime.now(timezone.utc).timestamp()) - 86400,
                    },
                    {
                        "match_id": 8000000000,
                        "player_slot": 0,
                        "radiant_win": True,
                        "hero_id": 8,
                        "start_time": 1700000000,
                    },
                ]
            if url.endswith("/heroStats"):
                return [{"id": 90, "localized_name": "Keeper of the Light", "7_pick": 1000, "7_win": 555}]
            if url.endswith("/matches/8977526658"):
                return sample_match()
            raise AssertionError(url)

        try:
            out = ip.ingest(fetch=fake_fetch)
            assert out["newMatchIds"] == ["8977526658"]
            assert 8000000000 not in [g.get("matchId") for g in out["games"]]
            launch_blob = json.loads(ip.LAUNCH_PATH.read_text())
            assert launch_blob["launch"] is True
            assert out["games"][0]["hero"] == "Keeper of the Light"
            brief = json.loads((tmp / "web" / "data" / "player-briefing.json").read_text())
            assert brief["points"]
            assert brief["lede"]
            assert brief["sessionMatchIds"] == ["8977526658"]
            again = ip.ingest(fetch=fake_fetch)
            assert again["newMatchIds"] == []
            assert json.loads(ip.LAUNCH_PATH.read_text())["launch"] is False
        finally:
            ip.time.sleep = orig_sleep


def test_launch_skips_without_new_map(monkey_env=None) -> None:
    import os

    os.environ.pop("CURSOR_API_KEY", None)
    os.environ.pop("FORCE_CURSOR", None)
    assert launch.main() == 0


if __name__ == "__main__":
    test_extract_mid_kotl()
    test_classify_meta_weak_and_did_not_close()
    test_stub_briefing_keeps_short_diagnosis()
    test_ingest_detects_new_ids()
    test_launch_skips_without_new_map()
    print("test_ingest_player ok")
