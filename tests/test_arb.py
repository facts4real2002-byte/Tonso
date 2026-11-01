"""Testet e parserave dhe llogaritjeve me përgjigje shembull në formatin e API-ve publike.

Çmimet këtu janë të shpikura për test – NUK janë të dhëna tregu.
"""
import unittest

from tonso import arb, exchanges as ex


class TestParsers(unittest.TestCase):
    def test_binance(self):
        q = ex.parse_binance_spot([
            {"symbol": "BTCUSDT", "bidPrice": "100.0", "askPrice": "100.1", "quoteVolume": "5000000"},
            {"symbol": "BTCEUR", "bidPrice": "90", "askPrice": "91", "quoteVolume": "1"},
            {"symbol": "DEADUSDT", "bidPrice": "0", "askPrice": "0", "quoteVolume": "0"}])
        self.assertEqual(list(q), ["BTC/USDT"])
        f = ex.parse_binance_funding([{"symbol": "ETHUSDT", "lastFundingRate": "0.0001", "markPrice": "3000"},
                                      {"symbol": "SOLUSDT", "lastFundingRate": "0.0002", "markPrice": "150"}],
                                     {"SOLUSDT": 4.0})
        self.assertAlmostEqual(f["ETH/USDT"].daily, 0.0003)
        self.assertAlmostEqual(f["SOL/USDT"].daily, 0.0012)

    def test_bybit(self):
        d = {"retCode": 0, "result": {"category": "spot", "list": [
            {"symbol": "ETHUSDT", "bid1Price": "3000", "ask1Price": "3000.5", "turnover24h": "2e7"}]}}
        self.assertIn("ETH/USDT", ex.parse_bybit_spot(d))
        fd = {"result": {"list": [{"symbol": "ETHUSDT", "fundingRate": "0.0001", "markPrice": "3000"}]}}
        self.assertAlmostEqual(ex.parse_bybit_funding(fd, {"ETHUSDT": 8})["ETH/USDT"].annual, 0.1095)

    def test_okx_kucoin_gate(self):
        okx = ex.parse_okx_spot({"code": "0", "data": [{"instId": "BTC-USDT", "bidPx": "100", "askPx": "100.2", "volCcy24h": "9e6"},
                                                       {"instId": "BTC-USDC", "bidPx": "100", "askPx": "100.2"}]})
        self.assertEqual(list(okx), ["BTC/USDT"])
        ku = ex.parse_kucoin_spot({"code": "200000", "data": {"ticker": [
            {"symbol": "BTC-USDT", "buy": "100", "sell": "100.1", "volValue": "3e6"}]}})
        self.assertAlmostEqual(ku["BTC/USDT"].bid, 100)
        kf = ex.parse_kucoin_funding({"data": [{"symbol": "XBTUSDTM", "fundingFeeRate": 0.0001,
                                                "fundingRateGranularity": 28800000, "markPrice": 100}]})
        self.assertIn("BTC/USDT", kf)  # XBT -> BTC
        self.assertEqual(kf["BTC/USDT"].interval_hours, 8)
        g = ex.parse_gate_spot([{"currency_pair": "BTC_USDT", "highest_bid": "100", "lowest_ask": "100.1", "quote_volume": "4e6"}])
        gf = ex.parse_gate_funding([{"name": "BTC_USDT", "funding_rate": "0.0003", "funding_interval": 28800},
                                    {"name": "OLD_USDT", "funding_rate": "0.01", "funding_interval": 28800, "in_delisting": True}])
        self.assertIn("BTC/USDT", g)
        self.assertEqual(list(gf), ["BTC/USDT"])


class TestScanner(unittest.TestCase):
    def test_spot_arb_net_after_fees(self):
        quotes = {
            "binance": {"BTC/USDT": ex.Quote(100.0, 100.05, 5e6)},
            "gate": {"BTC/USDT": ex.Quote(100.6, 100.7, 5e6)},
            "okx": {"BTC/USDT": ex.Quote(100.3, 100.9, 100)},  # pa likuiditet -> injorohet
        }
        a = arb.scan_spot(quotes)[0]
        self.assertEqual((a.buy_on, a.sell_on), ("binance", "gate"))
        self.assertAlmostEqual(a.gross, 100.6 / 100.05 - 1)
        self.assertAlmostEqual(a.net, a.gross - 0.001 - 0.002)

    def test_suspicious_gap_flagged(self):
        quotes = {"binance": {"X/USDT": ex.Quote(1.0, 1.0, 5e6)}, "gate": {"X/USDT": ex.Quote(1.5, 1.5, 5e6)}}
        self.assertTrue(arb.scan_spot(quotes)[0].suspicious)
        self.assertIn("përjashtuan", arb.format_report(arb.scan_spot(quotes), [], []))

    def test_carry_and_spread(self):
        fund = {"binance": {"ETH/USDT": ex.Funding(0.0003, 8)},
                "bybit": {"ETH/USDT": ex.Funding(-0.0001, 8)}}
        spot = {"binance": {"ETH/USDT": ex.Quote(1, 1, 5e6)}, "bybit": {"ETH/USDT": ex.Quote(1, 1, 5e6)}}
        carry = arb.scan_carry(fund, spot)
        self.assertEqual(len(carry), 1)  # funding negativ nuk është carry
        self.assertAlmostEqual(carry[0].daily, 0.0009)
        self.assertAlmostEqual(carry[0].breakeven_days, carry[0].cost / 0.0009)
        sp = arb.scan_funding_spread(fund)[0]
        self.assertEqual((sp.long_on, sp.short_on), ("bybit", "binance"))
        self.assertAlmostEqual(sp.daily_diff, 0.0012)

    def test_fetch_all_reports_errors(self):
        def boom():
            raise OSError("blocked")
        data, errors = ex.fetch_all({"ok": lambda: {"A/USDT": 1}, "bad": boom})
        self.assertIn("ok", data)
        self.assertIn("bad", errors)


if __name__ == "__main__":
    unittest.main()
