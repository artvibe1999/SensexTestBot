# SENSEX PRO – Strategies 41 to 60

*Note: As strictly mandated by the project integrity rules, performance metrics for all strategies below must be populated by running these precise rules through a quantitative backtesting engine using your historical SENSEX options dataset.*

## Strategy 41: SENSEX_AVWAP_41 (Anchored VWAP Bounce)

 1. **Name/ID:** SENSEX_AVWAP_41
 2. **Trading hypothesis:** VWAP anchored to the high/low of the first 15 minutes provides the most accurate average price for institutional intraday positioning.
 3. **Best Market Conditions:** Trending markets experiencing deep pullbacks.
 4. **Avoid in:** Choppy markets chopping through the AVWAP.
 5. **Indicators:** Anchored VWAP (anchored to 9:30 AM extreme).
 6. **Entry Conditions:** Price pulls back to the AVWAP and forms a rejection pin bar or engulfing candle.
 7. **Exit Conditions:** Close on the opposite side of the AVWAP.
 8. **CALL/PUT Logic:** Bounce off AVWAP upwards = CALL; Reject off AVWAP downwards = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Volume drops on pullback, expands on rejection.
13. **Candle Confirmation:** Rejection tail touching the AVWAP.
14. **Stop-loss:** Close across the AVWAP line.
15. **Profit-booking:** 1:2 Risk-to-Reward.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:00 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Yes, on subsequent tests.
20. **Risk/Capital:** Max 10% capital (₹5,000).
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 42: SENSEX_IB_EXT_42 (Initial Balance Extension)

 1. **Name/ID:** SENSEX_IB_EXT_42
 2. **Trading hypothesis:** Breaking the first 60-minute range (Initial Balance) with volume indicates long-term timeframe participants taking control.
 3. **Best Market Conditions:** Narrow Initial Balance (IB).
 4. **Avoid in:** Unusually wide IB (exhaustion risk).
 5. **Indicators:** 60-min High/Low (Initial Balance).
 6. **Entry Conditions:** Post 10:15 AM, 5-min candle closes firmly outside the IB.
 7. **Exit Conditions:** Price drops back into the IB and closes below its midpoint.
 8. **CALL/PUT Logic:** Break IB High = CALL; Break IB Low = PUT.
 9. **Strike Selection:** Slightly OTM (Delta ~0.45).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹350.
12. **Volume Confirmation:** RVOL > 1.5x on breakout.
13. **Candle Confirmation:** Marubozu or strong body.
14. **Stop-loss:** Opposite side of the breakout candle.
15. **Profit-booking:** 1:3 RR.
16. **Trailing SL:** VWAP.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** Rest of day.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 43: SENSEX_POC_BNC_43 (Volume Point of Control Bounce)

 1. **Name/ID:** SENSEX_POC_BNC_43
 2. **Trading hypothesis:** The highest volume node (POC) of the previous day acts as a major institutional magnet and reaction zone.
 3. **Best Market Conditions:** Mean-reverting markets.
 4. **Avoid in:** Gap-and-go trend days that never retest yesterday's range.
 5. **Indicators:** Volume Profile (Previous Day POC).
 6. **Entry Conditions:** Price touches yesterday's POC and prints a reversal candle on the 5-min chart.
 7. **Exit Conditions:** Fails to bounce and closes decisively beyond POC.
 8. **CALL/PUT Logic:** Drop to POC and bounce = CALL; Rally to POC and reject = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹400.
12. **Volume Confirmation:** High volume absorption at the POC.
13. **Candle Confirmation:** Pin bar/Hammer.
14. **Stop-loss:** POC +/- 20 index points.
15. **Profit-booking:** Previous day High/Low.
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 44: SENSEX_DIB_44 (Double Inside Bar Breakout)

 1. **Name/ID:** SENSEX_DIB_44
 2. **Trading hypothesis:** Two consecutive inside bars represent extreme volatility compression. The ensuing breakout is highly explosive.
 3. **Best Market Conditions:** Mid-day lulls (12:00 PM - 1:30 PM).
 4. **Avoid in:** Immediately post-open.
 5. **Indicators:** Price Action (Mother bar + 2 inside bars).
 6. **Entry Conditions:** Price breaks the extreme high or low of the Mother Bar.
 7. **Exit Conditions:** Price drops back into the Mother Bar range.
 8. **CALL/PUT Logic:** Break Mother Bar High = CALL; Break Low = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** Breakout volume must exceed the volume of the two inside bars combined.
