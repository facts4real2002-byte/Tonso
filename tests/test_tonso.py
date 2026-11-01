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

    def test_daily_target_and_stop(self):
        df = data.synthetic(n=4000, seed=3)
        res = run(df, daily_target=0.01, daily_stop=0.01)
        self.assertGreaterEqual(res.stats["dita_me_e_keqe_%"], -1.0 - 1e-9)  # kurrë më keq se -1%/ditë
        if len(res.trades):
            per_day = res.trades.groupby(res.trades["exit_time"].dt.normalize()).size()
            self.assertTrue((res.trades["entry_time"].dt.normalize() == res.trades["exit_time"].dt.normalize()).all())
            self.assertGreater(len(per_day), 0)
        capped = run(df, max_trades_per_day=2)
        self.assertLessEqual(capped.trades.groupby(capped.trades["entry_time"].dt.normalize()).size().max(), 2)

    def test_checks_no_lookahead(self):
        from tonso.checks import evaluate
        df = data.synthetic(n=2500, seed=5, momentum=0.2)
        full = evaluate(df)
        part = evaluate(df.iloc[:1800])
        cols = ["entry", "buy_passed", "sell_passed", "htf_ema"]
        np.testing.assert_allclose(full[cols].iloc[:1800].to_numpy(float), part[cols].to_numpy(float), equal_nan=True)

    def test_checklist_has_five_items(self):
        from tonso.checks import checklist
        action, items, _ = checklist(self.df)
        self.assertEqual(len(items), 5)
        self.assertIn(action, {"BUY", "SELL", "PRIT"})

    def test_drop_open_candle(self):
        df = self.df
        now = df.index[-1] + (df.index[1] - df.index[0]) / 2  # qiriri i fundit ende hapur
        self.assertEqual(len(data.drop_open_candle(df, now)), len(df) - 1)
        later = df.index[-1] + (df.index[1] - df.index[0]) * 2
        self.assertEqual(len(data.drop_open_candle(df, later)), len(df))

    def test_paper_trader_daily_cap_and_resume(self):
        import tempfile
        from tonso.paper import Config, PaperTrader
        df = data.synthetic(n=1500, seed=9)
        cfg = Config(symbol="T", use_checks=False, threshold=40)
        with tempfile.TemporaryDirectory() as tmp:
            tr = PaperTrader(cfg, tmp, notify_fn=lambda _: None)
            sig = tr.signals(df)
            tr.step(df.iloc[:300], sig)
            for k in range(301, 900):
                tr.step(df.iloc[:k], sig)
            # rinis nga skedari i gjendjes dhe vazhdo
            tr2 = PaperTrader(cfg, tmp, notify_fn=lambda _: None)
            self.assertAlmostEqual(tr2.state.capital, tr.state.capital)
            for k in range(900, len(df) + 1):
                tr2.step(df.iloc[:k], sig)
            days = [r for _, r in tr2.state.history]
            self.assertTrue(days)
            self.assertGreaterEqual(min(days), -1.0 - 1e-6)  # kurrë më keq se -1% në ditë


if __name__ == "__main__":
    unittest.main()
