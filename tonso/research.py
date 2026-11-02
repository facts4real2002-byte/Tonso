"""Test me të dhëna REALE historike: a funksionon strategjia me 100$, stop ditor -1% dhe compounding?

1. Funding carry (delta-neutral) – historia e funding-ut nga Gate.io për kontratat më likuide.
   Çdo ditë zgjedh kontratën(at) me funding-un më të lartë mesatar të 3 ditëve të KALUARA
   (pa parë të ardhmen), paguan tarifat kur ndërron, fiton/paguan funding-un real të ditës.
2. Boti me sinjale – qirinj realë 1h nga Binance, me/pa 5 verifikimet, rregulli +1%/-1% në ditë.

Kufizime (për ndershmëri):
  - Universi zgjidhet sipas volumit të SOTËM (survivorship bias – kontratat e delistuara mungojnë).
  - Carry supozon mbrojtje perfekte spot/perp (pa rrezik "basis" dhe pa slippage përtej tarifave).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import run as run_backtest
from .exchanges import get_json

GATE = "https://api.gateio.ws/api/v4"


# ---------------- të dhënat ----------------

def gate_universe(n: int = 60, min_volume: float = 5_000_000) -> list[str]:
    rows = get_json(f"{GATE}/futures/usdt/tickers")
    rows = [r for r in rows if float(r.get("volume_24h_quote") or 0) >= min_volume]
    rows.sort(key=lambda r: float(r.get("volume_24h_quote") or 0), reverse=True)
    return [r["contract"] for r in rows[:n]]


def gate_funding_history(contract: str, days: int = 180) -> pd.Series:
    """Pagesat e funding-ut (norma për periudhë) me kohën e pagesës, për `days` ditët e fundit."""
    since = int(time.time()) - days * 86400
    out, to = [], None
    for _ in range(20):
        url = f"{GATE}/futures/usdt/funding_rate?contract={contract}&limit=1000"
        if to:
            url += f"&from={since}&to={to}"
        rows = get_json(url)
        if not rows:
            break
        out.extend(rows)
        oldest = min(int(r["t"]) for r in rows)
        if oldest <= since or len(rows) < 1000:
            break
        to = oldest - 1
    if not out:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(int(r["t"]), unit="s", tz="UTC"): float(r["r"]) for r in out}).sort_index()
    return s[s.index >= pd.Timestamp(since, unit="s", tz="UTC")]


def binance_history(symbol: str, interval: str = "1h", days: int = 365) -> pd.DataFrame:
    step = {"1h": 3600_000, "4h": 4 * 3600_000, "15m": 900_000}[interval]
    start = int((time.time() - days * 86400) * 1000)
    frames = []
    while True:
        url = (f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}"
               f"&interval={interval}&limit=1000&startTime={start}")
        rows = get_json(url)
        if not rows:
            break
        frames.extend(rows)
        start = rows[-1][0] + step
        if len(rows) < 1000:
            break
    df = pd.DataFrame(frames).iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time").astype(float)
    df = df[~df.index.duplicated()]
    return df.iloc[:-1]  # qiriri i fundit mund të jetë ende i hapur


# ---------------- funding carry backtest ----------------

@dataclass
class CarryResult:
    equity: pd.Series
    daily_ret: pd.Series
    holdings: pd.Series
    switches: int


def carry_backtest(daily_funding: pd.DataFrame, capital: float = 100.0, efficiency: float = 0.5,
                   leg_cost: float = 0.0025, lookback: int = 3, entry_min: float = 0.001,
                   exit_min: float = 0.0002, switch_margin: float = 0.0015, top_k: int = 1,
                   daily_stop: float = 0.01) -> CarryResult:
    """daily_funding: rreshtat = ditët, kolonat = kontratat, vlerat = shuma e funding-ut të ditës (për 1$ short).

    efficiency: pjesa e kapitalit që bëhet nocional i short-it (0.5 = 50$ spot + 50$ marzh).
    leg_cost: kosto për hyrje OSE dalje mbi nocionalin (spot + perp; Gate: 0.2% + 0.05%).
    Vendimi për ditën d përdor vetëm ditët < d.
    """
    signal = daily_funding.rolling(lookback, min_periods=lookback).mean().shift(1)
    cap = capital
    held: list[str] = []
    eq, rets, hold_log = [], [], []
    switches = 0
    for day in daily_funding.index:
        start = cap
        scores = signal.loc[day].dropna()
        # dil nga ato që nuk paguajnë më
        keep = [h for h in held if scores.get(h, -1) >= exit_min]
        exits = [h for h in held if h not in keep]
        # kandidatët e rinj
        candidates = scores[(scores >= entry_min) & ~scores.index.isin(keep)].sort_values(ascending=False)
        new = list(candidates.index[: top_k - len(keep)])
        # ndërro nëse një kandidat është shumë më i mirë se më i dobëti që mbajmë
        if keep and len(candidates) and len(keep) == top_k:
            worst = min(keep, key=lambda h: scores.get(h, 0))
            best = candidates.index[0]
            if candidates.iloc[0] > scores.get(worst, 0) + switch_margin:
                keep.remove(worst)
                exits.append(worst)
                new = [best]
        per_slot = cap * efficiency / top_k
        cap -= per_slot * leg_cost * (len(exits) + len(new))
        switches += len(exits) + len(new)
        held = keep + new
        # funding-u real i ditës
        pnl = sum(per_slot * daily_funding.at[day, h] for h in held if pd.notna(daily_funding.at[day, h]))
        cap += pnl
        if held and (cap / start - 1) <= -daily_stop:  # stop ditor: mbyll gjithçka
            cap -= per_slot * leg_cost * len(held)
            switches += len(held)
            held = []
        eq.append(cap)
        rets.append(cap / start - 1)
        hold_log.append(",".join(held))
    idx = daily_funding.index
    return CarryResult(pd.Series(eq, idx), pd.Series(rets, idx), pd.Series(hold_log, idx), switches)


def summarize(name: str, equity: pd.Series, daily: pd.Series, capital: float = 100.0) -> str:
    days = len(daily)
    final = float(equity.iloc[-1]) if days else capital
    avg = ((final / capital) ** (1 / days) - 1) * 100 if days else 0.0
    dd = float((equity / equity.cummax().clip(lower=capital) - 1).min() * 100) if days else 0.0
    per_year = capital * (final / capital) ** (365 / days) if days else capital
    return (f"{name:<44} {days:4d} ditë  100$ → {final:8.2f}$  mesatarja {avg:+.3f}%/ditë  "
            f"ditë+ {(daily > 0).mean() * 100:4.0f}%  dita më e keqe {daily.min() * 100:+.2f}%  "
            f"DD {dd:+.1f}%  ritmi vjetor → {per_year:,.0f}$")


# ---------------- ekzekutimi ----------------

def main(days: int = 180, n_contracts: int = 60, signal_days: int = 365) -> None:
    print(f"#### TEST ME TË DHËNA REALE – {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC ####\n")

    print("=== A. FUNDING CARRY (Gate.io, delta-neutral, 100$, stop ditor -1%, compounding) ===")
    contracts = gate_universe(n_contracts)
    series = {}
    for c in contracts:
        try:
            s = gate_funding_history(c, days)
            if len(s):
                series[c] = s
        except Exception as err:
            print(f"  {c}: {err}")
    daily = pd.DataFrame({c: s.resample("1D").sum(min_count=1) for c, s in series.items()}).sort_index()
    daily = daily.iloc[:-1]  # dita e sotme e paplotë
    print(f"  {len(series)} kontrata, {len(daily)} ditë ({daily.index[0]:%Y-%m-%d} → {daily.index[-1]:%Y-%m-%d})")
    print(f"  Funding mesatar i të gjitha kontratave: {daily.stack().mean() * 100:+.3f}%/ditë")
    for label, kw in [
        ("Top 1, kërcen te më i miri", {"top_k": 1}),
        ("Top 3 (diversifikuar)", {"top_k": 3}),
        ("Top 3, prag më i lartë hyrjeje 0.2%/ditë", {"top_k": 3, "entry_min": 0.002}),
        ("Top 5, i qetë (switch_margin 0.3%)", {"top_k": 5, "switch_margin": 0.003}),
    ]:
        r = carry_backtest(daily, **kw)
        print("  " + summarize(label, r.equity, r.daily_ret) + f"  ndërrime {r.switches}")
    if "BTC_USDT" in daily:
        btc = daily["BTC_USDT"].dropna()
        eq = 100 * (1 + 0.5 * btc).cumprod() * (1 - 0.5 * 0.0025 * 2)
        print("  " + summarize("Vetëm BTC, mbaj gjithë kohën", eq, eq.pct_change().fillna(0.5 * btc.iloc[0])))

    print(f"\n=== B. BOTI ME SINJALE (Binance 1h, {signal_days} ditë, 100$, +1%/-1% në ditë, compounding) ===")
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        try:
            df = binance_history(sym, "1h", signal_days)
        except Exception as err:
            print(f"  {sym}: {err}")
            continue
        for label, kw in [
            ("pa verifikime, TP1/SL1", {"tp": 0.01, "sl": 0.01, "use_checks": False}),
            ("pa verifikime, TP2/SL1", {"tp": 0.02, "sl": 0.01, "use_checks": False}),
            ("5 verifikimet, TP1/SL1", {"tp": 0.01, "sl": 0.01, "use_checks": True}),
            ("5 verifikimet, TP2/SL1", {"tp": 0.02, "sl": 0.01, "use_checks": True}),
        ]:
            r = run_backtest(df, threshold=60, daily_target=0.01, daily_stop=0.01, max_trades_per_day=5, **kw)
            eq = r.equity.resample("1D").last().dropna() * 100
            print("  " + summarize(f"{sym} {label}", eq, eq.pct_change().dropna()) + f"  tregti {len(r.trades)}")
    print("\nKufizime: universi sipas volumit të sotëm (survivorship bias); carry pa rrezik basis/slippage.")


if __name__ == "__main__":
    main()
