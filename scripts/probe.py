"""One-off reachability probe for candidate public sources (run on GitHub Actions). Prints status codes and first bytes only."""
import json, urllib.request, http.cookiejar
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def go(name, url, data=None, headers=None, opener=None):
    try:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        with (opener or urllib.request.build_opener()).open(req, timeout=40) as r:
            b = r.read(); print(f"OK   {name}: {r.status} {len(b)}B {b[:160]!r}")
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__}: {str(e)[:150]}")
NI = {"Content-Type": "application/json; charset=utf-8", "Referer": "https://www.niftyindices.com/reports/historical-data"}
body = lambda n: json.dumps({"cinfo": "{'name':'%s','startDate':'11/01/2026','endDate':'11/20/2026','indexName':'%s'}" % (n, n)}).encode()
go("niftyindices price", "https://www.niftyindices.com/BackPage/getHistoricaldatatabletoString", body("NIFTY 50"), NI)
go("niftyindices pepb", "https://www.niftyindices.com/BackPage/getpepbHistoricaldataDBtoString", body("NIFTY 50"), NI)
go("niftyindices vix", "https://www.niftyindices.com/BackPage/getHistoricaldatatabletoString", body("INDIA VIX"), NI)
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
go("nse home", "https://www.nseindia.com/", headers={"Accept-Language": "en-US,en;q=0.9"}, opener=op)
go("nse fiidii", "https://www.nseindia.com/api/fiidiiTradeReact", headers={"Referer": "https://www.nseindia.com/reports/fii-dii", "Accept": "application/json"}, opener=op)
go("yahoo nsei", "https://query2.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=5d&interval=1d")
go("mospi cpi", "https://api.mospi.gov.in/api/cpi/getCPIData?base_year=2024&series=Current&year=2026&format=JSON")
go("rbi", "https://www.rbi.org.in/")
go("fred dgs10", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
go("fred india10", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDIRLTLT01STM")
go("frankfurter", "https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR")
