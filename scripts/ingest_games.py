#!/usr/bin/env python3
"""Ingest TI15 games involving the eight playoff teams.

Writes:
  data/cache/matches/{id}.json
  data/heroes.json
  data/games.json
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "matches"
UA = {"User-Agent": "TI15Analyzer/0.1"}
EIGHT = {
    9572001: "TEAM VISION",
    2163: "Team Liquid",
    10136357: "Nigma Galaxy",
    7119388: "Team Spirit",
    10150413: "Iron Wing",
    9247354: "Team Falcons",
    8255888: "BoomBoys",
    9823272: "Team Yandex",
}
# OpenDota team ids at EWC 2026 (league 19785) → canonical playoff names.
EWC_EIGHT = {
    9824702: "TEAM VISION",
    10182357: "Iron Wing",
    8255888: "BoomBoys",
    2163: "Team Liquid",
    10136357: "Nigma Galaxy",
    7119388: "Team Spirit",
    9247354: "Team Falcons",
    9823272: "Team Yandex",
}
EWC_LEAGUE = 19785
TI_LEAGUE = 19719
MID_NAMES = {
    "No[o]ne-",
    "No[o]ne",
    "Nisha",
    "lorenof",
    "Larl",
    "bzm",
    "Malr1ne",
    "gpk~",
    "gpk",
    "CHIRA_JUNIOR",
    "CHIRA_JUNIOR.",
}


def get_json(url: str, retries: int = 5) -> dict | list:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            wait = 8 if e.code == 429 else 2 + i * 2
            time.sleep(wait)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + i)
    raise RuntimeError(f"GET failed {url}: {last}")


def hero_name(heroes: dict[int, str], hero_id: int | None) -> str:
    if not hero_id:
        return "?"
    return heroes.get(int(hero_id), f"#{hero_id}")


def load_heroes() -> tuple[dict[int, str], dict[int, str]]:
    path = ROOT / "data" / "heroes.json"
    if path.exists():
        rows = json.loads(path.read_text())
    else:
        rows = get_json("https://api.opendota.com/api/heroes")
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    names = {int(h["id"]): h["localized_name"] for h in rows}
    npc = {int(h["id"]): h["name"] for h in rows}
    return names, npc


def list_league_matches(league_id: int, team_ids: set[int]) -> list[dict]:
    sql = f"""
    SELECT match_id, start_time, radiant_team_id, dire_team_id, radiant_win, duration, series_id
    FROM matches
    WHERE leagueid={league_id}
    ORDER BY start_time
    """
    url = "https://api.opendota.com/api/explorer?" + urllib.parse.urlencode({"sql": sql})
    rows = get_json(url)["rows"]
    return [
        r for r in rows if r["radiant_team_id"] in team_ids or r["dire_team_id"] in team_ids
    ]


def list_match_ids() -> list[dict]:
    return list_league_matches(TI_LEAGUE, set(EIGHT))


def fetch_match(match_id: int) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{match_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = get_json(f"https://api.opendota.com/api/matches/{match_id}")
    path.write_text(json.dumps(data))
    time.sleep(0.35)
    return data


def side_of_slot(slot: int) -> str:
    return "radiant" if slot < 128 else "dire"


def player_label(p: dict) -> str:
    return p.get("name") or p.get("personaname") or f"slot{p.get('player_slot')}"


def classify_roles(players: list[dict]) -> dict:
    """Return {side: {mid, cores, supports}} using lane_role + known mids + LH."""
    by_side = {"radiant": [], "dire": []}
    for p in players:
        by_side[side_of_slot(p.get("player_slot") or 0)].append(p)

    roles = {}
    for side, group in by_side.items():
        mid = None
        for p in group:
            name = player_label(p)
            if p.get("lane_role") == 2 or name in MID_NAMES:
                mid = p
                break
        if mid is None:
            mid = max(group, key=lambda x: ((x.get("xp_t") or [0] * 11)[10] if x.get("xp_t") else 0))
        rest = [p for p in group if p is not mid]
        rest_sorted = sorted(
            rest,
            key=lambda x: ((x.get("lh_t") or [0] * 11)[10] if x.get("lh_t") else x.get("last_hits") or 0),
            reverse=True,
        )
        cores = rest_sorted[:2]
        supports = rest_sorted[2:]
        # pos4 = support with more early kills
        supports = sorted(
            supports,
            key=lambda x: (
                -sum(1 for k in (x.get("kills_log") or []) if k.get("time", 9999) <= 600),
                (x.get("lh_t") or [0])[10] if x.get("lh_t") else 0,
            ),
        )
        roles[side] = {"mid": mid, "cores": cores, "supports": supports, "pos4": supports[0] if supports else None, "pos5": supports[1] if len(supports) > 1 else None}
    return roles


def hero_kills(players: list[dict]) -> list[dict]:
    events = []
    for p in players:
        side = side_of_slot(p.get("player_slot") or 0)
        for k in p.get("kills_log") or []:
            key = str(k.get("key") or "")
            if not key.startswith("npc_dota_hero_"):
                continue
            events.append(
                {
                    "time": int(k["time"]),
                    "side": side,
                    "killer": player_label(p),
                    "killer_hero_id": p.get("hero_id"),
                    "killer_slot": p.get("player_slot"),
                    "victim": key,
                }
            )
    events.sort(key=lambda e: (e["time"], e["killer_slot"] or 0))
    return events


def fight_clusters(events: list[dict], window: int = 25) -> list[list[dict]]:
    if not events:
        return []
    clusters = [[events[0]]]
    for e in events[1:]:
        if e["time"] - clusters[-1][-1]["time"] <= window:
            clusters[-1].append(e)
        else:
            clusters.append([e])
    return clusters


def first_tower(objectives: list[dict]) -> dict | None:
    towers = [o for o in objectives or [] if o.get("type") == "building_kill" and "tower1" in str(o.get("key"))]
    if not towers:
        return None
    t = min(towers, key=lambda o: o.get("time", 10**9))
    key = str(t.get("key") or "")
    # npc_dota_goodguys_tower1_*  => dire destroyed radiant tower
    destroyed_side = "radiant" if "goodguys" in key else "dire"
    taker = "dire" if destroyed_side == "radiant" else "radiant"
    return {"time": t.get("time"), "taker": taker, "key": key}


def draft_for_team(picks_bans: list[dict], team_bit: int, heroes: dict[int, str]) -> dict:
    # team 0 = radiant, 1 = dire
    bans, picks = [], []
    for d in picks_bans or []:
        if d.get("team") != team_bit:
            continue
        name = hero_name(heroes, d.get("hero_id"))
        if d.get("is_pick"):
            picks.append({"order": d.get("order"), "hero": name, "hero_id": d.get("hero_id")})
        else:
            bans.append({"order": d.get("order"), "hero": name, "hero_id": d.get("hero_id")})
    return {"bans": bans, "picks": picks, "phase1_bans": bans[:2], "first_picks": picks[:2]}


def first_to_ten(events: list[dict]) -> dict | None:
    """Which team first reaches 10 hero kills — not who claimed global kill #10."""
    counts = {"radiant": 0, "dire": 0}
    bags: dict[str, list[dict]] = {"radiant": [], "dire": []}
    for event in events:
        side = event["side"]
        counts[side] += 1
        bags[side].append(event)
        if counts[side] == 10:
            return {
                "side": side,
                "time": event["time"],
                "score": {"radiant": counts["radiant"], "dire": counts["dire"]},
                "completing": event,
                "kills": {"radiant": bags["radiant"], "dire": bags["dire"]},
            }
    return None


