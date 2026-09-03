#!/usr/bin/env python3
"""Pull one player's ranked games from OpenDota into web/data/player.json."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "player" / "config.json"
STATE_PATH = ROOT / "data" / "player" / "seen.json"
OUT_PATH = ROOT / "web" / "data" / "player.json"
LAUNCH_PATH = ROOT / "data" / "player-launch.json"
HEROES_PATH = ROOT / "data" / "heroes.json"
CST = timezone(timedelta(hours=8))
UA = {
    "User-Agent": (
        "TI15PlayoffAnalyzer/player-scout "
        "(https://github.com/Justineya/ti15-playoff-analyzer; personal ranked ingest)"
    )
}
API = "https://api.opendota.com/api"
ROLE = {1: "pos1", 2: "pos2", 3: "pos3", 4: "pos4", 5: "pos5"}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def dump(path: Path, blob) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, ensure_ascii=False, indent=2) + "\n")


def get_json(url: str, retries: int = 5):
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            time.sleep(8 if e.code == 429 else 1.5 + i)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 + i)
    raise RuntimeError(f"GET failed {url}: {last}")


def hero_names() -> dict[int, str]:
    rows = load_json(HEROES_PATH, [])
    out = {}
    for row in rows:
        hid = row.get("id")
        name = row.get("localized_name")
        if hid and name:
            out[int(hid)] = name
    return out


def hero_files() -> dict[int, str]:
    out = {}
    for row in load_json(HEROES_PATH, []):
        hid = row.get("id")
        name = str(row.get("name") or "")
        if hid and name.startswith("npc_dota_hero_"):
            out[int(hid)] = name.replace("npc_dota_hero_", "", 1)
    return out


def won(row: dict) -> bool:
    slot = int(row.get("player_slot") or 0)
    return bool(row.get("radiant_win")) == (slot < 128)


def pct_bracket(benchmarks: dict, key: str):
    raw = (benchmarks or {}).get(key) or {}
    return raw.get("pct_bracket")


def t_at(series, minute: int):
    if not series or len(series) <= minute:
        return None
    return series[minute]


def first_item(purch: list, names: set[str]):
    for ev in purch or []:
        if ev.get("key") in names:
            return ev.get("time")
    return None


def extract_player(match: dict, account_id: int, names: dict[int, str], files: dict[int, str] | None = None) -> dict | None:
    me = next((p for p in (match.get("players") or []) if p.get("account_id") == account_id), None)
    if not me:
        return None
    lane_role = me.get("lane_role")
    purch = me.get("purchase_log") or []
    bm = me.get("benchmarks") or {}
    start = int(match.get("start_time") or 0)
    duration = int(match.get("duration") or 0)
    is_rad = int(me.get("player_slot") or 0) < 128
    hid = int(me.get("hero_id") or 0)
    files = files or {}
    return {
        "matchId": match.get("match_id"),
        "when": datetime.fromtimestamp(start, CST).strftime("%Y-%m-%d %H:%M") if start else "",
        "startTime": start,
        "durationMin": round(duration / 60, 1) if duration else None,
        "win": bool(match.get("radiant_win")) == is_rad,
        "hero": names.get(hid, str(me.get("hero_id"))),
        "heroId": me.get("hero_id"),
        "heroFile": files.get(hid),
        "role": ROLE.get(lane_role) or (None if lane_role in (None, 0) else f"pos{lane_role}"),
        "laneRole": lane_role,
        "partySize": me.get("party_size") or match.get("party_size") or 1,
        "kills": me.get("kills"),
        "deaths": me.get("deaths"),
        "assists": me.get("assists"),
        "gpm": me.get("gold_per_min"),
        "xpm": me.get("xp_per_min"),
        "lastHits": me.get("last_hits"),
        "laneEfficiency": me.get("lane_efficiency"),
        "towerDamage": me.get("tower_damage"),
        "heroDamage": me.get("hero_damage"),
        "teamfight": me.get("teamfight_participation"),
        "lh10": t_at(me.get("lh_t"), 10),
        "gold10": t_at(me.get("gold_t"), 10),
        "parsed": bool(match.get("version")),
        "gpmBr": pct_bracket(bm, "gold_per_min"),
        "xpmBr": pct_bracket(bm, "xp_per_min"),
        "deathsBr": pct_bracket(bm, "deaths_per_min"),
        "lhBr": pct_bracket(bm, "last_hits_per_min"),
        "damageBr": pct_bracket(bm, "hero_damage_per_min"),
        "towerBr": pct_bracket(bm, "tower_damage"),
        "boots": first_item(purch, {"boots", "power_treads", "phase_boots", "arcane_boots", "tranquil_boots", "travel_boots"}),
        "bkb": first_item(purch, {"black_king_bar"}),
        "opendota": f"https://www.opendota.com/matches/{match.get('match_id')}",
    }


def divine_wr(hero_stats: list, hero_id: int) -> dict | None:
    row = next((h for h in hero_stats if h.get("id") == hero_id), None)
    if not row:
        return None
    picks = int(row.get("7_pick") or 0)
    wins = int(row.get("7_win") or 0)
    if picks <= 0:
        return None
    return {"picks": picks, "wins": wins, "wr": round(wins / picks, 4)}


def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def summarize(games: list[dict], hero_stats: list) -> dict:
    roles = defaultdict(lambda: {"games": 0, "wins": 0})
    heroes = defaultdict(lambda: {"games": 0, "wins": 0, "roles": Counter()})
    party = defaultdict(lambda: {"games": 0, "wins": 0})
    for g in games:
        role = g.get("role") or "unknown"
        roles[role]["games"] += 1
        roles[role]["wins"] += int(bool(g.get("win")))
        heroes[g.get("hero") or "?"]["games"] += 1
        heroes[g.get("hero") or "?"]["wins"] += int(bool(g.get("win")))
        heroes[g.get("hero") or "?"]["roles"][role] += 1
        ps = int(g.get("partySize") or 1)
        party[str(ps)]["games"] += 1
        party[str(ps)]["wins"] += int(bool(g.get("win")))
    wins = [g for g in games if g.get("win")]
    losses = [g for g in games if not g.get("win")]
    hero_rows = []
    for name, s in sorted(heroes.items(), key=lambda kv: -kv[1]["games"]):
        hid = next((g.get("heroId") for g in games if g.get("hero") == name), None)
        meta = divine_wr(hero_stats, int(hid)) if hid else None
        hero_rows.append(
            {
                "hero": name,
                "games": s["games"],
                "wins": s["wins"],
                "roles": dict(s["roles"]),
                "divine": meta,
            }
        )
    return {
        "n": len(games),
        "wins": len(wins),
        "losses": len(losses),
        "wr": round(len(wins) / len(games), 3) if games else None,
        "roles": {k: v for k, v in sorted(roles.items())},
        "party": {k: v for k, v in sorted(party.items())},
        "heroes": hero_rows,
        "winAvg": {
            "laneEfficiency": avg(g.get("laneEfficiency") for g in wins),
            "gpmBr": avg(g.get("gpmBr") for g in wins),
            "towerBr": avg(g.get("towerBr") for g in wins),
            "deaths": avg(g.get("deaths") for g in wins),
        },
        "lossAvg": {
            "laneEfficiency": avg(g.get("laneEfficiency") for g in losses),
            "gpmBr": avg(g.get("gpmBr") for g in losses),
            "towerBr": avg(g.get("towerBr") for g in losses),
            "deaths": avg(g.get("deaths") for g in losses),
        },
    }


def classify_game(game: dict, divine: dict | None) -> str:
    wr = (divine or {}).get("wr")
    role = game.get("role")
    gpm_br = game.get("gpmBr")
    tower_br = game.get("towerBr")
    if game.get("win"):
        return "win"
    if wr is not None and wr <= 0.47:
        return "meta_weak"
    if role == "pos1" and gpm_br is not None and gpm_br < 0.2:
        return "wrong_role"
    if gpm_br is not None and gpm_br >= 0.8 and tower_br is not None and tower_br < 0.5:
        return "did_not_close"
    if gpm_br is not None and gpm_br < 0.4:
        return "farm_collapse"
    return "other_loss"


KIND_NOTE = {
    "meta_weak": "版本坑",
    "did_not_close": "没收",
    "wrong_role": "别打1",
    "farm_collapse": "金崩",
    "other_loss": "负",
    "win": "胜",
}


def wl(row: dict) -> str:
    g = int(row.get("games") or 0)
    w = int(row.get("wins") or 0)
    return f"{w}-{g - w}"


def avg_br(rows: list[dict], key: str):
    xs = [g.get(key) for g in rows if g.get(key) is not None]
    return (sum(xs) / len(xs)) if xs else None


def stub_points(games: list[dict], summary: dict, new_ids: list) -> list[str]:
    points: list[str] = []
    idset = {str(x) for x in (new_ids or [])}
    fresh = [g for g in games if str(g.get("matchId")) in idset]
    scope = fresh or games
    if fresh:
        w = sum(1 for g in fresh if g.get("win"))
        l = len(fresh) - w
        solo = all(int(g.get("partySize") or 1) == 1 for g in fresh)
        tag = "全单排 " if solo else ""
        points.append(f"新{len(fresh)}把{tag}{w}-{l}。")
        lost = [g for g in fresh if not g.get("win")]
        if lost:
            bits = []
            for g in lost[:4]:
                kind = classify_game(g, g.get("divine"))
                bits.append(f"{g.get('hero') or '?'}{KIND_NOTE.get(kind, '')}")
            points.append("负：" + "、".join(bits) + "。")
        won = [g for g in fresh if g.get("win")]
        if won:
            points.append("胜：" + "、".join((g.get("hero") or "?") for g in won[:4]) + "。")
    else:
        points.append(f"窗口 {summary.get('wins')}-{summary.get('losses')}。")
    wins = [g for g in scope if g.get("win")]
    losses = [g for g in scope if not g.get("win")]
    wg, wt = avg_br(wins, "gpmBr"), avg_br(wins, "towerBr")
    lg, lt = avg_br(losses, "gpmBr"), avg_br(losses, "towerBr")
    if wg is not None and lg is not None:
        points.append(
            f"这批胜场 GPM {wg:.0%}、推塔 {(wt or 0):.0%}；负场 {lg:.0%} / {(lt or 0):.0%}。"
        )
    return points[:6]


def stub_briefing(profile: dict, games: list[dict], summary: dict, new_ids: list, hero_stats: list) -> dict:
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST"
    roles = summary.get("roles") or {}
    pos2 = roles.get("pos2") or {}
    pos3 = roles.get("pos3") or {}
    bits = []
    if new_ids:
        bits.append(f"+{len(new_ids)}")
    bits.append(f"{summary.get('wins')}-{summary.get('losses')}")
    if pos2.get("games"):
        bits.append(f"中{wl(pos2)}")
    if pos3.get("games"):
        bits.append(f"3号{wl(pos3)}")
    focus = []
    idset = {str(x) for x in (new_ids or [])}
    scoped = [g for g in games if str(g.get("matchId")) in idset] if idset else games
    for g in scoped:
        if not idset and g.get("win"):
            continue
        meta = g.get("divine") or divine_wr(hero_stats, int(g.get("heroId") or 0))
        kind = classify_game(g, meta)
        focus.append(
            {
                "matchId": g.get("matchId"),
                "hero": g.get("hero"),
                "heroFile": g.get("heroFile"),
                "role": g.get("role"),
                "kind": kind,
                "divineWr": meta,
                "note": KIND_NOTE.get(kind, ""),
            }
        )
    points = stub_points(games, summary, new_ids)
    return {
        "asOf": now,
        "source": "stub",
        "headline": " ".join(bits),
        "lede": points[0] if points else "",
        "narrative": "",
        "positioning": "主中 · 副三",
        "points": points,
        "sessionMatchIds": list(new_ids or []),
        "newMatchIds": new_ids,
        "focus": focus[:6],
        "note": "页面用卡片 + 短诊断。有新图就只复盘这批。非投注建议。",
    }


def try_fetch(fetch, url: str, default):
    try:
        blob = fetch(url)
        return blob if blob is not None else default
    except Exception as err:  # noqa: BLE001
        print("optional fetch failed", url, err)
        return default


def ingest(fetch=get_json) -> dict:
    cfg = load_json(CONFIG_PATH, {})
    account_id = int(cfg.get("accountId") or 203557151)
    lobby = int(cfg.get("lobbyType") or 7)
    list_limit = int(cfg.get("listLimit") or 80)
    parse_limit = int(cfg.get("parseLimit") or 25)
    form_days = int(cfg.get("formDays") or 120)
    names = hero_names()
    files = hero_files()
    profile = try_fetch(fetch, f"{API}/players/{account_id}", {})
    wl = try_fetch(fetch, f"{API}/players/{account_id}/wl?lobby_type={lobby}", {})
    listed = try_fetch(fetch, f"{API}/players/{account_id}/matches?lobby_type={lobby}&limit={list_limit}", [])
    hero_stats = try_fetch(fetch, f"{API}/heroStats", [])
    listed = listed if isinstance(listed, list) else []
    hero_stats = hero_stats if isinstance(hero_stats, list) else []
    if not listed:
        raise RuntimeError("OpenDota match list empty")
    now_ts = datetime.now(timezone.utc).timestamp()
    listed = [
        row
        for row in listed
        if int(row.get("start_time") or 0) >= now_ts - form_days * 86400
    ]
    state = load_json(STATE_PATH, {})
    seen = {str(x) for x in (state.get("matchIds") or [])}
    current_ids = [str(row.get("match_id")) for row in listed if row.get("match_id")]
    new_ids = [mid for mid in current_ids if mid not in seen]
    games = []
    for row in listed[:parse_limit]:
        mid = row.get("match_id")
        try:
            blob = fetch(f"{API}/matches/{mid}")
        except Exception as err:  # noqa: BLE001
            print("match fetch failed", mid, err)
            continue
        extracted = extract_player(blob if isinstance(blob, dict) else {}, account_id, names, files)
        if extracted:
            extracted["divine"] = divine_wr(hero_stats, int(extracted.get("heroId") or 0))
            games.append(extracted)
        time.sleep(0.35)
    games.sort(key=lambda g: int(g.get("startTime") or 0), reverse=True)
    summary = summarize(games, hero_stats)
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST"
    person = (profile or {}).get("profile") or {}
    out = {
        "asOf": now,
        "accountId": account_id,
        "name": cfg.get("name") or person.get("personaname") or "QQT",
        "personaname": person.get("personaname"),
        "rankTier": (profile or {}).get("rank_tier"),
        "leaderboardRank": (profile or {}).get("leaderboard_rank"),
        "rankedWl": wl if isinstance(wl, dict) else {},
        "opendota": cfg.get("opendota"),
        "newMatchIds": new_ids,
        "summary": summary,
        "games": games,
        "note": "只收录 lobby_type=7 排位。Divine 胜率来自 OpenDota 7_pick，不是 7k+ D2PT。",
    }
    dump(OUT_PATH, out)
    dump(
        STATE_PATH,
        {
            "matchIds": current_ids,
            "asOf": now,
            "newMatchIds": new_ids,
        },
    )
    dump(
        LAUNCH_PATH,
        {
            "launch": bool(new_ids),
            "fresh": bool(new_ids),
            "reason": f"new ranked maps {new_ids}" if new_ids else "no new ranked map",
            "newMatchIds": new_ids,
            "asOf": now,
        },
    )
    briefing_path = ROOT / "web" / "data" / "player-briefing.json"
    prev = load_json(briefing_path, {})
    stub = stub_briefing(
        {"personaname": person.get("personaname") or cfg.get("name")},
        games,
        summary,
        new_ids,
        hero_stats,
    )
    if new_ids or not prev:
        dump(briefing_path, stub)
    print("player ingest", "games", len(games), "new", new_ids or "none")
    return out


def main() -> None:
    ingest()


if __name__ == "__main__":
    main()
