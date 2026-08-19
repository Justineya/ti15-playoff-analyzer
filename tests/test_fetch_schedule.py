#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_schedule import (  # noqa: E402
    LP_TO_OURS,
    apply_schedule,
    parse_bracket,
    parse_kickoff,
    rebuild_days,
)

FIXTURE = (ROOT / "tests" / "fixtures" / "ti2026_main_event.wikitext").read_text()


def test_parse_all_fourteen_slots() -> None:
    parsed = parse_bracket(FIXTURE)
    assert set(parsed) == set(LP_TO_OURS.values())
    assert parsed["ubqf1"]["datetime"] == "2026-08-20 10:00"
    assert parsed["lbr1a"]["datetime"] == "2026-08-21 10:00"
    assert parsed["ubsf1"]["datetime"] == "2026-08-21 16:00"
    # Liquipedia puts R2M4 (lbqf2) at 10:00 and R2M3 (lbqf1) at 13:00.
    assert parsed["lbqf2"]["datetime"] == "2026-08-22 10:00"
    assert parsed["lbqf1"]["datetime"] == "2026-08-22 13:00"
    assert parsed["ubf"]["datetime"] == "2026-08-22 16:00"
    assert parsed["lbf"]["datetime"] == "2026-08-23 10:00"
    assert parsed["gf"]["datetime"] == "2026-08-23 13:00"
    assert parsed["gf"]["format"] == "Bo5"
    assert parsed["ubqf1"]["format"] == "Bo3"


def test_timezone_to_beijing() -> None:
    utc = parse_kickoff("|date=August 20, 2026 - 02:00 {{Abbr/UTC}}")
    assert utc is not None
    assert utc.strftime("%Y-%m-%d %H:%M") == "2026-08-20 10:00"
    iso = parse_kickoff("|date=2026-08-21 - 11:30 CST")
    assert iso is not None
    assert iso.strftime("%Y-%m-%d %H:%M") == "2026-08-21 11:30"


def test_apply_swaps_day3_order_and_keeps_teams() -> None:
    playoffs = json.loads((ROOT / "data" / "playoffs.json").read_text())
    iw = next(m for m in playoffs["matches"] if m["id"] == "ubqf1")
    assert iw["teamA"] == "Iron Wing"
    parsed = parse_bracket(FIXTURE)
    apply_schedule(playoffs, parsed, "2026-08-19 09:00 CST")
    by_id = {m["id"]: m for m in playoffs["matches"]}
    assert by_id["ubqf1"]["teamA"] == "Iron Wing"
    assert by_id["lbqf1"]["datetime"] == "2026-08-22 13:00"
    assert by_id["lbqf2"]["datetime"] == "2026-08-22 10:00"
    day3 = next(d for d in playoffs["days"] if d["date"] == "2026-08-22")
    assert day3["slots"][0] == "lbqf2"
    assert day3["slots"][1] == "lbqf1"
    assert playoffs["scheduleSource"].endswith("Main_Event")


def test_moved_match_rebuilds_days() -> None:
    matches = [
        {"id": "ubqf1", "round": "胜者组首轮", "datetime": "2026-08-20 10:00", "day": "2026-08-20"},
        {"id": "gf", "round": "总决赛", "datetime": "2026-08-24 12:00", "day": "2026-08-24"},
    ]
    days = rebuild_days(matches, [{"date": "2026-08-20", "label": "第1天 · 胜者组首轮"}])
    assert [d["date"] for d in days] == ["2026-08-20", "2026-08-24"]
    assert days[1]["slots"] == ["gf"]


def test_thin_parse_does_not_invent_times() -> None:
    parsed = parse_bracket("{{Bracket|id=x}}")
    assert parsed == {}
    playoffs = {"matches": [{"id": "ubqf1", "datetime": "2026-08-20 10:00", "day": "2026-08-20"}]}
    original = deepcopy(playoffs)
    apply_schedule(playoffs, parsed, "now")
    assert playoffs["matches"][0]["datetime"] == original["matches"][0]["datetime"]


def main() -> None:
    test_parse_all_fourteen_slots()
    test_timezone_to_beijing()
    test_apply_swaps_day3_order_and_keeps_teams()
    test_moved_match_rebuilds_days()
    test_thin_parse_does_not_invent_times()
    print("test_fetch_schedule ok")


if __name__ == "__main__":
    main()
