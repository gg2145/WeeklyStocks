#!/usr/bin/env python3
"""
Reliable Trading System Launcher
Simplified version that avoids hanging issues
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Launch the trading system with reliability checks"""
    print("=" * 60)
    print("WEEKLY ER TRADING SYSTEM - RELIABLE EDITION")
    print("=" * 60)
    print("Loading reliable interface...")
    print("Features:")
    print("  [*] Professional backtesting with interactive charts")
    print("  [*] Live trading controls and monitoring")
    print("  [*] IBKR connection testing and setup")
    print("  [*] Reliable startup without hanging")
    print("-" * 60)
    
    # Add current directory to path
    sys.path.append(str(Path(__file__).parent))
    
    try:
        print("Starting PyQt6 application...")
        
        # Import with timeout protection
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Import timeout")
        
        # Set a timeout for imports (Windows doesn't support SIGALRM, so we'll skip this)
        try:
            from PyQt6.QtWidgets import QApplication
            print("✅ PyQt6 imported successfully")
            
            from backtest_app import BacktestApp
            print("✅ BacktestApp imported successfully")
            
            print("Creating application...")
            app = QApplication(sys.argv)
            print("✅ QApplication created")
            
            print("Creating main window...")
            window = BacktestApp()
            print("✅ BacktestApp window created")
            
            print("Showing window...")
            window.show()
            print("✅ Window shown")
            
            print("Starting event loop...")
            print("🚀 Trading system is now running!")
            print("💡 If the system becomes unresponsive, press Ctrl+C to exit")
            
            # Run the application
            sys.exit(app.exec())
            
        except KeyboardInterrupt:
            print("\n⚠️ User interrupted startup")
            sys.exit(0)
            
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print("\nPossible solutions:")
        print("1. Install PyQt6: pip install PyQt6")
        print("2. Install matplotlib: pip install matplotlib")
        print("3. Install ib-insync: pip install ib-insync")
        print("\nFallback options:")
        print("1. Direct position monitoring: python simple_working_monitor.py")
        print("2. Professional monitor: python professional_position_monitor.py")
        print("3. Fix pending positions: python fix_pending_positions.py")
        input("Press Enter to exit...")
        sys.exit(1)
        
    except Exception as e:
        print(f"[ERROR] Error launching system: {e}")
        import traceback
        traceback.print_exc()
        print("\nFallback options:")
        print("1. Direct position monitoring: python simple_working_monitor.py")
        print("2. Professional monitor: python professional_position_monitor.py")
        print("3. Fix pending positions: python fix_pending_positions.py")
        print("4. Simple backtest: python backtest_core.py")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