def fight_for_kill(teamfights: list[dict], time_s: int) -> dict | None:
    for fight in teamfights or []:
        start = int(fight.get("start") or 0)
        end = int(fight.get("end") or 0)
        if start - 12 <= time_s <= end + 20:
            return fight
    return None


def participation_on_kills(
    match: dict,
    ten_kills: list[dict],
    npc_by_id: dict[int, str],
) -> dict[int, dict]:
    """Kill + assist counts on a specific set of kills (usually a team's first 10).

    Assists: same OpenDota teamfight with damage, or same 25s cluster as a
    teammate kill/death. OpenDota has no per-kill assist log.
    """
    players = match.get("players") or []
    slot_index = {p.get("player_slot"): i for i, p in enumerate(players)}
    npc_to_slot = {}
    for p in players:
        npc = npc_by_id.get(int(p.get("hero_id") or 0))
        if npc:
            npc_to_slot[npc] = p.get("player_slot")
    all_events = hero_kills(players)
    clusters = fight_clusters(all_events, window=25)
    event_cluster: dict[tuple, list[dict]] = {}
    for cluster in clusters:
        for event in cluster:
            event_cluster[(event["time"], event["killer_slot"], event["victim"])] = cluster

    stats: dict[int, dict] = defaultdict(lambda: {"kills": 0, "assists": 0})
    teamfights = match.get("teamfights") or []

    for kill in ten_kills:
        killer_slot = kill["killer_slot"]
        stats[killer_slot]["kills"] += 1
        side = kill["side"]
        assisted: set[int] = set()

        fight = fight_for_kill(teamfights, kill["time"])
        if fight:
            for i, fp in enumerate(fight.get("players") or []):
                if i >= len(players):
                    continue
                pslot = players[i].get("player_slot")
                if side_of_slot(pslot or 0) != side or pslot == killer_slot:
                    continue
                if (fp.get("damage") or 0) > 0:
                    assisted.add(pslot)

        cluster = event_cluster.get((kill["time"], kill["killer_slot"], kill["victim"])) or []
        for event in cluster:
            if event["side"] == side and event["killer_slot"] != killer_slot:
                assisted.add(event["killer_slot"])
            if event["side"] != side:
                victim_slot = npc_to_slot.get(event["victim"])
                if victim_slot is not None and side_of_slot(victim_slot) == side and victim_slot != killer_slot:
                    assisted.add(victim_slot)

        for slot in assisted:
            stats[slot]["assists"] += 1
    return stats


