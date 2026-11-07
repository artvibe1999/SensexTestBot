# SENSEX PRO – paper/live options trading bot

Single-leg SENSEX weekly options bot for Zerodha Kite Connect, implementing the
framework and 60 strategies in [`docs/`](docs/). It's controlled from Telegram and
runs as Docker containers: the bot itself, plus Caddy for the HTTPS Kite login callback.

## What it does

* **Data:** SENSEX index 5-min candles from the Kite historical API. The index has no
  volume, so volume comes from the nearest SENSEX future. Live index and option
  quotes are polled every 2 s.
* **Regime engine** (framework §2): BULLISH / BEARISH / SIDEWAYS / NEUTRAL, computed on
  5-min and confirmed on 15-min. Bullish disables PUTs, bearish disables CALLs, and
  sideways disables breakout strategies.
* **60 strategies**: 1–20 in `sxpro/strategies/catalog.py`, 21–60 in
  `sxpro/strategies/catalog_21_60.py` (specs: `docs/sensex_pro_additional_strategies_*.md`).
  They are evaluated on every closed 5-min candle, each within its own time window. If
  several strategies signal on the same candle, the first one in catalogue order wins
  (so 1–20 take priority over 21–60).
* **Extra feeds for 21–60**, fetched only while a strategy that needs them is enabled:
  India VIX (27, 29), NIFTY 50 (60), advance/decline breadth of 15 SENSEX heavyweights
  (37, built from one quote per candle), option-chain OI (39, 48), the 09:15 1-minute
  candle (34) and recent daily candles (50, 59).
* **Strike selection** (framework §5):
  * Expiry follows each strategy's rule. On expiry day the bot rolls to next week,
    except SENSEX_0DTE_12, which trades the same-day expiry.
  * Delta comes from Black-Scholes using implied volatility solved from the quote.
    The bot picks the strike closest to the target delta that also fits the
    strategy's premium range, stays under the max affordable premium, and has a
    bid-ask spread below 1%.
* **Premium and delta limits beyond the spec:** every strategy's maximum premium is
  raised to ₹900 (`PREMIUM_CAP`; 0DTE ₹250, `ZERO_DTE_PREMIUM_CAP`). Delta bands are
  widened by +0.15 at the top (max 0.80) and −0.05 at the bottom (min 0.25). Each
  strategy keeps its spec delta target, so the spec strike is still preferred; the wider
  limits only allow pricier or deeper in-the-money strikes when the preferred one is
  filtered out. Available margin still caps the premium (90% ÷ lots ÷ lot size).
* **Capital management** (framework §1):
  * 90% of available margin per trade: the paper balance, or Zerodha's available margin (45% for 0DTE). Set with `MARGIN_UTILIZATION_PCT`.
  * Loss limits: 10% of capital max loss per trade, 10% per day, 25% per week (`TRADE_LOSS_CAP_PCT`, `DAILY_LOSS_LIMIT_PCT`, `WEEKLY_LOSS_LIMIT_PCT`).
  * At most 3 trades per day.
  * After 4 consecutive losses, a 24-hour cool-off.
  * If equity falls 20% below its peak, the allocation per trade is halved.
* **Exits:**
  * Stops on the underlying: a price stop checked on every quote, or a close-based
    stop checked on candle close.
  * A hard premium stop, so no trade loses more than 10% of capital. In live mode
    it's also placed at the exchange as an SL order.
  * Targets, with partial booking where the spec calls for it (for example, 50% at
    1:2), plus trailing stops.
  * Time exits, the max holding time, and an intraday square-off at 15:20.
* **Paper trading** fills at the live bid/ask from Zerodha and deducts estimated
  charges.
* **Live trading** uses marketable LIMIT orders. An unfilled entry is cancelled; an
  unfilled exit is re-priced and retried.

### Interpretation notes

* *VWAP slope > 20°* is implemented as VWAP rising or falling more than 2 bps over 3
  candles.
* **SENSEX_GAP_07:** the spec's CALL/PUT line contradicts its own hypothesis ("fill the
  gap", exit at the previous day's close). The bot follows the hypothesis: it buys a
  PUT to fade a gap-up and a CALL to fade a gap-down.
* **Trailing stops** start once the trade is 1R in profit, or right after a partial
  booking.
* **Lot size** comes from the instrument master (currently 20 for SENSEX), so the
  maximum affordable premium is `available margin × 90% ÷ lot size`.

## Google Sheet and daily reconciliation

