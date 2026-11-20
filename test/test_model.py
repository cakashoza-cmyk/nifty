import json, sys, re, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "test"))
import model as m  # noqa: E402
import fetch as F  # noqa: E402
import wordcheck as W  # noqa: E402


class Logic(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(m.band_of(5, m.VAL_BANDS), "cheap"); self.assertEqual(m.band_of(26.1, m.VAL_BANDS), "below_avg")
        self.assertEqual(m.band_of(50, m.VAL_BANDS), "around_avg"); self.assertEqual(m.band_of(99.9, m.VAL_BANDS), "expensive")
        self.assertEqual(m.band_of(10, m.VIX_BANDS), "calm"); self.assertEqual(m.band_of(80, m.VIX_BANDS), "nervous")

    def test_pctile(self):
        self.assertEqual(m.pctile([1, 2, 3, 4], 3), 50.0); self.assertEqual(m.pctile([1, 2, 3, 4], 0), 0.0)

    def test_trend_state(self):
        self.assertEqual(m.trend_state(dict(c=110, s50=105, s200=100)), "rising")
        self.assertEqual(m.trend_state(dict(c=90, s50=95, s200=100)), "falling")
        self.assertEqual(m.trend_state(dict(c=106, s50=95, s200=100)), "mixed")

    def test_return_band(self):
        self.assertEqual(m.band(2.5, 21), "up"); self.assertEqual(m.band(-4.5, 63), "down"); self.assertEqual(m.band(1.0, 21), "flat")

    def test_headline_filter(self):
        for t in ["Top 5 stocks to buy this week", "Should you sell before Budget?", "Nifty target 27000 says broker", "Stop-loss levels for Nifty"]:
            self.assertTrue(re.search(F.RECO, t, re.I), t)
        self.assertFalse(re.search(F.RECO, "RBI keeps repo rate unchanged at 5.5%", re.I))

    def test_wordcheck(self):
        self.assertEqual(W.scan("Educational research only. Not investment advice."), [])
        self.assertTrue(W.scan("You should buy now")); self.assertTrue(W.scan("અત્યારે ખરીદો")); self.assertTrue(W.scan("अभी निवेश करें"))


class Data(unittest.TestCase):
    def setUp(self):
        self.live = json.loads((ROOT / "data/live.json").read_text()); self.model = json.loads((ROOT / "data/model.json").read_text())

    def test_every_item_has_source_and_date(self):
        for k, it in self.live["items"].items():
            self.assertTrue(it.get("source") and it.get("source_url") and it.get("as_of") and it.get("status"), k)

    def test_weights_only_if_earned(self):
        for h, x in self.model["models"].items():
            for w, k in zip(x["weights"], x["mask"]):
                if not k:
                    self.assertEqual(w, 0)
            if x["model_has_edge"]:
                self.assertLess(x["backtest"]["mae"], x["baseline"]["drift_mae"]); self.assertLess(x["backtest"]["mae"], x["baseline"]["naive_mae"])
            else:
                self.assertAlmostEqual(x["pred_pct"], x["drift_pct"], places=6)

    def test_no_reco_words_in_model_text(self):
        txt = " ".join(self.model["lessons"]) + " ".join(c["change"] for c in self.model["changelog"])
        self.assertEqual(W.scan(txt), [])

    def test_headlines_clean(self):
        for h in self.live.get("headlines", []):
            self.assertFalse(re.search(F.RECO, h["title"], re.I), h["title"])


if __name__ == "__main__":
    unittest.main()
