#!/usr/bin/env python3
"""Fill playoff feeder slots from completed TI15 maps and Liquipedia scores."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
PLAYOFF_START = datetime(2026, 8, 20, 0, 0, tzinfo=CST)
LIVE_PATH = ROOT / "web" / "data" / "live.json"


def parse_score(score) -> tuple[int, int]:
    raw = str(score or "")
    hit = raw.replace(":", "-").split("-", 1)
    if len(hit) != 2:
        return 0, 0
    try:
        return int(hit[0].strip()), int(hit[1].strip())
    except ValueError:
        return 0, 0


def merge_ids(*groups) -> list:
    out = []
    seen: set[str] = set()
    for group in groups:
        for value in group or []:
            key = str(value).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(int(key) if key.isdigit() else key)
    return out


def need_wins(fmt: str) -> int:
    return 3 if (fmt or "").lower() == "bo5" else 2


def pair_key(a, b) -> frozenset:
    return frozenset({a, b})


def parse_kickoff(dt) -> float | None:
    raw = str(dt or "").strip()
    if not raw:
        return None
    if len(raw) == 16:
        raw += ":00"
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST).timestamp()
    except ValueError:
        return None


def maps_for_series(match: dict, pool: list[dict], matches: list[dict]) -> list[dict]:
    """Same two teams can play twice (ubsf then GF). Split by kickoff, not all H2H maps."""
    a, b = match.get("teamA"), match.get("teamB")
    start = parse_kickoff(match.get("datetime"))
    later = []
    for other in matches:
        if other.get("id") == match.get("id"):
            continue
        oa, ob = other.get("teamA"), other.get("teamB")
        if not (isinstance(oa, str) and isinstance(ob, str)):
            continue
        if pair_key(oa, ob) != pair_key(a, b):
            continue
        t = parse_kickoff(other.get("datetime"))
        if start is not None and t is not None and t > start:
            later.append(t)
    end = min(later) if later else None
    out = []
    for g in pool:
        st = int(g.get("start_time") or 0)
        if start is not None and st < start - 2 * 3600:
            continue
        if end is not None and st >= end:
            continue
        out.append(g)
    return out


def playoff_games(games: list[dict]) -> list[dict]:
    start = PLAYOFF_START.timestamp()
    out = []
    for g in games:
        if g.get("source") == "ewc":
            continue
        if int(g.get("start_time") or 0) < start:
            continue
        out.append(g)
    return sorted(out, key=lambda g: g.get("start_time") or 0)


def series_result(maps: list[dict], team_a: str, team_b: str, fmt: str) -> dict:
    wins = {team_a: 0, team_b: 0}
    ids = []
    for g in maps:
        w = g.get("winner")
        if w in wins:
            wins[w] += 1
            ids.append(g.get("match_id"))
        if max(wins.values()) >= need_wins(fmt):
            break
    leader = team_a if wins[team_a] >= wins[team_b] else team_b
    done = max(wins.values()) >= need_wins(fmt)
    winner = leader if done else None
    loser = ({team_a, team_b} - {winner}).pop() if winner else None
    return {
        "wins": wins,
        "score": f"{wins[team_a]}-{wins[team_b]}",
        "mapsPlayed": sum(wins.values()),
        "matchIds": ids,
        "winner": winner,
        "loser": loser,
        "status": "completed" if done else ("live" if sum(wins.values()) else "scheduled"),
    }


def resolve_slot(slot, by_id: dict):
    if isinstance(slot, str):
        return slot
    src = by_id.get(slot.get("from") or "")
    if not src:
        return slot
    key = "winner" if slot.get("as") == "winner" else "loser"
    name = src.get(key)
    return name if isinstance(name, str) and name else slot


def fill_feeders(matches: list[dict]) -> bool:
    by_id = {m["id"]: m for m in matches}
    changed = False
    for m in matches:
        a = resolve_slot(m.get("teamA"), by_id)
        b = resolve_slot(m.get("teamB"), by_id)
        if a != m.get("teamA"):
            m["teamA"] = a
            changed = True
        if b != m.get("teamB"):
            m["teamB"] = b
            changed = True
        if isinstance(m.get("teamA"), str) and isinstance(m.get("teamB"), str):
            m["polyTitle"] = f"{m['teamA']} vs {m['teamB']}"
            if m.get("status") == "awaiting":
                m["status"] = "scheduled"
                changed = True
    return changed


def apply_live_results(matches: list[dict], live: dict) -> bool:
    """Liquipedia 2-1 can fill tomorrow's feeders before OpenDota parses Game 3."""
    rows = live.get("matches") or {}
    changed = False
    for m in matches:
        a, b = m.get("teamA"), m.get("teamB")
        if not (isinstance(a, str) and isinstance(b, str)):
            continue
        row = rows.get(m.get("id")) or {}
        score = row.get("score")
        wins_a, wins_b = parse_score(score)
        played = wins_a + wins_b
        if not played:
            continue
        need = need_wins(m.get("format") or "Bo3")
        have = int(m.get("mapsPlayed") or 0)
        if played < have:
            continue
        if m.get("status") in {"completed", "complete"} and m.get("winner"):
            have = int(m.get("mapsPlayed") or 0)
            if played <= have:
                continue
            if max(wins_a, wins_b) < need:
                continue
        before = (m.get("winner"), m.get("score"), m.get("status"), m.get("mapsPlayed"))
        m["score"] = f"{wins_a}-{wins_b}"
        m["mapsPlayed"] = played
        ids = merge_ids(m.get("matchIds"), row.get("matchIds"))
        if ids:
            m["matchIds"] = ids
        if max(wins_a, wins_b) >= need:
            m["winner"] = a if wins_a >= need else b
            m["loser"] = b if m["winner"] == a else a
            m["status"] = "completed"
        else:
            m["status"] = "live"
            m.pop("winner", None)
            m.pop("loser", None)
        after = (m.get("winner"), m.get("score"), m.get("status"), m.get("mapsPlayed"))
        if before != after:
            changed = True
    return changed


