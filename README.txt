# Weekly Expected Return (ER) — IBKR Live Runner

This repo contains:
- `ibkr_live_runner.py`: production-oriented live loop for Monday→Friday
- `us_trading_calendar.py`: US-holiday-aware scheduling
- `configure.py`: one-click config wizard
- `setup.sh`, `run.sh`: local venv bootstrap + run
- `Dockerfile`, `docker-compose.yml`: containerized run
- (Optional) TradingView webhook: `tv_webhook_ibkr.py`

## Quick start (local)

```bash
git clone <this-folder>
cd <this-folder>
./setup.sh          # creates venv, installs, runs config wizard
./run.sh            # starts the live runner (paper port 7497 by default)
```

> The runner waits for the next **US Monday** at either **09:30 ET** or **11:30 ET** (your choice) to place entries, monitors through the week, then exits near **Friday close**.

## Configure

The wizard writes `config.json` and seeds `tickers.csv`. Edit as needed.

Key knobs:
- `entry_timing`: `"open"` or `"delayed_2h"`
- `stop_mode`: `"atr"` or `"fixed"`
- `trailing_mode`: `"atr"` or `"percent"`
- `regime_spy_ema`, `max_vix`: set both for a robust regime filter
- `enable_hedge`, `hedge_ratio`: auto-SPY hedge when regime is bad
- `price_min`, `price_max`, `min_volume`: short-term universe control
- `ema_filters`, `ema_logic`: e.g. `[20]` or `[20,200]` with `"all"`

## IBKR Setup

- Use **IB Gateway** or **TWS** (Paper first).
- API: *Configure → API → Enable ActiveX/Socket Clients*.
- Default port in config is `7497` (paper).

## Notes

- Trailing logic ratchets the stop upward **only after** price crosses:
  - `entry + trailing_atr_mult × ATR` (ATR mode), or
  - `entry × (1 + trailing_pct)` (percent mode).
- When price first crosses **Expected Return**, the stop is raised to **ER** (profit-protect) and we continue to hold winners.
- Hedge: if regime fails at the start of the week and `enable_hedge=true`, the runner shorts **SPY** sized to `hedge_ratio × allocated_$`, and closes it at Friday.

## Docker

```bash
docker compose up --build -d
```

This will run with TZ=America/New_York and share the current folder.

## Safety & Limits

- **Paper trade first**.
- IBKR pacing: the runner staggers requests; if you scale beyond ~100 names, consider rate limiting further.
- Real-time market data entitlements may be required for accurate intraday monitoring.

## Optional: TradingView Webhook

`tv_webhook_ibkr.py` is a small Flask server that accepts TradingView alerts and forwards orders to IBKR. Use only if you prefer signals from TradingView.


## Journaling
The live runner writes:
- `logs/trade_journal.csv` → time-stamped entries/exits/hedge trades
- `logs/events_log.csv` → stop raises (ER-protect, trail), ER-hit events, etc.
