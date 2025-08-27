#!/usr/bin/env python3
"""
Quick tool to mark existing stocks as pending sales
Use this to mark your current IBKR pending orders in our tracking system
"""

from pending_sales import pending_tracker

def mark_existing_pending_sales():
    """Mark your current IBKR pending sales in our system"""
    
    print("=== MARK EXISTING PENDING SALES ===")
    print("Use this to add your current IBKR pending sell orders to our tracking system")
    print()
    
    # Your current positions that have pending sells in IBKR
    # Update this list based on what you see in IBKR
    pending_positions = [
        {"symbol": "CNC", "quantity": 1028},
        {"symbol": "ENPH", "quantity": 279}, 
        {"symbol": "INTC", "quantity": 422},
        {"symbol": "SIRI", "quantity": 874},
        {"symbol": "VTRS", "quantity": 1876},
    ]
    
    print(f"Found {len(pending_positions)} positions to mark as pending sales:")
    for pos in pending_positions:
        print(f"  - {pos['symbol']}: {pos['quantity']} shares")
    
    print()
    confirm = input("Mark all these as PENDING SALES in our tracking system? (y/n): ")
    
    if confirm.lower() == 'y':
        for pos in pending_positions:
            result = pending_tracker.mark_as_pending_sale(
                pos['symbol'], 
                pos['quantity'], 
                "MARKET",  # Assume market orders
                notes="Existing IBKR order marked via script"
            )
            print(f"✅ {result}")
        
        print(f"\n🎯 SUCCESS! Marked {len(pending_positions)} stocks as pending sales")
        print("Now when you open the Position Monitor, these will show as BRIGHT RED!")
        
        # Show current status
        print(f"\nCurrent pending sales in our system:")
        all_pending = pending_tracker.get_all_pending_sales()
        for symbol, info in all_pending.items():
            qty = info['quantity']
            timestamp = info['timestamp'][:19]
            print(f"  🚨 {symbol}: {qty} shares (since {timestamp})")
            
    else:
        print("Cancelled - no changes made")

if __name__ == "__main__":
    mark_existing_pending_sales()