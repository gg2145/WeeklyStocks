#!/usr/bin/env python3
"""
Simple Position Monitor - No Threading Issues
"""

import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                            QTableWidgetItem, QPushButton, QLabel, QTextEdit,
                            QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

class SimplePositionMonitor(QDialog):
    """Simple position monitor without complex threading"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simple Position Monitor")
        self.setGeometry(100, 100, 1000, 600)
        self.ib = None
        self.positions = {}
        
        self.init_ui()
        self.connect_to_ibkr()
        
        # Set up timer for updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000)  # Update every 5 seconds
        
    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Simple Position Monitor")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Status
        self.status_label = QLabel("Connecting...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh Now")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        self.close_all_btn = QPushButton("Close All Positions")
        self.close_all_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.close_all_btn.clicked.connect(self.close_all_positions)
        
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_all_btn)
        layout.addLayout(button_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Quantity", "Pending Orders", "Avg Cost", "Market Price", 
            "Market Value", "Unrealized P&L", "Action"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Summary
        self.summary_label = QLabel("Portfolio Summary: No data")
        self.summary_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 10px;")
        layout.addWidget(self.summary_label)
        
        # Log
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Close button
        close_btn = QPushButton("Close Monitor")
        close_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 10px;")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
    def connect_to_ibkr(self):
        """Simple synchronous connection"""
        if not IB_AVAILABLE:
            self.status_label.setText("❌ ib-insync not available")
            self.log_text.append("Error: ib-insync not installed")
            return
            
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            self.log_text.append(f"Connecting to {host}:{port} with client ID {client_id}...")
            
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("✅ Connected to IBKR")
                self.status_label.setStyleSheet("color: green; font-weight: bold; padding: 10px;")
                self.log_text.append("✅ Connected successfully")
                self.refresh_data()
            else:
                self.status_label.setText("❌ Failed to connect")
                self.status_label.setStyleSheet("color: red; font-weight: bold; padding: 10px;")
                
        except Exception as e:
            self.status_label.setText(f"❌ Connection error")
            self.status_label.setStyleSheet("color: red; font-weight: bold; padding: 10px;")
            self.log_text.append(f"❌ Connection failed: {e}")
    
    def refresh_data(self):
        """Refresh positions and orders"""
        if not self.ib or not self.ib.isConnected():
            return
            
        try:
            self.log_text.append("Refreshing data...")
            
            # Get positions
            positions = {}
            portfolio_items = self.ib.portfolio()
            self.log_text.append(f"Portfolio contains {len(portfolio_items)} items")
            
            for item in portfolio_items:
                self.log_text.append(f"Portfolio item: {item.contract.symbol} position:{item.position} value:{item.marketValue}")
                if item.position != 0:
                    symbol = item.contract.symbol
                    positions[symbol] = {
                        'contract': item.contract,
                        'quantity': int(item.position),
                        'avg_cost': float(item.averageCost),
                        'market_price': float(item.marketPrice),
                        'market_value': float(item.marketValue),
                        'unrealized_pnl': float(item.unrealizedPNL),
                        'pending_orders': []
                    }
            
            # Get open orders with more debugging
            try:
                # Get client info
                client_id = self.ib.client.clientId
                self.log_text.append(f"Connected as client ID: {client_id}")
                
                # Try multiple ways to get orders
                open_orders = self.ib.openOrders()
                self.log_text.append(f"openOrders() returned {len(open_orders)} orders")
                
                # Try all open orders
                try:
                    all_orders = self.ib.reqAllOpenOrders()
                    self.log_text.append(f"reqAllOpenOrders() returned {len(all_orders)} orders")
                    combined_orders = list(open_orders) + list(all_orders)
                except Exception as e:
                    self.log_text.append(f"reqAllOpenOrders() failed: {e}")
                    combined_orders = open_orders
                
                # Try getting completed orders too
                try:
                    from ib_insync import Trade
                    trades = self.ib.trades()
                    pending_trades = [t for t in trades if t.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit']]
                    self.log_text.append(f"Found {len(pending_trades)} pending trades")
                    for trade in pending_trades:
                        self.log_text.append(f"Pending trade: {trade.contract.symbol} {trade.order.action} {trade.order.totalQuantity} status:{trade.orderStatus.status}")
                except Exception as e:
                    self.log_text.append(f"Error getting trades: {e}")
                
                # Process orders
                unique_orders = {order.order.orderId: order for order in combined_orders}.values()
                self.log_text.append(f"Processing {len(unique_orders)} unique orders")
                
                for order in unique_orders:
                    self.log_text.append(f"Order: {order.contract.symbol} {order.action} {order.totalQuantity} status:{order.orderStatus.status} clientId:{order.order.clientId}")
                    symbol = order.contract.symbol
                    if symbol in positions and order.action == 'SELL':
                        positions[symbol]['pending_orders'].append({
                            'action': order.action,
                            'quantity': int(order.totalQuantity),
                            'status': order.orderStatus.status,
                            'order_id': order.order.orderId
                        })
                        
            except Exception as e:
                self.log_text.append(f"Error getting orders: {e}")
            
            self.positions = positions
            self.update_table()
            
        except Exception as e:
            self.log_text.append(f"Error refreshing: {e}")
    
    def update_table(self):
        """Update the positions table"""
        self.table.setRowCount(len(self.positions))
        
        total_value = 0
        total_pnl = 0
        
        for row, (symbol, pos) in enumerate(self.positions.items()):
            # Symbol
            self.table.setItem(row, 0, QTableWidgetItem(symbol))
            
            # Quantity
            self.table.setItem(row, 1, QTableWidgetItem(str(pos['quantity'])))
            
            # Pending orders
            pending_orders = pos['pending_orders']
            if pending_orders:
                order_text = f"{len(pending_orders)} SELL orders"
                for order in pending_orders:
                    order_text += f"\n{order['quantity']} shares ({order['status']})"
                pending_item = QTableWidgetItem(order_text)
                pending_item.setForeground(Qt.GlobalColor.red)
            else:
                pending_item = QTableWidgetItem("None")
            self.table.setItem(row, 2, pending_item)
            
            # Avg Cost
            self.table.setItem(row, 3, QTableWidgetItem(f"${pos['avg_cost']:.2f}"))
            
            # Market Price
            self.table.setItem(row, 4, QTableWidgetItem(f"${pos['market_price']:.2f}"))
            
            # Market Value
            value = pos['market_value']
            total_value += value
            self.table.setItem(row, 5, QTableWidgetItem(f"${value:.2f}"))
            
            # Unrealized P&L
            pnl = pos['unrealized_pnl']
            total_pnl += pnl
            pnl_item = QTableWidgetItem(f"${pnl:.2f}")
            if pnl >= 0:
                pnl_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                pnl_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 6, pnl_item)
            
            # Action button
            if pending_orders:
                close_btn = QPushButton("SELLING...")
                close_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
                close_btn.setEnabled(False)
            else:
                close_btn = QPushButton("Close")
                close_btn.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold;")
                close_btn.clicked.connect(lambda checked, s=symbol: self.close_position(s))
            self.table.setCellWidget(row, 7, close_btn)
        
        # Update summary
        if self.positions:
            pnl_pct = (total_pnl / (total_value - total_pnl)) * 100 if (total_value - total_pnl) > 0 else 0
            self.summary_label.setText(
                f"Portfolio: {len(self.positions)} positions | "
                f"Value: ${total_value:.2f} | "
                f"P&L: ${total_pnl:.2f} ({pnl_pct:+.1f}%)"
            )
        else:
            self.summary_label.setText("Portfolio: No active positions")
    
    def close_position(self, symbol):
        """Close a single position"""
        if symbol not in self.positions:
            return
            
        pos = self.positions[symbol]
        reply = QMessageBox.question(
            self, 'Close Position',
            f'Close {symbol} position?\n'
            f'Quantity: {pos["quantity"]}\n'
            f'Current Value: ${pos["market_value"]:.2f}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.place_sell_order(symbol, pos)
    
    def close_all_positions(self):
        """Close all positions"""
        if not self.positions:
            QMessageBox.information(self, "No Positions", "No positions to close")
            return
            
        reply = QMessageBox.question(
            self, 'Close All Positions',
            f'Close ALL {len(self.positions)} positions?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for symbol, pos in self.positions.items():
                self.place_sell_order(symbol, pos)
    
    def place_sell_order(self, symbol, pos):
        """Place a sell order for a position"""
        try:
            if not self.ib or not self.ib.isConnected():
                self.log_text.append(f"❌ Not connected - cannot sell {symbol}")
                return
                
            # Create contract with proper exchange
            contract = Stock(
                symbol=symbol,
                exchange=pos['contract'].primaryExchange,
                currency=pos['contract'].currency
            )
            
            # Place market sell order
            trade = self.ib.placeOrder(contract, MarketOrder("SELL", abs(pos['quantity'])))
            self.log_text.append(f"✅ Sell order placed for {symbol}: {abs(pos['quantity'])} shares")
            
            # Refresh immediately to show pending order
            self.refresh_data()
            
        except Exception as e:
            self.log_text.append(f"❌ Error selling {symbol}: {e}")
    
    def closeEvent(self, event):
        """Clean up on close"""
        if self.timer:
            self.timer.stop()
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        event.accept()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    dialog = SimplePositionMonitor()
    dialog.show()
    sys.exit(app.exec())