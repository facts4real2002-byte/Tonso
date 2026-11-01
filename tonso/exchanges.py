"""Lidhja me exchange-t përmes API-ve PUBLIKE (pa llogari, pa API key).

Çdo funksion kthen të dhëna të normalizuara:
  spot:    {"BTC/USDT": Quote(bid, ask, quote_volume_24h)}
  funding: {"BTC/USDT": Funding(rate, interval_hours, mark_price)}

Vetëm çifte me USDT, që krahasimi të jetë i drejtë (USD ≠ USDT).
"""

from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

TIMEOUT = 15
UA = {"User-Agent": "tonso-scanner/0.1"}

# Tarifa standarde "taker" (pa zbritje VIP / token). Mund t'i ndryshosh sipas llogarisë tënde.
TAKER_FEE = {"binance": 0.001, "bybit": 0.001, "okx": 0.001, "kucoin": 0.001, "gate": 0.002}
PERP_TAKER_FEE = {"binance": 0.0005, "bybit": 0.00055, "okx": 0.0005, "kucoin": 0.0006, "gate": 0.0005}

ALIASES = {"XBT": "BTC"}  # KuCoin futures e quan BTC "XBT"


@dataclass
class Quote:
    bid: float
    ask: float
    quote_volume: float  # volumi 24h në USDT (0 nëse s'dihet)


@dataclass
class Funding:
    rate: float            # p.sh. 0.0001 = 0.01% për periudhë
    interval_hours: float
    mark_price: float = 0.0

    @property
    def daily(self) -> float:
        return self.rate * 24 / self.interval_hours

    @property
    def annual(self) -> float:
        return self.daily * 365


def get_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _sym(base: str, quote: str = "USDT") -> str:
    base = base.upper()
    return f"{ALIASES.get(base, base)}/{quote.upper()}"


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


# ---------------- parsers (të ndara nga rrjeti, që të testohen) ----------------

def parse_binance_spot(rows) -> dict[str, Quote]:
    out = {}
    for r in rows:
        s = r.get("symbol", "")
        if s.endswith("USDT") and _f(r.get("bidPrice")) > 0 and _f(r.get("askPrice")) > 0:
            out[_sym(s[:-4])] = Quote(_f(r["bidPrice"]), _f(r["askPrice"]), _f(r.get("quoteVolume")))
    return out


def parse_binance_funding(rows, intervals: dict[str, float] | None = None) -> dict[str, Funding]:
    intervals = intervals or {}
    out = {}
    for r in rows:
        s = r.get("symbol", "")
        if s.endswith("USDT") and r.get("lastFundingRate") not in (None, ""):
            out[_sym(s[:-4])] = Funding(_f(r["lastFundingRate"]), intervals.get(s, 8.0), _f(r.get("markPrice")))
    return out


def parse_bybit_spot(data) -> dict[str, Quote]:
    out = {}
    for r in data.get("result", {}).get("list", []):
        s = r.get("symbol", "")
        if s.endswith("USDT") and _f(r.get("bid1Price")) > 0 and _f(r.get("ask1Price")) > 0:
            out[_sym(s[:-4])] = Quote(_f(r["bid1Price"]), _f(r["ask1Price"]), _f(r.get("turnover24h")))
    return out


def parse_bybit_funding(data, intervals: dict[str, float] | None = None) -> dict[str, Funding]:
    intervals = intervals or {}
    out = {}
    for r in data.get("result", {}).get("list", []):
        s = r.get("symbol", "")
        if s.endswith("USDT") and r.get("fundingRate") not in (None, ""):
            out[_sym(s[:-4])] = Funding(_f(r["fundingRate"]), intervals.get(s, 8.0), _f(r.get("markPrice")))
    return out


def parse_okx_spot(data) -> dict[str, Quote]:
    out = {}
    for r in data.get("data", []):
        base, _, quote = r.get("instId", "").partition("-")
        if quote == "USDT" and _f(r.get("bidPx")) > 0 and _f(r.get("askPx")) > 0:
            out[_sym(base)] = Quote(_f(r["bidPx"]), _f(r["askPx"]), _f(r.get("volCcy24h")))
    return out


def parse_kucoin_spot(data) -> dict[str, Quote]:
    out = {}
    for r in data.get("data", {}).get("ticker", []):
        base, _, quote = r.get("symbol", "").partition("-")
        if quote == "USDT" and _f(r.get("buy")) > 0 and _f(r.get("sell")) > 0:
            out[_sym(base)] = Quote(_f(r["buy"]), _f(r["sell"]), _f(r.get("volValue")))
    return out


