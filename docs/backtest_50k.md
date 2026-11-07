# Backtest at ₹50,000, fixed 2 lots: all 60 strategies, loss diagnosis, adjustment search

Period 6 Nov 2025 – 6 Nov 2026 (249 sessions), ₹50,000 paper capital, fixed 2 lots, all
risk limits on, Zerodha charges included, option premiums modelled (Black-Scholes on
India VIX). Scripts: `scripts/diagnose.py`, `scripts/tune_search.py`, `scripts/final_runs.py`.

## 1. Each strategy alone

| Strategy | Trades | Win % | Net ₹ | PF | Max DD ₹ | Avg win | Avg loss | Return % | Top exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ALL 60 (bot rules) | 636 | 41.0 | -6,589 | 0.99 | 100,240 | 2,799 | -1,965 | -13.2 | max holding min 156, target reached 93, closed across EMA 93 |
| SENSEX_TEMA_ALIGN_49 | 349 | 42.4 | 76,475 | 1.15 | 36,946 | 3,962 | -2,537 | 152.9 | EMA crossed EMA 84, closed beyond stop 76, max holding min 66 |
| SENSEX_ATR_EXP_25 | 201 | 43.3 | 49,444 | 1.32 | 21,977 | 2,323 | -1,339 | 98.9 | ATR back below its SMA 117, closed beyond stop 45, target reached 24 |
| SENSEX_IB_EXT_42 | 34 | 47.1 | 48,574 | 2.16 | 13,449 | 5,656 | -2,329 | 97.1 | underlying stop 15, time exit 11, target reached 8 |
| SENSEX_SUP_10 | 351 | 61.5 | 40,692 | 1.12 | 42,068 | 1,768 | -2,528 | 81.4 | target reached 199, Supertrend flipped 95, max holding min 30 |
| SENSEX_FLAG_BRK_54 | 41 | 39.0 | 21,552 | 1.47 | 10,355 | 4,243 | -1,854 | 43.1 | closed back inside the flag 15, trailing stop 14, underlying stop 7 |
| SENSEX_ORB_FAIL_24 | 149 | 43.6 | 20,642 | 1.13 | 37,891 | 2,803 | -1,923 | 41.3 | underlying stop 62, target reached 32, max holding min 24 |
| SENSEX_AVWAP_41 | 67 | 49.3 | 17,002 | 1.31 | 10,417 | 2,174 | -1,610 | 34.0 | target reached 22, closed beyond stop 17, closed across AVWAP 14 |
| SENSEX_VWAP_X_16 | 36 | 27.8 | 14,995 | 1.32 | 21,173 | 6,146 | -1,787 | 30.0 | crossed back across VWAP 19, target reached 6, time exit 5 |
| SENSEX_VWAP_03 | 20 | 90.0 | 12,620 | 3.14 | 3,609 | 1,029 | -2,951 | 25.2 | target reached 18, closed across VWAP 2 |
| SENSEX_GAP_GO_31 | 13 | 46.2 | 12,275 | 1.98 | 7,525 | 4,126 | -1,783 | 24.5 | time exit 5, closed across VWAP 5, trailing stop 2 |
| SENSEX_DBL_LIQ_52 | 13 | 76.9 | 10,546 | 2.84 | 3,848 | 1,628 | -1,912 | 21.1 | target reached 9, underlying stop 2, time exit 1 |
| SENSEX_OPEN_REJ_34 | 14 | 35.7 | 7,931 | 1.62 | 9,943 | 4,161 | -1,430 | 15.9 | crossed-min EMA 11, max holding min 3 |
| SENSEX_OPEN_DRV_22 | 4 | 75.0 | 7,817 | 3.77 | 2,817 | 3,545 | -2,817 | 15.6 | closed across VWAP 2, target reached 1, underlying stop 1 |
| SENSEX_VWAP_PIN_28 | 2 | 100.0 | 6,731 | – | 0 | 3,366 | 0 | 13.5 | intraday square-off 1, trailing stop 1 |
| SENSEX_SESSION_T_26 | 7 | 42.9 | 5,343 | 1.73 | 4,765 | 4,226 | -1,833 | 10.7 | time exit 4, MACD crossed against trade 3 |
| SENSEX_NR7_BRK_38 | 34 | 35.3 | 4,769 | 1.11 | 25,108 | 4,169 | -2,057 | 9.5 | underlying stop 18, trailing stop 7, time exit 6 |
| SENSEX_FIB_19 | 32 | 43.8 | 4,716 | 1.11 | 17,513 | 3,375 | -2,363 | 9.4 | time exit 9, broke level 8, target reached 7 |
| SENSEX_FIB_CONFL_56 | 15 | 53.3 | 4,586 | 1.28 | 6,042 | 2,592 | -2,307 | 9.2 | underlying stop 6, target reached 5, trailing stop 3 |
| SENSEX_VOL_DRY_36 | 6 | 83.3 | 4,381 | 12.27 | 389 | 954 | -389 | 8.8 | target reached 4, time exit 1, closed beyond stop 1 |
| SENSEX_GAP_EXH_59 | 2 | 50.0 | 3,662 | 4.91 | 936 | 4,598 | -936 | 7.3 | trailing stop 1, reclaimed VWAP 1 |
| SENSEX_DOJI_15 | 27 | 33.3 | 3,282 | 1.13 | 8,767 | 3,067 | -1,351 | 6.6 | closed across EMA 10, underlying stop 9, target reached 7 |
| SENSEX_TOD_REV_50 | 4 | 50.0 | 2,359 | 1.65 | 3,635 | 2,997 | -1,818 | 4.7 | underlying stop 2, trailing stop 1, target reached 1 |
| SENSEX_PDC_BNC_23 | 80 | 36.2 | 2,316 | 1.03 | 12,167 | 2,426 | -1,334 | 4.6 | underlying stop 38, target reached 22, trailing stop 12 |
| SENSEX_0DTE_12 | 6 | 33.3 | 1,830 | 1.56 | 1,854 | 2,555 | -820 | 3.7 | premium stop 4, trailing stop 2 |
| SENSEX_VOL_08 | 1 | 100.0 | 1,551 | – | 0 | 1,551 | 0 | 3.1 | target reached 1 |
| SENSEX_LIQ_GRAB_27 | 35 | 45.7 | 1,545 | 1.05 | 12,473 | 2,235 | -1,801 | 3.1 | underlying stop 14, target reached 12, trailing stop 6 |
| SENSEX_GAP_07 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_MCD_18 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_TREND_EXH_30 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_RVOL_BRK_32 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_GAMMA_SQR_39 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_GAP_FILL_REV_40 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_DIB_44 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_OB_TEST_45 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_OI_WALL_48 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_VWAP_PINCH_57 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_PREM_LOW_58 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_TTM_MOM_53 | 13 | 46.2 | -118 | 0.99 | 6,214 | 1,850 | -1,603 | -0.2 | momentum histogram fading 10, time exit 3 |
| SENSEX_RNG_14 | 11 | 72.7 | -747 | 0.88 | 3,146 | 665 | -2,022 | -1.5 | target reached 5, reached middle BB 3, closed above upper BB 2 |
| SENSEX_SLING_46 | 5 | 60.0 | -1,021 | 0.79 | 4,053 | 1,294 | -2,451 | -2.0 | underlying stop 2, trailing stop 1, max holding min 1 |
| SENSEX_EOD_IMB_51 | 14 | 42.9 | -2,396 | 0.65 | 4,615 | 741 | -855 | -4.8 | intraday square-off 11, underlying stop 3 |
| SENSEX_BRK_06 | 14 | 28.6 | -2,552 | 0.85 | 10,999 | 3,622 | -1,704 | -5.1 | closed back inside BB mid 9, time exit 4, max holding min 1 |
| SENSEX_MOM_01 | 1 | 0.0 | -3,101 | 0.00 | 3,101 | 0 | -3,101 | -6.2 | premium stop 1 |
| SENSEX_POC_BNC_43 | 10 | 30.0 | -3,512 | 0.64 | 5,675 | 2,125 | -1,412 | -7.0 | underlying stop 6, target reached 3, trailing stop 1 |
| SENSEX_REV_05 | 13 | 53.8 | -5,318 | 0.52 | 6,348 | 823 | -1,846 | -10.6 | underlying stop 6, RSI crossed above 2, time exit 2 |
| SENSEX_VWAP_DEV_21 | 18 | 50.0 | -6,665 | 0.55 | 13,430 | 907 | -1,648 | -13.3 | underlying stop 8, trailing stop 4, target reached 3 |
| SENSEX_TICK_DIV_37 | 111 | 48.6 | -6,684 | 0.94 | 18,383 | 1,788 | -1,812 | -13.4 | underlying stop 40, target reached 31, trailing stop 22 |
| SENSEX_EMA_TWIST_33 | 29 | 37.9 | -7,785 | 0.67 | 18,254 | 1,415 | -1,297 | -15.6 | closed beyond stop 16, target reached 8, trailing stop 4 |
| SENSEX_VIX_CRUSH_29 | 8 | 25.0 | -10,832 | 0.21 | 10,832 | 1,420 | -2,279 | -21.7 | closed below EMA 6, time exit 1, daily loss limit hit 1 |
| SENSEX_FALSE_11 | 13 | 38.5 | -10,954 | 0.32 | 14,128 | 1,050 | -2,026 | -21.9 | underlying stop 7, target reached 4, trailing stop 1 |
| SENSEX_TRAP_02 | 16 | 31.2 | -12,288 | 0.32 | 15,633 | 1,154 | -1,642 | -24.6 | underlying stop 10, target reached 4, trailing stop 1 |
| SENSEX_EOD_20 | 25 | 32.0 | -18,941 | 0.28 | 18,941 | 908 | -1,541 | -37.9 | intraday square-off 21, underlying stop 4 |
| SENSEX_HDIV_47 | 70 | 41.4 | -20,913 | 0.66 | 23,530 | 1,397 | -1,498 | -41.8 | target reached 25, underlying stop 21, RSI crossed below 12 |
| SENSEX_MACRO_DIV_60 | 56 | 39.3 | -22,412 | 0.50 | 27,290 | 1,011 | -1,313 | -44.8 | underlying stop 32, trailing stop 12, target reached 10 |
| SENSEX_WMA_13 | 100 | 44.0 | -23,601 | 0.72 | 23,601 | 1,377 | -1,503 | -47.2 | max holding min 54, time exit 14, WMA crossed back 9 |
| SENSEX_MTF_ALIGN_55 | 84 | 27.4 | -28,092 | 0.71 | 29,967 | 2,931 | -1,566 | -56.2 | underlying stop 36, m closed acrossm EMA 15, trailing stop 14 |
| SENSEX_TREND_04 | 17 | 0.0 | -28,612 | 0.00 | 28,612 | 0 | -1,683 | -57.2 | closed across EMA 17 |
| SENSEX_MACD_17 | 32 | 25.0 | -28,861 | 0.33 | 33,478 | 1,745 | -1,784 | -57.7 | MACD signal-line crossover 19, underlying stop 6, trailing stop 3 |
| SENSEX_IB_09 | 95 | 27.4 | -31,861 | 0.59 | 34,509 | 1,763 | -1,126 | -63.7 | closed back inside mother bar 47, max holding min 16, underlying stop 15 |
| SENSEX_FRACTAL_BRK_35 | 120 | 26.7 | -33,983 | 0.74 | 42,882 | 3,054 | -1,497 | -68.0 | closed across EMA 74, daily loss limit hit 17, max holding min 11 |

