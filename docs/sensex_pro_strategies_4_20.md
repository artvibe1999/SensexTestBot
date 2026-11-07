# SENSEX PRO – Strategies 4 to 20

*Note: Performance metrics (Total trades, Win rate, Max drawdown, etc.) for all strategies below must be populated by running these frameworks through a quantitative backtesting engine using historical SENSEX options data.*

## Strategy 4: SENSEX_TREND_04 (EMA & ADX Trend Continuation)
1. **Name/ID:** SENSEX_TREND_04
2. **Hypothesis:** Strong trends continue after minor pullbacks to short-term moving averages.
3. **Best Conditions:** Unidirectional Bullish/Bearish (ADX > 30).
4. **Avoid in:** ADX < 20, Sideways markets.
5. **Indicators:** 9 EMA, 21 EMA, ADX(14).
6. **Entry Conditions:** Price pulls back to touch 9 EMA; next candle closes in the direction of the trend (9 EMA > 21 EMA for CALL).
7. **Exit Conditions:** Price closes on the wrong side of the 21 EMA.
8. **CALL/PUT Logic:** Uptrend pullback = CALL; Downtrend pullback = PUT.
9. **Strike Selection:** ATM (Delta ~0.50).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Pullback volume must be < average; entry candle volume > average.
13. **Candle Confirmation:** Entry candle must engulf the previous pullback candle.
14. **Stop-loss:** Close below 21 EMA.
15. **Profit-booking:** 1:2 Risk-to-Reward.
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Allowed on next pullback.
20. **Risk/Capital:** Max 10% capital, 2% risk limit.
21. **Performance:** *[Requires historical backtest]*

## Strategy 5: SENSEX_REV_05 (RSI Divergence at Pivot)
1. **Name/ID:** SENSEX_REV_05
2. **Hypothesis:** Momentum divergence at key support/resistance signals a high-probability reversal.
3. **Best Conditions:** Maturing trends, approaching daily R2/S2.
4. **Avoid in:** First 45 mins of open (Opening momentum).
5. **Indicators:** RSI(14), Standard Pivot Points.
6. **Entry Conditions:** Price makes higher high at R1/R2, but RSI makes lower high. Bearish rejection candle forms.
7. **Exit Conditions:** RSI crosses 50 line.
8. **CALL/PUT Logic:** Bullish divergence at S1/S2 = CALL; Bearish at R1/R2 = PUT.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹350.
12. **Volume Confirmation:** Reversal candle volume > 1.5x previous candle.
13. **Candle Confirmation:** Pin bar or Engulfing at pivot.
14. **Stop-loss:** Pivot level +/- 10 points.
15. **Profit-booking:** Next pivot level.
16. **Trailing SL:** Trail by prior 5-min swing high/low.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 90 minutes.
19. **Re-entry:** Not allowed for the same pivot.
20. **Risk/Capital:** Max 10% capital, 2% risk limit.
21. **Performance:** *[Requires historical backtest]*

## Strategy 6: SENSEX_BRK_06 (Volatility Squeeze Breakout)
1. **Name/ID:** SENSEX_BRK_06
2. **Hypothesis:** Periods of low volatility (squeeze) precede explosive directional moves.
3. **Best Conditions:** Mid-day doldrums (11:30 AM - 1:00 PM) transitioning to afternoon momentum.
4. **Avoid in:** High volatility, immediately after market open.
5. **Indicators:** Bollinger Bands (20,2), Keltner Channels (20, 1.5).
6. **Entry Conditions:** BB contracts inside KC (Squeeze). Price closes outside BB with RVOL > 2.0.
7. **Exit Conditions:** Price closes back inside the BB moving average (20 SMA).
8. **CALL/PUT Logic:** Close above upper BB = CALL; Close below lower BB = PUT.
9. **Strike Selection:** Slightly OTM (Delta ~0.40).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹100 - ₹250.
12. **Volume Confirmation:** Breakout candle volume must be > 2x 20-period average.
13. **Candle Confirmation:** Marubozu or strong body (>70% of range).
14. **Stop-loss:** 20 SMA.
15. **Profit-booking:** 1:3 Risk-to-Reward.
16. **Trailing SL:** Parabolic SAR (0.02, 0.2).
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Not allowed on same squeeze.
20. **Risk/Capital:** Max 10% capital, 2% risk limit.
21. **Performance:** *[Requires historical backtest]*

