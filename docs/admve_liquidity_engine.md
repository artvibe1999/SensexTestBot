# ADMVE and shared liquidity intelligence

## Status and safety

ADMVE (strategy ID `SENSEX_ADMVE_80`) is a new research candidate. It is ranked first
when multiple strategy signals are ready, but it is **not described as backtest-verified
or profitable**. It is enabled by a one-time migration and runs in the existing default
paper mode. Live mode still requires the existing Telegram live-mode confirmation.

Priority is not permission to trade. ADMVE must pass the same entry window, regime,
re-entry, timing, option quote, delta, premium, spread, affordability, allocation,
risk-manager, order and exit checks as every other strategy. No signal is forced.

## ADMVE entry model

- Closed 5-minute candles for entries; completed 15-minute candles for directional
  confirmation. Indicators are computed without using a future candle.
- Directional trend: EMA 9/21/50 alignment and EMA21 slope, VWAP side, ADX >= 22 and
  rising, directional DMI, RSI(7) confirmation, ATR expansion relative to the median of
  prior ATR observations, and aligned 15-minute trend.
- Trigger: completed close beyond the previous six-bar high/low with candle-body,
  close-location and relative-volume confirmation, or a liquidity sweep/reclaim event
  in the direction of the confirmed trend.
- Sideways regime: separate squeeze/chop breakout path; requires rising ADX, directional
  DMI, VWAP side, 15-minute confirmation and close beyond the previous eight-bar range.
  The range middle is not an entry.
- Entry window 09:30–14:30 IST; no fresh entries after 14:30. Long CE in bullish setup,
  long PE in bearish setup. Single-leg only.
- Option preference: absolute delta target 0.55, normal band 0.45–0.65, subject to
  existing configured widening, premium cap, spread, available capital and lot sizing.
- Underlying initial stop 1.5 x ATR, 2R underlying target, 1.8 x ATR trailing level after
  the existing engine's 1R/partial-book activation, momentum invalidation exit and the
  existing premium emergency stop and intraday square-off.

The weighted evidence score is a deterministic filter, not a probability estimate.
Its initial threshold and indicator parameters require walk-forward and paper-trading
validation before any claim of edge.

## Shared liquidity intelligence

`sxpro/liquidity.py` is a pure analysis module. It does not place orders, size positions,
or veto other strategies. It publishes a context object consumed by ADMVE and used as
a category-aware ranking tie-breaker for all existing strategies:

- Prior-day high/low, pivot, confirmed local swing pivots, equal-high/equal-low clusters,
  and 30-minute opening-range levels.
- Approximate session volume profile / POC using the futures-volume proxy attached to
  SENSEX candles. This is a bar-level approximation, not trade-by-trade volume-at-price.
- Futures top-five-level bid/ask imbalance when a fresh quote with depth is available.
  A single snapshot is weak evidence; it is not treated as proof of absorption or intent.
- Sweep/reclaim detection requires a completed candle to trade beyond a level by an
  ATR/tick buffer and close back through it. A wick alone is insufficient.
- Breakout evidence uses a close beyond the prior six completed bars. Retest/acceptance
  should be separately evaluated in future validation before promoting the event rule.

Liquidity confluence is strategy-category aware: reversal strategies receive ranking
support for a same-direction sweep/reclaim, breakout strategies for a same-direction
breakout, and trend strategies for directional liquidity evidence. It only breaks ties
after the existing strategy group and market-fit score; it never changes a strategy's
entry rule or weakens risk checks.

## Backtesting limitations and validation gate

Historical order-book snapshots are unavailable in the existing backtest data, so
backtests calculate candle/volume-profile liquidity only; OBI is omitted. Existing option
prices are modelled by the current Black-Scholes approximation and are not historical
option fills. The historical volume input is the repository's documented volume proxy,
not a full historical futures order book.

Before enabling live mode, compare baseline strategies against ADMVE and ablations
(candle liquidity only, then depth confluence live-only) using identical periods, costs,
slippage, risk and sizing. Require out-of-sample/walk-forward reporting for net expectancy,
profit factor, drawdown, MAE/MFE, trade count, regime breakdown, skipped-signal reasons
and sensitivity to costs. Then paper trade for at least 30 sessions. Keep paper mode
default until these gates pass.
