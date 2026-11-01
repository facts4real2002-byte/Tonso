"""Gjenerimi i sinjaleve BUY / SELL / HOLD me një pikëzim (score) nga -100 deri +100.

Çdo komponent jep një votë; pesha e trendit rritet kur ADX tregon trend të fortë,
pesha e mean-reversion rritet kur tregu është anësor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .indicators import add_all


@dataclass
class Signal:
    action: str            # BUY / SELL / HOLD
    score: float           # -100 .. +100
    price: float
    stop_loss: float | None
    take_profit: float | None
    reasons: list[str] = field(default_factory=list)


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Llogarit score-in për çdo qiri (pa parë të ardhmen)."""
    d = add_all(df)
    c = d["close"]

    trend = np.sign(d["ema_fast"] - d["ema_slow"]) * 0.6 + np.sign(c - d["ema_trend"]) * 0.4
    momentum = np.tanh(d["macd_hist"] / (d["atr"] * 0.1 + 1e-12)) * 0.5 + np.sign(d["macd"]) * 0.5
    # mean reversion: RSI i ulët / çmimi nën bandën e poshtme -> pozitiv
    mr = ((50 - d["rsi"]) / 30).clip(-1, 1) * 0.5
    bb_pos = (c - d["bb_mid"]) / (d["bb_high"] - d["bb_mid"]).replace(0, np.nan)
    mr += (-bb_pos.fillna(0)).clip(-1, 1) * 0.5

    trend_w = (d["adx"] / 40).clip(0.2, 1.0)     # trend i fortë -> më shumë peshë trendit
    mr_w = 1.0 - trend_w
    raw = trend_w * (0.6 * trend + 0.4 * momentum) + mr_w * mr
    # konfirmim volumi
    raw *= np.where(d["vol_ratio"] > 1.2, 1.15, 1.0)

    d["score"] = (raw.clip(-1, 1) * 100).round(1)
    d.loc[d.index[:200], "score"] = 0.0  # periudhë ngrohjeje e indikatorëve
    return d


def latest_signal(df: pd.DataFrame, threshold: float = 40, sl_atr: float = 1.5, tp_atr: float = 2.0) -> Signal:
    d = score_frame(df)
    row = d.iloc[-1]
    s = float(row["score"])
    price = float(row["close"])
    a = float(row["atr"])

    reasons = []
    reasons.append(f"Trend: EMA20 {'>' if row['ema_fast'] > row['ema_slow'] else '<'} EMA50, "
                   f"çmimi {'mbi' if price > row['ema_trend'] else 'nën'} EMA200")
    reasons.append(f"RSI = {row['rsi']:.1f}" + (" (mbishitur)" if row["rsi"] > 70 else " (mbiblerë)" if row["rsi"] < 30 else ""))
    reasons.append(f"MACD hist = {row['macd_hist']:.4g} ({'pozitiv' if row['macd_hist'] > 0 else 'negativ'})")
    reasons.append(f"ADX = {row['adx']:.1f} ({'trend i fortë' if row['adx'] > 25 else 'treg anësor'})")
    reasons.append(f"Volumi = {row['vol_ratio']:.2f}x mesatarja")

    if s >= threshold:
        return Signal("BUY", s, price, price - sl_atr * a, price + tp_atr * a, reasons)
    if s <= -threshold:
        return Signal("SELL", s, price, price + sl_atr * a, price - tp_atr * a, reasons)
    return Signal("HOLD", s, price, None, None, reasons)
