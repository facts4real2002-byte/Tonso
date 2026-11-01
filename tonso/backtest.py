"""Backtest realist: hyrje në hapjen e qiririt të ardhshëm, TP/SL, tarifa dhe slippage.

Raporton edhe statistikën kryesore për objektivin "1% në ditë":
sa % e ditëve u arrit realisht ≥ +1%.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .signals import score_frame


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    daily: pd.Series
    stats: dict


def run(df: pd.DataFrame, threshold: float = 40, tp: float = 0.01, sl: float = 0.01,
        max_bars: int = 24, fee: float = 0.001, slippage: float = 0.0005,
        risk_per_trade: float = 1.0, allow_short: bool = True) -> BacktestResult:
    """tp/sl janë në përqindje (0.01 = 1%). risk_per_trade = pjesa e kapitalit në çdo tregti."""
    d = score_frame(df)
    o, h, l, c, s = (d[k].to_numpy() for k in ("open", "high", "low", "close", "score"))
    cost = fee + slippage  # për çdo anë

    trades = []
    equity = np.full(len(d), np.nan)
    equity[199] = 1.0
    cap = 1.0
    i = 200
    while i < len(d) - 2:
        side = 1 if s[i] >= threshold else -1 if (allow_short and s[i] <= -threshold) else 0
        if side == 0:
            i += 1
            continue
        entry_i = i + 1
        entry = o[entry_i]
        tp_px = entry * (1 + side * tp)
        sl_px = entry * (1 - side * sl)
        exit_px, exit_i, reason = None, None, "timeout"
        for j in range(entry_i, min(entry_i + max_bars, len(d))):
            hit_sl = l[j] <= sl_px if side == 1 else h[j] >= sl_px
            hit_tp = h[j] >= tp_px if side == 1 else l[j] <= tp_px
            if hit_sl:  # konservativ
                exit_px, exit_i, reason = sl_px, j, "SL"
                break
            if hit_tp:
                exit_px, exit_i, reason = tp_px, j, "TP"
                break
        if exit_px is None:
            exit_i = min(entry_i + max_bars, len(d)) - 1
            exit_px = c[exit_i]
        gross = side * (exit_px / entry - 1)
        net = gross - 2 * cost
        cap *= 1 + net * risk_per_trade
        trades.append({"entry_time": d.index[entry_i], "exit_time": d.index[exit_i],
                       "side": "LONG" if side == 1 else "SHORT", "entry": entry, "exit": exit_px,
                       "reason": reason, "ret_pct": net * 100})
        equity[exit_i] = cap
        i = exit_i + 1
    eq = pd.Series(equity, index=d.index).ffill().iloc[199:]

    tr = pd.DataFrame(trades)
    daily_eq = eq.resample("1D").last().dropna()
    daily = daily_eq.pct_change().dropna()
    n_days = max(len(daily), 1)
    total = float(eq.iloc[-1] - 1)
    dd = float((eq / eq.cummax() - 1).min())

    stats = {
        "tregti": len(tr),
        "win_rate_%": float((tr["ret_pct"] > 0).mean() * 100) if len(tr) else 0.0,
        "kthimi_mesatar_tregti_%": float(tr["ret_pct"].mean()) if len(tr) else 0.0,
        "kthimi_total_%": total * 100,
        "dite": n_days,
        "kthimi_mesatar_ditor_%": ((1 + total) ** (1 / n_days) - 1) * 100,
        "dite_me_>=1%_%": float((daily >= 0.01).mean() * 100) if len(daily) else 0.0,
        "dite_negative_%": float((daily < 0).mean() * 100) if len(daily) else 0.0,
        "max_drawdown_%": dd * 100,
        "sharpe_vjetor": float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0,
    }
    return BacktestResult(tr, eq, daily, stats)
