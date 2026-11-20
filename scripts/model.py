"""Nifty market-condition desk: condition read, research forecast ledger, scoring and learning.
Numbers only from data/live.json. No AI anywhere; every number is plain arithmetic or least squares, written to JSON.
EDUCATIONAL RESEARCH ONLY. This produces descriptions of market conditions and a scored forecast log, never a recommendation.

Condition read (latest trading day d):
  valuation band  = percentile of Nifty P/B on d among all daily P/B values since 1999 (P/B kept one basis throughout)
                    (P/E percentile shown only since 31 Mar 2021, when NSE moved P/E to consolidated earnings)
  trend state     = close vs its 200-day average, and 50-day vs 200-day average
  volatility      = percentile of India VIX among all values since Mar 2008
  earnings-yield gap = 100 / P/E - India 10-year G-sec yield (latest monthly), percentage points
  'what this has historically meant' = forward Nifty price returns observed on past days in the same state (descriptive statistics).
Forecast of the Nifty price change over h trading days (h = 21 ~ 1 month, 63 ~ 3 months), in log %:
  d% = drift + w_mom*momentum + w_trend*trend + w_val*valuation + w_vix*volatility + w_fx*rupee
  drift = average h-day change over all earlier history (the honest baseline for equities).
  weights re-fitted every run by ridge least squares on realised history; a variable keeps weight only if it cuts
  walk-forward error by at least 1% versus drift, and the model must beat both 'no change' and drift. Otherwise weights are 0.
"""
import json, csv, math, bisect, statistics as st
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LIVE, PRED, MODEL = ROOT / "data/live.json", ROOT / "data/predictions.json", ROOT / "data/model.json"
IST = timezone(timedelta(hours=5, minutes=30))
VERSION_BASE = "v1"
H = {21: "1 month", 63: "3 months"}
BAND = {21: 2.0, 63: 4.0}        # % move treated as 'flat'
RIDGE = 0.5
WARM = 750                        # samples (~3 years) before the first walk-forward forecast
STEP = 5
VARS = ["momentum", "trend", "valuation", "volatility", "rupee"]
PE_BREAK = "2021-03-31"
VAL_BANDS = [(20, "cheap"), (40, "below_avg"), (60, "around_avg"), (80, "above_avg"), (101, "expensive")]
VIX_BANDS = [(33.4, "calm"), (66.7, "normal"), (101, "nervous")]


class S:
    def __init__(self, hist):
        self.d = [a for a, _ in hist]; self.v = [b for _, b in hist]

    def at(self, day):
        i = bisect.bisect_right(self.d, day) - 1
        return self.v[i] if i >= 0 else None


def pctile(sorted_vals, x):
    return 100.0 * bisect.bisect_left(sorted_vals, x) / len(sorted_vals)


def band_of(p, bands):
    for lim, name in bands:
        if p < lim:
            return name
    return bands[-1][1]


def build(live):
    it = live["items"]
    px = it["nifty"]["history"]
    d = [a for a, _ in px]; c = np.array([b for _, b in px], dtype=float)
    pb, vix, inr = S(it["pb"]["history"]), S(it["vix"]["history"]) if "vix" in it else None, S(it["usdinr_hist"]["history"]) if "usdinr_hist" in it else None
    n = len(c)
    sma = lambda k: np.array([c[max(0, i - k + 1): i + 1].mean() if i >= k - 1 else np.nan for i in range(n)])
    s50, s200 = sma(50), sma(200)
    rows = []
    for i in range(n):
        rows.append(dict(d=d[i], c=c[i], s50=s50[i], s200=s200[i], pb=pb.at(d[i]), vix=vix.at(d[i]) if vix else None, inr=inr.at(d[i]) if inr else None))
    return rows


def trend_state(r):
    if np.isnan(r["s200"]):
        return None
    if r["c"] > r["s200"] and r["s50"] > r["s200"]:
        return "rising"
    if r["c"] < r["s200"] and r["s50"] < r["s200"]:
        return "falling"
    return "mixed"


def fwd(rows, i, h):
    return 100 * (rows[i + h]["c"] / rows[i]["c"] - 1) if i + h < len(rows) else None


def describe(vals):
    if not vals:
        return None
    v = sorted(vals)
    q = lambda p: v[min(len(v) - 1, int(p * len(v)))]
    return dict(n=len(v), median=round(q(0.5), 2), p10=round(q(0.1), 2), p90=round(q(0.9), 2), pos=round(100 * sum(x > 0 for x in v) / len(v), 1))


