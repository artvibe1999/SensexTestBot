# Research strategies 66-79 and the enabled best-6 set (2026-11-08)

Data: SENSEX 1-minute, 29 Sep 2022 - 6 Nov 2026 (from sensex-bot's own Kite session).
Train = up to 31 Oct 2025 (all choices made here), holdout = 1 Nov 2025 - 6 Nov 2026.
Engine backtests: ₹50,000 paper capital, fixed 2 lots, bot risk rules, one position at a time,
max 3 trades a day. Option prices are Black-Scholes on India VIX with 0.3% half-spread.

## How the rules were found
`scripts/screen2.py` and `scripts/screen3.py` test 13 new entry families (276 settings) on the
fast 1-minute simulator from `scripts/screen.py`. A family was kept only if most of its
settings were profitable in both periods. `scripts/greedy.py` replays the bot's
one-position rules on that simulator and builds a set by adding, at lowest priority, the
member that adds the most train-period profit.

## Each new strategy alone (engine, 4 years)

| Strategy | Trades | Net ₹ | PF | Train net | Holdout net (PF) | Verdict |
|---|---:|---:|---:|---:|---:|---|
| ORB60_74 (60-min range break) | 792 | +5,87,219 | 1.33 | +4,89,858 | +97,361 (1.19) | pass |
| VBOL_79 (open ± 0.35 × range, to 14:00) | 809 | +5,35,642 | 1.29 | +3,26,300 | +2,09,342 (1.41) | pass |
| HLBRK_66 (new day high/low beyond noise band) | 423 | +4,48,685 | 1.60 | +3,08,211 | +1,40,474 (1.79) | pass |
| NOISEV_78 (noise momentum, VWAP exit) | 549 | +3,96,555 | 1.42 | +2,46,625 | +1,49,930 (1.70) | pass |
| MIDDAY_68 (12:30 noise momentum) | 360 | +3,58,195 | 1.54 | +2,30,014 | +1,28,181 (1.84) | pass |
| MIDDAY_67 (11:00 noise momentum) | 346 | +3,24,467 | 1.42 | +2,70,765 | +53,701 (1.24) | pass |
| ODRIVE_69 (opening drive) | 415 | +2,94,151 | 1.28 | +1,23,569 | +1,70,581 (1.61) | pass |
| THRUST_72 (thrust candle) | 480 | +2,57,747 | 1.31 | +1,13,746 | +1,44,001 (1.80) | pass |
| LUNCH_73 (12-13h range break) | 299 | +1,87,004 | 1.42 | +1,45,000 | +42,005 (1.32) | pass |
| 3DAY_75 (3-day high/low break) | 251 | +1,22,248 | 1.34 | +22,424 | +99,824 (2.19) | pass |
| INSIDE_71 (inside-day breakout) | 96 | +36,650 | 1.21 | +15,535 | +21,115 (1.51) | pass |
| VWAPPB_70 (VWAP pullback) | 91 | −40,820 | 0.70 | −40,820 | halted | fail |
| FIRST30_77 (first-30-min direction) | 121 | −38,913 | 0.85 | −38,913 | halted | fail |
| CLOSESTR_76 (strong-close follow-through) | 21 | −37,896 | 0.26 | −37,896 | halted | fail |

Older strategies 1-60 over 4 years: only VWAP_03, 0DTE_12 and OPEN_DRV_22 were profitable in
both periods with a usable number of trades (`base4y.jsonl` on the backtest VM).

## Combined (engine, 4 years, one position)

| Set | Net ₹ | ≈ per year | PF | Max DD ₹ | 2023 | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| **Best 6 (enabled)** | **+9,35,912** | **₹2.28 L** | 1.47 | 59,137 | +57,845 | +1,37,534 |
| 17 verified, greedy order | +8,18,748 | ₹2.0 L | 1.30 | 1,23,686 | +3,021 | +2,33,851 |
| 19 research | +6,19,418 | ₹1.5 L | 1.22 | 1,06,083 | −40,674 | +1,69,056 |
| Previous 3 (NOISE+VBO+LATEMOM) | +6,14,307 | ₹1.5 L | 1.46 | 50,850 | −3,087 | +1,48,427 |

Best 6, in priority order: NOISE_61, ORB60_74, INSIDE_71, 3DAY_75, LATEMOM_63, HLBRK_66
(`strategies/tuning.py`). Years: 2022 (Sep-Dec) +71,890, 2023 +57,845, 2024 +4,63,996,
2025 +2,04,589, 2026 (to 6 Nov) +1,37,592.

With one position and 3 trades a day, more strategies do not add up: early entries
(ORB60, VBOL) take the slot and the daily trade budget, so later and stronger signals are
skipped. Profit also leans on 2024. Paper-trade before going live.
