const EIGHT = new Set([
  "TEAM VISION",
  "Team Liquid",
  "Nigma Galaxy",
  "Team Spirit",
  "Iron Wing",
  "Team Falcons",
  "BoomBoys",
  "Team Yandex",
]);

const pct = (n) => (n == null || Number.isNaN(n) ? "—" : `${Math.round(n * 100)}%`);
const mmss = (s) => {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
};
const TAG = {
  "TEAM VISION": "VSN",
  "Team Liquid": "Liquid",
  "Nigma Galaxy": "NGX",
  "Team Spirit": "Spirit",
  "Iron Wing": "IW",
  "Team Falcons": "FLCN",
  "BoomBoys": "BB",
  "Team Yandex": "TY",
};

const slotName = (slot) => {
  if (!slot) return "待定";
  if (typeof slot === "string") return slot;
  const who = slot.as === "winner" ? "胜者" : "败者";
  return `${slot.from} ${who}`;
};

function whenShort(dt) {
  const m = String(dt || "").match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})/);
  if (!m) return dt || "";
  return `${Number(m[2])}/${Number(m[3])} ${m[4]}`;
}

function resolveSide(slot, byId) {
  if (typeof slot === "string") {
    return { tag: TAG[slot] || slot.slice(0, 4), name: slot, tbd: false, drop: "" };
  }
  const src = byId[slot?.from];
  const kind = slot?.as === "winner" ? "胜者" : "败者";
  const fromUpper = src && String(src.round || "").includes("胜者组") && slot?.as === "loser";
  if (!src) return { tag: "TBD", name: kind, tbd: true, drop: "" };
  if (typeof src.teamA === "string" && typeof src.teamB === "string") {
    const pair = `${TAG[src.teamA] || src.teamA}/${TAG[src.teamB] || src.teamB}`;
    return {
      tag: kind === "胜者" ? "胜" : "败",
      name: `${pair} ${kind}`,
      tbd: true,
      drop: fromUpper ? "从胜者组掉下来" : "",
    };
  }
  return {
    tag: kind === "胜者" ? "胜" : "败",
    name: `${src.round}${kind}`,
    tbd: true,
    drop: fromUpper ? "从胜者组掉下来" : "",
  };
}

function teamRow(t) {
  return `<div class="ladder-team ${t.tbd ? "tbd" : ""}">
    <span class="ladder-tag">${t.tag}</span>
    <span class="ladder-name">${t.name}</span>
    ${t.drop ? `<span class="ladder-drop">${t.drop}</span>` : ""}
  </div>`;
}

function ladderMatch(id, byId, known) {
  const m = byId[id];
  if (!m) return "";
  const a = resolveSide(m.teamA, byId);
  const b = resolveSide(m.teamB, byId);
  const sim = known[id];
  const odds = sim ? `模型 ${pct(sim.series.pSeriesA)} / ${pct(sim.series.pSeriesB)}` : "";
  return `<div class="ladder-match ${m.status || ""}">
    <div class="ladder-meta"><span>${whenShort(m.datetime)}</span><span>${m.format}</span></div>
    ${teamRow(a)}${teamRow(b)}
    ${odds ? `<div class="ladder-odds">${odds}</div>` : '<div class="ladder-odds mute">待填</div>'}
  </div>`;
}

function roundCol(title, ids, byId, known) {
  return `<div class="ladder-round n${ids.length}">
    <div class="ladder-round-title">${title}</div>
    <div class="ladder-round-body">${ids
      .map((id) => `<div class="ladder-slot">${ladderMatch(id, byId, known)}</div>`)
      .join("")}</div>
  </div>`;
}

function joinCol(pairs, kind) {
  const inner = Array.from({ length: pairs }, () => `<div class="ladder-elbow"></div>`).join("");
  return `<div class="ladder-join ${kind || "pair"}" aria-hidden="true">${inner}</div>`;
}

function kaLine(unit) {
  if (!unit) return "—";
  const k = unit.kills_before_10 ?? 0;
  const a = unit.assists_before_10 ?? 0;
  const p = unit.participate_before_10 ?? k + a;
  return `参与 ${p} 次（击杀 ${k} + 助攻 ${a}）`;
}

function gameCard(g) {
  const f = g.f10k || {};
  const f10kTag = g.f10k ? `先到10杀 ${g.f10k.side === "radiant" ? g.radiant : g.dire}` : "未到10杀";
  const score = g.f10k?.score;
  return `<article class="game">
    <div class="game-top">
      <div>
        <strong>${g.radiant}</strong> ${g.score?.[0] ?? ""} — ${g.score?.[1] ?? ""} <strong>${g.dire}</strong>
        <div class="foot-note">胜者 ${g.winner} · ${Math.floor(g.duration / 60)} 分钟 · ${g.pace} / ${g.stance}</div>
      </div>
      <div>
        <span class="tag ${g.f10k ? "hot" : ""}">${f10kTag}</span>
        <a href="${g.opendota}" target="_blank" rel="noopener">OpenDota</a>
      </div>
    </div>
    <div class="lenses">
      <div><h4>BP 思路</h4><p>天辉：${g.blurb.bp.radiant}<br>夜魇：${g.blurb.bp.dire}</p></div>
      <div><h4>节奏 · 前中期攻防</h4><p>${g.blurb.pace}<br>攻防标签：${g.blurb.stance}。15分钟经济差 ${g.gold?.m15 ?? "?"}。一塔 ${g.first_tower ? mmss(g.first_tower.time) + " 由" + (g.first_tower.taker === "radiant" ? "天辉" : "夜魇") + "拆掉" : "未见T1记录"}。</p></div>
      <div><h4>先到 10 杀 · 中单参与</h4><p>${g.blurb.f10k}<br>${score ? "当时比分 " + score.radiant + "-" + score.dire + " · " : ""}${mmss(f.time)}<br>中单 ${g.sides.radiant.mid.player} ${g.sides.radiant.mid.hero} ${kaLine(g.sides.radiant.mid)}；${g.sides.dire.mid.player} ${g.sides.dire.mid.hero} ${kaLine(g.sides.dire.mid)}。</p></div>
      <div><h4>中辅联动</h4><p>${g.blurb.mid_support}</p></div>
    </div>
  </article>`;
}

function profileBox(p) {
  const mids = (p.mids || []).map((x) => x[0]).slice(0, 3).join(" / ");
  const midKa = p.avg_mid_ka_when_first_to_10 ?? p.avg_mid_kills_when_first_to_10;
  const midAll = p.avg_mid_ka_in_first10 ?? p.avg_mid_kills_in_first10;
  const ms = p.avg_mid_sup_ka_in_first10 ?? p.avg_mid_sup_kills_in_first10;
  return `<div class="profile">
    <h3>${p.name}</h3>
    <p>本届 ${p.wins}/${p.games}（${pct(p.winrate)}）· 场均 ${p.avg_duration_min} 分钟</p>
    <p>先到 10 杀 <b>${pct(p.f10k_rate)}</b>；先到时中单场均参与 ${midKa ?? "—"} 次，其中参与≥3 次 ${p.f10k_mid_ge3}/${p.f10k_got}</p>
    <p>中单前10杀场均参与 <b>${midAll}</b> · 中辅合计 <b>${ms}</b> · 中辅驱动 ${pct(p.mid_sup_driven_rate)}</p>
    <p>中单常用 ${mids || "—"}</p>
  </div>`;
}

