#!/usr/bin/env python3
"""Snapshot OpenDota live lobbies for TI15 eight-team games. No video."""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fetch_schedule import LP_TO_OURS, fetch_wikitext, match_blocks, parse_kickoff

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


def is_active(game: dict) -> bool:
    return int(game.get("deactivate_time") or 0) <= 0


def pick_game(games: list[dict], team_a: str, team_b: str) -> dict | None:
    want_a = ids_for(team_a)
    want_b = ids_for(team_b)
    active = [g for g in games or [] if is_active(g)]
    pool = active or list(games or [])
    for game in pool:
        rad = int(game.get("team_id_radiant") or 0)
        dire = int(game.get("team_id_dire") or 0)
        if (rad in want_a and dire in want_b) or (rad in want_b and dire in want_a):
            return game
    for game in pool:
        if int(game.get("league_id") or 0) != TI_LEAGUE:
            continue
        names = {ID_TO_TEAM.get(int(game.get("team_id_radiant") or 0)), ID_TO_TEAM.get(int(game.get("team_id_dire") or 0))}
        if {team_a, team_b} <= names:
            return game
    return None


HERO_RE = re.compile(r"\|t([12])h(\d+)=([^\|\n}]+)")
WIN_RE = re.compile(r"\|winner=(\d+)")
LEN_RE = re.compile(r"\|length=([^\|\n}]+)")
MATCHID_RE = re.compile(r"\|matchid(\d+)=(\d+)")
MAP_SPLIT_RE = re.compile(r"\|map(\d+)\s*=\s*\{\{Map", re.I)


def _clean(val: str) -> str:
    return (val or "").strip()


def parse_map_block(block: str) -> dict:
    heroes: dict[int, dict[int, str]] = {1: {}, 2: {}}
    for side, n, name in HERO_RE.findall(block or ""):
        name = _clean(name)
        if name:
            heroes[int(side)][int(n)] = name
    win = WIN_RE.search(block or "")
    length = LEN_RE.search(block or "")
    winner = int(win.group(1)) if win and win.group(1).isdigit() else None
    return {
        "heroes1": [heroes[1][i] for i in sorted(heroes[1])],
        "heroes2": [heroes[2][i] for i in sorted(heroes[2])],
        "winner": winner if winner in (1, 2) else None,
        "length": (_clean(length.group(1)) or None) if length else None,
    }


def parse_lp_match(body: str) -> dict:
    kickoff = parse_kickoff(body)
    match_ids = [mid for _, mid in sorted(MATCHID_RE.findall(body or ""), key=lambda x: int(x[0]))]
    maps = []
    hits = list(MAP_SPLIT_RE.finditer(body or ""))
    for i, hit in enumerate(hits):
        chunk = (body or "")[hit.end() : hits[i + 1].start() if i + 1 < len(hits) else len(body or "")]
        row = parse_map_block(chunk)
        row["n"] = int(hit.group(1))
        maps.append(row)
    wins1 = sum(1 for m in maps if m.get("winner") == 1)
    wins2 = sum(1 for m in maps if m.get("winner") == 2)
    score = f"{wins1}-{wins2}" if wins1 or wins2 else None
    return {
        "datetime": kickoff.strftime("%Y-%m-%d %H:%M") if kickoff else None,
        "matchIds": match_ids,
        "maps": maps,
        "score": score,
    }


def lp_matches(wikitext: str | None = None) -> dict[str, dict]:
    text = wikitext if wikitext is not None else fetch_wikitext()
    out: dict[str, dict] = {}
    for lp_id, body in match_blocks(text).items():
        ours = LP_TO_OURS.get(lp_id)
        if ours:
            out[ours] = parse_lp_match(body)
    return out


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
        "deactivateTime": int(game.get("deactivate_time") or 0),
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


def build_snapshot(raw: list[dict] | None = None, wikitext: str | None = None, skip_lp: bool = False) -> dict:
    raw = raw if raw is not None else get_json(LIVE_URL)
    games = ti_games(raw if isinstance(raw, list) else [])
    matches: dict[str, dict] = {}
    if not skip_lp:
        try:
            matches = lp_matches(wikitext)
        except Exception as e:  # noqa: BLE001
            print("lp parse skipped", e)
    return {
        "asOf": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S") + " CST",
        "source": LIVE_URL,
        "note": "OpenDota 观战记分 + 液体百科赛程。选人阶段观战源常常不推英雄，出兵后才会跳人头。没有画面。",
        "games": games,
        "matches": matches,
    }


def core_payload(blob: dict) -> str:
    return json.dumps({"games": blob.get("games"), "matches": blob.get("matches")}, ensure_ascii=False, sort_keys=True)


def main() -> None:
    snap = build_snapshot()
    path = ROOT / "web" / "data" / "live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and core_payload(json.loads(path.read_text())) == core_payload(snap):
        print("unchanged", path)
        return
    path.write_text(json.dumps(snap, ensure_ascii=False))
    print("wrote", path, "games", len(snap["games"]), "matches", len(snap.get("matches") or {}))


if __name__ == "__main__":
    main()