No trades: SENSEX_GAP_07, SENSEX_MCD_18, SENSEX_TREND_EXH_30, SENSEX_RVOL_BRK_32, SENSEX_GAMMA_SQR_39, SENSEX_GAP_FILL_REV_40, SENSEX_DIB_44, SENSEX_OB_TEST_45, SENSEX_OI_WALL_48, SENSEX_VWAP_PINCH_57, SENSEX_PREM_LOW_58

26 profitable (net > 0), 23 losing, 11 with no trades (39 and 48 need option OI history,
the rest have entry rules that SENSEX never met in the year; see backtest_21_60.md).
Losing strategies that hit the drawdown limits stop trading for the rest of the year, so
their full-year numbers understate how much they would lose.

## 2. Why the losing strategies lose (scripts/diagnose.py)

* **Entries are wrong, not stops too tight.** Losing trades moved only 0.3–0.6 ATR in
  favour (median) before failing, against 1.0–2.0 ATR adverse. Only #53 TTM (71%), #06
  BRK (50%) and #35/#55 (≈37%) had many losers that were ≥ 1 ATR in profit first.
* **Winners exit early:** winners peak at 1.5–3.4 ATR but exit at 0.8–1.8 ATR.
* **Time of day and side concentrate losses:** #09 IB loses ₹28.7k after 13:30 and ₹28.7k
  on PUTs; #13 WMA loses ₹22k on CALLs and ₹23k after 13:30; #47 HDIV loses ₹18.7k on CALLs.
