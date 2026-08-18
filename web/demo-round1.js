/** Fake first-round results so you can preview how later matches fill in. */
(function () {
  const data = window.TI15_DATA;
  if (!data?.playoffs?.matches) return;

  data.demo = {
    title: "模拟 · 第一轮打完",
    note: "假比分，只为看下一场怎么换队。正式站不会用这些结果。",
  };

  const results = {
    ubqf1: { winner: "Iron Wing", loser: "Team Spirit", score: "2-1" },
    ubqf2: { winner: "TEAM VISION", loser: "BoomBoys", score: "2-0" },
    ubqf3: { winner: "Team Liquid", loser: "Team Yandex", score: "2-1" },
    ubqf4: { winner: "Team Falcons", loser: "Nigma Galaxy", score: "2-0" },
  };

  for (const m of data.playoffs.matches) {
    const r = results[m.id];
    if (!r) continue;
    m.status = "completed";
    m.winner = r.winner;
    m.loser = r.loser;
    m.score = r.score;
    m.mapsPlayed = r.score === "2-0" ? 2 : 3;
  }

  const resolveSlot = (slot, byId) => {
    if (typeof slot === "string") return slot;
    const src = byId[slot?.from];
    if (!src) return slot;
    const name = slot?.as === "winner" ? src.winner : src.loser;
    return typeof name === "string" ? name : slot;
  };

  for (let i = 0; i < 6; i++) {
    const byId = Object.fromEntries(data.playoffs.matches.map((m) => [m.id, m]));
    for (const m of data.playoffs.matches) {
      const a = resolveSlot(m.teamA, byId);
      const b = resolveSlot(m.teamB, byId);
      m.teamA = a;
      m.teamB = b;
      if (typeof a === "string" && typeof b === "string") {
        m.polyTitle = `${a} vs ${b}`;
        if (m.status === "awaiting") m.status = "scheduled";
      }
    }
  }

  const pickSim = (id, a, b) => {
    const keys = [`${id}__${a}__${b}`, `${id}__${b}__${a}`, id];
    const pool = [...(data.simulations?.known || []), ...(data.simulations?.scenarios || [])];
    return pool.find((s) => keys.includes(s.id));
  };

  const next = data.playoffs.matches.find((m) => m.id === "lbr1a");
  const sim = next && typeof next.teamA === "string" ? pickSim(next.id, next.teamA, next.teamB) : null;
  const p = sim?.series?.pSeriesA;
  const leanA = p == null ? null : p >= 0.5;
  const lean = leanA == null ? null : leanA ? next.teamA : next.teamB;
  const pLean = leanA == null ? null : leanA ? p : 1 - p;

  data.daily = {
    asOf: "模拟",
    kind: "next-series",
    headline: `模拟第一轮结束。下一把 ${next?.teamA || "待定"} vs ${next?.teamB || "待定"}${
      lean ? `，看好 ${lean}（${Math.round(pLean * 100)}%）` : ""
    }。`,
    narrative:
      "假设：IW 2-1 Spirit，VISION 2-0 BoomBoys，Liquid 2-1 Yandex，Falcons 2-0 NGX。败者组第一场变成 Spirit vs BoomBoys；胜者组半决赛是 IW vs VISION、Liquid vs Falcons。",
    previous: data.playoffs.matches.find((m) => m.id === "ubqf4"),
    next,
    todayResults: data.playoffs.matches.filter((m) => results[m.id]),
  };
})();
