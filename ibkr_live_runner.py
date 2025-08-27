

"""
IBKR Live Runner — Weekly ER Strategy
- Monday entry (open or +2h), Friday exit
- Stops: fixed % or ATR, plus ATR/percent trailing
- ER logic: once price >= ER, raise stop to ER to lock gains while letting winners run
- Regime: SPY EMA and/or VIX; optional SPY hedge (short) for bad-regime weeks
- Holiday-aware for US markets
IMPORTANT: Paper-trade first. Not investment advice.
"""

import os, json, math, asyncio, logging, time
import datetime as dt
from typing import Dict, Any
from pathlib import Path

import pandas as pd
import numpy as np
import pytz

# Import our pending sales tracker for automatic tracking
try:
    from pending_sales import pending_tracker
    PENDING_TRACKING_AVAILABLE = True
except ImportError:
    PENDING_TRACKING_AVAILABLE = False
from dateutil.relativedelta import relativedelta

from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder, util, Contract


# ---------------- Journal helpers -----------------
class Journal:
    def __init__(self, base_dir: Path):
        self.base = base_dir / "logs"
        self.base.mkdir(parents=True, exist_ok=True)
        self.trade_path = self.base / "trade_journal.csv"
        self.event_path = self.base / "events_log.csv"
        # headers if not present
        if not self.trade_path.exists():
            self.trade_path.write_text("ts,symbol,side,qty,price,reason,orderId\n")
        if not self.event_path.exists():
            self.event_path.write_text("ts,symbol,event,detail\n")

    def now(self):
        from datetime import datetime
        import pytz
        return datetime.now(tz=NY).isoformat()

    def trade(self, symbol, side, qty, price, reason, orderId=None):
        line = f"{self.now()},{symbol},{side},{qty},{price},{reason},{orderId or ''}\n"
        with self.trade_path.open("a") as f:
            f.write(line)

    def event(self, symbol, event, detail=""):
        line = f"{self.now()},{symbol},{event},{str(detail).replace(',',';')}\n"
        with self.event_path.open("a") as f:
            f.write(line)
from us_trading_calendar import next_monday_trading_date, friday_of_week, ny_datetime, NY, is_us_trading_day
from options_protection import OptionsProtectionManager, BacktestConfig

BASE = Path(__file__).resolve().parent
LOG = logging.getLogger("weekly-er-live")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def auto_track_sell_order(symbol: str, quantity: int, order_type: str = "MARKET", price: float = None, notes: str = ""):
    """Automatically track sell orders in our pending sales system"""
    if PENDING_TRACKING_AVAILABLE:
        try:
            result = pending_tracker.mark_as_pending_sale(symbol, quantity, order_type, price, notes)
            LOG.info(f"📊 Auto-tracked pending sale: {result}")
        except Exception as e:
            LOG.warning(f"⚠️ Failed to auto-track pending sale for {symbol}: {e}")
    else:
        LOG.warning("⚠️ Pending sales tracking not available")

def auto_track_buy_order(symbol: str, quantity: int, order_type: str = "MARKET", price: float = None, notes: str = ""):
    """Automatically track buy orders in our pending orders system"""
    if PENDING_TRACKING_AVAILABLE:
        try:
            result = pending_tracker.mark_as_pending_buy(symbol, quantity, order_type, price, notes)
            LOG.info(f"📊 Auto-tracked pending buy: {result}")
        except Exception as e:
            LOG.warning(f"⚠️ Failed to auto-track pending buy for {symbol}: {e}")
    else:
        LOG.warning("⚠️ Pending orders tracking not available")

def auto_mark_buy_filled(symbol: str, notes: str = ""):
    """Mark buy order as filled (remove from tracking)"""
    if PENDING_TRACKING_AVAILABLE:
        try:
            result = pending_tracker.mark_as_bought(symbol, notes)
            LOG.info(f"📊 Auto-marked buy as filled: {result}")
        except Exception as e:
            LOG.warning(f"⚠️ Failed to mark buy as filled for {symbol}: {e}")
    else:
        LOG.warning("⚠️ Pending orders tracking not available")

# --------------- Config I/O -----------------
def load_config() -> Dict[str, Any]:
    return json.load(open(BASE/"config.json","r"))

