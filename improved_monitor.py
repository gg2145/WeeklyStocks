#!/usr/bin/env python3
"""
Improved Position Monitor - Crystal Clear Pending Orders Display
Accepts shared IBKR connection from main menu, highly visible pending orders
"""

import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

class ImprovedMonitor(QDialog):
    """Position monitor with crystal clear pending order visibility"""
    
    def __init__(self, parent=None, shared_ib=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Position Monitor - Live Trading")
        self.setGeometry(150, 150, 1400, 800)  # Large window
        
        # Use shared connection if provided
        self.ib = shared_ib
        self.owns_connection = shared_ib is None  # Only manage connection if we created it
        
        self.init_ui()
        
        # If using shared connection, immediately load data
        if self.ib and self.ib.isConnected():
            self.status_label.setText("✅ CONNECTED (Shared)")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #27ae60;")
            self.connect_btn.setEnabled(False)
            self.refresh_data()
            
            # Auto refresh every 10 seconds when connected
            self.auto_timer = QTimer()
            self.auto_timer.timeout.connect(self.refresh_data)
            self.auto_timer.start(10000)  # 10 seconds
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # HEADER SECTION - Very prominent
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                color: white;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        
        title = QLabel("📊 LIVE POSITION MONITOR")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin: 10px;")
        
        subtitle = QLabel("Real-time monitoring of your IBKR positions and pending sell orders")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #bdc3c7; margin-bottom: 10px;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_frame)
        
        # CONNECTION STATUS - Very visible
        conn_frame = QFrame()
        conn_frame.setFrameStyle(QFrame.Shape.Box)
        conn_frame.setStyleSheet("""
            QFrame {
                background-color: #ecf0f1;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        conn_layout = QHBoxLayout(conn_frame)
        
        conn_label = QLabel("🔌 IBKR Connection:")
        conn_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.status_label = QLabel("❌ NOT CONNECTED")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")
        
        self.connect_btn = QPushButton("🔗 Connect to IBKR")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.connect_btn.clicked.connect(self.connect_ibkr)
        
        conn_layout.addWidget(conn_label)
        conn_layout.addWidget(self.status_label)
        conn_layout.addStretch()
        conn_layout.addWidget(self.connect_btn)
        layout.addWidget(conn_frame)
        
        # CRITICAL ALERT SECTION - For pending orders
        self.alert_frame = QFrame()
        self.alert_frame.setFrameStyle(QFrame.Shape.Box)
        self.alert_frame.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 3px solid #ffc107;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        alert_layout = QVBoxLayout(self.alert_frame)
        
        self.alert_title = QLabel("⚠️ PENDING SELL ORDERS DETECTED")
        self.alert_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alert_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #856404; margin-bottom: 10px;")
        
        self.alert_text = QLabel()
        self.alert_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alert_text.setStyleSheet("font-size: 16px; color: #856404; font-weight: bold;")
        self.alert_text.setWordWrap(True)
        
        alert_layout.addWidget(self.alert_title)
        alert_layout.addWidget(self.alert_text)
        
        self.alert_frame.hide()  # Initially hidden
        layout.addWidget(self.alert_frame)
        
        # POSITIONS TABLE - Much better organized
        table_frame = QFrame()
        table_frame.setFrameStyle(QFrame.Shape.Box)
        table_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        table_layout = QVBoxLayout(table_frame)
        
        table_header = QLabel("📈 CURRENT POSITIONS & ORDERS")
        table_header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #2c3e50; background-color: white; padding: 10px; border-radius: 5px;")
        table_layout.addWidget(table_header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Position", "💰 Value", "📊 P&L", "🚨 SELLING STATUS", "⚠️ PENDING SELLS", "Action", "Details"
        ])
        
        # Make table much more professional
        self.table.setMinimumHeight(350)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #dee2e6;
                background-color: white;
                alternate-background-color: #f8f9fa;
                font-size: 13px;
                border: 1px solid #dee2e6;
            }
            QHeaderView::section {
                background-color: #343a40;
                color: white;
                padding: 12px;
                font-weight: bold;
                border: none;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        
        table_layout.addWidget(self.table)
        layout.addWidget(table_frame)
        
        # ACTION BUTTONS - Better organized
        actions_frame = QFrame()
        actions_frame.setFrameStyle(QFrame.Shape.Box)
        actions_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        actions_layout = QHBoxLayout(actions_frame)
        
        self.refresh_btn = QPushButton("🔄 Manual Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        self.close_all_btn = QPushButton("🚨 CLOSE ALL POSITIONS")
        self.close_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.close_all_btn.clicked.connect(self.close_all_positions)
        
        close_monitor_btn = QPushButton("❌ Close Monitor")
        close_monitor_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        close_monitor_btn.clicked.connect(self.close)
        
        actions_layout.addWidget(self.refresh_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.close_all_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(close_monitor_btn)
        layout.addWidget(actions_frame)
        
        # LOG SECTION - Compact but visible
        log_frame = QFrame()
        log_frame.setFrameStyle(QFrame.Shape.Box)
        log_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        log_layout = QVBoxLayout(log_frame)
        
        log_header = QLabel("📝 Activity Log")
        log_header.setStyleSheet("font-size: 14px; font-weight: bold; color: white; margin-bottom: 5px;")
        log_layout.addWidget(log_header)
        
        self.log = QTextEdit()
        self.log.setMaximumHeight(120)
        self.log.setReadOnly(True)
        self.log.setStyleSheet("""
            QTextEdit {
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #4a5568;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.log)
        layout.addWidget(log_frame)
        
    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}
    
    def log_msg(self, msg, level="INFO"):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#3498db", "SUCCESS": "#27ae60", "ERROR": "#e74c3c", "WARNING": "#f39c12"}
        color = colors.get(level, "#ecf0f1")
        
        self.log.append(f'<span style="color: {color};">[{timestamp}] {msg}</span>')
        
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def connect_ibkr(self):
        if not IB_AVAILABLE:
            self.log_msg("ERROR: ib-insync not installed. Run: pip install ib-insync", "ERROR")
            return
            
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            self.log_msg(f"Connecting to {host}:{port} with client ID {client_id}...", "INFO")
            
            self.ib = IB()
            # Use unique client ID to avoid conflicts
            monitor_client_id = client_id + 10  # Different from main app
            self.log_msg(f"Using client ID {monitor_client_id} for monitor connection", "INFO")
            self.ib.connect(host, port, clientId=monitor_client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("✅ CONNECTED")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #27ae60;")
                self.connect_btn.setText("🔌 Disconnect")
                self.connect_btn.clicked.disconnect()
                self.connect_btn.clicked.connect(self.disconnect_ibkr)
                self.log_msg("Successfully connected to IBKR", "SUCCESS")
                self.refresh_data()
                
                # Start auto refresh
                self.auto_timer = QTimer()
                self.auto_timer.timeout.connect(self.refresh_data)
                self.auto_timer.start(10000)  # 10 seconds
            else:
                self.log_msg("Failed to connect to IBKR", "ERROR")
                
        except Exception as e:
            self.log_msg(f"Connection error: {str(e)}", "ERROR")
    
    def disconnect_ibkr(self):
        if hasattr(self, 'auto_timer'):
            self.auto_timer.stop()
            
        if self.ib and self.ib.isConnected() and self.owns_connection:
            self.ib.disconnect()
        
        self.status_label.setText("❌ NOT CONNECTED")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")
        self.connect_btn.setText("🔗 Connect to IBKR")
        self.connect_btn.clicked.disconnect()
        self.connect_btn.clicked.connect(self.connect_ibkr)
        self.log_msg("Disconnected from IBKR", "INFO")
        
        # Hide alert
        self.alert_frame.hide()
        
    def refresh_data(self):
        if not self.ib or not self.ib.isConnected():
            self.log_msg("Cannot refresh - not connected to IBKR", "WARNING")
            return
            
        try:
            self.log_msg("Refreshing positions and orders...", "INFO")
            
            # Get positions with detailed info
            positions = {}
            portfolio = self.ib.portfolio()
            for item in portfolio:
                if item.position != 0:
                    positions[item.contract.symbol] = {
                        'qty': int(item.position),
                        'value': float(item.marketValue),
                        'pnl': float(item.unrealizedPNL),
                        'avg_cost': float(item.averageCost),
                        'market_price': float(item.marketPrice),
                        'contract': item.contract
                    }
            
            # Get ALL pending orders using every method - WITH DETAILED DEBUGGING
            all_orders = {}
            pending_symbols = set()
            
            # Method 1: openOrders() - MOST RELIABLE FOR PENDING ORDERS
            try:
                orders1 = self.ib.openOrders()
                self.log_msg(f"🔍 openOrders() found: {len(orders1)} orders", "INFO")
                for order in orders1:
                    order_id = order.order.orderId
                    symbol = order.contract.symbol
                    action = order.order.action
                    qty = order.order.totalQuantity
                    status = order.orderStatus.status
                    
                    self.log_msg(f"  📋 Order {order_id}: {action} {qty} {symbol} - Status: {status}", "INFO")
                    
                    all_orders[order_id] = order
                    if action == 'SELL':
                        pending_symbols.add(symbol)
                        self.log_msg(f"  🚨 DETECTED SELL ORDER: {symbol} - {qty} shares", "WARNING")
            except Exception as e:
                self.log_msg(f"❌ openOrders() failed: {e}", "ERROR")
            
            # Method 2: reqAllOpenOrders() - GETS ORDERS FROM ALL CLIENTS
            try:
                orders2 = self.ib.reqAllOpenOrders()
                self.log_msg(f"🔍 reqAllOpenOrders() found: {len(orders2)} orders", "INFO")
                for order in orders2:
                    order_id = order.order.orderId
                    symbol = order.contract.symbol
                    action = order.order.action
                    qty = order.order.totalQuantity
                    status = order.orderStatus.status
                    
                    if order_id not in all_orders:
                        self.log_msg(f"  📋 Additional Order {order_id}: {action} {qty} {symbol} - Status: {status}", "INFO")
                        all_orders[order_id] = order
                        if action == 'SELL':
                            pending_symbols.add(symbol)
                            self.log_msg(f"  🚨 ADDITIONAL SELL ORDER: {symbol} - {qty} shares", "WARNING")
            except Exception as e:
                self.log_msg(f"⚠️ reqAllOpenOrders() failed: {e}", "WARNING")
            
            # Method 3: trades() with pending status - GETS TRADES NOT COMPLETED
            try:
                trades = self.ib.trades()
                pending_trades = [t for t in trades if t.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit', 'ApiPending']]
                self.log_msg(f"🔍 trades() found: {len(trades)} total trades, {len(pending_trades)} pending", "INFO")
                
                for trade in pending_trades:
                    order_id = trade.order.orderId
                    symbol = trade.contract.symbol
                    action = trade.order.action
                    qty = trade.order.totalQuantity
                    status = trade.orderStatus.status
                    
                    if order_id not in all_orders:
                        self.log_msg(f"  📋 Pending Trade {order_id}: {action} {qty} {symbol} - Status: {status}", "INFO")
                        all_orders[order_id] = trade
                        if action == 'SELL':
                            pending_symbols.add(symbol)
                            self.log_msg(f"  🚨 PENDING SELL TRADE: {symbol} - {qty} shares", "WARNING")
            except Exception as e:
                self.log_msg(f"⚠️ trades() failed: {e}", "WARNING")
            
            # Method 4: Check client orders specifically - SOMETIMES MISSED BY OTHER METHODS
            try:
                # Get orders for this specific client ID
                client_orders = self.ib.client.orders
                self.log_msg(f"🔍 Client orders found: {len(client_orders)} orders", "INFO")
                for order_id, order_data in client_orders.items():
                    if hasattr(order_data, 'order') and hasattr(order_data, 'contract'):
                        symbol = order_data.contract.symbol
                        action = order_data.order.action
                        qty = order_data.order.totalQuantity
                        
                        if order_id not in all_orders and action == 'SELL':
                            self.log_msg(f"  🚨 CLIENT SELL ORDER: {symbol} - {qty} shares (Order ID: {order_id})", "WARNING")
                            all_orders[order_id] = order_data
                            pending_symbols.add(symbol)
            except Exception as e:
                self.log_msg(f"⚠️ Client orders check failed: {e}", "WARNING")
            
            # FINAL SUMMARY
            total_sell_orders = len([o for o in all_orders.values() if hasattr(o, 'order') and o.order.action == 'SELL'])
            self.log_msg(f"📊 DETECTION SUMMARY: {len(all_orders)} total orders, {total_sell_orders} sell orders, {len(pending_symbols)} symbols being sold", "SUCCESS")
            
            if pending_symbols:
                self.log_msg(f"🚨 SYMBOLS BEING SOLD: {', '.join(pending_symbols)}", "ERROR")
            
            # Show critical alert if there are pending sell orders
            if pending_symbols:
                self.show_pending_alert(pending_symbols, all_orders)
            else:
                self.alert_frame.hide()
            
            # Update the main table
            self.update_table(positions, all_orders)
            
            # Log results
            total_pending = len([o for o in all_orders.values() if o.order.action == 'SELL'])
            self.log_msg(f"Found {len(positions)} positions, {total_pending} pending sell orders", "SUCCESS")
            
        except Exception as e:
            self.log_msg(f"Error refreshing data: {str(e)}", "ERROR")
    
    def show_pending_alert(self, pending_symbols, all_orders):
        """Show highly visible alert for pending sell orders"""
        self.alert_frame.show()
        
        pending_details = []
        for symbol in pending_symbols:
            symbol_orders = [o for o in all_orders.values() 
                           if o.contract.symbol == symbol and o.order.action == 'SELL']
            for order in symbol_orders:
                qty = int(order.order.totalQuantity)
                status = order.orderStatus.status
                pending_details.append(f"{symbol}: {qty} shares ({status})")
        
        alert_text = f"🚨 {len(pending_details)} STOCKS ARE BEING SOLD RIGHT NOW!\n\n"
        alert_text += "\n".join(pending_details)
        alert_text += f"\n\nThese orders are active in your IBKR account and will execute when market conditions are met."
        
        self.alert_text.setText(alert_text)
    
    def update_table(self, positions, all_orders):
        """Update the positions table with EXTREMELY VISIBLE pending order indicators"""
        self.table.setRowCount(len(positions))
        row = 0
        
        for symbol, pos in positions.items():
            # Find all pending sell orders for this symbol
            symbol_orders = []
            for order_id, order_data in all_orders.items():
                if (order_data.contract.symbol == symbol and order_data.order.action == 'SELL'):
                    qty = int(order_data.order.totalQuantity)
                    status = order_data.orderStatus.status
                    symbol_orders.append({'qty': qty, 'status': status})
            
            # Determine if this row is for a pending sale
            is_selling = bool(symbol_orders)
            
            # SYMBOL - Make it HUGE and RED if selling
            if is_selling:
                symbol_item = QTableWidgetItem(f"🚨 {symbol} 🚨")
                symbol_item.setBackground(QColor("#dc3545"))  # Bright red
                symbol_item.setForeground(QColor("white"))
                symbol_item.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            else:
                symbol_item = QTableWidgetItem(symbol)
                symbol_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.table.setItem(row, 0, symbol_item)
            
            # Position quantity - RED background if selling
            pos_text = f"{pos['qty']:,} shares"
            if is_selling:
                pos_text = f"🔥 {pos_text} 🔥"
            pos_item = QTableWidgetItem(pos_text)
            pos_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            if is_selling:
                pos_item.setBackground(QColor("#dc3545"))
                pos_item.setForeground(QColor("white"))
            self.table.setItem(row, 1, pos_item)
            
            # Market value - RED if selling
            value_text = f"${pos['value']:,.0f}"
            if is_selling:
                value_text = f"💸 {value_text} 💸"
            value_item = QTableWidgetItem(value_text)
            value_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            if is_selling:
                value_item.setBackground(QColor("#dc3545"))
                value_item.setForeground(QColor("white"))
            self.table.setItem(row, 2, value_item)
            
            # P&L - RED background if selling
            pnl_text = f"${pos['pnl']:,.0f}"
            pnl_item = QTableWidgetItem(pnl_text)
            pnl_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            if is_selling:
                pnl_item.setBackground(QColor("#dc3545"))
                pnl_item.setForeground(QColor("white"))
            else:
                if pos['pnl'] >= 0:
                    pnl_item.setForeground(QColor("#27ae60"))
                else:
                    pnl_item.setForeground(QColor("#e74c3c"))
            self.table.setItem(row, 3, pnl_item)
            
            # SELLING STATUS - MASSIVE VISUAL INDICATOR
            if symbol_orders:
                status_item = QTableWidgetItem("🚨🚨 SELLING NOW 🚨🚨")
                status_item.setBackground(QColor("#dc3545"))  # Bright red
                status_item.setForeground(QColor("white"))
                status_item.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            else:
                status_item = QTableWidgetItem("✅ Open Position")
                status_item.setBackground(QColor("#28a745"))  # Green
                status_item.setForeground(QColor("white"))
                status_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.table.setItem(row, 4, status_item)
            
            # PENDING SELLS - MASSIVE RED BOX
            if symbol_orders:
                pending_text = f"🚨🚨 SELLING {sum(o['qty'] for o in symbol_orders):,} SHARES NOW 🚨🚨\n\n"
                for order in symbol_orders:
                    pending_text += f"🔥 {order['qty']:,} shares - {order['status']} 🔥\n"
                pending_text = pending_text.strip()
                
                pending_item = QTableWidgetItem(pending_text)
                pending_item.setBackground(QColor("#dc3545"))  # Bright red
                pending_item.setForeground(QColor("white"))
                pending_item.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            else:
                pending_item = QTableWidgetItem("✅ No pending sales")
                pending_item.setBackground(QColor("#28a745"))  # Green
                pending_item.setForeground(QColor("white"))
                pending_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            self.table.setItem(row, 5, pending_item)
            
            # Action button - DIFFERENT for selling
            if symbol_orders:
                action_btn = QPushButton("🚨 CURRENTLY SELLING 🚨")
                action_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dc3545;
                        color: white;
                        font-weight: bold;
                        padding: 12px;
                        border-radius: 6px;
                        border: 3px solid #fff;
                        font-size: 12px;
                    }
                """)
                action_btn.setEnabled(False)
            else:
                action_btn = QPushButton(f"🚨 Sell {symbol} Now")
                action_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffc107;
                        color: #212529;
                        font-weight: bold;
                        padding: 10px;
                        border-radius: 4px;
                        border: none;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #e0a800;
                    }
                """)
                action_btn.clicked.connect(lambda checked, s=symbol: self.close_single_position(s))
            
            self.table.setCellWidget(row, 6, action_btn)
            
            # Details - RED background if selling
            details = f"Avg: ${pos['avg_cost']:.2f}\nCurrent: ${pos['market_price']:.2f}"
            details_item = QTableWidgetItem(details)
            if is_selling:
                details_item.setBackground(QColor("#dc3545"))
                details_item.setForeground(QColor("white"))
                details_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            else:
                details_item.setFont(QFont("Arial", 10))
            self.table.setItem(row, 7, details_item)
            
            row += 1
    
    def close_single_position(self, symbol):
        """Close a single position with confirmation"""
        positions = {item.contract.symbol: item for item in self.ib.portfolio() if item.position > 0}
        if symbol not in positions:
            return
            
        pos = positions[symbol]
        qty = int(pos.position)
        value = float(pos.marketValue)
        
        reply = QMessageBox.question(
            self, '🚨 Close Position',
            f'Place MARKET SELL order for {symbol}?\n\n'
            f'Quantity: {qty:,} shares\n'
            f'Current Value: ${value:,.2f}\n\n'
            f'⚠️ This will sell at the current market price immediately!',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                contract = Stock(symbol, 'SMART', 'USD')
                order = MarketOrder('SELL', qty)
                trade = self.ib.placeOrder(contract, order)
                self.log_msg(f"✅ Placed market sell order: {qty:,} shares of {symbol}", "SUCCESS")
                
                # Refresh after delay
                QTimer.singleShot(3000, self.refresh_data)
                
            except Exception as e:
                self.log_msg(f"❌ Error selling {symbol}: {str(e)}", "ERROR")
    
    def close_all_positions(self):
        """Close all open positions with strong confirmation"""
        positions = [item for item in self.ib.portfolio() if item.position > 0]
        if not positions:
            QMessageBox.information(self, "No Positions", "No open positions to close.")
            return
        
        total_value = sum(float(item.marketValue) for item in positions)
        
        reply = QMessageBox.question(
            self, '🚨 CLOSE ALL POSITIONS',
            f'⚠️ DANGER: Close ALL {len(positions)} positions?\n\n'
            f'Total Portfolio Value: ${total_value:,.2f}\n\n'
            f'This will place MARKET SELL orders for:\n' + 
            '\n'.join([f'• {item.contract.symbol}: {int(item.position):,} shares (${float(item.marketValue):,.0f})' 
                      for item in positions[:5]]) +
            (f'\n... and {len(positions)-5} more' if len(positions) > 5 else '') +
            f'\n\n🔥 THIS ACTION CANNOT BE UNDONE! 🔥',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                orders_placed = 0
                for item in positions:
                    symbol = item.contract.symbol
                    qty = int(item.position)
                    contract = Stock(symbol, 'SMART', 'USD')
                    order = MarketOrder('SELL', qty)
                    trade = self.ib.placeOrder(contract, order)
                    orders_placed += 1
                    self.log_msg(f"✅ Placed sell order: {qty:,} shares of {symbol}", "SUCCESS")
                
                self.log_msg(f"🚨 Placed {orders_placed} market sell orders for all positions!", "WARNING")
                QTimer.singleShot(5000, self.refresh_data)
                
            except Exception as e:
                self.log_msg(f"❌ Error closing positions: {str(e)}", "ERROR")
    
    def closeEvent(self, event):
        """Clean shutdown"""
        if hasattr(self, 'auto_timer'):
            self.auto_timer.stop()
            
        # Only disconnect if we own the connection
        if self.ib and self.ib.isConnected() and self.owns_connection:
            self.ib.disconnect()
        
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    monitor = ImprovedMonitor()
    monitor.show()
    app.exec()