* **Charges** exceed the gross edge for #37 TICK_DIV (gross +₹1.8k, charges ₹8.4k) and #14 RNG.

## 3. Adjustment search (walk-forward)

18 losing strategies with ≥ 12 trades were each replayed with 13 adjustments that answer
those findings (15-min trend filter, ADX ≥ 20, stop ≥ 1 ATR, bank half at 1R / 1.5R,
trail without a fixed target, no entries after 13:30 / 12:00, 10:00–13:30 only, CALLs only,
PUTs only, and two combinations) on **6 Nov 2025 – 30 Jun 2026**. The best adjustment per
strategy (≥ 8 trades, PF ≥ 1.15, net > 0) was then replayed unseen on **1 Jul – 6 Nov 2026**
and kept only if still profitable there. #01, #14, #29, #43, #46 had too few trades to tune.

| Strategy | Best in-sample adjustment | In-sample | Out-of-sample (adjusted) | Out-of-sample (original) | Adopted |
|---|---|---:|---:|---:|---|
| SENSEX_MACD_17 | 15-min trend filter | 26 trades, +₹15,036, PF 1.69 | 12, −₹2,327, PF 0.72 | 25, −₹11,319 | no |
| SENSEX_TICK_DIV_37 | trail, no fixed target | 76, +₹26,181, PF 1.34 | 38, −₹989, PF 0.97 | 38, −₹3,172 | no |

