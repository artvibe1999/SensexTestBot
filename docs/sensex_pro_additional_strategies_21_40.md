# SENSEX PRO – Strategies 21 to 40

*Note: As with the previous framework, performance metrics for all strategies below must be calculated by running these precise rules through a quantitative backtesting engine using your historical SENSEX options dataset.*

## Strategy 21: SENSEX_VWAP_DEV_21 (VWAP Standard Deviation Reversion)

 1. **Name/ID:** SENSEX_VWAP_DEV_21

 2. **Trading hypothesis:** Price deviating too far from the VWAP (mean) in low-momentum markets will eventually revert to the mean.

 3. **Best Market Conditions:** Sideways or broad-range markets.

 4. **Avoid in:** High momentum gap-and-go days (ADX > 30).

 5. **Indicators:** VWAP with Upper/Lower Bands (Standard Deviation 2.0).

 6. **Entry Conditions:** Price touches/exceeds the 2.0 SD VWAP band and forms a reversal candle (pin bar or engulfing).

 7. **Exit Conditions:** Price reaches the core VWAP line.

 8. **CALL/PUT Logic:** Reject Lower Band = CALL; Reject Upper Band = PUT.

 9. **Strike Selection:** ATM (Delta \~0.50).

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹150 - ₹350.

12. **Volume Confirmation:** Volume must spike on the touch of the band (climax) and drop on the reversal candle.

13. **Candle Confirmation:** Pin bar wick must be >50% of the candle size.

14. **Stop-loss:** High/Low of the rejection wick.

15. **Profit-booking:** 100% at VWAP line.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 15:00 PM.

18. **Max holding duration:** 90 minutes.

19. **Re-entry:** Allowed if price re-tests the band.

20. **Risk/Capital:** Max 10% capital, 2% risk.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 22: SENSEX_OPEN_DRV_22 (Institutional Open Drive)

 1. **Name/ID:** SENSEX_OPEN_DRV_22

 2. **Trading hypothesis:** A strong, unidirectional move from the first tick signifies heavy institutional accumulation/distribution.

 3. **Best Market Conditions:** Gap ups/downs above previous day's high/low.

 4. **Avoid in:** Opens inside the previous day's value area.

 5. **Indicators:** Opening 5-min candle, VWAP.

 6. **Entry Conditions:** First 5-min candle is a strong Marubozu (no wicks) breaking previous day high/low. Enter on the open of the 2nd candle.

 7. **Exit Conditions:** Price closes below/above the VWAP.

 8. **CALL/PUT Logic:** Bullish Marubozu above PDH = CALL; Bearish Marubozu below PDL = PUT.

 9. **Strike Selection:** Slightly ITM (Delta \~0.60) to capture rapid intrinsic value.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹300 - ₹500.

12. **Volume Confirmation:** First candle volume > 3x the 20-period average.

13. **Candle Confirmation:** Body must be >85% of the total candle range.

14. **Stop-loss:** Midpoint of the first 5-min candle.

15. **Profit-booking:** 1:2.5 Risk-to-Reward.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 11:30 AM (Drive usually exhausts here).

18. **Max holding duration:** 2 hours.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital, 2% risk.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 23: SENSEX_PDC_BNC_23 (Previous Day Close Bounce)

 1. **Name/ID:** SENSEX_PDC_BNC_23

 2. **Trading hypothesis:** The previous day's closing price acts as a psychological and institutional liquidity zone.

 3. **Best Market Conditions:** Moderate gap open that fades back to the PDC.

 4. **Avoid in:** Flat opens where PDC is immediately chopped through.

 5. **Indicators:** Previous Day Close (PDC) level.

 6. **Entry Conditions:** Price drops/rises to the PDC level and forms a 5-min rejection candle.

 7. **Exit Conditions:** Fails to make a new high/low after 3 candles.

 8. **CALL/PUT Logic:** Bounce off PDC upwards = CALL; Reject off PDC downwards = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹350.

12. **Volume Confirmation:** Average volume on pullback, high volume on bounce.

13. **Candle Confirmation:** Hammer or Bullish Engulfing at PDC.

14. **Stop-loss:** PDC +/- 15 index points.

15. **Profit-booking:** Day's High/Low.

