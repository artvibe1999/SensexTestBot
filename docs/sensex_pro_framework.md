# SENSEX PRO – Institutional-Grade Single-Leg Options Trading Strategy Framework

## 1. Capital Management Framework (₹50,000 Capital)
This module dictates all position sizing and risk management prior to strategy execution, strictly adhering to the ₹50,000 limit.

*   **Maximum Capital Allocation per Trade:** 10% of total capital (₹5,000). This ensures survival through severe drawdowns.
*   **Maximum Permissible Loss per Trade:** 2% of total capital (₹1,000). 
*   **Daily Loss Limit:** 4% of total capital (₹2,000). If hit, the system suspends trading for the day.
*   **Weekly Loss Limit:** 10% of total capital (₹5,000). If hit, the system suspends trading for the week.
*   **Maximum Number of Trades per Day:** 3 trades. (Overtrading prevention).
*   **Maximum Consecutive Losing Trades:** 4 trades. Triggers a mandatory 24-hour cooling-off period.
*   **Position Sizing Logic:** 
    *   SENSEX Lot Size: 10 (as of current BSE standards, adjust dynamically via API).
    *   Formula: `Floor(Allocated Capital / (Option Premium * Lot Size))`
    *   Max Premium Affordable: ₹500 (Assuming 1 lot = 10 qty. ₹500 * 10 = ₹5,000).
*   **Emergency Capital Protection:** If equity drops below ₹40,000 (20% drawdown), max allocation per trade halves to 5% (₹2,500).

---

## 2. Market Regime Identification Engine
Evaluated continuously on 5-minute and 15-minute timeframes to dictate strategy selection.

### A. Unidirectional Bullish Market
*   **VWAP:** Price > VWAP, VWAP slope is positive (> 20 degrees).
*   **EMAs:** 9 EMA > 21 EMA, both sloping upward.
*   **ADX (14):** ADX > 25, +DI > -DI.
*   **Volume:** Relative Volume (RVOL) of bullish candles > 1.5x of 20-period moving average.
*   **Action:** Enable Trend-Following CALL strategies. Disable all PUT strategies.

### B. Unidirectional Bearish Market
*   **VWAP:** Price < VWAP, VWAP slope is negative.
*   **EMAs:** 9 EMA < 21 EMA, both sloping downward.
*   **ADX (14):** ADX > 25, -DI > +DI.
*   **Volume:** RVOL of bearish candles > 1.5x.
*   **Action:** Enable Trend-Following PUT strategies. Disable all CALL strategies.

### C. Sideways and Range-Bound Market
*   **ADX (14):** ADX < 20.
*   **Bollinger Bands (20, 2):** Bandwidth contraction (Squeeze).
*   **VWAP:** Price repeatedly crossing VWAP; VWAP slope is flat.
*   **Action:** Enable Reversal/Mean-Reversion strategies. Disable Breakout strategies.

---

## 3. Opening Session Analytical Framework (9:15 AM - 10:30 AM)

### Candle Classification (First 15-Min / 5-Min Candles)
*   **Institutional Accumulation Candle:** Bullish close, Lower wick > 40% of total range, Volume > 2x 20-period average.
*   **Institutional Distribution Candle:** Bearish close, Upper wick > 40% of total range, Volume > 2x 20-period average.
*   **Momentum Exhaustion:** 3 consecutive unidirectional candles where the 3rd candle's body is < 50% of the 1st candle's body, coupled with volume divergence.

### Opening Range Breakout (ORB) Logic
*   **Define Range:** High and Low of the first 30 minutes (9:15 AM - 9:45 AM).
*   **Valid Breakout:** 5-minute candle closes outside the ORB with RVOL > 2.0.
*   **False Breakout (Trap):** Candle breaks ORB, but closes inside the range, forming a pin-bar or rejection tail.

---

## 4. Trap Identification Engine
*   **Bull Trap (Liquidity Sweep):**
    *   Price breaks major resistance or previous day high.
    *   Breakout candle volume is low (< 1x average) OR next candle immediately closes below the breakout level (Bearish Engulfing / Pin bar).
    *   **Action:** Trigger PUT Strategy (Reversal).
