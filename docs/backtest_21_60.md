# Backtest: strategies 21–60

Engine replay (`python -m sxpro.backtest run`) of the production code on one year of
SENSEX data downloaded with the sensex-bot Kite session: **6 Nov 2025 – 6 Nov 2026,
249 sessions**, ₹30,000 paper capital, auto lots (90% of available margin), all risk
limits on (10% trade loss cap, 10% daily, 25% weekly, max 3 trades/day, 1 open position).

Caveats: option premiums are modelled with Black-Scholes on India VIX (Kite has no
history for expired options), with a 0.3% half-spread and Zerodha charges. Volume is the
constituent traded-value proxy. Auto lots compound, so a few large wins dominate the
rupee totals; trade counts below ~30 are not statistically meaningful.

## Combined runs (what the bot would do)

| Enabled set | Trades | Win % | Net ₹ | PF | Max DD ₹ |
|---|---:|---:|---:|---:|---:|
| Strategies 1–20 only (current bot) | 538 | 46.7 | −22,060 | 0.96 | 121,293 |
| All 60 | 344 | 41.3 | −24,105 | 0.91 | 43,474 |
| 1–20 + best six of 21–60 | 493 | 46.9 | −23,698 | 0.94 | 52,393 |
| Best six of 21–60 only (42, 52, 56, 54, 27, 34) | 133 | 44.4 | +102,836 | 1.28 | 56,950 |

Strategies 1–20 come first in catalogue order and the bot holds one position at a time,
so when they are enabled they take most of the slots from 21–60.

## Each strategy alone

