#!/usr/bin/env python3
"""
Professional Position Monitor - Cleaned Up Version
Maximizes table space to show 10+ positions without scrolling
"""

import json
import sys
import time
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                            QTableWidget, QTableWidgetItem, QPushButton, QLabel, 
                            QTextEdit, QMessageBox, QHeaderView, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

try:
    from ib_insync import IB, Stock, MarketOrder, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

class ProfessionalPositionMonitor(QDialog):
    """Professional position monitor optimized to show 10+ positions"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Professional Position Monitor - Clean Layout")
        
        # Set window flags to make it more stable
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        
        # Fixed window size optimized for maximum table space
        self.setMinimumSize(1000, 650)
        self.resize(1000, 650)
        
        # Center the window
        self.move(200, 150)
        
        self.ib = None
        self.positions_data = {}
        self.orders_data = {}
        
        self.init_ui()
        
        # Check for existing IBKR connection on startup
        QTimer.singleShot(500, self.check_existing_connection)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)  # Minimal spacing between elements
        layout.setContentsMargins(10, 10, 10, 10)  # Minimal margins
        
        # Compact header - single line
        header = QLabel("Professional Position Monitor - Clean Layout")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection and Account info - SINGLE COMPACT ROW
        info_layout = QHBoxLayout()
        info_layout.setSpacing(20)
        
        # Connection status and buttons
        self.status_label = QLabel("Checking connection...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #f39c12;")
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; 
                color: white; 
                font-weight: bold; 
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        self.connect_btn.clicked.connect(self.connect_to_ibkr)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; 
                color: white; 
                font-weight: bold; 
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.disconnect_btn.clicked.connect(self.disconnect_from_ibkr)
        self.disconnect_btn.setEnabled(False)
        
        # Account info labels
        self.account_label = QLabel("Account: --")
        self.total_value_label = QLabel("Total: --")
        self.total_pnl_label = QLabel("P&L: --")
        
        # Add all to single row
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.connect_btn)
        info_layout.addWidget(self.disconnect_btn)
        info_layout.addStretch()
        info_layout.addWidget(self.account_label)
        info_layout.addWidget(self.total_value_label)
        info_layout.addWidget(self.total_pnl_label)
        
        layout.addLayout(info_layout)
        
        # POSITIONS TABLE - MAXIMUM SPACE ALLOCATION
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Position", "Pending Sell Orders", "Avg Cost", 
            "Market Price", "Market Value", "Unrealized P&L", "Action"
        ])
        
        # CRITICAL: Set row height to exactly 30px for maximum positions
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setVisible(False)  # Hide row numbers to save space
        
        # Set table to expand and fill all available space
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setMinimumHeight(450)  # Ensure minimum height for many positions
        
        # Configure column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Set Action column to fixed width so it's always readable
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 100)  # Compact but readable Action column
        
        # Clean table styling
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                alternate-background-color: #f8f9fa;
                font-size: 12px;
                border: 1px solid #bdc3c7;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 6px;
                font-weight: bold;
                border: none;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px;
                border: none;
            }
        """)
        
        layout.addWidget(self.table)
        
        # Action buttons - COMPACT ROW
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.refresh_btn = QPushButton("Manual Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; 
                color: white; 
                font-weight: bold; 
                padding: 8px 12px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
        """)
        self.refresh_btn.clicked.connect(self.manual_refresh)
        self.refresh_btn.setEnabled(False)
        
        self.close_all_btn = QPushButton("Close All Positions")
        self.close_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12; 
                color: white; 
                font-weight: bold; 
                padding: 8px 12px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
        """)
        self.close_all_btn.clicked.connect(self.close_all_positions)
        self.close_all_btn.setEnabled(False)
        
        self.close_monitor_btn = QPushButton("Close Monitor")
        self.close_monitor_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; 
                color: white; 
                font-weight: bold; 
                padding: 8px 12px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
            }
        """)
        self.close_monitor_btn.clicked.connect(self.close)
        
        action_layout.addWidget(self.refresh_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.close_all_btn)
        action_layout.addWidget(self.close_monitor_btn)
        layout.addLayout(action_layout)
        
        # Status bar instead of log area - MINIMAL HEIGHT
        self.status_bar = QLabel("Ready")
        self.status_bar.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 4px 8px;
                border: 1px solid #34495e;
            }
        """)
        layout.addWidget(self.status_bar)
        
    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}
    
    def check_existing_connection(self):
        """Check if IBKR is already connected from main menu"""
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            # Try a quick connection test with a different client ID
            test_ib = IB()
            try:
                test_ib.connect(host, port, clientId=client_id + 100, timeout=3)
                if test_ib.isConnected():
                    test_ib.disconnect()
                    self.status_label.setText("✅ IBKR Available")
                    self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
                    self.update_status("IBKR detected and available")
                else:
                    self.status_label.setText("❌ IBKR Not Running")
                    self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
            except:
                self.status_label.setText("❌ IBKR Not Running")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
        except:
            self.status_label.setText("⚠️ Connection Check Failed")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #f39c12;")
    
    def update_status(self, message):
        """Update the status bar with timestamp"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_bar.setText(f"[{timestamp}] {message}")
    
    def connect_to_ibkr(self):
        if not IB_AVAILABLE:
            self.update_status("ERROR: ib-insync not available. Install with: pip install ib-insync")
            return
        
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            self.update_status(f"Connecting to {host}:{port} with client ID {client_id}...")
            
            # Create IB instance
            self.ib = IB()
            
            # Set up event handlers
            self.ib.positionEvent += self.on_position_update
            self.ib.updatePortfolioEvent += self.on_portfolio_update
            self.ib.orderStatusEvent += self.on_order_status_update
            self.ib.errorEvent += self.on_error
            
            # Connect synchronously
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("✅ Connected")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
                
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
                self.close_all_btn.setEnabled(True)
                
                self.update_status("Connected to IBKR successfully")
                
                # Get initial data
                self.initial_data_load()
            else:
                self.update_status("Failed to connect to IBKR")
                
        except Exception as e:
            self.update_status(f"Connection error: {e}")
    
    def disconnect_from_ibkr(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            
        self.status_label.setText("❌ Disconnected")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
        
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.close_all_btn.setEnabled(False)
        
        self.update_status("Disconnected from IBKR")
    
    def initial_data_load(self):
        """Load initial positions and orders"""
        try:
            # Get account info
            accounts = self.ib.managedAccounts()
            if accounts:
                self.account_label.setText(f"Account: {accounts[0]}")
            
            # Get positions
            positions = self.ib.positions()
            for pos in positions:
                self.positions_data[pos.contract.symbol] = pos
            
            # Get portfolio
            portfolio = self.ib.portfolio()
            for item in portfolio:
                if item.position != 0:
                    self.positions_data[item.contract.symbol] = item
            
            # Get open orders
            orders = self.ib.openOrders()
            for order in orders:
                self.orders_data[order.order.orderId] = order
                
            # Try reqAllOpenOrders to get orders from all clients
            try:
                all_orders = self.ib.reqAllOpenOrders()
                for order in all_orders:
                    if order.order.orderId not in self.orders_data:
                        self.orders_data[order.order.orderId] = order
            except Exception as e:
                self.update_status(f"reqAllOpenOrders failed: {e}")
                
            # Get trades (including pending)
            trades = self.ib.trades()
            pending_count = 0
            for trade in trades:
                if trade.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit']:
                    if trade.order.orderId not in self.orders_data:
                        self.orders_data[trade.order.orderId] = trade
                        pending_count += 1
            
            self.update_display()
            self.update_status(f"Loaded {len(self.positions_data)} positions, {len(self.orders_data)} orders")
            
        except Exception as e:
            self.update_status(f"Error loading initial data: {e}")
    
    # EVENT HANDLERS
    def on_position_update(self, position):
        """Handle position updates in real-time"""
        self.positions_data[position.contract.symbol] = position
        self.update_display()
        self.update_status(f"Position updated: {position.contract.symbol}")
    
    def on_portfolio_update(self, item):
        """Handle portfolio updates in real-time"""
        if item.position != 0:
            self.positions_data[item.contract.symbol] = item
        else:
            # Position was closed
            if item.contract.symbol in self.positions_data:
                del self.positions_data[item.contract.symbol]
        
        self.update_display()
        self.update_status(f"Portfolio updated: {item.contract.symbol}")
    
    def on_order_status_update(self, trade):
        """Handle order status changes in real-time"""
        self.orders_data[trade.order.orderId] = trade
        self.update_display()
        
        status = trade.orderStatus.status
        symbol = trade.contract.symbol
        action = trade.order.action
        qty = trade.order.totalQuantity
        
        self.update_status(f"Order update: {action} {qty} {symbol} - {status}")
        
        # Remove completed orders from tracking
        if status in ['Filled', 'Cancelled', 'Inactive']:
            if trade.order.orderId in self.orders_data:
                del self.orders_data[trade.order.orderId]
    
    def on_error(self, reqId, errorCode, errorString, contract):
        """Handle errors from IBKR"""
        self.update_status(f"IBKR Error {errorCode}: {errorString}")
    
    def update_display(self):
        """Update the positions table with current data"""
        try:
            # Clear existing table
            self.table.setRowCount(0)
            
            total_value = 0
            total_pnl = 0
            row = 0
            
            for symbol, item in self.positions_data.items():
                self.table.insertRow(row)
                
                # Handle both Position and PortfolioItem objects
                if hasattr(item, 'position'):
                    qty = int(item.position)
                    
                    # Position objects don't have marketValue, PortfolioItem objects do
                    if hasattr(item, 'marketValue'):
                        # This is a PortfolioItem
                        value = float(item.marketValue)
                        pnl = float(item.unrealizedPNL)
                        avg_cost = float(item.averageCost)
                        market_price = float(item.marketPrice)
                    else:
                        # This is a Position object - calculate values manually
                        avg_cost = float(item.avgCost) if hasattr(item, 'avgCost') else 0.0
                        
                        # For Position objects, we need to get market price from contract
                        try:
                            # Request market data for this symbol
                            contract = item.contract
                            ticker = self.ib.reqMktData(contract, '', False, False)
                            self.ib.sleep(0.1)  # Brief wait for market data
                            
                            if ticker and ticker.marketPrice():
                                market_price = float(ticker.marketPrice())
                                value = qty * market_price
                                pnl = value - (qty * avg_cost)
                            else:
                                # Fallback values if market data unavailable
                                market_price = avg_cost
                                value = qty * avg_cost
                                pnl = 0.0
                                
                            # Cancel the market data subscription
                            self.ib.cancelMktData(contract)
                            
                        except Exception as e:
                            self.update_status(f"Could not get market data for {symbol}: {e}")
                            # Use fallback values
                            market_price = avg_cost
                            value = qty * avg_cost
                            pnl = 0.0
                else:
                    continue  # Skip if not a position item
                
                total_value += value
                total_pnl += pnl
                
                # Check for pending orders for this symbol
                pending_orders = []
                for order_id, order_data in self.orders_data.items():
                    if order_data.contract.symbol == symbol and order_data.order.action == 'SELL':
                        order_qty = int(order_data.order.totalQuantity)
                        status = order_data.orderStatus.status
                        pending_orders.append(f"SELLING {order_qty} ({status})")
                
                # Populate table cells with compact formatting
                self.table.setItem(row, 0, QTableWidgetItem(symbol))
                self.table.setItem(row, 1, QTableWidgetItem(str(qty)))
                
                # Pending orders column
                if pending_orders:
                    pending_text = "\n".join(pending_orders)
                    pending_item = QTableWidgetItem(pending_text)
                    pending_item.setForeground(QColor("#e74c3c"))
                    pending_item.setBackground(QColor("#ffebee"))
                    font = QFont()
                    font.setBold(True)
                    pending_item.setFont(font)
                else:
                    pending_item = QTableWidgetItem("None")
                self.table.setItem(row, 2, pending_item)
                
                self.table.setItem(row, 3, QTableWidgetItem(f"${avg_cost:.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(f"${market_price:.2f}"))
                self.table.setItem(row, 5, QTableWidgetItem(f"${value:,.0f}"))
                
                # P&L with color coding
                pnl_item = QTableWidgetItem(f"${pnl:,.0f}")
                if pnl >= 0:
                    pnl_item.setForeground(QColor("#27ae60"))
                else:
                    pnl_item.setForeground(QColor("#e74c3c"))
                self.table.setItem(row, 6, pnl_item)
                
                # Action button - compact
                if pending_orders:
                    close_btn = QPushButton("Selling...")
                    close_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; font-size: 10px; padding: 2px;")
                    close_btn.setEnabled(False)
                else:
                    close_btn = QPushButton("Close")
                    close_btn.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; font-size: 10px; padding: 2px;")
                    close_btn.clicked.connect(lambda checked, s=symbol: self.close_single_position(s))
                
                self.table.setCellWidget(row, 7, close_btn)
                row += 1
            
            # Update account summary
            self.total_value_label.setText(f"Total: ${total_value:,.0f}")
            pnl_text = f"P&L: ${total_pnl:,.0f}"
            if total_pnl >= 0:
                self.total_pnl_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.total_pnl_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.total_pnl_label.setText(pnl_text)
            
            # Update status with position count
            self.update_status(f"Displaying {row} positions in table")
            
        except Exception as e:
            self.update_status(f"Error updating display: {e}")
    
    def manual_refresh(self):
        """Manual refresh of data"""
        self.update_status("Manual refresh requested...")
        self.initial_data_load()
    
    def close_single_position(self, symbol):
        """Close a single position"""
        if symbol not in self.positions_data:
            return
            
        item = self.positions_data[symbol]
        qty = int(item.position)
        
        # Handle both Position and PortfolioItem objects for value calculation
        if hasattr(item, 'marketValue'):
            value = float(item.marketValue)
        else:
            avg_cost = float(item.avgCost) if hasattr(item, 'avgCost') else 0.0
            value = qty * avg_cost
        
        reply = QMessageBox.question(
            self, 'Close Position',
            f'Close {symbol} position?\n\n'
            f'Quantity: {qty} shares\n'
            f'Estimated Value: ${value:,.2f}\n\n'
            f'This will place a MARKET SELL order.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.place_sell_order(symbol, qty)
    
    def close_all_positions(self):
        """Close all positions with proper delays to avoid rate limiting"""
        if not self.positions_data:
            QMessageBox.information(self, "No Positions", "No positions to close")
            return
            
        total_positions = len(self.positions_data)
        reply = QMessageBox.question(
            self, 'Close All Positions',
            f'Close ALL {total_positions} positions?\n\n'
            f'This will place MARKET SELL orders for all positions.\n'
            f'Orders will be submitted with delays to avoid rate limiting.\n'
            f'This action cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            positions_to_close = list(self.positions_data.items())
            self.update_status(f"Starting to close {len(positions_to_close)} positions with rate limiting protection...")
            
            order_count = 0
            for symbol, item in positions_to_close:
                if hasattr(item, 'position') and item.position > 0:
                    order_count += 1
                    self.update_status(f"Submitting order {order_count}/{len(positions_to_close)}: {symbol}")
                    
                    success = self.place_sell_order(symbol, int(item.position))
                    
                    if order_count < len(positions_to_close):
                        self.update_status(f"Waiting 0.5 seconds before next order...")
                        time.sleep(0.5)
            
            self.update_status(f"Completed submitting {order_count} sell orders")
    
    def place_sell_order(self, symbol, quantity):
        """Place a sell order for a position with enhanced error handling"""
        try:
            if not self.ib or not self.ib.isConnected():
                self.update_status("Not connected to IBKR")
                return False
            
            self.update_status(f"Placing sell order: {quantity} shares of {symbol}")
            
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Qualify the contract
            try:
                qualified_contracts = self.ib.qualifyContracts(contract)
                if not qualified_contracts:
                    self.update_status(f"Failed to qualify contract for {symbol}")
                    return False
                
                contract = qualified_contracts[0]
                
            except Exception as e:
                self.update_status(f"Contract qualification failed for {symbol}: {e}")
            
            # Create market sell order
            order = MarketOrder('SELL', quantity)
            order.transmit = True
            order.outsideRth = False
            
            # Place the order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait for order processing
            self.ib.sleep(0.1)
            
            # Check if order was accepted
            if trade and trade.order:
                order_id = trade.order.orderId
                status = trade.orderStatus.status if trade.orderStatus else "Unknown"
                
                self.update_status(f"Sell order submitted for {symbol}: Order ID {order_id}, Status: {status}")
                return True
            else:
                self.update_status(f"Failed to place order for {symbol}")
                return False
            
        except Exception as e:
            self.update_status(f"Error placing sell order for {symbol}: {str(e)}")
            return False
    
    def closeEvent(self, event):
        """Clean shutdown"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        event.accept()

def main():
    """Run the position monitor standalone"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyleSheet("""
        QDialog {
            background-color: #ecf0f1;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
    """)
    
    monitor = ProfessionalPositionMonitor()
    monitor.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
