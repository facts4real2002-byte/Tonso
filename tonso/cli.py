"""Ndërfaqja nga rreshti i komandës.

Shembuj:
  python -m tonso analyze --symbol BTCUSDT --interval 1h
  python -m tonso backtest --symbol ETHUSDT --interval 1h --tp 1 --sl 1
  python -m tonso analyze --synthetic        # pa internet, vetëm për testim
"""

from __future__ import annotations

import argparse
import sys

from . import data
from .backtest import run as run_backtest
from .scenarios import historical_signal_odds, monte_carlo
from .signals import latest_signal, score_frame

BARS_PER_DAY = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "2h": 12, "4h": 6, "1d": 1}


def _load(args) -> "data.pd.DataFrame":
    if args.csv:
        return data.load_csv(args.csv)
    if args.synthetic:
        return data.synthetic(n=args.limit, freq=args.interval)
    return data.fetch_binance(args.symbol, args.interval, args.limit)


def _pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def cmd_analyze(args) -> None:
    df = _load(args)
    sig = latest_signal(df, threshold=args.threshold)
    horizon = args.horizon or BARS_PER_DAY.get(args.interval, 24)
    tp, sl = args.tp / 100, args.sl / 100

    print(f"\n=== {args.symbol if not args.synthetic else 'SINTETIK'} [{args.interval}] — {df.index[-1]} ===")
    print(f"Çmimi: {sig.price:.6g}")
    print(f"SINJALI: {sig.action}   (score {sig.score:+.0f} / ±100, pragu ±{args.threshold:g})")
    if sig.stop_loss:
        print(f"  Stop-loss (ATR): {sig.stop_loss:.6g}   Take-profit (ATR): {sig.take_profit:.6g}")
    print("Arsyet:")
    for r in sig.reasons:
        print(f"  • {r}")

    direction = -1 if sig.action == "SELL" else 1
    side_name = "SHORT" if direction == -1 else "LONG"
    mc = monte_carlo(df["close"], horizon=horizon, tp=tp, sl=sl, direction=direction)
    print(f"\n--- Monte Carlo ({horizon} qirinj, 5000 shtigje, {side_name}) ---")
    print(f"P(+{args.tp:g}% para -{args.sl:g}%): {_pct(mc.p_hit_tp)}")
    print(f"P(-{args.sl:g}% para +{args.tp:g}%): {_pct(mc.p_hit_sl)}")
    print(f"P(asnjëra brenda horizontit): {_pct(mc.p_neither)}")
    print(f"P(çmimi më lart në fund): {_pct(mc.p_up)}")
    print("Shpërndarja e kthimit në fund: " + "  ".join(f"{k}={v:+.2f}%" for k, v in mc.percentiles.items()))
    print("\nSkenarët:")
    for name, (p, r) in mc.scenarios.items():
        print(f"  {name:<16} prob {_pct(p)}   kthim mesatar {r:+.2f}%")

    if sig.action != "HOLD":
        odds = historical_signal_odds(score_frame(df), args.threshold, horizon, tp, sl, sig.action)
        print(f"\n--- Historiku i këtij sinjali ({odds['samples']} raste) ---")
        if odds["samples"]:
            print(f"Arriti TP: {_pct(odds['p_tp'])}  |  Goditi SL: {_pct(odds['p_sl'])}  |  Kohë mbaroi: {_pct(odds['p_timeout'])}")
        if odds["samples"] < 30:
            print("  ⚠ Më pak se 30 raste – probabiliteti nuk është statistikisht i besueshëm.")

    print("\n⚠ Kjo NUK është këshillë financiare. Probabilitetet bazohen në të dhëna të kaluara.\n")


def cmd_backtest(args) -> None:
    df = _load(args)
    res = run_backtest(df, threshold=args.threshold, tp=args.tp / 100, sl=args.sl / 100,
                       max_bars=args.horizon or BARS_PER_DAY.get(args.interval, 24),
                       fee=args.fee / 100, risk_per_trade=args.risk, allow_short=not args.long_only)
    print(f"\n=== Backtest {args.symbol if not args.synthetic else 'SINTETIK'} [{args.interval}] "
          f"{df.index[0].date()} → {df.index[-1].date()} ===")
    for k, v in res.stats.items():
        print(f"  {k:<26} {v:,.2f}" if isinstance(v, float) else f"  {k:<26} {v}")
    target = 1.0
    avg = res.stats["kthimi_mesatar_ditor_%"]
    print(f"\nObjektivi: {target:.1f}%/ditë  →  arritur: {avg:+.3f}%/ditë "
          f"({'✅ ARRITUR' if avg >= target else '❌ NUK u arrit'})")
    if args.trades and len(res.trades):
        print(res.trades.tail(20).to_string(index=False))
    print()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tonso", description="Bot sinjalesh BUY/SELL me analizë probabilistike")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("analyze", "backtest"):
        sp = sub.add_parser(name)
        sp.add_argument("--symbol", default="BTCUSDT")
        sp.add_argument("--interval", default="1h", choices=list(BARS_PER_DAY))
        sp.add_argument("--limit", type=int, default=1000)
        sp.add_argument("--csv", help="Skedar CSV me OHLCV në vend të Binance")
        sp.add_argument("--synthetic", action="store_true", help="Të dhëna sintetike (pa internet)")
        sp.add_argument("--threshold", type=float, default=40, help="Pragu i score-it për sinjal (0-100)")
        sp.add_argument("--tp", type=float, default=1.0, help="Take-profit në %% (default 1)")
        sp.add_argument("--sl", type=float, default=1.0, help="Stop-loss në %% (default 1)")
        sp.add_argument("--horizon", type=int, default=0, help="Qirinj për horizontin (default = 1 ditë)")
    bt = sub.choices["backtest"]
    bt.add_argument("--fee", type=float, default=0.1, help="Tarifa për anë në %% (default 0.1)")
    bt.add_argument("--risk", type=float, default=1.0, help="Pjesa e kapitalit për tregti (0-1)")
    bt.add_argument("--long-only", action="store_true")
    bt.add_argument("--trades", action="store_true", help="Shfaq 20 tregtitë e fundit")

    args = p.parse_args(argv)
    try:
        {"analyze": cmd_analyze, "backtest": cmd_backtest}[args.cmd](args)
    except RuntimeError as e:
        print(f"Gabim: {e}\nProvo --csv skedar.csv ose --synthetic", file=sys.stderr)
        return 1
    return 0
