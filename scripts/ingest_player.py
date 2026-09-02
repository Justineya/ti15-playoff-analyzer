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


def extract_player(match: dict, account_id: int, names: dict[int, str]) -> dict | None:
    me = next((p for p in (match.get("players") or []) if p.get("account_id") == account_id), None)
    if not me:
        return None
    lane_role = me.get("lane_role")
    purch = me.get("purchase_log") or []
    bm = me.get("benchmarks") or {}
    start = int(match.get("start_time") or 0)
    duration = int(match.get("duration") or 0)
    is_rad = int(me.get("player_slot") or 0) < 128
    return {
        "matchId": match.get("match_id"),
        "when": datetime.fromtimestamp(start, CST).strftime("%Y-%m-%d %H:%M") if start else "",
        "startTime": start,
        "durationMin": round(duration / 60, 1) if duration else None,
        "win": bool(match.get("radiant_win")) == is_rad,
        "hero": names.get(int(me.get("hero_id") or 0), str(me.get("hero_id"))),
        "heroId": me.get("hero_id"),
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


def stub_briefing(profile: dict, games: list[dict], summary: dict, new_ids: list, hero_stats: list) -> dict:
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST"
    newest = games[:8]
    lines = []
    if new_ids:
        lines.append(f"新对局 {len(new_ids)} 把：{', '.join(str(i) for i in new_ids[:8])}。")
    else:
        lines.append("今天没有新的排位。下面仍是最近样本。")
    roles = summary.get("roles") or {}
    pos2 = roles.get("pos2") or {}
    pos3 = roles.get("pos3") or {}
    pos1 = roles.get("pos1") or {}
    lines.append(
        f"最近 {summary.get('n')} 把排位 {summary.get('wins')}-{summary.get('losses')}。"
        f"中单 {pos2.get('wins', 0)}-{pos2.get('games', 0) - pos2.get('wins', 0)}，"
        f"三号位 {pos3.get('wins', 0)}-{pos3.get('games', 0) - pos3.get('wins', 0)}，"
        f"一号位 {pos1.get('wins', 0)}-{pos1.get('games', 0) - pos1.get('wins', 0)}。"
    )
    win_avg = summary.get("winAvg") or {}
    loss_avg = summary.get("lossAvg") or {}
    if win_avg.get("gpmBr") is not None and loss_avg.get("gpmBr") is not None:
        lines.append(
            f"胜场同分段 GPM 分位 {win_avg['gpmBr']:.0%}、推塔 {win_avg.get('towerBr') or 0:.0%}；"
            f"负场 GPM {loss_avg['gpmBr']:.0%}、推塔 {loss_avg.get('towerBr') or 0:.0%}。"
        )
    focus = []
    for g in newest:
        if g.get("win"):
            continue
        meta = divine_wr(hero_stats, int(g.get("heroId") or 0))
        kind = classify_game(g, meta)
        wr = f"{meta['wr']:.0%}" if meta else "?"
        focus.append(
            {
                "matchId": g.get("matchId"),
                "hero": g.get("hero"),
                "role": g.get("role"),
                "kind": kind,
                "divineWr": meta,
                "note": f"{g.get('hero')} {g.get('role')} 负 · Divine胜率 {wr} · {kind}",
            }
        )
    headline = (
        f"{profile.get('personaname') or 'QQT'} 最近 {summary.get('n')} 把 "
        f"{summary.get('wins')}-{summary.get('losses')}"
    )
    return {
        "asOf": now,
        "source": "stub",
        "headline": headline,
        "narrative": " ".join(lines),
        "positioning": "Immortal 节奏核：主中、副三。一号位先别在组排补。",
        "newMatchIds": new_ids,
        "focus": focus[:6],
        "note": "数字来自 OpenDota。Cursor 日更会把 narrative 改成完整复盘。非投注建议。",
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
        extracted = extract_player(blob if isinstance(blob, dict) else {}, account_id, names)
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
