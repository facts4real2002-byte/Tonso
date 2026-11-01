"""Skaneri i arbitrazhit dhe i funding-ut.

1. Arbitrazh spot ndërmjet exchange-ve (model "kapital i ndarë paraprakisht"):
   blej te A me çmimin ASK, shit te B me çmimin BID, në të njëjtën kohë. Pa transferim.
   neto = BID_B / ASK_A - 1 - tarifa_A - tarifa_B

2. Funding delta-neutral (cash & carry): blej spot + short perpetual në të njëjtin exchange.
   Fiton funding-un kur është pozitiv; kosto = 2× tarifa spot + 2× tarifa perp.

3. Diferenca e funding-ut ndërmjet exchange-ve: long perp ku funding-u është i ulët,
   short perp ku është i lartë.
"""

from __future__ import annotations

from dataclasses import dataclass

from .exchanges import PERP_TAKER_FEE, TAKER_FEE, Funding, Quote

SUSPICIOUS_GAP = 0.05
SUSPICIOUS_FUNDING_DAILY = 0.005  # >0.5%/ditë diferencë = zakonisht kontrata të ndryshme ose treg i paqëndrueshëm


def _liquid(f: Funding, min_volume: float) -> bool:
    """Volumi i panjohur (None) lejohet, por volumi i njohur duhet të kalojë pragun."""
    return f.volume is None or f.volume >= min_volume  # >5% zakonisht = token tjetër me të njëjtin emër, ose depozita/tërheqje të bllokuara


@dataclass
class SpotArb:
    symbol: str
    buy_on: str
    buy_ask: float
    sell_on: str
    sell_bid: float
    gross: float
    net: float
    min_volume: float
    suspicious: bool


@dataclass
class CarryTrade:
    symbol: str
    exchange: str
    rate: float
    interval_hours: float
    daily: float
    annual: float
    cost: float
    breakeven_days: float


@dataclass
class FundingSpread:
    symbol: str
    long_on: str
    short_on: str
    daily_diff: float
    annual_diff: float
    cost: float
    breakeven_days: float
    suspicious: bool = False


def scan_spot(quotes: dict[str, dict[str, Quote]], min_volume: float = 1_000_000,
              fees: dict[str, float] | None = None) -> list[SpotArb]:
    """quotes: {exchange: {symbol: Quote}}. Kthen mundësitë të renditura sipas fitimit neto."""
    fees = {**TAKER_FEE, **(fees or {})}
    symbols: dict[str, dict[str, Quote]] = {}
    for ex, qs in quotes.items():
        for sym, q in qs.items():
            if q.ask >= q.bid > 0:  # injoro libra të prishur
                symbols.setdefault(sym, {})[ex] = q
    out = []
    for sym, by_ex in symbols.items():
        liquid = {ex: q for ex, q in by_ex.items() if q.quote_volume >= min_volume}
        if len(liquid) < 2:
            continue
        buy_ex = min(liquid, key=lambda e: liquid[e].ask)
        sell_ex = max(liquid, key=lambda e: liquid[e].bid)
        if buy_ex == sell_ex:
            continue
        ask, bid = liquid[buy_ex].ask, liquid[sell_ex].bid
        gross = bid / ask - 1
        net = gross - fees.get(buy_ex, 0.002) - fees.get(sell_ex, 0.002)
        out.append(SpotArb(sym, buy_ex, ask, sell_ex, bid, gross, net,
                           min(liquid[buy_ex].quote_volume, liquid[sell_ex].quote_volume),
                           gross > SUSPICIOUS_GAP))
    return sorted(out, key=lambda a: a.net, reverse=True)


def scan_carry(funding: dict[str, dict[str, Funding]], spot: dict[str, dict[str, Quote]] | None = None,
               min_volume: float = 1_000_000) -> list[CarryTrade]:
    """Funding pozitiv = short-et paguhen. Kërkon që spot-i të ekzistojë në të njëjtin exchange."""
    out = []
    for ex, rates in funding.items():
        spot_ex = (spot or {}).get(ex)
        for sym, f in rates.items():
            if f.rate <= 0 or not _liquid(f, min_volume):
                continue
            if spot is not None:
                q = (spot_ex or {}).get(sym)
                if q is None or q.quote_volume < min_volume:
                    continue
            cost = 2 * TAKER_FEE.get(ex, 0.002) + 2 * PERP_TAKER_FEE.get(ex, 0.0006)
            out.append(CarryTrade(sym, ex, f.rate, f.interval_hours, f.daily, f.annual, cost,
                                  cost / f.daily if f.daily > 0 else float("inf")))
    return sorted(out, key=lambda c: c.annual, reverse=True)


