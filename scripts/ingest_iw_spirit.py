#!/usr/bin/env python3
"""Tundra / Iron Wing vs Team Spirit maps: winners and first-to-10-kills.

Current IW five (Pure/bzm/33/Ari/Whitemon) is the Tundra line from Slam IV on.
TI25 Tundra was Crystallis — kept in the file as dropped, not in the headline sample.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from ingest_games import analyze_game, fetch_match, get_json, load_heroes

ROOT = Path(__file__).resolve().parents[1]
IW_IDS = {8291895, 10150413, 10182357}
SPIRIT_ID = 7119388
TEAM_MAP = {tid: "Iron Wing" for tid in IW_IDS}
TEAM_MAP[SPIRIT_ID] = "Team Spirit"
SINCE = "2025-08-01"
ROSTER_MIN = 4
IW_ACCOUNTS = {331855530, 93618577, 86698277, 346412363, 136829091}  # Pure, bzm, 33, Ari, Whitemon
SPIRIT_ACCOUNTS = {321580662, 106305042, 302214028, 218231587, 847565596}  # Yatoro, Larl, Collapse, not_me, rue


def list_h2h() -> list[dict]:
    sql = f"""
    SELECT match_id, start_time, leagueid, radiant_team_id, dire_team_id,
           radiant_win, duration, series_id
    FROM matches
    WHERE start_time >= extract(epoch FROM timestamp '{SINCE}')
      AND (
        (radiant_team_id IN ({",".join(str(i) for i in sorted(IW_IDS))}) AND dire_team_id = {SPIRIT_ID})
        OR (dire_team_id IN ({",".join(str(i) for i in sorted(IW_IDS))}) AND radiant_team_id = {SPIRIT_ID})
      )
    ORDER BY start_time
    """
    url = "https://api.opendota.com/api/explorer?" + urlencode({"sql": sql})
    return get_json(url)["rows"]


def league_names(ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    sql = f"SELECT leagueid, name FROM leagues WHERE leagueid IN ({','.join(str(i) for i in sorted(ids))})"
    url = "https://api.opendota.com/api/explorer?" + urlencode({"sql": sql})
    return {int(r["leagueid"]): r["name"] for r in get_json(url)["rows"]}


def account_ids(match: dict, side: str) -> set[int]:
    out = set()
    for p in match.get("players") or []:
        slot = p.get("player_slot") or 0
        ps = "radiant" if slot < 128 else "dire"
        if ps == side and p.get("account_id"):
            out.add(int(p["account_id"]))
    return out


def f10_name(game: dict) -> str | None:
    f = game.get("f10k") or {}
    if f.get("side") == "radiant":
        return game.get("radiant")
    if f.get("side") == "dire":
        return game.get("dire")
    return None


def summarize(maps: list[dict]) -> dict:
    if not maps:
        return {"maps": 0, "iwMaps": 0, "spiritMaps": 0, "iwF10": 0, "spiritF10": 0, "series": []}
    by_s: dict = defaultdict(list)
    for row in maps:
        by_s[row.get("series_id")].append(row)
    series = []
    for sid, rows in by_s.items():
        rows = sorted(rows, key=lambda x: x["start_time"])
        iw = sum(1 for r in rows if r["winner"] == "Iron Wing")
        sp = sum(1 for r in rows if r["winner"] == "Team Spirit")
        g1 = rows[0]
        series.append(
            {
                "series_id": sid,
                "date": g1["date"],
                "event": g1["event"],
                "score": f"{iw}-{sp}",
                "winner": "Iron Wing" if iw > sp else "Team Spirit" if sp > iw else "split",
                "g1Winner": g1["winner"],
                "g1F10": g1["f10"],
                "maps": [
                    {
                        "game": i,
                        "winner": r["winner"],
                        "f10": r["f10"],
                        "f10TimeMin": round(r["f10Time"] / 60, 1) if r.get("f10Time") is not None else None,
                        "converted": r["winner"] == r["f10"],
                    }
                    for i, r in enumerate(rows, 1)
                ],
            }
        )
    series.sort(key=lambda s: s["date"])
    iw_f10 = [r for r in maps if r["f10"] == "Iron Wing"]
    sp_f10 = [r for r in maps if r["f10"] == "Team Spirit"]
    g1s = [s["maps"][0] for s in series]
    return {
        "maps": len(maps),
        "seriesN": len(series),
        "iwMaps": sum(1 for r in maps if r["winner"] == "Iron Wing"),
        "spiritMaps": sum(1 for r in maps if r["winner"] == "Team Spirit"),
        "iwF10": len(iw_f10),
        "spiritF10": len(sp_f10),
        "iwF10ThenWin": sum(1 for r in iw_f10 if r["winner"] == "Iron Wing"),
        "spiritF10ThenWin": sum(1 for r in sp_f10 if r["winner"] == "Team Spirit"),
        "g1Iw": sum(1 for s in series if s["g1Winner"] == "Iron Wing"),
        "g1Spirit": sum(1 for s in series if s["g1Winner"] == "Team Spirit"),
        "g1IwF10": sum(1 for s in series if s["g1F10"] == "Iron Wing"),
        "g1SpiritF10": sum(1 for s in series if s["g1F10"] == "Team Spirit"),
        "series": series,
    }


def main() -> None:
    metas = list_h2h()
    names = league_names({int(m["leagueid"]) for m in metas})
    heroes, npc = load_heroes()
    maps = []
    for i, meta in enumerate(metas, 1):
        mid = int(meta["match_id"])
        print(f"[{i}/{len(metas)}] {mid}", flush=True)
        match = fetch_match(mid)
        game = analyze_game(meta, match, heroes, npc, team_map=TEAM_MAP, source="h2h", patch="")
        rad_ids = account_ids(match, "radiant")
        dire_ids = account_ids(match, "dire")
        iw_side = "radiant" if int(match.get("radiant_team_id") or 0) in IW_IDS else "dire"
        iw_n = len((rad_ids if iw_side == "radiant" else dire_ids) & IW_ACCOUNTS)
        sp_n = len((dire_ids if iw_side == "radiant" else rad_ids) & SPIRIT_ACCOUNTS)
        current = iw_n >= ROSTER_MIN
        f10 = f10_name(game)
        start = int(game.get("start_time") or meta.get("start_time") or 0)
        maps.append(
            {
                "match_id": mid,
                "start_time": start,
                "date": datetime.fromtimestamp(start, tz=timezone.utc).strftime("%Y-%m-%d"),
                "leagueId": meta.get("leagueid"),
                "event": names.get(int(meta["leagueid"]), str(meta.get("leagueid"))),
                "series_id": game.get("series_id") or meta.get("series_id"),
                "radiant": game["radiant"],
                "dire": game["dire"],
                "winner": game["winner"],
                "f10": f10,
                "f10Time": (game.get("f10k") or {}).get("time"),
                "duration": game.get("duration"),
                "parsed": game.get("parsed"),
                "iwRoster": iw_n,
                "spiritRoster": sp_n,
                "currentIw": current,
                "opendota": f"https://www.opendota.com/matches/{mid}",
            }
        )

    current_maps = [m for m in maps if m["currentIw"]]
    dropped = [m for m in maps if not m["currentIw"]]
    out = {
        "asOf": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC",
        "pair": ["Iron Wing", "Team Spirit"],
        "note": (
            "Iron Wing 前身是 Tundra。这里只把本届五人（Pure / bzm / 33 / Ari / Whitemon）"
            "至少 4 人在场的局算进样本。TI25 的 Tundra 是 Crystallis 阵容，另列、不进统计。"
        ),
        "current": summarize(current_maps),
        "droppedTi25": summarize(dropped),
        "maps": maps,
    }
    path = ROOT / "data" / "iw_spirit_h2h.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    cur = out["current"]
    print(
        "wrote",
        path,
        "current maps",
        cur["maps"],
        "IW",
        cur["iwMaps"],
        "Spirit",
        cur["spiritMaps"],
        "f10",
        cur["iwF10"],
        cur["spiritF10"],
    )


if __name__ == "__main__":
    main()
