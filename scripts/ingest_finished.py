#!/usr/bin/env python3
"""Ingest just-finished playoff maps into games.json, then the model can re-run.

Full ingest_games.py walks the whole league. After Game 1 we only need those
OpenDota ids so Game 2 odds include the new H2H / draft / F10K row.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ingest_games as ig
import map_trigger as mt

ROOT = Path(__file__).resolve().parents[1]
GAMES_PATH = ROOT / "data" / "games.json"
LIVE_PATH = ROOT / "web" / "data" / "live.json"
LAUNCH_PATH = ROOT / "data" / "cursor-launch.json"
TEAM_MAP = {**ig.EIGHT, **ig.EWC_EIGHT}


def as_int(value) -> int | None:
    raw = str(value or "").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def already_parsed(game: dict | None) -> bool:
    return bool(game and game.get("winner") and (game.get("parsed") or game.get("draft")))


def ids_to_ingest(live: dict, launch: dict, games_blob: dict) -> list[int]:
    want: list[int] = []
    seen: set[int] = set()

    def add(value) -> None:
        mid = as_int(value)
        if mid is None or mid in seen:
            return
        seen.add(mid)
        want.append(mid)

    for value in launch.get("newMapIds") or []:
        add(value)
    finished, _ = mt.collect_finished(live, games_blob, {"matches": []})
    for key in finished:
        add(key)
    have = {as_int(g.get("match_id")): g for g in games_blob.get("games") or []}
    out = []
    for mid in want:
        if already_parsed(have.get(mid)):
            continue
        out.append(mid)
    return out


def meta_from_match(match: dict, match_id: int) -> dict:
    return {
        "match_id": match.get("match_id") or match_id,
        "start_time": match.get("start_time"),
        "radiant_team_id": match.get("radiant_team_id"),
        "dire_team_id": match.get("dire_team_id"),
        "radiant_win": match.get("radiant_win"),
        "duration": match.get("duration"),
        "series_id": match.get("series_id"),
    }


def merge_game(games: list[dict], row: dict) -> list[dict]:
    mid = as_int(row.get("match_id"))
    out = [g for g in games if as_int(g.get("match_id")) != mid]
    out.append(row)
    out.sort(key=lambda g: int(g.get("start_time") or 0))
    return out


def main() -> None:
    live = json.loads(LIVE_PATH.read_text()) if LIVE_PATH.exists() else {}
    launch = json.loads(LAUNCH_PATH.read_text()) if LAUNCH_PATH.exists() else {}
    blob = json.loads(GAMES_PATH.read_text()) if GAMES_PATH.exists() else {"games": []}
    ids = ids_to_ingest(live, launch, blob)
    if not ids:
        print("ingest_finished: nothing new")
        return
    heroes, npc_by_id = ig.load_heroes()
    games = list(blob.get("games") or [])
    for mid in ids:
        print("ingest_finished", mid, flush=True)
        try:
            match = ig.fetch_match(mid)
        except Exception as err:  # noqa: BLE001
            print("ingest_finished skip", mid, err)
            continue
        if not isinstance(match, dict) or not match.get("match_id"):
            print("ingest_finished empty", mid)
            continue
        row = ig.analyze_game(meta_from_match(match, mid), match, heroes, npc_by_id, team_map=TEAM_MAP)
        games = merge_game(games, row)
    blob["games"] = games
    blob["n"] = len(games)
    blob["asOf"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " CST"
    GAMES_PATH.write_text(json.dumps(blob, ensure_ascii=False, indent=2) + "\n")
    print("ingest_finished wrote", GAMES_PATH, "added", ids)


if __name__ == "__main__":
    main()