| Strategy | Trades | Win % | Net ₹ | PF | Max DD ₹ | Avg win | Avg loss | Return % | Top exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ALL 60 (bot rules) | 344 | 41.3 | -24,105 | 0.91 | 43,474 | 1,772 | -1,365 | -80.4 | max holding min 73, target reached 56, closed across EMA 47 |
| SENSEX_IB_EXT_42 | 32 | 46.9 | 109,743 | 1.93 | 48,791 | 15,154 | -6,916 | 365.8 | daily loss limit hit 8, time exit 8, underlying stop 8 |
| SENSEX_DBL_LIQ_52 | 13 | 76.9 | 26,844 | 3.54 | 8,675 | 3,741 | -3,521 | 89.5 | target reached 9, underlying stop 2, daily loss limit hit 1 |
| SENSEX_FIB_CONFL_56 | 15 | 53.3 | 16,410 | 1.89 | 6,939 | 4,344 | -2,620 | 54.7 | target reached 5, underlying stop 5, trailing stop 3 |
| SENSEX_FLAG_BRK_54 | 41 | 39.0 | 14,418 | 1.21 | 25,093 | 5,243 | -2,779 | 48.1 | closed back inside the flag 15, trailing stop 14, underlying stop 6 |
| SENSEX_ORB_FAIL_24 | 141 | 43.3 | 13,429 | 1.04 | 77,626 | 5,456 | -3,992 | 44.8 | underlying stop 44, target reached 31, daily loss limit hit 24 |
| SENSEX_LIQ_GRAB_27 | 35 | 45.7 | 10,087 | 1.52 | 10,992 | 1,851 | -1,028 | 33.6 | underlying stop 13, target reached 12, trailing stop 6 |
| SENSEX_VOL_DRY_36 | 6 | 83.3 | 8,120 | 15.51 | 560 | 1,736 | -560 | 27.1 | target reached 4, time exit 1, closed beyond stop 1 |
| SENSEX_OPEN_DRV_22 | 4 | 75.0 | 7,817 | 3.77 | 2,817 | 3,545 | -2,817 | 26.1 | closed across VWAP 2, target reached 1, underlying stop 1 |
| SENSEX_OPEN_REJ_34 | 14 | 35.7 | 5,730 | 1.24 | 20,535 | 5,873 | -2,626 | 19.1 | crossed-min EMA 9, max holding min 3, daily loss limit hit 2 |
| SENSEX_TOD_REV_50 | 4 | 50.0 | 5,658 | 1.52 | 10,943 | 8,300 | -5,471 | 18.9 | daily loss limit hit 2, trailing stop 1, target reached 1 |
| SENSEX_SESSION_T_26 | 7 | 42.9 | 3,545 | 1.27 | 6,178 | 5,559 | -3,283 | 11.8 | daily loss limit hit 3, time exit 3, MACD crossed against trade 1 |
| SENSEX_ATR_EXP_25 | 196 | 42.9 | 2,641 | 1.02 | 21,544 | 1,981 | -1,462 | 8.8 | ATR back below its SMA 108, closed beyond stop 31, target reached 24 |
| SENSEX_GAP_EXH_59 | 2 | 50.0 | 895 | 1.65 | 1,381 | 2,276 | -1,381 | 3.0 | trailing stop 1, reclaimed VWAP 1 |
| SENSEX_TREND_EXH_30 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_RVOL_BRK_32 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_GAMMA_SQR_39 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_GAP_FILL_REV_40 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_DIB_44 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_OB_TEST_45 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_OI_WALL_48 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_VWAP_PINCH_57 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_PREM_LOW_58 | 0 | 0.0 | 0 | – | 0 | 0 | 0 | 0.0 |  |
| SENSEX_EOD_IMB_51 | 35 | 48.6 | -3,044 | 0.64 | 3,638 | 315 | -467 | -10.1 | intraday square-off 30, underlying stop 5 |
| SENSEX_GAP_GO_31 | 11 | 36.4 | -3,671 | 0.78 | 8,443 | 3,185 | -2,344 | -12.2 | time exit 3, trailing stop 2, daily loss limit hit 2 |
| SENSEX_VWAP_PIN_28 | 2 | 50.0 | -3,730 | 0.20 | 4,681 | 951 | -4,681 | -12.4 | daily loss limit hit 1, trailing stop 1 |
| SENSEX_TTM_MOM_53 | 13 | 46.2 | -3,962 | 0.74 | 8,483 | 1,842 | -2,145 | -13.2 | momentum histogram fading 7, daily loss limit hit 3, time exit 3 |
| SENSEX_AVWAP_41 | 65 | 49.2 | -4,157 | 0.92 | 12,468 | 1,506 | -1,586 | -13.9 | target reached 21, closed beyond stop 13, closed across AVWAP 11 |
| SENSEX_VWAP_DEV_21 | 17 | 52.9 | -5,197 | 0.61 | 12,180 | 912 | -1,675 | -17.3 | underlying stop 6, trailing stop 4, target reached 3 |
| SENSEX_TICK_DIV_37 | 114 | 48.2 | -6,043 | 0.93 | 16,432 | 1,396 | -1,404 | -20.1 | underlying stop 37, target reached 32, trailing stop 23 |
| SENSEX_POC_BNC_43 | 10 | 30.0 | -6,373 | 0.49 | 8,170 | 2,003 | -1,769 | -21.2 | underlying stop 4, target reached 3, daily loss limit hit 2 |
| SENSEX_EMA_TWIST_33 | 29 | 37.9 | -8,300 | 0.59 | 17,369 | 1,094 | -1,130 | -27.7 | closed beyond stop 14, target reached 8, trailing stop 4 |
| SENSEX_VIX_CRUSH_29 | 8 | 25.0 | -8,418 | 0.18 | 8,418 | 938 | -1,716 | -28.1 | closed below EMA 6, daily loss limit hit 1, time exit 1 |
| SENSEX_SLING_46 | 5 | 40.0 | -9,540 | 0.18 | 10,820 | 1,065 | -3,890 | -31.8 | daily loss limit hit 3, trailing stop 1, target reached 1 |
| SENSEX_NR7_BRK_38 | 33 | 30.3 | -11,383 | 0.70 | 20,055 | 2,668 | -1,655 | -37.9 | underlying stop 15, trailing stop 6, time exit 5 |
| SENSEX_PDC_BNC_23 | 76 | 35.5 | -11,606 | 0.78 | 12,545 | 1,483 | -1,054 | -38.7 | underlying stop 32, target reached 20, trailing stop 12 |
| SENSEX_MACRO_DIV_60 | 59 | 39.0 | -15,542 | 0.55 | 22,330 | 823 | -958 | -51.8 | underlying stop 32, trailing stop 14, target reached 10 |
| SENSEX_HDIV_47 | 75 | 41.3 | -16,190 | 0.61 | 20,945 | 822 | -947 | -54.0 | target reached 27, underlying stop 23, RSI crossed below 12 |
| SENSEX_MTF_ALIGN_55 | 77 | 27.3 | -19,271 | 0.62 | 19,271 | 1,473 | -896 | -64.2 | underlying stop 32, trailing stop 12, m closed acrossm EMA 12 |
| SENSEX_TEMA_ALIGN_49 | 90 | 36.7 | -20,009 | 0.75 | 23,806 | 1,845 | -1,419 | -66.7 | EMA crossed EMA 21, closed beyond stop 15, target reached 13 |
| SENSEX_FRACTAL_BRK_35 | 103 | 26.2 | -21,445 | 0.67 | 21,445 | 1,599 | -850 | -71.5 | closed across EMA 60, daily loss limit hit 17, max holding min 10 |


