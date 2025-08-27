#!/usr/bin/env python3
"""
Quick script to find which client ID has your pending sell orders
"""

import json
from ib_insync import IB

def load_config():
    try:
        with open("config.json", 'r') as f:
            return json.load(f)
    except:
        return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}

def test_client_id(client_id, host="127.0.0.1", port=7497):
    """Test a specific client ID for orders"""
    try:
        print(f"Testing client ID {client_id}...")
        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=5)
        
        if ib.isConnected():
            # Get orders
            orders = ib.openOrders()
            all_orders = ib.reqAllOpenOrders()
            trades = ib.trades()
            
            print(f"   Connected with client ID {client_id}")
            print(f"   openOrders(): {len(orders)} orders")
            print(f"   reqAllOpenOrders(): {len(all_orders)} orders") 
            print(f"   trades(): {len(trades)} trades")
            
            # Look for sell orders specifically
            sell_orders = [o for o in orders if o.order.action == 'SELL']
            sell_trades = [t for t in trades if t.order.action == 'SELL']
            
            if sell_orders or sell_trades:
                print(f"   *** FOUND {len(sell_orders)} SELL ORDERS! ***")
                for order in sell_orders:
                    print(f"      SELL: {order.contract.symbol} - {order.order.totalQuantity} shares ({order.orderStatus.status})")
                for trade in sell_trades:
                    print(f"      SELL TRADE: {trade.contract.symbol} - {trade.order.totalQuantity} shares ({trade.orderStatus.status})")
                return client_id
            else:
                print(f"   No sell orders found with client ID {client_id}")
            
            ib.disconnect()
        else:
            print(f"   Failed to connect with client ID {client_id}")
            
    except Exception as e:
        print(f"   Error with client ID {client_id}: {e}")
    
    return None

def main():
    config = load_config()
    host = config.get("ib_host", "127.0.0.1")
    port = int(config.get("ib_port", 7497))
    
    print(f"Searching for your sell orders on {host}:{port}...")
    print(f"Testing multiple client IDs to find where your orders are...")
    
    # Test common client IDs
    client_ids_to_test = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    found_client_id = None
    for client_id in client_ids_to_test:
        result = test_client_id(client_id, host, port)
        if result:
            found_client_id = result
            break
    
    if found_client_id:
        print(f"\n*** SUCCESS! Your sell orders are with CLIENT ID {found_client_id} ***")
        print(f"Update your monitor to use client ID {found_client_id} instead of {config.get('ib_client_id', 7)}")
    else:
        print(f"\nNo sell orders found with any client ID 0-10")
        print(f"Are you sure there are pending sell orders in IBKR?")

if __name__ == "__main__":
    main()