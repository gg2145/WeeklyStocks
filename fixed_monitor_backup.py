#!/usr/bin/env python3
"""
Fixed Position Monitor - Uses our own pending sales tracking
No more relying on IBKR API to detect orders - we track our own!
"""

import json
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

# Import our pending sales tracker
from pending_sales import pending_tracker

class FixedMonitor(QDialog):
    """Position monitor using proven working logic with enhanced visibility"""
    
    def __init__(self, parent=None, shared_ib=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Position Monitor - FIXED VERSION")
        self.setGeometry(150, 150, 1200, 700)
        
        # Use shared connection if provided, but don't assume ownership
        self.ib = shared_ib
        self.owns_connection = shared_ib is None
        
        self.init_ui()
        
        # If using shared connection, immediately load data
        if self.ib and self.ib.isConnected():
            self.status_label.setText("✅ CONNECTED (Shared)")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            self.connect_btn.setText("Disconnect")
            self.connect_btn.clicked.disconnect()
            self.connect_btn.clicked.connect(self.disconnect_ibkr)
            self.refresh_data()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📊 POSITION MONITOR - FIXED VERSION")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px; background-color: white; padding: 10px; border-radius: 5px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection
        conn_layout = QHBoxLayout()
        self.status_label = QLabel("❌ Not Connected")
        self.status_label.setStyleSheet("font-weight: bold; color: red; font-size: 14px;")
        
        self.connect_btn = QPushButton("Connect to IBKR")
        self.connect_btn.clicked.connect(self.connect_ibkr)
        
        conn_layout.addWidget(self.status_label)
        conn_layout.addStretch()
        conn_layout.addWidget(self.connect_btn)
        layout.addLayout(conn_layout)
        
        # Table with HIGHLY VISIBLE STYLING
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Position", "📋 PENDING ORDERS", "Market Value", "P&L", "Action", "Status"
        ])
        
        # Make table header very visible
        header = self.table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #343a40;
                color: white;
                padding: 15px;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }
        """)
        header.setStretchLastSection(True)
        
        # Table styling
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #dee2e6;
                background-color: white;
                alternate-background-color: #f8f9fa;
                font-size: 12px;
                border: 2px solid #dee2e6;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Log with VERY CLEAR STYLING
        log_label = QLabel("🔍 ACTIVITY LOG - Watch for order detection:")
        log_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px; background-color: #fff3cd; padding: 8px; border-radius: 5px;")
        layout.addWidget(log_label)
        
        self.log = QTextEdit()
        self.log.setMaximumHeight(150)
        self.log.setReadOnly(True)
        self.log.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        
        close_all_btn = QPushButton("🚨 Close All Positions")
        close_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #c82333; }
        """)
        close_all_btn.clicked.connect(self.close_all)
        
        close_btn = QPushButton("❌ Close Monitor")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """)
        close_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(close_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}

    def log_msg(self, msg):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f'<span style="color: #3498db;">[{timestamp}] {msg}</span>')
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def connect_ibkr(self):
        if not IB_AVAILABLE:
            self.log_msg("ERROR: ib-insync not installed")
            return
            
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            # Use the client ID from config settings
            try_client_id = client_id  # Use config client ID, not hardcoded
            self.log_msg(f"🔍 Using client ID {try_client_id} from settings...")
            
            try:
                self.log_msg(f"🔄 Connecting with client ID {try_client_id}...")
                
                self.ib = IB()
                self.ib.connect(host, port, clientId=try_client_id, timeout=10)
                
                if self.ib.isConnected():
                    connected = True
                    self.log_msg(f"✅ Connected with client ID {try_client_id}")
                else:
                    self.log_msg(f"❌ Failed to connect with client ID {try_client_id}")
                    
            except Exception as e:
                self.log_msg(f"❌ Connection error: {e}")
            
            if connected and self.ib.isConnected():
                self.status_label.setText("✅ Connected")
                self.status_label.setStyleSheet("font-weight: bold; color: green; font-size: 14px;")
                self.connect_btn.setText("Disconnect")
                self.connect_btn.clicked.disconnect()
                self.connect_btn.clicked.connect(self.disconnect_ibkr)
                # Show which account we're connected to
                try:
                    accounts = self.ib.managedAccounts()
                    if accounts:
                        self.log_msg(f"🏦 CONNECTED TO ACCOUNTS: {accounts}")
                        # Try to get account summary to confirm it's the right account
                        account_summary = self.ib.accountSummary()
                        for item in account_summary:
                            if item.tag == 'AccountType':
                                self.log_msg(f"📋 Account Type: {item.value}")
                except Exception as e:
                    self.log_msg(f"⚠️ Could not get account info: {e}")
                
                self.log_msg("✅ Connected successfully - checking for your pending orders")
                self.owns_connection = True
                self.refresh_data()
            else:
                self.log_msg("❌ Connection failed to all client IDs")
                
        except Exception as e:
            self.log_msg(f"Connection error: {e}")

    def disconnect_ibkr(self):
        if self.ib and self.ib.isConnected() and self.owns_connection:
            self.ib.disconnect()
        
        self.status_label.setText("❌ Not Connected")
        self.status_label.setStyleSheet("font-weight: bold; color: red; font-size: 14px;")
        self.connect_btn.setText("Connect to IBKR")
        self.connect_btn.clicked.disconnect()
        self.connect_btn.clicked.connect(self.connect_ibkr)
        self.log_msg("Disconnected")

    def refresh_data(self):
        if not self.ib or not self.ib.isConnected():
            self.log_msg("❌ Not connected - cannot refresh")
            return
            
        try:
            self.log_msg("🔍 Getting positions and orders... (FIXED MONITOR)")
            self.log_msg("🎯 Using our own pending sales tracking system (NO IBKR order detection)")
            
            # Get positions - EXACT SAME LOGIC AS WORKING MONITOR
            positions = {}
            portfolio = self.ib.portfolio()
            for item in portfolio:
                if item.position != 0:
                    positions[item.contract.symbol] = {
                        'qty': int(item.position),
                        'value': float(item.marketValue),
                        'pnl': float(item.unrealizedPNL),
                        'contract': item.contract
                    }
            
            # Get our tracked pending orders (both buys and sells)
            tracked_pending_sales = pending_tracker.get_all_pending_sales()
            tracked_pending_buys = pending_tracker.get_all_pending_buys()
            
            self.log_msg(f"🔍 DEBUG A: Got {len(tracked_pending_sales)} pending sales, {len(tracked_pending_buys)} pending buys")
            self.log_msg(f"🔍 DEBUG B: Positions keys: {list(positions.keys())}")
            
            # Combine positions and pending buy orders for display
            all_symbols = set(positions.keys())
            all_symbols.update(tracked_pending_buys.keys())
            
            self.log_msg(f"🔍 DEBUG C: Combined symbols: {list(all_symbols)}")
            
            self.log_msg(f"🔍 DEBUG: Found {len(positions)} positions, {len(tracked_pending_buys)} pending buys")
            self.log_msg(f"🔍 DEBUG: All symbols to process: {sorted(all_symbols)}")
            
            self.table.setRowCount(len(all_symbols))
            row = 0
            
            for symbol in sorted(all_symbols):
                try:
                    self.log_msg(f"🔍 DEBUG: Processing symbol {symbol} (row {row})")
                    # Get position info (if we own it)
                    pos = positions.get(symbol)
                
                    # Check OUR tracking system for pending orders
                    has_pending_sells = pending_tracker.is_pending_sale(symbol)
                    has_pending_buys = pending_tracker.is_pending_buy(symbol)
                    
                    # DEBUG: Log the pending status for debugging
                    self.log_msg(f"🔍 DEBUG: {symbol} - has_pending_sells={has_pending_sells}, has_pending_buys={has_pending_buys}")
                
                    # Get pending order info
                    pending_sell_info = pending_tracker.get_pending_sale_info(symbol)
                    pending_buy_info = pending_tracker.get_pending_buy_info(symbol)
                
                # Format pending orders display
                pending_orders = []
                if has_pending_sells and pending_sell_info:
                    qty = pending_sell_info.get('quantity', 0)
                    order_type = pending_sell_info.get('order_type', 'MARKET')
                    price = pending_sell_info.get('price')
                    if price:
                        pending_orders.append(f"SELL {qty} shares ({order_type} @ ${price:.2f})")
                    else:
                        pending_orders.append(f"SELL {qty} shares ({order_type})")
                
                if has_pending_buys and pending_buy_info:
                    qty = pending_buy_info.get('quantity', 0)
                    order_type = pending_buy_info.get('order_type', 'MARKET')
                    price = pending_buy_info.get('price')
                    if price:
                        pending_orders.append(f"BUY {qty} shares ({order_type} @ ${price:.2f})")
                    else:
                        pending_orders.append(f"BUY {qty} shares ({order_type})")
                
                # Symbol
                symbol_item = QTableWidgetItem(symbol)
                symbol_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                self.table.setItem(row, 0, symbol_item)
                
                # Position
                if pos:
                    pos_item = QTableWidgetItem(str(pos['qty']))
                else:
                    pos_item = QTableWidgetItem("0 (pending buy)")
                    pos_item.setForeground(QColor("blue"))
                    pos_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.table.setItem(row, 1, pos_item)
                
                # PENDING ORDERS column
                if pending_orders:
                    pending_text = "\n".join(pending_orders)
                    pending_item = QTableWidgetItem(pending_text)
                    if has_pending_sells:
                        pending_item.setBackground(QColor("#dc3545"))  # Red for sells
                    else:
                        pending_item.setBackground(QColor("#007bff"))  # Blue for buys
                    pending_item.setForeground(QColor("white"))
                    pending_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                else:
                    pending_item = QTableWidgetItem("None")
                self.table.setItem(row, 2, pending_item)
                
                # Market Value
                if pos:
                    value_item = QTableWidgetItem(f"${pos['value']:,.0f}")
                else:
                    value_item = QTableWidgetItem("$0 (no position)")
                    value_item.setForeground(QColor("gray"))
                self.table.setItem(row, 3, value_item)
                
                # P&L with color
                if pos:
                    pnl_item = QTableWidgetItem(f"${pos['pnl']:,.0f}")
                    if pos['pnl'] >= 0:
                        pnl_item.setForeground(QColor("green"))
                    else:
                        pnl_item.setForeground(QColor("red"))
                else:
                    pnl_item = QTableWidgetItem("N/A")
                    pnl_item.setForeground(QColor("gray"))
                self.table.setItem(row, 4, pnl_item)
                
                # Action button
                if pending_orders:
                    btn = QPushButton("Cancel Pending")
                    btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 8px;")
                    btn.clicked.connect(lambda checked, s=symbol: self.cancel_pending_order(s))
                elif pos:  # Has position, can sell
                    btn = QPushButton(f"Sell {symbol}")
                    btn.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 8px;")
                    btn.clicked.connect(lambda checked, s=symbol: self.close_position_with_tracking(s))
                else:  # No position, no pending orders
                    btn = QPushButton(f"Buy {symbol}")
                    btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
                    btn.clicked.connect(lambda checked, s=symbol: self.buy_position_with_tracking(s))
                self.table.setCellWidget(row, 5, btn)
                
                # Status - THIS IS WHERE WE SHOW ORDER STATUS
                if has_pending_sells:
                    status_item = QTableWidgetItem("PENDING SALE")
                    status_item.setBackground(QColor("#dc3545"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                elif has_pending_buys:
                    status_item = QTableWidgetItem("PENDING BUY")
                    status_item.setBackground(QColor("#007bff"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                elif pos:
                    status_item = QTableWidgetItem("Open")
                    status_item.setForeground(QColor("green"))
                    status_item.setFont(QFont("Arial", 10))
                else:
                    status_item = QTableWidgetItem("No Position")
                    status_item.setForeground(QColor("gray"))
                    status_item.setFont(QFont("Arial", 10))
                    self.table.setItem(row, 6, status_item)
                    
                    row += 1
                except Exception as symbol_error:
                    self.log_msg(f"❌ ERROR processing {symbol}: {symbol_error}")
                    import traceback
                    self.log_msg(f"❌ Traceback: {traceback.format_exc()}")
            
            self.log_msg(f"✅ Refreshed: {len(positions)} positions ({len(tracked_pending_sales)} pending sells, {len(tracked_pending_buys)} pending buys)")
            
        except Exception as e:
            self.log_msg(f"❌ Refresh error: {e}")
            import traceback
            traceback.print_exc()

    def close_position(self, symbol):
        reply = QMessageBox.question(
            self, 'Close Position',
            f'Close {symbol} position with MARKET order?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                contract = Stock(symbol, 'SMART', 'USD')
                # Find position size
                portfolio = self.ib.portfolio()
                for item in portfolio:
                    if item.contract.symbol == symbol and item.position > 0:
                        qty = int(item.position)
                        trade = self.ib.placeOrder(contract, MarketOrder('SELL', qty))
                        
                        # AUTOMATICALLY TRACK THIS SELL ORDER
                        result = pending_tracker.mark_as_pending_sale(
                            symbol, qty, "MARKET", 
                            notes=f"Close position via monitor at {datetime.now().strftime('%H:%M:%S')}"
                        )
                        self.log_msg(f"✅ {result}")
                        
                        self.log_msg(f"✅ Placed sell order: {qty} shares of {symbol}")
                        break
                
                # Refresh after delay
                QTimer.singleShot(2000, self.refresh_data)
                
            except Exception as e:
                self.log_msg(f"❌ Error closing {symbol}: {e}")

    def close_all(self):
        reply = QMessageBox.question(
            self, 'Close All',
            'Close ALL positions with MARKET orders?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                portfolio = self.ib.portfolio()
                for item in portfolio:
                    if item.position > 0:
                        symbol = item.contract.symbol
                        qty = int(item.position)
                        contract = Stock(symbol, 'SMART', 'USD')
                        trade = self.ib.placeOrder(contract, MarketOrder('SELL', qty))
                        
                        # AUTOMATICALLY TRACK THIS SELL ORDER
                        result = pending_tracker.mark_as_pending_sale(
                            symbol, qty, "MARKET", 
                            notes=f"Close all positions at {datetime.now().strftime('%H:%M:%S')}"
                        )
                        self.log_msg(f"✅ {result}")
                        
                        self.log_msg(f"✅ Placed sell order: {qty} shares of {symbol}")
                
                QTimer.singleShot(3000, self.refresh_data)
                
            except Exception as e:
                self.log_msg(f"❌ Error closing all: {e}")
    
    def close_position_with_tracking(self, symbol):
        """Close position and add to our tracking system"""
        reply = QMessageBox.question(
            self, 'Close Position',
            f'Close {symbol} position with MARKET order?\n\n'
            f'This will:\n'
            f'1. Place sell order in IBKR\n'
            f'2. Mark as PENDING SALE in our system\n'
            f'3. Show RED indicator immediately',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Find position size
                portfolio = self.ib.portfolio()
                qty = 0
                for item in portfolio:
                    if item.contract.symbol == symbol and item.position > 0:
                        qty = int(item.position)
                        break
                
                if qty > 0:
                    # 1. Place order in IBKR
                    contract = Stock(symbol, 'SMART', 'USD')
                    trade = self.ib.placeOrder(contract, MarketOrder('SELL', qty))
                    
                    # 2. Add to our tracking system immediately
                    result = pending_tracker.mark_as_pending_sale(
                        symbol, qty, "MARKET", 
                        notes=f"Individual sell via monitor at {datetime.now().strftime('%H:%M:%S')}"
                    )
                    
                    self.log_msg(f"✅ {result}")
                    self.log_msg(f"✅ Placed IBKR sell order: {qty} shares of {symbol}")
                    
                    # 3. Refresh display to show red indicator
                    QTimer.singleShot(1000, self.refresh_data)
                else:
                    self.log_msg(f"❌ No position found for {symbol}")
                
            except Exception as e:
                self.log_msg(f"❌ Error selling {symbol}: {e}")
    
    def cancel_pending_sale(self, symbol):
        """Remove from our tracking system"""
        reply = QMessageBox.question(
            self, 'Cancel Pending Sale',
            f'Remove {symbol} from pending sales tracking?\n\n'
            f'⚠️ This only removes it from our tracking.\n'
            f'You must cancel the actual IBKR order separately!',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = pending_tracker.mark_as_sold(symbol, "Cancelled by user")
            self.log_msg(f"✅ {result}")
            QTimer.singleShot(500, self.refresh_data)
    
    def cancel_pending_order(self, symbol):
        """Remove any pending order from our tracking system"""
        order_info = pending_tracker.get_pending_order_info(symbol)
        if not order_info:
            self.log_msg(f"❌ No pending order found for {symbol}")
            return
        
        order_type = order_info.get('action', 'UNKNOWN')
        quantity = order_info.get('quantity', 0)
        
        reply = QMessageBox.question(
            self, 'Cancel Pending Order',
            f'Remove {symbol} from pending orders tracking?\n\n'
            f'Order: {order_type} {quantity} shares\n'
            f'⚠️ This only removes it from our tracking.\n'
            f'You must cancel the actual IBKR order separately!',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = pending_tracker.mark_as_filled(symbol, "Cancelled by user")
            self.log_msg(f"✅ {result}")
            QTimer.singleShot(500, self.refresh_data)
    
    def buy_position_with_tracking(self, symbol):
        """Buy position with tracking (placeholder - would need actual buy implementation)"""
        qty, ok = QInputDialog.getInt(
            self, 'Buy Position',
            f'How many shares of {symbol} to buy?',
            value=100, min=1, max=10000
        )
        
        if ok:
            reply = QMessageBox.question(
                self, 'Buy Position',
                f'Place BUY order for {qty} shares of {symbol}?\n\n'
                f'This will:\n'
                f'1. Place buy order in IBKR\n'
                f'2. Mark as PENDING BUY in our system\n'
                f'3. Show BLUE indicator immediately',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # TODO: Actually place IBKR buy order here
                    # For now, just track it
                    contract = Stock(symbol, 'SMART', 'USD')
                    # trade = self.ib.placeOrder(contract, MarketOrder('BUY', qty))
                    
                    # Track the pending buy
                    result = pending_tracker.mark_as_pending_buy(
                        symbol, qty, "MARKET", 
                        notes=f"Manual buy via monitor at {datetime.now().strftime('%H:%M:%S')}"
                    )
                    
                    self.log_msg(f"✅ {result}")
                    self.log_msg(f"⚠️ NOTE: Actual IBKR buy order placement not implemented yet")
                    
                    # Refresh display to show blue indicator
                    QTimer.singleShot(1000, self.refresh_data)
                    
                except Exception as e:
                    self.log_msg(f"❌ Error buying {symbol}: {e}")

    def closeEvent(self, event):
        if self.ib and self.ib.isConnected() and self.owns_connection:
            self.ib.disconnect()
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    monitor = FixedMonitor()
    monitor.show()
    app.exec()