**No trades:** SENSEX_TREND_EXH_30, SENSEX_RVOL_BRK_32, SENSEX_GAMMA_SQR_39, SENSEX_GAP_FILL_REV_40, SENSEX_DIB_44, SENSEX_OB_TEST_45, SENSEX_OI_WALL_48, SENSEX_VWAP_PINCH_57, SENSEX_PREM_LOW_58
**Profitable with >=10 trades and PF>=1.2: SENSEX_IB_EXT_42, SENSEX_DBL_LIQ_52, SENSEX_FIB_CONFL_56, SENSEX_FLAG_BRK_54, SENSEX_LIQ_GRAB_27, SENSEX_OPEN_REJ_34

### Why some strategies never traded
* **39, 48** need option-chain OI, which has no history: live-only.
* **32, 57** use point thresholds (range < 30 pts over 4 candles; 6 candles within 15 pts
  of VWAP) that are tighter than normal SENSEX 5-min candles at ~80,000.
* **44:** the double-inside-bar pattern appeared 100 times and broke out 29 times, but the
  breakout candle never had more volume than the two inside bars combined.
* **58:** 116 gap-down days, 55 swept the opening low by 9:45, 9 recovered with a bullish
  engulfing candle, none of those with the required volume.
* **40:** 44 gaps filled to the previous close, but none with a doji/pin bar plus volume
  spike on the touch candle.
* **30, 45:** RSI > 85 with four same-colour candles fully outside the Bollinger Band
  (1 signal, blocked by the regime filter); first-tap order-block retests with an
  engulfing candle did not occur.

## Strategies 1–20 alone (same period and settings)

| Strategy | Trades | Win % | Net ₹ | PF | Max DD ₹ |
|---|---:|---:|---:|---:|---:|
| SENSEX_SUP_10 | 318 | 59.1 | 64,884 | 1.08 | 113,249 |
| SENSEX_VWAP_03 | 20 | 80.0 | 8,979 | 1.81 | 7,648 |
| SENSEX_VOL_08 | 1 | 100.0 | 3,948 | – | 0 |
| SENSEX_GAP_07 | 0 | 0.0 | 0 | – | 0 |
| SENSEX_MCD_18 | 0 | 0.0 | 0 | – | 0 |
| SENSEX_VWAP_X_16 | 36 | 27.8 | -1,493 | 0.97 | 24,884 |
| SENSEX_RNG_14 | 11 | 72.7 | -1,624 | 0.85 | 6,815 |
| SENSEX_MOM_01 | 1 | 0.0 | -3,101 | 0.00 | 3,101 |
| SENSEX_0DTE_12 | 6 | 33.3 | -4,080 | 0.79 | 10,454 |
| SENSEX_FIB_19 | 32 | 40.6 | -4,270 | 0.89 | 23,418 |
| SENSEX_REV_05 | 12 | 50.0 | -6,974 | 0.35 | 6,974 |
| SENSEX_FALSE_11 | 13 | 38.5 | -7,267 | 0.42 | 9,517 |
| SENSEX_BRK_06 | 13 | 30.8 | -8,582 | 0.44 | 11,929 |
| SENSEX_DOJI_15 | 27 | 33.3 | -9,742 | 0.62 | 9,782 |
| SENSEX_TRAP_02 | 16 | 31.2 | -13,471 | 0.19 | 15,556 |
| SENSEX_EOD_20 | 24 | 25.0 | -16,458 | 0.21 | 16,458 |
| SENSEX_WMA_13 | 66 | 39.4 | -17,950 | 0.50 | 17,950 |
| SENSEX_MACD_17 | 34 | 26.5 | -19,487 | 0.31 | 22,876 |
| SENSEX_TREND_04 | 17 | 0.0 | -20,007 | 0.00 | 20,007 |
| SENSEX_IB_09 | 88 | 26.1 | -21,925 | 0.55 | 25,197 |