def analyze_game(
    meta: dict,
    match: dict,
    heroes: dict[int, str],
    npc_by_id: dict[int, str],
    team_map: dict[int, str] | None = None,
    source: str = "ti15",
    patch: str = "7.41e",
) -> dict:
    team_map = team_map or EIGHT
    players = match.get("players") or []
    roles = classify_roles(players) if players else {}
    events = hero_kills(players)
    reached = first_to_ten(events)
    f10k = None
    if reached:
        done = reached["completing"]
        f10k = {
            "side": reached["side"],
            "time": reached["time"],
            "score": reached["score"],
            "completing_killer": done["killer"],
            "completing_hero": hero_name(heroes, done["killer_hero_id"]),
        }

    gold = match.get("radiant_gold_adv") or []

    def gold_at(minute: int) -> int | None:
        if minute < len(gold):
            return gold[minute]
        return None

    tower = first_tower(match.get("objectives") or [])
    duration = match.get("duration") or 0
    f10k_time = f10k["time"] if f10k else None

    # pace
    if f10k_time is None:
        pace = "未知"
    elif f10k_time < 720:
        pace = "快"
    elif f10k_time < 960:
        pace = "正常"
    else:
        pace = "慢"

    if duration >= 2700:
        length = "超长"
    elif duration >= 2100:
        length = "偏长"
    elif duration >= 1500:
        length = "标准"
    else:
        length = "雪球"

    # early aggression: kills in first 8 minutes (should be related to how fast F10K arrives)
    kills_8 = sum(1 for e in events if e["time"] <= 480)
    kills_15 = sum(1 for e in events if e["time"] <= 900)

    mid_in_first10 = {"radiant": 0, "dire": 0}
    pos4_in_first10 = {"radiant": 0, "dire": 0}
    pos5_in_first10 = {"radiant": 0, "dire": 0}
    mid_a_first10 = {"radiant": 0, "dire": 0}
    pos4_a_first10 = {"radiant": 0, "dire": 0}
    pos5_a_first10 = {"radiant": 0, "dire": 0}
    mid_ids = {}
    pos4_ids = {}
    pos5_ids = {}
    for side, r in roles.items():
        mid = r.get("mid")
        if mid:
            mid_ids[side] = mid.get("player_slot")
        pos4 = r.get("pos4")
        if pos4:
            pos4_ids[side] = pos4.get("player_slot")
        pos5 = r.get("pos5")
        if pos5:
            pos5_ids[side] = pos5.get("player_slot")

    part_by_side = {"radiant": {}, "dire": {}}
    if reached:
        for side, bag in reached["kills"].items():
            part_by_side[side] = participation_on_kills(match, bag, npc_by_id)
            for slot, st in part_by_side[side].items():
                if slot == mid_ids.get(side):
                    mid_in_first10[side] = st["kills"]
                    mid_a_first10[side] = st["assists"]
                elif slot == pos4_ids.get(side):
                    pos4_in_first10[side] = st["kills"]
                    pos4_a_first10[side] = st["assists"]
                elif slot == pos5_ids.get(side):
                    pos5_in_first10[side] = st["kills"]
                    pos5_a_first10[side] = st["assists"]

    # mid-support same-fight clusters in first 12 min (both get a kill, not assist)
    early = [e for e in events if e["time"] <= 720]
    clusters = fight_clusters(early, window=40)
    mid_sup = {"radiant": 0, "dire": 0}
    for cl in clusters:
        killers = {e["killer_slot"] for e in cl}
        for side in ("radiant", "dire"):
            if mid_ids.get(side) in killers and (
                pos4_ids.get(side) in killers or pos5_ids.get(side) in killers
            ):
                mid_sup[side] += 1

    def side_summary(side: str) -> dict:
        r = roles.get(side) or {}
        mid = r.get("mid") or {}
        pos4 = r.get("pos4") or {}
        pos5 = r.get("pos5") or {}
        gold10 = (mid.get("gold_t") or [None] * 11)
        xp10 = (mid.get("xp_t") or [None] * 11)
        mk = mid_in_first10.get(side, 0)
        ma = mid_a_first10.get(side, 0)
        p4k = pos4_in_first10.get(side, 0)
        p4a = pos4_a_first10.get(side, 0)
        p5k = pos5_in_first10.get(side, 0)
        p5a = pos5_a_first10.get(side, 0)
        mid_ka = mk + ma
        ms_ka = mk + ma + p4k + p4a + p5k + p5a
        return {
            "mid": {
                "player": player_label(mid) if mid else None,
                "hero": hero_name(heroes, mid.get("hero_id")) if mid else None,
                "hero_id": mid.get("hero_id"),
                "gold_t10": gold10[10] if len(gold10) > 10 else None,
                "xp_t10": xp10[10] if len(xp10) > 10 else None,
                "kills": mid.get("kills"),
                "kills_before_10": mk,
                "assists_before_10": ma,
                "participate_before_10": mid_ka,
            },
            "pos4": {
                "player": player_label(pos4) if pos4 else None,
                "hero": hero_name(heroes, pos4.get("hero_id")) if pos4 else None,
                "kills": pos4.get("kills"),
                "kills_before_10": p4k,
                "assists_before_10": p4a,
                "participate_before_10": p4k + p4a,
            },
            "pos5": {
                "player": player_label(pos5) if pos5 else None,
                "hero": hero_name(heroes, pos5.get("hero_id")) if pos5 else None,
                "kills_before_10": p5k,
                "assists_before_10": p5a,
                "participate_before_10": p5k + p5a,
            },
            "mid_support_fights_12min": mid_sup.get(side, 0),
            "kills_at_f10k": len(reached["kills"][side]) if reached else 0,
            "first10_mid_sup_kills": mk + p4k + p5k,
            "first10_mid_sup_ka": ms_ka,
            "mid_sup_driven": ms_ka >= 8,
        }

    rad_tid = match.get("radiant_team_id") or meta.get("radiant_team_id")
    dire_tid = match.get("dire_team_id") or meta.get("dire_team_id")
    rad_name = team_map.get(rad_tid) or match.get("radiant_name") or "Radiant"
    dire_name = team_map.get(dire_tid) or match.get("dire_name") or "Dire"
    radiant_win = match.get("radiant_win")
    winner = rad_name if radiant_win else dire_name

    # stance: 进攻/防守 for the F10K side and for winner early
    g10 = gold_at(10) or 0
    g15 = gold_at(15) or 0
    tower_time = tower["time"] if tower else None
    early_push = tower_time is not None and tower_time <= 600
    if f10k_time and f10k_time <= 720 and (early_push or abs(g15) >= 2500):
        stance = "进攻转线"
    elif f10k_time and f10k_time >= 960 and abs(g15) < 2000:
        stance = "发育对线"
    elif abs(g15) >= 4000:
        stance = "滚雪球"
    elif f10k_time and f10k_time <= 780 and not early_push:
        stance = "杀人不转塔"
    else:
        stance = "来回拉锯"

    # BP notes
    rad_draft = draft_for_team(match.get("picks_bans") or [], 0, heroes)
    dire_draft = draft_for_team(match.get("picks_bans") or [], 1, heroes)

    def bp_note(draft: dict, side: str, mid_hero: str | None) -> str:
        p1 = "、".join(x["hero"] for x in draft.get("phase1_bans") or [])
        fp = "、".join(x["hero"] for x in draft.get("first_picks") or [])
        mid_order = None
        for i, p in enumerate(draft.get("picks") or [], 1):
            if p["hero"] == mid_hero:
                mid_order = i
                break
        mid_txt = f"中单{mid_hero}第{mid_order}手拿" if mid_hero and mid_order else ""
        return "；".join(x for x in [f"一阶段禁{p1}" if p1 else "", f"前两手{fp}" if fp else "", mid_txt] if x)

    rad_s = side_summary("radiant")
    dire_s = side_summary("dire")

    f10k_txt = "没有队伍先堆到 10 杀"
    if f10k:
        win_side = f10k["side"]
        win_name = rad_name if win_side == "radiant" else dire_name
        lose_side = "dire" if win_side == "radiant" else "radiant"
        score = f10k["score"]
        win_s = rad_s if win_side == "radiant" else dire_s
        lose_s = dire_s if win_side == "radiant" else rad_s
        mid = win_s["mid"]
        f10k_txt = (
            f"{win_name}先到 10 杀（当时 {score['radiant']}-{score['dire']}，"
            f"{f10k_time // 60}分{f10k_time % 60:02d}秒）。"
            f"这 10 次击杀里，中单 {mid['player']}/{mid['hero']} 参与 {mid['participate_before_10']} 次"
            f"（击杀 {mid['kills_before_10']} + 助攻 {mid['assists_before_10']}），"
            f"中单+双辅合计参与 {win_s['first10_mid_sup_ka']} 次"
            f"{' · 中辅驱动' if win_s['mid_sup_driven'] else ''}。"
            f"对手当时 {lose_s['kills_at_f10k']} 杀。"
        )

    blurb = {
        "bp": {
            "radiant": bp_note(rad_draft, "radiant", rad_s["mid"]["hero"]),
            "dire": bp_note(dire_draft, "dire", dire_s["mid"]["hero"]),
        },
        "pace": f"{pace}节奏 / {length}局（{duration // 60}分{(duration % 60):02d}秒）；先到10杀出现在 {f10k_time // 60 if f10k_time else '?'}分" + (f"{(f10k_time % 60):02d}秒" if f10k_time else ""),
        "stance": stance,
        "f10k": f10k_txt,
        "mid_support": (
            f"天辉中单 {rad_s['mid']['player']}/{rad_s['mid']['hero']} 参与 {rad_s['mid']['participate_before_10']} 次"
            f"（击杀{rad_s['mid']['kills_before_10']}+助攻{rad_s['mid']['assists_before_10']}），"
            f"辅{rad_s['pos4']['player']}/{rad_s['pos4']['hero']} 参与 {rad_s['pos4']['participate_before_10']} 次，"
            f"中辅合计{rad_s['first10_mid_sup_ka']}{' · 中辅驱动' if rad_s['mid_sup_driven'] else ''}；"
            f"夜魇中单 {dire_s['mid']['player']}/{dire_s['mid']['hero']} 参与 {dire_s['mid']['participate_before_10']} 次"
            f"（击杀{dire_s['mid']['kills_before_10']}+助攻{dire_s['mid']['assists_before_10']}），"
            f"辅{dire_s['pos4']['player']}/{dire_s['pos4']['hero']} 参与 {dire_s['pos4']['participate_before_10']} 次，"
            f"中辅合计{dire_s['first10_mid_sup_ka']}{' · 中辅驱动' if dire_s['mid_sup_driven'] else ''}。"
            f"助攻按同一波团战伤害或同团阵亡估算，OpenDota 没有逐次助攻日志。"
        ),
    }

    return {
        "match_id": match.get("match_id") or meta.get("match_id"),
        "series_id": match.get("series_id") or meta.get("series_id"),
        "start_time": match.get("start_time") or meta.get("start_time"),
        "duration": duration,
        "parsed": match.get("version") is not None,
        "radiant": rad_name,
        "dire": dire_name,
        "radiant_team_id": match.get("radiant_team_id") or meta.get("radiant_team_id"),
        "dire_team_id": match.get("dire_team_id") or meta.get("dire_team_id"),
        "winner": winner,
        "radiant_win": radiant_win,
        "score": [match.get("radiant_score"), match.get("dire_score")],
        "pace": pace,
        "length": length,
        "stance": stance,
        "f10k": f10k,
        "f10k_mid_share": (
            (rad_s if f10k and f10k["side"] == "radiant" else dire_s)["mid"]["participate_before_10"] if f10k else 0
        ),
        "first_tower": tower,
        "gold": {"m5": gold_at(5), "m10": gold_at(10), "m15": gold_at(15), "m20": gold_at(20)},
        "kills_8min": kills_8,
        "kills_15min": kills_15,
        "draft": {"radiant": rad_draft, "dire": dire_draft},
        "sides": {"radiant": rad_s, "dire": dire_s},
        "blurb": blurb,
        "opendota": f"https://www.opendota.com/matches/{match.get('match_id') or meta.get('match_id')}",
        "source": source,
        "patch": patch,
    }