def scan_funding_spread(funding: dict[str, dict[str, Funding]], min_volume: float = 1_000_000) -> list[FundingSpread]:
    symbols: dict[str, dict[str, Funding]] = {}
    for ex, rates in funding.items():
        for sym, f in rates.items():
            if not _liquid(f, min_volume):
                continue
            symbols.setdefault(sym, {})[ex] = f
    out = []
    for sym, by_ex in symbols.items():
        if len(by_ex) < 2:
            continue
        lo = min(by_ex, key=lambda e: by_ex[e].daily)
        hi = max(by_ex, key=lambda e: by_ex[e].daily)
        diff = by_ex[hi].daily - by_ex[lo].daily
        if diff <= 0:
            continue
        cost = 2 * PERP_TAKER_FEE.get(lo, 0.0006) + 2 * PERP_TAKER_FEE.get(hi, 0.0006)
        out.append(FundingSpread(sym, lo, hi, diff, diff * 365, cost, cost / diff, diff > SUSPICIOUS_FUNDING_DAILY))
    return sorted(out, key=lambda s: s.daily_diff, reverse=True)


def format_report(spot_arbs, carries, spreads, errors: dict | None = None, top: int = 10) -> str:
    L = []
    if errors:
        L.append("⚠ Exchange pa përgjigje: " + ", ".join(f"{k} ({v[:60]})" for k, v in errors.items()))
    good = [a for a in spot_arbs if a.net > 0 and not a.suspicious]
    sus = [a for a in spot_arbs if a.suspicious]
    L.append(f"\n=== 1. ARBITRAZH SPOT (neto pas tarifave, pa transferim) – {len(good)} pozitive ===")
    for a in (good or spot_arbs)[:top]:
        L.append(f"  {a.symbol:<12} blej {a.buy_on:<8} {a.buy_ask:<12.6g} shit {a.sell_on:<8} {a.sell_bid:<12.6g} "
                 f"bruto {a.gross * 100:+.3f}%  NETO {a.net * 100:+.3f}%  vol.min {a.min_volume / 1e6:,.1f}M")
    if not good:
        L.append("  (asnjë mundësi pozitive tani – më sipër janë më të afërtat)")
    if sus:
        L.append(f"  ⚠ {len(sus)} diferenca >5% u përjashtuan (zakonisht token tjetër / tërheqje të bllokuara): "
                 + ", ".join(f"{a.symbol} {a.buy_on}->{a.sell_on} {a.gross * 100:.0f}%" for a in sus[:5]))

    L.append("\n=== 2. FUNDING DELTA-NEUTRAL (blej spot + short perp, i njëjti exchange) ===")
    for c in carries[:top]:
        L.append(f"  {c.symbol:<12} {c.exchange:<8} funding {c.rate * 100:+.4f}%/{c.interval_hours:g}h  "
                 f"= {c.daily * 100:.3f}%/ditë  {c.annual * 100:6.1f}%/vit  kosto {c.cost * 100:.2f}%  "
                 f"barazim pas {c.breakeven_days:.1f} ditësh")

    L.append("\n=== 3. DIFERENCA E FUNDING-UT (long perp te i ulëti, short te i larti) ===")
    ok_spreads = [s for s in spreads if not s.suspicious]
    for s in ok_spreads[:top]:
        L.append(f"  {s.symbol:<12} long {s.long_on:<8} short {s.short_on:<8} "
                 f"{s.daily_diff * 100:.3f}%/ditë  {s.annual_diff * 100:6.1f}%/vit  barazim pas {s.breakeven_days:.1f} ditësh")
    sus = [s for s in spreads if s.suspicious]
    if sus:
        L.append(f"  ⚠ {len(sus)} diferenca >0.5%/ditë u përjashtuan (kontrata të ndryshme / treg i paqëndrueshëm): "
                 + ", ".join(f"{s.symbol} {s.daily_diff * 100:.2f}%" for s in sus[:6]))
    L.append("\n⚠ Funding-u ndryshon çdo periudhë: norma e sotme nuk garantohet nesër. "
             "Kontrollo gjithmonë thellësinë e librit dhe statusin e depozitave/tërheqjeve.")
    return "\n".join(L)