def load_universe(cfg) -> list[str]:
    path = BASE/cfg["universe_file"]
    return pd.read_csv(path)["Ticker"].astype(str).tolist()

def load_expected_returns(cfg) -> dict:
    p = BASE/cfg.get("expected_returns_file","expected_returns.csv")
    if p.exists():
        er = pd.read_csv(p).set_index("Ticker")["ExpectedReturn"].to_dict()
        return er
    return {}

# --------------- Helpers --------------------
async def connect_ib(cfg) -> IB:
    ib = IB()
    await ib.connectAsync(cfg.get("ib_host","127.0.0.1"),
                          int(cfg.get("ib_port",7497)),
                          clientId=int(cfg.get("ib_client_id",7)))
    LOG.info("Connected: %s", ib.isConnected())
    return ib

async def hist_daily_closes(ib: IB, contract: Contract, days: int = 200):
    bars = ib.reqHistoricalData(contract, endDateTime="", durationStr=f"{max(days,10)} D",
                                barSizeSetting="1 day", whatToShow="TRADES", useRTH=True, formatDate=1)
    return bars

def compute_atr(bars, lookback=14):
    if not bars or len(bars) < 2:
        return None
    high = pd.Series([b.high for b in bars])
    low  = pd.Series([b.low for b in bars])
    close= pd.Series([b.close for b in bars])
    prev_close = close.shift(1)
    tr = pd.concat([(high-low).abs(), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    return float(tr.rolling(int(lookback), min_periods=1).mean().iloc[-1])

def ema(series: pd.Series, span: int) -> float:
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])

async def spy_regime_ok(ib: IB, ema_len: int | None, max_vix: float | None) -> bool:
    ok = True
    # SPY close vs EMA
    if ema_len and ema_len > 0:
        spy = Stock("SPY", "ARCA", "USD")
        bars = await hist_daily_closes(ib, spy, days=max(ema_len+10, 120))
        if bars and len(bars) > ema_len+2:
            closes = pd.Series([b.close for b in bars])
            e = ema(closes, ema_len)
            ok = closes.iloc[-1] > e
            LOG.info("SPY Regime: close=%.2f vs EMA%d=%.2f -> %s", closes.iloc[-1], ema_len, e, ok)
        else:
            LOG.warning("Insufficient SPY bars for EMA check; not blocking trades.")
    # VIX cap (approx via CBOE index if available)
    if ok and max_vix and max_vix > 0:
        try:
            vix = Stock("VIX", "CBOE", "USD")
            vb = await hist_daily_closes(ib, vix, days=10)
            if vb:
                v_last = float(vb[-1].close)
                ok = ok and (v_last <= max_vix)
                LOG.info("VIX filter: last=%.2f <= %.2f -> %s", v_last, max_vix, ok)
        except Exception as e:
            LOG.warning("VIX check failed (missing market data?): %s", e)
    return ok

def pass_filters(last_close: float, vol_sma: float, ema_checks: list[bool],
                 price_min: float, price_max: float, min_volume: float, ema_logic: str) -> bool:
    if not (price_min <= last_close <= price_max):
        return False
    if vol_sma is not None and vol_sma < min_volume:
        return False
    if ema_checks:
        if ema_logic == "all" and not all(ema_checks): return False
        if ema_logic == "any" and not any(ema_checks): return False
    return True

