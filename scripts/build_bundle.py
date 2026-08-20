#!/usr/bin/env python3
"""Build web/data/bundle.json from games.json + polymarket snapshot."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from f10k_g1 import build_report

ROOT = Path(__file__).resolve().parents[1]
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


def load_iw_spirit_h2h() -> dict | None:
    path = ROOT / "data" / "iw_spirit_h2h.json"
    if not path.exists():
        return None
    blob = json.loads(path.read_text())
    blob.pop("maps", None)
    return blob


def when_label(dt: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})", dt or "")
    if not m:
        return dt or ""
    return f"{int(m.group(2))}/{int(m.group(3))} {m.group(4)} CST"


def match_when(playoffs: dict, match_id: str, fallback: str) -> str:
    for m in playoffs.get("matches") or []:
        if m.get("id") == match_id:
            return when_label(m.get("datetime") or "") or fallback
    return fallback


def series_price(markets: dict, title_sub: str) -> dict | None:
    for event in markets["events"]:
        if title_sub not in (event.get("title") or ""):
            continue
        for market in event["markets"]:
            question = market["question"]
            if "(BO3)" in question and "Game" not in question:
                return {
                    "outcomes": market["outcomes"],
                    "prices": [float(x) for x in market["prices"]],
                    "volume": event.get("volume"),
                    "slug": event["slug"],
                }
    return None


def team_profile(games: list[dict], name: str) -> dict:
    mine = []
    for game in games:
        if name in (game["radiant"], game["dire"]):
            side = "radiant" if game["radiant"] == name else "dire"
            mine.append((game, side))
    n = len(mine)
    wins = sum(1 for game, _ in mine if game["winner"] == name)
    f10k_got = sum(1 for game, side in mine if game.get("f10k") and game["f10k"]["side"] == side)
    f10k_mid_share = []
    for game, side in mine:
        if game.get("f10k") and game["f10k"]["side"] == side:
            mid = game["sides"][side]["mid"]
            f10k_mid_share.append(mid.get("participate_before_10") or mid.get("kills_before_10") or 0)
    f10k_mid = sum(1 for share in f10k_mid_share if share >= 3)
    mid_k = sum((game["sides"][side]["mid"].get("participate_before_10") or game["sides"][side]["mid"].get("kills_before_10") or 0) for game, side in mine)
    ms_k = sum((game["sides"][side].get("first10_mid_sup_ka") or game["sides"][side].get("first10_mid_sup_kills") or 0) for game, side in mine)
    driven = sum(1 for game, side in mine if game["sides"][side].get("mid_sup_driven"))
    mids = Counter(game["sides"][side]["mid"]["hero"] for game, side in mine)
    pos4s = Counter(game["sides"][side]["pos4"]["hero"] for game, side in mine)
    pace = Counter(game["pace"] for game, _ in mine)
    stance = Counter(game["stance"] for game, _ in mine)
    duration = sum(game["duration"] for game, _ in mine) / n
    f10k_times = [
        game["f10k"]["time"]
        for game, side in mine
        if game.get("f10k") and game["f10k"]["side"] == side
    ]
    return {
        "name": name,
        "games": n,
        "wins": wins,
        "winrate": round(wins / n, 3),
        "f10k_got": f10k_got,
        "f10k_rate": round(f10k_got / n, 3),
        "f10k_mid_ge3": f10k_mid,
        "avg_mid_ka_when_first_to_10": round(sum(f10k_mid_share) / len(f10k_mid_share), 2) if f10k_mid_share else None,
        "avg_mid_kills_when_first_to_10": round(sum(f10k_mid_share) / len(f10k_mid_share), 2) if f10k_mid_share else None,
        "avg_mid_ka_in_first10": round(mid_k / n, 2),
        "avg_mid_kills_in_first10": round(mid_k / n, 2),
        "avg_mid_sup_ka_in_first10": round(ms_k / n, 2),
        "avg_mid_sup_kills_in_first10": round(ms_k / n, 2),
        "mid_sup_driven_rate": round(driven / n, 3),
        "avg_duration_min": round(duration / 60, 1),
        "avg_f10k_time_when_got_s": round(sum(f10k_times) / len(f10k_times), 0) if f10k_times else None,
        "mids": mids.most_common(5),
        "pos4s": pos4s.most_common(5),
        "pace": dict(pace),
        "stance": dict(stance),
    }


def h2h(games: list[dict], team_a: str, team_b: str) -> list[dict]:
    return [game for game in games if {game["radiant"], game["dire"]} == {team_a, team_b}]


def main() -> None:
    games = json.loads((ROOT / "data" / "games.json").read_text())["games"]
    markets = json.loads((ROOT / "data" / "polymarket-playoffs.json").read_text())
    playoffs_preview = json.loads((ROOT / "data" / "playoffs.json").read_text())
    series = [
        {
            "id": "ubqf1",
            "teamA": "Iron Wing",
            "teamB": "Team Spirit",
            "when": match_when(playoffs_preview, "ubqf1", "8/20 10:00 CST"),
            "poly": series_price(markets, "Iron Wing vs Team Spirit"),
            "insight": "本届无直接交手。EWC 也没打过：1w 8/13、Spirit 10/15，帮不上。F10K=先到10杀。IW 先到10杀 56%，Spirit 50%。市场接近均势，G1 看谁先把比分堆到 10-x。",
        },
        {
            "id": "ubqf2",
            "teamA": "TEAM VISION",
            "teamB": "BoomBoys",
            "when": match_when(playoffs_preview, "ubqf2", "8/20 13:00 CST"),
            "poly": series_price(markets, "TEAM VISION vs BoomBoys"),
            "insight": "EWC 决赛就是这两队，VISION 3-1；瑞士又 2-0。系列低保有一个月内的重复样本。局2 BoomBoys 先到10杀但 VISION 仍赢——先到10杀不等于赢图，F10K 不要当低保。市场 80% 给系列，让分别盲目跟。",
        },
        {
            "id": "ubqf3",
            "teamA": "Team Liquid",
            "teamB": "Team Yandex",
            "when": match_when(playoffs_preview, "ubqf3", "8/20 16:00 CST"),
            "poly": series_price(markets, "Team Liquid vs Team Yandex"),
            "insight": "EWC 没有这两队交手。当时 Yandex 进四强（14/17）、Liquid 生存赛出局（9/16），不能倒过来当 8/20 的系列先验。本届 Liquid 先到10杀 71% 仍是八强最高，人头多半在边路。市场只给系列 54.5%。",
        },
        {
            "id": "ubqf4",
            "teamA": "Nigma Galaxy",
            "teamB": "Team Falcons",
            "when": match_when(playoffs_preview, "ubqf4", "8/20 19:00 CST"),
            "poly": series_price(markets, "Nigma Galaxy vs Team Falcons"),
            "insight": "本届无直接交手。EWC 两边都是 5–8、没打过。NGX 本届胜率 80% 但先到10杀只有 30%——赢图不靠堆前10人头。Falcons 先到10杀 59%。市场 65.5% 给 Falcons。若猜先到10杀，跟 Falcons，不要跟 NGX 系列混为一谈。",
        },
    ]
    playoffs = playoffs_preview
    poly = markets
    poly_slugs = [
        m["polySlug"]
        for m in playoffs.get("matches") or []
        if m.get("polySlug") and isinstance(m.get("teamA"), str) and isinstance(m.get("teamB"), str)
    ]
    daily_path = ROOT / "web" / "data" / "daily.json"
    daily = json.loads(daily_path.read_text()) if daily_path.exists() else None
    sims = json.loads((ROOT / "data" / "simulations.json").read_text())
    sim_by_id = {item["id"]: item for item in sims.get("known") or []}
    for item in series:
        item["h2hIds"] = [game["match_id"] for game in h2h(games, item["teamA"], item["teamB"])]
        item["profileA"] = team_profile(games, item["teamA"])
        item["profileB"] = team_profile(games, item["teamB"])
        item["sim"] = sim_by_id.get(item["id"])

    published = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " CST"
    bundle = {
        "asOf": published,
        "publishedAt": published,
        "note": "逐场页列 TI15 八强地图（含淘汰赛新局）。BP/F10K/胜率模拟 = TI15 100% + EWC 八强地图 45%。",
        "polySlugs": poly_slugs,
        "polymarket": poly,
        "teams": {name: team_profile(games, name) for name in EIGHT},
        "playoffs": playoffs,
        "daily": daily,
        "simulations": sims,
        "ewc": json.loads((ROOT / "data" / "ewc.json").read_text()),
        "f10kG1": build_report(),
        "iwSpiritH2h": load_iw_spirit_h2h(),
        "series": series,
        "games": games,
    }
    out = ROOT / "web" / "data" / "bundle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, ensure_ascii=False)
    out.write_text(payload)
    js_path = ROOT / "web" / "data.js"
    js_path.write_text("window.TI15_DATA = " + payload + ";\n")
    css = (ROOT / "web" / "styles.css").read_text()
    odds_js = (ROOT / "web" / "odds.js").read_text()
    app_js = (ROOT / "web" / "analysis.js").read_text()
    poly_asof = poly.get("asOf", "2026-08-17")[:16].replace("T", " ")
    standalone = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TI15 逐场分析 · 八强 80 局</title>
  <style>{css}</style>
</head>
<body>
  <div class="bg-grid"></div>
  <header class="topbar">
    <div class="brand"><span class="aegis">TI15</span><span>逐场分析</span></div>
    <div class="status" id="odds-status">Polymarket …</div>
    <button type="button" class="odds-refresh" id="odds-refresh" title="从 Polymarket 拉最新价格">刷新赔率</button>
  </header>
  <main>
    <section class="hero">
      <p class="kicker">只做八强的 TI15 场次</p>
      <h1>对阵图、BP 模拟、先到 10 杀、胜率和 Polymarket 回报率。</h1>
      <p class="lede">参与次数 = 击杀 + 助攻。每局至少 5 次 BP 模拟，再按本届战绩估先到 10 杀和胜率。</p>
    </section>
    <div class="filters" id="filters"></div>
    <div id="app">加载数据…</div>
  </main>
  <footer><p>数据：OpenDota league 19719 · 市场：Polymarket {poly_asof} · 点「刷新赔率」拉最新 · 非投注建议</p></footer>
  <script>window.TI15_DATA = {payload};</script>
  <script>{odds_js}</script>
  <script>{app_js}</script>
</body>
</html>
"""
    stand_path = ROOT / "web" / "standalone.html"
    stand_path.write_text(standalone)
    print("wrote", out, "bytes", out.stat().st_size)
    print("wrote", js_path, "bytes", js_path.stat().st_size)
    print("wrote", stand_path, "bytes", stand_path.stat().st_size)


if __name__ == "__main__":
    main()
