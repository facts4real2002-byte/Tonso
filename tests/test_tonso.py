import unittest

import numpy as np

from tonso import data
from tonso.backtest import run
from tonso.indicators import add_all, rsi
from tonso.scenarios import historical_signal_odds, monte_carlo
from tonso.signals import latest_signal, score_frame


class TestTonso(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = data.synthetic(n=1500, seed=1)

    def test_indicators_no_nan_after_warmup(self):
        d = add_all(self.df).iloc[200:]
        self.assertFalse(d[["rsi", "atr", "macd", "adx"]].isna().any().any())
        self.assertTrue(((d["rsi"] >= 0) & (d["rsi"] <= 100)).all())

    def test_rsi_extremes(self):
        up = data.pd.Series(np.arange(1, 100, dtype=float))
        self.assertGreater(rsi(up).iloc[-1], 95)

    def test_score_has_no_lookahead(self):
        full = score_frame(self.df)["score"]
        partial = score_frame(self.df.iloc[:1000])["score"]
        np.testing.assert_allclose(full.iloc[:1000].to_numpy(), partial.to_numpy())

    def test_score_bounds_and_signal(self):
        s = score_frame(self.df)["score"]
        self.assertTrue(((s >= -100) & (s <= 100)).all())
        sig = latest_signal(self.df)
        self.assertIn(sig.action, {"BUY", "SELL", "HOLD"})
        if sig.action == "BUY":
            self.assertLess(sig.stop_loss, sig.price)
            self.assertGreater(sig.take_profit, sig.price)

    def test_monte_carlo_probabilities_sum_to_one(self):
        mc = monte_carlo(self.df["close"], horizon=24)
        self.assertAlmostEqual(mc.p_hit_tp + mc.p_hit_sl + mc.p_neither, 1.0, places=6)
        self.assertAlmostEqual(sum(p for p, _ in mc.scenarios.values()), 1.0, places=6)
        self.assertLess(mc.percentiles["p5"], mc.percentiles["p95"])

    def test_historical_odds(self):
        odds = historical_signal_odds(score_frame(self.df), 30, 24, 0.01, 0.01, "BUY")
        if odds["samples"]:
            self.assertAlmostEqual(odds["p_tp"] + odds["p_sl"] + odds["p_timeout"], 1.0)

    def test_backtest_runs_and_costs_hurt(self):
        free = run(self.df, fee=0, slippage=0)
        paid = run(self.df, fee=0.001, slippage=0.0005)
        self.assertEqual(len(free.trades), len(paid.trades))
        if len(paid.trades):
            self.assertLess(paid.stats["kthimi_total_%"], free.stats["kthimi_total_%"])
        self.assertIn("dite_me_>=1%_%", paid.stats)


if __name__ == "__main__":
    unittest.main()