async def build_candidates(ib: IB, cfg, tickers: list[str]) -> list[dict]:
    ema_filters = cfg.get("ema_filters", [])
    ema_logic   = cfg.get("ema_logic","any")
    vol_days    = int(cfg.get("volume_ma_days",20))
    price_min   = float(cfg.get("price_min",0))
    price_max   = float(cfg.get("price_max",1e9))
    min_volume  = float(cfg.get("min_volume",0))
    atr_lb      = int(cfg.get("atr_lookback",14))

    out = []
    for sym in tickers:
        c = Stock(sym, "SMART", "USD")
        bars = await hist_daily_closes(ib, c, days=max(200, vol_days+50, 126+20))
        if not bars or len(bars) < 30: 
            continue
        last = bars[-1]
        closes = pd.Series([b.close for b in bars])
        vols   = pd.Series([b.volume for b in bars])
        vol_sma = float(vols.rolling(vol_days, min_periods=1).mean().iloc[-1])
        ema_checks = [last.close > ema(closes, int(span)) for span in ema_filters]
        if not pass_filters(last.close, vol_sma, ema_checks, price_min, price_max, min_volume, ema_logic):
            continue
        atr_val = compute_atr(bars, lookback=atr_lb)
        mom126 = float(closes.iloc[-1] / closes.iloc[-126] - 1.0) if len(closes) > 126 else 0.0
        out.append({"symbol": sym, "last_close": float(last.close), "atr": atr_val, "mom126": mom126})
        # small pacing to avoid pacing violations
        await asyncio.sleep(0.05)
    # Rank
    if cfg.get("ranking","momentum_126d") == "momentum_126d":
        out.sort(key=lambda d: d["mom126"], reverse=True)
    return out[: int(cfg.get("max_positions",100)) ]

def expected_return_for(sym: str, price: float, atr: float | None, cfg, er_map) -> float:
    mode = cfg.get("expected_return_mode","fixed")
    if mode == "file" and sym in er_map:
        return float(er_map[sym])
    if mode == "atr" and atr and price>0:
        return max(0.005, float(cfg.get("atr_k",1.2)) * (atr/price))
    return float(cfg.get("fixed_er_pct",0.02))

# --------------- Live logic -----------------
class LiveState:
    def __init__(self):
        self.positions: Dict[str, dict] = {}  # sym -> dict(entry, qty, stop_id, target_hit, er_level, trail_amt, orderIds)
        self.hedge: dict | None = None

async def place_entry_and_stop(ib: IB, journal: Journal, sym: str, qty: int, entry_type: str, entry_limit: float | None,
                               initial_stop: float, config: Dict[str, Any] = None) -> dict:
    c = Stock(sym, "SMART", "USD")
    # Entry
    if entry_type == "MKT" or entry_limit is None:
        entry_order = MarketOrder("BUY", qty)
    else:
        entry_order = LimitOrder("BUY", qty, entry_limit)
    trade = ib.placeOrder(c, entry_order)
    LOG.info("Placed entry %s x %s", sym, qty)
    
    # Track the pending buy order
    auto_track_buy_order(sym, qty, entry_type, entry_limit, "Entry order via live runner")
    
    await trade.filledEvent  # wait until filled
    fill_px = float(trade.orderStatus.avgFillPrice or trade.order.lmtPrice or 0.0)
    try:
        journal.trade(sym, 'BUY', qty, fill_px, 'entry', trade.order.orderId)
        # Mark as filled in our tracking
        auto_mark_buy_filled(sym, f"Filled at ${fill_px}")
    except Exception: pass

    # Initial stop as child
    stop_order = StopOrder("SELL", qty, round(initial_stop, 2))
    stop_order.parentId = trade.order.orderId
    stop_trade = ib.placeOrder(c, stop_order)
    try:
        journal.event(sym, 'initial_stop', {'stop': round(initial_stop,2)})
    except Exception: pass
    await asyncio.sleep(0.1)
    
    # Prepare position data for options protection
    position_data = {
        "contract": c, 
        "entry_trade": trade, 
        "stop_trade": stop_trade, 
        "entry_price": fill_px,
        "quantity": qty
    }
    
    # Apply options protection if enabled
    options_protection = None
    if config:
        options_protection = await apply_options_protection(ib, journal, position_data, config)
    
    position_data["options_protection"] = options_protection
    return position_data

async def modify_stop(ib: IB, journal: Journal, contract: Contract, stop_trade, new_stop: float, reason: str = 'raise_stop'):
    # Modify existing child stop
    try:
        o = stop_trade.order
        o.auxPrice = round(float(new_stop), 2)  # stopPrice
        ib.placeOrder(contract, o)
        LOG.info("Raised stop for %s -> %.2f (%s)", contract.symbol, float(new_stop), reason)
        try:
            journal.event(contract.symbol, reason, {'new_stop': round(float(new_stop),2)})
        except Exception: pass
    except Exception as e:
        LOG.warning("Failed to modify stop for %s: %s", contract.symbol, e)

