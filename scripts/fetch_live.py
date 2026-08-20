#!/usr/bin/env python3
"""Snapshot OpenDota live lobbies for TI15 eight-team games. No video."""
from __future__ import annotations

import json
import re
import time
import urllib.error
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


def get_json(url: str, retries: int = 4) -> list | dict:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 and i < retries - 1:
                time.sleep(2**i)
                continue
            raise
        except (TimeoutError, urllib.error.URLError) as e:
            last = e
            if i < retries - 1:
                time.sleep(1)
                continue
            raise
    raise last or RuntimeError(url)


def ids_for(name: str) -> set[int]:
    return set(TEAM_IDS.get(name) or [])


def is_active(game: dict) -> bool:
    return int(game.get("deactivate_time") or game.get("deactivateTime") or 0) <= 0


def game_clock(game: dict) -> int:
    return int(game.get("game_time") or game.get("gameTime") or 0)


def pick_game(games: list[dict], team_a: str, team_b: str) -> dict | None:
    """Prefer the newest map. OpenDota often keeps G1 'active' after G2 picking starts."""
    want_a = ids_for(team_a)
    want_b = ids_for(team_b)
    active = [g for g in games or [] if is_active(g)]
    hits: list[dict] = []
    for game in active:
        rad = int(game.get("team_id_radiant") or (game.get("radiant") or {}).get("id") or 0)
        dire = int(game.get("team_id_dire") or (game.get("dire") or {}).get("id") or 0)
        if (rad in want_a and dire in want_b) or (rad in want_b and dire in want_a):
            hits.append(game)
    if not hits:
        for game in active:
            if int(game.get("league_id") or 0) != TI_LEAGUE:
                continue
            names = {
                ID_TO_TEAM.get(int(game.get("team_id_radiant") or 0)),
                ID_TO_TEAM.get(int(game.get("team_id_dire") or 0)),
            }
            if {team_a, team_b} <= names:
                hits.append(game)
    if not hits:
        return None
    hits.sort(key=lambda g: (game_clock(g), str(g.get("match_id") or g.get("matchId") or "")))
    return hits[0]


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
        "radiantWin": game.get("radiant_win") if isinstance(game.get("radiant_win"), bool) else None,
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


MATCH_URL = "https://api.opendota.com/api/matches/"


def load_playoffs() -> dict:
    path = ROOT / "data" / "playoffs.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def compact_ids(game: dict) -> tuple[int, int]:
    rad = int(game.get("team_id_radiant") or (game.get("radiant") or {}).get("id") or 0)
    dire = int(game.get("team_id_dire") or (game.get("dire") or {}).get("id") or 0)
    return rad, dire


def game_match_id(game: dict) -> str:
    return str(game.get("match_id") or game.get("matchId") or "")


def is_pair_game(game: dict, team_a: str, team_b: str) -> bool:
    rad, dire = compact_ids(game)
    want_a = ids_for(team_a)
    want_b = ids_for(team_b)
    return (rad in want_a and dire in want_b) or (rad in want_b and dire in want_a)


def winner_from_detail(detail: dict, team_a: str, team_b: str) -> str | None:
    if not isinstance(detail, dict) or not isinstance(detail.get("radiant_win"), bool):
        return None
    rad = int(detail.get("radiant_team_id") or (detail.get("radiant_team") or {}).get("team_id") or 0)
    dire = int(detail.get("dire_team_id") or (detail.get("dire_team") or {}).get("team_id") or 0)
    want_a = ids_for(team_a)
    want_b = ids_for(team_b)
    if rad in want_a and dire in want_b:
        a_is_radiant = True
    elif rad in want_b and dire in want_a:
        a_is_radiant = False
    else:
        return None
    a_won = detail["radiant_win"] if a_is_radiant else not detail["radiant_win"]
    return team_a if a_won else team_b