def apply_results(matches: list[dict], games: list[dict]) -> bool:
    indexed: dict[frozenset, list[dict]] = {}
    for g in playoff_games(games):
        key = pair_key(g["radiant"], g["dire"])
        indexed.setdefault(key, []).append(g)
    changed = False
    for m in matches:
        a, b = m.get("teamA"), m.get("teamB")
        if not (isinstance(a, str) and isinstance(b, str)):
            continue
        maps = maps_for_series(m, indexed.get(pair_key(a, b) or frozenset(), []), matches)
        if not maps:
            continue
        res = series_result(maps, a, b, m.get("format") or "Bo3")
        before = (m.get("winner"), m.get("score"), m.get("status"), m.get("mapsPlayed"))
        m["mapsPlayed"] = res["mapsPlayed"]
        m["score"] = res["score"]
        m["matchIds"] = res["matchIds"]
        if res["winner"]:
            m["winner"] = res["winner"]
            m["loser"] = res["loser"]
            m["status"] = "completed"
        else:
            m["status"] = res["status"]
            m.pop("winner", None)
            m.pop("loser", None)
        after = (m.get("winner"), m.get("score"), m.get("status"), m.get("mapsPlayed"))
        if before != after:
            changed = True
    return changed


def main() -> None:
    po_path = ROOT / "data" / "playoffs.json"
    games_path = ROOT / "data" / "games.json"
    games = json.loads(games_path.read_text()).get("games") or [] if games_path.exists() else []
    live = json.loads(LIVE_PATH.read_text()) if LIVE_PATH.exists() else {}
    playoffs = json.loads(po_path.read_text())
    matches = playoffs.get("matches") or []
    changed = False
    for _ in range(8):
        step = apply_results(matches, games)
        step = apply_live_results(matches, live) or step
        step = fill_feeders(matches) or step
        changed = changed or step
        if not step:
            break
    if changed:
        playoffs["asOf"] = datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST"
        po_path.write_text(json.dumps(playoffs, ensure_ascii=False, indent=2) + "\n")
    done = [m["id"] for m in matches if m.get("status") == "completed"]
    live_ids = [m["id"] for m in matches if m.get("status") == "live"]
    known = [m["id"] for m in matches if isinstance(m.get("teamA"), str) and isinstance(m.get("teamB"), str)]
    print("bracket completed", done, "live", live_ids, "named", known, "changed", changed)


if __name__ == "__main__":
    main()
