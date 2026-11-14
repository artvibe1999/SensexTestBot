# Entry timing research (2026-11-14)

**Question:** the live paper bot "buys at the high, then the market reverses into the stop".
The 3 paper losses (9, 11, 12 Nov 2026) entered at 7% / 18% / 92% of the day's range right
after 180-340 point runs, so the complaint is real for those trades.

**Test:** 4-year engine backtest (Sep 2022 - Nov 2026, 1-minute SENSEX, modelled options),
verified six strategies, 2 lots, risk limits pinned to Rs 50k. Selection on the train period
(<= Oct 2025) only; Nov 2025 - Nov 2026 is the holdout. Script: `scripts/entry_timing.py`.

| Variant | Net 4y | PF | Win % | Max DD | Train net (PF) | Holdout net (PF) |
|---|---|---|---|---|---|---|
| base | +6.13L | 1.33 | 40.0 | 77k | +4.75L (1.36) | +1.39L (1.25) |
| ENTRY_EXT_MAX_ATR 1.5 | +5.34L | 1.36 | 43.1 | 1.02L | +4.22L (1.39) | +1.12L (1.27) |
| **ENTRY_EXT_MAX_ATR 2.0** | **+6.26L** | **1.38** | 42.4 | 83k | **+4.92L (1.41)** | +1.34L (1.30) |
| ENTRY_EXT_MAX_ATR 2.5 | +6.44L | 1.36 | 41.4 | 77k | +5.19L (1.41) | +1.26L (1.25) |
| ENTRY_RUN_MAX_ATR 2 | +4.09L | 1.22 | 39.8 | 93k | +2.38L (1.18) | +1.72L (1.34) |
| ENTRY_RUN_MAX_ATR 3 | +6.03L | 1.33 | 40.4 | 81k | +4.43L (1.34) | +1.60L (1.30) |
| pullback 0.3 ATR / 30 min | +5.67L | 1.32 | 42.1 | 81k | +4.51L (1.36) | +1.16L (1.23) |
| pullback 0.5 ATR / 30 min | +4.35L | 1.25 | 41.8 | 74k | +3.59L (1.28) | +0.77L (1.15) |
| pullback 0.75 ATR / 45 min | +4.56L | 1.27 | 42.9 | 77k | +3.56L (1.29) | +1.00L (1.22) |
| pullback 1.0 ATR / 60 min | +3.30L | 1.21 | 43.0 | 65k | +2.43L (1.21) | +0.87L (1.19) |

**Findings**
* Waiting for a pullback is worse in train AND holdout at every setting: these are momentum
  strategies (~40% win rate, avg win ~2x avg loss) and the trades that never pull back are the
  big winners.
* Skipping signals already > 2 ATR beyond EMA21 is the best train result and about equal to
  base on the holdout (higher PF and win rate, net -4k). Small refinement, not a fix.
* Adopted (user, 2026-11-14): `ENTRY_EXT_MAX_ATR=2.0` on sensex-bot (paper). All guards
  default to off in code.