def parse_kucoin_funding(data) -> dict[str, Funding]:
    out = {}
    for r in data.get("data", []):
        s = r.get("symbol", "")
        if s.endswith("USDTM") and r.get("fundingFeeRate") is not None:
            hours = _f(r.get("fundingRateGranularity")) / 3_600_000 or 8.0  # ms -> orë
            out[_sym(s[:-5])] = Funding(_f(r["fundingFeeRate"]), hours, _f(r.get("markPrice")))
    return out


def parse_gate_spot(rows) -> dict[str, Quote]:
    out = {}
    for r in rows:
        base, _, quote = r.get("currency_pair", "").partition("_")
        if quote == "USDT" and _f(r.get("highest_bid")) > 0 and _f(r.get("lowest_ask")) > 0:
            out[_sym(base)] = Quote(_f(r["highest_bid"]), _f(r["lowest_ask"]), _f(r.get("quote_volume")))
    return out


def parse_gate_funding(rows) -> dict[str, Funding]:
    out = {}
    for r in rows:
        base, _, quote = r.get("name", "").partition("_")
        if quote == "USDT" and r.get("funding_rate") not in (None, "") and not r.get("in_delisting"):
            hours = _f(r.get("funding_interval")) / 3600 or 8.0
            out[_sym(base)] = Funding(_f(r["funding_rate"]), hours, _f(r.get("mark_price")))
    return out


# ---------------- rrjeti ----------------

def _binance_intervals() -> dict[str, float]:
    try:  # vetëm simbolet me interval jo-standard shfaqen këtu
        return {r["symbol"]: float(r["fundingIntervalHours"]) for r in get_json("https://fapi.binance.com/fapi/v1/fundingInfo")}
    except Exception:
        return {}


def _bybit_intervals() -> dict[str, float]:
    try:
        d = get_json("https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000")
        return {r["symbol"]: _f(r.get("fundingInterval")) / 60 or 8.0 for r in d["result"]["list"]}
    except Exception:
        return {}


def _binance_spot():
    # data-api.binance.vision funksionon edhe nga vende ku api.binance.com bllokohet (p.sh. serverë në SHBA)
    for url in ("https://api.binance.com/api/v3/ticker/24hr", "https://data-api.binance.vision/api/v3/ticker/24hr"):
        try:
            return parse_binance_spot(get_json(url))
        except Exception as err:
            last = err
    raise last


SPOT = {
    "binance": _binance_spot,
    "bybit": lambda: parse_bybit_spot(get_json("https://api.bybit.com/v5/market/tickers?category=spot")),
    "okx": lambda: parse_okx_spot(get_json("https://www.okx.com/api/v5/market/tickers?instType=SPOT")),
    "kucoin": lambda: parse_kucoin_spot(get_json("https://api.kucoin.com/api/v1/market/allTickers")),
    "gate": lambda: parse_gate_spot(get_json("https://api.gateio.ws/api/v4/spot/tickers")),
}

FUNDING = {
    "binance": lambda: parse_binance_funding(get_json("https://fapi.binance.com/fapi/v1/premiumIndex"), _binance_intervals()),
    "bybit": lambda: parse_bybit_funding(get_json("https://api.bybit.com/v5/market/tickers?category=linear"), _bybit_intervals()),
    "kucoin": lambda: parse_kucoin_funding(get_json("https://api-futures.kucoin.com/api/v1/contracts/active")),
    "gate": lambda: parse_gate_funding(get_json("https://api.gateio.ws/api/v4/futures/usdt/contracts")),
}


def fetch_all(sources: dict, names: list[str] | None = None) -> tuple[dict, dict]:
    """Merr paralelisht nga të gjitha exchange-t. Kthen (të_dhënat, gabimet)."""
    names = [n for n in (names or sources) if n in sources]
    results, errors = {}, {}

    def one(n):
        try:
            return n, sources[n](), None
        except Exception as err:
            return n, None, f"{type(err).__name__}: {err}"

    with ThreadPoolExecutor(max_workers=len(names) or 1) as ex:
        for n, data, err in ex.map(one, names):
            if err:
                errors[n] = err
            else:
                results[n] = data
    return results, errors
