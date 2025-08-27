#!/usr/bin/env python3
"""
Working Position Monitor - Simple and Reliable
No threading, no complex event loops, just basic functionality that works
"""

import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

# Import our pending sales tracker for automatic tracking
try:
    from pending_sales import pending_tracker
    PENDING_TRACKING_AVAILABLE = True
except ImportError:
    PENDING_TRACKING_AVAILABLE = False

class WorkingMonitor(QDialog):
    """Simple, working position monitor"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Position Monitor")
        self.setGeometry(200, 200, 1000, 600)  # Reasonable size
        
        self.ib = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Position Monitor")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection
        conn_layout = QHBoxLayout()
        self.status_label = QLabel("Not Connected")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ibkr)
        
        conn_layout.addWidget(self.status_label)
        conn_layout.addStretch()
        conn_layout.addWidget(self.connect_btn)
        layout.addLayout(conn_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Position", "Pending Sells", "Market Value", "P&L", "Action", "Status"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        
        # Log
        self.log = QTextEdit()
        self.log.setMaximumHeight(120)
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        
        close_all_btn = QPushButton("Close All Positions")
        close_all_btn.setStyleSheet("background-color: orange; color: white; font-weight: bold;")
        close_all_btn.clicked.connect(self.close_all)
        
        close_btn = QPushButton("Close Monitor")
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
        self.log.append(f"{msg}")
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
            
            self.log_msg(f"Connecting to {host}:{port} client {client_id}...")
            
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet("font-weight: bold; color: green;")
                self.connect_btn.setText("Disconnect")
                self.connect_btn.clicked.disconnect()
                self.connect_btn.clicked.connect(self.disconnect_ibkr)
                self.log_msg("Connected successfully")
                self.refresh_data()
            else:
                self.log_msg("Connection failed")
                
        except Exception as e:
            self.log_msg(f"Connection error: {e}")
    
    def disconnect_ibkr(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        
        self.status_label.setText("Not Connected")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        self.connect_btn.setText("Connect")
        self.connect_btn.clicked.disconnect()
        self.connect_btn.clicked.connect(self.connect_ibkr)
        self.log_msg("Disconnected")
    
    def refresh_data(self):
        if not self.ib or not self.ib.isConnected():
            self.log_msg("Not connected")
            return
            
        try:
            self.log_msg("Getting positions and orders...")
            
            # Get positions
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
            
            # Get ALL orders - try every method
            all_orders = {}
            
            # Method 1: openOrders
            orders1 = self.ib.openOrders()
            self.log_msg(f"openOrders(): {len(orders1)} orders")
            for order in orders1:
                all_orders[order.order.orderId] = order
            
            # Method 2: reqAllOpenOrders
            try:
                orders2 = self.ib.reqAllOpenOrders()
                self.log_msg(f"reqAllOpenOrders(): {len(orders2)} orders")
                for order in orders2:
                    all_orders[order.order.orderId] = order
            except Exception as e:
                self.log_msg(f"reqAllOpenOrders failed: {e}")
            
            # Method 3: trades
            try:
                trades = self.ib.trades()
                pending = [t for t in trades if t.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit']]
                self.log_msg(f"trades(): {len(pending)} pending")
                for trade in pending:
                    all_orders[trade.order.orderId] = trade
            except Exception as e:
                self.log_msg(f"trades() failed: {e}")
            
            # Update table
            self.table.setRowCount(len(positions))
            row = 0
            
            for symbol, pos in positions.items():
                # Find pending sell orders for this symbol
                pending_sells = []
                for order_id, order_data in all_orders.items():
                    if (order_data.contract.symbol == symbol and 
                        order_data.order.action == 'SELL'):
                        qty = int(order_data.order.totalQuantity)
                        status = order_data.orderStatus.status
                        pending_sells.append(f"{qty} shares ({status})")
                
                # Populate row
                self.table.setItem(row, 0, QTableWidgetItem(symbol))
                self.table.setItem(row, 1, QTableWidgetItem(str(pos['qty'])))
                
                # Pending sells - VERY VISIBLE
                if pending_sells:
                    pending_text = "; ".join(pending_sells)
                    pending_item = QTableWidgetItem(f"SELLING: {pending_text}")
                    pending_item.setBackground(QColor("#ffcccc"))
                    pending_item.setForeground(QColor("#cc0000"))
                    font = QFont()
                    font.setBold(True)
                    pending_item.setFont(font)
                else:
                    pending_item = QTableWidgetItem("None")
                self.table.setItem(row, 2, pending_item)
                
                self.table.setItem(row, 3, QTableWidgetItem(f"${pos['value']:,.0f}"))
                
                # P&L with color
                pnl_item = QTableWidgetItem(f"${pos['pnl']:,.0f}")
                if pos['pnl'] >= 0:
                    pnl_item.setForeground(QColor("green"))
                else:
                    pnl_item.setForeground(QColor("red"))
                self.table.setItem(row, 4, pnl_item)
                
                # Action button
                if pending_sells:
                    btn = QPushButton("Selling...")
                    btn.setEnabled(False)
                    btn.setStyleSheet("background-color: #ffcccc;")
                else:
                    btn = QPushButton("Close")
                    btn.clicked.connect(lambda checked, s=symbol: self.close_position(s))
                self.table.setCellWidget(row, 5, btn)
                
                # Status
                if pending_sells:
                    self.table.setItem(row, 6, QTableWidgetItem("PENDING SALE"))
                else:
                    self.table.setItem(row, 6, QTableWidgetItem("Open"))
                
                row += 1
            
            self.log_msg(f"Updated: {len(positions)} positions, {len(all_orders)} orders total")
            
        except Exception as e:
            self.log_msg(f"Refresh error: {e}")
    
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
                        if PENDING_TRACKING_AVAILABLE:
                            try:
                                result = pending_tracker.mark_as_pending_sale(symbol, qty, "MARKET", notes="Manual sell via monitor")
                                self.log_msg(f"Auto-tracked: {result}")
                            except Exception as e:
                                self.log_msg(f"Tracking failed: {e}")
                        
                        self.log_msg(f"Placed sell order: {qty} shares of {symbol}")
                        break
                
                # Refresh after short delay
                QTimer.singleShot(2000, self.refresh_data)
                
            except Exception as e:
                self.log_msg(f"Error closing {symbol}: {e}")
    
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
                        if PENDING_TRACKING_AVAILABLE:
                            try:
                                result = pending_tracker.mark_as_pending_sale(symbol, qty, "MARKET", notes="Close all positions")
                                self.log_msg(f"Auto-tracked: {result}")
                            except Exception as e:
                                self.log_msg(f"Tracking failed: {e}")
                        
                        self.log_msg(f"Placed sell order: {qty} shares of {symbol}")
                
                QTimer.singleShot(3000, self.refresh_data)
                
            except Exception as e:
                self.log_msg(f"Error closing all: {e}")
    
    def closeEvent(self, event):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    monitor = WorkingMonitor()
    monitor.show()
    app.exec()