16. **Trailing SL:** 5-min swing low/high.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** Yes, once.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 24: SENSEX_ORB_FAIL_24 (ORB Fade / Trap)

 1. **Name/ID:** SENSEX_ORB_FAIL_24

 2. **Trading hypothesis:** Failed opening range breakouts trap retail momentum traders, providing fuel for a sharp move in the opposite direction.

 3. **Best Market Conditions:** Low RVOL at the open.

 4. **Avoid in:** Gap and go days with high momentum.

 5. **Indicators:** 15-min Opening Range High/Low.

 6. **Entry Conditions:** Price breaks ORB, immediately rejects (within 1-2 candles), and closes back inside the ORB.

 7. **Exit Conditions:** Price reaches the opposite side of the ORB.

 8. **CALL/PUT Logic:** Failed ORB High = PUT; Failed ORB Low = CALL.

 9. **Strike Selection:** Slightly OTM (Delta \~0.40) for rapid gamma expansion.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹150 - ₹300.

12. **Volume Confirmation:** Breakout has low volume; reversal candle has high volume.

13. **Candle Confirmation:** Strong close inside the range.

14. **Stop-loss:** The extreme of the false breakout wick.

15. **Profit-booking:** Opposite ORB boundary.

16. **Trailing SL:** VWAP.

17. **Time-based exit:** 14:00 PM.

18. **Max holding duration:** 1-2 hours.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 25: SENSEX_ATR_EXP_25 (ATR Expansion Continuation)

 1. **Name/ID:** SENSEX_ATR_EXP_25

 2. **Trading hypothesis:** Sudden expansions in Average True Range signal the start of an institutional trend wave.

 3. **Best Market Conditions:** Transitioning from Sideways to Trending.

 4. **Avoid in:** Late afternoon (post 2:45 PM).

 5. **Indicators:** ATR (14), 21 EMA.

 6. **Entry Conditions:** ATR(14) crosses above its 10-period SMA, and a strong trend candle closes above/below 21 EMA.

 7. **Exit Conditions:** ATR(14) crosses back below its SMA.

 8. **CALL/PUT Logic:** Bullish close = CALL; Bearish close = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹250 - ₹400.

12. **Volume Confirmation:** Expanding volume aligning with ATR expansion.

13. **Candle Confirmation:** Strong close in trend direction.

14. **Stop-loss:** 21 EMA.

15. **Profit-booking:** 1:2 Risk-to-Reward.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** Yes.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 26: SENSEX_SESSION_T_26 (Lunch Hour Fade)

 1. **Name/ID:** SENSEX_SESSION_T_26

 2. **Trading hypothesis:** Low volume moves between 12:00 PM and 1:30 PM are often faded by institutions returning from the lunch session.

 3. **Best Market Conditions:** Clear trend established in the morning, drifting in the opposite direction during lunch.

 4. **Avoid in:** Flat morning sessions.

 5. **Indicators:** VWAP, MACD.

 6. **Entry Conditions:** Post 1:30 PM, price breaks the 12:00 PM - 1:30 PM consolidation range in the direction of the morning trend.

 7. **Exit Conditions:** MACD crossover against the trade.

 8. **CALL/PUT Logic:** Morning uptrend + lunch dip breakout = CALL.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹350.

12. **Volume Confirmation:** Breakout post 1:30 PM must have higher volume than the lunch hour average.

13. **Candle Confirmation:** Clean breakout of the lunch range high/low.

14. **Stop-loss:** Opposite side of the lunch range.

15. **Profit-booking:** 1:2 RR.

16. **Trailing SL:** VWAP.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 27: SENSEX_LIQ_GRAB_27 (Swing Low/High Liquidity Sweep)

 1. **Name/ID:** SENSEX_LIQ_GRAB_27

 2. **Trading hypothesis:** Smart money triggers retail stops just below major swing lows or above swing highs to accumulate positions.

 3. **Best Market Conditions:** Trending markets experiencing deep pullbacks.

 4. **Avoid in:** Extremely high VIX environments.

 5. **Indicators:** ZigZag (to identify swings), Price Action.

 6. **Entry Conditions:** Price drops below a clear swing low, stays below for < 2 candles, and closes firmly back above the swing low.

 7. **Exit Conditions:** Price reaches the most recent lower high / higher low.

 8. **CALL/PUT Logic:** Sweep below swing low = CALL; Sweep above swing high = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹400.