def main() -> None:
    heroes, npc_by_id = load_heroes()
    metas = list_match_ids()
    games = []
    print(f"in-scope rows {len(metas)}")
    for i, meta in enumerate(metas, 1):
        mid = int(meta["match_id"])
        print(f"[{i}/{len(metas)}] {mid}", flush=True)
        match = fetch_match(mid)
        games.append(analyze_game(meta, match, heroes, npc_by_id, source="ti15", patch="7.41e"))

    out = {
        "asOf": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " CST",
        "n": len(games),
        "definition": {
            "f10k": "哪支队伍先获得 10 次英雄击杀（先到10杀），不是全局第10个击杀的收刀人",
            "participate": "参与次数 = 击杀 + 助攻。助攻来自同一波 OpenDota 团战里出过伤害，或同一波 25 秒团里的击杀/阵亡",
            "mid": "lane_role=2，否则用已知中单名单",
            "mid_support_fight": "前12分钟、40秒窗口内中单与游走辅都出过击杀",
            "mid_sup_driven": "先到10杀时，该队中单+两个辅助合计参与次数 ≥ 8",
            "stance": "由 F10K 时间、一塔时间、15分钟经济差合成",
        },
        "games": games,
    }
    path = ROOT / "data" / "games.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote", path, "games", len(games))


if __name__ == "__main__":
    main()
