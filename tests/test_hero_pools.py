#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hero_pools import build_report, team_pool  # noqa: E402


def _fake_game(radiant, dire, winner, rad_picks, dire_picks, rad_bans=None, dire_bans=None, source="ti15"):
    def draft(picks, bans):
        return {
            "picks": [{"hero": h, "hero_id": i, "order": i} for i, h in enumerate(picks, 1)],
            "bans": [{"hero": h} for h in (bans or [])],
        }

    return {
        "source": source,
        "radiant": radiant,
        "dire": dire,
        "winner": winner,
        "draft": {"radiant": draft(rad_picks, rad_bans), "dire": draft(dire_picks, dire_bans)},
        "sides": {
            "radiant": {"mid": {"player": "bzm", "hero": rad_picks[0]}, "pos4": {"player": "Ari", "hero": rad_picks[1]}, "pos5": {"player": "Whitemon", "hero": rad_picks[2]}},
            "dire": {"mid": {"player": "Larl", "hero": dire_picks[0]}, "pos4": {"player": "rue", "hero": dire_picks[1]}, "pos5": {"player": "not me", "hero": dire_picks[2]}},
        },
    }


def test_counts_picks_and_wins() -> None:
    games = [
        _fake_game("Iron Wing", "Team Spirit", "Iron Wing", ["Hoodwink", "Earth Spirit", "Kez"], ["Drow Ranger", "Rubick", "Clockwerk"]),
        _fake_game("Iron Wing", "Team Spirit", "Team Spirit", ["Hoodwink", "Ringmaster", "Tusk"], ["Drow Ranger", "Underlord", "Rubick"]),
        _fake_game("Iron Wing", "Nigma Galaxy", "Iron Wing", ["Earth Spirit", "Hoodwink", "Io"], ["Lina", "Tiny", "Bane"]),
    ]
    iw = team_pool(games, "Iron Wing")
    assert iw["maps"] == 3 and iw["wins"] == 2
    assert iw["picks"][0]["hero"] == "Hoodwink" and iw["picks"][0]["n"] == 3
    assert iw["picks"][0]["wins"] == 2
    assert iw["firstPicks"][0]["hero"] == "Hoodwink"
    assert iw["roles"]["mid"]["heroes"][0]["hero"] in {"Hoodwink", "Earth Spirit"}


def test_skips_ewc_and_covers_eight() -> None:
    report = build_report()
    assert report["teams"].keys() == {
        "TEAM VISION",
        "Team Liquid",
        "Nigma Galaxy",
        "Team Spirit",
        "Iron Wing",
        "Team Falcons",
        "BoomBoys",
        "Team Yandex",
    }
    iw = report["teams"]["Iron Wing"]
    sp = report["teams"]["Team Spirit"]
    assert iw["maps"] >= 10
    assert iw["picks"][0]["hero"] == "Hoodwink"
    assert any(r["hero"] == "Drow Ranger" for r in sp["picks"][:5])
    assert "EWC" not in report["sample"]
    assert iw["pickIndex"]["Hoodwink"]["n"] == iw["picks"][0]["n"]


if __name__ == "__main__":
    test_counts_picks_and_wins()
    test_skips_ewc_and_covers_eight()
    print("test_hero_pools ok")
