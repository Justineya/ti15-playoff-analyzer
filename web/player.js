(function () {
  const app = document.getElementById("app");
  const asof = document.getElementById("player-asof");
  const IMG = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/";

  const ROLE = { pos1: "1", pos2: "中", pos3: "3", pos4: "4", pos5: "5" };
  const KIND = {
    win: "胜",
    meta_weak: "版本坑",
    did_not_close: "没收",
    wrong_role: "别打这位置",
    farm_collapse: "崩了",
    other_loss: "负",
  };

  function pct(v) {
    if (v == null || Number.isNaN(Number(v))) return null;
    return Math.round(Number(v) * 100);
  }

  function pctLabel(v) {
    const n = pct(v);
    return n == null ? "—" : n + "%";
  }

  function bar(v, cls) {
    const n = pct(v);
    const w = n == null ? 0 : Math.max(4, Math.min(100, n));
    return `<span class="pb ${cls || ""}"><i style="width:${w}%"></i></span>`;
  }

  function portrait(file, name) {
    if (file) {
      return `<img class="ph" src="${IMG}${file}.png" alt="${name || ""}" width="84" height="47" />`;
    }
    return `<span class="ph ph-empty">${(name || "?").slice(0, 2)}</span>`;
  }

  function record(s) {
    const g = (s && s.games) || 0;
    const w = (s && s.wins) || 0;
    return { w, l: g - w, g };
  }

  function render(player, brief) {
    const s = player.summary || {};
    const games = player.games || [];
    const ranked = player.rankedWl || {};
    asof.textContent = (player.asOf || "").replace(" CST", "");

    const strip = games
      .slice()
      .reverse()
      .map((g) => `<i class="${g.win ? "w" : "l"}" title="${g.hero}"></i>`)
      .join("");

    const roles = ["pos2", "pos3", "pos1"]
      .map((key) => {
        const r = record((s.roles || {})[key]);
        const dots = games
          .filter((g) => (g.role || "unknown") === key)
          .map((g) => `<i class="${g.win ? "w" : "l"}"></i>`)
          .join("");
        return `<div class="role-tile">
          <em>${ROLE[key]}</em>
          <strong>${r.w}-${r.l}</strong>
          <span class="dots">${dots || "—"}</span>
        </div>`;
      })
      .join("");

    const cmp = [
      ["对线", (s.winAvg || {}).laneEfficiency, (s.lossAvg || {}).laneEfficiency],
      ["GPM", (s.winAvg || {}).gpmBr, (s.lossAvg || {}).gpmBr],
      ["推塔", (s.winAvg || {}).towerBr, (s.lossAvg || {}).towerBr],
    ]
      .map(([lab, a, b]) => `<div class="cmp-row">
        <span>${lab}</span>
        ${bar(a, "win")}
        <b>${pctLabel(a)}</b>
        ${bar(b, "loss")}
        <b class="dim">${pctLabel(b)}</b>
      </div>`)
      .join("");

    const focusById = {};
    (brief.focus || []).forEach((row) => {
      if (row.matchId) focusById[String(row.matchId)] = row;
    });

    const tags = (brief.focus || [])
      .map((row) => {
        const g = games.find((x) => String(x.matchId) === String(row.matchId)) || {};
        return `<a class="tag tag-${row.kind}" href="${g.opendota || "#"}">
          ${portrait(g.heroFile || row.heroFile, row.hero)}
          <span><b>${KIND[row.kind] || row.kind}</b>${row.hero || ""}</span>
        </a>`;
      })
      .join("");

    const cards = games
      .map((g) => {
        const mark = g.win ? "W" : "L";
        const tag = focusById[String(g.matchId)];
        const chip = tag ? `<em class="chip chip-${tag.kind}">${KIND[tag.kind] || tag.note || ""}</em>` : "";
        return `<a class="mc ${g.win ? "win" : "loss"}" href="${g.opendota || "#"}">
          ${portrait(g.heroFile, g.hero)}
          <div class="mc-body">
            <div class="mc-top">
              <strong class="wl">${mark}</strong>
              <span class="nm">${g.hero || "—"}</span>
              <span class="rl">${ROLE[g.role] || "—"}</span>
              <span class="kd">${g.kills ?? "—"}/${g.deaths ?? "—"}/${g.assists ?? "—"}</span>
              ${chip}
            </div>
            <div class="mc-bars">
              <label>线</label>${bar(g.laneEfficiency)}
              <label>金</label>${bar(g.gpmBr)}
              <label>塔</label>${bar(g.towerBr, g.win ? "" : "loss")}
            </div>
          </div>
        </a>`;
      })
      .join("");

    const pool = (s.heroes || [])
      .map((h) => {
        const file = (games.find((g) => g.hero === h.hero) || {}).heroFile;
        const wr = h.divine && h.divine.wr != null ? pctLabel(h.divine.wr) : "—";
        return `<div class="pool">
          ${portrait(file, h.hero)}
          <strong>${h.wins}-${h.games - h.wins}</strong>
          <span>${wr}</span>
        </div>`;
      })
      .join("");

    app.innerHTML = `
      <section class="player-head">
        <div class="score">
          <b>${s.wins || 0}</b><span>-</span><b class="loss-n">${s.losses || 0}</b>
        </div>
        <div class="head-meta">
          <p class="kicker">Immortal #${player.leaderboardRank || "—"} · ${brief.positioning || "主中"}</p>
          <div class="strip">${strip}</div>
          <p class="career">${ranked.win || 0}-${ranked.lose || 0} 生涯排位</p>
        </div>
      </section>
      <section class="role-row">${roles}</section>
      <section class="cmp">
        <div class="cmp-lab"><span>胜</span><span class="dim">负</span></div>
        ${cmp}
      </section>
      <section class="tags">${tags}</section>
      <section class="mcs">${cards}</section>
      <section class="pools">${pool}</section>
    `;
  }

  Promise.all([
    fetch("./data/player.json?v=scan").then((r) => (r.ok ? r.json() : null)),
    fetch("./data/player-briefing.json?v=scan").then((r) => (r.ok ? r.json() : {})),
  ])
    .then(([player, brief]) => {
      if (!player) {
        app.textContent = "还没有战绩。";
        return;
      }
      render(player, brief || {});
    })
    .catch(() => {
      app.textContent = "刷新一下。";
    });
})();
