#!/usr/bin/env python3
"""
Simple Trading System Menu
No GUI hanging issues - direct access to all tools
"""

import sys
import subprocess
import os
from pathlib import Path

def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_menu():
    """Display the main menu"""
    clear_screen()
    print("=" * 60)
    print("WEEKLY ER TRADING SYSTEM - SIMPLE MENU")
    print("=" * 60)
    print()
    print("📊 POSITION MONITORING:")
    print("  1. Professional Position Monitor")
    print("  2. Simple Position Monitor")
    print("  3. Fix Pending Positions")
    print()
    print("📈 BACKTESTING:")
    print("  4. Run Backtest (Core Engine)")
    print("  5. Launch Full GUI (may hang)")
    print()
    print("⚙️  SYSTEM TOOLS:")
    print("  6. Test IBKR Connection")
    print("  7. View System Status")
    print("  8. Open Config File")
    print()
    print("🚪 EXIT:")
    print("  9. Exit")
    print()
    print("=" * 60)

def run_professional_monitor():
    """Launch professional position monitor"""
    print("🚀 Launching Professional Position Monitor...")
    try:
        subprocess.run([sys.executable, "professional_position_monitor.py"])
    except Exception as e:
        print(f"❌ Error: {e}")
        input("Press Enter to continue...")

def run_simple_monitor():
    """Launch simple position monitor"""
    print("🚀 Launching Simple Position Monitor...")
    try:
        subprocess.run([sys.executable, "simple_working_monitor.py"])
    except Exception as e:
        print(f"❌ Error: {e}")
        input("Press Enter to continue...")

def fix_pending_positions():
    """Run pending positions fix"""
    print("🔧 Fixing Pending Positions...")
    try:
        subprocess.run([sys.executable, "fix_pending_positions.py", "--fix"])
    except Exception as e:
        print(f"❌ Error: {e}")
    input("Press Enter to continue...")

def run_backtest():
    """Run core backtest engine"""
    print("📈 Running Core Backtest Engine...")
    try:
        subprocess.run([sys.executable, "backtest_core.py"])
    except Exception as e:
        print(f"❌ Error: {e}")
    input("Press Enter to continue...")

def launch_full_gui():
    """Launch full GUI (warning about hanging)"""
    print("⚠️  WARNING: Full GUI may hang!")
    choice = input("Continue anyway? (y/N): ").lower()
    if choice == 'y':
        print("🚀 Launching Full GUI...")
        try:
            subprocess.Popen([sys.executable, "start_trading_system_reliable.py"])
            print("✅ GUI launched in background")
        except Exception as e:
            print(f"❌ Error: {e}")
    input("Press Enter to continue...")

def test_ibkr_connection():
    """Test IBKR connection"""
    print("🔍 Testing IBKR Connection...")
    try:
        import json
        from ib_insync import IB
        
        # Load config
        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
        except:
            host = "127.0.0.1"
            port = 7497
            client_id = 7
        
        print(f"Connecting to {host}:{port} with client ID {client_id}...")
        
        ib = IB()
        ib.connect(host, port, clientId=client_id + 200, timeout=5)
        
        if ib.isConnected():
            port_name = "Paper Trading" if port == 7497 else "Live Trading" if port == 7496 else f"Port {port}"
            print(f"✅ IBKR Connected ({port_name})")
            
            # Get basic info
            accounts = ib.managedAccounts()
            if accounts:
                print(f"📊 Account: {accounts[0]}")
            
            positions = ib.positions()
            print(f"📈 Positions: {len(positions)}")
            
            ib.disconnect()
        else:
            print("❌ Connection failed")
            
    except ImportError:
        print("❌ ib-insync not installed")
        print("💡 Install with: pip install ib-insync")
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    input("Press Enter to continue...")

def show_system_status():
    """Show system status"""
    print("🔍 SYSTEM STATUS:")
    print("-" * 40)
    
    # Check files
    files_to_check = [
        'backtest_core.py',
        'professional_position_monitor.py', 
        'simple_working_monitor.py',
        'fix_pending_positions.py',
        'tickers.csv',
        'config.json',
        'pending_sales.json'
    ]
    
    for file in files_to_check:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - MISSING")
    
    # Check directories
    dirs_to_check = ['data', 'reports', 'logs']
    for dir in dirs_to_check:
        if os.path.exists(dir):
            print(f"✅ {dir}/ directory")
        else:
            print(f"❌ {dir}/ directory - MISSING")
    
    # Check Python packages
    packages = ['PyQt6', 'matplotlib', 'ib_insync', 'pandas', 'yfinance']
    print("\n📦 PYTHON PACKAGES:")
    for pkg in packages:
        try:
            __import__(pkg.lower().replace('-', '_'))
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} - NOT INSTALLED")
    
    input("\nPress Enter to continue...")

def open_config():
    """Open config file"""
    print("⚙️  Opening config.json...")
    try:
        if os.name == 'nt':  # Windows
            os.startfile("config.json")
        else:  # macOS/Linux
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", "config.json"])
        print("✅ Config file opened")
    except Exception as e:
        print(f"❌ Error opening config: {e}")
    input("Press Enter to continue...")

def main():
    """Main menu loop"""
    while True:
        show_menu()
        
        try:
            choice = input("Select option (1-9): ").strip()
            
            if choice == '1':
                run_professional_monitor()
            elif choice == '2':
                run_simple_monitor()
            elif choice == '3':
                fix_pending_positions()
            elif choice == '4':
                run_backtest()
            elif choice == '5':
                launch_full_gui()
            elif choice == '6':
                test_ibkr_connection()
            elif choice == '7':
                show_system_status()
            elif choice == '8':
                open_config()
            elif choice == '9':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please select 1-9.")
                input("Press Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()