12. **Volume Confirmation:** High volume on the sweep candle indicating absorption.

13. **Candle Confirmation:** Hammer or Bullish Engulfing closing above the swing level.

14. **Stop-loss:** Absolute low/high of the sweep wick.

15. **Profit-booking:** Next major structural pivot.

16. **Trailing SL:** 5-min previous candle low.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 28: SENSEX_VWAP_PIN_28 (Expiry Day VWAP Pinning)

 1. **Name/ID:** SENSEX_VWAP_PIN_28

 2. **Trading hypothesis:** On expiry days, option writers often manipulate the index to close near the VWAP to decay maximum premium.

 3. **Best Market Conditions:** Expiry days (0DTE), 2:00 PM onwards, price is far from VWAP.

 4. **Avoid in:** Unidirectional trending expiry days.

 5. **Indicators:** VWAP.

 6. **Entry Conditions:** At 2:00 PM, if price is > 0.5% away from VWAP, and ADX is declining, enter towards VWAP.

 7. **Exit Conditions:** Price touches VWAP or 15:20 PM.

 8. **CALL/PUT Logic:** Price below VWAP = CALL; Price above VWAP = PUT.

 9. **Strike Selection:** ITM (Delta \~0.70) to avoid theta decay.

10. **Expiry Selection:** CURRENT DAY (0DTE).

11. **Premium Selection:** ₹100 - ₹200.

12. **Volume Confirmation:** Declining volume indicating trend exhaustion.

13. **Candle Confirmation:** First reversal candle closing against the trend.

14. **Stop-loss:** Swing high/low of the day.

15. **Profit-booking:** VWAP line.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 15:20 PM.

18. **Max holding duration:** 80 minutes.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 29: SENSEX_VIX_CRUSH_29 (VIX Contraction Short-Covering)

 1. **Name/ID:** SENSEX_VIX_CRUSH_29

 2. **Trading hypothesis:** A sudden drop in India VIX during a down-trend often triggers short-covering rallies in SENSEX.

 3. **Best Market Conditions:** Bearish morning transitioning into sideways mid-day.

 4. **Avoid in:** Rising VIX environments.

 5. **Indicators:** India VIX, SENSEX VWAP.

 6. **Entry Conditions:** India VIX drops > 3% intraday; SENSEX 5-min candle crosses above VWAP.

 7. **Exit Conditions:** SENSEX price closes below 21 EMA.

 8. **CALL/PUT Logic:** ALWAYS CALL (Strategy specifically targets short-covering).

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹350.

12. **Volume Confirmation:** Rising volume on the SENSEX VWAP crossover.

13. **Candle Confirmation:** Strong bullish close.

14. **Stop-loss:** Swing low of the day.

15. **Profit-booking:** 1:2.5 RR.

16. **Trailing SL:** 21 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** Rest of day.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 30: SENSEX_TREND_EXH_30 (Parabolic Exhaustion Fade)

 1. **Name/ID:** SENSEX_TREND_EXH_30

 2. **Trading hypothesis:** Parabolic, uninterrupted moves of 4+ large candles often exhaust themselves and sharply retrace.

 3. **Best Market Conditions:** News-driven spikes or late-day panics.

 4. **Avoid in:** Slow, grinding trends.

 5. **Indicators:** RSI (14), Bollinger Bands (20,2).

 6. **Entry Conditions:** 4 consecutive 5-min candles of the same color, RSI > 85 or < 15, and price completely outside the Bollinger Band.

 7. **Exit Conditions:** Price touches the 20 SMA (Middle BB).

 8. **CALL/PUT Logic:** RSI < 15 = CALL; RSI > 85 = PUT.

 9. **Strike Selection:** Slightly OTM (Delta \~0.40).

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹150 - ₹300.

12. **Volume Confirmation:** Volume spike on the 4th candle (climax).

13. **Candle Confirmation:** A reversal Doji or Pin Bar forming completely outside the BB.

14. **Stop-loss:** High/Low of the climax Doji.

15. **Profit-booking:** 20 SMA.

