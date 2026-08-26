#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
global.window = global;
global.document = { getElementById: () => null, addEventListener: () => {} };
const fs = require("fs");
eval(fs.readFileSync("web/analysis.js", "utf8"));
const F = window.TI15_MATCH;
const matches = [
  { id: "ubqf1", datetime: "2026-08-20 10:30", status: "completed", teamA: "Iron Wing", teamB: "Team Spirit", score: "0-2", format: "Bo3" },
  { id: "ubqf2", datetime: "2026-08-20 13:45", status: "live", teamA: "TEAM VISION", teamB: "BoomBoys", score: "1-1", mapsPlayed: 2, format: "Bo3" },
  { id: "ubqf3", datetime: "2026-08-20 16:00", status: "scheduled", teamA: "Team Liquid", teamB: "Team Yandex", format: "Bo3" },
  { id: "ubqf4", datetime: "2026-08-20 19:00", status: "scheduled", teamA: "Nigma Galaxy", teamB: "Team Falcons", format: "Bo3" },
];
const now = Date.UTC(2026, 7, 20, 9, 11); // 17:11 CST
const hit = F.focusMatch(matches, "", now);
if (!hit || hit.id !== "ubqf2") {
  console.error("expected ubqf2 still on screen at 17:11, got", hit && hit.id);
  process.exit(1);
}
const after = F.focusMatch(
  matches.map((m) => (m.id === "ubqf2" ? { ...m, status: "completed", score: "2-1" } : m)),
  "",
  now
);
if (!after || after.id !== "ubqf3") {
  console.error("expected ubqf3 after VSN series done, got", after && after.id);
  process.exit(2);
}
const gf = [
  { id: "lbf", datetime: "2026-08-23 10:00", status: "completed", teamA: "A", teamB: "B", score: "1-2", format: "Bo3" },
  { id: "gf", datetime: "2026-08-23 13:00", status: "live", teamA: "C", teamB: "D", score: "2-2", mapsPlayed: 4, format: "Bo5" },
];
const late = Date.UTC(2026, 7, 23, 12, 10); // 20:10 CST, 7h after GF kickoff
const gfHit = F.focusMatch(gf, "", late);
if (!gfHit || gfHit.id !== "gf") {
  console.error("expected gf still on screen 7h in, got", gfHit && gfHit.id);
  process.exit(3);
}
const over = [
  { id: "ubqf1", datetime: "2026-08-20 10:30", status: "completed", teamA: "Iron Wing", teamB: "Team Spirit", score: "0-2", format: "Bo3" },
  { id: "gf", datetime: "2026-08-23 13:00", status: "completed", teamA: "TEAM VISION", teamB: "Team Spirit", score: "2-3", format: "Bo5" },
];
const afterEvent = Date.UTC(2026, 7, 26, 3, 0);
const overHit = F.focusMatch(over, "", afterEvent);
if (!overHit || overHit.id !== "gf") {
  console.error("expected gf after the event, got", overHit && overHit.id);
  process.exit(4);
}
"""


def test_homepage_stays_on_live_bo3_past_three_hours() -> None:
    proc = subprocess.run(["node", "-e", SCRIPT], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout or f"exit {proc.returncode}")


if __name__ == "__main__":
    test_homepage_stays_on_live_bo3_past_three_hours()
    print("test_focus_match ok")