No other strategy had any adjustment that was profitable in-sample with enough trades.
Both candidates improved on the original out of sample but still lost money, so **no
adjusted strategy was adopted** (`sxpro/strategies/tuning.py` stays empty). The losses
come from the entry signals themselves; the generic adjustments do not fix them.

## 4. The 26 profitable strategies together

| Run | Trades | Win % | Gross ₹ | Charges ₹ | Net ₹ | PF | Max DD ₹ | Final balance ₹ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full year | 669 | 44.8 | 113,636 | 52,420 | **+61,215** | 1.08 | 118,950 | 111,215 |
| 1 Jul – 6 Nov 2026 only (fresh ₹50k) | 94 | 41.5 | −27,695 | 6,359 | **−34,054** | 0.63 | 41,101 | 15,946 |

Full-year monthly net: Nov +20.2k, Dec +6.9k, Jan +2.8k, Feb +23.2k, Mar +10.2k,
Apr +37.9k, May +4.4k, Jun −20.6k, Jul −44.4k, Aug +7.3k, Sep −14.5k, Oct +1.1k, Nov +26.8k.

Inside the full-year run: VWAP_X_16 +17.6k, SUP_10 +16.9k, PDC_BNC_23 +13.2k, AVWAP_41
+12.8k, LIQ_GRAB_27 +11.2k … ORB_FAIL_24 −3.8k, ATR_EXP_25 −8.3k, TEMA_ALIGN_49 −27.5k
(203 trades). In the July–November run the balance fell to ₹15.9k, after which 277
signals were skipped because 2 lots were no longer affordable.

The "profitable" list is chosen with hindsight on the same year. Started fresh on the last
four months, the set lost ₹34k, so there is no evidence yet of a durable edge.