13. **Candle Confirmation:** Close outside Mother Bar.
14. **Stop-loss:** Midpoint of the Mother Bar.
15. **Profit-booking:** 1:2.5 RR.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1 hour.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 45: SENSEX_OB_TEST_45 (Order Block Retest)

 1. **Name/ID:** SENSEX_OB_TEST_45
 2. **Trading hypothesis:** Institutional algorithms place limit orders at the origin of impulsive moves (Order Blocks).
 3. **Best Market Conditions:** Trending markets pulling back to the morning origin.
 4. **Avoid in:** V-shaped reversal days with heavy momentum against the OB.
 5. **Indicators:** Order Block (last opposite candle before a massive impulse move).
 6. **Entry Conditions:** Price taps the OB zone for the *first time* and forms a 5-min reversal candle.
 7. **Exit Conditions:** Close entirely beyond the Order Block zone.
 8. **CALL/PUT Logic:** Tap bullish OB (demand) = CALL; Tap bearish OB (supply) = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Average on approach, spike on tap.
13. **Candle Confirmation:** Engulfing out of the OB zone.
14. **Stop-loss:** Just below/above the OB zone.
15. **Profit-booking:** Next major liquidity zone (swing high/low).
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2-3 hours.
19. **Re-entry:** No (first tap only).
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 46: SENSEX_SLING_46 (VWAP Slingshot)

 1. **Name/ID:** SENSEX_SLING_46
 2. **Trading hypothesis:** A sudden, low-volume piercing of VWAP that immediately reverses traps breakout traders, acting as a slingshot.
 3. **Best Market Conditions:** Trending markets.
 4. **Avoid in:** Choppy, range-bound days where VWAP is flat.
 5. **Indicators:** VWAP.
 6. **Entry Conditions:** Price breaks VWAP against the primary trend, but the very next candle engulfs it and closes back on the trend side of VWAP.
 7. **Exit Conditions:** Fails to make a new high/low within 3 candles.
 8. **CALL/PUT Logic:** Fake breakdown of VWAP = CALL; Fake breakout of VWAP = PUT.
 9. **Strike Selection:** Slightly OTM (Delta ~0.40).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹300.
12. **Volume Confirmation:** Fakeout has low volume, reversal candle has high volume.
13. **Candle Confirmation:** Engulfing candle closing past VWAP.
14. **Stop-loss:** High/Low of the fakeout wick.
15. **Profit-booking:** 1:2 RR.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1 hour.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 47: SENSEX_HDIV_47 (RSI Hidden Divergence)

 1. **Name/ID:** SENSEX_HDIV_47
 2. **Trading hypothesis:** Hidden divergence signals trend continuation, offering a superior entry point during pullbacks.
 3. **Best Market Conditions:** Established trends with clear swing highs/lows.
 4. **Avoid in:** Choppy, undefined markets.
 5. **Indicators:** RSI(14).
 6. **Entry Conditions:** Uptrend: Price makes higher low, but RSI makes lower low. Downtrend: Price makes lower high, but RSI makes higher high.
 7. **Exit Conditions:** RSI crosses 50 in opposite direction.
 8. **CALL/PUT Logic:** Hidden Bullish Div = CALL; Hidden Bearish Div = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹450.
12. **Volume Confirmation:** Average.
13. **Candle Confirmation:** Bullish/Bearish engulfing confirming the bounce.
14. **Stop-loss:** Recent swing extreme.
15. **Profit-booking:** Previous Swing High/Low.
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Yes, on next hidden divergence.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 48: SENSEX_OI_WALL_48 (Open Interest Wall Reject)

 1. **Name/ID:** SENSEX_OI_WALL_48
 2. **Trading hypothesis:** Massive Open Interest blocks at round numbers (e.g., 75000, 76000) act as institutional defense lines.
 3. **Best Market Conditions:** First test of a major psychological strike.
 4. **Avoid in:** Late day expiry squeezes where walls are broken.
 5. **Indicators:** Options Chain OI data (requires live OI fetch via API).
 6. **Entry Conditions:** Price hits a strike with > 2x the OI of surrounding strikes and prints a 5-min rejection candle.
 7. **Exit Conditions:** Price consolidates > 15 mins at the strike without dropping.
 8. **CALL/PUT Logic:** Hit Call OI Wall (Resistance) = PUT. Hit Put OI Wall (Support) = CALL.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** High volume climax on the touch.
