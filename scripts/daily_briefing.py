#!/usr/bin/env python3
"""After each finished map: last result + next map/series lean.

Writes web/data/daily.json. Cursor launch flags live in map_trigger.py
(live.json score / G2 lobby, not only parsed games.json).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
PLAYOFF_START = datetime(2026, 8, 20, 0, 0, tzinfo=CST)
STATE_PATH = ROOT / "data" / "briefing-state.json"
LIVE_PATH = ROOT / "web" / "data" / "live.json"
TAG = {
    "TEAM VISION": "VSN",
    "Team Liquid": "Liquid",
    "Nigma Galaxy": "NGX",
    "Team Spirit": "Spirit",
    "Iron Wing": "IW",
    "Team Falcons": "FLCN",
    "BoomBoys": "BB",
    "Team Yandex": "TY",
}


def load(name: str):
    return json.loads((ROOT / "data" / name).read_text())


def named(slot) -> bool:
    return isinstance(slot, str)


def tag(name) -> str:
    if not isinstance(name, str):
        return "待定"
    return TAG.get(name, name)


def need_wins(fmt: str) -> int:
    return 3 if (fmt or "").lower() == "bo5" else 2


def p_series_from_score(p_map: float, wins_a: int, wins_b: int, need: int) -> float:
    @lru_cache(None)
    def p(a: int, b: int) -> float:
        if a >= need:
            return 1.0
        if b >= need:
            return 0.0
        return p_map * p(a + 1, b) + (1.0 - p_map) * p(a, b + 1)

    return p(wins_a, wins_b)


def find_sim(known: dict[str, dict], match: dict) -> dict | None:
    mid = match.get("id")
    if mid and mid in known:
        return known[mid]
    a, b = match.get("teamA"), match.get("teamB")
    if mid and named(a) and named(b):
        return known.get(f"{mid}__{a}__{b}") or known.get(f"{mid}__{b}__{a}")
    return None


def parse_score(match: dict) -> tuple[int, int]:
    raw = str(match.get("score") or "")
    if "-" in raw:
        left, right = raw.replace(":", "-").split("-", 1)
        try:
            return int(left.strip()), int(right.strip())
        except ValueError:
            pass
    return 0, 0


def load_live() -> dict:
    if not LIVE_PATH.exists():
        return {}
    try:
        return json.loads(LIVE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def apply_live_overlay(match: dict, live: dict) -> dict:
    """Use live.json series score so Game 2 briefing does not wait for ingest."""
    m = dict(match)
    row = (live.get("matches") or {}).get(m.get("id")) or {}
    live_score = row.get("score")
    if maps_played_score(live_score) >= maps_played_score(m.get("score")) and live_score:
        m["score"] = live_score
    ids = []
    for mid in [*(m.get("matchIds") or []), *(row.get("matchIds") or [])]:
        s = str(mid) if mid else ""
        if s and s not in ids:
            ids.append(s)
    if ids:
        m["matchIds"] = ids
    if row.get("maps"):
        m["liveMaps"] = row["maps"]
    wins_a, wins_b = parse_score(m)
    if wins_a + wins_b:
        m["mapsPlayed"] = wins_a + wins_b
        if m.get("status") == "scheduled":
            m["status"] = "live"
    return m


def maps_played_score(score) -> int:
    a, b = parse_score({"score": score})
    return a + b


def winner_of_played_map(match: dict, n: int) -> str | None:
    a, b = match.get("teamA"), match.get("teamB")
    for row in match.get("liveMaps") or []:
        if int(row.get("n") or 0) == n and row.get("winner") in (1, 2):
            return a if row["winner"] == 1 else b
    wins_a, wins_b = parse_score(match)
    if n == 1 and wins_a + wins_b == 1:
        return a if wins_a == 1 else b
    return None


def short_why(sim: dict | None) -> str:
    w = (sim or {}).get("why") or ""
    return w.replace("H2H 0 局", "本届没交过手").replace("常用中单 ", "中单爱拿 ")


def market_prices(poly: dict | None, key: str) -> dict | None:
    row = (poly or {}).get(key) or {}
    outcomes = row.get("outcomes") or []
    prices = [float(x) for x in (row.get("prices") or [])]
    if len(outcomes) != 2 or len(prices) != 2:
        return None
    return {"outcomes": outcomes, "prices": [round(prices[0], 3), round(prices[1], 3)]}


def lean_from_p(team_a: str, team_b: str, p_a: float | None, market: dict | None, why: str = "") -> dict | None:
    if p_a is None or not named(team_a) or not named(team_b):
        return None
    p_a = float(p_a)
    lean_a = p_a >= 0.5
    lean = team_a if lean_a else team_b
    p_lean = p_a if lean_a else 1 - p_a
    return {
        "team": lean,
        "tag": tag(lean),
        "p": round(p_lean, 3),
        "pA": round(p_a, 3),
        "pB": round(1 - p_a, 3),
        "breakEven": round(1 / p_lean, 2) if p_lean else None,
        "market": market,
        "why": why,
    }


def playoff_maps(games: list[dict]) -> list[dict]:
    start = PLAYOFF_START.timestamp()
    out = []
    for g in games:
        if g.get("source") == "ewc":
            continue
        if int(g.get("start_time") or 0) < start:
            continue
        out.append(g)
    return sorted(out, key=lambda g: g.get("start_time") or 0)


def maps_for_match(match: dict, games: list[dict]) -> list[dict]:
    a, b = match.get("teamA"), match.get("teamB")
    if not (named(a) and named(b)):
        return []
    ids = match.get("matchIds") or []
    if ids:
        by_id = {str(g.get("match_id")): g for g in games if g.get("match_id") is not None}
        return [by_id[str(i)] for i in ids if str(i) in by_id]
    pair = {a, b}
    return [g for g in playoff_maps(games) if {g.get("radiant"), g.get("dire")} == pair]


def f10_name(game: dict) -> str | None:
    f = game.get("f10k") or {}
    side = f.get("side")
    if side == "radiant":
        return game.get("radiant")
    if side == "dire":
        return game.get("dire")
    return None


def pick_names(draft_side) -> list[str]:
    return [x.get("hero") for x in (draft_side or {}).get("picks") or [] if x.get("hero")]


def pack_map(game: dict, n: int) -> dict:
    draft = game.get("draft") or {}
    sides = game.get("sides") or {}
    rad, dire = game.get("radiant"), game.get("dire")
    f10 = game.get("f10k") or {}
    return {
        "game": n,
        "matchId": game.get("match_id"),
        "winner": game.get("winner"),
        "score": game.get("score"),
        "f10": f10_name(game),
        "f10Time": f10.get("time"),
        "durationMin": round((game.get("duration") or 0) / 60, 1) if game.get("duration") else None,
        "pace": game.get("pace"),
        "stance": game.get("stance"),
        "picks": {
            rad: pick_names(draft.get("radiant")),
            dire: pick_names(draft.get("dire")),
        }
        if rad and dire
        else {},
        "mid": {
            rad: ((sides.get("radiant") or {}).get("mid") or {}).get("hero"),
            dire: ((sides.get("dire") or {}).get("mid") or {}).get("hero"),
        }
        if rad and dire
        else {},
        "blurb": (game.get("blurb") or {}).get("f10k"),
    }


def pack_live_map(match: dict, live_row: dict, n: int) -> dict:
    ids = [str(x) for x in (live_row.get("matchIds") or match.get("matchIds") or []) if x]
    mp = next((row for row in live_row.get("maps") or [] if int(row.get("n") or 0) == n), None) or {}
    winner = None
    if mp.get("winner") in (1, 2):
        winner = match.get("teamA") if mp["winner"] == 1 else match.get("teamB")
    elif n == 1:
        winner = winner_of_played_map(match, 1)
    return {
        "game": n,
        "matchId": ids[n - 1] if len(ids) >= n else (ids[0] if ids else None),
        "winner": winner,
        "score": None,
        "f10": None,
        "durationMin": None,
        "length": mp.get("length"),
        "heroesA": mp.get("heroes1") or [],
        "heroesB": mp.get("heroes2") or [],
    }


def next_upcoming(packed_matches: list[dict]) -> dict | None:
    for m in sorted(packed_matches, key=lambda x: x.get("when") or ""):
        if m.get("status") not in {"completed", "complete"}:
            return m
    return None


def side_label(slot) -> str:
    if named(slot):
        return slot
    kind = "胜者" if (slot or {}).get("as") == "winner" else "败者"
    return f"{(slot or {}).get('from') or '?'} {kind}"


def pack_match(match: dict) -> dict:
    a, b = match.get("teamA"), match.get("teamB")
    return {
        "id": match.get("id"),
        "round": match.get("round"),
        "day": match.get("day"),
        "when": match.get("datetime"),
        "format": match.get("format") or "Bo3",
        "teamA": a if named(a) else None,
        "teamB": b if named(b) else None,
        "teamALabel": a if named(a) else side_label(a),
        "teamBLabel": b if named(b) else side_label(b),
        "status": match.get("status"),
        "score": match.get("score"),
        "winner": match.get("winner"),
        "polySlug": match.get("polySlug"),
        "mapsPlayed": match.get("mapsPlayed") or 0,
    }


def map_model(sim: dict | None, game_n: int) -> dict | None:
    maps = (sim or {}).get("maps") or []
    for row in maps:
        if row.get("game") == game_n:
            return row
    if maps and game_n - 1 < len(maps):
        return maps[game_n - 1]
    return maps[0] if maps else None


def main() -> None:
    playoffs = load("playoffs.json")
    sims = load("simulations.json")
    games = load("games.json").get("games") or []
    live = load_live()
    known = {item["id"]: item for item in sims.get("known") or [] if item.get("id")}
    matches = [apply_live_overlay(m, live) for m in playoffs.get("matches") or []]
    packed = [pack_match(m) for m in matches]
    now = datetime.now(CST)

    prev_map = None
    previous_maps: list[dict] = []
    next_map = None
    series_lean = None
    prev_series = None
    nxt_series = next_upcoming(packed)
    kind = "preview"
    focus = None

    live_or_open = [
        m
        for m in matches
        if named(m.get("teamA"))
        and named(m.get("teamB"))
        and m.get("status") in {"live", "scheduled"}
    ]
    live_or_open.sort(key=lambda m: m.get("datetime") or "")
    completed = [m for m in matches if m.get("status") in {"completed", "complete"} and m.get("winner")]
    completed.sort(key=lambda m: m.get("datetime") or "")

    focus_match = None
    for m in live_or_open:
        if maps_for_match(m, games) or m.get("status") == "live" or parse_score(m) != (0, 0):
            focus_match = m
            break
    if focus_match is None and live_or_open:
        focus_match = live_or_open[0]
    if focus_match is None and completed:
        focus_match = completed[-1]

    if focus_match:
        focus = pack_match(focus_match)
        sim = find_sim(known, focus_match)
        a, b = focus_match.get("teamA"), focus_match.get("teamB")
        wins_a, wins_b = parse_score(focus_match)
        played = wins_a + wins_b or len(maps_for_match(focus_match, games))
        need = need_wins(focus_match.get("format") or "Bo3")
        done = focus_match.get("status") in {"completed", "complete"} or max(wins_a, wins_b) >= need
        rows = maps_for_match(focus_match, games)
        live_row = (live.get("matches") or {}).get(focus_match.get("id")) or {}
        if rows:
            previous_maps = [pack_map(g, i + 1) for i, g in enumerate(rows)]
            prev_map = previous_maps[-1]
        elif played:
            previous_maps = [pack_live_map(focus_match, live_row, n) for n in range(1, played + 1)]
            prev_map = previous_maps[-1]
        p_map = float((sim or {}).get("pMapA") or 0.5)
        p_series = p_series_from_score(p_map, wins_a, wins_b, need) if not done else None
        series_lean = lean_from_p(a, b, p_series if p_series is not None else (sim or {}).get("series", {}).get("pSeriesA"), market_prices((sim or {}).get("poly"), "series"), short_why(sim))
        if not done:
            kind = "next-map" if played else "preview"
            nxt_n = played + 1
            model = map_model(sim, nxt_n) or {}
            next_map = {
                "game": nxt_n,
                "teamA": a,
                "teamB": b,
                "lean": lean_from_p(
                    a,
                    b,
                    model.get("pWinA"),
                    market_prices((sim or {}).get("poly"), f"g{nxt_n}"),
                    short_why(sim),
                ),
                "f10": lean_from_p(a, b, model.get("pF10A"), None),
            }
            nxt_series = pack_match(focus_match)
            nxt_series["lean"] = series_lean
        else:
            kind = "next-series"
            prev_series = pack_match(focus_match)
            prev_series["lean"] = series_lean
            nxt = next_upcoming(packed)
            nxt_series = nxt
            if nxt and nxt.get("teamA") and nxt.get("teamB"):
                src = next((row for row in matches if row.get("id") == nxt["id"]), None)
                nsim = find_sim(known, src) if src else None
                nxt["lean"] = lean_from_p(
                    nxt["teamA"],
                    nxt["teamB"],
                    (nsim or {}).get("series", {}).get("pSeriesA"),
                    market_prices((nsim or {}).get("poly"), "series"),
                    short_why(nsim),
                )
                next_map = {
                    "game": 1,
                    "teamA": nxt["teamA"],
                    "teamB": nxt["teamB"],
                    "lean": lean_from_p(
                        nxt["teamA"],
                        nxt["teamB"],
                        (map_model(nsim, 1) or {}).get("pWinA"),
                        market_prices((nsim or {}).get("poly"), "g1"),
                        short_why(nsim),
                    ),
                    "f10": lean_from_p(nxt["teamA"], nxt["teamB"], (map_model(nsim, 1) or {}).get("pF10A"), None),
                }

    map_ids = [g.get("match_id") for g in playoff_maps(games) if g.get("match_id")]
    prev_state = {}
    if STATE_PATH.exists():
        prev_state = json.loads(STATE_PATH.read_text())
    seen = [x for x in (prev_state.get("mapIds") or [])]
    new_ids = [i for i in map_ids if i not in seen]

    headline, narrative = compose(kind, prev_map, next_map, series_lean, prev_series, nxt_series)
    payload = {
        "asOf": now.strftime("%Y-%m-%d %H:%M") + " CST",
        "timezone": "Asia/Shanghai",
        "kind": kind,
        "headline": headline,
        "narrative": narrative,
        "previousMap": prev_map,
        "previousMaps": previous_maps,
        "nextMap": next_map,
        "seriesLean": series_lean,
        "previous": prev_series,
        "next": nxt_series,
        "focus": focus,
        "todayResults": [
            pack_match(m)
            for m in matches
            if m.get("day") == now.strftime("%Y-%m-%d") and m.get("status") in {"completed", "complete"}
        ],
        "newMapIds": new_ids,
    }
    out = ROOT / "web" / "data" / "daily.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "web" / "data" / "daily.md").write_text(f"# TI15 局间战报 · {payload['asOf']}\n\n{headline}\n\n{narrative}\n")
    prev_state = dict(prev_state)
    prev_state["mapIds"] = map_ids
    prev_state["lastReason"] = headline
    prev_state["asOf"] = payload["asOf"]
    STATE_PATH.write_text(json.dumps(prev_state, ensure_ascii=False, indent=2) + "\n")
    print("wrote", out, "kind", kind, "newMaps", new_ids, "headline", headline)


def compose(kind, prev_map, next_map, series_lean, prev_series, nxt_series) -> tuple[str, str]:
    bits = []
    if prev_map and prev_map.get("winner"):
        f10 = f"，先到10杀 {tag(prev_map['f10'])}" if prev_map.get("f10") else ""
        dur = f"，{prev_map['durationMin']}分钟" if prev_map.get("durationMin") else ""
        bits.append(f"第{prev_map['game']}局 {tag(prev_map['winner'])} 赢了{f10}{dur}。")
        picks = prev_map.get("picks") or {}
        if picks:
            parts = []
            for team, heroes in picks.items():
                if heroes:
                    parts.append(f"{tag(team)} {'、'.join(heroes[:3])}")
            if parts:
                bits.append("上一局阵容 " + " / ".join(parts) + "。")
    if kind == "next-map" and next_map and next_map.get("lean"):
        lean = next_map["lean"]
        be = f"现场赔率至少 {lean['breakEven']}。" if lean.get("breakEven") else ""
        bits.append(f"下一局第{next_map['game']}局按上一局重算后看好 {lean['tag']}（{round(lean['p'] * 100)}%）。{be}")
        if series_lean:
            bits.append(f"系列现在看好 {series_lean['tag']}（{round(series_lean['p'] * 100)}%）。")
        if next_map.get("f10"):
            bits.append(f"先到10杀看好 {next_map['f10']['tag']}。")
    elif nxt_series and nxt_series.get("lean"):
        lean = nxt_series["lean"]
        extra = ""
        if prev_series and prev_series.get("winner"):
            extra = f"上一把 {tag(prev_series['winner'])} {prev_series.get('score') or ''}。"
        bits.append(
            extra
            + f"下一把 {tag(nxt_series.get('teamA'))} vs {tag(nxt_series.get('teamB'))}，看好 {lean['tag']}（系列 {round(lean['p'] * 100)}%）。"
        )
        if next_map and next_map.get("lean"):
            bits.append(f"第1局看好 {next_map['lean']['tag']}（{round(next_map['lean']['p'] * 100)}%）。")
    elif nxt_series:
        bits.append(
            f"下一把 {nxt_series.get('when','')[11:16]} {nxt_series.get('round') or ''} "
            f"{nxt_series.get('teamALabel') or '待定'} vs {nxt_series.get('teamBLabel') or '待定'}。"
        )
    else:
        bits.append("淘汰赛还没开打。局一打完会写下局看好谁。")
    why = ""
    if next_map and next_map.get("lean") and next_map["lean"].get("why"):
        why = next_map["lean"]["why"]
        if why and not why.endswith("。"):
            why += "。"
    headline_bits = [b for b in bits if not b.startswith("上一局阵容")]
    headline = "".join(headline_bits[:2]) if headline_bits else "等待下一局。"
    narrative = "".join(bits) + why
    return headline, narrative


if __name__ == "__main__":
    assert abs(p_series_from_score(0.5, 0, 0, 2) - 0.5) < 1e-9
    assert abs(p_series_from_score(0.5, 1, 0, 2) - 0.75) < 1e-9
    assert abs(p_series_from_score(0.5, 0, 1, 2) - 0.25) < 1e-9
    main()
