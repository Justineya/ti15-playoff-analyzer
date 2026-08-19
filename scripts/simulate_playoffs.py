#!/usr/bin/env python3
"""Simulate playoff BP (5+ per map), then F10K and win rate from TI15 sample.

Also compute Polymarket ROI for known series. Later-round pairings are
precomputed so the page can switch the moment a result lands.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

from stake_plan import build_bankroll

ROOT = Path(__file__).resolve().parents[1]
SIMS_PER_MAP = 5
MAPS_BO3 = 3
MAPS_BO5 = 5
SEED = 20260817
TREE_RUNS = 1000
TREE_SEED = 20260820
EWC_SAMPLE_WEIGHT = 0.45  # 7.41d at EWC vs 7.41e at TI — same skeleton, lighter weight
EIGHT = [
    "TEAM VISION",
    "Team Liquid",
    "Nigma Galaxy",
    "Team Spirit",
    "Iron Wing",
    "Team Falcons",
    "BoomBoys",
    "Team Yandex",
]
MATCH_ORDER = [
    "ubqf1",
    "ubqf2",
    "ubqf3",
    "ubqf4",
    "lbr1a",
    "lbr1b",
    "ubsf1",
    "ubsf2",
    "lbqf2",
    "lbqf1",
    "ubf",
    "lbsf",
    "lbf",
    "gf",
]

# 7.41 captain's mode as observed in TI15 parses. 0 = first picker, 1 = second.
CM = [
    (0, "ban"), (0, "ban"),
    (1, "ban"), (1, "ban"),
    (0, "ban"),
    (1, "ban"), (1, "ban"),
    (0, "pick"), (1, "pick"),
    (0, "ban"), (0, "ban"),
    (1, "ban"),
    (1, "pick"), (0, "pick"), (0, "pick"),
    (1, "pick"), (1, "pick"), (0, "pick"),
    (0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"),
    (0, "pick"), (1, "pick"),
]


def shrink(wins: int, n: int, prior_p: float, prior_n: float = 10.0) -> float:
    if n + prior_n <= 0:
        return prior_p
    return (wins + prior_p * prior_n) / (n + prior_n)


def logit(p: float) -> float:
    p = min(max(p, 0.02), 0.98)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    if x >= 20:
        return 0.99
    if x <= -20:
        return 0.01
    return 1 / (1 + math.exp(-x))


def load_json(name: str):
    return json.loads((ROOT / "data" / name).read_text())


def resolve_name(slot, known: dict[str, dict]) -> str | None:
    if isinstance(slot, str):
        return slot
    src = known.get(slot.get("from") or "")
    if not src:
        return None
    key = "winner" if slot.get("as") == "winner" else "loser"
    return src.get(key)


def feeder_teams(slot, matches_by_id: dict) -> list[str]:
    if isinstance(slot, str):
        return [slot]
    src = matches_by_id.get(slot.get("from") or "")
    if not src:
        return []
    a, b = src.get("teamA"), src.get("teamB")
    names = []
    for side in (a, b):
        if isinstance(side, str):
            names.append(side)
        else:
            names.extend(feeder_teams(side, matches_by_id))
    # unique preserve order
    out, seen = [], set()
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def load_model_games() -> list[dict]:
    ti = load_json("games.json")["games"]
    for g in ti:
        g["sample_weight"] = 1.0
    ewc_path = ROOT / "data" / "ewc_games.json"
    ewc: list[dict] = []
    if ewc_path.exists():
        ewc = load_json("ewc_games.json").get("games") or []
        for g in ewc:
            g["sample_weight"] = EWC_SAMPLE_WEIGHT
    return ti + ewc


def build_team_stats(games: list[dict]) -> dict:
    stats = {}
    global_hero = defaultdict(lambda: {"picks": 0.0, "wins": 0.0, "f10k": 0.0})
    for game in games:
        w = float(game.get("sample_weight") or 1.0)
        for side in ("radiant", "dire"):
            name = game[side]
            draft_side = (game.get("draft") or {}).get(side) or {}
            picks = [p["hero"] for p in draft_side.get("picks") or []]
            bans = [b["hero"] for b in draft_side.get("bans") or []]
            won = game.get("winner") == name
            got_f10k = bool(game.get("f10k") and game["f10k"]["side"] == side)
            mid = ((game.get("sides") or {}).get(side) or {}).get("mid") or {}
            rec = stats.setdefault(
                name,
                {
                    "games": 0.0,
                    "wins": 0.0,
                    "f10k": 0.0,
                    "games_ti": 0.0,
                    "games_ewc": 0.0,
                    "picks": Counter(),
                    "bans": Counter(),
                    "mid": Counter(),
                    "hero_games": defaultdict(float),
                    "hero_wins": defaultdict(float),
                    "hero_f10k": defaultdict(float),
                    "first_picks": Counter(),
                    "h2h_win": defaultdict(float),
                    "h2h_n": defaultdict(float),
                },
            )
            rec["games"] += w
            rec["wins"] += w * int(won)
            rec["f10k"] += w * int(got_f10k)
            if game.get("source") == "ewc":
                rec["games_ewc"] += w / EWC_SAMPLE_WEIGHT
            else:
                rec["games_ti"] += w
            rec["picks"].update({h: w for h in picks})
            rec["bans"].update({h: w for h in bans})
            if picks:
                rec["first_picks"][picks[0]] += w
            if mid.get("hero"):
                rec["mid"][mid["hero"]] += w
            opp = game["dire"] if side == "radiant" else game["radiant"]
            rec["h2h_n"][opp] += w
            rec["h2h_win"][opp] += w * int(won)
            for hero in picks:
                rec["hero_games"][hero] += w
                rec["hero_wins"][hero] += w * int(won)
                rec["hero_f10k"][hero] += w * int(got_f10k)
                global_hero[hero]["picks"] += w
                global_hero[hero]["wins"] += w * int(won)
                global_hero[hero]["f10k"] += w * int(got_f10k)
    stats["_global"] = global_hero
    stats["_all_heroes"] = sorted(global_hero)
    return stats


def weighted_choice(rng: random.Random, weights: dict[str, float], banned: set[str]) -> str | None:
    pool = [(k, w) for k, w in weights.items() if k not in banned and w > 0]
    if not pool:
        return None
    total = sum(w for _, w in pool)
    x = rng.random() * total
    acc = 0.0
    for k, w in pool:
        acc += w
        if x <= acc:
            return k
    return pool[-1][0]


def ban_weights(stats: dict, team: str, opp: str, taken: set[str]) -> dict[str, float]:
    me = stats.get(team) or {}
    them = stats.get(opp) or {}
    glob = stats["_global"]
    w: dict[str, float] = defaultdict(float)
    for hero, n in (them.get("picks") or Counter()).items():
        w[hero] += 3.0 * n
    for hero, n in (me.get("bans") or Counter()).items():
        w[hero] += 2.0 * n
    for hero, row in glob.items():
        w[hero] += 0.15 * row["picks"]
    for hero in list(w):
        if hero in taken:
            w.pop(hero, None)
    return w


def pick_weights(stats: dict, team: str, taken: set[str]) -> dict[str, float]:
    me = stats.get(team) or {}
    glob = stats["_global"]
    team_wr = shrink(me.get("wins", 0), me.get("games", 0), 0.5)
    w: dict[str, float] = {}
    for hero, n in (me.get("picks") or Counter()).items():
        hw = shrink(me["hero_wins"].get(hero, 0), me["hero_games"].get(hero, 0), team_wr)
        w[hero] = (n ** 1.15) * (0.35 + hw)
    if len(w) < 8:
        for hero, row in glob.items():
            w.setdefault(hero, 0.05 * row["picks"])
    for hero in list(w):
        if hero in taken:
            w.pop(hero, None)
    return w


def simulate_draft(rng: random.Random, stats: dict, team_a: str, team_b: str, a_first: bool) -> dict:
    order = [team_a, team_b] if a_first else [team_b, team_a]
    taken: set[str] = set()
    drafts = {team_a: {"picks": [], "bans": []}, team_b: {"picks": [], "bans": []}}
    for rel, action in CM:
        team = order[rel]
        opp = order[1 - rel]
        if action == "ban":
            hero = weighted_choice(rng, ban_weights(stats, team, opp, taken), taken)
        else:
            hero = weighted_choice(rng, pick_weights(stats, team, taken), taken)
        if not hero:
            continue
        taken.add(hero)
        drafts[team][action + "s"].append(hero)
    return {
        "firstPick": order[0],
        "teamA": {"name": team_a, **drafts[team_a]},
        "teamB": {"name": team_b, **drafts[team_b]},
    }


def hero_logodds(stats: dict, team: str, hero: str, kind: str) -> float:
    me = stats.get(team) or {}
    glob = stats["_global"]
    team_p = shrink(me.get("wins", 0), me.get("games", 0), 0.5) if kind == "win" else shrink(me.get("f10k", 0), me.get("games", 0), 0.5)
    n = me.get("hero_games", {}).get(hero, 0)
    if kind == "win":
        p = shrink(me.get("hero_wins", {}).get(hero, 0), n, team_p, prior_n=5)
        g = glob.get(hero) or {"wins": 0, "picks": 0}
        gp = shrink(g["wins"], g["picks"], 0.5, prior_n=8)
    else:
        p = shrink(me.get("hero_f10k", {}).get(hero, 0), n, team_p, prior_n=5)
        g = glob.get(hero) or {"f10k": 0, "picks": 0}
        gp = shrink(g["f10k"], g["picks"], 0.5, prior_n=8)
    return 0.65 * logit(p) + 0.35 * logit(gp)


def matchup_probs(stats: dict, team_a: str, team_b: str, draft: dict) -> dict:
    a = stats.get(team_a) or {"games": 0, "wins": 0, "f10k": 0, "h2h_n": {}, "h2h_win": {}, "mid": Counter()}
    b = stats.get(team_b) or {"games": 0, "wins": 0, "f10k": 0, "h2h_n": {}, "h2h_win": {}, "mid": Counter()}
    wr_a = shrink(a.get("wins", 0), a.get("games", 0), 0.5)
    wr_b = shrink(b.get("wins", 0), b.get("games", 0), 0.5)
    f_a = shrink(a.get("f10k", 0), a.get("games", 0), 0.5)
    f_b = shrink(b.get("f10k", 0), b.get("games", 0), 0.5)
    picks_a = draft["teamA"]["picks"]
    picks_b = draft["teamB"]["picks"]
    win_hero = 0.0
    f10_hero = 0.0
    if picks_a:
        win_hero += sum(hero_logodds(stats, team_a, h, "win") for h in picks_a) / len(picks_a)
        f10_hero += sum(hero_logodds(stats, team_a, h, "f10k") for h in picks_a) / len(picks_a)
    if picks_b:
        win_hero -= sum(hero_logodds(stats, team_b, h, "win") for h in picks_b) / len(picks_b)
        f10_hero -= sum(hero_logodds(stats, team_b, h, "f10k") for h in picks_b) / len(picks_b)
    h2h_n = a.get("h2h_n", {}).get(team_b, 0)
    h2h_adj = 0.0
    if h2h_n:
        h2h_p = shrink(a.get("h2h_win", {}).get(team_b, 0), h2h_n, 0.5, prior_n=2)
        h2h_adj = 0.35 * (logit(h2h_p) - logit(0.5))
    fp = 0.08 if draft.get("firstPick") == team_a else -0.08
    win_x = 0.35 * (logit(wr_a) - logit(wr_b)) + 0.50 * win_hero + h2h_adj + fp
    f10_x = 0.70 * (logit(f_a) - logit(f_b)) + 0.30 * f10_hero
    p_win = sigmoid(win_x)
    p_f10 = sigmoid(f10_x)
    mid_a = (a.get("mid") or Counter()).most_common(1)
    mid_b = (b.get("mid") or Counter()).most_common(1)
    return {
        "pWinA": round(p_win, 3),
        "pWinB": round(1 - p_win, 3),
        "pF10A": round(p_f10, 3),
        "pF10B": round(1 - p_f10, 3),
        "h2hGames": h2h_n,
        "sampleA": a.get("games", 0),
        "sampleB": b.get("games", 0),
        "why": (
            f"本届胜率 {team_a} {round(wr_a*100)}% / {team_b} {round(wr_b*100)}%；"
            f"先到10杀 {round(f_a*100)}% / {round(f_b*100)}%；"
            f"H2H {h2h_n} 局"
            + (f"；{team_a} 常用中单 {mid_a[0][0]}" if mid_a else "")
        ),
    }


def bo_n_from_p(p: float, n: int) -> dict:
    """Independent maps, p = P(A wins a map)."""
    need = n // 2 + 1
    # simulate paths via binomial of first (n) but series stops early; for totals:
    # P(A wins series) = P(A wins at least `need` maps) with maps played until need.
    # For identical p, P(A series) = sum_{k=need}^{n} C(k-1, need-1) * p^need * (1-p)^{k-need}
    p_series = 0.0
    for k in range(need, n + 1):
        # A wins in exactly k maps: A has need-1 in first k-1, then wins k
        # C(k-1, need-1)
        comb = math.comb(k - 1, need - 1)
        p_series += comb * (p ** need) * ((1 - p) ** (k - need))
    # Over 2.5 in Bo3 = goes to game 3 = split first two
    if n == 3:
        p_over = 2 * p * (1 - p)
        p_sweep_a = p * p  # 2-0
        p_sweep_b = (1 - p) * (1 - p)
    else:
        # Bo5 over 4.5 = goes to game 5 = 2-2 after 4
        p_over = math.comb(4, 2) * (p ** 2) * ((1 - p) ** 2)
        p_sweep_a = p ** 3
        p_sweep_b = (1 - p) ** 3
    return {
        "pSeriesA": round(p_series, 3),
        "pSeriesB": round(1 - p_series, 3),
        "pOver": round(p_over, 3),
        "pUnder": round(1 - p_over, 3),
        "pCoverMinus15A": round(p_sweep_a, 3),  # A -1.5
        "pCoverPlus15B": round(1 - p_sweep_a, 3),
    }


def poly_markets(event: dict, team_a: str, team_b: str) -> dict:
    out = {}
    for market in event.get("markets") or []:
        q = market.get("question") or ""
        outcomes = market.get("outcomes") or []
        prices = [float(x) for x in market.get("prices") or []]
        if len(outcomes) != 2 or len(prices) != 2:
            continue
        row = {"outcomes": outcomes, "prices": prices, "question": q}
        if "(BO3)" in q and "Game" not in q:
            out["series"] = row
        elif "Game 1 Winner" in q:
            out["g1"] = row
        elif "Game 2 Winner" in q:
            out["g2"] = row
        elif "O/U 2.5" in q:
            out["ou25"] = row
        elif "Handicap" in q:
            out["handicap"] = row
    return out


def roi_row(label: str, pick: str, model_p: float, market_p: float | None, n_maps_sample: int, h2h_n: int = 0) -> dict:
    if market_p is None or market_p <= 0:
        return {
            "market": label,
            "pick": pick,
            "modelP": round(model_p, 3),
            "marketP": None,
            "roi": None,
            "ev": None,
            "action": "无盘口",
            "note": "Polymarket 没有这格",
        }
    roi = model_p / market_p - 1
    ev = model_p - market_p
    gap = abs(model_p - market_p)
    if n_maps_sample < 8:
        action = "样本太薄，空仓"
    elif gap >= 0.20 and h2h_n == 0:
        action = "和市场差太大，只观察"
    elif gap >= 0.15 and h2h_n == 0:
        action = "观察 / 极小注"
    elif roi >= 0.18 and model_p >= 0.38 and roi < 0.55:
        action = "小注买"
    elif roi >= 0.08 and model_p >= 0.42:
        action = "观察 / 极小注"
    elif roi <= -0.12:
        action = "市场更贵，不买"
    else:
        action = "没有明显正期望，空仓"
    return {
        "market": label,
        "pick": pick,
        "modelP": round(model_p, 3),
        "marketP": round(market_p, 3),
        "odds": round(1 / market_p, 2),
        "roi": round(roi, 3),
        "ev": round(ev, 3),
        "action": action,
        "note": f"买 YES 成本 {round(market_p, 3)}，模型 {round(model_p, 3)}，期望回报率 {round(roi*100, 1)}%",
    }


TAGS = {
    "Iron Wing": ["iron", "iw"],
    "Team Spirit": ["spirit"],
    "TEAM VISION": ["vision", "vsn"],
    "BoomBoys": ["boom"],
    "Team Liquid": ["liquid"],
    "Team Yandex": ["yandex"],
    "Nigma Galaxy": ["nigma", "ngx"],
    "Team Falcons": ["falcon", "flc"],
}


def price_for_name(prices: dict, name: str) -> float | None:
    for k, v in prices.items():
        if name.lower() in k.lower() or k.lower() in name.lower():
            return v
        for t in TAGS.get(name, []):
            if t in k.lower():
                return v
    return None


def best_side(model_a: float, model_b: float, mkt: dict | None, name_a: str, name_b: str) -> tuple[str, float, float | None]:
    pick = name_a if model_a >= model_b else name_b
    model_p = max(model_a, model_b)
    if not mkt:
        return pick, model_p, None
    prices = {mkt["outcomes"][0]: mkt["prices"][0], mkt["outcomes"][1]: mkt["prices"][1]}
    market_p = price_for_name(prices, pick)
    return pick, model_p, market_p


def handicap_side(sim: dict, market: dict | None) -> tuple[str, float, float | None]:
    """Handicap market: the team written with (-1.5) is buying a 2-0."""
    a, b = sim["teamA"], sim["teamB"]
    p_a_sweep = sim["series"]["pCoverMinus15A"]
    p_b_sweep = round(sim["pMapB"] ** 2, 3)
    if not market:
        pick = a if p_a_sweep >= p_b_sweep else b
        return pick, max(p_a_sweep, p_b_sweep), None
    q = (market.get("question") or "").lower()
    prices = {market["outcomes"][0]: market["prices"][0], market["outcomes"][1]: market["prices"][1]}
    minus_team = None
    minus_pos = q.find("-1.5")
    if minus_pos >= 0:
        window = q[max(0, minus_pos - 28) : minus_pos]
        for name in (a, b):
            if any(t in window for t in TAGS.get(name, []) + [name.lower(), name.split()[-1].lower()]):
                minus_team = name
                break
    if minus_team is None:
        minus_team = a
    plus_team = b if minus_team == a else a
    p_minus = p_a_sweep if minus_team == a else p_b_sweep
    p_plus = 1 - p_minus
    price_minus = price_for_name(prices, minus_team)
    price_plus = price_for_name(prices, plus_team)
    roi_m = (p_minus / price_minus - 1) if price_minus else -9
    roi_p = (p_plus / price_plus - 1) if price_plus else -9
    if roi_m >= roi_p:
        return f"{minus_team} -1.5", p_minus, price_minus
    return f"{plus_team} +1.5", p_plus, price_plus


def simulate_series(stats: dict, team_a: str, team_b: str, fmt: str, rng: random.Random, detail: bool = True) -> dict:
    n_maps = MAPS_BO5 if fmt == "Bo5" else MAPS_BO3
    maps = []
    p_wins = []
    p_f10s = []
    for g in range(1, n_maps + 1):
        drafts = []
        for s in range(SIMS_PER_MAP):
            a_first = ((g + s) % 2 == 1)
            rng_i = random.Random(rng.randint(1, 10**9) + s * 17 + g * 101)
            draft = simulate_draft(rng_i, stats, team_a, team_b, a_first)
            probs = matchup_probs(stats, team_a, team_b, draft)
            row = {"sim": s + 1, **probs}
            if detail:
                row["draft"] = draft
            else:
                row["picksA"] = draft["teamA"]["picks"]
                row["picksB"] = draft["teamB"]["picks"]
                row["firstPick"] = draft["firstPick"]
            drafts.append(row)
        avg_win = sum(d["pWinA"] for d in drafts) / len(drafts)
        avg_f10 = sum(d["pF10A"] for d in drafts) / len(drafts)
        p_wins.append(avg_win)
        p_f10s.append(avg_f10)
        maps.append(
            {
                "game": g,
                "pWinA": round(avg_win, 3),
                "pWinB": round(1 - avg_win, 3),
                "pF10A": round(avg_f10, 3),
                "pF10B": round(1 - avg_f10, 3),
                "sims": drafts if detail else drafts[:1],
            }
        )
    p_map = sum(p_wins) / len(p_wins)
    p_f10 = sum(p_f10s) / len(p_f10s)
    series = bo_n_from_p(p_map, 3 if fmt != "Bo5" else 5)
    return {
        "teamA": team_a,
        "teamB": team_b,
        "format": fmt,
        "pMapA": round(p_map, 3),
        "pMapB": round(1 - p_map, 3),
        "pF10A": round(p_f10, 3),
        "pF10B": round(1 - p_f10, 3),
        "series": series,
        "maps": maps if detail else maps[:1],
        "why": maps[0]["sims"][0]["why"] if maps and maps[0]["sims"] else "",
    }


def side_name(slot, by_id: dict) -> str | None:
    if isinstance(slot, str):
        return slot
    src = by_id.get((slot or {}).get("from") or "")
    if not src:
        return None
    key = "winner" if slot.get("as") == "winner" else "loser"
    name = src.get(key)
    return name if isinstance(name, str) else None


def play_series(p_map_a: float, fmt: str, rng: random.Random) -> tuple[bool, str]:
    need = 3 if (fmt or "").lower() == "bo5" else 2
    wins_a = wins_b = 0
    while wins_a < need and wins_b < need:
        if rng.random() < p_map_a:
            wins_a += 1
        else:
            wins_b += 1
    return wins_a > wins_b, f"{wins_a}-{wins_b}"


def pair_p_map(stats: dict, team_a: str, team_b: str, rng: random.Random) -> float:
    ps = []
    for s in range(SIMS_PER_MAP):
        draft = simulate_draft(random.Random(rng.randint(1, 10**9) + s), stats, team_a, team_b, s % 2 == 0)
        ps.append(matchup_probs(stats, team_a, team_b, draft)["pWinA"])
    return sum(ps) / len(ps)


def p_map_lookup(cache: dict[tuple[str, str], float], a: str, b: str) -> float:
    if (a, b) in cache:
        return cache[(a, b)]
    if (b, a) in cache:
        return 1 - cache[(b, a)]
    return 0.5


def one_bracket(matches: list[dict], p_cache: dict[tuple[str, str], float], rng: random.Random) -> dict:
    state = {m["id"]: dict(m) for m in matches}
    for _ in range(16):
        progressed = False
        for m in state.values():
            if isinstance(m.get("winner"), str):
                continue
            a = side_name(m.get("teamA"), state)
            b = side_name(m.get("teamB"), state)
            if not (isinstance(a, str) and isinstance(b, str) and a != b):
                continue
            if m.get("status") in {"completed", "complete"} and isinstance(m.get("winner"), str):
                continue
            a_wins, score = play_series(p_map_lookup(p_cache, a, b), m.get("format") or "Bo3", rng)
            m["teamA"] = a
            m["teamB"] = b
            m["winner"] = a if a_wins else b
            m["loser"] = b if a_wins else a
            if not a_wins:
                left, right = score.split("-")
                score = f"{right}-{left}"
            m["score"] = score
            progressed = True
        if not progressed:
            break
    return state


def finish_place(state: dict) -> dict[str, str]:
    out = {}
    gf = state.get("gf") or {}
    if gf.get("winner"):
        out[gf["winner"]] = "1"
    if gf.get("loser"):
        out[gf["loser"]] = "2"
    lbf = state.get("lbf") or {}
    if lbf.get("loser"):
        out[lbf["loser"]] = "3"
    lbsf = state.get("lbsf") or {}
    if lbsf.get("loser"):
        out[lbsf["loser"]] = "4"
    for mid in ("lbqf1", "lbqf2"):
        loser = (state.get(mid) or {}).get("loser")
        if loser:
            out[loser] = "5-6"
    for mid in ("lbr1a", "lbr1b"):
        loser = (state.get(mid) or {}).get("loser")
        if loser:
            out[loser] = "7-8"
    return out


def ranked(counter: Counter, runs: int, limit: int | None = None) -> list[dict]:
    rows = [{"name": name, "n": n, "p": round(n / runs, 3)} for name, n in counter.most_common(limit)]
    return rows


def simulate_tree(stats: dict, matches: list[dict], rng: random.Random, runs: int = TREE_RUNS) -> dict:
    p_cache: dict[tuple[str, str], float] = {}
    for i, a in enumerate(EIGHT):
        for b in EIGHT[i + 1 :]:
            p_cache[(a, b)] = pair_p_map(stats, a, b, rng)
    champ = Counter()
    place = {name: Counter() for name in EIGHT}
    slot_win = {mid: Counter() for mid in MATCH_ORDER}
    slot_pair = {mid: Counter() for mid in MATCH_ORDER}
    slot_score = {mid: Counter() for mid in MATCH_ORDER}
    run_log: list[dict[str, dict]] = []
    locked = {
        m["id"]: m.get("winner")
        for m in matches
        if m.get("status") in {"completed", "complete"} and m.get("winner")
    }
    for _ in range(runs):
        state = one_bracket(matches, p_cache, rng)
        record: dict[str, dict] = {}
        for mid in MATCH_ORDER:
            m = state.get(mid) or {}
            w = m.get("winner")
            if not w:
                continue
            a, b = m.get("teamA"), m.get("teamB")
            rec = {"winner": w, "a": a, "b": b, "score": m.get("score") or ""}
            record[mid] = rec
            slot_win[mid][w] += 1
            if isinstance(a, str) and isinstance(b, str):
                slot_pair[mid][f"{a} vs {b}"] += 1
            if rec["score"]:
                slot_score[mid][f"{w} {rec['score']}"] += 1
        if state.get("gf", {}).get("winner"):
            champ[state["gf"]["winner"]] += 1
        for name, bucket in finish_place(state).items():
            if name in place:
                place[name][bucket] += 1
        run_log.append(record)
    remaining = run_log
    path = []
    for mid in MATCH_ORDER:
        cnt = Counter(r[mid]["winner"] for r in remaining if mid in r)
        if not cnt:
            break
        winner, n = cnt.most_common(1)[0]
        subset = [r for r in remaining if r.get(mid, {}).get("winner") == winner]
        match = next((m for m in matches if m["id"] == mid), {})
        pairs = Counter(
            f"{r[mid]['a']} vs {r[mid]['b']}"
            for r in subset
            if isinstance(r[mid].get("a"), str) and isinstance(r[mid].get("b"), str)
        )
        scores = Counter(f"{r[mid]['winner']} {r[mid]['score']}" for r in subset if r[mid].get("score"))
        path.append(
            {
                "id": mid,
                "round": match.get("round") or mid,
                "when": match.get("datetime"),
                "winner": winner,
                "p": round(n / max(len(remaining), 1), 3),
                "n": n,
                "of": len(remaining),
                "topPair": pairs.most_common(1)[0][0] if pairs else "",
                "scoreMode": scores.most_common(1)[0][0] if scores else "",
            }
        )
        remaining = subset
    tree_keys = Counter(tuple(r.get(mid, {}).get("winner", "") for mid in MATCH_ORDER) for r in run_log)
    top_trees = []
    for key, n in tree_keys.most_common(5):
        top_trees.append(
            {
                "n": n,
                "p": round(n / runs, 3),
                "winners": {mid: key[i] for i, mid in enumerate(MATCH_ORDER) if key[i]},
            }
        )
    p_maps = {f"{a} vs {b}": round(p, 3) for (a, b), p in sorted(p_cache.items())}
    return {
        "runs": runs,
        "seed": TREE_SEED,
        "locked": locked,
        "pMap": p_maps,
        "champion": ranked(champ, runs),
        "place": {
            name: {k: round(place[name][k] / runs, 3) for k in ("1", "2", "3", "4", "5-6", "7-8")}
            for name in EIGHT
        },
        "slots": {
            mid: {
                "winners": ranked(slot_win[mid], max(sum(slot_win[mid].values()), 1)),
                "pairings": [{"pair": k, "n": v, "p": round(v / max(sum(slot_pair[mid].values()), 1), 3)} for k, v in slot_pair[mid].most_common(6)],
            }
            for mid in MATCH_ORDER
        },
        "path": path,
        "topTrees": top_trees,
        "note": (
            "1000 次是把每张地图的模型胜率当骰子，按双败对阵图整棵掷完。"
            "每局独立，没有连胜惯性、没有败者组复仇、总决赛没有胜者组少赢一局。"
            "已结束的系列会锁死，不再重掷。"
        ),
    }


def betting_card(sim: dict, poly: dict | None, sample_n: int) -> dict:
    a, b = sim["teamA"], sim["teamB"]
    series = sim["series"]
    g1 = sim["maps"][0]
    h2h_n = (sim.get("maps") or [{}])[0].get("sims", [{}])[0].get("h2hGames") or 0
    rows = []
    m = poly or {}
    pick, mp, mktp = best_side(series["pSeriesA"], series["pSeriesB"], m.get("series"), a, b)
    rows.append(roi_row("系列胜者", pick, mp, mktp, sample_n, h2h_n))
    pick, mp, mktp = best_side(g1["pWinA"], g1["pWinB"], m.get("g1"), a, b)
    rows.append(roi_row("第一局", pick, mp, mktp, sample_n, h2h_n))
    if m.get("ou25"):
        over_p = m["ou25"]["prices"][0] if m["ou25"]["outcomes"][0].lower().startswith("over") else m["ou25"]["prices"][1]
        under_p = 1 - over_p if over_p is not None else None
        roi_o = series["pOver"] / over_p - 1 if over_p else -9
        roi_u = series["pUnder"] / under_p - 1 if under_p else -9
        if roi_o >= roi_u:
            rows.append(roi_row("总局数 O/U 2.5", "Over 2.5", series["pOver"], over_p, sample_n, h2h_n))
        else:
            rows.append(roi_row("总局数 O/U 2.5", "Under 2.5", series["pUnder"], under_p, sample_n, h2h_n))
    else:
        rows.append(roi_row("总局数 O/U 2.5", "Over 2.5", series["pOver"], None, sample_n, h2h_n))
    if m.get("handicap"):
        pick, mp, mktp = handicap_side(sim, m.get("handicap"))
        rows.append(roi_row("让分", pick, mp, mktp, sample_n, h2h_n))
    pick, mp, mktp = best_side(sim["pF10A"], sim["pF10B"], None, a, b)
    rows.append(roi_row("先到 10 杀（无盘，仅模型）", pick, mp, None, sample_n, h2h_n))
    buys = [r for r in rows if r.get("roi") is not None and r["roi"] >= 0.08 and "买" in (r.get("action") or "")]
    if not buys:
        plan = "这系列没有达到小注门槛的正期望格，建议空仓，只看模拟。"
    else:
        bits = [f"{r['market']}买{r['pick']}（期望回报率 {round(r['roi']*100,1)}%）" for r in buys[:3]]
        plan = "若只按模型 vs Polymarket 差价：" + "；".join(bits) + "。单场合计不超过银行资金 3%。"
    return {"rows": rows, "plan": plan}


def main() -> None:
    games = load_model_games()
    ti_n = sum(1 for g in games if g.get("source") != "ewc")
    ewc_n = sum(1 for g in games if g.get("source") == "ewc")
    playoffs = load_json("playoffs.json")
    poly = load_json("polymarket-playoffs.json")
    stats = build_team_stats(games)
    matches = playoffs["matches"]
    by_id = {m["id"]: m for m in matches}

    events_by_title = {}
    for event in poly.get("events") or []:
        events_by_title[event.get("title") or ""] = event

    rng = random.Random(SEED)
    known = []
    scenarios = []

    for match in matches:
        a, b = match["teamA"], match["teamB"]
        if isinstance(a, str) and isinstance(b, str):
            sim = simulate_series(stats, a, b, match.get("format") or "Bo3", rng)
            sim["id"] = match["id"]
            sim["round"] = match["round"]
            sim["when"] = match.get("datetime")
            sim["status"] = "scheduled"
            sim["polySlug"] = match.get("polySlug")
            title = match.get("polyTitle") or ""
            event = None
            for ev in poly.get("events") or []:
                if title and title in (ev.get("title") or ""):
                    event = ev
                    break
            markets = poly_markets(event, a, b) if event else {}
            sim["poly"] = markets
            sample_n = min(stats.get(a, {}).get("games", 0), stats.get(b, {}).get("games", 0))
            sim["betting"] = betting_card(sim, markets, sample_n)
            known.append(sim)
        else:
            fa = feeder_teams(a, by_id)
            fb = feeder_teams(b, by_id)
            pairings = [(x, y) for x, y in product(fa, fb) if x != y]
            # Keep next-round pairings detailed; later rounds stay as compact scenarios.
            next_round = match["id"] in {"lbr1a", "lbr1b", "ubsf1", "ubsf2"}
            if not next_round:
                continue
            for x, y in pairings:
                sim = simulate_series(stats, x, y, match.get("format") or "Bo3", rng, detail=False)
                sim["id"] = f"{match['id']}__{x}__{y}"
                sim["slot"] = match["id"]
                sim["round"] = match["round"]
                sim["when"] = match.get("datetime")
                sim["status"] = "scenario"
                sim["if"] = f"若 {x} 对上 {y}"
                sample_n = min(stats.get(x, {}).get("games", 0), stats.get(y, {}).get("games", 0))
                sim["betting"] = betting_card(sim, {}, sample_n)
                scenarios.append(sim)

    teams_for_bank = {}
    for name, rec in stats.items():
        if name.startswith("_"):
            continue
        n = rec.get("games") or 0
        got = rec.get("f10k") or 0
        teams_for_bank[name] = {
            "games": round(n, 1),
            "gamesTi": int(rec.get("games_ti") or 0),
            "gamesEwc": int(rec.get("games_ewc") or 0),
            "f10k_got": round(got, 1),
            "f10k_rate": (got / n) if n else 0,
        }

    cst = timezone(timedelta(hours=8))
    out = {
        "asOf": datetime.now(cst).strftime("%Y-%m-%d %H:%M") + " CST",
        "seed": SEED,
        "simsPerMap": SIMS_PER_MAP,
        "definition": {
            "bp": "TI15 80 局 + EWC 八强地图（45% 权重）里的选禁频率，7.41 队长模式每局 5 次",
            "win": "加权队胜率 + 阵容英雄收缩胜率 + 有限 H2H（含 EWC 八强交手）",
            "f10k": "加权先到10杀率 + 阵容英雄先到10杀倾向",
            "roi": "买 Polymarket YES：期望回报率 = 模型概率/市场价格 - 1",
            "stake": "默认¼Kelly；大胆½Kelly（p 不往上加）；全Kelly样本撑不住",
            "ewcWeight": EWC_SAMPLE_WEIGHT,
            "sampleMaps": {"ti15": ti_n, "ewc": ewc_n},
        },
        "known": known,
        "scenarios": scenarios,
        "tree": simulate_tree(stats, matches, random.Random(TREE_SEED)),
        "bankroll": build_bankroll(known, teams_for_bank),
    }
    path = ROOT / "data" / "simulations.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    champs = ", ".join(f"{r['name']} {round(r['p']*100)}%" for r in (out["tree"].get("champion") or [])[:3])
    print("wrote", path, "known", len(known), "scenarios", len(scenarios), "tree", champs)


if __name__ == "__main__":
    main()