def condition(live, rows):
    it = live["items"]; L = len(rows) - 1; last = rows[L]
    pbs = sorted(r["pb"] for r in rows if r["pb"])
    pb_p = pctile(pbs, last["pb"])
    vb = band_of(pb_p, VAL_BANDS)
    pe_after = sorted(v for a, v in it["pe"]["history"] if a >= PE_BREAK)
    pe_p = pctile(pe_after, it["pe"]["value"])
    # historical meaning: forward 1-year (252 days) and 3-month returns by valuation band (full-sample percentile thresholds, descriptive)
    by_val = {}
    for i, r in enumerate(rows):
        if r["pb"]:
            b = band_of(pctile(pbs, r["pb"]), VAL_BANDS)
            for h in (63, 252):
                f = fwd(rows, i, h)
                if f is not None:
                    by_val.setdefault(b, {}).setdefault(h, []).append(f)
    by_val = {b: {str(h): describe(v) for h, v in x.items()} for b, x in by_val.items()}
    ts = trend_state(last)
    by_tr = {}
    for i, r in enumerate(rows):
        s = trend_state(r)
        if s:
            for h in (21, 63):
                f = fwd(rows, i, h)
                if f is not None:
                    by_tr.setdefault(s, {}).setdefault(h, []).append(f)
    by_tr = {b: {str(h): describe(v) for h, v in x.items()} for b, x in by_tr.items()}
    allf = {str(h): describe([f for f in (fwd(rows, i, h) for i in range(len(rows))) if f is not None]) for h in (21, 63, 252)}
    out = dict(as_of=last["d"], close=last["c"], s50=round(float(last["s50"]), 2), s200=round(float(last["s200"]), 2),
               dist200_pct=round(100 * (last["c"] / last["s200"] - 1), 2), trend=ts, trend_hist=by_tr,
               pb=last["pb"], pb_pctile=round(pb_p, 1), pb_since=pbs and rows[next(i for i, r in enumerate(rows) if r["pb"])]["d"], val_band=vb, val_hist=by_val,
               pe=it["pe"]["value"], pe_pctile_since_2021=round(pe_p, 1), pe_band_since_2021=band_of(pe_p, VAL_BANDS), dy=it["dy"]["value"], all_days=allf)
    if "vix" in it:
        vx = sorted(v for _, v in it["vix"]["history"])
        vp = pctile(vx, it["vix"]["value"])
        vixs = S(it["vix"]["history"])
        by_v = {}
        for i, r in enumerate(rows):
            v = vixs.at(r["d"]) if r["d"] >= it["vix"]["history"][0][0] else None
            if v:
                f = fwd(rows, i, 63)
                if f is not None:
                    by_v.setdefault(band_of(pctile(vx, v), VIX_BANDS), []).append(f)
        out.update(vix=it["vix"]["value"], vix_pctile=round(vp, 1), vix_band=band_of(vp, VIX_BANDS), vix_since=it["vix"]["history"][0][0],
                   vix_hist={b: describe(v) for b, v in by_v.items()})
    # macro backdrop
    m = {}
    if "in10" in it:
        ey = 100 / it["pe"]["value"]
        m["ey_gap"] = round(ey - it["in10"]["value"], 2); m["ey"] = round(ey, 2)
        in10 = S([[a[:7], v] for a, v in it["in10"]["history"]])
        gaps = sorted(100 / v - in10.at(a[:7]) for a, v in it["pe"]["history"] if a >= PE_BREAK and in10.at(a[:7]))
        m["ey_gap_pctile_since_2021"] = round(pctile(gaps, m["ey_gap"]), 1) if gaps else None
    if "cpi" in it and "repo" in it:
        m["real_repo"] = round(it["repo"]["value"] - it["cpi"]["value"], 2)
    if "in10" in it and "cpi" in it:
        m["real_10y"] = round(it["in10"]["value"] - it["cpi"]["value"], 2)
    for k, days in (("usdinr_hist", 91), ("brent", 91)):
        if k in it:
            h = S(it[k]["history"]); ref = (date.fromisoformat(it[k]["as_of"]) - timedelta(days=days)).isoformat()
            if h.at(ref):
                m[k + "_3m_pct"] = round(100 * (it[k]["value"] / h.at(ref) - 1), 2)
    for k in ("fii", "dii"):
        if k in it:
            hist = it[k]["history"]; m[k + "_last"] = it[k]["value"]; m[k + "_days"] = len(hist)
            m[k + "_sum_recent"] = round(sum(v for _, v in hist[-5:]), 2); m[k + "_n_recent"] = min(5, len(hist))
    out["macro"] = m
    return out


