#!/usr/bin/env python3
"""Pull T1 major maps involving the TI15 eight (renames + roster check).

Writes data/majors_games.json. Not part of the 5-minute refresh — historical.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from ingest_games import get_json
from majors import (
    EIGHT,
    ROSTER_MIN,
    all_player_ids,
    canonical_side,
    league_by_id,
    majors_with_weights,
)

ROOT = Path(__file__).resolve().parents[1]


def fetch_league_matches(league_id: int) -> list[dict]:
    sql = f"""
    SELECT match_id, start_time, duration, radiant_team_id, dire_team_id,
           radiant_win, radiant_team_name, dire_team_name, series_id
    FROM matches
    WHERE leagueid={int(league_id)}
    ORDER BY start_time
    """
    url = "https://api.opendota.com/api/explorer?" + urlencode({"sql": sql})
    return get_json(url)["rows"]


def fetch_player_sides(match_ids: list[int], account_ids: set[int]) -> dict[int, dict[str, set[int]]]:
    """match_id → {radiant: {account_id}, dire: {account_id}} for TI-eight players only."""
    out: dict[int, dict[str, set[int]]] = defaultdict(lambda: {"radiant": set(), "dire": set()})
    if not match_ids:
        return out
    id_list = ",".join(str(i) for i in sorted(account_ids))
    chunk = 80
    for i in range(0, len(match_ids), chunk):
        mids = ",".join(str(int(x)) for x in match_ids[i : i + chunk])
        sql = f"""
        SELECT match_id, account_id, player_slot
        FROM player_matches
        WHERE match_id IN ({mids})
          AND account_id IN ({id_list})
        """
        url = "https://api.opendota.com/api/explorer?" + urlencode({"sql": sql})
        rows = get_json(url)["rows"]
        for row in rows:
            side = "radiant" if int(row["player_slot"] or 0) < 128 else "dire"
            out[int(row["match_id"])][side].add(int(row["account_id"]))
        print(f"  roster chunk {i // chunk + 1}/{(len(match_ids) + chunk - 1) // chunk} → {len(rows)} player rows", flush=True)
    return out


def slim_game(meta: dict, event: dict, sides: dict[str, set[int]]) -> dict | None:
    rad = canonical_side(
        sides.get("radiant") or set(),
        meta.get("radiant_team_name"),
        meta.get("radiant_team_id"),
    )
    dire = canonical_side(
        sides.get("dire") or set(),
        meta.get("dire_team_name"),
        meta.get("dire_team_id"),
    )
    if rad not in EIGHT and dire not in EIGHT:
        return None
    radiant_win = meta.get("radiant_win")
    winner = rad if radiant_win else dire
    return {
        "match_id": meta.get("match_id"),
        "series_id": meta.get("series_id"),
        "start_time": meta.get("start_time"),
        "duration": meta.get("duration"),
        "leagueId": event["leagueId"],
        "event": event["name"],
        "eventId": event["id"],
        "source": "major",
        "sample_weight": event["weight"],
        "radiant": rad,
        "dire": dire,
        "radiant_team_id": meta.get("radiant_team_id"),
        "dire_team_id": meta.get("dire_team_id"),
        "winner": winner,
        "radiant_win": radiant_win,
        "rosterOverlap": {
            "radiant": len(sides.get("radiant") or []),
            "dire": len(sides.get("dire") or []),
        },
        "opendota": f"https://www.opendota.com/matches/{meta.get('match_id')}",
    }


def fill_opponent_names(games: list[dict]) -> None:
    ids = {
        int(g[key])
        for g in games
        for side, key in (("radiant", "radiant_team_id"), ("dire", "dire_team_id"))
        if str(g.get(side) or "").startswith("team-") and g.get(key)
    }
    if not ids:
        return
    sql = f"SELECT team_id, name FROM teams WHERE team_id IN ({','.join(str(i) for i in sorted(ids))})"
    url = "https://api.opendota.com/api/explorer?" + urlencode({"sql": sql})
    names = {int(r["team_id"]): r["name"] for r in get_json(url)["rows"] if r.get("name")}
    for g in games:
        for side, key in (("radiant", "radiant_team_id"), ("dire", "dire_team_id")):
            if str(g.get(side) or "").startswith("team-") and g.get(key):
                g[side] = names.get(int(g[key]), g[side])
        g["winner"] = g["radiant"] if g.get("radiant_win") else g["dire"]


def main() -> None:
    events = majors_with_weights()
    by_league = league_by_id()
    players = all_player_ids()
    games: list[dict] = []
    skipped = 0
    for event in events:
        lid = int(event["leagueId"])
        print(f"{event['name']} league {lid} weight {event['weight']}", flush=True)
        metas = fetch_league_matches(lid)
        print(f"  matches {len(metas)}", flush=True)
        sides = fetch_player_sides([int(m["match_id"]) for m in metas], players)
        kept = 0
        for meta in metas:
            row = slim_game(meta, by_league[lid], sides.get(int(meta["match_id"])) or {})
            if row is None:
                skipped += 1
                continue
            games.append(row)
            kept += 1
        print(f"  kept {kept} (eight roster ≥{ROSTER_MIN})", flush=True)

    fill_opponent_names(games)

    per_team = {name: 0 for name in EIGHT}
    per_event = {e["id"]: 0 for e in events}
    for g in games:
        per_event[g["eventId"]] += 1
        for side in ("radiant", "dire"):
            if g[side] in per_team:
                per_team[g[side]] += 1

    out = {
        "asOf": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " CST",
        "window": "2026-02-16 ~ 2026-06-07",
        "note": (
            "近半年 T1 大赛、至少一侧是本届八强阵容（≥4/5 名 TI 选手）。"
            "改名已合并：PARIVISION/PVISION→VISION，BetBoom→BoomBoys，Tundra/1w→Iron Wing。"
            "权重按结束日距 TI 衰减；不含 BP/F10K（补丁不同）。"
            "未收 BLAST Slam VI（窗口外）、预选、Division 2、Essence。"
        ),
        "weight": {
            "ti": 1.0,
            "ewc": 0.45,
            "formula": "0.45 * 0.5 ** ((days_before_ti - 30) / 75), floor 0.10",
        },
        "events": events,
        "n": len(games),
        "skippedNoRoster": skipped,
        "gamesPerTeam": per_team,
        "gamesPerEvent": per_event,
        "games": games,
    }
    path = ROOT / "data" / "majors_games.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote", path, "games", len(games), "skipped", skipped)


if __name__ == "__main__":
    main()
