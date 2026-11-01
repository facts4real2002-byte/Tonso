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
        risk_per_trade: float = 1.0, allow_short: bool = True,
        daily_target: float | None = None, daily_stop: float | None = None,
        max_trades_per_day: int | None = None, use_checks: bool = False,
        check_kwargs: dict | None = None) -> BacktestResult:
    """tp/sl janë në përqindje (0.01 = 1%). risk_per_trade = pjesa e kapitalit në çdo tregti.

    Rregulli ditor (opsional):
      daily_target – kur fitimi i ditës arrin p.sh. +1% neto, ndalo deri nesër.
      daily_stop   – humbja maksimale e ditës (p.sh. 1%). Madhësia e pozicionit zvogëlohet
                     automatikisht që asnjë tregti të mos e kalojë këtë kufi (përveç gap-eve).
      Kur ka rregull ditor, çdo tregti mbyllet më së voni në fund të ditës.
    """
    cost = fee + slippage  # për çdo anë
    if use_checks:  # hyrje vetëm kur kalojnë të 5 verifikimet
        from .checks import evaluate
        kw = {"threshold": threshold, "tp": tp, "sl": sl, "horizon": max_bars, "fee": cost}
        d = evaluate(df, **{**kw, **(check_kwargs or {})})
        entry_sig = d["entry"].to_numpy()
    else:
        d = score_frame(df)
        sc = d["score"].to_numpy()
        entry_sig = np.where(sc >= threshold, 1, np.where(sc <= -threshold, -1, 0))
    if not allow_short:
        entry_sig = np.maximum(entry_sig, 0)
    o, h, l, c = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
    day = d.index.normalize()
    day_rules = daily_target is not None or daily_stop is not None or max_trades_per_day is not None
    # indeksi i qiririt të fundit të çdo dite
    last_bar_of_day = pd.Series(np.arange(len(d)), index=d.index).groupby(day).transform("max").to_numpy()
    cur_day, day_start_cap, day_trades, day_locked = None, 1.0, 0, False
    day_outcome: dict = {}

    trades = []
    equity = np.full(len(d), np.nan)
    equity[199] = 1.0
    cap = 1.0
    i = 200
    while i < len(d) - 2:
        if day[i] != cur_day:  # ditë e re -> rifillo numëratorët
            cur_day, day_start_cap, day_trades, day_locked = day[i], cap, 0, False
        if day_locked:
            i = last_bar_of_day[i] + 1
            continue
        side = int(entry_sig[i])
        if side == 0:
            i += 1
            continue
        entry_i = i + 1
        if day_rules and (day[entry_i] != cur_day or entry_i >= last_bar_of_day[i]):
            i += 1  # mos hyr në qiririn e fundit të ditës
            continue
        entry = o[entry_i]
        size = risk_per_trade
        if daily_stop is not None:
            budget = cap - day_start_cap * (1 - daily_stop)  # sa mund të humbasim ende sot
            size = min(size, max(budget, 0) / cap / (sl + 2 * cost))
            if size <= 0.01:
                day_locked = True
                continue
        end_j = min(entry_i + max_bars, len(d))
        if day_rules:
            end_j = min(end_j, last_bar_of_day[i] + 1)
        tp_px = entry * (1 + side * tp)
        sl_px = entry * (1 - side * sl)
        exit_px, exit_i, reason = None, None, "timeout"
        for j in range(entry_i, end_j):
            hit_sl = l[j] <= sl_px if side == 1 else h[j] >= sl_px
            hit_tp = h[j] >= tp_px if side == 1 else l[j] <= tp_px
            if hit_sl:  # konservativ
                exit_px, exit_i, reason = sl_px, j, "SL"
                break
            if hit_tp:
                exit_px, exit_i, reason = tp_px, j, "TP"
                break
        if exit_px is None:
            exit_i = end_j - 1
            exit_px = c[exit_i]
            reason = "fund-dite" if day_rules and exit_i == last_bar_of_day[i] else "timeout"
        gross = side * (exit_px / entry - 1)
        net = gross - 2 * cost
        cap *= 1 + net * size
        trades.append({"entry_time": d.index[entry_i], "exit_time": d.index[exit_i],
                       "side": "LONG" if side == 1 else "SHORT", "entry": entry, "exit": exit_px,
                       "size": round(size, 3), "reason": reason, "ret_pct": net * 100,
                       "kapitali_ret_pct": net * size * 100})
        equity[exit_i] = cap
        i = exit_i + 1
        if day_rules:
            day_trades += 1
            day_ret = cap / day_start_cap - 1
            if daily_target is not None and day_ret >= daily_target:
                day_locked, day_outcome[cur_day] = True, "target"
            elif daily_stop is not None and day_ret <= -daily_stop * 0.99:
                day_locked, day_outcome[cur_day] = True, "stop"
            elif max_trades_per_day is not None and day_trades >= max_trades_per_day:
                day_locked = True
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
        "dite_target_arritur_%": sum(v == "target" for v in day_outcome.values()) / n_days * 100,
        "dite_stop_goditur_%": sum(v == "stop" for v in day_outcome.values()) / n_days * 100,
        "dita_me_e_keqe_%": float(daily.min() * 100) if len(daily) else 0.0,
        "sharpe_vjetor": float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0,
    }
    return BacktestResult(tr, eq, daily, stats)