async def apply_options_protection(ib: IB, journal: Journal, position_data: dict, config: Dict[str, Any]) -> dict | None:
    """Apply options protection to a newly opened position"""
    if not config.get('enable_options_protection', False):
        return None
    
    try:
        symbol = position_data['contract'].symbol
        position_value = position_data['entry_price'] * position_data.get('quantity', 0)
        
        # Initialize options protection manager
        backtest_config = BacktestConfig()  # Use default config
        protection_manager = OptionsProtectionManager(backtest_config)
        
        # Prepare position info for protection system
        positions = {
            symbol: {
                'price': position_data['entry_price'],
                'quantity': position_data.get('quantity', 0),
                'value': position_value
            }
        }
        
        # Implement protection (this returns protection details)
        protection_results = protection_manager.implement_comprehensive_protection(
            ib, positions, position_value
        )
        
        if protection_results and protection_results['individual_protection'].get(symbol):
            protection_info = protection_results['individual_protection'][symbol]
            cost = protection_info.get('cost', 0)
            protection_type = protection_info.get('type', 'unknown')
            
            LOG.info(f"Applied {protection_type} protection to {symbol}: cost ${cost:.2f}")
            journal.event(symbol, 'options_protection', {
                'type': protection_type,
                'cost': cost,
                'protection_level': protection_info.get('protection_level', 0)
            })
            
            return protection_results['individual_protection'][symbol]
            
    except Exception as e:
        LOG.warning(f"Failed to apply options protection to {symbol}: {e}")
        
    return None

async def monitor_options_protection(ib: IB, journal: Journal, symbol: str, position_data: dict, current_price: float, config: Dict[str, Any]):
    """Monitor and adjust options protection for active positions"""
    try:
        options_info = position_data.get("options_protection")
        if not options_info:
            return
        
        # Initialize options protection manager
        backtest_config = BacktestConfig()  # Use default config
        protection_manager = OptionsProtectionManager(backtest_config)
        
        # Monitor protection - this would check if adjustments are needed
        # For now, we'll just log the monitoring activity
        protection_type = options_info.get('type', 'unknown')
        protection_level = options_info.get('protection_level', 0)
        
        # Simple check: if stock has moved significantly from protection level
        if protection_level > 0:
            distance_from_protection = (current_price - protection_level) / protection_level
            
            if distance_from_protection > 0.1:  # 10% above protection
                LOG.debug(f"{symbol}: Stock well above protection level ({distance_from_protection:.1%})")
            elif distance_from_protection < -0.05:  # 5% below protection
                LOG.info(f"{symbol}: Stock approaching protection level ({distance_from_protection:.1%})")
                journal.event(symbol, 'options_protection_alert', {
                    'current_price': current_price,
                    'protection_level': protection_level,
                    'distance_pct': distance_from_protection
                })
    
    except Exception as e:
        LOG.warning(f"Error monitoring options protection for {symbol}: {e}")

async def open_spy_hedge(ib: IB, journal: Journal, alloc_usd: float, hedge_ratio: float) -> dict | None:
    spy = Stock("SPY","ARCA","USD")
    md = await ib.reqMktDataAsync(spy, "", False, False)
    px = float(md.last or md.close or 0.0)
    if px <= 0:
        return None
    notional = hedge_ratio * alloc_usd
    qty = max(1, int(notional / px))
    if qty <= 0:
        return None
    trade = ib.placeOrder(spy, MarketOrder("SELL", qty))
    
    # AUTOMATICALLY TRACK SPY HEDGE SELL ORDER
    auto_track_sell_order("SPY", qty, "MARKET", px, "SPY hedge - short position")
    
    await trade.filledEvent
    LOG.info("Opened SPY hedge qty=%s at ~%.2f", qty, float(trade.orderStatus.avgFillPrice or px))
    try:
        journal.trade('SPY','SELL',qty,float(trade.orderStatus.avgFillPrice or px),'open_hedge', trade.order.orderId)
    except Exception: pass
    return {"contract": spy, "qty": qty, "avg": float(trade.orderStatus.avgFillPrice or px)}

