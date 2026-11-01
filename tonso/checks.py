"""5 verifikimet para hyrjes në tregti. Një tregti hapet VETËM nëse kalojnë të 5.

1. Trendi në kohë më të madhe (4× intervali): çmimi në anën e duhur të EMA50 të TF-së së madhe.
2. Sinjali hyrës: score ≥ prag (default 60).
3. Volumi: ≥ 1.2× mesatarja e 20 qirinjve.
4. Rrezik/volatilitet: SL jashtë "zhurmës" (SL ≥ 1×ATR%) dhe hyrja jo e vonuar
   (çmimi jo më larg se 1.5×ATR nga EMA20).
5. Probabiliteti: herët e kaluara të këtij setup-i (1–4 të kaluara njëkohësisht) (vetëm ato që ishin TASHMË të mbyllura
   në atë moment – pa parë të ardhmen) kanë ≥ 30 raste dhe P(TP para SL) mbi pikën e barazimit
   pas tarifave.

Gjithçka llogaritet pa parë të ardhmen, që backtest-i të jetë i ndershëm.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .signals import score_frame

CHECK_NAMES = {
    "c1_trend_htf": "Trendi në kohë më të madhe",
    "c2_signal": "Sinjali hyrës (score)",
    "c3_volume": "Volumi",
    "c4_risk": "Rrezik/volatilitet",
    "c5_probability": "Probabiliteti historik",
}


def _htf_ema(close: pd.Series, factor: int = 4, span: int = 50) -> pd.Series:
    """EMA në kohë më të madhe, e vendosur në qiririn ku mbyllet qiriri i madh (pa lookahead).

    Indeksi supozohet të jetë koha e HAPJES së qirinjve (si Binance).
    """
    if len(close.index) < 2:
        return pd.Series(np.nan, index=close.index)
    base = close.index[1] - close.index[0]
    rule = base * factor
    big = close.resample(rule, origin="epoch").agg(["last", "count"])
    big = big[big["count"] == factor]["last"]          # vetëm qirinj të mëdhenj të plotë
    ema = big.ewm(span=span, adjust=False).mean()
    ema.index = ema.index + rule - base                 # i njohur vetëm kur mbyllet qiriri i fundit
    return ema.reindex(close.index.union(ema.index)).ffill().reindex(close.index)


def _signal_outcomes(d: pd.DataFrame, side: int, horizon: int, tp: float, sl: float):
    """Për çdo qiri: rezultati nëse do hynim në mbyllje (+1 TP, -1 SL, 0 kohë mbaroi) dhe kur u mbyll."""
    c, h, l = d["close"].to_numpy(), d["high"].to_numpy(), d["low"].to_numpy()
    n = len(d)
    outcome = np.zeros(n, dtype=int)
    resolved_at = np.full(n, n + 10**9)
    for i in range(n - 1):
        tp_px, sl_px = c[i] * (1 + side * tp), c[i] * (1 - side * sl)
        end = min(i + 1 + horizon, n)
        for j in range(i + 1, end):
            if (l[j] <= sl_px) if side == 1 else (h[j] >= sl_px):
                outcome[i], resolved_at[i] = -1, j
                break
            if (h[j] >= tp_px) if side == 1 else (l[j] <= tp_px):
                outcome[i], resolved_at[i] = 1, j
                break
        else:
            if end - i - 1 == horizon:
                resolved_at[i] = end - 1
    return outcome, resolved_at


def _rolling_odds(signal_mask: np.ndarray, outcome: np.ndarray, resolved_at: np.ndarray):
    """P(TP) e njohur në çdo qiri, duke numëruar vetëm sinjalet e mbyllura para tij."""
    n = len(signal_mask)
    wins = np.zeros(n + 1)
    total = np.zeros(n + 1)
    decided = np.zeros(n + 1)
    for k in np.flatnonzero(signal_mask):
        r = resolved_at[k]
        if r < n:
            total[r + 1] += 1
            wins[r + 1] += outcome[k] == 1
            decided[r + 1] += outcome[k] != 0
    # në qiririn i dimë vetëm ato që u mbyllën deri në i (përfshirë)
    return np.cumsum(wins)[1:], np.cumsum(total)[1:], np.cumsum(decided)[1:]


def evaluate(df: pd.DataFrame, threshold: float = 60, tp: float = 0.01, sl: float = 0.01,
             horizon: int = 24, fee: float = 0.0015, min_samples: int = 30,
             vol_min: float = 1.2, htf_factor: int = 4) -> pd.DataFrame:
    """Kthen score_frame + kolonat c1..c5 për BUY dhe SELL dhe `entry` (+1 / -1 / 0)."""
    d = score_frame(df)
    htf = _htf_ema(d["close"], htf_factor)
    d["htf_ema"] = htf
    atr_pct = d["atr"] / d["close"]
    breakeven = (sl + 2 * fee) / (tp + sl)
    d["breakeven_p"] = breakeven

    for side, name in ((1, "buy"), (-1, "sell")):
        c1 = (side * (d["close"] - htf) > 0) & htf.notna()
        c2 = side * d["score"] >= threshold
        c3 = d["vol_ratio"] >= vol_min
        c4 = (sl >= atr_pct) & ((d["close"] - d["ema_fast"]).abs() <= 1.5 * d["atr"])
        outcome, resolved = _signal_outcomes(d, side, horizon, tp, sl)
        setup = (c1 & c2 & c3 & c4).to_numpy()  # probabiliteti i këtij setup-i të plotë, jo i çdo sinjali
        wins, total, decided = _rolling_odds(setup, outcome, resolved)
        with np.errstate(invalid="ignore", divide="ignore"):
            p = np.where(decided > 0, wins / decided, np.nan)
        d[f"{name}_p_tp"] = p
        d[f"{name}_samples"] = total
        c5 = pd.Series((total >= min_samples) & (np.nan_to_num(p) > breakeven), index=d.index)
        for key, val in zip(CHECK_NAMES, (c1, c2, c3, c4, c5)):
            d[f"{name}_{key}"] = val.astype(bool)
        d[f"{name}_passed"] = sum(d[f"{name}_{k}"].astype(int) for k in CHECK_NAMES)

    d["entry"] = np.where(d["buy_passed"] == 5, 1, np.where(d["sell_passed"] == 5, -1, 0))
    return d


def checklist(df: pd.DataFrame, **kw) -> tuple[str, list[tuple[str, bool, str]], pd.Series]:
    """Lista e kontrollit për qiririn e fundit: (veprimi, [(emri, kaloi, detaje)], rreshti)."""
    d = evaluate(df, **kw)
    row = d.iloc[-1]
    side = "buy" if row["score"] >= 0 else "sell"
    sign = 1 if side == "buy" else -1
    atr_pct = row["atr"] / row["close"] * 100
    p = row[f"{side}_p_tp"]
    details = {
        "c1_trend_htf": f"çmimi {row['close']:.6g} {'>' if row['close'] > row['htf_ema'] else '<'} "
                        f"EMA50 e TF {kw.get('htf_factor', 4)}× ({row['htf_ema']:.6g})",
        "c2_signal": f"score {row['score']:+.0f}, duhet {'≥ +' if sign == 1 else '≤ -'}{kw.get('threshold', 60):g}",
        "c3_volume": f"{row['vol_ratio']:.2f}× mesatarja, duhet ≥ {kw.get('vol_min', 1.2)}",
        "c4_risk": f"ATR {atr_pct:.2f}% vs SL {kw.get('sl', 0.01) * 100:g}%, "
                   f"distanca nga EMA20 {abs(row['close'] - row['ema_fast']) / row['atr']:.1f}×ATR (≤1.5)",
        "c5_probability": (f"P(TP para SL) {p * 100:.0f}% nga {int(row[f'{side}_samples'])} raste, "
                           f"barazimi {row['breakeven_p'] * 100:.0f}%, duhen ≥ {kw.get('min_samples', 30)} raste")
        if not np.isnan(p) else "ende pa histori sinjalesh",
    }
    items = [(CHECK_NAMES[k], bool(row[f"{side}_{k}"]), details[k]) for k in CHECK_NAMES]
    action = {1: "BUY", -1: "SELL", 0: "PRIT"}[int(row["entry"])]
    return action, items, row