13. **Candle Confirmation:** Pin Bar.
14. **Stop-loss:** Strike Price +/- 30 index points.
15. **Profit-booking:** VWAP.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1-2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 49: SENSEX_TEMA_ALIGN_49 (Triple EMA Alignment)

 1. **Name/ID:** SENSEX_TEMA_ALIGN_49
 2. **Trading hypothesis:** When the 8, 13, and 21 EMAs are perfectly stacked and fanned out, institutional trend-following is at its strongest.
 3. **Best Market Conditions:** Unidirectional trending markets.
 4. **Avoid in:** Entangled EMAs.
 5. **Indicators:** 8 EMA, 13 EMA, 21 EMA.
 6. **Entry Conditions:** EMAs are stacked (8 > 13 > 21). Price pulls back into the space between 8 and 13 EMA, then closes back in trend direction.
 7. **Exit Conditions:** 8 EMA crosses below 13 EMA.
 8. **CALL/PUT Logic:** Bullish stack = CALL; Bearish stack = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹450.
12. **Volume Confirmation:** Not strictly required, momentum-based.
13. **Candle Confirmation:** Strong close validating the bounce.
14. **Stop-loss:** Close below 21 EMA.
15. **Profit-booking:** 1:2 RR.
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Yes, on every valid pullback.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 50: SENSEX_TOD_REV_50 (European Open Reversal)

 1. **Name/ID:** SENSEX_TOD_REV_50
 2. **Trading hypothesis:** The European market open (~12:30 PM to 1:00 PM IST) injects fresh liquidity, often reversing the morning trend.
 3. **Best Market Conditions:** Exhausted morning trends that have hit ADR (Average Daily Range) limits by 12:30 PM.
 4. **Avoid in:** Dead flat mornings.
 5. **Indicators:** Time of Day (12:30 - 13:15 IST), ADR, RSI.
 6. **Entry Conditions:** Between 12:30 and 13:15, if RSI is > 70 or < 30 and a major reversal pattern (Engulfing/Pin Bar) forms on the 5-min chart.
 7. **Exit Conditions:** Price reaches VWAP.
 8. **CALL/PUT Logic:** Down morning + Reversal = CALL; Up morning + Reversal = PUT.
 9. **Strike Selection:** Slightly OTM (Delta ~0.45).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹300.
12. **Volume Confirmation:** Spike in volume coinciding with the European open window.
13. **Candle Confirmation:** Clear reversal pattern.
14. **Stop-loss:** Swing high/low of the reversal.
15. **Profit-booking:** VWAP.
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:00 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 51: SENSEX_EOD_IMB_51 (End of Day Imbalance Scalp)

 1. **Name/ID:** SENSEX_EOD_IMB_51
 2. **Trading hypothesis:** The final 15 minutes of trading feature aggressive institutional rebalancing. Breaking the 3:00 PM candle dictates the final move.
 3. **Best Market Conditions:** High momentum days where institutions are forced to cover.
 4. **Avoid in:** Range-bound, low-volume days.
 5. **Indicators:** 15:00 PM 5-min candle.
 6. **Entry Conditions:** 15:05 PM candle breaks the high/low of the 15:00 PM candle.
 7. **Exit Conditions:** Momentum stops or 15:25 PM hard exit.
 8. **CALL/PUT Logic:** Break 15:00 High = CALL; Break 15:00 Low = PUT.
 9. **Strike Selection:** ITM (Delta ~0.60).
10. **Expiry Selection:** Next weekly (to avoid massive same-day decay/spread issues in the last 15 mins).
11. **Premium Selection:** ₹300 - ₹500.
12. **Volume Confirmation:** Expanding volume at 15:00.
13. **Candle Confirmation:** Immediate break and close.
14. **Stop-loss:** Midpoint of the 15:00 candle.
15. **Profit-booking:** Trail aggressively.
16. **Trailing SL:** 1-min previous candle low/high.
17. **Time-based exit:** 15:25 PM (Auto-square off).
18. **Max holding duration:** 20 mins.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 5% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 52: SENSEX_DBL_LIQ_52 (Double Bottom/Top Liquidity Grab)

 1. **Name/ID:** SENSEX_DBL_LIQ_52
 2. **Trading hypothesis:** A "W" or "M" pattern where the second leg slightly pierces the first leg grabs liquidity before reversing.
 3. **Best Market Conditions:** Broad structural ranges.
 4. **Avoid in:** Strong unidirectional trends.
 5. **Indicators:** ZigZag / Price Action.
 6. **Entry Conditions:** Price forms a double bottom, but the right leg drops slightly below the left leg (sweep), immediately followed by a bullish engulfing candle.
 7. **Exit Conditions:** Reaches the neckline of the pattern.
 8. **CALL/PUT Logic:** Sweep of Double Bottom = CALL; Sweep of Double Top = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Highest volume must be on the sweeping candle (absorption).