async def close_spy_hedge(ib: IB, journal: Journal, hedge: dict | None):
    if not hedge:
        return
    
    qty = int(hedge["qty"])
    # Track the pending buy to close hedge
    auto_track_buy_order("SPY", qty, "MARKET", notes="Close SPY hedge - cover short position")
    
    trade = ib.placeOrder(hedge["contract"], MarketOrder("BUY", qty))
    await trade.filledEvent
    LOG.info("Closed SPY hedge.")
    try:
        fill_price = float(trade.orderStatus.avgFillPrice or 0.0)
        journal.trade('SPY','BUY', qty, fill_price, 'close_hedge', trade.order.orderId)
        # Mark buy as filled in our tracking
        auto_mark_buy_filled("SPY", f"Hedge closed at ${fill_price}")
    except Exception: pass

async def monitor_loop(ib: IB, journal: Journal, cfg, state: LiveState, stop_event: asyncio.Event):
    """
    Polls quotes and applies:
    - ER protective stop (once last >= ER)
    - ATR/percent trailing ratchet (based on entry and ATR)
    """
    trailing_mode = cfg.get("trailing_mode","atr")
    trailing_pct  = float(cfg.get("trailing_pct",0.02))
    trailing_atr_mult = float(cfg.get("trailing_atr_mult",1.0))

    while not stop_event.is_set():
        for sym, p in list(state.positions.items()):
            c = p["contract"]
            md = await ib.reqMktDataAsync(c, "", False, False)
            last = float(md.last or md.close or 0.0)
            if last <= 0:
                await asyncio.sleep(0.05)
                continue

            # ER protective
            if (not p["target_hit"]) and last >= p["er_level"]:
                p["target_hit"] = True
                try:
                    journal.event(c.symbol, 'ER_hit', {'last': last, 'ER': p['er_level']})
                except Exception: pass
                # Raise stop to ER immediately
                await modify_stop(ib, journal, c, p["stop_trade"], p["er_level"], reason='protect_ER')

            # Options protection monitoring
            if p.get("options_protection") and cfg.get('enable_options_protection', False):
                await monitor_options_protection(ib, journal, sym, p, last, cfg)

            # Trailing ratchet
            candidate = None
            if trailing_mode == "percent":
                candidate = p["entry_price"] * (1 + trailing_pct)
            else:  # ATR-based
                if p["atr"] and p["atr"] > 0:
                    candidate = p["entry_price"] + trailing_atr_mult * p["atr"]
            if candidate and last >= candidate and candidate > p["trail_level"]:
                p["trail_level"] = candidate
                await modify_stop(ib, journal, c, p["stop_trade"], p["trail_level"], reason='trail_ratchet')

        await asyncio.sleep(2.0)  # poll interval

async def monday_entries(ib: IB, journal: Journal, cfg, tickers: list[str], state: LiveState):
    # Entry timing
    today = dt.datetime.now(tz=NY).date()
    monday = next_monday_trading_date(dt.datetime.now(tz=NY))
    if today != monday:
        LOG.info("Waiting for next Monday trading day: %s", monday.isoformat())

    entry_clock = dt.time(11,30) if cfg.get("entry_timing","delayed_2h")=="delayed_2h" else dt.time(9,30)
    target_dt = ny_datetime(monday, entry_clock.hour, entry_clock.minute)
    while dt.datetime.now(tz=NY) < target_dt:
        await asyncio.sleep(5)

    # Regime
    regime_ok = await spy_regime_ok(ib, cfg.get("regime_spy_ema", 50), cfg.get("max_vix", 0))
    hedge_flag = False
    if not regime_ok and not bool(cfg.get("enable_hedge", False)):
        LOG.info("Regime failed, enable_hedge=False => standing down this week.")
        return hedge_flag
    elif not regime_ok and bool(cfg.get("enable_hedge", False)):
        hedge_flag = True
        LOG.info("Regime failed, enable_hedge=True => will apply SPY hedge.")

    # Selection
    cands = await build_candidates(ib, cfg, tickers)
    er_map = load_expected_returns(cfg)

    cap = float(cfg.get("capital_per_trade", 10000.0))
    stop_mode = cfg.get("stop_mode","atr")
    stop_fixed_pct = float(cfg.get("stop_fixed_pct",0.01))
    stop_atr_mult = float(cfg.get("stop_atr_mult",1.5))

    total_alloc = 0.0
    for c in cands:
        sym, px, atr = c["symbol"], c["last_close"], c["atr"]
        er_pct = expected_return_for(sym, px, atr, cfg, er_map)
        qty = max(1, int(cap / px))

        # Initial stop
        if stop_mode == "fixed":
            stop_level = px * (1 - stop_fixed_pct)
        else:
            stop_level = px - stop_atr_mult * (atr or (0.01*px))

        # Place entry + stop
        res = await place_entry_and_stop(ib, journal, sym, qty, "MKT", None, stop_level, cfg)
        state.positions[sym] = {
            "contract": res["contract"],
            "entry_trade": res["entry_trade"],
            "stop_trade": res["stop_trade"],
            "entry_price": float(res["entry_price"] or px),
            "qty": qty,
            "atr": atr,
            "er_level": float(res["entry_price"] or px) * (1 + er_pct),
            "target_hit": False,
            "trail_level": float(stop_level),
        }
        total_alloc += cap
        await asyncio.sleep(0.2)

    # Hedge
    if hedge_flag and total_alloc > 0:
        h = await open_spy_hedge(ib, journal, total_alloc, float(cfg.get("hedge_ratio",1.0)))
        state.hedge = h

    return hedge_flag

