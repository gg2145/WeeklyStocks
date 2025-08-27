#!/usr/bin/env python3
"""
SIMPLE WORKING MONITOR - No complexity, just works
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

from pending_sales import pending_tracker

class SimpleWorkingMonitor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIMPLE WORKING Monitor")
        self.setGeometry(200, 200, 1000, 600)
        
        self.ib = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("SIMPLE WORKING MONITOR")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection
        conn_layout = QHBoxLayout()
        self.status_label = QLabel("Not Connected")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ibkr)
        
        conn_layout.addWidget(self.status_label)
        conn_layout.addStretch()
        conn_layout.addWidget(self.connect_btn)
        layout.addLayout(conn_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Symbol", "Position", "Orders", "STATUS"])
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_simple)
        
        buy_btn = QPushButton("Add Buy Order")
        buy_btn.clicked.connect(self.add_buy_order)
        
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(buy_btn)
        layout.addLayout(btn_layout)
        
        # Log
        self.log = QTextEdit()
        self.log.setMaximumHeight(150)
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        
    def log_msg(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {msg}")
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def connect_ibkr(self):
        if not IB_AVAILABLE:
            self.log_msg("ERROR: ib-insync not installed")
            return
            
        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
            
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 1)) + 20  # Use +20 to avoid any conflicts
            
            self.log_msg(f"Connecting to {host}:{port} with client ID {client_id}")
            
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                self.connect_btn.setText("Disconnect")
                self.connect_btn.clicked.disconnect()
                self.connect_btn.clicked.connect(self.disconnect_ibkr)
                self.log_msg("Connected successfully")
                self.refresh_simple()
            else:
                self.log_msg("Connection failed")
                
        except Exception as e:
            self.log_msg(f"Connection error: {e}")

    def disconnect_ibkr(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        
        self.status_label.setText("Not Connected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.connect_btn.setText("Connect")
        self.connect_btn.clicked.disconnect()
        self.connect_btn.clicked.connect(self.connect_ibkr)
        self.log_msg("Disconnected")

    def refresh_simple(self):
        """SIMPLE refresh - just show what we have"""
        try:
            self.log_msg("=== SIMPLE REFRESH ===")
            
            # Get positions if connected
            positions = {}
            if self.ib and self.ib.isConnected():
                portfolio = self.ib.portfolio()
                for item in portfolio:
                    if item.position != 0:
                        positions[item.contract.symbol] = int(item.position)
                self.log_msg(f"IBKR positions: {positions}")
            else:
                self.log_msg("Not connected - showing pending orders only")
            
            # Get pending orders
            pending_sales = pending_tracker.get_all_pending_sales()
            pending_buys = pending_tracker.get_all_pending_buys()
            
            self.log_msg(f"Pending sales: {list(pending_sales.keys())}")
            self.log_msg(f"Pending buys: {list(pending_buys.keys())}")
            
            # Combine all symbols
            all_symbols = set(positions.keys())
            all_symbols.update(pending_sales.keys())
            all_symbols.update(pending_buys.keys())
            
            self.log_msg(f"All symbols to show: {sorted(all_symbols)}")
            
            # Update table
            self.table.setRowCount(len(all_symbols))
            
            for row, symbol in enumerate(sorted(all_symbols)):
                self.log_msg(f"Processing row {row}: {symbol}")
                
                # Symbol
                self.table.setItem(row, 0, QTableWidgetItem(symbol))
                
                # Position
                pos_qty = positions.get(symbol, 0)
                self.table.setItem(row, 1, QTableWidgetItem(str(pos_qty)))
                
                # Orders
                orders_text = []
                if symbol in pending_sales:
                    qty = pending_sales[symbol]['quantity']
                    orders_text.append(f"SELL {qty}")
                if symbol in pending_buys:
                    qty = pending_buys[symbol]['quantity']
                    orders_text.append(f"BUY {qty}")
                
                orders_str = ", ".join(orders_text) if orders_text else "None"
                self.table.setItem(row, 2, QTableWidgetItem(orders_str))
                
                # STATUS - THE IMPORTANT PART
                if symbol in pending_sales:
                    status_item = QTableWidgetItem("PENDING SALE")
                    status_item.setBackground(QColor("red"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                    self.log_msg(f"Set PENDING SALE status for {symbol}")
                elif symbol in pending_buys:
                    status_item = QTableWidgetItem("PENDING BUY")
                    status_item.setBackground(QColor("blue"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                    self.log_msg(f"Set PENDING BUY status for {symbol}")
                else:
                    status_item = QTableWidgetItem("Open")
                    status_item.setForeground(QColor("green"))
                    self.log_msg(f"Set Open status for {symbol}")
                    
                self.table.setItem(row, 3, status_item)
            
            self.log_msg(f"=== REFRESH COMPLETE: {len(all_symbols)} symbols ===")
            
        except Exception as e:
            self.log_msg(f"Refresh error: {e}")
            import traceback
            self.log_msg(traceback.format_exc())
    
    def add_buy_order(self):
        """Add buy order"""
        if not self.ib or not self.ib.isConnected():
            self.log_msg("Not connected - cannot place order")
            return
            
        symbol, ok1 = QInputDialog.getText(self, 'Buy Order', 'Symbol:')
        if not ok1 or not symbol:
            return
            
        qty, ok2 = QInputDialog.getInt(self, 'Buy Order', f'Quantity for {symbol}:', 100, 1, 10000)
        if not ok2:
            return
            
        try:
            # Place IBKR order
            contract = Stock(symbol.upper(), 'SMART', 'USD')
            order = MarketOrder('BUY', qty)
            trade = self.ib.placeOrder(contract, order)
            
            # Track it
            pending_tracker.mark_as_pending_buy(symbol.upper(), qty, "MARKET", notes="Manual buy")
            
            self.log_msg(f"Buy order placed: {qty} shares of {symbol}")
            QTimer.singleShot(1000, self.refresh_simple)
            
        except Exception as e:
            self.log_msg(f"Buy order error: {e}")

if __name__ == "__main__":
    app = QApplication([])
    monitor = SimpleWorkingMonitor()
    monitor.show()
    app.exec()