## The 16 profitable strategies together (enabled on sensex-bot 2026-11-07)

Solo net > 0: 03, 08, 10, 22, 24, 25, 26, 27, 34, 36, 42, 50, 52, 54, 56, 59. All other 44
strategies are disabled.

| Run | Trades | Win % | Gross ₹ | Charges ₹ | Net ₹ | PF | Max DD ₹ | Final balance ₹ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 profitable together | 488 | 50.4 | 90,951 | 53,293 | +37,659 | 1.04 | 213,678 | 67,659 |

Per strategy inside that run: 27 +36,266 (10 trades), 25 +28,001 (85), 24 +23,130 (110),
03 +20,429 (13), 22 +4,229, 34 +4,163, 59 +3,662, 26 +400, 36 0, 54 −260, 56 −2,710,
50 −3,555, 52 −3,979, 42 −21,757 (12), 10 −50,360 (207).

Monthly net: Nov +19.6k, Dec −14.9k, Jan +16.8k, Feb +33.0k, Mar +32.2k, Apr +38.8k,
May −53.0k, Jun −43.2k, Jul −11.8k, Aug +12.6k, Sep −12.3k, Oct +1.6k, Nov (to 6th) +18.4k.

Together the strategies compete for one position and three trades a day, so their
combined result is not the sum of the solo results: SENSEX_SUP_10 (+64.9k alone) takes 207
of the 488 slots and loses 50.4k in the combined run, and IB_EXT_42 (+109.7k alone) gets
only 12 trades. Auto lots compound, which is why the drawdown is several times the
starting ₹30,000.


## Fixed 2 lots (no compounding)

Same period and ₹30,000 capital, `--lots 2` (every trade ran at 2 lots).

| Run | Trades | Win % | Gross ₹ | Charges ₹ | Net ₹ | PF | Max DD ₹ | Worst trade ₹ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 (the 16 without SUP_10) | 422 | 45.3 | 133,764 | 32,316 | +101,449 | 1.26 | 47,709 | −7,520 |
| 16 (with SUP_10) | 585 | 51.8 | 171,812 | 45,225 | +126,587 | 1.23 | 55,712 | −7,608 |
| 16, auto lots (for comparison) | 488 | 50.4 | 90,951 | 53,293 | +37,659 | 1.04 | 213,678 | – |

Monthly net, 15 at 2 lots: Nov +11.0k, Dec +3.4k, Jan +32.8k, Feb +26.8k, Mar +42.1k,
Apr +2.3k, May +1.4k, Jun +0.5k, Jul −4.5k, Aug −2.5k, Sep −14.5k, Oct −9.3k, Nov +11.8k.

Monthly net, 16 at 2 lots: Nov +11.7k, Dec −0.5k, Jan +44.3k, Feb +32.2k, Mar +29.6k,
Apr +16.3k, May −2.2k, Jun −11.8k, Jul −7.9k, Aug +8.7k, Sep −14.1k, Oct −2.8k, Nov +23.1k.