async def friday_exit_all(ib: IB, journal: Journal, state: LiveState):
    today_ny = dt.datetime.now(tz=NY).date()
    # figure out the current week monday, then friday
    # but simpler: find next Friday after today if today < Friday; otherwise if Friday, use today.
    # However, we started Monday; store monday? We'll recompute based on Monday of this week.
    wd = today_ny.weekday()
    monday = today_ny - dt.timedelta(days=wd)
    friday = friday_of_week(monday)

    # wait until ~15:55 NY
    target_dt = ny_datetime(friday, 15, 55)
    while dt.datetime.now(tz=NY) < target_dt:
        await asyncio.sleep(10)

    # Flatten
    for sym, p in list(state.positions.items()):
        # cancel stop first (IBKR will cancel automatically if using parent/child OCO, but be explicit)
        try:
            ib.cancelOrder(p["stop_trade"].order)
            await asyncio.sleep(0.05)
        except Exception:
            pass
        # market sell
        trade = ib.placeOrder(p["contract"], MarketOrder("SELL", int(p["qty"])))
        
        # AUTOMATICALLY TRACK THIS SELL ORDER IN OUR SYSTEM
        auto_track_sell_order(sym, int(p["qty"]), "MARKET", notes="Friday close - auto exit")
        
        await trade.filledEvent
        try:
            px = float(trade.orderStatus.avgFillPrice or 0.0)
            journal.trade(sym,'SELL',int(p['qty']), px, 'friday_close', trade.order.orderId)
            
            # Mark as sold in our tracking system once filled
            if PENDING_TRACKING_AVAILABLE:
                try:
                    pending_tracker.mark_as_sold(sym, f"Friday close filled at ${px:.2f}")
                    LOG.info(f"📊 Marked {sym} as sold in tracking system")
                except Exception: pass
                    
        except Exception: pass
        LOG.info("Closed %s", sym)
        await asyncio.sleep(0.1)
    state.positions.clear()

    # Close hedge if any
    if state.hedge:
        await close_spy_hedge(ib, journal, state.hedge)
        state.hedge = None

async def run_week_cycle():
    cfg = load_config()
    tickers = load_universe(cfg)

    ib = await connect_ib(cfg)
    try:
        state = LiveState()
        journal = Journal(BASE)
        # Monday entries (& hedge)
        await monday_entries(ib, journal, cfg, tickers, state)

        # Monitor through the week until Friday close
        stop_event = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_loop(ib, journal, cfg, state, stop_event))
        await friday_exit_all(ib, journal, state)
        stop_event.set()
        try:
            await monitor_task
        except Exception:
            pass
    finally:
        ib.disconnect()

if __name__ == "__main__":
    util.startLoop()
    asyncio.run(run_week_cycle())