16. **Trailing SL:** None, strict target.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 45 minutes.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 5% capital (High risk mean-reversion).

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 31: SENSEX_GAP_GO_31 (Unfilled Gap Continuation)

 1. **Name/ID:** SENSEX_GAP_GO_31

 2. **Trading hypothesis:** Gaps that are not filled within the first hour act as strong institutional support/resistance for a trend day.

 3. **Best Market Conditions:** Large gap (>0.6%) with strong underlying global cues.

 4. **Avoid in:** Gaps inside the previous day's range.

 5. **Indicators:** First 60-min High/Low, VWAP.

 6. **Entry Conditions:** Post 10:15 AM, price forms a pullback to VWAP but remains outside the gap zone, then breaks the 60-min High/Low.

 7. **Exit Conditions:** Price closes inside the gap zone.

 8. **CALL/PUT Logic:** Gap up + Break 60-min High = CALL; Gap down + Break 60-min Low = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹250 - ₹400.

12. **Volume Confirmation:** Breakout volume > pullback volume.

13. **Candle Confirmation:** Strong close outside the 60-min range.

14. **Stop-loss:** VWAP.

15. **Profit-booking:** 1:3 RR.

16. **Trailing SL:** 21 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** Rest of day.

19. **Re-entry:** Yes, on further VWAP pullbacks.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 32: SENSEX_RVOL_BRK_32 (Relative Volume Micro-Consolidation Breakout)

 1. **Name/ID:** SENSEX_RVOL_BRK_32

 2. **Trading hypothesis:** A sudden volume spike during a tight, low-volume consolidation precedes a sharp directional move.

 3. **Best Market Conditions:** Mid-day sessions (11:00 AM - 1:00 PM).

 4. **Avoid in:** High volatility sessions.

 5. **Indicators:** Relative Volume (RVOL), 9 EMA.

 6. **Entry Conditions:** Price consolidates in a <30 point range for 4+ candles. Next candle breaks the range with RVOL > 2.5.

 7. **Exit Conditions:** Close below 9 EMA.

 8. **CALL/PUT Logic:** Break range high = CALL; Break range low = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹150 - ₹300.

12. **Volume Confirmation:** RVOL > 2.5 is mandatory.

13. **Candle Confirmation:** Candle body > 70% of total range.

14. **Stop-loss:** Mid-point of the breakout candle.

15. **Profit-booking:** 1:2 RR.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 1 hour.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 33: SENSEX_EMA_TWIST_33 (EMA Ribbon Twist)

 1. **Name/ID:** SENSEX_EMA_TWIST_33

 2. **Trading hypothesis:** When short-term EMAs converge tightly and then expand, it signals a regime shift from sideways to trending.

 3. **Best Market Conditions:** Transition phases.

 4. **Avoid in:** Established trends (EMAs already wide apart).

 5. **Indicators:** 5 EMA, 13 EMA, 21 EMA.

 6. **Entry Conditions:** All three EMAs converge within a 10-point spread. Price breaks out, and the 5 crosses 13 and 21 sharply.

 7. **Exit Conditions:** 5 EMA crosses back over the 13 EMA.

 8. **CALL/PUT Logic:** 5 crosses above 13/21 = CALL; 5 crosses below = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹400.

12. **Volume Confirmation:** Breakout volume > 1.5x average.

13. **Candle Confirmation:** Close outside the EMA cluster.

14. **Stop-loss:** 21 EMA.

15. **Profit-booking:** 1:2.5 RR.

16. **Trailing SL:** 13 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 34: SENSEX_OPEN_REJ_34 (First Tick Rejection)

 1. **Name/ID:** SENSEX_OPEN_REJ_34

 2. **Trading hypothesis:** If the first 1-minute candle pushes hard into a major daily resistance/support and immediately rejects, the high/low of the day is often set.

 3. **Best Market Conditions:** Pre-market gap into major S/R level.

 4. **Avoid in:** Openings in the middle of nowhere (no key levels nearby).

 5. **Indicators:** Daily S/R levels, 1-min chart.

 6. **Entry Conditions:** 1-min candle hits major daily S/R and forms a long rejection wick (>60% of candle). Enter on the break of the 1-min candle low/high.

 7. **Exit Conditions:** Price crosses the 9 EMA on the 5-min chart.

 8. **CALL/PUT Logic:** Rejection at Support = CALL; Rejection at Resistance = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹250 - ₹400.

