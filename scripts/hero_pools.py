#!/usr/bin/env python3
"""TI15 most-picked heroes per playoff team. Display only — not a model input."""
from __future__ import annotations

import json
from collections import Counter
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
TOP_PICKS = 8
TOP_FIRST = 5
TOP_BANS = 6
TOP_ROLE = 4


def _load_ti_games() -> list[dict]:
    blob = json.loads((ROOT / "data" / "games.json").read_text())
    games = blob.get("games") or []
    return [g for g in games if g.get("source", "ti15") == "ti15"]


def _side(game: dict, name: str) -> str | None:
    if game.get("radiant") == name:
        return "radiant"
    if game.get("dire") == name:
        return "dire"
    return None


def _rows(counter: Counter, wins: Counter | None = None, extra: Counter | None = None, limit: int = 8) -> list[dict]:
    out = []
    for hero, n in counter.most_common(limit):
        if not hero or hero == "?":
            continue
        row = {"hero": hero, "n": n}
        if wins is not None:
            w = int(wins[hero])
            row["wins"] = w
            row["wr"] = round(w / n, 3) if n else None
        if extra is not None:
            row["first"] = int(extra[hero])
        out.append(row)
    return out


def _role_pool(hero_counts: Counter, player_counts: Counter, limit: int = TOP_ROLE) -> dict:
    return {
        "heroes": _rows(hero_counts, limit=limit),
        "players": [{"player": p, "n": n} for p, n in player_counts.most_common(3) if p],
    }


def team_pool(games: list[dict], name: str) -> dict:
    picks: Counter = Counter()
    pick_wins: Counter = Counter()
    first: Counter = Counter()
    bans: Counter = Counter()
    hero_ids: dict[str, int] = {}
    roles = {key: Counter() for key in ("mid", "pos4", "pos5")}
    role_players = {key: Counter() for key in ("mid", "pos4", "pos5")}
    maps = 0
    wins = 0
    for game in games:
        side = _side(game, name)
        if not side:
            continue
        maps += 1
        won = game.get("winner") == name
        if won:
            wins += 1
        draft = ((game.get("draft") or {}).get(side) or {})
        heroes = [p.get("hero") for p in draft.get("picks") or [] if p.get("hero")]
        for item in draft.get("picks") or []:
            hero = item.get("hero")
            if not hero:
                continue
            picks[hero] += 1
            if won:
                pick_wins[hero] += 1
            if item.get("hero_id") and hero not in hero_ids:
                hero_ids[hero] = int(item["hero_id"])
        if heroes:
            first[heroes[0]] += 1
        for item in draft.get("bans") or []:
            hero = item.get("hero")
            if hero:
                bans[hero] += 1
        side_blob = ((game.get("sides") or {}).get(side) or {})
        for key in ("mid", "pos4", "pos5"):
            slot = side_blob.get(key) or {}
            if slot.get("hero"):
                roles[key][slot["hero"]] += 1
            if slot.get("player"):
                role_players[key][slot["player"]] += 1
    pick_rows = _rows(picks, pick_wins, first, TOP_PICKS)
    for row in pick_rows:
        if row["hero"] in hero_ids:
            row["heroId"] = hero_ids[row["hero"]]
    return {
        "name": name,
        "maps": maps,
        "wins": wins,
        "picks": pick_rows,
        "firstPicks": _rows(first, limit=TOP_FIRST),
        "bans": _rows(bans, limit=TOP_BANS),
        "roles": {key: _role_pool(roles[key], role_players[key]) for key in ("mid", "pos4", "pos5")},
        "pickIndex": {hero: {"n": n, "wins": pick_wins[hero]} for hero, n in picks.items()},
        "banIndex": dict(bans),
    }


def build_report(games: list[dict] | None = None) -> dict:
    games = games if games is not None else _load_ti_games()
    teams = {name: team_pool(games, name) for name in EIGHT}
    return {
        "sample": f"TI15 八强 {len(games)} 局",
        "note": "只算本届八强在 TI15 打过的图，不含 EWC。常用 = 选出来的次数，不是选手个人生涯。",
        "teams": teams,
    }


if __name__ == "__main__":
    report = build_report()
    for name, pool in report["teams"].items():
        top = ", ".join(f"{r['hero']} {r['n']}" for r in pool["picks"][:5])
        print(f"{name} ({pool['maps']}): {top}")
