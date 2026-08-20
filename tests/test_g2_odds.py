#!/usr/bin/env python3
"""Game 2 card: series p after G1, and OpenDota winner → score."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def p_series_after(p_map: float, wins_a: int, wins_b: int, need: int = 2) -> float:
    memo: dict[tuple[int, int], float] = {}

    def walk(a: int, b: int) -> float:
        key = (a, b)
        if key in memo:
            return memo[key]
        if a >= need:
            v = 1.0
        elif b >= need:
            v = 0.0
        else:
            v = p_map * walk(a + 1, b) + (1 - p_map) * walk(a, b + 1)
        memo[key] = v
        return v

    return walk(wins_a, wins_b)


def next_game(score: str, fmt: str = "Bo3") -> int:
    if not score or "-" not in score:
        return 1
    a_s, b_s = score.replace(":", "-").split("-", 1)
    a, b = int(a_s), int(b_s)
    need = 3 if fmt.lower() == "bo5" else 2
    if a >= need or b >= need:
        return 1
    return a + b + 1


def test_bo3_switches_to_game_2() -> None:
    assert next_game("") == 1
    assert next_game("0-1") == 2
    assert next_game("1-0") == 2
    assert next_game("1-1") == 3
    assert next_game("2-0") == 1
    assert next_game("0-2") == 1


def test_series_p_after_g1_loss_is_map_squared() -> None:
    # Bo3, trail 0-1: must win both remaining maps.
    assert abs(p_series_after(0.5, 0, 1) - 0.25) < 1e-9
    assert abs(p_series_after(0.4, 0, 1) - 0.16) < 1e-9
    assert abs(p_series_after(0.5, 1, 0) - 0.75) < 1e-9


def test_opendota_spirit_radiant_win_is_0_1() -> None:
    script = r"""
global.window = global;
const fs = require("fs");
const path = require("path");
eval(fs.readFileSync(path.join("web", "live.js"), "utf8"));
const idMap = { "Iron Wing": [10150413], "Team Spirit": [7119388] };
const w = window.TI15_LIVE.winnerOfMatch(
  { radiant_win: true, radiant_team_id: 7119388, dire_team_id: 10150413 },
  "Iron Wing",
  "Team Spirit",
  idMap
);
if (w !== "B") {
  console.error("expected B (Spirit), got", w);
  process.exit(1);
}
if (window.TI15_LIVE.scoreFromWinners(["B"]) !== "0-1") process.exit(2);
if (window.TI15_LIVE.scoreFromWinners(["A", "B"]) !== "1-1") process.exit(3);
const pick = window.TI15_LIVE.pickGame(
  [
    { match_id: "8955197224", deactivate_time: 9, team_id_radiant: 7119388, team_id_dire: 10150413, league_id: 19719 },
    { match_id: "8955247801", deactivate_time: 0, team_id_radiant: 10150413, team_id_dire: 7119388, league_id: 19719 },
  ],
  "Iron Wing",
  "Team Spirit",
  idMap
);
if (!pick || String(pick.match_id) !== "8955247801") {
  console.error("expected live G2, got", pick && pick.match_id);
  process.exit(5);
}
if (window.TI15_LIVE.pickGame(
  [{ match_id: "8955197224", deactivate_time: 9, team_id_radiant: 7119388, team_id_dire: 10150413 }],
  "Iron Wing",
  "Team Spirit",
  idMap
)) process.exit(6);
const g2pick = window.TI15_LIVE.pickGame(
  [
    { match_id: "8955304019", deactivate_time: 0, game_time: 4524, team_id_radiant: 8255888, team_id_dire: 9572001 },
    { match_id: "8955383956", deactivate_time: 0, game_time: -10, team_id_radiant: 9572001, team_id_dire: 8255888 },
  ],
  "TEAM VISION",
  "BoomBoys",
  { "TEAM VISION": [9572001], BoomBoys: [8255888] }
);
if (!g2pick || String(g2pick.match_id) !== "8955383956") {
  console.error("expected G2 picking lobby, got", g2pick && g2pick.match_id);
  process.exit(7);
}
const g2long = window.TI15_LIVE.pickGame(
  [
    { match_id: "8955304019", deactivate_time: 0, game_time: 100, team_id_radiant: 8255888, team_id_dire: 9572001 },
    { match_id: "8955383956", deactivate_time: 0, game_time: 5000, team_id_radiant: 9572001, team_id_dire: 8255888 },
  ],
  "TEAM VISION",
  "BoomBoys",
  { "TEAM VISION": [9572001], BoomBoys: [8255888] }
);
if (!g2long || String(g2long.match_id) !== "8955383956") {
  console.error("expected newer match id even if G2 clock is longer, got", g2long && g2long.match_id);
  process.exit(8);
}
const lp = {
  score: "1-0",
  matchIds: ["8955304019", "8955383956"],
  maps: [{ n: 1, winner: 1 }],
};
const skipG1 = window.TI15_LIVE.pickGame(
  [
    { match_id: "8955304019", deactivate_time: 0, game_time: 4524, team_id_radiant: 8255888, team_id_dire: 9572001 },
    { match_id: "8955383956", deactivate_time: 0, game_time: -10, team_id_radiant: 9572001, team_id_dire: 8255888 },
  ],
  "TEAM VISION",
  "BoomBoys",
  { "TEAM VISION": [9572001], BoomBoys: [8255888] },
  lp
);
if (!skipG1 || String(skipG1.match_id) !== "8955383956") {
  console.error("expected LP to drop finished G1, got", skipG1 && skipG1.match_id);
  process.exit(9);
}
const done = window.TI15_LIVE.finishedMatchIds(lp);
if (!done.has("8955304019") || done.has("8955383956")) process.exit(10);
"""
    proc = subprocess.run(["node", "-e", script], cwd=ROOT, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout or f"exit {proc.returncode}")


if __name__ == "__main__":
    test_bo3_switches_to_game_2()
    test_series_p_after_g1_loss_is_map_squared()
    test_opendota_spirit_radiant_win_is_0_1()
    print("test_g2_odds ok")
