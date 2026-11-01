# Tonso – Bot sinjalesh BUY/SELL me analizë probabilistike

Bot në Python që:

1. **Jep sinjal BUY / SELL / HOLD** me një score nga −100 deri +100 (trend + momentum + mean-reversion + volum, me pesha që ndryshojnë sipas fuqisë së trendit/ADX).
2. **Llogarit probabilitete me Monte Carlo** (5000 shtigje, block-bootstrap nga kthimet reale): P(+1% para −1%), shpërndarja e çmimit pas 1 dite, dhe **5 skenarë** (bullish fort → bearish fort) me probabilitetin e secilit.
3. **Tregon probabilitetin empirik**: herët e kaluara kur u dha i njëjti sinjal, sa % arriti TP para SL.
4. **Bën backtest realist** (hyrje në qiririn e ardhshëm, tarifa + slippage, SL konservativ) dhe mat direkt objektivin **1% në ditë**.

## Instalimi

```bash
pip install -r requirements.txt     # vetëm pandas + numpy
```

## Përdorimi

```bash
# Analiza e sinjalit aktual (të dhëna live nga Binance, pa API key)
python -m tonso analyze --symbol BTCUSDT --interval 1h

# Backtest me TP 1% / SL 1% dhe tarifa 0.1% për anë
python -m tonso backtest --symbol ETHUSDT --interval 1h --tp 1 --sl 1 --trades

# Me skedarin tënd CSV (kolonat: time, open, high, low, close, volume)
python -m tonso analyze --csv te_dhenat.csv --interval 4h

# Pa internet (të dhëna sintetike – vetëm për të testuar kodin)
python -m tonso analyze --synthetic
```

### Rregulli ditor: +1% → ndalo, −1% → ndalo

```bash
python -m tonso backtest --symbol BTCUSDT --daily-target 1 --daily-stop 1 --max-trades 5
```

- Kur fitimi i ditës arrin **+1% neto**, boti ndalon deri nesër.
- Humbja e ditës **nuk e kalon kurrë −1%**: madhësia e pozicionit zvogëlohet automatikisht sipas buxhetit që mbetet.
- Çdo tregti mbyllet më së voni në fund të ditës.
- Backtest-i tregon `dite_target_arritur_%` dhe `dite_stop_goditur_%`. Që sistemi të jetë fitimprurës, ditët me +1% duhet të jenë **më shumë** se ditët me −1%.

### 5 verifikimet para hyrjes

`analyze` tregon listën e kontrollit me ✅/❌. Tregtia hapet **vetëm nëse kalojnë të 5**:

1. **Trendi në kohë më të madhe**: çmimi në anën e duhur të EMA50 në kohë 4× më të madhe.
2. **Sinjali hyrës**: score ≥ +60 (BUY) ose ≤ −60 (SELL).
3. **Volumi**: ≥ 1.2× mesatarja.
4. **Rrezik/volatilitet**: SL jashtë zhurmës (SL ≥ ATR%), dhe hyrja jo e vonuar (≤ 1.5×ATR nga EMA20).
5. **Probabiliteti**: i njëjti setup në të kaluarën ka ≥ 30 raste, dhe P(TP para SL) mbi pikën e barazimit pas tarifave. Me TP 1% / SL 1% dhe 0.15% kosto për anë, kjo pikë është **65%**.

```bash
python -m tonso backtest --symbol BTCUSDT --checks --daily-target 1 --daily-stop 1 --max-trades 5
```

Me të dhëna sintetike, filtri e uli humbjen maksimale nga **−60% në −1% deri −4%**, sepse refuzon tregtitë pa avantazh të provuar. Por nuk krijon fitim vetë: avantazhi duhet të ekzistojë në tregun real.

### Tregtim provë (paper trading), pa para reale

```bash
python -m tonso paper --symbol BTCUSDT --interval 1h            # live, kontrollon çdo orë
python -m tonso paper --symbol BTCUSDT --interval 1h --once     # një hap (për cron)
python -m tonso paper --replay synthetic                        # simulim i shpejtë pa internet
```