* **Google Sheet:** rows are written with a Google service-account key through the
  Sheets API (`GOOGLE_SHEET_ID`, plus the key's JSON on one line in
  `GOOGLE_SERVICE_ACCOUNT_JSON`; share the sheet with the key's `client_email` as an
  Editor). An Apps Script web app (`SHEETS_WEBHOOK_URL` and `SHEETS_SECRET`) still works
  when no service account is set. Missing tabs are created with a header row. Rows are
  batched every 5 seconds and retried until Google accepts them; `/health` shows the
  backend and queue.
  * `Orders`: every paper and live entry, partial exit, exit and exchange SL order.
  * `Log`: every Telegram notification, plus WARNING and ERROR log lines.
  * `Status`: startup, Kite login, mode, lots, capital and strategy changes, a heartbeat
    every 15 minutes (`STATUS_INTERVAL_MIN`), the daily report and shutdown.
  * `Trades`: the final, reconciled trades, written once per trade by the 16:00 job.
* **16:00 IST reconciliation** (`REPORT_TIME`; run it on demand with `/report`):
  1. **Live:** fetches every completed SENSEX option order of the day from Kite, from
     the bot and manual alike. Gross P&L is Zerodha's own day-position P&L; any quantity
     still open is marked at its last price.
  2. **Paper:** takes the day's paper trades from the bot's database, one order per
     fill (entry, plus each partial and final exit).
  3. **Charges and taxes:** for both, they come from Kite's virtual contract-note API,
     which is Zerodha's own calculation of brokerage, STT, exchange charges, SEBI fee,
     stamp duty and GST. If that API fails, the same published rates are applied by
     formula (`sxpro/charges.py`).
  4. **Corrections:** stored trades, and the paper balance, are corrected to these numbers.
  5. **Publishing:** the final trades go to the sheet's `Trades` tab, and a summary
     goes to Telegram. (No cloud-storage HTML report in this deployment.)

## Telegram commands

| Command | Action |
|---|---|
| `/status` | Mode, Kite login, lots, paper capital, live funds, risk gate, regime |
| `/mode paper` / `/mode live` → `/confirmlive` | Switch trading mode (live asks for confirmation within 2 minutes) |
| `/lots paper <n\|auto>` / `/lots live <n\|auto>` | Lots per trade for each mode (`auto` = 90% of available margin, max 50 lots) |
| `/capital <amount>` | Paper trading capital (resets the paper balance) |
| `/funds` | Live funds fetched from Zerodha (`margins/equity`) |
| `/positions`, `/trades [mode]`, `/pnl`, `/regime` | Reporting |
| `/pause`, `/resume`, `/squareoff` | Stop or allow new entries; close everything now |
| `/ids` | Every strategy ID with ✅ enabled / ⛔ disabled |
| `/strategies`, `/enable <ID|all>`, `/disable <ID|all>` | Strategy details; turn strategies on or off (short IDs like `GAP_07` work) |\|all>`, `/disable <ID\|all>` | Turn strategies on or off |
| `/login`, `/token <request_token>` | Daily Kite login |
| `/report` | Run the 16:00 reconciliation now |

Live capital is always the `net` equity margin fetched from Zerodha. Available cash
caps the position size.

## Daily Kite login

Kite access tokens expire every morning. At `LOGIN_PROMPT_TIME` (08:30) the bot checks
its token and, if it has expired, sends the login link on Telegram. After you log in,
Zerodha redirects to `https://$BOT_DOMAIN/kite/callback` and the bot stores the new
token. The redirect URL in your Kite developer app must match this exactly. If the
redirect fails, copy the `request_token` from the URL and send `/token <request_token>`.

## Deploy

The VM has no GitHub credentials. The code is shipped as an archive of a commit, and
`.env` stays on the VM in `~/sxbot`:

```bash
# on your PC, from the repo
git archive --format=tar.gz -o sxpro.tar.gz HEAD
gcloud compute scp sxpro.tar.gz sxbot:~/sxpro.tar.gz --zone asia-south1-a
# on the VM
tar -xzf ~/sxpro.tar.gz -C ~/sxbot && cd ~/sxbot && mkdir -p data && docker compose up -d --build
docker compose logs -f bot
```

Runtime state (the Kite token, paper balance, settings and trades) lives in
`~/sxbot/data/sxpro.db` and survives restarts and redeploys.

Environment variables used: `KITE_API_KEY`, `KITE_API_SECRET`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, `BOT_DOMAIN`, `LOGIN_PROMPT_TIME`, `PRODUCT`, `PAPER_CAPITAL`
(used only on first boot), `MAX_LOTS` (cap for auto sizing), and the optional overrides
in `sxpro/config.py`.

## Tests

```bash
pip install -r requirements.txt pytest && pytest -q
docker compose exec bot python -m sxpro.replay --days 30   # signal sanity check on real data
```

> ⚠️ Backtest of strategies 21–60 (and the 1–20 baseline): [`docs/backtest_21_60.md`](docs/backtest_21_60.md). Option prices there are modelled, not real fills. Paper trade before going live.
