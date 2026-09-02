(function () {
  const app = document.getElementById("app");
  const asof = document.getElementById("player-asof");

  function pct(v) {
    if (v == null || Number.isNaN(Number(v))) return "—";
    return Math.round(Number(v) * 100) + "%";
  }

  function kda(g) {
    return `${g.kills ?? "—"}/${g.deaths ?? "—"}/${g.assists ?? "—"}`;
  }

  function roleLabel(role) {
    return { pos1: "一号位", pos2: "中单", pos3: "三号位", pos4: "四号位", pos5: "五号位", unknown: "未解析" }[role] || role || "—";
  }

  function kindLabel(kind) {
    return {
      win: "胜",
      meta_weak: "版本偏弱",
      did_not_close: "赢线没收",
      wrong_role: "位置/发挥",
      farm_collapse: "经济崩了",
      other_loss: "其他负",
    }[kind] || kind || "";
  }

  function metaCell(g) {
    const d = g.divine;
    if (!d || d.wr == null) return "—";
    return `Divine ${pct(d.wr)}`;
  }

  function record(s) {
    if (!s) return "—";
    const g = s.games || 0;
    const w = s.wins || 0;
    return `${w}-${g - w}`;
  }

  function render(player, brief) {
    const s = player.summary || {};
    const games = player.games || [];
    const rank = player.leaderboardRank ? `Immortal #${player.leaderboardRank}` : `段位 ${player.rankTier ?? "—"}`;
    const ranked = player.rankedWl || {};
    asof.textContent = player.asOf || brief.asOf || "";
    const focus = (brief.focus || [])
      .map((row) => `<li><span class="player-kind">${kindLabel(row.kind)}</span> ${row.note || row.hero || ""}</li>`)
      .join("");
    const roleCards = ["pos2", "pos3", "pos1"]
      .map((key) => {
        const row = (s.roles || {})[key] || { games: 0, wins: 0 };
        return `<div><b>${roleLabel(key)}</b>${record(row)}</div>`;
      })
      .join("");
    const rows = games
      .map((g) => {
        const mark = g.win ? "W" : "L";
        return `<tr class="${g.win ? "is-win" : "is-loss"}">
          <td>${(g.when || "").slice(5)}</td>
          <td class="mono">${mark}</td>
          <td>${g.hero || "—"}</td>
          <td>${roleLabel(g.role)}</td>
          <td class="mono">${kda(g)}</td>
          <td>${g.durationMin ?? "—"}分</td>
          <td>${pct(g.laneEfficiency)}</td>
          <td>${pct(g.gpmBr)}</td>
          <td>${pct(g.towerBr)}</td>
          <td>${metaCell(g)}</td>
          <td>${g.partySize > 1 ? g.partySize + "排" : "单"}</td>
        </tr>`;
      })
      .join("");
    const heroes = (s.heroes || [])
      .slice(0, 10)
      .map((h) => {
        const wr = h.divine && h.divine.wr != null ? pct(h.divine.wr) : "—";
        return `<li>${h.hero} ${h.wins}-${h.games - h.wins} · Divine ${wr}</li>`;
      })
      .join("");
    app.innerHTML = `
      <section class="hero">
        <p class="kicker">个人排位 · ${rank}</p>
        <h1>${brief.headline || player.name || "QQT"}</h1>
        <p class="lede">${brief.narrative || "还没有日更战报。"}</p>
        <p class="player-pos">${brief.positioning || ""}</p>
        <div class="hero-meta">
          <div><b>最近样本</b>${s.wins || 0}-${s.losses || 0}</div>
          <div><b>生涯排位</b>${ranked.win || 0}-${ranked.lose || 0}</div>
          ${roleCards}
        </div>
      </section>
      <section>
        <h2>今天盯什么</h2>
        <ul class="player-focus">${focus || "<li>没有新的负局分类。</li>"}</ul>
      </section>
      <section>
        <h2>最近排位</h2>
        <p class="section-lead">分位是同分段同英雄。Divine 胜率是 OpenDota 高分段桶，7k+ 位置胜率在战报正文里。</p>
        <div class="player-table-wrap">
          <table class="player-table">
            <thead>
              <tr>
                <th>时间</th><th></th><th>英雄</th><th>位置</th><th>KDA</th><th>时长</th>
                <th>对线</th><th>GPM分位</th><th>推塔分位</th><th>Divine</th><th>排</th>
              </tr>
            </thead>
            <tbody>${rows || "<tr><td colspan='11'>还没有解析局</td></tr>"}</tbody>
          </table>
        </div>
      </section>
      <section>
        <h2>这批英雄池</h2>
        <ul class="player-heroes">${heroes || "<li>无</li>"}</ul>
      </section>
    `;
  }

  Promise.all([
    fetch("./data/player.json?v=player").then((r) => (r.ok ? r.json() : null)),
    fetch("./data/player-briefing.json?v=player").then((r) => (r.ok ? r.json() : {})),
  ])
    .then(([player, brief]) => {
      if (!player) {
        app.textContent = "还没有战绩文件。等北京时间 8 点的日更，或在 Actions 里手动跑 Player daily scout。";
        return;
      }
      render(player, brief || {});
    })
    .catch(() => {
      app.textContent = "战绩文件没下来，刷新一下。";
    });
})();
