"""Burimet e të dhënave: Binance (publik, pa çelës), CSV, ose të dhëna sintetike për testim."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

BINANCE_URLS = (
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
)

COLUMNS = ["open", "high", "low", "close", "volume"]


def fetch_binance(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 1000) -> pd.DataFrame:
    """Shkarkon qirinjtë (OHLCV) nga API publike e Binance."""
    params = urllib.parse.urlencode({"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 1000)})
    last_err: Exception | None = None
    for base in BINANCE_URLS:
        try:
            with urllib.request.urlopen(f"{base}?{params}", timeout=15) as resp:
                rows = json.loads(resp.read())
            break
        except Exception as err:  # provo URL-në tjetër
            last_err = err
    else:
        raise RuntimeError(f"Nuk mund të merren të dhënat nga Binance: {last_err}")

    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["time", *COLUMNS]
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time").astype(float)
    return df


def load_csv(path: str) -> pd.DataFrame:
    """Lexon një CSV me kolona: time/date, open, high, low, close, volume."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    time_col = next((c for c in ("time", "date", "datetime", "timestamp") if c in df.columns), None)
    if time_col is None:
        raise ValueError("CSV duhet të ketë një kolonë kohe (time/date/datetime/timestamp)")
    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.set_index(time_col).sort_index()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[COLUMNS].astype(float)


def synthetic(n: int = 2000, seed: int = 42, start_price: float = 100.0,
              drift: float = 0.0, vol: float = 0.006, freq: str = "1h") -> pd.DataFrame:
    """Gjeneron të dhëna sintetike (random walk me regjime volatiliteti).

    Shërben VETËM për të testuar kodin – nuk vërteton asnjë avantazh në treg real.
    """
    rng = np.random.default_rng(seed)
    regime = np.repeat(rng.choice([0.6, 1.0, 1.8], size=n // 100 + 1), 100)[:n]
    rets = rng.standard_t(df=4, size=n) / np.sqrt(2) * vol * regime + drift
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, vol * 0.6, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.lognormal(10, 0.5, n)
    idx = pd.date_range("2024-01-01", periods=n, freq=freq.replace("m", "min") if freq.endswith("m") else freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
