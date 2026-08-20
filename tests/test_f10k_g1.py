#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from f10k_g1 import build_report, mark_game_index  # noqa: E402


def test_g1_is_earliest_in_series() -> None:
    games = [
        {"match_id": 2, "series_id": 1, "start_time": 20, "radiant": "A", "dire": "B", "winner": "A", "f10k": {"side": "radiant", "time": 600}},
        {"match_id": 1, "series_id": 1, "start_time": 10, "radiant": "A", "dire": "B", "winner": "B", "f10k": {"side": "dire", "time": 700}},
        {"match_id": 3, "series_id": 2, "start_time": 30, "radiant": "A", "dire": "C", "winner": "A", "f10k": {"side": "radiant", "time": 800}},
    ]
    mark_game_index(games)
    by_id = {g["match_id"]: g["_g"] for g in games}
    assert by_id == {1: 1, 2: 2, 3: 1}


def test_report_has_eight_and_g1_convert_in_range() -> None:
    report = build_report()
    assert "Iron Wing" in report["teams"]
    assert "Team Spirit" in report["teams"]
    g1 = report["overall"]["g1"]
    assert g1["n"] >= 20
    assert 0.55 <= g1["rate"] <= 0.85
    iw = report["teams"]["Iron Wing"]["g1"]
    assert iw["n"] >= 5
    assert iw["rate"] is not None


if __name__ == "__main__":
    test_g1_is_earliest_in_series()
    test_report_has_eight_and_g1_convert_in_range()
    print("test_f10k_g1 ok")