12. **Volume Confirmation:** Extremely high opening volume.

13. **Candle Confirmation:** 1-min Pin Bar.

14. **Stop-loss:** The absolute high/low of the 1-min wick.

15. **Profit-booking:** VWAP level.

16. **Trailing SL:** 9 EMA (5-min chart).

17. **Time-based exit:** 11:00 AM.

18. **Max holding duration:** 90 minutes.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 35: SENSEX_FRACTAL_BRK_35 (Fractal Breakout)

 1. **Name/ID:** SENSEX_FRACTAL_BRK_35

 2. **Trading hypothesis:** Breaking a 5-bar Williams Fractal signals the exhaustion of a pullback and the resumption of the macro trend.

 3. **Best Market Conditions:** Unidirectional markets with healthy pullbacks.

 4. **Avoid in:** Choppy markets.

 5. **Indicators:** Williams Fractals, 21 EMA.

 6. **Entry Conditions:** Price in an uptrend (above 21 EMA) pulls back to form an Up Fractal, then a 5-min candle breaks that Fractal High.

 7. **Exit Conditions:** Price closes below 21 EMA.

 8. **CALL/PUT Logic:** Break Up Fractal High in Uptrend = CALL; Break Down Fractal Low in Downtrend = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹400.

12. **Volume Confirmation:** Average volume.

13. **Candle Confirmation:** Close beyond the fractal extreme.

14. **Stop-loss:** The most recent opposite fractal.

15. **Profit-booking:** 1:2 RR.

16. **Trailing SL:** 21 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** Yes, on next fractal break.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 36: SENSEX_VOL_DRY_36 (Volume Dry-Up Pullback)

 1. **Name/ID:** SENSEX_VOL_DRY_36

 2. **Trading hypothesis:** Pullbacks that exhibit steadily decreasing volume indicate a lack of institutional interest in the counter-trend move.

 3. **Best Market Conditions:** Strong morning trend followed by a slow mid-day drift.

 4. **Avoid in:** Pullbacks with expanding volume.

 5. **Indicators:** Volume, VWAP.

 6. **Entry Conditions:** Price pulls back for 3-5 candles towards VWAP. Volume strictly decreases on every pullback candle. Reversal candle forms at VWAP.

 7. **Exit Conditions:** Close below VWAP.

 8. **CALL/PUT Logic:** Bull trend + low vol pullback to VWAP = CALL.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹350.

12. **Volume Confirmation:** Reversal candle volume must break the dry-up sequence (be higher than the last 3 candles).

13. **Candle Confirmation:** Bullish/Bearish engulfing.

14. **Stop-loss:** Close below VWAP.

15. **Profit-booking:** Previous Swing High/Low.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** Yes.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 37: SENSEX_TICK_DIV_37 (Internal Breadth Divergence)

 1. **Name/ID:** SENSEX_TICK_DIV_37

 2. **Trading hypothesis:** If SENSEX makes a new high but broader market breadth (advance/decline) is falling, it is a trap. *(Note: Requires underlying constituent data)*

 3. **Best Market Conditions:** Late stages of a prolonged intraday trend.

 4. **Avoid in:** First hour of trading.

 5. **Indicators:** SENSEX Spot, Advance/Decline Ratio (Custom data feed).

 6. **Entry Conditions:** SENSEX hits a new High of Day, but A/D ratio is making lower highs. Enter on first bearish 5-min close.

 7. **Exit Conditions:** A/D ratio crosses back above 1.0.

 8. **CALL/PUT Logic:** Price High + A/D Low = PUT; Price Low + A/D High = CALL.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹200 - ₹400.

12. **Volume Confirmation:** Breakout candle volume is weak.

13. **Candle Confirmation:** Bearish Engulfing / Pin bar.

14. **Stop-loss:** High of the day + 10 points.

15. **Profit-booking:** VWAP.

16. **Trailing SL:** 21 EMA.

17. **Time-based exit:** 15:00 PM.

