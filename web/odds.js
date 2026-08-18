/** Live Polymarket odds fetch + client-side betting card recompute. */
(function () {
  const GAMMA = "https://gamma-api.polymarket.com";

  const TAGS = {
    "Iron Wing": ["iron", "iw"],
    "Team Spirit": ["spirit"],
    "TEAM VISION": ["vision", "vsn"],
    BoomBoys: ["boom"],
    "Team Liquid": ["liquid"],
    "Team Yandex": ["yandex"],
    "Nigma Galaxy": ["nigma", "ngx"],
    "Team Falcons": ["falcon", "flc"],
  };

  function parseField(raw) {
    if (Array.isArray(raw)) return raw;
    if (typeof raw === "string") {
      try {
        return JSON.parse(raw);
      } catch {
        return [];
      }
    }
    return [];
  }

  function normalizeMarket(m) {
    const outcomes = parseField(m.outcomes);
    const prices = parseField(m.outcomePrices || m.prices).map(Number);
    return { question: m.question || "", outcomes, prices };
  }

  function polyMarkets(event) {
    const out = {};
    for (const m of event?.markets || []) {
      const row = normalizeMarket(m);
      const q = row.question;
      if (row.outcomes.length !== 2 || row.prices.length !== 2) continue;
      if (q.includes("(BO3)") && !q.includes("Game")) out.series = row;
      else if (q.includes("Game 1 Winner")) out.g1 = row;
      else if (q.includes("Game 2 Winner")) out.g2 = row;
      else if (q.includes("O/U 2.5")) out.ou25 = row;
      else if (q.includes("Handicap")) out.handicap = row;
    }
    return out;
  }

  function priceForName(prices, name) {
    for (const [k, v] of Object.entries(prices)) {
      if (name.toLowerCase().includes(k.toLowerCase()) || k.toLowerCase().includes(name.toLowerCase())) return v;
      for (const t of TAGS[name] || []) {
        if (k.toLowerCase().includes(t)) return v;
      }
    }
    return null;
  }

  function roiRow(label, pick, modelP, marketP, sampleN, h2hN) {
    if (marketP == null || marketP <= 0) {
      return {
        market: label,
        pick,
        modelP: Math.round(modelP * 1000) / 1000,
        marketP: null,
        roi: null,
        ev: null,
        action: "无盘口",
        note: "Polymarket 没有这格",
      };
    }
    const roi = modelP / marketP - 1;
    const ev = modelP - marketP;
    const gap = Math.abs(modelP - marketP);
    let action;
    if (sampleN < 8) action = "样本太薄，空仓";
    else if (gap >= 0.2 && h2hN === 0) action = "和市场差太大，只观察";
    else if (gap >= 0.15 && h2hN === 0) action = "观察 / 极小注";
    else if (roi >= 0.18 && modelP >= 0.38 && roi < 0.55) action = "小注买";
    else if (roi >= 0.08 && modelP >= 0.42) action = "观察 / 极小注";
    else if (roi <= -0.12) action = "市场更贵，不买";
    else action = "没有明显正期望，空仓";
    return {
      market: label,
      pick,
      modelP: Math.round(modelP * 1000) / 1000,
      marketP: Math.round(marketP * 1000) / 1000,
      odds: Math.round((1 / marketP) * 100) / 100,
      roi: Math.round(roi * 1000) / 1000,
      ev: Math.round(ev * 1000) / 1000,
      action,
      note: `买 YES 成本 ${Math.round(marketP * 1000) / 1000}，模型 ${Math.round(modelP * 1000) / 1000}，期望回报率 ${Math.round(roi * 1000) / 10}%`,
    };
  }

  function bestSide(modelA, modelB, mkt, nameA, nameB) {
    const pick = modelA >= modelB ? nameA : nameB;
    const modelP = Math.max(modelA, modelB);
    if (!mkt) return { pick, modelP, marketP: null };
    const prices = { [mkt.outcomes[0]]: mkt.prices[0], [mkt.outcomes[1]]: mkt.prices[1] };
    return { pick, modelP, marketP: priceForName(prices, pick) };
  }

  function handicapSide(sim, market) {
    const a = sim.teamA;
    const b = sim.teamB;
    const pASweep = sim.series.pCoverMinus15A;
    const pBSweep = Math.round(sim.pMapB ** 2 * 1000) / 1000;
    if (!market) {
      const pick = pASweep >= pBSweep ? a : b;
      return { pick, modelP: Math.max(pASweep, pBSweep), marketP: null };
    }
    const q = (market.question || "").toLowerCase();
    const prices = { [market.outcomes[0]]: market.prices[0], [market.outcomes[1]]: market.prices[1] };
    let minusTeam = null;
    const minusPos = q.indexOf("-1.5");
    if (minusPos >= 0) {
      const window = q.slice(Math.max(0, minusPos - 28), minusPos);
      for (const name of [a, b]) {
        const tags = [...(TAGS[name] || []), name.toLowerCase(), name.split(" ").pop().toLowerCase()];
        if (tags.some((t) => window.includes(t))) {
          minusTeam = name;
          break;
        }
      }
    }
    if (!minusTeam) minusTeam = a;
    const plusTeam = minusTeam === a ? b : a;
    const pMinus = minusTeam === a ? pASweep : pBSweep;
    const pPlus = 1 - pMinus;
    const priceMinus = priceForName(prices, minusTeam);
    const pricePlus = priceForName(prices, plusTeam);
    const roiM = priceMinus ? pMinus / priceMinus - 1 : -9;
    const roiP = pricePlus ? pPlus / pricePlus - 1 : -9;
    if (roiM >= roiP) return { pick: `${minusTeam} -1.5`, modelP: pMinus, marketP: priceMinus };
    return { pick: `${plusTeam} +1.5`, modelP: pPlus, marketP: pricePlus };
  }

  function bettingCard(sim, poly, sampleN) {
    const a = sim.teamA;
    const b = sim.teamB;
    const series = sim.series;
    const g1 = sim.maps[0];
    const h2hN = g1?.sims?.[0]?.h2hGames || 0;
    const m = poly || {};
    const rows = [];
    let side = bestSide(series.pSeriesA, series.pSeriesB, m.series, a, b);
    rows.push(roiRow("系列胜者", side.pick, side.modelP, side.marketP, sampleN, h2hN));
    side = bestSide(g1.pWinA, g1.pWinB, m.g1, a, b);
    rows.push(roiRow("第一局", side.pick, side.modelP, side.marketP, sampleN, h2hN));
    if (m.ou25) {
      const overP = m.ou25.outcomes[0].toLowerCase().startsWith("over") ? m.ou25.prices[0] : m.ou25.prices[1];
      const underP = 1 - overP;
      const roiO = series.pOver / overP - 1;
      const roiU = series.pUnder / underP - 1;
      if (roiO >= roiU) rows.push(roiRow("总局数 O/U 2.5", "Over 2.5", series.pOver, overP, sampleN, h2hN));
      else rows.push(roiRow("总局数 O/U 2.5", "Under 2.5", series.pUnder, underP, sampleN, h2hN));
    } else {
      rows.push(roiRow("总局数 O/U 2.5", "Over 2.5", series.pOver, null, sampleN, h2hN));
    }
    if (m.handicap) {
      side = handicapSide(sim, m.handicap);
      rows.push(roiRow("让分", side.pick, side.modelP, side.marketP, sampleN, h2hN));
    }
    side = bestSide(sim.pF10A, sim.pF10B, null, a, b);
    rows.push(roiRow("先到 10 杀（无盘，仅模型）", side.pick, side.modelP, side.marketP, sampleN, h2hN));
    const buys = rows.filter((r) => r.roi != null && r.roi >= 0.08 && (r.action || "").includes("买"));
    const plan = buys.length
      ? `若只按模型 vs Polymarket 差价：${buys
          .slice(0, 3)
          .map((r) => `${r.market}买${r.pick}（期望回报率 ${Math.round(r.roi * 1000) / 10}%）`)
          .join("；")}。单场合计不超过银行资金 3%。`
      : "这系列没有达到小注门槛的正期望格，建议空仓，只看模拟。";
    return { rows, plan };
  }

  async function fetchEvent(slug) {
    const url = `${GAMMA}/events?slug=${encodeURIComponent(slug)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Polymarket ${slug}: HTTP ${res.status}`);
    const rows = await res.json();
    if (!rows?.length) throw new Error(`Polymarket ${slug}: 无事件`);
    const event = rows[0];
    return {
      slug: event.slug || slug,
      title: event.title || "",
      volume: event.volume,
      markets: (event.markets || []).map(normalizeMarket),
    };
  }

  function sampleN(data, teamA, teamB) {
    const ta = data.teams?.[teamA]?.games || 0;
    const tb = data.teams?.[teamB]?.games || 0;
    return ta && tb ? Math.min(ta, tb) : ta || tb || 0;
  }

  function seriesPolyFromMarkets(event) {
    for (const m of event.markets || []) {
      const q = m.question || "";
      if (q.includes("(BO3)") && !q.includes("Game")) {
        return {
          outcomes: m.outcomes,
          prices: m.prices.map(Number),
          volume: event.volume,
          slug: event.slug,
        };
      }
    }
    return null;
  }

  async function refreshOdds(data) {
    const slugs = data.polySlugs || [];
    if (!slugs.length) throw new Error("没有 polySlug 配置");
    const events = await Promise.all(slugs.map(fetchEvent));
    const bySlug = Object.fromEntries(events.map((e) => [e.slug, e]));
    const asOf = new Date().toISOString();

    for (const sim of data.simulations?.known || []) {
      const slug = sim.polySlug;
      const event = slug ? bySlug[slug] : null;
      if (!event) continue;
      const markets = polyMarkets(event);
      sim.poly = markets;
      sim.polyLive = seriesPolyFromMarkets(event);
      sim.betting = bettingCard(sim, markets, sampleN(data, sim.teamA, sim.teamB));
    }

    for (const s of data.series || []) {
      const match = (data.playoffs?.matches || []).find((m) => m.id === s.id);
      const slug = match?.polySlug;
      const event = slug ? bySlug[slug] : null;
      if (event) s.poly = seriesPolyFromMarkets(event);
    }

    data.polymarket = {
      asOf,
      source: GAMMA,
      events,
    };
    return { asOf, count: events.length };
  }

  function formatAsOf(iso) {
    if (!iso) return "未刷新";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
  }

  window.TI15_ODDS = { refreshOdds, formatAsOf, polyMarkets, bettingCard };
})();
