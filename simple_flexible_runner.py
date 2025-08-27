#!/usr/bin/env python3
"""
Simple Flexible Live Trading Runner (No Unicode Issues)
"""

import os, json, asyncio, logging
import datetime as dt
from typing import Dict, Any
from pathlib import Path
import pandas as pd
import pytz
from ib_insync import IB, Stock, MarketOrder, StopOrder

BASE = Path(__file__).resolve().parent
NY = pytz.timezone('America/New_York')
LOG = logging.getLogger("flexible")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

class Journal:
    def __init__(self, base_dir: Path):
        self.base = base_dir / "logs"
        self.base.mkdir(parents=True, exist_ok=True)
        self.trade_path = self.base / "trade_journal.csv"
        if not self.trade_path.exists():
            self.trade_path.write_text("ts,symbol,side,qty,price,reason,orderId\n")

    def trade(self, symbol, side, qty, price, reason, orderId=None):
        from datetime import datetime
        ts = datetime.now(tz=NY).isoformat()
        line = f"{ts},{symbol},{side},{qty},{price},{reason},{orderId or ''}\n"
        with self.trade_path.open("a") as f:
            f.write(line)

def load_config() -> Dict[str, Any]:
    return json.load(open(BASE/"config.json","r"))

async def connect_ib(cfg) -> IB:
    ib = IB()
    await ib.connectAsync(cfg.get("ib_host","127.0.0.1"),
                          int(cfg.get("ib_port",7497)),
                          clientId=int(cfg.get("ib_client_id",7)))
    return ib

def print_menu():
    now = dt.datetime.now(tz=NY)
    print("\n" + "="*50)
    print("FLEXIBLE WEEKLY ER TRADING SYSTEM")
    print("="*50)
    print(f"NY Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Market: {'OPEN' if 9.5 <= now.hour + now.minute/60 <= 16 and now.weekday() < 5 else 'CLOSED'}")
    
    print("\nOPTIONS:")
    print("1. Monitor Positions")
    print("2. Close All Positions") 
    print("3. System Status")
    print("4. Exit")
    print("-" * 50)

async def get_positions(ib: IB) -> Dict[str, dict]:
    positions = {}
    try:
        portfolio_items = ib.portfolio()
        for item in portfolio_items:
            if item.position != 0:
                symbol = item.contract.symbol
                positions[symbol] = {
                    'contract': item.contract,
                    'quantity': int(item.position),
                    'market_price': float(item.marketPrice),
                    'market_value': float(item.marketValue),
                    'unrealized_pnl': float(item.unrealizedPNL),
                }
        return positions
    except Exception as e:
        print(f"Error getting positions: {e}")
        return {}

def show_positions(positions: Dict[str, dict]):
    if not positions:
        print("No active positions")
        return
    
    print(f"\nACTIVE POSITIONS ({len(positions)}):")
    print("-" * 60)
    print(f"{'Symbol':<8} {'Qty':<6} {'Price':<10} {'Value':<12} {'P&L':<10}")
    print("-" * 60)
    
    total_value = 0
    total_pnl = 0
    
    for symbol, pos in positions.items():
        qty = pos['quantity']
        price = pos['market_price']
        value = pos['market_value']
        pnl = pos['unrealized_pnl']
        
        total_value += value
        total_pnl += pnl
        
        print(f"{symbol:<8} {qty:<6} ${price:<9.2f} ${value:<11.2f} ${pnl:<9.2f}")
    
    print("-" * 60)
    print(f"{'TOTAL':<21} ${total_value:<11.2f} ${total_pnl:<9.2f}")

async def monitor_positions(ib: IB):
    print("\nMONITOR MODE (Ctrl+C to exit)")
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("POSITION MONITOR")
            positions = await get_positions(ib)
            show_positions(positions)
            print(f"\nLast updated: {dt.datetime.now(tz=NY).strftime('%H:%M:%S')}")
            print("Press Ctrl+C to return to menu")
            await asyncio.sleep(30)
    except KeyboardInterrupt:
        print("\nExiting monitor...")

async def close_all_positions(ib: IB, journal: Journal):
    print("\nCLOSE ALL POSITIONS")
    
    positions = await get_positions(ib)
    if not positions:
        print("No positions to close")
        return
    
    show_positions(positions)
    confirm = input(f"\nClose ALL {len(positions)} positions? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Close cancelled")
        return
    
    print("\nClosing positions...")
    
    for symbol, pos in positions.items():
        try:
            contract = pos['contract']
            qty = abs(int(pos['quantity']))
            
            # Cancel existing orders
            orders = ib.openOrders()
            for order in orders:
                if order.contract.symbol == symbol:
                    ib.cancelOrder(order)
                    await asyncio.sleep(0.1)
            
            # Place market sell
            if qty > 0:
                trade = ib.placeOrder(contract, MarketOrder("SELL", qty))
                await trade.filledEvent
                
                fill_price = float(trade.orderStatus.avgFillPrice or 0.0)
                journal.trade(symbol, 'SELL', qty, fill_price, 'manual_close', trade.order.orderId)
                print(f"Closed {symbol}: {qty} shares @ ${fill_price:.2f}")
                await asyncio.sleep(0.2)
        
        except Exception as e:
            print(f"Error closing {symbol}: {e}")
    
    print("\nAll positions closed!")

async def show_status(ib: IB):
    print("\nSYSTEM STATUS")
    print("-" * 30)
    print(f"IBKR Connection: {'Connected' if ib.isConnected() else 'Disconnected'}")
    
    if ib.isConnected():
        positions = await get_positions(ib)
        print(f"Active Positions: {len(positions)}")
        
        # Account info
        try:
            account_values = ib.accountValues()
            net_liq = next((v.value for v in account_values if v.tag == 'NetLiquidation'), 'N/A')
            print(f"Net Liquidation: ${net_liq}")
        except:
            print("Account info: Unable to retrieve")
    
    input("\nPress Enter to continue...")

async def main():
    print("Starting system...")
    cfg = load_config()
    ib = await connect_ib(cfg)
    journal = Journal(BASE)
    
    if not ib.isConnected():
        print("Failed to connect to IBKR")
        print("Make sure TWS/Gateway is running")
        input("Press Enter to exit...")
        return
    
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print_menu()
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                await monitor_positions(ib)
            
            elif choice == "2":
                await close_all_positions(ib, journal)
                input("Press Enter to continue...")
            
            elif choice == "3":
                await show_status(ib)
            
            elif choice == "4":
                print("Exiting...")
                break
            
            else:
                print("Invalid choice. Select 1-4.")
                await asyncio.sleep(1)
    
    finally:
        ib.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")