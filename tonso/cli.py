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
from .checks import checklist
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

    action, items, _ = checklist(df, threshold=max(args.threshold, 60), tp=tp, sl=sl, horizon=horizon)
    passed = sum(ok for _, ok, _ in items)
    print(f"\n--- 5 verifikimet ({passed}/5) → {action} ---")
    for name, ok, det in items:
        print(f"  {'✅' if ok else '❌'} {name:<28} {det}")

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
                       fee=args.fee / 100, risk_per_trade=args.risk, allow_short=not args.long_only,
                       daily_target=args.daily_target / 100 if args.daily_target else None,
                       daily_stop=args.daily_stop / 100 if args.daily_stop else None,
                       max_trades_per_day=args.max_trades or None, use_checks=args.checks)
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


def cmd_paper(args) -> None:
    import time

    from .paper import Config, PaperTrader

    cfg = Config(symbol=args.symbol, interval=args.interval, start_capital=args.capital,
                 tp=args.tp / 100, sl=args.sl / 100, horizon=BARS_PER_DAY.get(args.interval, 24),
                 threshold=args.threshold, daily_target=args.daily_target / 100,
                 daily_stop=args.daily_stop / 100, max_trades=args.max_trades,
                 use_checks=not args.no_checks, allow_short=not args.long_only)

    if args.replay:  # simulim i shpejtë qiri pas qiriri
        df = data.synthetic(n=6000, freq=args.interval) if args.replay == "synthetic" else data.load_csv(args.replay)
        cfg.symbol = "REPLAY"
        trader = PaperTrader(cfg, args.state_dir, notify_fn=lambda _: None)
        sig = trader.signals(df)  # pa lookahead (testuar), prandaj mund ta llogarisim një herë
        start = 400
        trader.step(df.iloc[:start], sig)
        for k in range(start + 1, len(df) + 1):
            for e in trader.step(df.iloc[:k], sig):
                print(f"{df.index[k - 1]}  {e}")
        print("\n" + trader.summary())
        return

    trader = PaperTrader(cfg, args.state_dir)
    print(f"Paper trading {cfg.symbol} {cfg.interval} – gjendja: {trader.state_path}")
    step = {"m": 60, "h": 3600, "d": 86400}[args.interval[-1]] * int(args.interval[:-1])
    while True:
        try:
            df = data.drop_open_candle(data.fetch_binance(cfg.symbol, cfg.interval, 1000))
            for e in trader.step(df):
                print(f"{df.index[-1]}  {e}")
            print(f"{pd_now()}  {trader.summary()}")
        except RuntimeError as err:
            print(f"Gabim rrjeti: {err} – provoj sërish")
        if args.once:
            return
        time.sleep(step - time.time() % step + 5)  # prit mbylljen e qiririt të radhës


def cmd_scan(args) -> None:
    import csv
    import time
    from pathlib import Path

    from . import arb, exchanges
    from .paper import notify

    names = [n.strip() for n in args.exchanges.split(",")] if args.exchanges else None
    while True:
        spot, err1 = exchanges.fetch_all(exchanges.SPOT, names)
        fund, err2 = exchanges.fetch_all(exchanges.FUNDING, names)
        errors = {**err1, **{f"{k}-futures": v for k, v in err2.items()}}
        if not spot and not fund:
            raise RuntimeError("Asnjë exchange nuk u përgjigj: " + "; ".join(f"{k}: {v}" for k, v in errors.items()))
        spot_arbs = arb.scan_spot(spot, min_volume=args.min_volume)
        carries = arb.scan_carry(fund, spot, min_volume=args.min_volume)
        spreads = arb.scan_funding_spread(fund, min_volume=args.min_volume)
        print(f"\n##### {pd_now()} UTC | spot: {', '.join(spot)} | futures: {', '.join(fund)}")
        print(arb.format_report(spot_arbs, carries, spreads, errors, args.top))

        hits = [a for a in spot_arbs if a.net * 100 >= args.alert_net and not a.suspicious]
        hits_c = [c for c in carries if c.annual * 100 >= args.alert_apr]
        for a in hits:
            notify(f"💱 ARB {a.symbol}: blej {a.buy_on} {a.buy_ask:.6g} → shit {a.sell_on} {a.sell_bid:.6g} | neto {a.net * 100:+.3f}%")
        for c in hits_c[:3]:
            notify(f"💰 FUNDING {c.symbol} @ {c.exchange}: {c.annual * 100:.0f}%/vit ({c.rate * 100:+.4f}%/{c.interval_hours:g}h)")
        if args.log:  # histori, që të shohësh sa shpesh shfaqen mundësitë
            path = Path(args.log)
            new = not path.exists()
            with path.open("a", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["time", "type", "symbol", "where", "net_or_daily_pct", "annual_pct"])
                for a in spot_arbs[:args.top]:
                    w.writerow([pd_now(), "spot", a.symbol, f"{a.buy_on}->{a.sell_on}", round(a.net * 100, 4), ""])
                for c in carries[:args.top]:
                    w.writerow([pd_now(), "carry", c.symbol, c.exchange, round(c.daily * 100, 4), round(c.annual * 100, 2)])
        if not args.loop:
            return
        time.sleep(args.loop)


