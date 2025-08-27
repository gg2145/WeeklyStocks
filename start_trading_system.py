#!/usr/bin/env python3
"""
Main Launcher for Weekly ER Trading System
Professional entry point for complete trading platform
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Launch the modern tabbed GUI trading system"""
    print("=" * 60)
    print("WEEKLY ER TRADING SYSTEM - MODERN EDITION")
    print("=" * 60)
    print("Loading modern tabbed interface...")
    print("Features:")
    print("  [*] Professional backtesting with interactive charts")
    print("  [*] Live trading controls and monitoring")
    print("  [*] IBKR connection testing and setup")
    print("  [*] Complete trading workflow management")
    print("  [*] Modern tabbed interface with all tools")
    print("-" * 60)
    
    # Add current directory to path
    sys.path.append(str(Path(__file__).parent))
    
    try:
        # Import and launch the GUI directly (not as subprocess)
        print("DEBUG: About to import PyQt6...")
        from PyQt6.QtWidgets import QApplication
        print("DEBUG: PyQt6 imported successfully")
        
        print("DEBUG: About to import BacktestApp...")
        from backtest_app import BacktestApp
        print("DEBUG: BacktestApp imported successfully")
        
        print("DEBUG: Creating QApplication...")
        app = QApplication(sys.argv)
        print("DEBUG: QApplication created")
        
        print("DEBUG: Creating BacktestApp window...")
        window = BacktestApp()
        print("DEBUG: BacktestApp window created")
        
        print("DEBUG: Showing window...")
        window.show()
        print("DEBUG: Window shown, starting event loop...")
        
        # Run the application
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print("Make sure PyQt6 is installed: pip install PyQt6")
        print("\nFallback options:")
        print("1. Direct position monitoring: python simple_flexible_runner.py")
        print("2. IBKR setup: python setup_live_trading.py") 
        print("3. System monitoring: python system_monitor.py")
        input("Press Enter to exit...")
        sys.exit(1)
        
    except Exception as e:
        print(f"[ERROR] Error launching modern GUI: {e}")
        import traceback
        traceback.print_exc()
        print("\nFallback options:")
        print("1. Direct position monitoring: python simple_flexible_runner.py")
        print("2. IBKR setup: python setup_live_trading.py") 
        print("3. System monitoring: python system_monitor.py")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()