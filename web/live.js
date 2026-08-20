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

  function pickGame(games, teamA, teamB, idMap) {
    const idsA = new Set(idMap?.[teamA] || EXTRA_IDS[teamA] || []);
    const idsB = new Set(idMap?.[teamB] || EXTRA_IDS[teamB] || []);
    const list = games || [];
    const byId = list.find((g) => {
      const r = Number(g.team_id_radiant ?? g.radiant?.id ?? 0);
      const d = Number(g.team_id_dire ?? g.dire?.id ?? 0);
      return (idsA.has(r) && idsB.has(d)) || (idsA.has(d) && idsB.has(r));
    });
    if (byId) return byId;
    return (
      list.find((g) => {
        if (Number(g.league_id ?? g.leagueId) !== TI_LEAGUE) return false;
        const names = [g.team_name_radiant || g.radiant?.name, g.team_name_dire || g.dire?.name];
        return names.includes(teamA) && names.includes(teamB);
      }) || null
    );
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

  async function fetchFeed(data, teamA, teamB) {
    const idMap = teamIdMap(data?.playoffs);
    const heroes = data?.heroes || {};
    let raw = null;
    let source = LIVE;
    try {
      raw = await fetchJson(LIVE);
    } catch (err) {
      try {
        const snap = await fetchJson(FALLBACK + `?t=${Date.now()}`);
        raw = snap.games || [];
        source = FALLBACK;
      } catch {
        return { ok: false, error: String(err?.message || err), source: LIVE };
      }
    }
    const games = Array.isArray(raw) ? raw : raw?.games || [];
    const game = pickGame(games, teamA, teamB, idMap);
    if (!game) {
      return { ok: true, empty: true, source, n: games.length };
    }
    return { ok: true, source, game: summarize(game, teamA, teamB, heroes, idMap) };
  }

  window.TI15_LIVE = { fetchFeed, pickGame, summarize, teamIdMap, phaseOf };
})();
