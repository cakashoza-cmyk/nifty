/* Nifty Condition Desk front end. Educational research only: describes conditions and history, never recommends.
   All numbers come from data/*.json (public sources, fetched by GitHub Actions). No AI produces any number or text. */
(function () {
"use strict";
const $ = (id) => document.getElementById(id);
const LS = "niftydesk.v1";
let S = Object.assign({ lang: "gu" }, JSON.parse(localStorage.getItem(LS) || "{}"));
const save = () => localStorage.setItem(LS, JSON.stringify(S));
let L = null, M = null, P = null;
const f2 = (x, d = 2) => (x == null || isNaN(x)) ? "—" : Number(x).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x, d = 1) => (x == null || isNaN(x)) ? "—" : (x > 0 ? "+" : "") + Number(x).toFixed(d) + "%";
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pill = (k, t) => `<span class="pill p-${k}">${t || k}</span>`;
const fill = (t, o) => t.replace(/\{(\w+)\}/g, (_, k) => o[k] != null ? o[k] : "—");
const T = () => window.STR[S.lang] || window.STR.gu;
const EN = () => window.STR.en;
function item(k) { return L && L.items[k]; }
function audit(val, a) {
  const body = [a.source ? `<b>Source:</b> ${a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.source)}</a>` : esc(a.source)}` : "", a.asof ? `<b>As of:</b> ${esc(a.asof)}` : "",
    a.fetched ? `<b>Fetched:</b> ${esc(a.fetched)}` : "", a.formula ? `<b>Formula:</b> <span class="formula" style="display:block">${esc(a.formula)}</span>` : "", a.note ? esc(a.note) : ""].filter(Boolean).join("<br>");
  const st = a.status || "est";
  return `<details class="aud"><summary>${val} ${pill(st, st === "est" ? "estimate" : st)}</summary><div class="audbox">${body}</div></details>`;
}
function ia(k, txt) {
  const it = item(k);
  if (!it) return `<span class="grey">no live source</span> ${pill("none", "no live source")}`;
  return audit(txt || f2(it.value), { status: it.status, source: it.source, url: it.source_url, asof: it.as_of, fetched: L.generated_ist,
    note: (it.note || "") + (it.status === "stale" ? " STALE: last refresh failed (" + (it.stale_reason || "") + "); showing last good value." : "") });
}

/* ---------- main screen ---------- */
function renderSimple() {
  const t = T();
  document.documentElement.lang = S.lang;
  document.querySelectorAll("#langs button").forEach((b) => b.classList.toggle("on", b.dataset.l === S.lang));
  $("s-title").textContent = t.title; $("disc-top").textContent = t.disc_short; $("s-disc").textContent = t.disc;
  ["v-title", "t-title", "x-title", "m-title", "l-title"].forEach((id) => ($(id).textContent = t[id.replace("-", "_")]));
  $("wa-btn").textContent = t.wa; $("speak-btn").textContent = t.speak; $("details-link").textContent = t.details; $("s-src").textContent = t.src;
  $("speak-btn").style.display = ("speechSynthesis" in window) ? "" : "none";
  if (!L || !M) return;
  const c = M.condition, m = c.macro, ad = c.all_days;
  $("a-today").textContent = fill(t.today, { d: c.as_of });
  $("a-close").textContent = fill(t.close, { v: f2(c.close) });
  const vb = t["band_" + c.val_band], tr = t["tr_" + c.trend], vo = c.vix_band ? t["vol_" + c.vix_band] : "—";
  $("chips").innerHTML = [fill(t.chip_val, { v: vb }), fill(t.chip_tr, { v: tr }), fill(t.chip_vol, { v: vo })].map((x) => `<span class="chip">${esc(x)}</span>`).join("");
  $("v-main").textContent = vb;
  $("v-sub").textContent = fill(t.v_sub, { pb: f2(c.pb), p: f2(c.pb_pctile, 0), pe: f2(c.pe), pp: f2(c.pe_pctile_since_2021, 0) });
  const vh = (c.val_hist[c.val_band] || {})["252"];
  $("v-mean").textContent = vh ? fill(t.v_mean, { m: pct(vh.median), pos: f2(vh.pos, 0), am: pct(ad["252"].median), apos: f2(ad["252"].pos, 0) }) : "";
  $("t-main").textContent = tr;
  $("t-sub").textContent = fill(t.t_sub, { d: fill(c.dist200_pct >= 0 ? t.above : t.below, { p: f2(Math.abs(c.dist200_pct), 1) + "%" }), s200: f2(c.s200, 0), s50: f2(c.s50, 0) });
  const th = (c.trend_hist[c.trend] || {})["63"];
  $("t-mean").textContent = th ? fill(t.t_mean, { m: pct(th.median), pos: f2(th.pos, 0), am: pct(ad["63"].median), apos: f2(ad["63"].pos, 0) }) : "";
  $("x-main").textContent = c.vix != null ? vo + " · " + f2(c.vix) : "—";
  $("x-sub").textContent = c.vix != null ? fill(t.x_sub, { v: f2(c.vix), p: f2(c.vix_pctile, 0) }) : "";
  const xh = c.vix_hist && c.vix_hist[c.vix_band];
  $("x-mean").textContent = xh ? fill(t.x_mean, { m: pct(xh.median), lo: pct(xh.p10), hi: pct(xh.p90) }) : "";
  const g = (k) => item(k) ? item(k).value : null, ga = (k) => item(k) ? item(k).as_of : "—";
  $("m-rates").textContent = fill(t.m_rates, { repo: f2(g("repo")), cpi: f2(g("cpi")), cd: ga("cpi"), in10: f2(g("in10")), id: ga("in10") });
  $("m-gap").textContent = m.ey_gap != null ? fill(t.m_gap, { ey: f2(m.ey), gap: (m.ey_gap > 0 ? "+" : "") + f2(m.ey_gap), p: f2(m.ey_gap_pctile_since_2021, 0) }) : "";
  $("m-world").textContent = fill(t.m_world, { fx: f2(g("usdinr")), fx3: pct(m.usdinr_hist_3m_pct), br: f2(g("brent")), br3: pct(m.brent_3m_pct), us: f2(g("us10")) });
  $("m-flow").textContent = item("fii") ? fill(t.m_flow, { d: ga("fii"), fii: f2(g("fii"), 0), dii: f2(g("dii"), 0) }) : "";
  const m1 = M.models["21"], m3 = M.models["63"];
  $("l-main").textContent = fill(t.l_main, { p1: pct(m1.pred_pct, 2), p3: pct(m3.pred_pct, 2) });
  $("l-zero").textContent = (!m1.model_has_edge && !m3.model_has_edge) ? fill(t.l_zero, { e1: f2(m1.backtest.mae), d1: f2(m1.baseline.drift_mae), n1: f2(m1.baseline.naive_mae) }) : t.l_some;
  const ns = ((P && P.predictions) || []).filter((p) => p.scored).length;
  $("l-track").textContent = fill(t.l_track, { n: ns });
  $("s-updated").textContent = fill(t.updated, { t: L.generated_ist });
}
function summaryText() {
  const t = T();
  return [t.title, $("a-today").textContent, $("a-close").textContent, [...document.querySelectorAll("#chips .chip")].map((x) => x.textContent).join(" · "),
    $("v-mean").textContent, t.disc, location.origin + location.pathname].filter(Boolean).join("\n");
}

/* ---------- details (English) ---------- */
function tbl(head, body) { return `<div class="tablewrap"><table><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>${body.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</table></div>`; }
const dsc = (x) => x ? `${pct(x.median)} median · ${f2(x.pos, 0)}% higher · 10th–90th pct ${pct(x.p10)} to ${pct(x.p90)} · ${x.n} days` : "—";
function renderCond() {
  const c = M.condition, e = EN();
  $("s-cond").innerHTML = `<div class="card"><div class="ct">Condition read for ${c.as_of} close (descriptive only)</div>
    <p>Nifty 50 ${ia("nifty", f2(c.close))}</p>
    <p>Valuation: <b>${e["band_" + c.val_band]}</b> · Trend: <b>${e["tr_" + c.trend]}</b> · Volatility: <b>${c.vix_band ? e["vol_" + c.vix_band] : "—"}</b></p>
    <p class="sub">These are labels for where today's numbers sit in their own history. They are not a forecast and not a recommendation. The forward-change statistics on the next tabs describe what followed similar days in the past; overlapping windows mean far fewer independent examples than the day counts suggest, and the band thresholds use the full sample (hindsight).</p></div>`;
}
function renderVal() {
  const c = M.condition, b = M.bands.valuation, e = EN();
  $("s-val").innerHTML = `<div class="grid2"><div class="card"><div class="ct">P/B percentile since ${c.pb_since}</div><div class="big">${audit(f2(c.pb_pctile, 1) + "%", { status: "est", source: "NSE Indices P/B history", url: item("pb").source_url, asof: c.as_of, formula: "share of all daily P/B values since 1999 below today's P/B (" + f2(c.pb) + ")" })}</div><p>P/B ${ia("pb")} · band <b>${e["band_" + c.val_band]}</b></p></div>
   <div class="card"><div class="ct">P/E percentile since ${M.pe_break} (consolidated basis)</div><div class="big">${audit(f2(c.pe_pctile_since_2021, 1) + "%", { status: "est", source: "NSE Indices P/E history", url: item("pe").source_url, asof: c.as_of, formula: "share of daily P/E values since 31 Mar 2021 below today's P/E" })}</div><p>P/E ${ia("pe")} · dividend yield ${ia("dy", f2(item("dy").value) + "%")}</p><p class="sub">${esc(item("pe").note)}</p></div></div>
  <div class="card"><div class="ct">What followed past days in each valuation band (P/B percentile, since 1999)</div>
   ${tbl(["Band", "Percentile range", "Next 3 months", "Next 12 months"], b.map(([lim, k], i) => [e["band_" + k] + (k === c.val_band ? " ← today" : ""), (i ? b[i - 1][0] : 0) + "–" + Math.min(lim, 100), dsc((c.val_hist[k] || {})["63"]), dsc((c.val_hist[k] || {})["252"])]).concat([["All days", "", dsc(c.all_days["63"]), dsc(c.all_days["252"])]]))}
   <p class="sub">Price changes only (dividends excluded). Descriptive history, not a prediction.</p></div>`;
}
function renderTrend() {
  const c = M.condition, e = EN();
  $("s-trend").innerHTML = `<div class="grid2"><div class="card"><div class="ct">Trend state</div><div class="big">${e["tr_" + c.trend]}</div>
    <p>Close ${f2(c.close)} vs 200-day average ${audit(f2(c.s200), { status: "est", formula: "mean of the last 200 Nifty closes", source: "NSE Indices", asof: c.as_of })} (${pct(c.dist200_pct)}), 50-day average ${f2(c.s50)}.</p>
    <p class="sub">Rising = close above the 200-day average and 50-day above 200-day; falling = both below; otherwise mixed.</p>
    ${tbl(["State", "Next 1 month", "Next 3 months"], ["rising", "mixed", "falling"].map((k) => [e["tr_" + k] + (k === c.trend ? " ← today" : ""), dsc((c.trend_hist[k] || {})["21"]), dsc((c.trend_hist[k] || {})["63"])]))}</div>
   <div class="card"><div class="ct">India VIX</div><div class="big">${ia("vix")}</div><p>Percentile since ${c.vix_since}: ${f2(c.vix_pctile, 1)}% → <b>${c.vix_band ? e["vol_" + c.vix_band] : "—"}</b> (calm = bottom third, nervous = top third).</p>
    ${tbl(["State", "Next 3 months"], ["calm", "normal", "nervous"].map((k) => [e["vol_" + k] + (k === c.vix_band ? " ← today" : ""), dsc((c.vix_hist || {})[k])]))}
    <p class="sub">NSE Indices' public history for India VIX starts in ${c.vix_since}, so this table covers fewer years.</p></div></div>`;
}
function renderMacro() {
  const m = M.condition.macro;
  $("s-macro").innerHTML = `<div class="grid2"><div class="card"><div class="ct">Rates and inflation</div>
    <p>RBI repo ${ia("repo", f2(item("repo").value) + "%")} · CPI inflation ${ia("cpi", f2(item("cpi").value) + "%")} · 10-year G-sec ${ia("in10", f2(item("in10").value) + "%")}</p>
    <p>Real repo (repo − CPI): ${audit(pct(m.real_repo, 2), { status: "est", formula: "repo rate − latest CPI inflation" })} · Real 10-year (G-sec − CPI): ${audit(pct(m.real_10y, 2), { status: "est", formula: "10-year G-sec (monthly) − latest CPI inflation" })}</p></div>
   <div class="card"><div class="ct">Earnings-yield gap</div><div class="big">${audit((m.ey_gap > 0 ? "+" : "") + f2(m.ey_gap) + " pp", { status: "est", source: "NSE Indices P/E; FRED India 10-year", asof: M.condition.as_of + " / " + item("in10").as_of, formula: "100 ÷ P/E (" + f2(item("pe").value) + ") = " + f2(m.ey) + "% minus 10-year G-sec yield " + f2(item("in10").value) + "%" })}</div>
    <p>Percentile since 31 Mar 2021 (same P/E basis): ${f2(m.ey_gap_pctile_since_2021, 1)}%. A lower gap means bonds yield more relative to equity earnings than usual.</p></div>
   <div class="card"><div class="ct">World and rupee</div><p>USD/INR ${ia("usdinr")} (${pct(m.usdinr_hist_3m_pct)} over 3 months, ECB series) · Brent ${ia("brent", "$" + f2(item("brent").value))} (${pct(m.brent_3m_pct)}) · US 10-year ${ia("us10", f2(item("us10").value) + "%")}</p></div>
   <div class="card"><div class="ct">Institutional flows (cash market, provisional)</div><p>FII/FPI ${ia("fii", "₹" + f2(item("fii") && item("fii").value, 0) + " cr")} · DII ${ia("dii", "₹" + f2(item("dii") && item("dii").value, 0) + " cr")}</p>
    <p class="sub">One trading day; history accumulates from each refresh (${m.fii_days || 0} day(s) so far). NSE often refuses automated requests, so days can be missing.</p></div></div>`;
}
function renderLog() {
  const ps = (P && P.predictions) || [];
  const mods = Object.values(M.models);
  const sc = ps.filter((p) => p.scored), fails = sc.filter((p) => !p.band_hit);
  $("s-log").innerHTML = mods.map((m) => { const b = m.baseline, g = m.backtest; return `<div class="card"><div class="ct">${m.label} (${m.horizon_days} trading days): research forecast ${pct(m.pred_pct, 2)} (band: ${m.pred_band}, ±${m.band_pct}%)</div>
    <p class="formula">d% = drift ${f2(m.drift_pct, 3)} + ${m.vars.map((k, i) => `${m.weights[i]} × ${k}`).join(" + ")}</p>
    ${tbl(["Variable", "Now", "Weight", "Walk-forward error alone", "Kept?"], m.vars.map((k, i) => [k, f2(m.features_now[k], 2), m.weights[i], f2(m.single[k].mae, 3) + "%", m.mask[i] ? "yes" : "no"]))}
    <p>Walk-forward back-test ${b.start} to ${b.end} (${b.n} forecasts, each fitted only on earlier data): average error <b>${f2(g.mae, 3)}%</b> vs drift ${f2(b.drift_mae, 3)}% vs 'no change' ${f2(b.naive_mae, 3)}%; all five variables together ${f2(m.ungated.mae, 3)}%. Band right ${f2(g.hit, 1)}% vs drift ${f2(b.drift_hit, 1)}% vs 'no change' ${f2(b.naive_hit, 1)}%. Gate: ${esc(m.gate_reason)}.</p></div>`; }).join("") +
  `<div class="card"><div class="ct">What the log has learned (fixed templates)</div><ul>${M.lessons.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>
   <div class="card"><div class="ct">Live research log (one entry per horizon per trading day; scored after the horizon passes)</div>
   ${tbl(["ID", "Close", "Forecast", "Band", "Version", "Scored", "Actual", "Band right?"], ps.slice(-60).reverse().map((p) => [p.id, f2(p.close), pct(p.pred_pct, 2), p.pred_band, p.model_version, p.scored ? p.realised_date : "pending", p.realised_pct != null ? pct(p.realised_pct, 2) : "—", p.band_hit == null ? "—" : p.band_hit ? "yes" : "no"]))}
   <p class="sub">Missed forecasts so far: ${fails.length} of ${sc.length} scored (all kept in the log). <a href="data/track_record.csv">Download track_record.csv</a> · model archive in data/models/</p></div>
   <div class="card"><div class="ct">Model versions</div>${tbl(["Version", "Date", "Change"], M.changelog.slice().reverse().map((c) => [c.version, c.date, esc(c.change)]))}</div>`;
}
function renderSources() {
  $("s-sources").innerHTML = `<div class="card"><div class="ct">Data items</div>${tbl(["Item", "Value", "As of", "Status", "Source"], Object.values(L.items).map((it) => [esc(it.label), f2(it.value) + " " + esc(it.unit), esc(it.as_of), pill(it.status), `<a href="${esc(it.source_url)}" target="_blank" rel="noopener">${esc(it.source)}</a>`]))}
   ${Object.keys(L.errors || {}).length ? `<div class="warn">Last refresh errors: ${esc(JSON.stringify(L.errors))}</div>` : ""}</div>
   <div class="card"><div class="ct">Not used</div><ul><li>Derivatives (F&amp;O) data and individual stocks: out of scope by design.</li><li>Yahoo Finance ^NSEI: rate-limited (HTTP 429) from GitHub's servers; not needed because NSE Indices' official closes work.</li><li>India VIX before 2018: not in NSE Indices' public history endpoint.</li></ul></div>
   <div class="card"><div class="ct">Headlines (context only; never used in any number or reading)</div><ul>${(L.headlines || []).map((h) => `<li>${esc(h.date)} <a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a></li>`).join("")}</ul></div>`;
}
function renderAll() {
  renderSimple();
  if (!L || !M) return;
  $("disc-details").textContent = EN().disc;
  $("meta-data").textContent = "Data refreshed " + L.generated_ist + " · latest close " + M.data_date;
  $("meta-model").textContent = "Model " + M.version + " · " + M.generated_ist;
  [renderCond, renderVal, renderTrend, renderMacro, renderLog, renderSources].forEach((f) => { try { f(); } catch (e) { console.error(e); const id = { renderCond: "s-cond", renderVal: "s-val", renderTrend: "s-trend", renderMacro: "s-macro", renderLog: "s-log", renderSources: "s-sources" }[f.name]; $(id).innerHTML = `<div class="warn">Could not render: ${esc(e.message)}</div>`; } });
}
function route() {
  const det = location.hash.startsWith("#details");
  $("simple").style.display = det ? "none" : ""; $("details").style.display = det ? "" : "none";
  if (det) renderAll(); else renderSimple();
}
document.addEventListener("click", (ev) => {
  const tb = ev.target.closest(".tab");
  if (tb) { document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === tb)); document.querySelectorAll(".screen").forEach((x) => x.classList.toggle("active", x.id === "s-" + tb.dataset.s)); }
  const l = ev.target.closest("#langs button"); if (l) { S.lang = l.dataset.l; save(); renderSimple(); }
});
$("back-link").onclick = (e) => { e.preventDefault(); history.pushState(null, "", location.pathname); route(); };
window.addEventListener("hashchange", route);
$("wa-btn").onclick = () => window.open("https://wa.me/?text=" + encodeURIComponent(summaryText()), "_blank");
$("speak-btn").onclick = () => { const u = new SpeechSynthesisUtterance([$("a-close").textContent, ...[...document.querySelectorAll("#chips .chip")].map((x) => x.textContent), $("v-mean").textContent, T().disc].join(". "));
  u.lang = { gu: "gu-IN", hi: "hi-IN", en: "en-IN" }[S.lang]; speechSynthesis.cancel(); speechSynthesis.speak(u); };
const j = (u) => fetch(u + "?t=" + Date.now()).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
Promise.all([j("data/live.json"), j("data/model.json"), j("data/predictions.json").catch(() => null)])
  .then(([l, m, p]) => { L = l; M = m; P = p; route(); })
  .catch((e) => { console.error(e); renderSimple(); $("a-close").textContent = String(e); });
renderSimple();
})();