def pd_now() -> str:
    return data.pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M")


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
    bt.add_argument("--daily-target", type=float, default=0, help="Ndalo për sot pas +X%% neto (p.sh. 1)")
    bt.add_argument("--daily-stop", type=float, default=0, help="Humbja maksimale e ditës në %% (p.sh. 1)")
    bt.add_argument("--max-trades", type=int, default=0, help="Maksimumi i tregtive në ditë")
    bt.add_argument("--trades", action="store_true", help="Shfaq 20 tregtitë e fundit")
    bt.add_argument("--checks", action="store_true", help="Hyr vetëm kur kalojnë 5 verifikimet")

    pp = sub.add_parser("paper", help="Tregtim provë live (pa para reale) me rregullat ditore")
    pp.add_argument("--symbol", default="BTCUSDT")
    pp.add_argument("--interval", default="1h", choices=list(BARS_PER_DAY))
    pp.add_argument("--capital", type=float, default=1000)
    pp.add_argument("--tp", type=float, default=1.0)
    pp.add_argument("--sl", type=float, default=1.0)
    pp.add_argument("--threshold", type=float, default=60)
    pp.add_argument("--daily-target", type=float, default=1.0)
    pp.add_argument("--daily-stop", type=float, default=1.0)
    pp.add_argument("--max-trades", type=int, default=5)
    pp.add_argument("--no-checks", action="store_true", help="Përdor vetëm score-in, pa 5 verifikimet")
    pp.add_argument("--long-only", action="store_true")
    pp.add_argument("--state-dir", default="paper_state")
    pp.add_argument("--once", action="store_true", help="Një hap dhe dil (për cron)")
    pp.add_argument("--replay", help="Riluaj një CSV qiri pas qiriri (ose 'synthetic') – pa internet")

    sc = sub.add_parser("scan", help="Skaner arbitrazhi dhe funding-u (Binance, Bybit, OKX, KuCoin, Gate)")
    sc.add_argument("--exchanges", help="p.sh. binance,bybit,okx (default: të gjitha)")
    sc.add_argument("--min-volume", type=float, default=1_000_000, help="Volumi min 24h në USDT (default 1M)")
    sc.add_argument("--top", type=int, default=10)
    sc.add_argument("--loop", type=int, default=0, help="Përsërit çdo N sekonda")
    sc.add_argument("--alert-net", type=float, default=0.15, help="Telegram kur arbitrazhi neto ≥ X%%")
    sc.add_argument("--alert-apr", type=float, default=30, help="Telegram kur funding ≥ X%% në vit")
    sc.add_argument("--log", help="Ruaj historinë në CSV")

    args = p.parse_args(argv)
    try:
        {"analyze": cmd_analyze, "backtest": cmd_backtest, "paper": cmd_paper, "scan": cmd_scan}[args.cmd](args)
    except RuntimeError as e:
        hint = "" if args.cmd == "scan" else "\nProvo --csv skedar.csv ose --synthetic"
        print(f"Gabim: {e}{hint}", file=sys.stderr)
        return 1
    return 0