function polyLine(s) {
  if (!s.poly) return "暂无市场快照";
  const [a, b] = s.poly.prices;
  return `Polymarket 系列 ${s.poly.outcomes[0]} ${pct(a)} / ${s.poly.outcomes[1]} ${pct(b)}`;
}

function draftBlock(sim) {
  const d = sim.draft;
  if (d) {
    return `<div class="draft">
      <div><b>${d.teamA.name}</b> 选 ${d.teamA.picks.join("、")}<br>禁 ${d.teamA.bans.join("、")}</div>
      <div><b>${d.teamB.name}</b> 选 ${d.teamB.picks.join("、")}<br>禁 ${d.teamB.bans.join("、")}</div>
    </div>
    <p class="foot-note">先手 ${d.firstPick} · 这套阵容下 ${d.teamA.name} 胜率 ${pct(sim.pWinA)} · 先到10杀 ${pct(sim.pF10A)}</p>`;
  }
  return `<p>选：${(sim.picksA || []).join("、")} vs ${(sim.picksB || []).join("、")} · 胜率 ${pct(sim.pWinA)} · 先到10杀 ${pct(sim.pF10A)}</p>`;
}

function mapSims(map) {
  return `<div class="map-sim">
    <h4>第 ${map.game} 局 · 5 次 BP 平均：胜率 ${pct(map.pWinA)} / ${pct(map.pWinB)} · 先到10杀 ${pct(map.pF10A)} / ${pct(map.pF10B)}</h4>
    ${(map.sims || [])
      .map(
        (sim) => `<article class="sim-card"><div class="sim-tag">模拟 ${sim.sim}</div>${draftBlock(sim)}</article>`
      )
      .join("")}
  </div>`;
}

function betTable(betting, liveNote) {
  if (!betting) return "";
  const rows = (betting.rows || [])
    .map((r) => {
      const roi = r.roi == null ? "—" : `${r.roi >= 0 ? "+" : ""}${Math.round(r.roi * 100)}%`;
      const mkt = r.marketP == null ? "无盘" : pct(r.marketP);
      const odds = r.odds ? ` · 等价 ${r.odds.toFixed(2)}` : "";
      return `<tr>
        <td>${r.market}</td>
        <td>${r.pick}</td>
        <td>${pct(r.modelP)}</td>
        <td>${mkt}${odds}</td>
        <td>${roi}</td>
        <td>${r.action}</td>
      </tr>`;
    })
    .join("");
  return `<div class="bet">
    <h3>押注方案（模型 vs Polymarket）${liveNote || ""}</h3>
    <p class="insight">${betting.plan}</p>
    <table class="src-table">
      <thead><tr><th>盘口</th><th>买谁</th><th>模型</th><th>市场</th><th>期望回报率</th><th>建议</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="foot-note">期望回报率 = 模型概率 ÷ 市场价格 − 1。按 $1 买 YES 计。不是稳胆，样本只有本届 80 局。</p>
  </div>`;
}

function simPanel(sim, liveNote) {
  if (!sim) return '<p class="empty">还没有模拟。</p>';
  const polyBits = [];
  if (sim.polyLive?.prices) {
    const [a, b] = sim.polyLive.prices;
    polyBits.push(`系列市场 ${sim.polyLive.outcomes[0]} ${pct(a)} / ${sim.polyLive.outcomes[1]} ${pct(b)}`);
  }
  if (sim.poly?.g1?.prices) {
    const g = sim.poly.g1;
    polyBits.push(`G1 ${g.outcomes[0]} ${pct(g.prices[0])} / ${g.outcomes[1]} ${pct(g.prices[1])}`);
  }
  return `<div class="sim-wrap">
    <p class="insight">${sim.why || ""} 系列 ${sim.teamA} ${pct(sim.series?.pSeriesA)} / ${sim.teamB} ${pct(sim.series?.pSeriesB)}。先到10杀 ${pct(sim.pF10A)} / ${pct(sim.pF10B)}。${polyBits.length ? `<br><span class="note">${polyBits.join(" · ")}</span>` : ""}</p>
    ${betTable(sim.betting, liveNote)}
    ${(sim.maps || []).map(mapSims).join("")}
  </div>`;
}

function renderBracket(data) {
  const matches = data.playoffs?.matches || [];
  const byId = Object.fromEntries(matches.map((m) => [m.id, m]));
  const known = Object.fromEntries((data.simulations?.known || []).map((s) => [s.id, s]));
  const upper = [
    roundCol("胜者组首轮 · 8/20", ["ubqf1", "ubqf2", "ubqf3", "ubqf4"], byId, known),
    joinCol(2, "pair"),
    roundCol("胜者组半决赛 · 8/21", ["ubsf1", "ubsf2"], byId, known),
    joinCol(1, "pair"),
    roundCol("胜者组决赛 · 8/22", ["ubf"], byId, known),
    joinCol(1, "line"),
    roundCol("总决赛 Bo5 · 8/23", ["gf"], byId, known),
  ].join("");
  const lower = [
    roundCol("败者组首轮 · 8/21", ["lbr1a", "lbr1b"], byId, known),
    joinCol(2, "line"),
    roundCol("败者组四分之一 · 8/22", ["lbqf1", "lbqf2"], byId, known),
    joinCol(1, "pair"),
    roundCol("败者组半决赛 · 8/22", ["lbsf"], byId, known),
    joinCol(1, "line"),
    roundCol("败者组决赛 · 8/23", ["lbf"], byId, known),
  ].join("");
  return `<section class="series-block">
    <div class="series-head"><h2>淘汰赛对阵图</h2><div class="poly">双败 · 总决赛 Bo5 · 其余 Bo3</div></div>
    <p class="section-lead">和液体百科同一张阶梯：上面胜者组往右晋级，下面败者组接住掉下来的队。金标是已排好的队，灰标是「谁赢谁进」。</p>
    <div class="ladder-legend">
      <span><i class="lg gold"></i>已排对阵</span>
      <span><i class="lg mute"></i>待填 / 情景</span>
      <span><i class="lg drop"></i>从胜者组掉进败者组</span>
    </div>
    <div class="ladder-scroll">
      <div class="ladder-block">
        <div class="ladder-kicker">胜者组 Upper</div>
        <div class="ladder upper">${upper}</div>
      </div>
      <div class="ladder-block">
        <div class="ladder-kicker">败者组 Lower</div>
        <div class="ladder lower">${lower}</div>
      </div>
    </div>
  </section>`;
}

