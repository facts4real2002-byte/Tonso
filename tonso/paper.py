"""Tregtim provë (paper trading): i njëjti rregull si backtest-i, por live dhe pa para reale.

- Hyn vetëm kur kalojnë 5 verifikimet (ose score-i, nëse checks=False).
- +1% neto në ditë -> ndalon deri nesër; humbja e ditës kufizohet në -1%.
- Gjendja ruhet në JSON (mund ta ndalosh e rinisësh), tregtitë në CSV.
- Njoftime opsionale në Telegram: TELEGRAM_BOT_TOKEN dhe TELEGRAM_CHAT_ID.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .checks import evaluate
from .signals import score_frame


@dataclass
class Config:
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    start_capital: float = 1000.0
    tp: float = 0.01
    sl: float = 0.01
    horizon: int = 24
    threshold: float = 60
    fee: float = 0.0015            # tarifa + slippage për anë
    risk: float = 1.0              # pjesa maksimale e kapitalit për tregti
    daily_target: float = 0.01
    daily_stop: float = 0.01
    max_trades: int = 5
    use_checks: bool = True
    allow_short: bool = True


@dataclass
class State:
    capital: float
    last_bar: str | None = None
    day: str | None = None
    day_start_cap: float = 0.0
    day_trades: int = 0
    day_locked: bool = False
    position: dict | None = None
    history: list = field(default_factory=list)  # [(dita, kthimi_%)]


def notify(text: str) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", body, timeout=10)
    except Exception as err:  # njoftimi nuk duhet ta ndalojë botin
        print(f"[telegram] dështoi: {err}")


class PaperTrader:
    def __init__(self, cfg: Config, state_dir: str | Path = "paper_state", notify_fn=notify):
        self.cfg = cfg
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / f"{cfg.symbol}_{cfg.interval}.json"
        self.trades_path = self.dir / f"{cfg.symbol}_{cfg.interval}_trades.csv"
        self.notify = notify_fn
        if self.state_path.exists():
            self.state = State(**json.loads(self.state_path.read_text()))
        else:
            self.state = State(capital=cfg.start_capital, day_start_cap=cfg.start_capital)

    # ---------- ndihmëse ----------
    def _save(self) -> None:
        self.state_path.write_text(json.dumps(asdict(self.state), indent=2, default=str))

    def _log_trade(self, row: dict) -> None:
        new = not self.trades_path.exists()
        with self.trades_path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)

    def signals(self, df: pd.DataFrame) -> pd.Series:
        c = self.cfg
        if c.use_checks:
            sig = evaluate(df, threshold=c.threshold, tp=c.tp, sl=c.sl, horizon=c.horizon, fee=c.fee)["entry"]
        else:
            sc = score_frame(df)["score"]
            sig = pd.Series(np.where(sc >= c.threshold, 1, np.where(sc <= -c.threshold, -1, 0)), index=df.index)
        return sig if c.allow_short else sig.clip(lower=0)

    def _close(self, t: pd.Timestamp, price: float, reason: str, events: list) -> None:
        st, pos = self.state, self.state.position
        net = pos["side"] * (price / pos["entry"] - 1) - 2 * self.cfg.fee
        pnl = st.capital * net * pos["size"]
        st.capital += pnl
        st.day_trades += 1
        st.position = None
        self._log_trade({"symbol": self.cfg.symbol, "side": "LONG" if pos["side"] == 1 else "SHORT",
                         "entry_time": pos["time"], "exit_time": str(t), "entry": pos["entry"],
                         "exit": round(price, 8), "size": round(pos["size"], 4), "reason": reason,
                         "ret_pct": round(net * 100, 3), "pnl": round(pnl, 2), "capital": round(st.capital, 2)})
        day_ret = st.capital / st.day_start_cap - 1
        events.append(f"MBYLL {reason} @ {price:.6g} | {net * 100:+.2f}% | P&L {pnl:+.2f} | "
                      f"dita {day_ret * 100:+.2f}% | kapitali {st.capital:.2f}")
        if day_ret >= self.cfg.daily_target:
            st.day_locked = True
            events.append(f"🎯 Objektivi ditor +{self.cfg.daily_target * 100:g}% u arrit – ndalim deri nesër.")
        elif day_ret <= -self.cfg.daily_stop * 0.99:
            st.day_locked = True
            events.append(f"🛑 Humbja maksimale ditore -{self.cfg.daily_stop * 100:g}% – ndalim deri nesër.")
        elif st.day_trades >= self.cfg.max_trades:
            st.day_locked = True
            events.append(f"Maksimumi {self.cfg.max_trades} tregti për sot u arrit.")

    # ---------- logjika kryesore ----------
    def step(self, df: pd.DataFrame, sig: pd.Series | None = None) -> list[str]:
        """Përpunon të gjithë qirinjtë e MBYLLUR që s'janë parë ende. df duhet të ketë vetëm qirinj të mbyllur."""
        cfg, st = self.cfg, self.state
        sig = self.signals(df) if sig is None else sig
        step = df.index[1] - df.index[0]
        new = df.index if st.last_bar is None else df.index[df.index > pd.Timestamp(st.last_bar)]
        if st.last_bar is None:
            new = new[-1:]  # në nisje mos "tregto" historinë – fillo nga qiriri i fundit
        events: list[str] = []
        for t in new:
            bar = df.loc[t]
            day = str(t.normalize().date())
            if day != st.day:
                if st.day is not None:
                    st.history.append((st.day, round((st.capital / st.day_start_cap - 1) * 100, 3)))
                st.day, st.day_start_cap, st.day_trades, st.day_locked = day, st.capital, 0, False
            last_of_day = (t + step).normalize() != t.normalize()

            if st.position:
                pos = st.position
                pos["bars"] += 1
                s = pos["side"]
                if (bar["low"] <= pos["sl"]) if s == 1 else (bar["high"] >= pos["sl"]):
                    self._close(t, pos["sl"], "SL", events)
                elif (bar["high"] >= pos["tp"]) if s == 1 else (bar["low"] <= pos["tp"]):
                    self._close(t, pos["tp"], "TP", events)
                elif pos["bars"] >= cfg.horizon or last_of_day:
                    self._close(t, float(bar["close"]), "fund-dite" if last_of_day else "kohe", events)

            side = int(sig.get(t, 0))
            if not st.position and not st.day_locked and side != 0 and not last_of_day:
                budget = st.capital - st.day_start_cap * (1 - cfg.daily_stop)
                size = min(cfg.risk, max(budget, 0) / st.capital / (cfg.sl + 2 * cfg.fee))
                if size > 0.01:
                    entry = float(bar["close"])
                    st.position = {"side": side, "entry": entry, "time": str(t), "bars": 0, "size": size,
                                   "tp": entry * (1 + side * cfg.tp), "sl": entry * (1 - side * cfg.sl)}
                    events.append(f"HAP {'LONG' if side == 1 else 'SHORT'} @ {entry:.6g} | madhësia {size * 100:.0f}% "
                                  f"| TP {st.position['tp']:.6g} | SL {st.position['sl']:.6g}")
            st.last_bar = str(t)
        self._save()
        for e in events:
            self.notify(f"[{cfg.symbol} {cfg.interval}] {e}")
        return events

    def summary(self) -> str:
        st = self.state
        hist = st.history + ([(st.day, (st.capital / st.day_start_cap - 1) * 100)] if st.day else [])
        rets = [r for _, r in hist]
        total = (st.capital / self.cfg.start_capital - 1) * 100
        lines = [f"Kapitali: {st.capital:.2f} (fillimi {self.cfg.start_capital:.2f}, {total:+.2f}%)",
                 f"Ditë: {len(rets)} | ≥+1%: {sum(r >= 0.99 for r in rets)} | ≤-1%: {sum(r <= -0.99 for r in rets)} "
                 f"| mesatarja ditore: {np.mean(rets) if rets else 0:+.3f}%"]
        if st.position:
            lines.append(f"Pozicion i hapur: {st.position}")
        return "\n".join(lines)
