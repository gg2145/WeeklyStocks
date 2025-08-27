#!/usr/bin/env python3
"""
Simple test of monitor refresh logic without GUI
"""

from pending_sales import pending_tracker

def test_monitor_logic():
    print("=== TESTING MONITOR LOGIC ===")
    
    # Test pending sales detection
    print(f"1. Total pending orders: {pending_tracker.get_pending_count()}")
    
    pending_sales = pending_tracker.get_all_pending_sales()
    pending_buys = pending_tracker.get_all_pending_buys()
    
    print(f"2. Pending sales: {len(pending_sales)}")
    print(f"3. Pending buys: {len(pending_buys)}")
    
    # Test each symbol
    test_symbols = ['CNC', 'ENPH', 'INTC', 'SIRI', 'VTRS']
    
    for symbol in test_symbols:
        has_pending_sells = pending_tracker.is_pending_sale(symbol)
        has_pending_buys = pending_tracker.is_pending_buy(symbol)
        
        print(f"4. {symbol}:")
        print(f"   - is_pending_sale: {has_pending_sells}")
        print(f"   - is_pending_buy: {has_pending_buys}")
        
        if has_pending_sells:
            print(f"   ✅ Should show PENDING SALE status")
        elif has_pending_buys:
            print(f"   ✅ Should show PENDING BUY status")
        else:
            print(f"   ✅ Should show Open status")

if __name__ == "__main__":
    test_monitor_logic()