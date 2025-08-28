#!/usr/bin/env python3
"""
Fix Pending Positions - Clean up mismatch between IBKR positions and pending orders
"""

import json
from datetime import datetime
from pending_sales import pending_tracker

try:
    from ib_insync import IB
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("WARNING: ib-insync not available - will show pending orders only")

def get_ibkr_positions():
    """Get current positions from IBKR"""
    if not IB_AVAILABLE:
        return {}
    
    try:
        # Load config
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        host = config.get("ib_host", "127.0.0.1")
        port = int(config.get("ib_port", 7497))
        client_id = int(config.get("ib_client_id", 1)) + 50  # Use +50 to avoid conflicts
        
        print(f"Connecting to IBKR at {host}:{port} with client ID {client_id}")
        
        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=10)
        
        if not ib.isConnected():
            print("Failed to connect to IBKR")
            return {}
        
        # Get portfolio positions
        portfolio = ib.portfolio()
        positions = {}
        
        for item in portfolio:
            if item.position != 0:
                symbol = item.contract.symbol
                quantity = int(item.position)
                positions[symbol] = quantity
                print(f"IBKR Position: {symbol} = {quantity} shares")
        
        ib.disconnect()
        print(f"Found {len(positions)} positions in IBKR")
        return positions
        
    except Exception as e:
        print(f"Error getting IBKR positions: {e}")
        return {}

def analyze_pending_vs_actual():
    """Analyze pending orders vs actual positions"""
    print("=" * 60)
    print("PENDING POSITIONS ANALYSIS")
    print("=" * 60)
    
    # Get current data
    ibkr_positions = get_ibkr_positions()
    pending_sales = pending_tracker.get_all_pending_sales()
    pending_buys = pending_tracker.get_all_pending_buys()
    
    print(f"\nIBKR Positions ({len(ibkr_positions)}):")
    for symbol, qty in sorted(ibkr_positions.items()):
        print(f"  {symbol}: {qty} shares")
    
    print(f"\nPending Sales ({len(pending_sales)}):")
    for symbol, info in sorted(pending_sales.items()):
        qty = info['quantity']
        timestamp = info['timestamp'][:19]  # Remove microseconds
        print(f"  {symbol}: {qty} shares (marked {timestamp})")
    
    print(f"\nPending Buys ({len(pending_buys)}):")
    for symbol, info in sorted(pending_buys.items()):
        qty = info['quantity']
        timestamp = info['timestamp'][:19]
        print(f"  {symbol}: {qty} shares (marked {timestamp})")
    
    # Analysis
    print("\n" + "=" * 60)
    print("MISMATCH ANALYSIS")
    print("=" * 60)
    
    issues_found = []
    
    # Check pending sales that are still in portfolio
    for symbol in pending_sales:
        if symbol in ibkr_positions:
            issues_found.append(f"❌ {symbol}: Marked for SALE but still in portfolio ({ibkr_positions[symbol]} shares)")
    
    # Check pending buys that are now in portfolio
    for symbol in pending_buys:
        if symbol in ibkr_positions:
            issues_found.append(f"❌ {symbol}: Marked for BUY but already in portfolio ({ibkr_positions[symbol]} shares)")
    
    # Check positions not in pending
    for symbol in ibkr_positions:
        if symbol not in pending_sales and symbol not in pending_buys:
            issues_found.append(f"✅ {symbol}: In portfolio, no pending orders (OK)")
    
    if issues_found:
        print("\nIssues found:")
        for issue in issues_found:
            print(f"  {issue}")
    else:
        print("\n✅ No mismatches found!")
    
    return len([i for i in issues_found if i.startswith("❌")])

def fix_mismatches(auto_fix=False):
    """Fix the mismatches"""
    print("\n" + "=" * 60)
    print("FIXING MISMATCHES")
    print("=" * 60)
    
    ibkr_positions = get_ibkr_positions()
    pending_sales = pending_tracker.get_all_pending_sales()
    pending_buys = pending_tracker.get_all_pending_buys()
    
    fixes_applied = []
    
    # Fix pending sales that are still in portfolio (orders didn't execute)
    for symbol in pending_sales:
        if symbol in ibkr_positions:
            if auto_fix:
                pending_tracker.mark_as_filled(symbol, "Auto-fix: Still in portfolio, removing pending sale")
                fixes_applied.append(f"✅ Removed {symbol} from pending sales (still in portfolio)")
            else:
                print(f"Would remove {symbol} from pending sales (still in portfolio)")
    
    # Fix pending buys that are now in portfolio (orders executed)
    for symbol in pending_buys:
        if symbol in ibkr_positions:
            if auto_fix:
                pending_tracker.mark_as_filled(symbol, "Auto-fix: Now in portfolio, removing pending buy")
                fixes_applied.append(f"✅ Removed {symbol} from pending buys (now in portfolio)")
            else:
                print(f"Would remove {symbol} from pending buys (now in portfolio)")
    
    if auto_fix:
        print(f"\nApplied {len(fixes_applied)} fixes:")
        for fix in fixes_applied:
            print(f"  {fix}")
    else:
        print(f"\nWould apply {len(fixes_applied)} fixes. Run with --fix to apply them.")
    
    return len(fixes_applied)

def main():
    """Main function"""
    import sys
    
    print("Fix Pending Positions Utility")
    print("Analyzes and fixes mismatches between IBKR positions and pending orders")
    print()
    
    # Analyze first
    mismatch_count = analyze_pending_vs_actual()
    
    if mismatch_count == 0:
        print("\n🎉 No issues found! Your pending orders are in sync.")
        return
    
    print(f"\n⚠️  Found {mismatch_count} mismatches.")
    
    # Check if user wants to fix
    if "--fix" in sys.argv or "--auto-fix" in sys.argv:
        print("\nApplying fixes...")
        fixes_applied = fix_mismatches(auto_fix=True)
        print(f"\n✅ Applied {fixes_applied} fixes!")
        
        # Re-analyze to confirm
        print("\nRe-analyzing after fixes...")
        final_mismatch_count = analyze_pending_vs_actual()
        
        if final_mismatch_count == 0:
            print("\n🎉 All issues resolved!")
        else:
            print(f"\n⚠️  {final_mismatch_count} issues remain.")
    else:
        print("\nTo fix these issues, run:")
        print("  python fix_pending_positions.py --fix")
        
        # Show what would be fixed
        fix_mismatches(auto_fix=False)

if __name__ == "__main__":
    main()