18. **Max holding duration:** 2 hours.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 38: SENSEX_NR7_BRK_38 (NR7 Contraction Breakout)

 1. **Name/ID:** SENSEX_NR7_BRK_38

 2. **Trading hypothesis:** The Narrowest Range of the last 7 candles (NR7) signals severe volatility compression, leading to an explosive breakout.

 3. **Best Market Conditions:** Dead/sideways markets mid-session.

 4. **Avoid in:** High volatility environments.

 5. **Indicators:** Custom NR7 pattern identifier.

 6. **Entry Conditions:** Identify NR7 candle. Enter when price breaks the High/Low of the NR7 candle.

 7. **Exit Conditions:** Opposite side of the NR7 candle is broken.

 8. **CALL/PUT Logic:** Break NR7 High = CALL; Break NR7 Low = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹150 - ₹300.

12. **Volume Confirmation:** Breakout volume > 1.5x average.

13. **Candle Confirmation:** Strong close outside the NR7 range.

14. **Stop-loss:** Opposite extreme of the NR7 candle.

15. **Profit-booking:** 1:3 RR.

16. **Trailing SL:** 9 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** 1-2 hours.

19. **Re-entry:** Yes, on next NR7.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 39: SENSEX_GAMMA_SQR_39 (Post-2 PM Gamma Squeeze)

 1. **Name/ID:** SENSEX_GAMMA_SQR_39

 2. **Trading hypothesis:** On expiry days, a break of a major support/resistance after 2:00 PM forces massive short-covering from option writers, driving gamma vertical.

 3. **Best Market Conditions:** Expiry day, price coiled near major S/R level.

 4. **Avoid in:** Non-expiry days.

 5. **Indicators:** Open Interest (OI) concentrations, Day High/Low.

 6. **Entry Conditions:** Price breaks a major OI concentration strike (e.g., 75,000 CE writers) post 2:00 PM.

 7. **Exit Conditions:** Momentum stops (first inside bar).

 8. **CALL/PUT Logic:** Break heavy Call OI = CALL (squeeze); Break heavy Put OI = PUT.

 9. **Strike Selection:** ATM (Delta \~0.50).

10. **Expiry Selection:** Current Day (0DTE).

11. **Premium Selection:** ₹50 - ₹150.

12. **Volume Confirmation:** Exploding volume on the breakout.

13. **Candle Confirmation:** Rapid Marubozu candle.

14. **Stop-loss:** -30% of premium.

15. **Profit-booking:** 1:3 RR.

16. **Trailing SL:** Previous 3-min candle low/high.

17. **Time-based exit:** 15:25 PM.

18. **Max holding duration:** 30 minutes.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 5% capital.

21. **Performance:** *\[Requires historical backtest\]*

## Strategy 40: SENSEX_GAP_FILL_REV_40 (Gap Fill Reversal)

 1. **Name/ID:** SENSEX_GAP_FILL_REV_40

 2. **Trading hypothesis:** Once an opening gap is completely filled, the primary institutional daily trend resumes in the original direction of the gap.

 3. **Best Market Conditions:** Gap up/down that slowly bleeds out over the morning to fill.

 4. **Avoid in:** Rapid, high-volume gap fills (momentum is too strong to fade).

 5. **Indicators:** Previous Day Close (PDC).

 6. **Entry Conditions:** Price drops/rises to exactly touch the PDC (filling the gap), and immediately prints a reversal candle.

 7. **Exit Conditions:** Closes beyond the PDC by > 20 points.

 8. **CALL/PUT Logic:** Gap up, fills to PDC, bounces = CALL. Gap down, fills to PDC, rejects = PUT.

 9. **Strike Selection:** ATM.

10. **Expiry Selection:** Current weekly.

11. **Premium Selection:** ₹250 - ₹350.

12. **Volume Confirmation:** Volume must spike at the exact moment the gap is filled (absorption).

13. **Candle Confirmation:** Pin Bar or Doji at the PDC.

14. **Stop-loss:** PDC level +/- 25 points.

15. **Profit-booking:** VWAP or Day High/Low.

16. **Trailing SL:** 21 EMA.

17. **Time-based exit:** 15:15 PM.

18. **Max holding duration:** Rest of day.

19. **Re-entry:** No.

20. **Risk/Capital:** Max 10% capital.

21. **Performance:** *\[Requires historical backtest\]*