*   **Bear Trap:**
    *   Price breaks major support or previous day low.
    *   Breakout candle volume is low OR next candle immediately closes above the breakdown level.
    *   **Action:** Trigger CALL Strategy (Reversal).
*   **Volume-Price Divergence:** Price makes a higher high, but the volume on the up-leg is significantly lower than the previous up-leg. Indicates exhaustion.

---

## 5. Single-Leg Options Strike Selection Engine
*   **Constraint:** Capital ≤ ₹5,000 per trade.
*   **Expiry Selection:** Current weekly expiry (if days to expiry > 1). On expiry day (0DTE), select next week's expiry to avoid extreme gamma/theta risk, unless executing a pure momentum scalp (< 15 mins).
*   **Strike Selection (Moneyness):**
    *   Target Delta: 0.40 to 0.60 (ATM to slightly OTM).
    *   Max Premium: ₹500 (based on ₹50,000 capital, 10% risk rule).
    *   Liquidity Check: Bid-Ask spread must be < 1% of the premium.
*   **Avoid:** Deep OTM (Delta < 0.20) due to low probability, and Deep ITM due to capital constraints.

---

## 6. Strategy Documentation (Sample Specifications)

*Note: Per your requirements, 20 strategies must be developed. Below are 3 fully documented algorithmic logic structures covering Momentum, Reversal, and VWAP. You must run these through your backtester against historical SENSEX data to validate the performance metrics.*

### Strategy 1: SENSEX_MOM_01 (Opening Range Breakout)
1. **Trading hypothesis:** Institutional order flow at the open dictates the trend for the morning session.
2. **Best Market Conditions:** High gap-up/gap-down with immediate volume.
3. **Avoid in:** Range-bound pre-market, ADX < 20 on daily.
4. **Indicators:** 5-min ORB (9:15-9:45 High/Low), RVOL.
5. **Entry Conditions:** 5-min candle closes above ORB High with RVOL > 1.5.
6. **Exit Conditions:** Price closes below 9 EMA on 5-min chart.
7. **CALL/PUT Logic:** Break ORB High = CALL. Break ORB Low = PUT.
8. **Strike Selection:** ATM (Delta ~0.50).
9. **Expiry Selection:** Current weekly expiry.
10. **Premium Selection:** Between ₹200 - ₹400.
11. **Volume Confirmation:** Breakout candle volume must be > 1.5x previous 20 candles.
12. **Candle Confirmation:** Breakout candle body must be > 60% of its total range.
13. **Stop-loss:** Low of the breakout candle or -15% of option premium (whichever is closer).
14. **Profit-booking:** 50% at 1:2 RR, trail rest.
15. **Trailing SL:** Trail by 5-min previous candle low.
16. **Time-based exit:** Close by 10:30 AM if no momentum.
17. **Max holding duration:** 45 minutes.
18. **Re-entry:** Not allowed.
19. **Risk/Capital:** Max 10% capital, 2% risk.
20. **Expected Frequency:** 2-3 times a week.
21. **Performance:** *[Requires historical backtest]*

### Strategy 2: SENSEX_TRAP_02 (Liquidity Sweep Reversal)
1. **Trading hypothesis:** Smart money sweeps retail stop-losses at key highs/lows before reversing the market.
2. **Best Market Conditions:** Sideways / Broad ranges.
3. **Avoid in:** Unidirectional trending markets (ADX > 30).
4. **Indicators:** Support/Resistance (Pivot Points), Price Action.
5. **Entry Conditions:** Price breaks R1 or Previous Day High, but closes back below it within 2 candles (5-min chart).
6. **Exit Conditions:** Price reaches VWAP or central pivot.
7. **CALL/PUT Logic:** Failed high breakout = PUT. Failed low breakdown = CALL.
8. **Strike Selection:** Slightly OTM (Delta 0.40) for higher RoI on reversal.
9. **Expiry Selection:** Current weekly.
10. **Premium Selection:** ₹150 - ₹300.
11. **Volume Confirmation:** Breakout candle has high volume, but the reversal candle has equal or greater volume (Absorption).
12. **Candle Confirmation:** Reversal candle must be a bearish/bullish engulfing or a long-wick pin bar.
13. **Stop-loss:** High/Low of the trap wick.
14. **Profit-booking:** VWAP level.
15. **Trailing SL:** 9 EMA.
16. **Time-based exit:** End of day (15:15).
17. **Max holding duration:** 2 hours.
18. **Re-entry:** Allowed if a secondary trap forms at a higher/lower pivot.
19. **Risk/Capital:** Max 10% capital, 2% risk.
20. **Expected Frequency:** 1-2 times a week.
21. **Performance:** *[Requires historical backtest]*

