#!/usr/bin/env python3
"""
Pending Orders Tracker - Track our own buy/sell orders since IBKR API can't see them reliably
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class PendingSalesTracker:
    """Track pending buy and sell orders in our own system"""
    
    def __init__(self, file_path: str = "pending_sales.json"):
        self.file_path = file_path
        self.pending_sales = self.load_pending_sales()
    
    def load_pending_sales(self) -> Dict:
        """Load pending sales from JSON file"""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            print(f"Error loading pending sales: {e}")
            return {}
    
    def save_pending_sales(self):
        """Save pending sales to JSON file"""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.pending_sales, f, indent=2)
        except Exception as e:
            print(f"Error saving pending sales: {e}")
    
    def mark_as_pending_sale(self, symbol: str, quantity: int, order_type: str = "MARKET", price: Optional[float] = None, notes: str = ""):
        """Mark a stock as pending sale"""
        timestamp = datetime.now().isoformat()
        
        self.pending_sales[symbol] = {
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "timestamp": timestamp,
            "notes": notes,
            "status": "PENDING_SALE",
            "action": "SELL"
        }
        
        self.save_pending_sales()
        return f"Marked {symbol} ({quantity} shares) as pending sale"
    
    def mark_as_pending_buy(self, symbol: str, quantity: int, order_type: str = "MARKET", price: Optional[float] = None, notes: str = ""):
        """Mark a stock as pending buy"""
        timestamp = datetime.now().isoformat()
        
        self.pending_sales[symbol] = {
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "timestamp": timestamp,
            "notes": notes,
            "status": "PENDING_BUY",
            "action": "BUY"
        }
        
        self.save_pending_sales()
        return f"Marked {symbol} ({quantity} shares) as pending buy"
    
    def mark_as_sold(self, symbol: str, notes: str = ""):
        """Mark a stock as sold (remove from pending)"""
        if symbol in self.pending_sales:
            del self.pending_sales[symbol]
            self.save_pending_sales()
            return f"Removed {symbol} from pending orders (marked as sold)"
        return f"{symbol} was not in pending orders"
    
    def mark_as_bought(self, symbol: str, notes: str = ""):
        """Mark a stock as bought (remove from pending)"""
        if symbol in self.pending_sales:
            del self.pending_sales[symbol]
            self.save_pending_sales()
            return f"Removed {symbol} from pending orders (marked as bought)"
        return f"{symbol} was not in pending orders"
    
    def mark_as_filled(self, symbol: str, notes: str = ""):
        """Mark any order as filled (remove from pending) - generic method"""
        if symbol in self.pending_sales:
            action = self.pending_sales[symbol].get('action', 'UNKNOWN')
            del self.pending_sales[symbol]
            self.save_pending_sales()
            return f"Removed {symbol} from pending orders (marked as filled - {action})"
        return f"{symbol} was not in pending orders"
    
    def is_pending_sale(self, symbol: str) -> bool:
        """Check if a stock is pending sale"""
        return symbol in self.pending_sales and self.pending_sales[symbol].get('action') == 'SELL'
    
    def is_pending_buy(self, symbol: str) -> bool:
        """Check if a stock is pending buy"""
        return symbol in self.pending_sales and self.pending_sales[symbol].get('action') == 'BUY'
    
    def is_pending_order(self, symbol: str) -> bool:
        """Check if a stock has any pending order"""
        return symbol in self.pending_sales
    
    def get_pending_sale_info(self, symbol: str) -> Optional[Dict]:
        """Get pending sale info for a symbol"""
        info = self.pending_sales.get(symbol)
        if info and info.get('action') == 'SELL':
            return info
        return None
    
    def get_pending_buy_info(self, symbol: str) -> Optional[Dict]:
        """Get pending buy info for a symbol"""
        info = self.pending_sales.get(symbol)
        if info and info.get('action') == 'BUY':
            return info
        return None
    
    def get_pending_order_info(self, symbol: str) -> Optional[Dict]:
        """Get pending order info for a symbol (buy or sell)"""
        return self.pending_sales.get(symbol)
    
    def get_all_pending_sales(self) -> Dict:
        """Get all pending sales"""
        return {k: v for k, v in self.pending_sales.items() if v.get('action') == 'SELL'}
    
    def get_all_pending_buys(self) -> Dict:
        """Get all pending buys"""
        return {k: v for k, v in self.pending_sales.items() if v.get('action') == 'BUY'}
    
    def get_all_pending_orders(self) -> Dict:
        """Get all pending orders (buys and sells)"""
        return self.pending_sales.copy()
    
    def clear_all_pending_sales(self):
        """Clear all pending orders (emergency reset)"""
        self.pending_sales = {}
        self.save_pending_sales()
        return "Cleared all pending orders"
    
    def get_pending_count(self) -> int:
        """Get count of all pending orders"""
        return len(self.pending_sales)
    
    def get_pending_sales_count(self) -> int:
        """Get count of pending sales"""
        return len([v for v in self.pending_sales.values() if v.get('action') == 'SELL'])
    
    def get_pending_buys_count(self) -> int:
        """Get count of pending buys"""
        return len([v for v in self.pending_sales.values() if v.get('action') == 'BUY'])

# Global instance
pending_tracker = PendingSalesTracker()

def mark_pending_sale(symbol: str, quantity: int, **kwargs) -> str:
    """Convenience function to mark pending sale"""
    return pending_tracker.mark_as_pending_sale(symbol, quantity, **kwargs)

def mark_pending_buy(symbol: str, quantity: int, **kwargs) -> str:
    """Convenience function to mark pending buy"""
    return pending_tracker.mark_as_pending_buy(symbol, quantity, **kwargs)

def mark_sold(symbol: str, **kwargs) -> str:
    """Convenience function to mark as sold"""
    return pending_tracker.mark_as_sold(symbol, **kwargs)

def mark_bought(symbol: str, **kwargs) -> str:
    """Convenience function to mark as bought"""
    return pending_tracker.mark_as_bought(symbol, **kwargs)

def mark_filled(symbol: str, **kwargs) -> str:
    """Convenience function to mark order as filled"""
    return pending_tracker.mark_as_filled(symbol, **kwargs)

def is_pending_sale(symbol: str) -> bool:
    """Convenience function to check pending sale"""
    return pending_tracker.is_pending_sale(symbol)

def is_pending_buy(symbol: str) -> bool:
    """Convenience function to check pending buy"""
    return pending_tracker.is_pending_buy(symbol)

def is_pending_order(symbol: str) -> bool:
    """Convenience function to check any pending order"""
    return pending_tracker.is_pending_order(symbol)

def get_pending_sales() -> Dict:
    """Convenience function to get all pending sales"""
    return pending_tracker.get_all_pending_sales()

def get_pending_buys() -> Dict:
    """Convenience function to get all pending buys"""
    return pending_tracker.get_all_pending_buys()

def get_pending_orders() -> Dict:
    """Convenience function to get all pending orders"""
    return pending_tracker.get_all_pending_orders()

if __name__ == "__main__":
    # Test the tracker
    tracker = PendingSalesTracker()
    
    print("Testing Pending Sales Tracker:")
    print(tracker.mark_as_pending_sale("AAPL", 100, "MARKET", notes="Test order"))
    print(tracker.mark_as_pending_sale("GOOGL", 50, "LIMIT", 150.00, "Limit order test"))
    
    print(f"\nPending sales: {tracker.get_all_pending_sales()}")
    print(f"AAPL pending: {tracker.is_pending_sale('AAPL')}")
    print(f"MSFT pending: {tracker.is_pending_sale('MSFT')}")
    
    print(tracker.mark_as_sold("AAPL", "Sold successfully"))
    print(f"After selling AAPL: {tracker.get_all_pending_sales()}")