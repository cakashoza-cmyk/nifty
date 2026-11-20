# Nifty Condition Desk

Educational research log on where the Nifty 50 stands against its own history (valuation, trend, volatility, economic backdrop), with a scored forecast log. Gujarati-first, with Hindi and English. Same structure as [STTIE](https://github.com/cakashoza-cmyk/sttie), [Gold Desk](https://github.com/cakashoza-cmyk/gold) and [LGD Desk](https://github.com/cakashoza-cmyk/lgd).

**Educational research only. Not investment advice. The author is not a SEBI-registered Investment Adviser or Research Analyst. Past patterns do not guarantee anything. No derivatives (F&O) and no individual stocks.**

Live: https://cakashoza-cmyk.github.io/nifty/ · Methodology: methodology.html

- `scripts/fetch.py`: NSE Indices (Nifty 50 close, P/E, P/B, dividend yield, India VIX), RBI/FBIL, MoSPI CPI, FRED, NSE FII/DII, Google News RSS → `data/live.json`.
- `scripts/model.py`: condition read, walk-forward model with weight gate, dated forecast log (`data/predictions.json`), scoring, `data/model.json`, `data/models/`, `data/track_record.csv`.
- `.github/workflows/refresh.yml`: weekdays 08:30, 14:30, 20:30 IST.
- Tests: `python3 -m unittest discover -s test -p "test_*.py"`; wording check: `python3 test/wordcheck.py`; browser check: `test/verify.py`.

No keys, no backend, no AI-generated numbers or text.
