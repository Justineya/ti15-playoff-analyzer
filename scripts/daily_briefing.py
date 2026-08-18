#!/usr/bin/env python3
"""Write today's results + next-match lean to web/data/daily.json."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
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


def short_why(sim: dict | None) -> str:
    w = (sim or {}).get("why") or ""
    return (
        w.replace("H2H 0 局", "本届没交过手")
        .replace("常用中单 ", "中单爱拿 ")
    )


def find_sim(known: dict[str, dict], match: dict) -> dict | None:
    mid = match.get("id")
    if mid and mid in known:
        return known[mid]
    a, b = match.get("teamA"), match.get("teamB")
    if mid and named(a) and named(b):
        return known.get(f"{mid}__{a}__{b}") or known.get(f"{mid}__{b}__{a}")
    return None


def series_prices(sim: dict | None) -> dict | None:
    poly = (sim or {}).get("poly") or {}
    series = poly.get("series") or {}
    outcomes = series.get("outcomes") or []
    prices = [float(x) for x in (series.get("prices") or [])]
    if len(outcomes) != 2 or len(prices) != 2:
        return None
    return {"outcomes": outcomes, "prices": [round(prices[0], 3), round(prices[1], 3)]}


def lean_block(sim: dict | None, team_a: str | None, team_b: str | None) -> dict | None:
    if not (named(team_a) and named(team_b) and sim):
        return None
    p_a = (sim.get("series") or {}).get("pSeriesA")
    if p_a is None:
        return None
    p_a = float(p_a)
    lean_a = p_a >= 0.5
    lean = team_a if lean_a else team_b
    p_lean = p_a if lean_a else 1 - p_a
    f10_a = sim.get("pF10A")
    f10_lean = None
    if f10_a is not None:
        f10_lean = team_a if float(f10_a) >= 0.5 else team_b
    return {
        "team": lean,
        "tag": tag(lean),
        "p": round(p_lean, 3),
        "pA": round(p_a, 3),
        "pB": round(1 - p_a, 3),
        "breakEven": round(1 / p_lean, 2) if p_lean else None,
        "f10Team": f10_lean,
        "f10A": round(float(f10_a), 3) if f10_a is not None else None,
        "market": series_prices(sim),
        "why": short_why(sim),
    }


def pack_match(match: dict, sim: dict | None) -> dict:
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
        "lean": lean_block(sim, a if named(a) else None, b if named(b) else None),
    }


def side_label(slot) -> str:
    if named(slot):
        return slot
    kind = "胜者" if (slot or {}).get("as") == "winner" else "败者"
    return f"{(slot or {}).get('from') or '?'} {kind}"


def done(match: dict) -> bool:
    return match.get("status") in {"completed", "complete"}


def upcoming(match: dict) -> bool:
    return match.get("status") not in {"completed", "complete"}


def day_label(playoffs: dict, day: str) -> str:
    for row in playoffs.get("days") or []:
        if row.get("date") == day:
            return row.get("label") or day
    return day


def headline(prev: dict | None, nxt: dict | None, today: str, today_results: list[dict]) -> str:
    if prev and nxt and nxt.get("teamA") and nxt.get("teamB") and nxt.get("lean"):
        return (
            f"上一把 {tag(prev['winner'])} 赢了 {prev.get('score') or ''}。"
            f"下一把 {tag(nxt['teamA'])} vs {tag(nxt['teamB'])}，"
            f"看好 {nxt['lean']['tag']}（{round(nxt['lean']['p'] * 100)}%）。"
        )
    if nxt and nxt.get("teamA") and nxt.get("teamB") and nxt.get("lean"):
        prefix = "还没打完。" if (today_results or prev) else "还没开打。"
        return (
            f"{prefix}下一把 {tag(nxt['teamA'])} vs {tag(nxt['teamB'])}，"
            f"看好 {nxt['lean']['tag']}（{round(nxt['lean']['p'] * 100)}%）。"
        )
    if today_results:
        bits = [
            f"{tag(r['winner'])} {r.get('score') or ''}"
            for r in today_results
            if r.get("winner")
        ]
        return f"{today[5:].replace('-', '/')} 已打：{' · '.join(bits) or '赛果写入中'}。"
    return "淘汰赛还没开打。下一把看好谁会写在这里。"


def narrative(
    prev: dict | None,
    nxt: dict | None,
    today_results: list[dict],
    tomorrow: list[dict],
    include_tomorrow: bool,
) -> str:
    lines = []
    if today_results:
        bits = []
        for r in today_results:
            if r.get("winner") and named(r.get("teamA")) and named(r.get("teamB")):
                bits.append(f"{tag(r['teamA'])} vs {tag(r['teamB'])} {r.get('score') or ''}，{tag(r['winner'])} 赢")
            elif named(r.get("teamA")) and named(r.get("teamB")):
                bits.append(f"{tag(r['teamA'])} vs {tag(r['teamB'])} {r.get('status')}")
        if bits:
            lines.append("今天：" + "；".join(bits) + "。")
    if prev and prev.get("winner"):
        lines.append(
            f"上一把 {prev.get('round') or ''} {tag(prev.get('teamA'))} vs {tag(prev.get('teamB'))}，"
            f"{tag(prev['winner'])} {prev.get('score') or ''} 拿下。"
        )
    if nxt:
        a, b = nxt.get("teamA"), nxt.get("teamB")
        lean = nxt.get("lean") or {}
        when = (nxt.get("when") or "")[11:16]
        if named(a) and named(b) and lean.get("team"):
            be = lean.get("breakEven")
            extra = f"现场赔率至少 {be} 再买。" if be else ""
            why = lean.get("why") or ""
            if why and not why.endswith("。"):
                why += "。"
            lines.append(
                f"下一把 {when} {nxt.get('round') or ''} {tag(a)} vs {tag(b)}，"
                f"模型看好 {lean.get('tag')}（系列 {round(lean['p'] * 100)}%）。{extra}{why}"
            )
        else:
            lines.append(
                f"下一把 {when} {nxt.get('round') or ''} {nxt.get('teamALabel') or '待定'} vs {nxt.get('teamBLabel') or '待定'}，对阵还没出来。"
            )
    if include_tomorrow and tomorrow:
        names = []
        for m in tomorrow:
            clock = (m.get("when") or "")[11:16]
            if m.get("teamA") and m.get("teamB") and m.get("lean"):
                names.append(f"{clock} {tag(m['teamA'])}/{tag(m['teamB'])} 看好 {m['lean']['tag']}")
            else:
                names.append(f"{clock} {m.get('teamALabel') or '待定'} vs {m.get('teamBLabel') or '待定'}")
        if names:
            lines.append("明天：" + "；".join(names) + "。")
    return "".join(lines) or "赛果和下一把预测会在每天收工后写进这里。"


def main() -> None:
    playoffs = load("playoffs.json")
    sims = load("simulations.json")
    known = {item["id"]: item for item in sims.get("known") or [] if item.get("id")}
    matches = list(playoffs.get("matches") or [])
    packed = [pack_match(m, find_sim(known, m)) for m in matches]

    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")
    days = [d.get("date") for d in playoffs.get("days") or [] if d.get("date")]
    playoff_day = today if today in days else None
    if playoff_day is None:
        future = [d for d in days if d >= today]
        playoff_day = future[0] if future else (days[-1] if days else today)
    tomorrow_date = (datetime.strptime(playoff_day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    today_results = [p for p in packed if p.get("day") == playoff_day and done(p)]
    today_results.sort(key=lambda m: m.get("when") or "")
    tomorrow = [p for p in packed if p.get("day") == tomorrow_date]
    tomorrow.sort(key=lambda m: m.get("when") or "")

    completed = [p for p in packed if done(p)]
    completed.sort(key=lambda m: m.get("when") or "")
    prev = completed[-1] if completed else None

    nxt = None
    for p in sorted(packed, key=lambda m: m.get("when") or ""):
        if upcoming(p):
            nxt = p
            break
    if nxt is None and tomorrow:
        nxt = tomorrow[0]

    payload = {
        "asOf": now.strftime("%Y-%m-%d %H:%M") + " CST",
        "timezone": "Asia/Shanghai",
        "playoffDay": playoff_day,
        "playoffDayLabel": day_label(playoffs, playoff_day),
        "headline": headline(prev, nxt, playoff_day, today_results),
        "narrative": narrative(prev, nxt, today_results, tomorrow, playoff_day == today),
        "previous": prev,
        "next": nxt,
        "todayResults": today_results,
        "tomorrow": tomorrow,
    }
    out = ROOT / "web" / "data" / "daily.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    md = ROOT / "web" / "data" / "daily.md"
    md.write_text(
        f"# TI15 收工战报 · {payload['asOf']}\n\n"
        f"{payload['headline']}\n\n"
        f"{payload['narrative']}\n"
    )
    print("wrote", out, "headline", payload["headline"])


if __name__ == "__main__":
    main()