function yuan(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const s = Number.isInteger(v) ? String(v) : v.toFixed(1);
  return `${s} 元`;
}

function pct1(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${Number(n).toFixed(1)}%`;
}

function actionCell(action) {
  const klass = action === "下" || (action && action.includes("压缩")) ? "y" : "n";
  return `<span class="${klass}">${action || "—"}</span>`;
}

const STAKE_PROFILES = {
  稳健: { fraction: 0.25, cap: 0.05 },
  大胆: { fraction: 0.5, cap: 0.08 },
  过猛: { fraction: 1, cap: 0.15 },
};
const STAKE_MIN = 8;

function fullKelly(p, odds) {
  if (odds <= 1 || p <= 0 || p >= 1) return 0;
  const edge = p * odds - 1;
  return Math.max(0, edge / (odds - 1));
}

function sizedKelly(p, odds, fraction, cap) {
  return Math.min(cap, fullKelly(p, odds) * fraction);
}

function breakEvenOdds(p) {
  if (p <= 0) return 99;
  return Math.round((1 / p) * 100) / 100;
}

function calcTicket(p, odds, bankroll, profileId) {
  const prof = STAKE_PROFILES[profileId] || STAKE_PROFILES["稳健"];
  const fk = fullKelly(p, odds);
  const qk = sizedKelly(p, odds, prof.fraction, prof.cap);
  const evPerYuan = p * odds - 1;
  let stake = Math.round(bankroll * qk);
  let action = "下";
  if (qk <= 0 || evPerYuan <= 0) {
    action = "空仓";
    stake = 0;
  } else if (stake < STAKE_MIN) {
    action = "优势太薄，空仓";
    stake = 0;
  }
  return {
    p,
    odds,
    fullKelly: fk,
    kellyUsed: qk,
    evPerYuan,
    stake,
    pctOfBank: bankroll ? (100 * stake) / bankroll : 0,
    ifWin: stake ? bankroll + stake * (odds - 1) : bankroll,
    ifLose: stake ? bankroll - stake : bankroll,
    evYuan: stake * evPerYuan,
    action,
    breakEven: breakEvenOdds(p),
  };
}

function renderStakeCalculator(br) {
  const picks = br.picks || [];
  const matchOpts = picks
    .map((p, i) => `<option value="${i}">${p.when} · ${p.teamA || p.team} vs ${p.teamB || p.opp}</option>`)
    .join("");
  const profOpts = (br.calculatorProfiles || Object.keys(STAKE_PROFILES).map((id) => ({ id })))
    .map((pr) => `<option value="${pr.id}">${pr.id}</option>`)
    .join("");
  const ev = br.evRule || {};
  return `<section class="series-block calc-block" id="stake-calc">
    <div class="series-head"><h2>注码计算器</h2><div class="poly">填本金 · 选场次 · 填真实赔率 · 点计算</div></div>
    <p class="insight">${ev.headline || "不只能投高概率方，看 p×赔率 是否大于 1。"}</p>
    <p class="section-lead">${ev.formula || ""} ${ev.favoriteTrap || ""} ${ev.underdogOk || ""}</p>
    <form class="calc-form" id="calc-form">
      <label>本金（元）<input type="number" id="calc-bank" min="1" step="1" value="${br.start || 1000}"></label>
      <label>场次<select id="calc-match">${matchOpts}</select></label>
      <label>买哪边<select id="calc-side"></select></label>
      <label>赔率<input type="number" id="calc-odds" min="1.01" step="0.01" value="${(br.defaultOdds || 1.7).toFixed(2)}"></label>
      <label>风格<select id="calc-profile">${profOpts}</select></label>
      <button type="submit" class="calc-btn">计算</button>
    </form>
    <div id="calc-result" class="calc-result empty">选好场次和赔率后点「计算」。</div>
    <div id="calc-both" class="calc-both"></div>
    <p class="foot-note">${ev.bothSides || ""} ${ev.example || ""}</p>
  </section>`;
}

function wireStakeCalculator(br) {
  const form = document.getElementById("calc-form");
  const matchEl = document.getElementById("calc-match");
  const sideEl = document.getElementById("calc-side");
  if (!form || !matchEl || !sideEl) return;

  const picks = br.picks || [];

  const fillSides = () => {
    const pick = picks[Number(matchEl.value)] || picks[0];
    if (!pick) return;
    sideEl.innerHTML = (pick.sides || [])
      .map((s, i) => `<option value="${i}">${s.label} · 模型 ${pct(s.modelP)} · 盈亏平衡 ${s.breakEvenOdds}</option>`)
      .join("");
  };

  fillSides();
  matchEl.addEventListener("change", fillSides);

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const bank = Number(document.getElementById("calc-bank").value);
    const odds = Number(document.getElementById("calc-odds").value);
    const profile = document.getElementById("calc-profile").value;
    const pick = picks[Number(matchEl.value)] || picks[0];
    const side = (pick?.sides || [])[Number(sideEl.value)] || pick?.sides?.[0];
    const resultEl = document.getElementById("calc-result");
    const bothEl = document.getElementById("calc-both");
    if (!pick || !side || !bank || bank <= 0 || !odds || odds <= 1) {
      resultEl.className = "calc-result warn";
      resultEl.innerHTML = "请填有效本金和赔率（>1）。";
      bothEl.innerHTML = "";
      return;
    }
    const t = calcTicket(side.modelP, odds, bank, profile);
    const evPct = Math.round(t.evPerYuan * 1000) / 10;
    resultEl.className = `calc-result ${t.stake ? "go-card" : "warn"}`;
    resultEl.innerHTML = `<h3>${pick.when} · ${side.label}</h3>
      <div class="stat-row stake-stats">
        <div><b>${actionCell(t.action)}</b><span>动作 · ${profile}</span></div>
        <div><b>${yuan(t.stake)}</b><span>建议注码（${pct1(t.pctOfBank)}）</span></div>
        <div><b class="${t.evPerYuan >= 0 ? "y" : "n"}">${evPct >= 0 ? "+" : ""}${evPct}%</b><span>每元期望</span></div>
        <div><b>${yuan(t.evYuan)}</b><span>这注期望收益</span></div>
      </div>
      <p>模型 p = <b>${pct(side.modelP)}</b> · 赔率 <b>${odds.toFixed(2)}</b> · 盈亏平衡 <b>${t.breakEven}</b></p>
      <p>全Kelly ${pct1(100 * t.fullKelly)} · 实下分数 ${pct1(100 * t.kellyUsed)} · 赢到 ${yuan(t.ifWin)} · 输到 ${yuan(t.ifLose)}</p>
      <p class="note">${t.stake ? "正期望才出注码；负期望任何风格都是 0。" : t.evPerYuan <= 0 ? "p×赔率 < 1，这边不应下（不管是不是热门）。" : "优势太薄（低于最低注码门槛），建议空仓。"}</p>`;

    const bothRows = (pick.sides || [])
      .map((s) => {
        const x = calcTicket(s.modelP, odds, bank, profile);
        const edge = Math.round(x.evPerYuan * 1000) / 10;
        const fav = s.side === side.side ? " ← 你选的" : "";
        return `<tr>
          <td>${s.label}${fav}</td>
          <td>${pct(s.modelP)}</td>
          <td>${s.breakEvenOdds}</td>
          <td class="${x.evPerYuan >= 0 ? "y" : "n"}">${edge >= 0 ? "+" : ""}${edge}%</td>
          <td><b>${yuan(x.stake)}</b></td>
          <td>${actionCell(x.action)}</td>
        </tr>`;
      })
      .join("");
    bothEl.innerHTML = `<h3>同一赔率 ${odds.toFixed(2)} 下 · 两边各算一遍</h3>
      <p class="section-lead">热门和冷门用同一个赔率框只是方便对比——实盘请填你实际能拿到的价格。通常只有一边（或都没有）正期望。</p>
      <table class="src-table compact">
        <thead><tr><th>方向</th><th>模型 p</th><th>盈亏平衡</th><th>期望/元</th><th>注码</th><th>动作</th></tr></thead>
        <tbody>${bothRows}</tbody>
      </table>`;
  });
}

function forkBox(title, node, tone) {
  if (!node) return `<div class="card"><h3>${title}</h3><p class="note">后面没有要下的票。</p></div>`;
  return `<div class="card ${tone || ""}">
    <h3>${title}</h3>
    <p>本金变成 <b>${yuan(node.bank)}</b></p>
    <p>下一把 ${node.next}：<b>${yuan(node.stake)}</b>（${pct1(node.pctOfBank)}）</p>
    <p class="note">若还下固定 100：${yuan(node.naiveFixed100)}。若下 10%：${yuan(node.naive10pct)}。¼Kelly 不是这两个数。</p>
  </div>`;
}

function renderStake(data) {
  const br = data.simulations?.bankroll;
  if (!br) return '<p class="empty">还没有注码方案。先跑 simulate_playoffs.py。</p>';
  const resize = br.resizeAt170 || {};
  const first = resize.first || {};
  const win = resize.ifWin || {};
  const lose = resize.ifLose || {};
  const compareRows = (br.compareAt170 || [])
    .map((r) => `<tr>
      <td>${r.when}<br><span class="note">${r.pick}</span></td>
      <td>${pct(r.modelP)}<br><span class="note">盈亏平衡 ${r.breakEvenOdds}</span></td>
      <td>${r.edgePerYuan > 0 ? '<span class="y">+' : '<span class="n">'}${Math.round(r.edgePerYuan * 1000) / 10}%</span></td>
      <td>${yuan(r.fixed100)}<br><span class="${r.fixed100Ev >= 0 ? "y" : "n"}">EV ${r.fixed100Ev}</span></td>
      <td><b>${yuan(r.qKelly)}</b>（${pct1(r.qKellyPct)}）<br>${actionCell(r.action)}</td>
      <td><b>${yuan(r.halfKelly)}</b>（${pct1(r.halfKellyPct)}）<br>${actionCell(r.actionBold)}</td>
      <td>${yuan(r.fullKellyStake)}（${pct1(r.fullKellyPct)}）</td>
    </tr>`)
    .join("");
  const pickCards = (br.picks || [])
    .map((p) => {
      const t = p.atDefault || {};
      const grid = (p.grid || [])
        .map(
          (g) => `<tr>
            <td>${g.odds.toFixed(2)}</td>
            <td>${pct1(100 * g.fullKelly)}</td>
            <td>${pct1(100 * g.quarterKelly)}</td>
            <td>${yuan(g.stake)}</td>
            <td>${actionCell(g.action)}</td>
          </tr>`
        )
        .join("");
      return `<article class="game">
        <div class="game-top">
          <div>
            <strong>${p.alias || p.pick}</strong>
            <div class="foot-note">${p.when} · ${p.sample || ""}</div>
          </div>
          <div>
            <span class="tag ${t.stake ? "hot" : ""}">模型 ${pct(p.modelP)}</span>
            <span class="tag">盈亏平衡 ${p.breakEvenOdds}</span>
          </div>
        </div>
        <p>${p.note || ""}</p>
        <p>低保 ${br.defaultOdds.toFixed(2)}：${actionCell(t.action)} ${t.stake ? yuan(t.stake) + "（本金 " + pct1(t.pctOfBank) + "，全Kelly " + pct1(100 * t.fullKelly) + "）" : "不下。p×赔率 < 1，固定 100 也是亏的。"}</p>
        <table class="src-table compact">
          <thead><tr><th>赔率</th><th>全Kelly</th><th>¼Kelly</th><th>注码</th><th>动作</th></tr></thead>
          <tbody>${grid}</tbody>
        </table>
      </article>`;
    })
    .join("");
  const walk = (br.sequentialAt170?.walk || [])
    .map((n) => {
      if (!n.stake) {
        return `<li><b>${n.when}</b> ${n.pick} → 空仓，本金仍是 ${yuan(n.bankBefore)}</li>`;
      }
      return `<li><b>${n.when}</b> ${n.pick}：本金 ${yuan(n.bankBefore)} 下 <b>${yuan(n.stake)}</b>（${pct1(n.pctOfBank)}）。赢到 ${yuan(n.ifWinBank)}，输到 ${yuan(n.ifLoseBank)}。</li>`;
    })
    .join("");
  const simul = br.simultaneousAt170 || {};
  const simulRows = (simul.tickets || [])
    .map(
      (t) => `<tr>
        <td>${t.when}</td>
        <td>${t.pick}</td>
        <td>${pct(t.modelP)}</td>
        <td>${yuan(t.rawStake)}</td>
        <td>${yuan(t.stake)}</td>
        <td>${actionCell(t.action)}</td>
      </tr>`
    )
    .join("");
  const why = (br.whyQuarter || []).map((x) => `<li>${x}</li>`).join("");
  const rules = (br.rules || []).map((x) => `<li>${x}</li>`).join("");
  const sampleWhy = (br.sampleWhy || []).map((x) => `<li>${x}</li>`).join("");
  const uncRows = (br.picks || [])
    .map((p) => {
      const u = p.uncertainty || {};
      const w = u.wilson95 || [];
      const rw = u.rawWilson95 || [];
      return `<tr>
        <td>${p.alias || p.pick}<br><span class="note">有效样本 min(${u.teamN}, ${u.oppN}) = ${u.nEff} 局</span></td>
        <td>${pct(p.modelP)} ± ${pct1(100 * (u.se || 0))}</td>
        <td>${pct(w[0])} – ${pct(w[1])}</td>
        <td>${pct(u.pMinusSe)}<br><span class="${u.plusEvIfLow ? "y" : "n"}">低1σ时 ${u.plusEvIfLow ? "仍+" : "变负"}EV</span></td>
        <td>${u.raw || "—"} → ${pct(rw[0])}–${pct(rw[1])}</td>
        <td>${u.needNFor5pp || "—"} 局才够 ±5 点<br><span class="note">现在 ${u.nEff}</span></td>
      </tr>`;
    })
    .join("");
  const profiles = br.profiles || {};
  const profOrder = ["稳健", "大胆", "过猛"];
  const profCards = profOrder
    .map((k) => {
      const pr = profiles[k];
      if (!pr) return "";
      const bits = (pr.tickets || [])
        .filter((t) => t.stake)
        .map((t) => `${t.pick.replace("先到 10 杀", "F10K")} ${yuan(t.stake)}`)
        .join("；") || "没有正期望票";
      return `<div class="card ${k === "大胆" ? "go-card" : k === "过猛" ? "warn" : ""}">
        <h3>${pr.label}</h3>
        <p>当日合计 <b>${yuan(pr.total)}</b> · 两张都输大约剩 ${yuan(pr.ifAllLose)}</p>
        <p>${bits}</p>
        <p class="note">${pr.why}</p>
      </div>`;
    })
    .join("");
  const boldResize = br.resizeBoldAt170 || {};
  const bFirst = boldResize.first || {};
  const bWin = boldResize.ifWin || {};
  const evRule = br.evRule || {};
  const bothSideRows = (br.picks || [])
    .map((p) => {
      const rows = (p.bothAt170 || p.sides || [])
        .map((s) => {
          const ev = s.evPerYuan != null ? s.evPerYuan : s.modelP * br.defaultOdds - 1;
          const t = s.atDefault || {};
          return `<tr>
            <td>${p.when}<br><span class="note">${s.label || s.team}</span></td>
            <td>${pct(s.modelP)}</td>
            <td>${s.breakEvenOdds}</td>
            <td class="${ev >= 0 ? "y" : "n"}">${ev >= 0 ? "+" : ""}${Math.round(ev * 1000) / 10}%</td>
            <td>${actionCell(t.action || (ev > 0 ? "下" : "空仓"))} ${t.stake ? yuan(t.stake) : ""}</td>
          </tr>`;
        })
        .join("");
      return rows;
    })
    .join("");
  return `${renderStakeCalculator(br)}<section class="series-block">
    <div class="series-head"><h2>注码：赚了下一把下多少</h2><div class="poly">本金 ${yuan(br.start)} · 低保按 ${br.defaultOdds.toFixed(2)}</div></div>
    <div class="decide">
      <p class="kicker">先回答这个问题</p>
      <h3>${br.question}</h3>
      <p class="lede">${br.answer}</p>
      <p class="note">${br.formula}</p>
    </div>
    <h3>样本够不够准？</h3>
    <p class="insight">${br.sampleHeadline || ""}</p>
    <ol class="engine">${sampleWhy}</ol>
    <table class="src-table">
      <thead><tr><th>票</th><th>模型 p ± 1σ</th><th>模型 95%</th><th>若真 p 低 1σ</th><th>该队原始率 95%</th><th>要 ±5 点需要</th></tr></thead>
      <tbody>${uncRows}</tbody>
    </table>
    <p class="foot-note">σ = √(p(1−p)/n)，n 取对阵两队里更少的那侧。Wilson 是小样本二项区间。低保 1.70 时，这四张票只要真 p 低一个标准误，全部变负期望——所以默认不能下全Kelly。</p>
    <h3>大胆一点怎么下</h3>
    <p class="section-lead">${br.boldRule || ""}</p>
    <div class="phases">${profCards}</div>
    <p class="insight">大胆档 Liquid 大约 ${yuan(bFirst.stake)}（${pct1(bFirst.pctOfBank)}），赢了下一把 Falcons 大约 ${yuan(bWin.stake)}，仍然不是 100，也不是 10%（${yuan(bWin.naive10pct)}）。IW / VISION 先到10杀点估计已亏，大胆也是 0。</p>
    <div class="stat-row stake-stats">
      <div><b>${yuan(first.stake)}</b><span>稳健 · ${first.pick || "Liquid"}</span></div>
      <div><b>${yuan(bFirst.stake)}</b><span>大胆 · 同一张票</span></div>
      <div><b>${yuan(win.stake)}</b><span>稳健 · 若赢了下一把</span></div>
      <div><b>${yuan(bWin.stake)}</b><span>大胆 · 若赢了下一把</span></div>
    </div>
    <div class="compare">
      ${forkBox("稳健：若第一张赢了", win, "go-card")}
      ${forkBox("稳健：若第一张输了", lose, "warn")}
    </div>
    <p class="insight">赢了下一把大约 ${yuan(win.stake)}，不是 ${yuan(win.naiveFixed100)}，也不是本金的 10%（${yuan(win.naive10pct)}）。分数变成 ${pct1(win.pctOfBank)}，由下一把自己的优势决定，不是因为刚赢了就改成 10%。本金从 ${yuan(first.bank)} 变成 ${yuan(win.bank)}。</p>
    <h3>同一天四场 G1 先到10杀</h3>
    <p class="section-lead">固定 100 不管有没有优势。¼Kelly 空掉负期望，正期望大约 4%。½Kelly 大约 8%，仍低于 10%。全Kelly 把估出来的 p 当成真值，样本撑不住。</p>
    <table class="src-table">
      <thead><tr><th>场次</th><th>模型 p</th><th>期望/元</th><th>固定 100</th><th>稳健 ¼</th><th>大胆 ½</th><th>过猛 全</th></tr></thead>
      <tbody>${compareRows}</tbody>
    </table>
    <p class="foot-note">${resize.whyNot100 || ""} ${resize.whyNot10pct || ""} 先到10杀 Polymarket 没有盘，表里赔率按常见低保 1.70；你拿到真实赔率后看每张票下面的赔率表，或用上面的计算器。</p>
    <h3>低保 ${br.defaultOdds.toFixed(2)} · 两边各算期望（不只能买热门）</h3>
    <p class="section-lead">${evRule.favoriteTrap || ""} ${evRule.underdogOk || ""}</p>
    <table class="src-table compact">
      <thead><tr><th>场次 / 方向</th><th>模型 p</th><th>盈亏平衡</th><th>期望/元</th><th>¼Kelly @1000</th></tr></thead>
      <tbody>${bothSideRows}</tbody>
    </table>
    <h3>8/20 按开赛顺序走</h3>
    <ol class="engine">${walk}</ol>
    <h3>若开赛前就要一次下完</h3>
    <p class="section-lead">四张票都按 1000 各算 ¼Kelly，合计超过本金 10%（${yuan(simul.cap)}）就同比例压缩。现在合计 ${yuan(simul.total)}，${simul.scale < 1 ? "触发了压缩。" : "没有碰到上限。"}</p>
    <table class="src-table">
      <thead><tr><th>时间</th><th>买</th><th>模型</th><th>未压缩</th><th>实下</th><th>动作</th></tr></thead>
      <tbody>${simulRows}</tbody>
    </table>
    <h3>四张低保票 · 赔率一变注码就变</h3>
    ${pickCards}
    <h3>为什么是 ¼Kelly，不是全Kelly</h3>
    <ol class="engine">${why}</ol>
    <h3>规则</h3>
    <ol class="engine">${rules}</ol>
    <p class="foot-note">这是资金公式示意，不是投注建议。p 来自本届 80 局样本，赔率请换成你盘口上的真实价格。</p>
  </section>`;
}

function renderEwc(data) {
  const e = data.ewc;
  if (!e) return "";
  const eight = e.eight || {};
  const rec = Object.entries(eight)
    .map(([name, r]) => `<tr><td>${name}<br><span class="note">EWC 名 ${r.as}</span></td><td>${r.maps}</td><td>${r.place}</td></tr>`)
    .join("");
  const aug = (e.forAug20 || []).map((x) => `<li><b>${x.use}</b> ${x.text}</li>`).join("");
  const diff = (e.patchDiff || []).map((x) => `<li>${x}</li>`).join("");
  const m = e.meta || {};
  return `<section class="series-block">
    <div class="series-head"><h2>EWC 先验 · ${e.patch} → 本届 ${e.tiPatch}</h2><div class="poly">${e.dates} · 巴黎</div></div>
    <p class="insight">${e.whyInclude}</p>
    <p class="section-lead">${e.whyWeightNotFull || e.whyNotPoolF10K || ""}</p>
    <div class="stat-row stake-stats">
      <div><b>${e.patch}</b><span>EWC 版本 · 模型权重 ${Math.round((e.sampleWeight || 0.45) * 100)}%</span></div>
      <div><b>${m.ewcMapsEight} 局</b><span>八强在 EWC 打过的地图</span></div>
      <div><b>${m.ewcAvgMinEight} 分</b><span>EWC 场均 · TI ${m.tiAvgMinEight} 分</span></div>
      <div><b>已并进</b><span>胜率 · F10K · BP · H2H</span></div>
    </div>
    <ol class="engine">${diff}</ol>
    <table class="src-table compact">
      <thead><tr><th>八强</th><th>EWC 地图</th><th>名次</th></tr></thead>
      <tbody>${rec}</tbody>
    </table>
    <h3>对 8/20 四场怎么用</h3>
    <ol class="engine">${aug}</ol>
  </section>`;
}

function renderPredictions(data, liveNote) {
  const known = data.simulations?.known || [];
  const scenarios = data.simulations?.scenarios || [];
  const bySlot = {};
  for (const s of scenarios) {
    (bySlot[s.slot] ||= []).push(s);
  }
  const po = data.playoffs || {};
  const upcoming = (po.matches || []).filter((m) => m.status === "awaiting");
  const knownHtml = known
    .map((sim) => {
      const series = (data.series || []).find((s) => s.id === sim.id);
      return `<section class="series-block" id="sim-${sim.id}">
        <div class="series-head">
          <h2>${sim.round} · ${sim.teamA} vs ${sim.teamB}</h2>
          <div class="poly">${sim.when || ""} CST</div>
        </div>
        ${series ? `<p class="insight">${series.insight}</p>` : ""}
        ${simPanel(sim, liveNote)}
      </section>`;
    })
    .join("");
  const nextIds = new Set(["lbr1a", "lbr1b", "ubsf1", "ubsf2"]);
  const nextHtml = upcoming
    .filter((m) => nextIds.has(m.id))
    .map((m) => {
      const list = bySlot[m.id] || [];
      if (!list.length) return "";
      const rows = list
        .map((s) => {
          const plan = s.betting?.plan || "";
          return `<article class="game">
            <div class="game-top"><strong>${s.if}</strong><span class="tag">${pct(s.series.pSeriesA)} / ${pct(s.series.pSeriesB)}</span></div>
            <p>地图 ${pct(s.pMapA)} · 先到10杀 ${pct(s.pF10A)} / ${pct(s.pF10B)}</p>
            <p class="foot-note">${plan}</p>
            ${s.maps?.[0] ? mapSims(s.maps[0]) : ""}
          </article>`;
        })
        .join("");
      return `<section class="series-block">
        <div class="series-head"><h2>${m.round} · 情景预测</h2><div class="poly">${m.datetime} CST · ${m.format}</div></div>
        <p class="section-lead">${slotName(m.teamA)} vs ${slotName(m.teamB)}。下面每一种可能对阵都已经跑过模拟，出线后对上号即可。</p>
        ${rows}
      </section>`;
    })
    .join("");
  return renderEwc(data) + knownHtml + nextHtml;
}

function render(data, mode, liveNote) {
  const app = document.getElementById("app");
  const byId = Object.fromEntries(data.games.map((g) => [g.match_id, g]));

  if (mode === "stake") {
    app.innerHTML = renderStake(data) + renderEwc(data);
    wireStakeCalculator(data.simulations?.bankroll || {});
    return;
  }
  if (mode === "bracket") {
    app.innerHTML = renderBracket(data);
    return;
  }
  if (mode === "predict") {
    app.innerHTML = renderPredictions(data, liveNote);
    return;
  }
  if (mode === "series") {
    app.innerHTML = renderEwc(data) + data.series
      .map((s) => {
        const h2h = (s.h2hIds || []).map((id) => byId[id]).filter(Boolean);
        const sim = (data.simulations?.known || []).find((x) => x.id === s.id) || s.sim;
        return `<section class="series-block" id="sim-${s.id}">
          <div class="series-head">
            <h2>${s.teamA} vs ${s.teamB}</h2>
            <div class="poly">${s.when} · ${polyLine(s)}</div>
          </div>
          <p class="insight">${s.insight}</p>
          <div class="compare">${profileBox(s.profileA)}${profileBox(s.profileB)}</div>
          ${simPanel(sim, liveNote)}
          <h3>本届直接交手</h3>
          ${h2h.length ? h2h.map(gameCard).join("") : '<p class="empty">本届无直接交手，上面是各自 80 局里的中单/F10K 画像。</p>'}
        </section>`;
      })
      .join("");
    return;
  }

  let list = data.games;
  if (EIGHT.has(mode)) {
    list = data.games.filter((g) => g.radiant === mode || g.dire === mode);
  }
  list = [...list].sort((a, b) => b.start_time - a.start_time);
  app.innerHTML = `<p class="section-lead">${list.length} 局 · 按时间倒序</p>` + list.map(gameCard).join("");
}

function parsePlayoffTime(dt) {
  const m = String(dt || "").match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] - 8, +m[5]));
}

function dayKey(dt) {
  const m = String(dt || "").match(/(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
}

function whenNice(dt) {
  const m = String(dt || "").match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})/);
  if (!m) return dt || "";
  return `${Number(m[2])}月${Number(m[3])}日 ${m[4]}`;
}

function namedSides(m) {
  return typeof m?.teamA === "string" && typeof m?.teamB === "string";
}

function windowMsSafe() {
  return 3 * 3600 * 1000;
}

function focusMatch(matches, preferId) {
  const list = [...(matches || [])]
    .filter((m) => m.datetime)
    .sort((a, b) => String(a.datetime).localeCompare(b.datetime));
  if (preferId) {
    const hit = list.find((m) => m.id === preferId);
    if (hit) return hit;
  }
  const now = Date.now();
  for (const m of list) {
    if (m.status === "complete") continue;
    const t = parsePlayoffTime(m.datetime);
    if (!t) continue;
    if (now < t.getTime() + windowMsSafe()) return m;
  }
  return list.find(namedSides) || list[0] || null;
}

function countdown(dt) {
  const t = parsePlayoffTime(dt);
  if (!t) return "";
  const diff = t.getTime() - Date.now();
  if (diff > 36e5 * 48) return `还有 ${Math.round(diff / 36e5 / 24)} 天`;
  if (diff > 0) {
    const h = Math.floor(diff / 36e5);
    const min = Math.floor((diff % 36e5) / 6e4);
    return h >= 1 ? `还有 ${h} 小时 ${min} 分` : `还有 ${min} 分钟`;
  }
  return "";
}

function phaseLabel(m) {
  const t = parsePlayoffTime(m?.datetime);
  if (!t) return m?.round || "";
  const now = Date.now();
  if (now < t.getTime()) return countdown(m.datetime);
  if (now < t.getTime() + windowMsSafe()) return "进行中";
  return m.round || "";
}

function shortWhy(sim) {
  const w = sim?.why || "";
  if (!w) return "";
  return w
    .replace(/H2H 0 局/g, "本届没交过手")
    .replace(/H2H [\d.]+ 局/g, "本届有交手")
    .replace(/常用中单 /g, "中单爱拿 ");
}

function shortAct(text) {
  const t = String(text || "");
  if (t.includes("无盘")) return "无盘";
  if (t.includes("小注")) return "小注";
  if (t === "下" || t.includes("压缩")) return "下";
  if (t.includes("空仓") || t.includes("观察") || t.includes("没有明显")) return "空仓";
  return t || "空仓";
}

function stampClass(act) {
  if (act === "下" || act === "小注") return "go";
  if (act === "无盘") return "none";
  return "skip";
}

function marketRow(sim, name) {
  return (sim?.betting?.rows || []).find((r) => r.market.includes(name));
}

function splitStyle(p) {
  const a = Math.round(Math.min(Math.max(p ?? 0.5, 0.05), 0.95) * 100);
  return `--split:${a}% ${100 - a}%`;
}

function marketCard(title, pick, modelP, marketP, action) {
  const act = shortAct(action);
  const mkt = marketP == null ? "无" : pct(marketP);
  return `<article class="market">
    <div class="m-label">${title}</div>
    <div class="m-pick">${pick || "—"}</div>
    <div class="m-odds"><span>我们 <b>${pct(modelP)}</b></span><span>盘口 <b>${mkt}</b></span></div>
    <div class="bar" style="${splitStyle(modelP)}"><i></i><i></i></div>
    <span class="stamp ${stampClass(act)}">${act}</span>
  </article>`;
}

function liveCalc(m, sim, br) {
  const series = sim?.series || {};
  const sides = [
    { label: `${m.teamA} 赢系列`, p: series.pSeriesA },
    { label: `${m.teamB} 赢系列`, p: series.pSeriesB },
    { label: `${m.teamA} 先到 10 杀`, p: sim?.pF10A },
    { label: `${m.teamB} 先到 10 杀`, p: sim?.pF10B },
  ].filter((s) => s.p != null);
  const seriesRow = marketRow(sim, "系列");
  const defaultOdds = seriesRow?.odds || br?.defaultOdds || 1.7;
  const opts = sides.map((s, i) => `<option value="${i}">${s.label}</option>`).join("");
  return `<section class="live-calc" id="live-calc">
    <h3>下多少</h3>
    <p class="hint">填你盘口上的真实赔率。没有优势就是 0。</p>
    <form class="calc-form" id="live-form">
      <label>本金（元）<input type="number" id="live-bank" min="1" step="1" value="${br?.start || 1000}"></label>
      <label>买哪边<select id="live-side">${opts}</select></label>
      <label>赔率<input type="number" id="live-odds" min="1.01" step="0.01" value="${Number(defaultOdds).toFixed(2)}"></label>
      <button type="submit" class="calc-btn">算</button>
    </form>
    <div class="live-result empty" id="live-result">填好点「算」。</div>
  </section>`;
}

function wireLiveCalc(sim) {
  const form = document.getElementById("live-form");
  if (!form || !sim) return;
  const series = sim.series || {};
  const sides = [
    { label: `${sim.teamA} 赢系列`, p: series.pSeriesA },
    { label: `${sim.teamB} 赢系列`, p: series.pSeriesB },
    { label: `${sim.teamA} 先到 10 杀`, p: sim.pF10A },
    { label: `${sim.teamB} 先到 10 杀`, p: sim.pF10B },
  ].filter((s) => s.p != null);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const bank = Number(document.getElementById("live-bank").value);
    const odds = Number(document.getElementById("live-odds").value);
    const side = sides[Number(document.getElementById("live-side").value)] || sides[0];
    const box = document.getElementById("live-result");
    if (!side || !bank || bank <= 0 || !odds || odds <= 1) {
      box.className = "live-result";
      box.innerHTML = "请填本金和赔率。";
      return;
    }
    const t = calcTicket(side.p, odds, bank, "稳健");
    if (!t.stake) {
      box.className = "live-result";
      box.innerHTML = `<div class="big">空仓</div><div class="sub">${side.label} · 这个价没有优势。</div>`;
      return;
    }
    box.className = "live-result";
    box.innerHTML = `<div class="big">${yuan(t.stake)}</div><div class="sub">${side.label} · 赢到 ${yuan(t.ifWin)} · 输到 ${yuan(t.ifLose)}</div>`;
  });
}

function slateChip(m, sim, on) {
  const series = marketRow(sim, "系列");
  const act = shortAct(series?.action || (sim ? "空仓" : "待定"));
  const a = TAG[m.teamA] || m.teamA;
  const b = TAG[m.teamB] || m.teamB;
  const time = String(m.datetime || "").slice(11, 16);
  const who = series?.pick ? TAG[series.pick] || series.pick : "";
  return `<button type="button" class="slate-chip ${on ? "on" : ""}" data-match="${m.id}">
    <span class="t">${time}</span>
    <span class="pair">${a} / ${b}</span>
    <span class="a">${act}${who ? " · " + who : ""}</span>
  </button>`;
}

function renderNow(data, matchId) {
  const matches = data.playoffs?.matches || [];
  const m = focusMatch(matches, matchId);
  const app = document.getElementById("app");
  if (!m) {
    app.innerHTML = '<p class="empty">还没有赛程。</p>';
    return;
  }
  const known = Object.fromEntries((data.simulations?.known || []).map((s) => [s.id, s]));
  const byId = Object.fromEntries(matches.map((x) => [x.id, x]));
  const sim = namedSides(m) ? known[m.id] : null;
  const a = namedSides(m)
    ? { name: m.teamA, tag: TAG[m.teamA] || m.teamA }
    : resolveSide(m.teamA, byId);
  const b = namedSides(m)
    ? { name: m.teamB, tag: TAG[m.teamB] || m.teamB }
    : resolveSide(m.teamB, byId);
  const series = marketRow(sim, "系列");
  const f10 = marketRow(sim, "先到");
  const day = dayKey(m.datetime);
  const sameDay = matches.filter((x) => namedSides(x) && dayKey(x.datetime) === day);
  const slate = sameDay.length
    ? `<div class="slate">
        <div class="slate-head">同一天</div>
        <div class="slate-row">${sameDay.map((x) => slateChip(x, known[x.id], x.id === m.id)).join("")}</div>
      </div>`
    : "";
  const seriesPick = series?.pick || (sim && (sim.series?.pSeriesA >= sim.series?.pSeriesB ? m.teamA : m.teamB));
  const f10Pick = f10?.pick || (sim && (sim.pF10A >= sim.pF10B ? m.teamA : m.teamB));
  const markets =
    namedSides(m) && sim
      ? `<div class="markets">
        ${marketCard("系列", seriesPick, series?.modelP ?? sim.series?.pSeriesA, series?.marketP, series?.action)}
        ${marketCard("先到 10 杀", f10Pick, f10?.modelP ?? sim.pF10A, f10?.marketP, f10?.action)}
      </div>`
      : `<p class="live-why">对阵还没出来。出线后这里会换成买谁、下多少。</p>`;
  const why = shortWhy(sim);
  app.innerHTML = `<section class="live-stage">
    <div class="live-kicker">
      <span>${m.round || ""}</span>
      <span>${whenNice(m.datetime)} · ${m.format || "Bo3"}</span>
      <span class="phase">${phaseLabel(m)}</span>
    </div>
    <div class="live-poster">
      <div class="live-teams">
        <div class="live-team"><div class="tagline">${a.tag || ""}</div><h2>${a.name || "待定"}</h2></div>
        <div class="live-vs">VS</div>
        <div class="live-team"><div class="tagline">${b.tag || ""}</div><h2>${b.name || "待定"}</h2></div>
      </div>
      ${why ? `<p class="live-why">${why}</p>` : ""}
      ${markets}
    </div>
    ${slate}
    ${namedSides(m) && sim ? liveCalc(m, sim, data.simulations?.bankroll) : ""}
  </section>`;
  wireLiveCalc(sim);
}

function historyItems(data) {
  return [
    ["now", "回到现场"],
    ["bracket", "对阵图"],
    ["predict", "预测明细"],
    ["series", "交手复盘"],
    ["stake", "注码说明"],
    ["all", "已打的局"],
    ...Object.keys(data.teams || {}).map((n) => [n, n]),
  ];
}

function closeHistory() {
  const menu = document.getElementById("history-menu");
  const btn = document.getElementById("history-btn");
  if (menu) menu.hidden = true;
  if (btn) {
    btn.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
  }
}

function setup(data) {
  const menu = document.getElementById("history-menu");
  const histBtn = document.getElementById("history-btn");
  const homeBtn = document.getElementById("home-btn");
  const oddsStatus = document.getElementById("odds-status");
  let mode = "now";
  let matchId = "";
  let liveNote = "";

  const updateOddsStatus = () => {
    if (!oddsStatus) return;
    const pub = data.publishedAt || data.asOf || "";
    oddsStatus.textContent = pub ? `更新 ${pub.replace(" CST", "")}` : "待更新";
  };

  const paint = () => {
    document.body.classList.toggle("is-archive", mode !== "now");
    if (menu) {
      for (const btn of menu.querySelectorAll("button[data-mode]")) {
        btn.classList.toggle("on", btn.dataset.mode === mode);
      }
    }
    if (mode === "now") {
      renderNow(data, matchId);
      return;
    }
    const app = document.getElementById("app");
    const label = historyItems(data).find((x) => x[0] === mode)?.[1] || "";
    render(data, mode === "all" ? "all" : mode, liveNote);
    app.insertAdjacentHTML(
      "afterbegin",
      `<div class="archive-banner"><span>历史数据 · ${label}</span><button type="button" class="history-btn" data-back>回到现场</button></div>`
    );
    app.querySelector("[data-back]")?.addEventListener("click", () => {
      mode = "now";
      paint();
    });
  };

  if (menu) {
    const items = historyItems(data);
    const top = items.slice(0, 6);
    const teams = items.slice(6);
    menu.innerHTML =
      `<div class="hist-label">赛程与模型</div>` +
      top.map(([id, label]) => `<button type="button" data-mode="${id}">${label}</button>`).join("") +
      (teams.length
        ? `<div class="hist-label">队伍</div>` +
          teams.map(([id, label]) => `<button type="button" data-mode="${id}">${label}</button>`).join("")
        : "");
  }

  histBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!menu) return;
    const open = menu.hidden;
    menu.hidden = !open;
    histBtn.classList.toggle("open", Boolean(open));
    histBtn.setAttribute("aria-expanded", open ? "true" : "false");
  });
  menu?.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-mode]");
    if (!btn) return;
    mode = btn.dataset.mode;
    if (mode === "now") matchId = "";
    closeHistory();
    paint();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".history-wrap")) closeHistory();
  });
  homeBtn?.addEventListener("click", () => {
    mode = "now";
    matchId = "";
    closeHistory();
    paint();
  });
  document.getElementById("app")?.addEventListener("click", (e) => {
    const chip = e.target.closest(".slate-chip");
    if (!chip) return;
    matchId = chip.dataset.match || "";
    mode = "now";
    paint();
  });

  updateOddsStatus();
  paint();
}

if (window.TI15_DATA) {
  setup(window.TI15_DATA);
} else {
  document.getElementById("app").innerHTML = "数据没加载到。请打开站点首页。";
}