## Strategy 7: SENSEX_GAP_07 (Gap Fill Fade)
1. **Name/ID:** SENSEX_GAP_07
2. **Hypothesis:** Gap ups/downs often reverse to fill the gap if opening volume doesn't sustain.
3. **Best Conditions:** Gap > 0.5% against previous prevailing trend.
4. **Avoid in:** Runaway gaps with immediate heavy volume.
5. **Indicators:** Previous Day Close (PDC), VWAP.
6. **Entry Conditions:** 5-min candle shows rejection (wick) moving away from the gap direction, closing below VWAP.
7. **Exit Conditions:** Price reaches PDC (Gap filled).
8. **CALL/PUT Logic:** Gap down, bounce, reject VWAP = PUT (to fill gap); Gap up, reject = CALL.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹400.
12. **Volume Confirmation:** Fading candle volume > opening candle volume.
13. **Candle Confirmation:** Rejection wick > 50% of candle body.
14. **Stop-loss:** High/Low of the opening 5-min candle.
15. **Profit-booking:** 80% at PDC.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 11:30 AM (If gap isn't filled early, abort).
18. **Max holding duration:** 2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital, 2% risk limit.
21. **Performance:** *[Requires historical backtest]*

## Strategy 8: SENSEX_VOL_08 (Volume Spread Analysis Climax)
1. **Name/ID:** SENSEX_VOL_08
2. **Hypothesis:** Ultra-high volume on a wide spread candle into resistance signifies buying climax and smart money distribution.
3. **Best Conditions:** Extended trends hitting major psychological levels (e.g., 75,000, 76,000).
4. **Avoid in:** Early stage breakouts.
5. **Indicators:** Volume, Support/Resistance zones.
6. **Entry Conditions:** Ultra-high volume (3x average) on an unusually large bullish candle hitting resistance, followed immediately by an inside bar or bearish close.
7. **Exit Conditions:** Price drops to 21 EMA.
8. **CALL/PUT Logic:** Climax at resistance = PUT; Selling climax at support = CALL.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** Climax candle volume must be highest of the session.
13. **Candle Confirmation:** Next candle must not break the high/low of the climax candle.
14. **Stop-loss:** High/Low of the climax candle.
15. **Profit-booking:** 21 EMA.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:00 PM.
18. **Max holding duration:** 1 hour.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital, 2% risk limit.
21. **Performance:** *[Requires historical backtest]*

## Strategy 9: SENSEX_IB_09 (Inside Bar Breakout)
1. **Name/ID:** SENSEX_IB_09
2. **Hypothesis:** Inside bars represent consolidation; breakouts from them yield sharp momentum.
3. **Best Conditions:** Trending markets pausing for 1-2 candles.
4. **Avoid in:** Range-bound markets (ADX < 20).
5. **Indicators:** Inside Bar pattern, 9 EMA.
6. **Entry Conditions:** Price breaks the high/low of the "Mother Bar" in the direction of the 9 EMA slope.
7. **Exit Conditions:** Price closes inside the Mother Bar range.
8. **CALL/PUT Logic:** Break Mother Bar High = CALL; Break Mother Bar Low = PUT.
9. **Strike Selection:** Slightly OTM (Delta ~0.45).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹300.
12. **Volume Confirmation:** Breakout candle volume > Mother Bar volume.
13. **Candle Confirmation:** Close outside Mother Bar.
14. **Stop-loss:** Low/High of the Inside Bar.
15. **Profit-booking:** 1:1.5 Risk-to-Reward.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 45 minutes.
19. **Re-entry:** Allowed on subsequent Inside Bars.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 10: SENSEX_SUP_10 (Supertrend Pullback)
1. **Name/ID:** SENSEX_SUP_10
2. **Hypothesis:** Supertrend acts as dynamic support/resistance in highly trending regimes.
3. **Best Conditions:** Unidirectional markets.
4. **Avoid in:** Choppy/Sideways (Supertrend frequently flipping).
5. **Indicators:** Supertrend (10,3).
6. **Entry Conditions:** Price pulls back to within 0.2% of the Supertrend line and forms a reversal candle.
7. **Exit Conditions:** Supertrend changes color.
8. **CALL/PUT Logic:** Bounce off green ST = CALL; Reject off red ST = PUT.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹400.
12. **Volume Confirmation:** Reversal candle volume > pullback volume.
13. **Candle Confirmation:** Pin bar/Hammer/Shooting Star.
14. **Stop-loss:** Close across the Supertrend line.
15. **Profit-booking:** Previous Swing High/Low.
16. **Trailing SL:** Supertrend line.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Yes, on next pullback.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 11: SENSEX_FALSE_11 (False Breakdown / Spring)
1. **Name/ID:** SENSEX_FALSE_11
2. **Hypothesis:** A dip below major support that is quickly bought up traps breakout sellers and fuels a short-covering rally.
3. **Best Conditions:** Broad range-bound markets.
4. **Avoid in:** Heavy bearish momentum (ADX > 35, DI- > DI+).
5. **Indicators:** Previous Day Low (PDL), Major Support zones.
6. **Entry Conditions:** Price breaks PDL, spends < 10 mins below it, and closes back above PDL forcefully.
7. **Exit Conditions:** Price reaches VWAP.
8. **CALL/PUT Logic:** Spring at Support = CALL. Upthrust at Resistance = PUT.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** The recovery candle must have higher volume than the breakdown candle.
13. **Candle Confirmation:** Bullish engulfing closing above the support level.
14. **Stop-loss:** The absolute low of the spring wick.
15. **Profit-booking:** Central Pivot / VWAP.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 12: SENSEX_0DTE_12 (Expiry Day 2:00 PM Gamma Scalp)
1. **Name/ID:** SENSEX_0DTE_12
2. **Hypothesis:** Late-day options on expiry experience massive gamma spikes during directional breakouts due to institutional squaring off.
3. **Best Conditions:** SENSEX Expiry days only (Fridays/Tuesdays depending on exchange schedule), post 1:30 PM.
4. **Avoid in:** Non-expiry days.
5. **Indicators:** VWAP, Day High/Low.
6. **Entry Conditions:** Price breaks Day High or Day Low after 1:30 PM with rising volume.
7. **Exit Conditions:** Momentum stalls (first opposing colored 5-min candle).
8. **CALL/PUT Logic:** Break Day High = CALL; Break Day Low = PUT.
9. **Strike Selection:** ATM or slightly OTM (Delta 0.30 - 0.50).
10. **Expiry Selection:** CURRENT DAY (0DTE).
11. **Premium Selection:** ₹30 - ₹100 (Capital allocation reduced due to zero-day risk).
12. **Volume Confirmation:** Breakout volume > 1.5x average.
13. **Candle Confirmation:** Strong close outside range.
14. **Stop-loss:** -30% of option premium (Strict hard stop).
15. **Profit-booking:** +50% of premium, trail rest.
16. **Trailing SL:** Previous 3-min candle low/high.
17. **Time-based exit:** 15:20 PM.
18. **Max holding duration:** 30 mins.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 5% capital (₹2,500) due to extreme volatility.
21. **Performance:** *[Requires historical backtest]*

## Strategy 13: SENSEX_WMA_13 (Weighted MA Crossover Scalp)
1. **Name/ID:** SENSEX_WMA_13
2. **Hypothesis:** Faster WMA crossovers capture micro-trends in high-liquidity environments.
3. **Best Conditions:** Opening session (9:30 - 10:30) and Closing session (14:00 - 15:15).
4. **Avoid in:** 11:30 - 13:30 (Lunch hours).
5. **Indicators:** 5 WMA, 13 WMA.
6. **Entry Conditions:** 5 WMA crosses 13 WMA cleanly.
7. **Exit Conditions:** 5 WMA crosses back below/above 13 WMA.
8. **CALL/PUT Logic:** 5 crosses above 13 = CALL; 5 crosses below 13 = PUT.
9. **Strike Selection:** ITM (Delta ~0.60) for maximum mirroring of spot.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹300 - ₹500.
12. **Volume Confirmation:** None required, pure price action scalp.
13. **Candle Confirmation:** Entry on candle close.
14. **Stop-loss:** Swing low/high prior to crossover.
15. **Profit-booking:** 1:1.5 RR.
16. **Trailing SL:** 13 WMA.
17. **Time-based exit:** End of momentum window.
18. **Max holding duration:** 15-20 mins.
19. **Re-entry:** Yes.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 14: SENSEX_RNG_14 (Stochastic Range Reversion)
1. **Name/ID:** SENSEX_RNG_14
2. **Hypothesis:** In non-trending markets, price oscillates predictably between overbought and oversold zones.
3. **Best Conditions:** Sideways regime (ADX < 20, BB flat).
4. **Avoid in:** Trending markets.
5. **Indicators:** Stochastic Oscillator (14,3,3), Bollinger Bands.
6. **Entry Conditions:** Price touches upper/lower BB, and Stochastic crosses back inside from >80 or <20.
7. **Exit Conditions:** Stochastic reaches opposite extreme.
8. **CALL/PUT Logic:** Stoch crosses > 20 upwards at Lower BB = CALL.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹150 - ₹300.
12. **Volume Confirmation:** Lower volume at edges confirms lack of breakout interest.
13. **Candle Confirmation:** Rejection candle at BB edge.
14. **Stop-loss:** Close outside the Bollinger Band.
15. **Profit-booking:** 20 SMA (Middle BB).
16. **Trailing SL:** None, rigid target.
17. **Time-based exit:** 15:00 PM.
18. **Max holding duration:** 2 hours.
19. **Re-entry:** Yes.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 15: SENSEX_DOJI_15 (Doji Continuation)
1. **Name/ID:** SENSEX_DOJI_15
2. **Hypothesis:** A Doji after a strong momentum move indicates a brief pause before continuation.
3. **Best Conditions:** Strong trending regimes.
4. **Avoid in:** Choppy markets.
5. **Indicators:** Price Action (Doji), 9 EMA.
6. **Entry Conditions:** A Doji forms touching/near the 9 EMA during a trend; next candle breaks the Doji high/low in trend direction.
7. **Exit Conditions:** Break of 9 EMA.
8. **CALL/PUT Logic:** Uptrend + Doji High broken = CALL.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Doji must have low volume; breakout candle must have high volume.
13. **Candle Confirmation:** Close beyond Doji extreme.
14. **Stop-loss:** Opposite extreme of the Doji.
15. **Profit-booking:** 1:2 RR.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1 hour.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 16: SENSEX_VWAP_X_16 (VWAP Crossover)
1. **Name/ID:** SENSEX_VWAP_X_16
2. **Hypothesis:** Crossing the VWAP with strong volume indicates a shift in intraday institutional bias.
3. **Best Conditions:** Reversal days (V-shape recoveries).
4. **Avoid in:** Flat VWAP days (price chopping around VWAP).
5. **Indicators:** VWAP.
6. **Entry Conditions:** Full candle body closes completely across the VWAP line.
7. **Exit Conditions:** Price crosses back across VWAP.
8. **CALL/PUT Logic:** Cross below to above = CALL; Above to below = PUT.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹400.
12. **Volume Confirmation:** Crossover candle volume > 1.5x average.
13. **Candle Confirmation:** Full body crossover (no overlap with VWAP line on open/close).
14. **Stop-loss:** Opposite side of the crossover candle.
15. **Profit-booking:** Next major resistance/support.
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2-3 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 17: SENSEX_MACD_17 (MACD Zero-Line Reject)
1. **Name/ID:** SENSEX_MACD_17
2. **Hypothesis:** MACD histograms rejecting the zero line signify strong trend resumption.
3. **Best Conditions:** Unidirectional markets.
4. **Avoid in:** Range-bound.
5. **Indicators:** MACD (12,26,9).
6. **Entry Conditions:** MACD line pulls back to zero line and bounces off it, histogram expands in trend direction.
7. **Exit Conditions:** MACD signal line crossover.
8. **CALL/PUT Logic:** Bounce off zero upwards = CALL.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Standard.
13. **Candle Confirmation:** Bullish/Bearish engulfing on price chart matching MACD bounce.
14. **Stop-loss:** Recent swing low/high.
15. **Profit-booking:** 1:2 RR.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 1-2 hours.
19. **Re-entry:** Yes.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 18: SENSEX_MCD_18 (Morning Consolidation Breakout)
1. **Name/ID:** SENSEX_MCD_18
2. **Hypothesis:** Markets that chop tightly between 9:15 and 10:30 accumulate orders for a mid-day breakout.
3. **Best Conditions:** Extremely tight 9:15 - 10:30 range (< 0.3% of SENSEX value).
4. **Avoid in:** Wide morning ranges.
5. **Indicators:** 10:30 AM Range High/Low.
6. **Entry Conditions:** Post 10:30 AM, 5-min candle breaks the morning range.
7. **Exit Conditions:** Re-enters range and hits VWAP.
8. **CALL/PUT Logic:** Break High = CALL; Break Low = PUT.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹200 - ₹350.
12. **Volume Confirmation:** Breakout RVOL > 2.0.
13. **Candle Confirmation:** Close outside range.
14. **Stop-loss:** Mid-point of the morning consolidation range.
15. **Profit-booking:** 1:3 RR.
16. **Trailing SL:** 9 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** Rest of day.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 19: SENSEX_FIB_19 (Fibonacci 0.618 Retracement)
1. **Name/ID:** SENSEX_FIB_19
2. **Hypothesis:** Institutional algos often buy/sell pullbacks at the Golden Ratio (61.8%).
3. **Best Conditions:** Clear morning impulse move followed by slow, low-volume pullback.
4. **Avoid in:** High-volume sharp pullbacks.
5. **Indicators:** Fibonacci Retracement Tool (Impulse Low to High).
6. **Entry Conditions:** Price touches the 0.618 level and forms a reversal candle.
7. **Exit Conditions:** Breaks the 0.786 level.
8. **CALL/PUT Logic:** Uptrend pullback to 0.618 = CALL.
9. **Strike Selection:** Slightly ITM (Delta 0.55).
10. **Expiry Selection:** Current weekly.
11. **Premium Selection:** ₹250 - ₹450.
12. **Volume Confirmation:** Reversal candle volume > pullback volume.
13. **Candle Confirmation:** Pin bar at 0.618.
14. **Stop-loss:** Close below 0.786 Fib level.
15. **Profit-booking:** The 0.0% Fib level (Impulse peak).
16. **Trailing SL:** 21 EMA.
17. **Time-based exit:** 15:15 PM.
18. **Max holding duration:** 2-3 hours.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*

## Strategy 20: SENSEX_EOD_20 (End of Day Squeeze)
1. **Name/ID:** SENSEX_EOD_20
2. **Hypothesis:** Institutional positioning for the next day causes aggressive moves post 2:30 PM.
3. **Best Conditions:** Price consolidating near Day High or Day Low at 2:30 PM.
4. **Avoid in:** Price hovering in the middle of the day's range.
5. **Indicators:** Day High/Low, VWAP.
6. **Entry Conditions:** Price breaks out of a post-1:30 PM consolidation flag/pennant after 2:30 PM.
7. **Exit Conditions:** Momentum stops.
8. **CALL/PUT Logic:** Break flag high = CALL.
9. **Strike Selection:** ATM.
10. **Expiry Selection:** Current weekly (or next weekly if on expiry day to avoid decay).
11. **Premium Selection:** ₹200 - ₹400.
12. **Volume Confirmation:** Expanding volume on the 2:30 PM candle.
13. **Candle Confirmation:** Strong close in direction of main daily trend.
14. **Stop-loss:** Below the 2:30 PM consolidation zone.
15. **Profit-booking:** 1:1.5 RR.
16. **Trailing SL:** 5-min previous candle low.
17. **Time-based exit:** 15:25 PM (Mandatory auto-square off).
18. **Max holding duration:** 45 minutes.
19. **Re-entry:** No.
20. **Risk/Capital:** Max 10% capital.
21. **Performance:** *[Requires historical backtest]*