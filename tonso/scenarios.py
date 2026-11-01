"""Analizë probabilistike me Monte Carlo (bootstrap i kthimeve historike).

Përgjigjet pyetjeve si:
  - Sa është probabiliteti që çmimi të prekë +1% para se të prekë -X% brenda N qirinjve?
  - Si duken skenarët bullish / bazë / bearish (percentilet)?
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ScenarioReport:
    horizon: int
    p_up: float                  # P(çmimi në fund > çmimi aktual)
    p_hit_tp: float              # P(prek TP para SL)
    p_hit_sl: float              # P(prek SL para TP)
    p_neither: float
    expected_return: float       # kthimi mesatar në fund të horizontit
    percentiles: dict[str, float]  # p5, p25, p50, p75, p95 (kthime %)
    scenarios: dict[str, tuple[float, float]]  # emri -> (probabiliteti, kthimi mesatar %)


def monte_carlo(close: pd.Series, horizon: int = 24, n_paths: int = 5000, lookback: int = 500,
                tp: float = 0.01, sl: float = 0.01, direction: int = 1, block: int = 6,
                seed: int | None = 7) -> ScenarioReport:
    """Block-bootstrap i log-kthimeve të fundit (ruan pak autokorrelacion & volatilitet).

    direction=1 për long (TP sipër), -1 për short (TP poshtë).
    """
    rng = np.random.default_rng(seed)
    rets = np.log(close).diff().dropna().to_numpy()[-lookback:]
    if len(rets) < block * 4:
        raise ValueError("Shumë pak të dhëna për Monte Carlo")
    rets = rets - rets.mean()  # pa drift: mos supozo që trendi i kaluar vazhdon

    n_blocks = int(np.ceil(horizon / block))
    starts = rng.integers(0, len(rets) - block, size=(n_paths, n_blocks))
    idx = (starts[..., None] + np.arange(block)).reshape(n_paths, -1)[:, :horizon]
    paths = np.exp(np.cumsum(rets[idx], axis=1)) - 1.0  # kthim kumulativ

    pnl = paths * direction
    hit_tp = pnl >= tp
    hit_sl = pnl <= -sl
    first_tp = np.where(hit_tp.any(1), hit_tp.argmax(1), horizon + 1)
    first_sl = np.where(hit_sl.any(1), hit_sl.argmax(1), horizon + 1)
    tp_first = (first_tp < first_sl)
    sl_first = (first_sl < first_tp)

    final = paths[:, -1]
    pct = {f"p{q}": float(np.percentile(final, q) * 100) for q in (5, 25, 50, 75, 95)}

    sd = final.std()
    buckets = {
        "Bullish fort": final > sd,
        "Bullish i lehtë": (final > 0.25 * sd) & (final <= sd),
        "Anësor": (final >= -0.25 * sd) & (final <= 0.25 * sd),
        "Bearish i lehtë": (final < -0.25 * sd) & (final >= -sd),
        "Bearish fort": final < -sd,
    }
    scen = {k: (float(m.mean()), float(final[m].mean() * 100) if m.any() else 0.0) for k, m in buckets.items()}

    return ScenarioReport(
        horizon=horizon,
        p_up=float((final > 0).mean()),
        p_hit_tp=float(tp_first.mean()),
        p_hit_sl=float(sl_first.mean()),
        p_neither=float(1 - tp_first.mean() - sl_first.mean()),
        expected_return=float(final.mean() * 100),
        percentiles=pct,
        scenarios=scen,
    )


def historical_signal_odds(scored: pd.DataFrame, threshold: float, horizon: int,
                           tp: float, sl: float, side: str) -> dict:
    """Probabiliteti EMPIRIK: herët e kaluara kur u dha i njëjti sinjal, sa herë u arrit TP para SL?"""
    close, high, low = scored["close"].to_numpy(), scored["high"].to_numpy(), scored["low"].to_numpy()
    mask = scored["score"].to_numpy() >= threshold if side == "BUY" else scored["score"].to_numpy() <= -threshold
    wins = losses = timeouts = 0
    for i in np.flatnonzero(mask[:-horizon] if horizon else mask):
        entry = close[i]
        for j in range(i + 1, i + 1 + horizon):
            if side == "BUY":
                hit_sl, hit_tp = low[j] <= entry * (1 - sl), high[j] >= entry * (1 + tp)
            else:
                hit_sl, hit_tp = high[j] >= entry * (1 + sl), low[j] <= entry * (1 - tp)
            if hit_sl:          # konservativ: nëse të dyja në të njëjtin qiri, numëro humbje
                losses += 1
                break
            if hit_tp:
                wins += 1
                break
        else:
            timeouts += 1
    n = wins + losses + timeouts
    return {"samples": n, "p_tp": wins / n if n else float("nan"),
            "p_sl": losses / n if n else float("nan"), "p_timeout": timeouts / n if n else float("nan")}
