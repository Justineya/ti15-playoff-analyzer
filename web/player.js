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

  function heroName(game, row) {
    return (game && game.heroZh) || (row && row.heroZh) || (row && row.hero) || (game && game.hero) || "—";
  }

  function portrait(file, name) {
    if (file) {
      return `<img class="ph" src="${IMG}${file}.png" alt="${name || ""}" width="84" height="47" />`;
    }
    return `<span class="ph ph-empty">${(name || "?").slice(0, 2)}</span>`;
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function diagnosis(brief) {
    const points = (brief.points || []).map((p) => String(p || "").trim()).filter(Boolean);
    const headline = (brief.headline || "").trim();
    const lede = (brief.lede || "").trim();
    if (!headline && !lede && !points.length) return "";
    const items = points.map((p) => `<li>${esc(p)}</li>`).join("");
    return `<section class="dx">
      <p class="dx-k">${esc(brief.scopeLabel || "分析")}</p>
      ${headline ? `<p class="dx-h">${esc(headline)}</p>` : ""}
      ${lede ? `<p class="dx-lede">${esc(lede)}</p>` : ""}
      ${items ? `<ul class="dx-list">${items}</ul>` : ""}
    </section>`;
  }

  function highlightIds(brief) {
    return new Set((brief.sessionMatchIds || brief.newMatchIds || []).map(String).filter(Boolean));
  }

  function mean(rows, key) {
    const xs = rows.map((g) => g[key]).filter((v) => v != null && !Number.isNaN(Number(v)));
    if (!xs.length) return null;
    return xs.reduce((a, b) => a + Number(b), 0) / xs.length;
  }

  function clock(g) {
    const w = g.when || "";
    return w.length >= 16 ? w.slice(11, 16) : "";
  }

  function render(player, brief) {
    const s = player.summary || {};
    const ranked = player.rankedWl || {};
    const games = (player.games || [])
      .slice()
      .sort((a, b) => (b.startTime || 0) - (a.startTime || 0));
    const fresh = highlightIds(brief);
    asof.textContent = (player.asOf || "").replace(" CST", "");

    const wins = games.filter((g) => g.win);
    const losses = games.filter((g) => !g.win);

    const strip = games
      .slice()
      .reverse()
      .map((g) => `<i class="${g.win ? "w" : "l"}" title="${heroName(g)}"></i>`)
      .join("");

    const cmp = [
      ["对线", mean(wins, "laneEfficiency"), mean(losses, "laneEfficiency")],
      ["GPM", mean(wins, "gpmBr"), mean(losses, "gpmBr")],
      ["推塔", mean(wins, "towerBr"), mean(losses, "towerBr")],
    ]
      .filter(([, a, b]) => a != null || b != null)
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
      .filter((row) => games.some((g) => String(g.matchId) === String(row.matchId)))
      .map((row) => {
        const g = games.find((x) => String(x.matchId) === String(row.matchId)) || {};
        return `<a class="tag tag-${row.kind}" href="${g.opendota || "#"}">
          ${portrait(g.heroFile || row.heroFile, heroName(g, row))}
          <span><b>${row.note || KIND[row.kind] || row.kind}</b>${heroName(g, row)}</span>
        </a>`;
      })
      .join("");

    const cards = games
      .map((g) => {
        const mark = g.win ? "W" : "L";
        const tag = focusById[String(g.matchId)];
        const isNew = fresh.has(String(g.matchId));
        const chipText = (tag && (tag.note || KIND[tag.kind])) || (isNew ? "新" : "");
        const chip = chipText
          ? `<em class="chip ${tag ? "chip-" + tag.kind : "chip-new"}">${chipText}</em>`
          : "";
        const lane = ROLE[g.role] || clock(g) || "—";
        const dur = g.durationMin != null ? Math.round(g.durationMin) + "′" : "";
        return `<a class="mc ${g.win ? "win" : "loss"}${isNew ? " fresh" : ""}" href="${g.opendota || "#"}">
          ${portrait(g.heroFile, heroName(g, tag))}
          <div class="mc-body">
            <div class="mc-top">
              <strong class="wl">${mark}</strong>
              <span class="nm">${heroName(g, tag)}</span>
              <span class="rl">${lane}</span>
              <span class="kd">${g.kills ?? "—"}/${g.deaths ?? "—"}/${g.assists ?? "—"}</span>
              <span class="dur">${dur}</span>
              ${chip}
            </div>
            <div class="mc-bars">
              <label>金</label>${bar(g.gpmBr)}
              <label>塔</label>${bar(g.towerBr, g.win ? "" : "loss")}
              <label>伤</label>${bar(g.damageBr, g.win ? "" : "loss")}
            </div>
          </div>
        </a>`;
      })
      .join("");

    app.innerHTML = `
      <section class="player-head">
        <div class="score">
          <b>${s.wins || wins.length}</b><span>-</span><b class="loss-n">${s.losses || losses.length}</b>
        </div>
        <div class="head-meta">
          <p class="kicker">Immortal #${player.leaderboardRank || "—"} · ${esc(brief.positioning || "主三")}</p>
          <div class="strip">${strip}</div>
          <p class="career">${ranked.win || 0}-${ranked.lose || 0} 生涯排位 · ${games.length} 把近况</p>
        </div>
      </section>
      ${diagnosis(brief)}
      ${cmp ? `<section class="cmp">
        <div class="cmp-lab"><span>胜</span><span class="dim">负</span></div>
        ${cmp}
      </section>` : ""}
      <section class="tags">${tags}</section>
      <section class="mcs">${cards}</section>
    `;
  }

  Promise.all([
    fetch("./data/player.json?v=t10").then((r) => (r.ok ? r.json() : null)),
    fetch("./data/player-briefing.json?v=t10").then((r) => (r.ok ? r.json() : {})),
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
