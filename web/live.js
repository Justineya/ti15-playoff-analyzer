/** Live match scoreboard from OpenDota (spectator delay, no video). */
(function () {
  const LIVE = "https://api.opendota.com/api/live";
  const FALLBACK = "./data/live.json";
  const TI_LEAGUE = 19719;
  const EXTRA_IDS = {
    "TEAM VISION": [9572001, 9824702],
    "Team Liquid": [2163],
    "Nigma Galaxy": [10136357],
    "Team Spirit": [7119388],
    "Iron Wing": [10150413, 10182357, 8291895],
    "Team Falcons": [9247354],
    BoomBoys: [8255888],
    "Team Yandex": [9823272],
  };
  const MATCH = "https://api.opendota.com/api/matches/";
  const seenIds = {};
  const finishedCache = {};
  const missAt = {};

  function rememberId(teamA, teamB, id) {
    id = String(id || "");
    if (!id) return;
    const k = `${teamA}|${teamB}`;
    const arr = seenIds[k] || (seenIds[k] = []);
    if (!arr.includes(id)) arr.push(id);
  }

  function knownIds(teamA, teamB, lp) {
    const k = `${teamA}|${teamB}`;
    return [...new Set([...(seenIds[k] || []), ...((lp && lp.matchIds) || [])].map(String).filter(Boolean))];
  }

  function winnerOfMatch(detail, teamA, teamB, idMap) {
    if (!detail || typeof detail.radiant_win !== "boolean") return null;
    const rad = Number(detail.radiant_team_id || detail.radiant_team?.team_id || 0);
    const dire = Number(detail.dire_team_id || detail.dire_team?.team_id || 0);
    const idsA = new Set(idMap?.[teamA] || EXTRA_IDS[teamA] || []);
    const idsB = new Set(idMap?.[teamB] || EXTRA_IDS[teamB] || []);
    let aIsRadiant = null;
    if (idsA.has(rad) && idsB.has(dire)) aIsRadiant = true;
    else if (idsA.has(dire) && idsB.has(rad)) aIsRadiant = false;
    if (aIsRadiant == null) return null;
    return (aIsRadiant ? detail.radiant_win : !detail.radiant_win) ? "A" : "B";
  }

  function scoreFromWinners(results) {
    let a = 0;
    let b = 0;
    for (const w of results) {
      if (w === "A") a += 1;
      else if (w === "B") b += 1;
    }
    if (!a && !b) return null;
    return `${a}-${b}`;
  }

  async function lookupFinished(id) {
    id = String(id || "");
    if (!id) return null;
    if (finishedCache[id]) return finishedCache[id];
    const now = Date.now();
    if (missAt[id] && now - missAt[id] < 20000) return null;
    try {
      const m = await fetchJson(MATCH + id);
      if (m && typeof m.radiant_win === "boolean") {
        finishedCache[id] = m;
        return m;
      }
    } catch {
      /* match may still be unparsed */
    }
    missAt[id] = now;
    return null;
  }

  async function finishedScore(teamA, teamB, lp, idMap, skipId) {
    const skip = String(skipId || "");
    const ids = knownIds(teamA, teamB, lp).filter((id) => id && id !== skip);
    if (!ids.length) return null;
    const rows = await Promise.all(ids.map(lookupFinished));
    const winners = [];
    for (let i = 0; i < ids.length; i += 1) {
      const w = winnerOfMatch(rows[i], teamA, teamB, idMap);
      if (!w) break;
      winners.push(w);
    }
    const score = scoreFromWinners(winners);
    if (!score) return null;
    return { score, maps: winners.length };
  }

  function teamIdMap(playoffs) {
    const out = {};
    for (const t of playoffs?.teams || []) {
      const extra = EXTRA_IDS[t.name] || [];
      out[t.name] = [...new Set([t.opendotaId, ...extra].filter(Boolean).map(Number))];
    }
    for (const [name, ids] of Object.entries(EXTRA_IDS)) {
      if (!out[name]) out[name] = ids.slice();
    }
    return out;
  }

  function isActive(g) {
    return Number(g.deactivate_time ?? g.deactivateTime ?? 0) <= 0;
  }

  function pairGames(games, teamA, teamB, idMap) {
    const idsA = new Set(idMap?.[teamA] || EXTRA_IDS[teamA] || []);
    const idsB = new Set(idMap?.[teamB] || EXTRA_IDS[teamB] || []);
    return (games || []).filter((g) => {
      const r = Number(g.team_id_radiant ?? g.radiant?.id ?? 0);
      const d = Number(g.team_id_dire ?? g.dire?.id ?? 0);
      if ((idsA.has(r) && idsB.has(d)) || (idsA.has(d) && idsB.has(r))) return true;
      const names = [g.team_name_radiant || g.radiant?.name, g.team_name_dire || g.dire?.name];
      return names.includes(teamA) && names.includes(teamB);
    });
  }

  function gameClock(g) {
    return Number(g.game_time ?? g.gameTime ?? 0);
  }

  function pickGame(games, teamA, teamB, idMap) {
    const active = pairGames(games, teamA, teamB, idMap).filter(isActive);
    if (!active.length) return null;
    return active.slice().sort((a, b) => {
      const clock = gameClock(a) - gameClock(b);
      if (clock) return clock;
      return String(a.match_id ?? a.matchId ?? "").localeCompare(String(b.match_id ?? b.matchId ?? ""));
    })[0];
  }

  function mergeGames(primary, extra) {
    const out = [];
    const seen = new Set();
    for (const g of [...(primary || []), ...(extra || [])]) {
      const id = String(g.match_id ?? g.matchId ?? "");
      const key = id || JSON.stringify(g);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(g);
    }
    return out;
  }

  function rawPlayers(game) {
    if (game.players && game.players[0] && game.players[0].heroId != null) {
      return (game.players || []).map((p) => ({
        account_id: p.accountId,
        hero_id: p.heroId,
        name: p.name,
        team: p.team,
        team_slot: p.slot,
      }));
    }
    return game.players || [];
  }

  function heroOf(id, heroes) {
    if (!id) return { name: "", slug: "" };
    const row = heroes?.[id] || heroes?.[String(id)];
    if (!row) return { name: `#${id}`, slug: "" };
    return { name: row.name || row.localized_name || "", slug: row.slug || "" };
  }

  function phaseOf(game) {
    const t = Number(game.game_time ?? game.gameTime);
    const picked = rawPlayers(game).filter((p) => Number(p.hero_id || 0) > 0).length;
    if (Number.isNaN(t)) return "在线";
    if (t < 0 && picked < 10) return "选人中";
    if (t < 0) return "出兵前";
    return "进行中";
  }

  function summarize(game, teamA, teamB, heroes, idMap) {
    if (!game) return null;
    const radId = Number(game.team_id_radiant ?? game.radiant?.id ?? 0);
    const direId = Number(game.team_id_dire ?? game.dire?.id ?? 0);
    const radName = game.radiant?.name || game.team_name_radiant || "天辉";
    const direName = game.dire?.name || game.team_name_dire || "夜魇";
    const idsA = new Set(idMap?.[teamA] || EXTRA_IDS[teamA] || []);
    const aIsRadiant = idsA.has(radId) || (!idsA.has(direId) && radName === teamA);
    const players = rawPlayers(game)
      .slice()
      .sort((x, y) => Number(x.team_slot || 0) - Number(y.team_slot || 0));
    const pack = (teamBit) =>
      players
        .filter((p) => Number(p.team) === teamBit)
        .map((p) => {
          const hid = Number(p.hero_id || 0);
          const h = heroOf(hid, heroes);
          return { name: p.name || "", heroId: hid, hero: h.name, slug: h.slug };
        });
    const radScore = Number(game.radiant_score ?? game.radiantScore ?? 0);
    const direScore = Number(game.dire_score ?? game.direScore ?? 0);
    const lead = Number(game.radiant_lead ?? game.radiantLead ?? 0);
    return {
      matchId: String(game.match_id ?? game.matchId ?? ""),
      seriesId: game.series_id ?? game.seriesId,
      phase: phaseOf(game),
      gameTime: Number(game.game_time ?? game.gameTime ?? 0),
      delay: Number(game.delay || 0),
      spectators: Number(game.spectators || 0),
      lastUpdate: Number(game.last_update_time ?? game.lastUpdate ?? 0),
      aIsRadiant,
      teamA,
      teamB,
      scoreA: aIsRadiant ? radScore : direScore,
      scoreB: aIsRadiant ? direScore : radScore,
      leadA: aIsRadiant ? lead : -lead,
      playersA: pack(aIsRadiant ? 0 : 1),
      playersB: pack(aIsRadiant ? 1 : 0),
      radiantName: radName,
      direName: direName,
    };
  }

  async function fetchJson(url) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 8000);
    try {
      const res = await fetch(url, { cache: "no-store", signal: ac.signal, credentials: "omit" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function fetchFeed(data, teamA, teamB, matchId) {
    const idMap = teamIdMap(data?.playoffs);
    const heroes = data?.heroes || {};
    const polledAt = Date.now();
    const settled = await Promise.allSettled([fetchJson(LIVE), fetchJson(FALLBACK + `?t=${polledAt}`)]);
    const liveRes = settled[0];
    const snapRes = settled[1];
    const snap = snapRes.status === "fulfilled" ? snapRes.value : null;
    let games = [];
    let source = LIVE;
    if (liveRes.status === "fulfilled") {
      const raw = liveRes.value;
      games = Array.isArray(raw) ? raw : raw?.games || [];
      if (snap?.games) games = mergeGames(games, snap.games);
    } else if (snap?.games) {
      games = snap.games;
      source = FALLBACK;
    } else {
      const err = liveRes.status === "rejected" ? liveRes.reason : "no live";
      return { ok: false, error: String(err?.message || err), source: LIVE, polledAt };
    }
    const lp = (snap && snap.matches && matchId && snap.matches[matchId]) || null;
    if (lp?.matchIds) {
      for (const id of lp.matchIds) rememberId(teamA, teamB, id);
    }
    for (const g of pairGames(games, teamA, teamB, idMap)) {
      rememberId(teamA, teamB, g.match_id ?? g.matchId);
    }
    const game = pickGame(games, teamA, teamB, idMap);
    const liveId = game ? String(game.match_id ?? game.matchId ?? "") : "";
    const finished = await finishedScore(teamA, teamB, lp, idMap, liveId);
    const ids = knownIds(teamA, teamB, lp);
    let mapNumber = ids.length || 1;
    if (liveId && ids.includes(liveId)) mapNumber = ids.indexOf(liveId) + 1;
    else if (finished?.maps) mapNumber = finished.maps + (liveId ? 1 : 0);
    const series = { ...(lp || {}) };
    if (finished?.score && !series.score) series.score = finished.score;
    if (ids.length) series.matchIds = ids;
    if (!game) {
      return {
        ok: true,
        empty: true,
        source,
        n: games.length,
        polledAt,
        datetime: series.datetime || null,
        series,
        finished,
        mapNumber,
      };
    }
    const summary = summarize(game, teamA, teamB, heroes, idMap);
    rememberId(teamA, teamB, summary.matchId);
    return {
      ok: true,
      source,
      game: summary,
      polledAt,
      datetime: series.datetime || null,
      series,
      finished,
      mapNumber,
    };
  }

  window.TI15_LIVE = {
    fetchFeed,
    pickGame,
    pairGames,
    summarize,
    teamIdMap,
    phaseOf,
    isActive,
    winnerOfMatch,
    scoreFromWinners,
  };
})();
