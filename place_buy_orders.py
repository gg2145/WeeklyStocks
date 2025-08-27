#!/usr/bin/env python3
"""
Direct buy order placement - bypassing the monitor
"""

import json
from ib_insync import IB, Stock, MarketOrder
from pending_sales import pending_tracker

def place_pending_buy_orders():
    """Place all pending buy orders directly in IBKR"""
    
    # Get config
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
    except:
        config = {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 1}
    
    host = config.get("ib_host", "127.0.0.1")
    port = int(config.get("ib_port", 7497))
    client_id = int(config.get("ib_client_id", 1)) + 30  # Use +30 to avoid conflicts
    
    # Get pending buy orders
    pending_buys = pending_tracker.get_all_pending_buys()
    
    if not pending_buys:
        print("No pending buy orders found")
        return
    
    print(f"Found {len(pending_buys)} pending buy orders:")
    for symbol, info in pending_buys.items():
        qty = info['quantity']
        print(f"  BUY {symbol}: {qty} shares")
    
    # Connect to IBKR
    print(f"\\nConnecting to IBKR at {host}:{port} with client ID {client_id}...")
    
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id, timeout=10)
        
        if not ib.isConnected():
            print("❌ Failed to connect to IBKR")
            return
        
        print("✅ Connected to IBKR")
        
        # Place each buy order
        for symbol, info in pending_buys.items():
            try:
                qty = info['quantity']
                
                print(f"\\nPlacing BUY order: {qty} shares of {symbol}")
                
                # Create contract and order
                contract = Stock(symbol, 'SMART', 'USD')
                order = MarketOrder('BUY', qty)
                
                # Place order
                trade = ib.placeOrder(contract, order)
                
                print(f"✅ Order placed for {symbol}: {qty} shares")
                print(f"   Order ID: {trade.order.orderId}")
                print(f"   Status: {trade.orderStatus.status}")
                
            except Exception as e:
                print(f"❌ Error placing order for {symbol}: {e}")
        
        print(f"\\n🎯 Buy order placement complete!")
        print(f"Check your IBKR account to confirm orders are submitted.")
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("\\nDisconnected from IBKR")

if __name__ == "__main__":
    place_pending_buy_orders()