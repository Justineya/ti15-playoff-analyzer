#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ingest_iw_spirit import summarize  # noqa: E402


def test_current_roster_beats_crystallis_filter() -> None:
    blob = json.loads((ROOT / "data" / "iw_spirit_h2h.json").read_text())
    cur = blob["current"]
    assert cur["maps"] == 7
    assert cur["seriesN"] == 5
    assert cur["iwMaps"] == 3
    assert cur["spiritMaps"] == 4
    assert cur["spiritF10"] == 5
    assert cur["iwF10"] == 2
    assert cur["g1SpiritF10"] == 4
    assert cur["g1IwF10"] == 1
    # DL28 G1: Spirit F10, IW won
    dl = next(s for s in cur["series"] if "DreamLeague" in s["event"])
    assert dl["g1F10"] == "Team Spirit" and dl["g1Winner"] == "Iron Wing"
    dropped = blob["droppedTi25"]
    assert dropped["maps"] == 3
    assert all(not m["currentIw"] for m in blob["maps"] if m["event"].startswith("The International 2025"))


def test_summarize_g1() -> None:
    maps = [
        {"series_id": 1, "start_time": 1, "date": "2026-01-01", "event": "X", "winner": "Iron Wing", "f10": "Team Spirit"},
        {"series_id": 1, "start_time": 2, "date": "2026-01-01", "event": "X", "winner": "Iron Wing", "f10": "Iron Wing"},
    ]
    s = summarize(maps)
    assert s["g1SpiritF10"] == 1
    assert s["iwMaps"] == 2


if __name__ == "__main__":
    test_current_roster_beats_crystallis_filter()
    test_summarize_g1()
    print("test_iw_spirit_h2h ok")
