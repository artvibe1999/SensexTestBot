# Research strategies 61–65: new entry logic

## Method

1. **Literature.** Intraday index strategies with published evidence:
   * Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective Intraday Momentum
     Strategy for S&P500 ETF (SPY)": trade breakouts of a "noise area" built from the
     average move from the open at each time of day over 14 days; VWAP trailing stop;
     reported Sharpe 1.33 net, 2007–2024.
   * Gao, Han, Li & Zhou (2018, JFE), "Market Intraday Momentum": the first half-hour
     return predicts the last half-hour return (small R², costs eat much of it).
   * Zarattini & Aziz, opening-range breakout in the direction of the first candle
     (strong on single stocks in play; one replication on indices: gross yes, net ~0).
   No published test on SENSEX/Nifty was found, so our own data decides.
2. **Data.** 4 years of SENSEX 1-minute candles (29 Sep 2022 – 6 Nov 2026, 1,012
   sessions), India VIX and the constituent volume proxy, downloaded with the sensex-bot
   Kite session.
3. **Screen** (`scripts/screen.py`): 249 variants of 7 rule families, each trade priced as
   an ATM weekly option (Black-Scholes on VIX, 0.3% half-spread, Zerodha charges, 2 lots).
   Rules were chosen on **Sep 2022 – Oct 2025** only; **Nov 2025 – Nov 2026** was held out.
4. **Engine backtest** of the chosen rules with the production engine and every risk
   limit (₹50,000 capital, fixed 2 lots).

## Screen: share of variants profitable

| Family | Train profitable | Holdout profitable | Median holdout net ₹ |
|---|---:|---:|---:|
| Volatility breakout (open ± k × prior range) | 48/48 | 48/48 | 168,751 |
| Noise-area momentum | 54/54 | 53/54 | 79,349 |
| Late-session momentum | 9/12 | 12/12 | 43,925 |
| Previous-day high/low breakout | 12/12 | 12/12 | 46,472 |
| Opening range, first-candle direction | 63/72 | 66/72 | 100,107 |
| First-30-minute momentum | 14/24 | 16/24 | 13,861 |
| Gap continuation | 17/27 | 4/27 | −6,444 |

## Strategies (settings picked on the train period)

* **SENSEX_NOISE_61:** every 30 min from 09:45 to 14:15, enter when the close is outside
  open × (1 ± 1.25 × the 14-day average move from the open at that time) on the VWAP side;
  hold to 15:20.
* **SENSEX_VBO_62:** first 5-min close beyond open ± 0.7 × previous day's range by 12:00;
  stop at the opposite level; chandelier trail of 3 × the opening 30-min average range.
* **SENSEX_LATEMOM_63:** at 14:00, day move from the open beyond ±0.6% on the VWAP side;
  hold to 15:20.
* **SENSEX_PDB_64:** previous-day high/low break by 12:00 on days that open inside
  yesterday's range; stop 0.1 × prior range back inside; exit on a close across VWAP.
* **SENSEX_ORB30_65:** 30-min opening range break in the first 30 minutes' direction by
  11:00; stop at the other side; chandelier trail as 62.

They run before strategies 1–60 (`priority = 10`).

## Engine backtest, 4 years (₹50,000, 2 lots, all risk limits)

| Run | Trades | Win % | Net ₹ | PF | Max DD ₹ |
|---|---:|---:|---:|---:|---:|
| NOISE_61 | 453 | 50.6 | 536,805 | 1.50 | 67,399 |
| ORB30_65 | 574 | 43.6 | 388,036 | 1.29 | 78,329 |
| VBO_62 | 294 | 45.2 | 298,685 | 1.43 | 73,276 |
| LATEMOM_63 | 222 | 49.5 | 138,848 | 1.41 | 25,910 |
| PDB_64 | 296 | 27.0 | 93,067 | 1.22 | 43,324 |
| NOISE + VBO + LATEMOM | 579 | 48.2 | 614,307 | 1.46 | 50,850 |
| NOISE + LATEMOM | 488 | 51.4 | 585,137 | 1.52 | 51,400 |
| NOISE + VBO | 550 | 47.3 | 522,072 | 1.39 | 72,535 |
| NOISE + ORB30 | 729 | 44.4 | 464,278 | 1.26 | 103,573 |
| All five | 882 | 40.7 | 536,578 | 1.28 | 112,174 |

Train (Sep 2022 – Oct 2025) vs holdout (Nov 2025 – Nov 2026):

| Set | Train net ₹ (PF) | Holdout net ₹ (PF) | Losing holdout months | Net by year |
|---|---|---|---|---|
| NOISE + VBO + LATEMOM | 465,880 (1.47) | 148,427 (1.41) | 6/13 | 2022 +47k, 2023 −3k, 2024 +292k, 2025 +123k, 2026 +155k |
| NOISE + LATEMOM | 508,074 (1.64) | 77,063 (1.23) | 7/13 | 2022 +25k, 2023 +6k, 2024 +287k, 2025 +181k, 2026 +85k |
| All five | 371,908 (1.26) | 164,670 (1.32) | 4/13 | 2022 +61k, 2023 −73k, 2024 +210k, 2025 +182k, 2026 +156k |

## Caveats

* Option prices are modelled (Black-Scholes, flat VIX smile); the strategies earn most on
  big trend days, where real premiums and spreads can differ from the model.
* 2024 (election-month swings) contributes about half of the 4-year profit; 2023, a quiet
  year, was flat to slightly negative.
* Weekly expiry is modelled as Thursday throughout; SENSEX expiries moved between days
  over 2022–2026.
* Drawdowns of ₹50–110k exceed the ₹50,000 capital at fixed 2 lots.
