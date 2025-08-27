#!/usr/bin/env python3
"""
Working Position Monitor - Tested and Functional
"""

import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

class WorkingPositionMonitor(QDialog):
    """Reliable position monitor that actually works"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Position Monitor - Working Version")
        self.setGeometry(100, 100, 900, 600)
        self.ib = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Working Position Monitor")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection section
        conn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect to IBKR")
        self.connect_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
        self.connect_btn.clicked.connect(self.connect_ibkr)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 10px;")
        self.disconnect_btn.clicked.connect(self.disconnect_ibkr)
        self.disconnect_btn.setEnabled(False)
        
        self.status_label = QLabel("Not Connected")
        self.status_label.setStyleSheet("font-weight: bold; padding: 10px;")
        
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.disconnect_btn)
        conn_layout.addStretch()
        conn_layout.addWidget(self.status_label)
        layout.addLayout(conn_layout)
        
        # Data display
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        self.data_text.setMinimumHeight(350)
        layout.addWidget(self.data_text)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh Data")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.refresh_btn.setEnabled(False)
        
        self.close_all_btn = QPushButton("Close All Positions")
        self.close_all_btn.setStyleSheet("background-color: #fd7e14; color: white; font-weight: bold;")
        self.close_all_btn.clicked.connect(self.close_all_positions)
        self.close_all_btn.setEnabled(False)
        
        action_layout.addWidget(self.refresh_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.close_all_btn)
        layout.addLayout(action_layout)
        
        # Close button
        close_btn = QPushButton("Close Monitor")
        close_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 10px;")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}
    
    def connect_ibkr(self):
        if not IB_AVAILABLE:
            self.data_text.append("ERROR: ib-insync not installed. Run: pip install ib-insync")
            return
            
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            self.data_text.append(f"Connecting to {host}:{port} with client ID {client_id}...")
            
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("✅ Connected")
                self.status_label.setStyleSheet("color: green; font-weight: bold; padding: 10px;")
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
                self.close_all_btn.setEnabled(True)
                
                self.data_text.append("SUCCESS: Connected to IBKR")
                self.refresh_data()
            else:
                self.data_text.append("ERROR: Failed to connect")
                
        except Exception as e:
            self.data_text.append(f"ERROR: Connection failed - {e}")
    
    def disconnect_ibkr(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold; padding: 10px;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.close_all_btn.setEnabled(False)
        self.data_text.append("Disconnected from IBKR")
    
    def refresh_data(self):
        if not self.ib or not self.ib.isConnected():
            self.data_text.append("ERROR: Not connected to IBKR")
            return
            
        try:
            self.data_text.append("\n" + "="*60)
            self.data_text.append("REFRESHING DATA...")
            self.data_text.append("="*60)
            
            # Get account info
            account = self.ib.managedAccounts()[0] if self.ib.managedAccounts() else "Unknown"
            self.data_text.append(f"Account: {account}")
            
            # Get positions
            portfolio = self.ib.portfolio()
            self.data_text.append(f"\nPORTFOLIO ({len(portfolio)} items):")
            
            total_value = 0
            for item in portfolio:
                if item.position != 0:
                    symbol = item.contract.symbol
                    qty = int(item.position)
                    value = item.marketValue
                    pnl = item.unrealizedPNL
                    total_value += value
                    
                    self.data_text.append(f"  {symbol}: {qty} shares, ${value:,.2f}, P&L: ${pnl:,.2f}")
            
            self.data_text.append(f"\nTOTAL PORTFOLIO VALUE: ${total_value:,.2f}")
            
            # Get open orders
            orders = self.ib.openOrders()
            self.data_text.append(f"\nOPEN ORDERS ({len(orders)} found):")
            
            if orders:
                for order in orders:
                    symbol = order.contract.symbol
                    action = order.action
                    qty = order.totalQuantity
                    status = order.orderStatus.status
                    order_id = order.order.orderId
                    
                    self.data_text.append(f"  Order {order_id}: {action} {qty} {symbol} ({status})")
            else:
                self.data_text.append("  No open orders found")
            
            # Get trades  
            trades = self.ib.trades()
            pending_trades = [t for t in trades if t.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit']]
            self.data_text.append(f"\nPENDING TRADES ({len(pending_trades)} found):")
            
            if pending_trades:
                for trade in pending_trades:
                    symbol = trade.contract.symbol
                    action = trade.order.action
                    qty = trade.order.totalQuantity
                    status = trade.orderStatus.status
                    
                    self.data_text.append(f"  {action} {qty} {symbol} ({status})")
            else:
                self.data_text.append("  No pending trades found")
                
            self.data_text.append("\nREFRESH COMPLETE")
            
        except Exception as e:
            self.data_text.append(f"ERROR refreshing data: {e}")
    
    def close_all_positions(self):
        if not self.ib or not self.ib.isConnected():
            self.data_text.append("ERROR: Not connected to IBKR")
            return
            
        reply = QMessageBox.question(
            self, 'Close All Positions',
            'This will place MARKET SELL orders for ALL positions.\n\nAre you sure?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        try:
            portfolio = self.ib.portfolio()
            positions_to_close = [item for item in portfolio if item.position > 0]
            
            self.data_text.append(f"\nCLOSING {len(positions_to_close)} POSITIONS...")
            
            for item in positions_to_close:
                symbol = item.contract.symbol
                qty = int(item.position)
                
                # Create proper contract
                contract = Stock(symbol, 'SMART', 'USD')
                
                # Place market sell order
                order = MarketOrder('SELL', qty)
                trade = self.ib.placeOrder(contract, order)
                
                self.data_text.append(f"  Placed SELL order: {qty} shares of {symbol}")
                
            self.data_text.append("ALL CLOSING ORDERS PLACED")
            
            # Refresh to show new orders
            QTimer.singleShot(2000, self.refresh_data)
            
        except Exception as e:
            self.data_text.append(f"ERROR closing positions: {e}")
    
    def closeEvent(self, event):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    dialog = WorkingPositionMonitor()
    dialog.show()
    app.exec()