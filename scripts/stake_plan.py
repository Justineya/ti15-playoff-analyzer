#!/usr/bin/env python3
"""Bankroll math: fractional Kelly on the *current* bankroll.

Default is ¼Kelly. Bold is ½Kelly on the same (already-shrunken) p — never
by inflating p. Sample per team is 10–17 maps, so the point estimate is noisy.
"""
from __future__ import annotations

import math

BANKROLL0 = 1000
KELLY_FRACTION = 0.25  # Thorp: use 1/4 when p is estimated, not known
CAP = 0.05  # never more than 5% of current bankroll on one ticket
MIN_STAKE = 8  # below this, skip (noise / juice)
ODDS_GRID = [1.55, 1.60, 1.65, 1.70, 1.75, 1.80, 1.85, 1.90, 2.00]
DEFAULT_LOW_ODDS = 1.70  # typical 低保 placeholder; plug in the real price
Z95 = 1.96

# 大胆只拧「拿几成 Kelly」，不拧 p。过猛 = 把估出来的 p 当成真值。
PROFILES = {
    "稳健": {
        "id": "稳健",
        "fraction": 0.25,
        "cap": 0.05,
        "simulCap": 0.10,
        "label": "稳健 · ¼Kelly",
        "why": "p 是估的。Thorp：估计概率时用 1/4 Kelly。",
    },
    "大胆": {
        "id": "大胆",
        "fraction": 0.50,
        "cap": 0.08,
        "simulCap": 0.16,
        "label": "大胆 · ½Kelly",
        "why": "同一张票大约下到稳健的两倍，单票硬顶 8%。不把模型 p 往上加。负期望仍然空仓。",
    },
    "过猛": {
        "id": "过猛",
        "fraction": 1.00,
        "cap": 0.15,
        "simulCap": 0.30,
        "label": "过猛 · 全Kelly",
        "why": "把 10–17 局估出来的 p 当成已知真值。估高 10 个点就会过度下注，长期增长更差。",
    },
}


def full_kelly(p: float, odds: float) -> float:
    """f* = (p*odds - 1) / (odds - 1). Negative => no bet."""
    if odds <= 1 or p <= 0 or p >= 1:
        return 0.0
    edge = p * odds - 1
    return max(0.0, edge / (odds - 1))


def sized_kelly(p: float, odds: float, fraction: float, cap: float) -> float:
    return min(cap, full_kelly(p, odds) * fraction)


def quarter_kelly(p: float, odds: float) -> float:
    return sized_kelly(p, odds, KELLY_FRACTION, CAP)


def break_even_odds(p: float) -> float:
    if p <= 0:
        return 99.0
    return round(1 / p, 2)


def binom_se(p: float, n: int) -> float:
    if n <= 0:
        return 0.5
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.sqrt(p * (1 - p) / n)