### Strategy 3: SENSEX_VWAP_03 (Mid-Session Pullback)
1. **Trading hypothesis:** In trending markets, pullbacks to the VWAP offer high-probability continuation entries.
2. **Best Market Conditions:** Unidirectional Bullish/Bearish (ADX > 25).
3. **Avoid in:** Sideways market, VWAP slope is flat.
4. **Indicators:** VWAP, 21 EMA.
5. **Entry Conditions:** Price pulls back to within 0.1% of VWAP and forms a rejection candle (pin bar / engulfing) in the direction of the main trend.
6. **Exit Conditions:** Trend reversal (closing below VWAP + 21 EMA).
7. **CALL/PUT Logic:** Bounce off VWAP upwards = CALL. Reject off VWAP downwards = PUT.
8. **Strike Selection:** ATM (Delta ~0.50).
9. **Expiry Selection:** Next weekly (if post 2:00 PM on expiry day), else current weekly.
10. **Premium Selection:** ₹250 - ₹450.
11. **Volume Confirmation:** Volume dries up on the pullback and expands on the rejection candle.
12. **Candle Confirmation:** Clear rejection tail touching the VWAP line.
13. **Stop-loss:** Close below VWAP on 5-min chart.
14. **Profit-booking:** Previous swing high/low.
15. **Trailing SL:** Supertrend (10, 3).
16. **Time-based exit:** 15:15 PM.
17. **Max holding duration:** 1-3 hours.
18. **Re-entry:** Allowed on secondary pullbacks.
19. **Risk/Capital:** Max 10% capital, 2% risk.
20. **Expected Frequency:** 3-5 times a week.
21. **Performance:** *[Requires historical backtest]*

---

## 7. Zerodha Kite Connect API Integration Architecture

### Required API Endpoints
1.  **Instrument Identification:** `GET /instruments`
    *   *Usage:* Fetch daily list of SENSEX options, map strikes, expiry dates, and lot sizes. Filter for `instrument_type == 'CE' | 'PE'`.
2.  **Historical Data (Requires Historical API Add-on):** `GET /instruments/historical/{instrument_token}/{interval}`
    *   *Usage:* Fetch OHLCV data for SENSEX index and options to build technical indicators (VWAP, EMAs). Note: Kite API limits historical data depth for expired options.
3.  **Live Market Data:** WebSocket API (`wss://ws.kite.trade/`)
    *   *Usage:* Subscribe to SENSEX spot and 4-6 selected option strikes (ATM, ITM, OTM). Retrieve tick-level data (LTP, Volume, Open Interest, Bid/Ask).
4.  **Order Placement:** `POST /orders/{variety}`
    *   *Usage:* Place `REGULAR` orders with `product='MIS'` (intraday) or `NRML`.
5.  **Order Modification/Cancellation:** `PUT /orders/{variety}/{order_id}` / `DELETE /orders/{variety}/{order_id}`
    *   *Usage:* Manage trailing stop-losses.

### Data Limitations & Workarounds
*   **Limitation:** Historical Bid-Ask spread and Order Flow (tick-by-tick market depth) are NOT available via standard Kite historical API.
*   **Workaround:** Rely on OHLCV volume data for historical backtesting. For live trading, capture the WebSocket Level 2 quote depth in real-time into a local Redis/PostgreSQL database to compute real-time order flow imbalances.
*   **Limitation:** Historical options data is difficult to stitch continuously due to changing strikes.
*   **Workaround:** Build backtests primarily on SENSEX Spot/Futures signals, then map the timestamp of the signal to the nearest ATM historical option contract at that exact time to calculate accurate entry/exit premiums.