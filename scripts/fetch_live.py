#!/usr/bin/env python3
"""Snapshot OpenDota live lobbies for TI15 eight-team games. No video."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_URL = "https://api.opendota.com/api/live"
UA = {
    "User-Agent": (
        "TI15PlayoffAnalyzer/1.0 "
        "(https://github.com/Justineya/ti15-playoff-analyzer; live scoreboard, no video)"
    )
}
TI_LEAGUE = 19719
# Playoff OpenDota ids plus recent rename / EWC ids.
TEAM_IDS: dict[str, list[int]] = {
    "TEAM VISION": [9572001, 9824702],
    "Team Liquid": [2163],
    "Nigma Galaxy": [10136357],
    "Team Spirit": [7119388],
    "Iron Wing": [10150413, 10182357, 8291895],
    "Team Falcons": [9247354],
    "BoomBoys": [8255888],
    "Team Yandex": [9823272],
}
ID_TO_TEAM = {i: name for name, ids in TEAM_IDS.items() for i in ids}


def get_json(url: str) -> list | dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ids_for(name: str) -> set[int]:
    return set(TEAM_IDS.get(name) or [])


def pick_game(games: list[dict], team_a: str, team_b: str) -> dict | None:
    want_a = ids_for(team_a)
    want_b = ids_for(team_b)
    for game in games or []:
        rad = int(game.get("team_id_radiant") or 0)
        dire = int(game.get("team_id_dire") or 0)
        if (rad in want_a and dire in want_b) or (rad in want_b and dire in want_a):
            return game
    for game in games or []:
        if int(game.get("league_id") or 0) != TI_LEAGUE:
            continue
        names = {ID_TO_TEAM.get(int(game.get("team_id_radiant") or 0)), ID_TO_TEAM.get(int(game.get("team_id_dire") or 0))}
        if {team_a, team_b} <= names:
            return game
    return None


def compact_player(p: dict) -> dict:
    return {
        "accountId": p.get("account_id"),
        "heroId": int(p.get("hero_id") or 0),
        "name": p.get("name") or p.get("personaname") or "",
        "team": int(p.get("team") or 0),
        "slot": int(p.get("team_slot") or 0),
    }


def compact_game(game: dict) -> dict:
    rad = int(game.get("team_id_radiant") or 0)
    dire = int(game.get("team_id_dire") or 0)
    return {
        "matchId": str(game.get("match_id") or ""),
        "seriesId": game.get("series_id"),
        "leagueId": game.get("league_id"),
        "gameTime": game.get("game_time"),
        "delay": game.get("delay"),
        "spectators": game.get("spectators"),
        "radiantScore": game.get("radiant_score") or 0,
        "direScore": game.get("dire_score") or 0,
        "radiantLead": game.get("radiant_lead") or 0,
        "lastUpdate": game.get("last_update_time"),
        "gameMode": game.get("game_mode"),
        "radiant": {
            "id": rad,
            "name": ID_TO_TEAM.get(rad) or game.get("team_name_radiant") or "Radiant",
        },
        "dire": {
            "id": dire,
            "name": ID_TO_TEAM.get(dire) or game.get("team_name_dire") or "Dire",
        },
        "players": [compact_player(p) for p in game.get("players") or []],
    }


def ti_games(raw: list[dict]) -> list[dict]:
    eight = set(ID_TO_TEAM)
    out = []
    for game in raw or []:
        rad = int(game.get("team_id_radiant") or 0)
        dire = int(game.get("team_id_dire") or 0)
        if int(game.get("league_id") or 0) == TI_LEAGUE or (rad in eight and dire in eight):
            out.append(compact_game(game))
    return out


def build_snapshot(raw: list[dict] | None = None) -> dict:
    raw = raw if raw is not None else get_json(LIVE_URL)
    games = ti_games(raw if isinstance(raw, list) else [])
    return {
        "asOf": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S") + " CST",
        "source": LIVE_URL,
        "note": "OpenDota 观战记分板，约 1–2 分钟延迟，没有画面。",
        "games": games,
    }


def main() -> None:
    snap = build_snapshot()
    path = ROOT / "web" / "data" / "live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False))
    print("wrote", path, "games", len(snap["games"]))


if __name__ == "__main__":
    main()