def wilson(k: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval. k may be fractional (model p × n_eff)."""
    if n <= 0:
        return (0.0, 1.0)
    p = min(max(k / n, 0.0), 1.0)
    z2 = z * z
    den = n + z2
    center = (n * p + z2 / 2) / den
    margin = (z / den) * math.sqrt(n * p * (1 - p) + z2 / 4)
    return (round(max(0.0, center - margin), 3), round(min(1.0, center + margin), 3))


def need_n(p: float, halfwidth: float = 0.05, z: float = Z95) -> int:
    """Maps needed so a 95% interval is about ±halfwidth."""
    p = min(max(p, 0.02), 0.98)
    n = (z * z * p * (1 - p)) / (halfwidth * halfwidth)
    return int(math.ceil(n))


def ticket(
    p: float,
    odds: float,
    bankroll: float,
    fraction: float = KELLY_FRACTION,
    cap: float = CAP,
) -> dict:
    fk = full_kelly(p, odds)
    qk = sized_kelly(p, odds, fraction, cap)
    ev_per_yuan = p * odds - 1
    stake = int(round(bankroll * qk))
    if qk <= 0 or ev_per_yuan <= 0:
        action = "空仓"
        stake = 0
    elif stake < MIN_STAKE:
        action = "优势太薄，空仓"
        stake = 0
    else:
        action = "下"
    win_bank = round(bankroll + stake * (odds - 1), 1) if stake else bankroll
    lose_bank = round(bankroll - stake, 1) if stake else bankroll
    return {
        "odds": odds,
        "fullKelly": round(fk, 4),
        "quarterKelly": round(qk, 4),
        "kellyUsed": round(qk, 4),
        "fraction": fraction,
        "evPerYuan": round(ev_per_yuan, 4),
        "stake": stake,
        "pctOfBank": round(100 * stake / bankroll, 2) if bankroll else 0,
        "ifWin": win_bank,
        "ifLose": lose_bank,
        "evYuan": round(stake * ev_per_yuan, 1),
        "action": action,
    }


def grid_for(p: float, bankroll: float = BANKROLL0, fraction: float = KELLY_FRACTION, cap: float = CAP) -> list[dict]:
    return [ticket(p, o, bankroll, fraction, cap) for o in ODDS_GRID]


def _next_live(picks, odds, bank, fraction, cap) -> dict | None:
    running = bank
    for pick in picks:
        t = ticket(pick["modelP"], odds, running, fraction, cap)
        if t["stake"]:
            return {
                "next": pick["pick"],
                "when": pick["when"],
                "bank": round(running, 1),
                "stake": t["stake"],
                "pctOfBank": t["pctOfBank"],
                "action": t["action"],
                "quarterKelly": t["kellyUsed"],
                "naiveFixed100": 100,
                "naive10pct": int(round(running * 0.10)),
            }
    return None


def sequential_path(
    picks: list[dict],
    odds: float,
    start: float = BANKROLL0,
    fraction: float = KELLY_FRACTION,
    cap: float = CAP,
) -> dict:
    steps = []
    for pick in picks:
        t = ticket(pick["modelP"], odds, start, fraction, cap)
        steps.append({"id": pick["id"], "when": pick["when"], "pick": pick["pick"], "modelP": pick["modelP"], "bankBefore": start, **t})

    walk = []
    running = start
    for i, pick in enumerate(picks):
        t = ticket(pick["modelP"], odds, running, fraction, cap)
        node = {
            "pick": pick["pick"],
            "when": pick["when"],
            "modelP": pick["modelP"],
            "bankBefore": round(running, 1),
            "stake": t["stake"],
            "pctOfBank": t["pctOfBank"],
            "quarterKelly": t["kellyUsed"],
            "action": t["action"],
            "ifWinBank": t["ifWin"],
            "ifLoseBank": t["ifLose"],
        }
        if t["stake"] == 0:
            node["nextNote"] = "空仓，本金不动，进入下一场"
            walk.append(node)
            continue
        rest = picks[i + 1 :]
        node["ifWinNext"] = _next_live(rest, odds, t["ifWin"], fraction, cap)
        node["ifLoseNext"] = _next_live(rest, odds, t["ifLose"], fraction, cap)
        walk.append(node)
        break
    return {"odds": odds, "start": start, "fraction": fraction, "cap": cap, "steps": steps, "walk": walk}


def simultaneous(
    picks: list[dict],
    odds: float,
    start: float = BANKROLL0,
    fraction: float = KELLY_FRACTION,
    cap: float = CAP,
    simul_cap: float = 0.10,
) -> dict:
    raw = []
    for pick in picks:
        t = ticket(pick["modelP"], odds, start, fraction, cap)
        raw.append({**pick, **t})
    total = sum(r["stake"] for r in raw)
    cap_yuan = int(round(start * simul_cap))
    scale = 1.0 if total <= cap_yuan or total == 0 else cap_yuan / total
    sized = []
    for r in raw:
        stake = int(round(r["stake"] * scale)) if r["stake"] else 0
        sized.append(
            {
                "pick": r["pick"],
                "when": r["when"],
                "modelP": r["modelP"],
                "rawStake": r["stake"],
                "stake": stake,
                "action": "空仓" if stake == 0 else ("压缩后下" if scale < 0.999 else "下"),
            }
        )
    return {
        "odds": odds,
        "scale": round(scale, 3),
        "total": sum(x["stake"] for x in sized),
        "cap": cap_yuan,
        "tickets": sized,
    }


def strategy_compare(picks: list[dict], odds: float, start: float = BANKROLL0) -> list[dict]:
    rows = []
    for pick in picks:
        t_q = ticket(pick["modelP"], odds, start, 0.25, 0.05)
        t_h = ticket(pick["modelP"], odds, start, 0.50, 0.08)
        t_f = ticket(pick["modelP"], odds, start, 1.00, 0.15)
        edge = pick["modelP"] * odds - 1
        rows.append(
            {
                "pick": pick["pick"],
                "when": pick["when"],
                "modelP": pick["modelP"],
                "breakEvenOdds": break_even_odds(pick["modelP"]),
                "edgePerYuan": round(edge, 4),
                "fixed100": 100,
                "fixed100Ev": round(100 * edge, 1),
                "pct10": int(round(start * 0.10)),
                "pct10Ev": round(start * 0.10 * edge, 1),
                "qKelly": t_q["stake"],
                "qKellyEv": t_q["evYuan"],
                "qKellyPct": t_q["pctOfBank"],
                "halfKelly": t_h["stake"],
                "halfKellyPct": t_h["pctOfBank"],
                "fullKellyStake": t_f["stake"],
                "fullKellyPct": t_f["pctOfBank"],
                "fullKellyTruePct": round(100 * t_q["fullKelly"], 2),
                "action": t_q["action"],
                "actionBold": t_h["action"],
            }
        )
    return rows


def resize_example(
    picks: list[dict],
    odds: float,
    start: float = BANKROLL0,
    fraction: float = KELLY_FRACTION,
    cap: float = CAP,
) -> dict:
    live = [p for p in picks if ticket(p["modelP"], odds, start, fraction, cap)["stake"] > 0]
    if len(live) < 2:
        live = picks[-2:]
    first, second = live[0], live[1]
    t1 = ticket(first["modelP"], odds, start, fraction, cap)
    win = ticket(second["modelP"], odds, t1["ifWin"], fraction, cap)
    lose = ticket(second["modelP"], odds, t1["ifLose"], fraction, cap)
    return {
        "question": "赚了下一把还是下 100，还是下 10%？",
        "answer": "都不是。下一把 = 结算后的本金 × 下一把自己的Kelly分数。赢了只是本金变大，分数不因为刚赢了就加大。",
        "odds": odds,
        "fraction": fraction,
        "first": {
            "pick": first["pick"],
            "when": first["when"],
            "modelP": first["modelP"],
            "bank": start,
            "stake": t1["stake"],
            "pctOfBank": t1["pctOfBank"],
            "quarterKelly": t1["kellyUsed"],
            "fullKelly": t1["fullKelly"],
            "ifWin": t1["ifWin"],
            "ifLose": t1["ifLose"],
        },
        "ifWin": {
            "bank": t1["ifWin"],
            "next": second["pick"],
            "stake": win["stake"],
            "pctOfBank": win["pctOfBank"],
            "naiveFixed100": 100,
            "naive10pct": int(round(t1["ifWin"] * 0.10)),
        },
        "ifLose": {
            "bank": t1["ifLose"],
            "next": second["pick"],
            "stake": lose["stake"],
            "pctOfBank": lose["pctOfBank"],
            "naiveFixed100": 100,
            "naive10pct": int(round(t1["ifLose"] * 0.10)),
        },
        "whyNot100": "固定 100 不看优势：负期望也会下 100，优势大的也只下 100。",
        "whyNot10pct": (
            f"本金 10% 在低保 {odds:.2f}、p≈{first['modelP']:.0%} 时接近全Kelly"
            f"（全Kelly约 {round(100 * t1['fullKelly'])}%）。p 是从约 10–17 局估的，全Kelly会过度下注。"
        ),
    }


def uncertainty_for(pick: dict, teams: dict, odds: float = DEFAULT_LOW_ODDS) -> dict:
    """Binomial error on the matchup. n_eff = smaller team's map count."""
    a = teams.get(pick["team"]) or {}
    b = teams.get(pick["opp"]) or {}
    n_a = int(a.get("games") or 0)
    n_b = int(b.get("games") or 0)
    n_eff = min(n_a, n_b) if n_a and n_b else (n_a or n_b)
    p = pick["modelP"]
    se = round(binom_se(p, n_eff), 3)
    p_low = round(max(0.01, p - se), 3)
    p_high = round(min(0.99, p + se), 3)
    lo, hi = wilson(p * n_eff, n_eff)
    raw_n = n_a
    raw_k = int(a.get("f10k_got") or 0)
    raw_p = (raw_k / raw_n) if raw_n else 0.0
    raw_lo, raw_hi = wilson(raw_k, raw_n)
    edge = p * odds - 1
    edge_low = p_low * odds - 1
    need5 = need_n(p, 0.05)
    need10 = need_n(p, 0.10)
    return {
        "teamN": n_a,
        "oppN": n_b,
        "nEff": n_eff,
        "se": se,
        "pMinusSe": p_low,
        "pPlusSe": p_high,
        "wilson95": [lo, hi],
        "rawRate": round(raw_p, 3),
        "raw": f"{raw_k}/{raw_n}",
        "rawWilson95": [raw_lo, raw_hi],
        "edgeAtPoint": round(edge, 4),
        "edgeIfLow": round(edge_low, 4),
        "plusEvIfLow": edge_low > 0,
        "needNFor5pp": need5,
        "needNFor10pp": need10,
        "haveVsNeed5": f"{n_eff}/{need5}",
        "verdict": (
            "点估计有优势，但真 p 只要低 1 个标准误就变负期望。样本撑不住把这张票当稳的。"
            if edge > 0 and edge_low <= 0
            else (
                "点估计已是负期望。再大胆也不能下。"
                if edge <= 0
                else "低 1 个标准误仍有正期望，这张相对站得住。"
            )
        ),
    }


def profile_block(picks: list[dict], profile: dict, odds: float = DEFAULT_LOW_ODDS) -> dict:
    frac, cap, scap = profile["fraction"], profile["cap"], profile["simulCap"]
    tickets = []
    for pick in picks:
        t = ticket(pick["modelP"], odds, BANKROLL0, frac, cap)
        tickets.append(
            {
                "pick": pick["pick"],
                "when": pick["when"],
                "modelP": pick["modelP"],
                "stake": t["stake"],
                "pctOfBank": t["pctOfBank"],
                "action": t["action"],
                "ifWin": t["ifWin"],
                "ifLose": t["ifLose"],
            }
        )
    live = [x for x in tickets if x["stake"]]
    two_loss = BANKROLL0
    for x in live:
        two_loss = round(two_loss * (1 - x["pctOfBank"] / 100), 1)
    return {
        **{k: profile[k] for k in ("id", "label", "why", "fraction", "cap", "simulCap")},
        "tickets": tickets,
        "total": sum(x["stake"] for x in tickets),
        "ifAllLose": two_loss,
        "resize": resize_example(picks, odds, BANKROLL0, frac, cap),
        "sequential": sequential_path(picks, odds, BANKROLL0, frac, cap),
        "simultaneous": simultaneous(picks, odds, BANKROLL0, frac, cap, scap),
    }


def build_bankroll(known: list[dict], teams: dict) -> dict:
    by_id = {s["id"]: s for s in known}

    def g1_f10(sim_id: str, side: str) -> float:
        sim = by_id.get(sim_id) or {}
        g1 = (sim.get("maps") or [{}])[0]
        key = "pF10A" if side == "A" else "pF10B"
        return float(g1.get(key) or sim.get(key) or 0.5)

    def g1_f10_both(sim_id: str) -> tuple[float, float]:
        sim = by_id.get(sim_id) or {}
        g1 = (sim.get("maps") or [{}])[0]
        pa = float(g1.get("pF10A") or sim.get("pF10A") or 0.5)
        pb = float(g1.get("pF10B") or sim.get("pF10B") or 0.5)
        return pa, pb

    def matchup_teams(sim_id: str) -> tuple[str, str]:
        sim = by_id.get(sim_id) or {}
        return sim.get("teamA") or "", sim.get("teamB") or ""

    def sample_line(name: str) -> str:
        t = teams.get(name) or {}
        n_ti = t.get("gamesTi") or 0
        n_ewc = t.get("gamesEwc") or 0
        n = t.get("games") or 0
        got = t.get("f10k_got") or 0
        rate = t.get("f10k_rate")
        return f"模型样本 TI {n_ti} + EWC {n_ewc}（有效 {round(n,1)}）· 先到10杀 {round((rate or 0)*100)}%"

    picks = [
        {
            "id": "ubqf1",
            "when": "8/20 10:00 G1",
            "alias": "1win / Iron Wing",
            "team": "Iron Wing",
            "opp": "Team Spirit",
            "pick": "Iron Wing 先到 10 杀",
            "modelP": g1_f10("ubqf1", "A"),
            "sample": sample_line("Iron Wing"),
            "note": "模型只有约 54%。低保 1.70 时 p×赔率<1，期望为负——低保不等于该下。",
        },
        {
            "id": "ubqf2",
            "when": "8/20 13:00 G1",
            "alias": "PAVI / TEAM VISION",
            "team": "TEAM VISION",
            "opp": "BoomBoys",
            "pick": "TEAM VISION 先到 10 杀",
            "modelP": g1_f10("ubqf2", "A"),
            "sample": sample_line("TEAM VISION"),
            "note": "系列可以是低保：EWC 决赛 3-1、瑞士 2-0。先到10杀不是。瑞士第二局 BoomBoys 先到10杀、VISION 仍赢图。",
        },
        {
            "id": "ubqf3",
            "when": "8/20 16:00 G1",
            "alias": "液体 / Team Liquid",
            "team": "Team Liquid",
            "opp": "Team Yandex",
            "pick": "Team Liquid 先到 10 杀",
            "modelP": g1_f10("ubqf3", "A"),
            "sample": sample_line("Team Liquid"),
            "note": "四场里最站得住的10杀低保。本届先到10杀率八强最高。",
        },
        {
            "id": "ubqf4",
            "when": "8/20 19:00 G1",
            "alias": "Falcons",
            "team": "Team Falcons",
            "opp": "Nigma Galaxy",
            "pick": "Team Falcons 先到 10 杀",
            "modelP": g1_f10("ubqf4", "B"),
            "sample": sample_line("Team Falcons"),
            "note": "NGX 赢图不靠堆前10人头。先到10杀跟 Falcons，不要跟 NGX 系列混为一谈。NGX 只有 10 局，这条的误差最大。",
        },
    ]
    for p in picks:
        pa, pb = g1_f10_both(p["id"])
        ta, tb = matchup_teams(p["id"])
        if ta:
            p["teamA"] = ta
        if tb:
            p["teamB"] = tb
        p["pF10A"] = round(pa, 3)
        p["pF10B"] = round(pb, 3)
        p["sides"] = [
            {
                "side": "A",
                "team": ta or p.get("team"),
                "label": f"{ta or p.get('team')} 先到 10 杀",
                "modelP": round(pa, 3),
                "breakEvenOdds": break_even_odds(pa),
            },
            {
                "side": "B",
                "team": tb or p.get("opp"),
                "label": f"{tb or p.get('opp')} 先到 10 杀",
                "modelP": round(pb, 3),
                "breakEvenOdds": break_even_odds(pb),
            },
        ]
        p["modelP"] = round(p["modelP"], 3)
        p["breakEvenOdds"] = break_even_odds(p["modelP"])
        p["grid"] = grid_for(p["modelP"], BANKROLL0)
        p["atDefault"] = ticket(p["modelP"], DEFAULT_LOW_ODDS, BANKROLL0)
        p["atBold"] = ticket(p["modelP"], DEFAULT_LOW_ODDS, BANKROLL0, 0.50, 0.08)
        p["atFull"] = ticket(p["modelP"], DEFAULT_LOW_ODDS, BANKROLL0, 1.00, 0.15)
        p["uncertainty"] = uncertainty_for(p, teams)
        p["bothAt170"] = [
            {
                **s,
                "evPerYuan": round(s["modelP"] * DEFAULT_LOW_ODDS - 1, 4),
                "atDefault": ticket(s["modelP"], DEFAULT_LOW_ODDS, BANKROLL0),
            }
            for s in p["sides"]
        ]
        plus = [x for x in p["bothAt170"] if x["evPerYuan"] > 0]
        p["evSideNote"] = (
            f"低保 {DEFAULT_LOW_ODDS}：{' / '.join(x['team'] for x in plus)} 点估计有正期望"
            if plus
            else f"低保 {DEFAULT_LOW_ODDS}：两边点估计都是负期望，应空仓"
        )

    profiles = {k: profile_block(picks, v) for k, v in PROFILES.items()}
    any_plus_if_low = any(p["uncertainty"]["plusEvIfLow"] for p in picks)

    return {
        "start": BANKROLL0,
        "method": "quarter-kelly-on-current-bankroll",
        "kellyFraction": KELLY_FRACTION,
        "cap": CAP,
        "minStake": MIN_STAKE,
        "defaultOdds": DEFAULT_LOW_ODDS,
        "formula": "全Kelly f* = (p×赔率 − 1) / (赔率 − 1)；实下注码 = 当前本金 × min(上限, 分数×f*)",
        "question": "赚了下一把还是下 100，还是下 10%？",
        "answer": "都不是。下一把 = 结算后的本金 × 下一把自己的Kelly分数。赢了本金变大，金额可以略升；分数由下一把优势决定，不因为刚赢了就改成 10%。",
        "sampleTooSmall": True,
        "sampleHeadline": "够用来分「谁更常先到10杀」，不够用来把 65% 当成真值去下全Kelly。",
        "sampleWhy": [
            "八强本届一共 80 局，每队只有 10–17 局。二项标准误大约 9–13 个百分点。",
            "Liquid 原始先到10杀 10/14≈71%，95% Wilson 大约 45%–88%。中间那截什么结果都能装进去。",
            "要对 65% 估到 ±5 个点（95%），大约需要 350 局。我们有 14。估到 ±10 个点大约要 87 局，也没有。",
            "模型已经向 0.5 收缩（先验约 10 局），所以页面上的 65% 已经比原始 71% 保守。再往上加 p 不是大胆，是把噪声当信号。",
            "EWC（7.41d）八强地图按 45% 权重并进模型：系列、H2K、BP 倾向、先到10杀率都变厚。TI15 7.41e 仍为 100%。",
            "所以：稳健用 ¼Kelly；大胆只把分数改成 ½Kelly，p 不动；过猛才是全Kelly，样本撑不住。",
        ],
        "boldRule": "大胆 = 同一张正期望票下到大约两倍（½Kelly，单票上限 8%）。IW / VISION 先到10杀点估计已是负期望，大胆也是 0。不因为大胆就把 54% 当成 65%。",
        "lowSeStillMinus": not any_plus_if_low,
        "evRule": {
            "headline": "不只能投高概率方。看的是 p×赔率 有没有大于 1，不是谁模型概率更高。",
            "formula": "每注期望 = 模型 p × 你拿到的赔率 − 1。大于 0 才有优势；Kelly 只对这种票算注码。",
            "favoriteTrap": "热门方概率高，但低保 1.70 常让 p×赔率<1（例如模型 57%×1.70=0.97）。这不是「该买热门」。",
            "underdogOk": "冷门方概率低，若盘口给够高（例如模型 42% 要赔率≥2.38），一样可以是正期望。",
            "bothSides": "同一局通常只有一边（或两边都没有）正期望。用计算器分别填两边的真实赔率试。",
            "example": "VISION F10K 模型约 58%/42%。1.70 买 VISION 点估计亏；若 BoomBoys 给到 2.50，42%×2.50=1.05 才转正。",
        },
        "calculatorProfiles": [
            {"id": "稳健", "fraction": 0.25, "cap": 0.05},
            {"id": "大胆", "fraction": 0.50, "cap": 0.08},
            {"id": "过猛", "fraction": 1.00, "cap": 0.15},
        ],
        "rules": [
            "不是固定 100。也不是每把都下当前本金的 10%。10% 接近全Kelly，概率是估出来的，会过度下注。",
            "不是「只买热门」。买哪边只看 p×赔率−1 是否为正；冷门赔够高一样可以下。",
            "每一把单独算优势。优势不同，分数不同。没优势就 0。大胆不把负期望变成正期望。",
            "注码 = 当前本金 × 这一把的分数Kelly。赢了本金变大，下一把金额变大；输了变小。分数不因为刚赢了就加大。",
            "同一天四场按开赛顺序：一场 G1 先到10杀结算完，再用新本金算下一场。",
            "若开赛前就要一次下完：先各算 Kelly，合计超过当日上限就同比例压缩。",
            "绝不输了加码翻本（马丁）。那是负期望下的破产策略。",
        ],
        "whyQuarter": [
            "Kelly 公式在 p 和赔率已知、可重复独立下注时，最大化对数财富增长。",
            "这里的 p 来自本届 10–17 局/队，标准误大约 9–13 个百分点，不是已知真值。",
            "Thorp 的做法：估计概率时用 1/4 Kelly。全Kelly在估高 10 个点时会过度下注，长期增长反而更差。",
            "大胆一档用 1/2 Kelly，仍然用同一张已经收缩过的 p，单票硬顶 8%。",
            "单票再加硬顶，避免某一场「模型很满」把本金一次押进去。",
        ],
        "picks": picks,
        "profiles": profiles,
        "compareAt170": strategy_compare(picks, 1.70),
        "resizeAt170": resize_example(picks, 1.70),
        "resizeBoldAt170": resize_example(picks, 1.70, BANKROLL0, 0.50, 0.08),
        "sequentialAt170": sequential_path(picks, 1.70),
        "sequentialAt185": sequential_path(picks, 1.85),
        "simultaneousAt170": simultaneous(picks, 1.70),
        "simultaneousAt185": simultaneous(picks, 1.85),
    }


def _self_check() -> None:
    assert abs(full_kelly(0.65, 1.70) - 0.15) < 1e-9
    assert abs(quarter_kelly(0.65, 1.70) - 0.0375) < 1e-9
    t = ticket(0.65, 1.70, 1000)
    assert t["stake"] == 38
    assert t["action"] == "下"
    bold = ticket(0.65, 1.70, 1000, 0.50, 0.08)
    assert bold["stake"] == 75  # 0.075 * 1000
    assert ticket(0.54, 1.70, 1000)["stake"] == 0
    assert ticket(0.54, 1.70, 1000, 0.50, 0.08)["stake"] == 0  # bold does not revive -EV
    t2 = ticket(0.65, 1.70, t["ifWin"])
    assert t2["stake"] in {38, 39}
    assert abs(t2["pctOfBank"] - t["pctOfBank"]) < 0.2
    assert quarter_kelly(0.80, 2.00) == CAP
    assert ticket(0.80, 2.00, 1000)["stake"] == 50
    lo, hi = wilson(10, 14)
    assert 0.44 <= lo <= 0.48
    assert 0.87 <= hi <= 0.90
    assert need_n(0.65, 0.05) >= 300
    print("stake_plan self-check ok")


if __name__ == "__main__":
    _self_check()
