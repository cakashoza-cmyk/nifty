"""Nifty market-condition desk: data refresh. Free public sources only, no keys. Writes data/live.json.
Each source is fetched independently; on failure the last good value is kept and marked stale.
Same pattern as STTIE, Gold Desk and LGD Desk (github.com/cakashoza-cmyk)."""
import json, re, ssl, html, sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "live.json"
IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
NOW = datetime.now(IST)
NI_URL = "https://www.niftyindices.com/reports/historical-data"


def get(url, data=None, headers=None, timeout=60, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5)


def check(v, lo, hi, name):
    if v is None or not (lo <= v <= hi):
        raise ValueError(f"{name}={v} outside sanity range {lo}-{hi}")
    return v


def merge_hist(old, new):
    d = {a: b for a, b in (old or [])}
    d.update({a: b for a, b in new})
    return [[k, d[k]] for k in sorted(d)]


# ---------- NSE Indices (niftyindices.com) ----------
def ni(endpoint, name, start, end):
    body = json.dumps({"cinfo": "{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (name, start.strftime("%m/%d/%Y"), end.strftime("%m/%d/%Y"), name)}).encode()
    return json.loads(get("https://www.niftyindices.com/BackPage/" + endpoint, body,
                          {"Content-Type": "application/json; charset=utf-8", "Referer": NI_URL, "X-Requested-With": "XMLHttpRequest"}))


def iso(s):
    return datetime.strptime(s.strip(), "%d %b %Y").strftime("%Y-%m-%d")


def ni_series(endpoint, name, prev_hist, first, parse):
    """Full history on the first run (one call per year), then only the last 40 days."""
    start = date.fromisoformat(prev_hist[-1][0]) - timedelta(days=40) if prev_hist else first
    out, s = [], start
    while s <= NOW.date():
        e = min(s + timedelta(days=364), NOW.date())
        out += [x for x in (parse(r) for r in ni(endpoint, name, s, e)) if x]
        print(f"    {name} {endpoint[3:12]} {s}..{e}: {len(out)} rows", flush=True)
        s = e + timedelta(days=1)
    return merge_hist(prev_hist, out)


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def nifty(prev):
    common = dict(source="NSE Indices Ltd (niftyindices.com), Historical Data report", source_url=NI_URL, status="official")
    px = ni_series("getHistoricaldatatabletoString", "NIFTY 50", prev.get("nifty", {}).get("history"), date(1999, 1, 1),
                   lambda r: [iso(r["HistoricalDate"]), num(r["CLOSE"])] if num(r["CLOSE"]) else None)
    pe_rows = ni_series("getpepbHistoricaldataDBtoString", "NIFTY 50", prev.get("pe", {}).get("rows"), date(1999, 1, 1),
                        lambda r: [iso(r["DATE"]), [num(r["pe"]), num(r["pb"]), num(r["divYield"])]])
    d, v = px[-1]
    out = {"nifty": dict(label="Nifty 50 closing level", value=check(v, 3000, 100000, "nifty"), unit="index points", as_of=d,
                         note="Official end-of-day close published by NSE Indices. Updated after market close.", history=px, **common)}
    pd_, (pe, pb, dy) = pe_rows[-1]
    note = ("Published daily by NSE Indices. From 31 Mar 2021 the P/E uses consolidated earnings (earlier: standalone), so P/E before and after "
            "that date is not like-for-like (it fell from 40.4 to 33.2 overnight). P/B and dividend yield did not change basis.")
    out["pe"] = dict(label="Nifty 50 P/E (price to earnings)", value=check(pe, 5, 100, "pe"), unit="times", as_of=pd_, note=note, rows=pe_rows,
                     history=[[a, b[0]] for a, b in pe_rows if b[0]], **common)
    out["pb"] = dict(label="Nifty 50 P/B (price to book)", value=check(pb, 0.5, 15, "pb"), unit="times", as_of=pd_, note=note,
                     history=[[a, b[1]] for a, b in pe_rows if b[1]], **common)
    out["dy"] = dict(label="Nifty 50 dividend yield", value=check(dy, 0.1, 10, "dy"), unit="%", as_of=pd_, note=note,
                     history=[[a, b[2]] for a, b in pe_rows if b[2]], **common)
    return out


def vix(prev):
    h = ni_series("getHistoricaldatatabletoString", "INDIA VIX", prev.get("vix", {}).get("history"), date(2008, 3, 1),
                  lambda r: [iso(r["HistoricalDate"]), num(r["CLOSE"])] if num(r["CLOSE"]) else None)
    return dict(label="India VIX (expected volatility)", value=check(h[-1][1], 5, 100, "vix"), unit="index (annualised %)", as_of=h[-1][0],
                source="NSE Indices Ltd (niftyindices.com), Historical Data report", source_url=NI_URL, status="official",
                note="NSE's measure of how much the market expects Nifty to move over the next 30 days. Higher = more nervous.", history=h)


def rbi():
    t = get("https://www.rbi.org.in/").decode("utf-8", "ignore")
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    repo = float(re.search(r"Policy Repo Rate\s*:\s*([\d.]+)\s*%", t).group(1))
    usd = float(re.search(r"INR\s*/\s*1 USD\s*:\s*([\d.]+)", t).group(1))
    m = re.search(r"\(As at [^)]*? of (\w+ \d{1,2}, \d{4})\)", t)
    fx_date = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d") if m else NOW.strftime("%Y-%m-%d")
    return {"repo": dict(label="RBI policy repo rate", value=check(repo, 2, 12, "repo"), unit="% p.a.", as_of=NOW.strftime("%Y-%m-%d"),
                         source="Reserve Bank of India homepage, 'Current Rates'", source_url="https://www.rbi.org.in/", status="official",
                         note="Date shown is the date we read it from the RBI site."),
            "usdinr": dict(label="USD/INR reference rate", value=check(usd, 60, 140, "usdinr"), unit="₹ per US$", as_of=fx_date,
                           source="FBIL reference rate, as shown on RBI homepage", source_url="https://www.fbil.org.in/", status="official",
                           note="Set once a day around 1:30 pm IST.")}


def ecb():
    j = json.loads(get(f"https://api.frankfurter.dev/v1/2005-01-01..?base=USD&symbols=INR"))
    h = [[d, j["rates"][d]["INR"]] for d in sorted(j["rates"])]
    return dict(label="USD/INR (ECB cross rate), daily history", value=check(h[-1][1], 40, 140, "inr"), unit="₹ per US$", as_of=h[-1][0],
                source="European Central Bank reference rates via Frankfurter API", source_url="https://www.frankfurter.app/", status="live",
                note="Used for history and back-tests; the FBIL rate is used for today's figure.", history=h)


def mospi(prev):
    j = json.loads(get(f"https://api.mospi.gov.in/api/cpi/getCPIData?base_year=2024&series=Current&year={NOW.year}&format=JSON"))
    rows = [r for r in j["data"] if r["state"] == "All India" and r["sector"] == "Combined" and r["division"] == "CPI (General)" and r.get("inflation")]
    if not rows and NOW.month <= 2:
        j = json.loads(get(f"https://api.mospi.gov.in/api/cpi/getCPIData?base_year=2024&series=Current&year={NOW.year - 1}&format=JSON"))
        rows = [r for r in j["data"] if r["state"] == "All India" and r["sector"] == "Combined" and r["division"] == "CPI (General)" and r.get("inflation")]
    mon = lambda r: datetime.strptime(r["year"] + " " + r["month"], "%Y %B").strftime("%Y-%m")
    rows.sort(key=mon)
    r = rows[-1]
    hist = merge_hist(prev.get("cpi", {}).get("history"), [[mon(x), float(x["inflation"])] for x in rows])
    return dict(label="India CPI inflation (all-India, combined), year on year", value=check(float(r["inflation"]), -5, 25, "cpi"), unit="%", as_of=mon(r),
                index=float(r["index"]), source="MoSPI CPI API (base 2024)", source_url="https://api.mospi.gov.in/cpi", status="official",
                note="Official monthly CPI, released around the 12th of the next month. History accumulates from each refresh.", history=hist)


FRED = {"us10": ("DGS10", "US 10-year government bond yield", "% p.a.", -1, 15),
        "brent": ("DCOILBRENTEU", "Brent crude oil price", "US$ per barrel", 5, 300),
        "in10": ("INDIRLTLT01STM", "India 10-year government bond yield (monthly)", "% p.a.", 2, 15)}


def fred(key):
    sid, label, unit, lo, hi = FRED[key]
    rows = [l.split(",") for l in get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=90, tries=3).decode().strip().splitlines()[1:]]
    hist = [[d, float(v)] for d, v in rows if v not in (".", "")]
    if key != "in10":
        hist = [x for x in hist if x[0] >= "2004-01-01"]
    note = {"in10": "Monthly average of the benchmark 10-year G-sec yield (OECD, from RBI data), via FRED. Published with a lag of a few weeks; date = month.",
            "us10": "Official US Treasury data via the Federal Reserve, 1-3 day lag.", "brent": "US EIA daily Brent spot price via FRED, a few days' lag."}[key]
    return dict(label=label, value=check(hist[-1][1], lo, hi, key), unit=unit, as_of=hist[-1][0][:7] if key == "in10" else hist[-1][0],
                source=f"FRED, Federal Reserve Bank of St. Louis (series {sid})", source_url=f"https://fred.stlouisfed.org/series/{sid}", status="official", note=note, history=hist)


def fiidii(prev):
    j = json.loads(get("https://www.nseindia.com/api/fiidiiTradeReact", headers={"Referer": "https://www.nseindia.com/reports/fii-dii", "Accept": "application/json"}, timeout=30))
    out = {}
    for r in j:
        k = "fii" if r["category"].startswith("FII") else "dii" if r["category"] == "DII" else None
        if not k:
            continue
        d = datetime.strptime(r["date"], "%d-%b-%Y").strftime("%Y-%m-%d")
        hist = merge_hist(prev.get(k, {}).get("history"), [[d, float(r["netValue"])]])
        out[k] = dict(label=("Foreign (FII/FPI)" if k == "fii" else "Domestic institutions (DII)") + " net buying in cash market, provisional",
                      value=check(float(r["netValue"]), -100000, 100000, k), unit="₹ crore (net, one day)", as_of=d,
                      source="NSE provisional FII/DII cash-market data", source_url="https://www.nseindia.com/reports/fii-dii", status="official",
                      note="Provisional, one trading day; NSE's site often refuses automated requests, so days can be missing. History accumulates from each refresh.", history=hist[-500:])
    if not out:
        raise ValueError("no FII/DII rows")
    return out


def headlines():
    q = '(Nifty OR Sensex) (market OR RBI OR inflation OR FII) when:7d'
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-IN&gl=IN&ceid=IN:en"
    root = ET.fromstring(get(url))
    items = []
    for it in root.iter("item"):
        t = (it.findtext("title") or "").lstrip("| ").strip()
        if any(x["title"] == t for x in items):
            continue
        d = datetime.strptime(it.findtext("pubDate"), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc).astimezone(IST)
        items.append({"title": t, "date": d.strftime("%Y-%m-%d"), "url": it.findtext("link")})
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[:12]


def main():
    prev = json.loads(OUT.read_text()) if OUT.exists() else {"items": {}}
    P = prev["items"]
    items, errors, groups = {}, {}, {}

    def run(name, fn, keys=None):
        try:
            r = fn()
            r = r if keys is None else {keys: r}
            for k in r:
                groups[k] = name
            items.update(r)
        except Exception as e:  # noqa: BLE001
            errors[name] = f"{type(e).__name__}: {e}"[:300]
            for k, old in P.items():
                if old.get("group") == name and k not in items:
                    old = dict(old); old["status"] = "stale"; old["stale_reason"] = errors[name]
                    items[k] = old

    run("niftyindices", lambda: nifty(P))
    run("vix", lambda: vix(P), "vix")
    run("rbi", rbi)
    run("ecb", ecb, "usdinr_hist")
    run("mospi", lambda: mospi(P), "cpi")
    for k in FRED:
        run("fred_" + k, lambda k=k: fred(k), k)
    run("nse_fiidii", lambda: fiidii(P))
    for k, v in items.items():
        if k in groups:
            v["group"] = groups[k]
    try:
        news = headlines()
    except Exception as e:  # noqa: BLE001
        errors["news"] = str(e)[:300]; news = prev.get("headlines", [])
    out = {"generated_ist": NOW.strftime("%Y-%m-%d %H:%M IST"), "items": items, "errors": errors, "headlines": news,
           "headlines_source": "Google News RSS search (public). Headlines only; never used in any number or reading."}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("items:", len(items), "| errors:", json.dumps(errors))
    for k, v in items.items():
        print(f"  {k:12s} {v['value']:>10} {v['unit']:28s} as of {v['as_of']}  [{v['status']}]  hist={len(v.get('history', []))}")
    if "nifty" not in items:
        sys.exit(2)


if __name__ == "__main__":
    main()
