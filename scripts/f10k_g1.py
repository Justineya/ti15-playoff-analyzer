#!/usr/bin/env python3
"""Game-1 first-to-10-kills rates from TI15 + EWC maps."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EIGHT = [
    "TEAM VISION",
    "Team Liquid",
    "Nigma Galaxy",
    "Team Spirit",
    "Iron Wing",
    "Team Falcons",
    "BoomBoys",
    "Team Yandex",
]


def _load_games() -> list[dict]:
    ti = json_games("games.json")
    ewc_path = ROOT / "data" / "ewc_games.json"
    ewc = json_games("ewc_games.json") if ewc_path.exists() else []
    for g in ti:
        g["_src"] = "ti15"
    for g in ewc:
        g["_src"] = "ewc"
    games = ti + ewc
    mark_game_index(games)
    return games


def json_games(name: str) -> list[dict]:
    import json

    return json.loads((ROOT / "data" / name).read_text()).get("games") or []


def mark_game_index(games: list[dict]) -> None:
    by_series: dict = defaultdict(list)
    for g in games:
        by_series[g.get("series_id") or g.get("match_id")].append(g)
    for rows in by_series.values():
        rows.sort(key=lambda x: x.get("start_time") or 0)
        for i, g in enumerate(rows, 1):
            g["_g"] = i


def f10_team(game: dict) -> str | None:
    f = game.get("f10k") or {}
    side = f.get("side")
    if side == "radiant":
        return game.get("radiant")
    if side == "dire":
        return game.get("dire")
    return None


def _rate(rows: list[dict], name: str) -> dict:
    got = n = converted = 0
    times: list[int] = []
    mids: dict[str, int] = defaultdict(int)
    for g in rows:
        if name not in (g.get("radiant"), g.get("dire")):
            continue
        side = "radiant" if g.get("radiant") == name else "dire"
        if not g.get("f10k"):
            continue
        n += 1
        hit = g["f10k"].get("side") == side
        if hit:
            got += 1
            if g.get("winner") == name:
                converted += 1
            t = g["f10k"].get("time")
            if t is not None:
                times.append(int(t))
            mid = ((g.get("sides") or {}).get(side) or {}).get("mid") or {}
            if mid.get("hero"):
                mids[mid["hero"]] += 1
    return {
        "got": got,
        "n": n,
        "rate": round(got / n, 3) if n else None,
        "convert": round(converted / got, 3) if got else None,
        "avgTimeMin": round(sum(times) / len(times) / 60, 1) if times else None,
        "mid": max(mids, key=mids.get) if mids else None,
    }


def _convert(rows: list[dict]) -> dict:
    n = wins = 0
    for g in rows:
        t = f10_team(g)
        if not t:
            continue
        n += 1
        wins += int(g.get("winner") == t)
    return {"n": n, "win": wins, "rate": round(wins / n, 3) if n else None}


def team_row(games: list[dict], name: str) -> dict:
    mine = [g for g in games if name in (g.get("radiant"), g.get("dire"))]
    g1 = [g for g in mine if g.get("_g") == 1]
    return {"all": _rate(mine, name), "g1": _rate(g1, name)}


def build_report(games: list[dict] | None = None) -> dict:
    games = list(games) if games is not None else _load_games()
    mark_game_index(games)
    g1 = [g for g in games if g.get("_g") == 1]
    later = [g for g in games if (g.get("_g") or 0) >= 2]
    return {
        "sample": "TI15 + EWC 八强地图，不加权。系列里开得最早的一局算第一局。",
        "overall": {
            "g1": _convert(g1),
            "later": _convert(later),
            "all": _convert(games),
        },
        "teams": {name: team_row(games, name) for name in EIGHT},
        "note": "先到10杀之后第一局大约七成赢图，后面的局略高。不是稳赢，不要当低保。",
    }


def main() -> None:
    import json
    from datetime import datetime, timedelta, timezone

    out = build_report()
    out["asOf"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " CST"
    path = ROOT / "data" / "f10k_g1.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote", path, "g1", out["overall"]["g1"])


if __name__ == "__main__":
    main()
