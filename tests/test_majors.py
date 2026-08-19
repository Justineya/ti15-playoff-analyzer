#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from majors import canonical_side, recency_weight  # noqa: E402
from simulate_playoffs import build_team_stats, matchup_probs  # noqa: E402


def test_recency_falls_with_age() -> None:
    ti = recency_weight("2026-08-13")
    ewc = recency_weight("2026-07-19")
    blast = recency_weight("2026-06-07")
    pgl8 = recency_weight("2026-04-26")
    dl28 = recency_weight("2026-03-01")
    assert ti == 1.0
    assert 0.40 <= ewc <= 0.50
    assert blast < ewc
    assert pgl8 < blast
    assert dl28 < pgl8
    assert dl28 >= 0.10


def test_rename_maps_with_tundra_and_pari_rosters() -> None:
    # Pure, bzm, 33, Ari, Whitemon
    iw = {331855530, 93618577, 86698277, 346412363, 136829091}
    assert canonical_side(iw, "Tundra Esports") == "Iron Wing"
    # Satanic, No[o]ne-, Noticed, 9Class, Dukalis
    vis = {1044002267, 106573901, 195108598, 164199202, 73401082}
    assert canonical_side(vis, "PARIVISION") == "TEAM VISION"
    # BetBoom five
    bb = {172099728, 480412663, 165564598, 317880638, 196878136}
    assert canonical_side(bb, "BetBoom Team") == "BoomBoys"
    # empty parse but current org id still needs the TI five
    assert canonical_side(set(), None, 10136357) == "Nigma Galaxy（旧阵容）"
    assert canonical_side(set(), "Tundra Esports", 8291895) == "Iron Wing"


def test_old_nigma_not_mapped() -> None:
    # Davai, OmaR, GH only — SumaiL/lorenof missing
    old = {138880576, 152168157, 101356886}
    assert canonical_side(old, "Nigma Galaxy") == "Nigma Galaxy（旧阵容）"


def test_majors_move_wr_not_f10k() -> None:
    games = [
        {
            "source": "ti15",
            "radiant": "BoomBoys",
            "dire": "Team Spirit",
            "winner": "BoomBoys",
            "sample_weight": 1.0,
            "f10k": {"side": "radiant"},
            "draft": {"radiant": {"picks": [{"hero": "Tusk"}]}, "dire": {"picks": [{"hero": "Io"}]}},
            "sides": {"radiant": {"mid": {"hero": "Tusk"}}, "dire": {"mid": {"hero": "Io"}}},
        },
        {
            "source": "major",
            "radiant": "BoomBoys",
            "dire": "Aurora Gaming",
            "winner": "BoomBoys",
            "sample_weight": 0.21,
        },
        {
            "source": "major",
            "radiant": "Iron Wing",
            "dire": "TEAM VISION",
            "winner": "Iron Wing",
            "sample_weight": 0.16,
        },
    ]
    stats = build_team_stats(games)
    bb = stats["BoomBoys"]
    assert round(bb["games"], 2) == 1.21
    assert round(bb["wins"], 2) == 1.21
    assert bb["games_ti"] == 1.0
    assert bb["games_major"] == 1
    assert bb["f10k_games"] == 1.0
    assert bb["f10k"] == 1.0
    assert "Tusk" in bb["picks"]
    iw = stats["Iron Wing"]
    assert iw["picks"] == {}
    assert iw["f10k_games"] == 0


def test_h2h_includes_weighted_majors() -> None:
    games = [
        {
            "source": "major",
            "radiant": "Iron Wing",
            "dire": "BoomBoys",
            "winner": "BoomBoys",
            "sample_weight": 0.21,
        }
    ]
    stats = build_team_stats(games)
    draft = {
        "firstPick": "Iron Wing",
        "teamA": {"name": "Iron Wing", "picks": []},
        "teamB": {"name": "BoomBoys", "picks": []},
    }
    row = matchup_probs(stats, "Iron Wing", "BoomBoys", draft)
    assert row["h2hGames"] == 0.21


if __name__ == "__main__":
    test_recency_falls_with_age()
    test_rename_maps_with_tundra_and_pari_rosters()
    test_old_nigma_not_mapped()
    test_majors_move_wr_not_f10k()
    test_h2h_includes_weighted_majors()
    print("ok", date.today())