13. **Candle Confirmation:** Engulfing candle closing back inside the range.
14. **Stop-loss:** The extreme of the sweep wick.
15. **Profit-booking:** Neckline.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 53: SENSEX_TTM_MOM_53 (Squeeze Momentum Ignition)

 1. **Name/ID:** SENSEX_TTM_MOM_53
 2. **Trading hypothesis:** Volatility squeezes combined with a shift in momentum histogram lead to explosive multi-bar runs.
 3. **Best Market Conditions:** Sideways transitioning to trend.
 4. **Avoid in:** Already over-extended trends.
 5. **Indicators:** Squeeze Indicator (e.g., TTM Squeeze - BB/Keltner math), Momentum Histogram.
 6. **Entry Conditions:** Squeeze fires (dots turn green/off) AND histogram shifts from negative to positive (or vice versa) simultaneously.
 7. **Exit Conditions:** Histogram prints a lighter color (momentum slowing).
 8. **CALL/PUT Logic:** Hist positive = CALL; Hist negative = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** Breakout volume required.
13. **Candle Confirmation:** Close outside Keltner Channel.
14. **Stop-loss:** 20 SMA.
15. **Profit-booking:** Discretionary based on histogram.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1-2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 54: SENSEX_FLAG_BRK_54 (Flag/Pennant Continuation)

 1. **Name/ID:** SENSEX_FLAG_BRK_54
 2. **Trading hypothesis:** Flags represent controlled profit-taking by institutions before the next leg in the direction of the trend.
 3. **Best Market Conditions:** Strong momentum pole in the morning.
 4. **Avoid in:** Flags that retrace > 50% of the pole (invalidates the pattern).
 5. **Indicators:** Price Action (Trendlines), Volume.
 6. **Entry Conditions:** Price breaks the upper/lower descending trendline of the flag with expanding volume.
 7. **Exit Conditions:** Close back inside the flag pattern.
 8. **CALL/PUT Logic:** Bull flag break = CALL; Bear flag break = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹400.
12. **Volume Confirmation:** Volume MUST contract during the flag and expand on the breakout.
13. **Candle Confirmation:** Clear close outside the trendline.
14. **Stop-loss:** Opposite side of the flag.
15. **Profit-booking:** 100% projection of the flagpole.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1-2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 55: SENSEX_MTF_ALIGN_55 (Multi-Timeframe Alignment)

 1. **Name/ID:** SENSEX_MTF_ALIGN_55
 2. **Trading hypothesis:** Trades taken in the direction of the 15-minute and 60-minute trends have the highest probability of follow-through.
 3. **Best Market Conditions:** Macro trending days.
 4. **Avoid in:** MTF conflict (15m is bullish, 60m is bearish).
 5. **Indicators:** 9 EMA on 5m, 15m, and 60m.
 6. **Entry Conditions:** 60m > 9EMA, 15m > 9EMA. Wait for 5m to pull back below its 9EMA, then enter when a 5m candle closes back *above* the 5m 9EMA.
 7. **Exit Conditions:** 15m candle closes below its 15m 9EMA.
 8. **CALL/PUT Logic:** All MTFs bullish = CALL; All MTFs bearish = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹450.
12. **Volume Confirmation:** Standard.
13. **Candle Confirmation:** Engulfing on 5m chart.
14. **Stop-loss:** Swing low of the 5m pullback.
15. **Profit-booking:** 1:3 RR.
16. **Trailing SL:** 21 EMA on 5m chart.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2-3 hours.
19. **Re-entry:** Yes.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 56: SENSEX_FIB_CONFL_56 (Fibonacci 38.2 & 50 EMA Confluence)

 1. **Name/ID:** SENSEX_FIB_CONFL_56
 2. **Trading hypothesis:** The confluence of a 38.2% Fibonacci retracement and the 50 EMA acts as an institutional reload zone.
 3. **Best Market Conditions:** Stable, grinding trends.
 4. **Avoid in:** Parabolic blow-off tops.
 5. **Indicators:** Fib Retracement, 50 EMA.
 6. **Entry Conditions:** Price pulls back, simultaneously touching the 38.2% Fib level and the 50 EMA. Reversal candle forms.
 7. **Exit Conditions:** Close below the 50.0% Fib level.
 8. **CALL/PUT Logic:** Uptrend pullback = CALL.
 9. **Strike Selection:** Slightly ITM (Delta ~0.55).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹450.