# ---------- forecast model ----------
def table(rows, h):
    pbs = [r["pb"] for r in rows]
    out = []
    vix_med = None
    for i in range(252 * 5, len(rows)):
        r = rows[i]
        if None in (r["pb"], r["inr"]) or np.isnan(r["s200"]) or rows[i - h]["inr"] is None:
            continue
        past_pb = [x for x in pbs[i - 252 * 5: i] if x]
        past_vix = [rows[j]["vix"] for j in range(max(0, i - 252), i) if rows[j]["vix"]]
        if r["vix"] is None or len(past_vix) < 200:
            continue
        x = np.array([100 * math.log(r["c"] / rows[i - h]["c"]), 100 * (r["c"] / r["s200"] - 1), -100 * math.log(r["pb"] / st.median(past_pb)),
                      r["vix"] - st.median(past_vix), 100 * math.log(r["inr"] / rows[i - h]["inr"])])
        y = 100 * math.log(rows[i + h]["c"] / r["c"]) if i + h < len(rows) else None
        out.append((i, r["d"], x, y, rows[i + h]["d"] if i + h < len(rows) else None))
    return out


def fit(tab, mask, before_i, h):
    sub = [t for t in tab if t[3] is not None and t[0] + h <= before_i]
    if len(sub) < 250:
        return None
    y = np.array([t[3] for t in sub]); drift = float(y.mean())
    m = np.array(mask, dtype=float)
    if not m.any():
        return np.zeros(len(VARS)), np.zeros(len(VARS)), drift, len(sub)
    X = np.array([t[2] for t in sub]); mu = X.mean(axis=0); Xc = (X - mu) * m
    w = np.linalg.solve(Xc.T @ Xc + RIDGE * len(y) * np.eye(len(VARS)), Xc.T @ (y - drift)) * m
    return w, mu, drift, len(sub)


def band(p, h):
    return "up" if p > BAND[h] else "down" if p < -BAND[h] else "flat"


def backtest(tab, h, mask):
    res = []
    for k in range(WARM, len(tab), STEP):
        i, d, x, y, _ = tab[k]
        if y is None:
            continue
        f = fit(tab, mask, i, h)
        if not f:
            continue
        w, mu, drift, _ = f
        res.append((d, drift + float(w @ (x - mu)), drift, y))
    if not res:
        return None
    mae = lambda j: round(st.mean(abs(r[j] - r[3]) for r in res), 3)
    hit = lambda f: round(100 * sum(band(f(r), h) == band(r[3], h) for r in res) / len(res), 1)
    return dict(n=len(res), start=res[0][0], end=res[-1][0], mae=mae(1), drift_mae=mae(2), naive_mae=round(st.mean(abs(r[3]) for r in res), 3),
                hit=hit(lambda r: r[1]), drift_hit=hit(lambda r: r[2]), naive_hit=hit(lambda r: 0.0),
                up_share=round(100 * sum(r[3] > 0 for r in res) / len(res), 1))


def gate(tab, h):
    base = backtest(tab, h, [0] * len(VARS))
    single, mask = {}, []
    for j, v in enumerate(VARS):
        b = backtest(tab, h, [int(k == j) for k in range(len(VARS))])
        single[v] = b
        mask.append(int(b["mae"] <= 0.99 * base["drift_mae"]))
    gated = backtest(tab, h, mask) if any(mask) else None
    reason = ("kept: " + ", ".join(v for v, k in zip(VARS, mask) if k)) if any(mask) else "no variable cut walk-forward error by 1% or more versus drift"
    if gated and not (gated["mae"] < gated["drift_mae"] and gated["mae"] < gated["naive_mae"]):
        mask = [0] * len(VARS); reason = "kept variables together did not beat both drift and 'no change'"
    return dict(mask=mask, single=single, base=base, gated=gated if any(mask) else None, ungated=backtest(tab, h, [1] * len(VARS)), reason=reason)