def load_local_winners() -> dict[str, str]:
    path = ROOT / "data" / "games.json"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        blob = json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return {}
    for game in blob.get("games") or []:
        mid = str(game.get("match_id") or "")
        winner = game.get("winner")
        if mid and winner:
            out[mid] = winner
    return out


def score_from_finished_ids(
    match_ids: list[str],
    team_a: str,
    team_b: str,
    skip_id: str | None = None,
    local_winners: dict[str, str] | None = None,
) -> str | None:
    wins_a = 0
    wins_b = 0
    skip = str(skip_id or "")
    local = local_winners if local_winners is not None else load_local_winners()
    for mid in match_ids:
        if not mid or str(mid) == skip:
            continue
        winner = local.get(str(mid))
        if winner not in (team_a, team_b):
            try:
                detail = get_json(MATCH_URL + str(mid))
            except Exception as e:  # noqa: BLE001
                print("match lookup skipped", mid, e)
                continue
            winner = winner_from_detail(detail if isinstance(detail, dict) else {}, team_a, team_b)
        if winner == team_a:
            wins_a += 1
        elif winner == team_b:
            wins_b += 1
    if wins_a or wins_b:
        return f"{wins_a}-{wins_b}"
    return None


def overlay_series(
    games: list[dict],
    lp: dict[str, dict],
    playoffs: dict | None = None,
    local_winners: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Fill series score/matchIds from OpenDota when Liquipedia lags or fails."""
    out = {k: dict(v) for k, v in (lp or {}).items()}
    blob = playoffs if playoffs is not None else load_playoffs()
    winners = local_winners if local_winners is not None else load_local_winners()
    live_ids = {game_match_id(g) for g in games or [] if is_active(g) and game_match_id(g)}
    for match in blob.get("matches") or []:
        mid = match.get("id")
        team_a, team_b = match.get("teamA"), match.get("teamB")
        if not mid or not isinstance(team_a, str) or not isinstance(team_b, str):
            continue
        pair = [g for g in games or [] if is_pair_game(g, team_a, team_b)]
        ids = []
        for game in pair:
            gid = game_match_id(game)
            if gid and gid not in ids:
                ids.append(gid)
        row = dict(out.get(mid) or {})
        merged = list(dict.fromkeys([*(row.get("matchIds") or []), *ids]))
        if merged:
            row["matchIds"] = merged
        if not row.get("score"):
            skip = next((i for i in merged if i in live_ids), None)
            score = score_from_finished_ids(merged, team_a, team_b, skip_id=skip, local_winners=winners)
            if score:
                row["score"] = score
        if row:
            out[mid] = row
    return out


def build_snapshot(raw: list[dict] | None = None, wikitext: str | None = None, skip_lp: bool = False) -> dict:
    prev_path = ROOT / "web" / "data" / "live.json"
    prev = json.loads(prev_path.read_text()) if prev_path.exists() else {}
    if raw is not None:
        games = ti_games(raw if isinstance(raw, list) else [])
    else:
        try:
            fetched = get_json(LIVE_URL)
            games = ti_games(fetched if isinstance(fetched, list) else [])
        except Exception as e:  # noqa: BLE001
            print("opendota live failed", e)
            games = prev.get("games") or []
    matches: dict[str, dict] = dict(prev.get("matches") or {}) if prev else {}
    if not skip_lp:
        try:
            matches = lp_matches(wikitext)
        except Exception as e:  # noqa: BLE001
            print("lp parse skipped", e)
    matches = overlay_series(games, matches)
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
    try:
        snap = build_snapshot()
    except Exception as e:  # noqa: BLE001
        print("snapshot failed", e)
        return
    path = ROOT / "web" / "data" / "live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and core_payload(json.loads(path.read_text())) == core_payload(snap):
        print("unchanged", path)
        return
    path.write_text(json.dumps(snap, ensure_ascii=False))
    print("wrote", path, "games", len(snap["games"]), "matches", len(snap.get("matches") or {}))


if __name__ == "__main__":
    main()
