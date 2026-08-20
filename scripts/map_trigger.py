#!/usr/bin/env python3
"""Flag a Cursor launch when a playoff map ends — from live.json, not ingest.

daily_briefing.py only saw finished maps after OpenDota parse landed in
games.json. Game 2 often starts (and Liquipedia already has 1-0) before that.
This writes data/cursor-launch.json for launch_eod_cursor.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
LIVE_PATH = ROOT / "web" / "data" / "live.json"
GAMES_PATH = ROOT / "data" / "games.json"
PLAYOFFS_PATH = ROOT / "data" / "playoffs.json"
STATE_PATH = ROOT / "data" / "briefing-state.json"
LAUNCH_PATH = ROOT / "data" / "cursor-launch.json"
MIN_GAME_TIME = 300
PLAYOFF_START_TS = datetime(2026, 8, 20, 0, 0, tzinfo=CST).timestamp()


def maps_played(score) -> int:
    raw = str(score or "")
    if "-" not in raw:
        return 0
    left, right = raw.replace(":", "-").split("-", 1)
    try:
        return int(left.strip()) + int(right.strip())
    except ValueError:
        return 0


def as_id(value) -> str:
    return str(value or "").strip()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def game_clock(game: dict) -> int:
    return int(game.get("gameTime") or game.get("game_time") or 0)


def is_active(game: dict) -> bool:
    return int(game.get("deactivateTime") or game.get("deactivate_time") or 0) <= 0


def game_match_id(game: dict) -> str:
    return as_id(game.get("matchId") or game.get("match_id"))


def collect_finished(live: dict, games_blob: dict, playoffs: dict) -> tuple[set[str], dict[str, str]]:
    """Finished map keys + latest series scores. Keys are OpenDota ids or series:mapN."""
    finished: set[str] = set()
    series: dict[str, str] = {}

    for game in games_blob.get("games") or []:
        if game.get("source") == "ewc":
            continue
        if int(game.get("start_time") or 0) < PLAYOFF_START_TS:
            continue
        mid = as_id(game.get("match_id"))
        if mid and game.get("winner"):
            finished.add(mid)

    live_games = list(live.get("games") or [])
    active_ids = {game_match_id(g) for g in live_games if is_active(g) and game_match_id(g)}
    for game in live_games:
        mid = game_match_id(game)
        if not mid:
            continue
        deactivated = not is_active(game)
        ended_flag = game.get("radiantWin")
        if ended_flag is None:
            ended_flag = game.get("radiant_win")
        ended = isinstance(ended_flag, bool)
        if (deactivated or ended) and game_clock(game) >= MIN_GAME_TIME:
            finished.add(mid)

    def add_series_row(sid: str, row: dict) -> None:
        if not sid:
            return
        score = row.get("score")
        played = maps_played(score)
        if played:
            series[sid] = str(score)
        ids = [as_id(x) for x in (row.get("matchIds") or []) if as_id(x)]
        for i, mid in enumerate(ids):
            if i < played:
                finished.add(mid)
            # A later lobby for this series is live → earlier maps are done.
            if any(later in active_ids for later in ids[i + 1 :]):
                finished.add(mid)
        for mp in row.get("maps") or []:
            if mp.get("winner") not in (1, 2):
                continue
            n = int(mp.get("n") or 0)
            if n and n <= len(ids):
                finished.add(ids[n - 1])
            elif n:
                finished.add(f"{sid}:map{n}")
        if played and not ids:
            for n in range(1, played + 1):
                finished.add(f"{sid}:map{n}")

    for sid, row in (live.get("matches") or {}).items():
        add_series_row(sid, row or {})
    for match in playoffs.get("matches") or []:
        add_series_row(as_id(match.get("id")), match)

    return finished, series


def seed_seen(state: dict) -> set[str]:
    seen = {as_id(x) for x in (state.get("finishedMatchIds") or []) if as_id(x)}
    if seen:
        return seen
    # First run after this feature: IW/Spirit maps already in mapIds must not re-fire.
    return {as_id(x) for x in (state.get("mapIds") or []) if as_id(x)}


def decide(state: dict, finished: set[str], series: dict[str, str]) -> dict:
    seen = seed_seen(state)
    pending = [as_id(x) for x in (state.get("pendingLaunch") or []) if as_id(x)]
    pending_set = set(pending)
    new_ids = sorted(finished - seen - pending_set)
    if new_ids:
        pending.extend(new_ids)
    launch = bool(pending)
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST"
    reason = f"finished maps {pending}" if launch else "no new playoff map"
    new_state = dict(state)
    new_state["series"] = {**(state.get("series") or {}), **series}
    new_state["pendingLaunch"] = pending
    new_state["finishedMatchIds"] = sorted(seen)
    new_state["asOf"] = now if new_ids else (state.get("asOf") or now)
    launch_blob = {
        "launch": launch,
        "fresh": bool(new_ids),
        "reason": reason,
        "newMapIds": pending,
        "series": series,
        "asOf": new_state["asOf"],
    }
    return {"state": new_state, "launch": launch_blob}


def mark_launched(state: dict) -> dict:
    pending = [as_id(x) for x in (state.get("pendingLaunch") or []) if as_id(x)]
    seen = seed_seen(state)
    for mid in pending:
        seen.add(mid)
    out = dict(state)
    out["finishedMatchIds"] = sorted(seen)
    out["pendingLaunch"] = []
    return out


def main() -> None:
    live = load_json(LIVE_PATH, {})
    games = load_json(GAMES_PATH, {})
    playoffs = load_json(PLAYOFFS_PATH, {})
    state = load_json(STATE_PATH, {})
    finished, series = collect_finished(live, games, playoffs)
    decided = decide(state, finished, series)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(decided["state"], ensure_ascii=False, indent=2) + "\n")
    LAUNCH_PATH.write_text(json.dumps(decided["launch"], ensure_ascii=False, indent=2) + "\n")
    blob = decided["launch"]
    print("map_trigger launch", blob["launch"], blob["reason"])


if __name__ == "__main__":
    main()