def main():
    live = json.loads(LIVE.read_text())
    rows = build(live)
    today = datetime.now(IST).date()
    cond = condition(live, rows)
    old = json.loads(MODEL.read_text()) if MODEL.exists() else {}
    ledger = json.loads(PRED.read_text()) if PRED.exists() else {"predictions": []}
    idx = {r["d"]: i for i, r in enumerate(rows)}
    L = len(rows) - 1
    models = {}
    for h in H:
        tab = table(rows, h)
        g = gate(tab, h)
        w, mu, drift, n = fit(tab, g["mask"], L + h, h)
        last = tab[-1]
        pred = drift + float(w @ (last[2] - mu)) if last[1] == rows[L]["d"] else drift
        models[str(h)] = dict(horizon_days=h, label=H[h], vars=VARS, weights=[round(float(x), 4) for x in w], mask=g["mask"], gate_reason=g["reason"],
                              baseline=g["base"], backtest=g["gated"] or g["base"], single=g["single"], ungated=g["ungated"], n_fit=n,
                              drift_pct=round(drift, 3), pred_pct=round(pred, 3), pred_band=band(pred, h), band_pct=BAND[h],
                              features_now=dict(zip(VARS, [round(float(x), 3) for x in last[2]])), model_has_edge=any(g["mask"]))
    # ledger: one entry per horizon per trading day; scored when h more trading days exist
    preds = ledger["predictions"]; scored_now = []
    for p in preds:
        if p.get("scored") or p["data_date"] not in idx:
            continue
        i = idx[p["data_date"]]
        if i + p["horizon_days"] <= L:
            r = rows[i + p["horizon_days"]]
            act = 100 * math.log(r["c"] / p["close"])
            p.update(scored=True, realised_date=r["d"], realised_close=r["c"], realised_pct=round(act, 3), error=round(p["pred_pct"] - act, 3),
                     band_hit=band(p["pred_pct"], p["horizon_days"]) == band(act, p["horizon_days"]),
                     drift_band_hit=band(p["drift_pct"], p["horizon_days"]) == band(act, p["horizon_days"]),
                     naive_band_hit=band(0, p["horizon_days"]) == band(act, p["horizon_days"]), scored_on=today.isoformat())
            scored_now.append(p["id"])
    sig = {h: dict(mask=m["mask"], weights=m["weights"]) for h, m in models.items()}
    version, changelog = old.get("version"), old.get("changelog", [])
    if not version:
        version = f"{VERSION_BASE}.0"; changelog = [dict(version=version, date=today.isoformat(), change="First version. Weights start from the walk-forward gate; zero where nothing earned weight.")]
    elif old.get("signature") != sig:
        version = f"{VERSION_BASE}.{int(version.split('.')[1]) + 1}"
        changelog.append(dict(version=version, date=today.isoformat(), change="Re-fit: " + "; ".join(f"{H[int(h)]}: weights {m['weights']} ({m['gate_reason']})" for h, m in models.items())))
    dd = rows[L]["d"]
    for h, m in models.items():
        pid = f"{dd}-{h}d"
        if not any(p["id"] == pid for p in preds):
            preds.append(dict(id=pid, made_on=today.isoformat(), data_date=dd, close=rows[L]["c"], horizon_days=int(h), model_version=version,
                              pred_pct=m["pred_pct"], pred_band=m["pred_band"], drift_pct=m["drift_pct"], weights=m["weights"], scored=False))
    sc = [p for p in preds if p.get("scored")]
    lessons = []
    for h, m in models.items():
        b = m["baseline"]; g = m["backtest"]
        lessons.append(f"{m['label']} ({h} trading days) walk-forward back-test {b['start']} to {b['end']}, {b['n']} forecasts: model error {g['mae']}% vs drift {b['drift_mae']}% vs 'no change' {b['naive_mae']}%; "
                       f"band right {g['hit']}% vs drift {b['drift_hit']}% vs 'no change' {b['naive_hit']}%. Nifty rose over {h} days {b['up_share']}% of the time. Gate: {m['gate_reason']}.")
        if not m["model_has_edge"]:
            lessons.append(f"{m['label']}: no variable has earned weight, so the forecast is just the historical drift ({m['drift_pct']}% in log terms).")
    lessons.append(f"Live research log: {len(sc)} forecasts scored so far" + (" (too few to judge)." if len(sc) < 20 else "."))
    model = dict(version=version, generated_ist=datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"), data_date=dd, signature=sig, changelog=changelog,
                 condition=cond, models=models, lessons=lessons, bands=dict(valuation=VAL_BANDS, vix=VIX_BANDS), pe_break=PE_BREAK,
                 live_score={h: dict(n=len(s), band_hit=round(100 * sum(p["band_hit"] for p in s) / len(s), 1) if s else None,
                                     drift_band_hit=round(100 * sum(p["drift_band_hit"] for p in s) / len(s), 1) if s else None,
                                     naive_band_hit=round(100 * sum(p["naive_band_hit"] for p in s) / len(s), 1) if s else None)
                             for h in models for s in [[p for p in sc if str(p["horizon_days"]) == h]]})
    ledger["predictions"] = preds[-3000:]
    PRED.write_text(json.dumps(ledger, indent=0))
    cols = ["id", "made_on", "data_date", "horizon_days", "model_version", "close", "pred_pct", "pred_band", "drift_pct", "scored", "realised_date", "realised_close", "realised_pct", "error", "band_hit", "drift_band_hit", "naive_band_hit"]
    with open(ROOT / "data/track_record.csv", "w", newline="") as fh:
        wr = csv.writer(fh); wr.writerow(cols)
        for p in preds:
            wr.writerow([p.get(c, "") for c in cols])
    arch = ROOT / "data/models"; arch.mkdir(exist_ok=True)
    if not (arch / f"model_{version}.json").exists():
        (arch / f"model_{version}.json").write_text(json.dumps(model, indent=1))
    MODEL.write_text(json.dumps(model, indent=1))
    print("model", version, "| data", dd, "| valuation", cond["val_band"], cond["pb_pctile"], "| trend", cond["trend"], "| vix", cond.get("vix_band"), "| scored now", len(scored_now))
    for l in lessons:
        print(" -", l)


if __name__ == "__main__":
    main()