- I njëjti rregull: 5 verifikimet, +1% → ndalo, −1% → ndalo, maksimumi 5 tregti në ditë.
- Gjendja ruhet në `paper_state/` (JSON + CSV i tregtive), kështu që mund ta ndalosh e rinisësh.
- **Telegram**: vendos `TELEGRAM_BOT_TOKEN` dhe `TELEGRAM_CHAT_ID` për njoftime për çdo hyrje/dalje.

Parametra të dobishëm: `--threshold` (sa i fortë duhet sinjali, default 40), `--tp`, `--sl` (në %), `--horizon` (qirinj), `--fee`, `--risk` (pjesa e kapitalit për tregti), `--long-only`.

### Shembull rezultati

```
SINJALI: HOLD   (score -20 / ±100, pragu ±40)
--- Monte Carlo (24 qirinj, 5000 shtigje, LONG) ---
P(+1% para -1%):  60.0%
P(-1% para +1%):  39.9%
Skenarët:
  Bullish fort     prob  16.1%   kthim mesatar +8.99%
  Anësor           prob  20.5%   kthim mesatar +0.02%
  Bearish fort     prob  13.9%   kthim mesatar -9.65%
```

## ⚠ E vërteta për "1% në ditë"

| | Llogaritja | Rezultati |
|---|---|---|
| 1% në ditë, 1 vit (365 ditë) | 1.01³⁶⁵ | **×37.8** (+3 678%) |
| 1% në ditë tregtare (252) | 1.01²⁵² | **×12.3** |
| 1 000 € pas 2 vitesh | 1000 × 1.01⁷³⁰ | **≈ 1 430 000 €** |

Asnjë fond në botë nuk e mban këtë ritëm për vite (fondet më të mira bëjnë 20–40% **në vit**). Pra:

- **1%/ditë është objektiv, jo garanci.** Backtest-i e mat ndershëm: `kthimi_mesatar_ditor_%` dhe `dite_me_>=1%_%`.
- **Tarifat vrasin strategjitë e shpeshta.** Me 0.1% tarifë + 0.05% slippage për anë, çdo tregti kushton ~0.3%. Për të fituar 1% neto duhen ~1.3% bruto.
- **TP 1% / SL 1% kërkon win-rate > ~65%** pas kostove vetëm për të qenë fitimprurës.
- **Monte Carlo ≠ parashikim.** Ai tregon çfarë *mund* të ndodhë nëse e ardhmja ngjan me të kaluarën e afërt.
- Mos e përdor me para reale pa e testuar të paktën disa muaj në *paper trading* dhe pa e kaluar backtest-in në **disa** simbole dhe periudha (jo vetëm aty ku duket mirë → overfitting).

Rekomandim praktik: synoni **drawdown të vogël dhe kthim pozitiv pas tarifave** së pari; 1%/ditë mbajeni si "tavan", jo si "dysheme". Përdorni `--risk 0.1`–`0.25` (rrezik i pjesshëm i kapitalit) në vend të gjithë kapitalit.

## Struktura

```
tonso/
  data.py        Binance / CSV / sintetike
  indicators.py  EMA, RSI, MACD, ATR, Bollinger, ADX
  signals.py     score −100..+100 → BUY/SELL/HOLD + SL/TP me ATR
  scenarios.py   Monte Carlo, skenarë, probabilitet historik i sinjalit
  backtest.py    backtest me tarifa, statistika ditore, objektivi 1%
  checks.py      5 verifikimet (pa parë të ardhmen)
  paper.py       tregtim provë live + Telegram
  cli.py         komandat `analyze` dhe `backtest`
tests/           python -m unittest discover -s tests
```

**Kjo nuk është këshillë financiare.** Tregtimi me kriptovaluta/aksione mbart rrezik të lartë humbjeje.