12. **Volume Confirmation:** Reversal candle > average volume.
13. **Candle Confirmation:** Pin Bar/Hammer.
14. **Stop-loss:** Just below the 50.0% Fib.
15. **Profit-booking:** 0% Fib level (swing high).
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2-3 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 57: SENSEX_VWAP_PINCH_57 (VWAP Pinch Squeeze)

 1. **Name/ID:** SENSEX_VWAP_PINCH_57
 2. **Trading hypothesis:** When price tightly coils exactly on the VWAP line for an extended period, it is building energy for an explosive break.
 3. **Best Market Conditions:** Mid-day chop leading into 1:30 PM.
 4. **Avoid in:** Expanding volatility.
 5. **Indicators:** VWAP, Bollinger Bands (tightly compressed around VWAP).
 6. **Entry Conditions:** Price chops over VWAP > 6 candles within a 15-point range. Enter on the first strong candle closing completely detached from the VWAP.
 7. **Exit Conditions:** Close back over VWAP.
 8. **CALL/PUT Logic:** Break upside = CALL; Break downside = PUT.
 9. **Strike Selection:** Slightly OTM (Delta ~0.45).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹300.
12. **Volume Confirmation:** Breakout RVOL > 2.0.
13. **Candle Confirmation:** Clean Marubozu detachment.
14. **Stop-loss:** Opposite side of the VWAP pinch zone.
15. **Profit-booking:** 1:2.5 RR.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1 hour.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 58: SENSEX_PREM_LOW_58 (Pre-Market Low Sweep)

 1. **Name/ID:** SENSEX_PREM_LOW_58
 2. **Trading hypothesis:** Sweeping the implied pre-market low (derived from SGX/GIFT Nifty correlations at open) traps early bears.
 3. **Best Market Conditions:** Gap down opens.
 4. **Avoid in:** Gap downs with continuous massive selling volume.
 5. **Indicators:** Day Low (first 5 mins).
 6. **Entry Conditions:** Price breaks the Day Low between 9:20 - 9:45, fails to sustain for > 2 candles, and closes back above.
 7. **Exit Conditions:** Drops back and closes below the new low.
 8. **CALL/PUT Logic:** Sweep of Low = CALL.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹400.
12. **Volume Confirmation:** High volume absorption.
13. **Candle Confirmation:** Bullish engulfing.
14. **Stop-loss:** Low of the sweep wick.
15. **Profit-booking:** VWAP.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 11:30 AM.
18. **Max holding duration:** 90 mins.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 59: SENSEX_GAP_EXH_59 (Exhaustion Gap Fade)

 1. **Name/ID:** SENSEX_GAP_EXH_59
 2. **Trading hypothesis:** A late-stage gap in the direction of an already extended trend often signals exhaustion and a sharp reversion.
 3. **Best Market Conditions:** Gap up after 3+ consecutive bullish days.
 4. **Avoid in:** Breakaway gaps at the start of a new trend.
 5. **Indicators:** Daily chart context, Intraday VWAP.
 6. **Entry Conditions:** Gap up > 0.5% after an extended run. Price fails to make a new high in the first 15 mins and drops below VWAP.
 7. **Exit Conditions:** Price reclaims VWAP.
 8. **CALL/PUT Logic:** Gap up exhaustion = PUT.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** Opening 15-min volume is lower than the previous day's open.
13. **Candle Confirmation:** Bearish close below VWAP.
14. **Stop-loss:** High of the day.
15. **Profit-booking:** Previous day close (gap fill).
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2-3 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*

## Strategy 60: SENSEX_MACRO_DIV_60 (Nifty/Sensex Divergence)

 1. **Name/ID:** SENSEX_MACRO_DIV_60
 2. **Trading hypothesis:** When Nifty makes a new high but Sensex fails to confirm (due to banking/IT specific weakness), a mean-reversion is imminent.
 3. **Best Market Conditions:** Macro turning points.
 4. **Avoid in:** Heavily correlated unidirectional days.
 5. **Indicators:** Nifty 50 Spot, Sensex Spot.
 6. **Entry Conditions:** Nifty prints a new High of Day, but Sensex forms a lower high and prints a bearish reversal candle.
 7. **Exit Conditions:** Sensex breaks its high.
 8. **CALL/PUT Logic:** Sensex lower high = PUT; Sensex higher low = CALL.
 9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Nifty breakout volume is low.
13. **Candle Confirmation:** Reversal on Sensex chart.
14. **Stop-loss:** High of the Sensex reversal candle.
15. **Profit-booking:** VWAP.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *\[Requires historical backtest\]*