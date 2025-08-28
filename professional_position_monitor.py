#!/usr/bin/env python3
"""
Professional Position Monitor - Event-Driven Architecture
Based on proven ib-insync patterns and best practices
"""

import json
import sys
import time
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                            QTableWidget, QTableWidgetItem, QPushButton, QLabel, 
                            QTextEdit, QMessageBox, QHeaderView, QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

try:
    from ib_insync import IB, Stock, MarketOrder, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

class ProfessionalPositionMonitor(QDialog):
    """Professional position monitor using proven ib-insync event patterns"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Professional Position Monitor")
        
        # Set window flags to make it more stable
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        
        # Use proven working dimensions from working_position_monitor.py
        self.setMinimumSize(900, 600)
        self.resize(1000, 600)
        
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
        
        # Header
        header = QLabel("Professional Position Monitor")
        header.setStyleSheet("font-size: 20px; font-weight: bold; margin: 15px; color: #2c3e50;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection and Account section - combined for better space usage
        conn_group = QGroupBox("IBKR Connection & Account")
        conn_layout = QHBoxLayout(conn_group)
        
        # Left side - Connection status
        status_section = QVBoxLayout()
        self.status_label = QLabel("Checking connection...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #f39c12;")
        status_section.addWidget(self.status_label)
        
        # Connection buttons
        button_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; 
                color: white; 
                font-weight: bold; 
                padding: 12px 25px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.connect_btn.clicked.connect(self.connect_to_ibkr)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; 
                color: white; 
                font-weight: bold; 
                padding: 12px 25px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.disconnect_btn.clicked.connect(self.disconnect_from_ibkr)
        self.disconnect_btn.setEnabled(False)
        
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.disconnect_btn)
        status_section.addLayout(button_layout)
        
        # Right side - Account info (moved up here)
        account_section = QFormLayout()
        self.account_label = QLabel("--")
        self.total_value_label = QLabel("--")
        self.total_pnl_label = QLabel("--")
        
        account_section.addRow("Account:", self.account_label)
        account_section.addRow("Total Value:", self.total_value_label)
        account_section.addRow("Unrealized P&L:", self.total_pnl_label)
        
        # Add both sections to main layout
        conn_layout.addLayout(status_section)
        conn_layout.addStretch()
        conn_layout.addLayout(account_section)
        layout.addWidget(conn_group)
        
        # Positions table - MUCH BIGGER
        positions_group = QGroupBox("Positions & Pending Orders")
        positions_layout = QVBoxLayout(positions_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Position", "Pending Sell Orders", "Avg Cost", 
            "Market Price", "Market Value", "Unrealized P&L", "Action"
        ])
        
        # Set standard row height for more positions
        self.table.verticalHeader().setDefaultSectionSize(35)  # 35px per row - standard table height
        
        # Style the table with fixed Action column width
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Set Action column to fixed width so it's always readable
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)  # Action column (index 7)
        self.table.setColumnWidth(7, 120)  # Fixed width for Action column
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                alternate-background-color: #f8f9fa;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 10px;
                font-weight: bold;
                border: none;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 8px;
            }
        """)
        positions_layout.addWidget(self.table)
        layout.addWidget(positions_group)
        
        # Action buttons - now includes Close Monitor button
        action_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Manual Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; 
                color: white; 
                font-weight: bold; 
                padding: 10px 15px;
                border-radius: 5px;
                border: none;
            }
        """)
        self.refresh_btn.clicked.connect(self.manual_refresh)
        self.refresh_btn.setEnabled(False)
        
        # Close Monitor button moved here to save space
        self.close_monitor_btn = QPushButton("Close Monitor")
        self.close_monitor_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; 
                color: white; 
                font-weight: bold; 
                padding: 10px 15px;
                border-radius: 5px;
                border: none;
            }
        """)
        self.close_monitor_btn.clicked.connect(self.close)
        
        self.close_all_btn = QPushButton("Close All Positions")
        self.close_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12; 
                color: white; 
                font-weight: bold; 
                padding: 10px 15px;
                border-radius: 5px;
                border: none;
            }
        """)
        self.close_all_btn.clicked.connect(self.close_all_positions)
        self.close_all_btn.setEnabled(False)
        
        action_layout.addWidget(self.refresh_btn)
        action_layout.addWidget(self.close_monitor_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.close_all_btn)
        layout.addLayout(action_layout)
        
        # Log section - MINIMAL SIZE without GroupBox
        self.log_text = QTextEdit()
        self.log_text.setMinimumHeight(30)  # Just enough for one line of text
        self.log_text.setMaximumHeight(30)  # Force it to stay small
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #34495e;
                padding: 2px;
                margin: 0px;
            }
        """)
        layout.addWidget(self.log_text)
        
    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}
    
    def check_existing_connection(self):
        """Check if IBKR is already connected from main menu"""
        try:
            # Try to create a test connection to see if IBKR is available
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
                    self.status_label.setText("IBKR available - click Connect")
                    self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #27ae60;")
                    self.log_message("IBKR detected and available", "SUCCESS")
                else:
                    self.status_label.setText("IBKR not running")
                    self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")
            except:
                self.status_label.setText("IBKR not running")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")
        except:
            self.status_label.setText("Connection check failed")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #f39c12;")
    
    def log_message(self, message, level="INFO"):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#3498db", "SUCCESS": "#27ae60", "ERROR": "#e74c3c", "WARNING": "#f39c12"}
        color = colors.get(level, "#ecf0f1")
        
        self.log_text.append(f'<span style="color: {color};">[{timestamp}] {message}</span>')
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def connect_to_ibkr(self):
        if not IB_AVAILABLE:
            self.log_message("ib-insync not available. Install with: pip install ib-insync", "ERROR")
            return
        
        try:
            config = self.load_config()
            host = config.get("ib_host", "127.0.0.1")
            port = int(config.get("ib_port", 7497))
            client_id = int(config.get("ib_client_id", 7))
            
            self.log_message(f"Connecting to {host}:{port} with client ID {client_id}...")
            
            # Create IB instance
            self.ib = IB()
            
            # Set up event handlers (PROVEN PATTERN)
            self.ib.positionEvent += self.on_position_update
            self.ib.updatePortfolioEvent += self.on_portfolio_update
            self.ib.orderStatusEvent += self.on_order_status_update
            self.ib.errorEvent += self.on_error
            
            # Connect synchronously (proven to work)
            self.ib.connect(host, port, clientId=client_id, timeout=10)
            
            if self.ib.isConnected():
                self.status_label.setText("✅ Connected")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
                
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
                self.close_all_btn.setEnabled(True)
                
                self.log_message("Connected to IBKR successfully", "SUCCESS")
                
                # Get initial data
                self.initial_data_load()
            else:
                self.log_message("Failed to connect to IBKR", "ERROR")
                
        except Exception as e:
            self.log_message(f"Connection error: {e}", "ERROR")
    
    def disconnect_from_ibkr(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
        
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.close_all_btn.setEnabled(False)
        
        self.log_message("Disconnected from IBKR", "INFO")
    
    def initial_data_load(self):
        """Load initial positions and orders"""
        try:
            # Get account info
            accounts = self.ib.managedAccounts()
            if accounts:
                self.account_label.setText(accounts[0])
            
            # Get positions
            positions = self.ib.positions()
            for pos in positions:
                self.positions_data[pos.contract.symbol] = pos
            
            # Get portfolio
            portfolio = self.ib.portfolio()
            for item in portfolio:
                if item.position != 0:
                    self.positions_data[item.contract.symbol] = item
            
            # Get open orders - try multiple methods to find your pending sells
            orders = self.ib.openOrders()
            self.log_message(f"Found {len(orders)} open orders via openOrders()")
            for order in orders:
                self.orders_data[order.order.orderId] = order
                self.log_message(f"Order: {order.contract.symbol} {order.action} {order.totalQuantity} - {order.orderStatus.status}")
                
            # Try reqAllOpenOrders to get orders from all clients
            try:
                all_orders = self.ib.reqAllOpenOrders()
                self.log_message(f"Found {len(all_orders)} orders via reqAllOpenOrders()")
                for order in all_orders:
                    if order.order.orderId not in self.orders_data:
                        self.orders_data[order.order.orderId] = order
                        self.log_message(f"Additional order: {order.contract.symbol} {order.action} {order.totalQuantity} - {order.orderStatus.status}")
            except Exception as e:
                self.log_message(f"reqAllOpenOrders failed: {e}", "WARNING")
                
            # Get trades (including pending) - this often finds orders that openOrders misses
            trades = self.ib.trades()
            pending_count = 0
            for trade in trades:
                if trade.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit']:
                    if trade.order.orderId not in self.orders_data:
                        self.orders_data[trade.order.orderId] = trade
                        pending_count += 1
                        self.log_message(f"Pending trade: {trade.contract.symbol} {trade.order.action} {trade.order.totalQuantity} - {trade.orderStatus.status}")
            
            if pending_count > 0:
                self.log_message(f"Found {pending_count} additional pending trades", "SUCCESS")
            
            self.update_display()
            self.log_message(f"Loaded {len(self.positions_data)} positions, {len(self.orders_data)} orders", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"Error loading initial data: {e}", "ERROR")
    
    # EVENT HANDLERS (PROVEN PATTERN)
    def on_position_update(self, position):
        """Handle position updates in real-time"""
        self.positions_data[position.contract.symbol] = position
        self.update_display()
        self.log_message(f"Position updated: {position.contract.symbol}")
    
    def on_portfolio_update(self, item):
        """Handle portfolio updates in real-time"""
        if item.position != 0:
            self.positions_data[item.contract.symbol] = item
        else:
            # Position was closed
            if item.contract.symbol in self.positions_data:
                del self.positions_data[item.contract.symbol]
        
        self.update_display()
        self.log_message(f"Portfolio updated: {item.contract.symbol}")
    
    def on_order_status_update(self, trade):
        """Handle order status changes in real-time"""
        self.orders_data[trade.order.orderId] = trade
        self.update_display()
        
        status = trade.orderStatus.status
        symbol = trade.contract.symbol
        action = trade.order.action
        qty = trade.order.totalQuantity
        
        self.log_message(f"Order update: {action} {qty} {symbol} - {status}")
        
        # Remove completed orders from tracking
        if status in ['Filled', 'Cancelled', 'Inactive']:
            if trade.order.orderId in self.orders_data:
                del self.orders_data[trade.order.orderId]
    
    def on_error(self, reqId, errorCode, errorString, contract):
        """Handle errors from IBKR"""
        self.log_message(f"IBKR Error {errorCode}: {errorString}", "ERROR")
    
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
                            self.log_message(f"Could not get market data for {symbol}: {e}", "WARNING")
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
                        pending_orders.append(f"SELLING {order_qty} shares ({status})")
                
                # Populate table cells
                self.table.setItem(row, 0, QTableWidgetItem(symbol))
                self.table.setItem(row, 1, QTableWidgetItem(str(qty)))
                
                # Pending orders column - MUCH MORE VISIBLE
                if pending_orders:
                    pending_text = "\n".join(pending_orders)
                    pending_item = QTableWidgetItem(pending_text)
                    pending_item.setForeground(QColor("#e74c3c"))
                    pending_item.setBackground(QColor("#ffebee"))  # Light red background
                    font = QFont()
                    font.setBold(True)
                    pending_item.setFont(font)
                else:
                    pending_item = QTableWidgetItem("No pending orders")
                self.table.setItem(row, 2, pending_item)
                
                self.table.setItem(row, 3, QTableWidgetItem(f"${avg_cost:.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(f"${market_price:.2f}"))
                self.table.setItem(row, 5, QTableWidgetItem(f"${value:,.2f}"))
                
                # P&L with color coding
                pnl_item = QTableWidgetItem(f"${pnl:,.2f}")
                if pnl >= 0:
                    pnl_item.setForeground(QColor("#27ae60"))
                else:
                    pnl_item.setForeground(QColor("#e74c3c"))
                self.table.setItem(row, 6, pnl_item)
                
                # Action button
                if pending_orders:
                    close_btn = QPushButton("Selling...")
                    close_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
                    close_btn.setEnabled(False)
                else:
                    close_btn = QPushButton("Close")
                    close_btn.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
                    close_btn.clicked.connect(lambda checked, s=symbol: self.close_single_position(s))
                
                self.table.setCellWidget(row, 7, close_btn)
                row += 1
            
            # Update account summary
            self.total_value_label.setText(f"${total_value:,.2f}")
            pnl_text = f"${total_pnl:,.2f}"
            if total_pnl >= 0:
                self.total_pnl_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.total_pnl_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.total_pnl_label.setText(pnl_text)
            
        except Exception as e:
            self.log_message(f"Error updating display: {e}", "ERROR")
    
    def manual_refresh(self):
        """Manual refresh of data"""
        self.log_message("Manual refresh requested...")
        self.initial_data_load()
    
    def close_single_position(self, symbol):
        """Close a single position"""
        if symbol not in self.positions_data:
            return
            
        item = self.positions_data[symbol]
        qty = int(item.position)
        
        # Handle both Position and PortfolioItem objects for value calculation
        if hasattr(item, 'marketValue'):
            # This is a PortfolioItem
            value = float(item.marketValue)
        else:
            # This is a Position object - estimate value
            avg_cost = float(item.avgCost) if hasattr(item, 'avgCost') else 0.0
            value = qty * avg_cost  # Rough estimate
        
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
            # Create a snapshot of positions to avoid dictionary modification during iteration
            positions_to_close = list(self.positions_data.items())
            self.log_message(f"Starting to close {len(positions_to_close)} positions with rate limiting protection...", "INFO")
            
            order_count = 0
            for symbol, item in positions_to_close:
                if hasattr(item, 'position') and item.position > 0:
                    order_count += 1
                    self.log_message(f"Submitting order {order_count}/{len(positions_to_close)}: {symbol}", "INFO")
                    
                    success = self.place_sell_order(symbol, int(item.position))
                    
                    # Add delay between orders to avoid rate limiting (IBKR allows ~50 orders per second)
                    if order_count < len(positions_to_close):  # Don't delay after the last order
                        self.log_message(f"Waiting 0.5 seconds before next order to avoid rate limiting...", "INFO")
                        time.sleep(0.5)  # 500ms delay between orders
            
            self.log_message(f"Completed submitting {order_count} sell orders", "SUCCESS")
    
    def place_sell_order(self, symbol, quantity):
        """Place a sell order for a position with enhanced error handling"""
        try:
            if not self.ib or not self.ib.isConnected():
                self.log_message("Not connected to IBKR", "ERROR")
                return False
            
            self.log_message(f"Attempting to place sell order: {quantity} shares of {symbol}", "INFO")
            
            # Create contract with more specific details
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Qualify the contract to ensure it's valid
            try:
                qualified_contracts = self.ib.qualifyContracts(contract)
                if not qualified_contracts:
                    self.log_message(f"Failed to qualify contract for {symbol}", "ERROR")
                    return False
                
                contract = qualified_contracts[0]
                self.log_message(f"Contract qualified for {symbol}: {contract.primaryExchange}", "INFO")
                
            except Exception as e:
                self.log_message(f"Contract qualification failed for {symbol}: {e}", "WARNING")
                # Continue with original contract - sometimes this still works
            
            # Create market sell order
            order = MarketOrder('SELL', quantity)
            
            # Add order transmission settings to improve reliability
            order.transmit = True
            order.outsideRth = False  # Only during regular trading hours
            
            # Place the order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait a moment for order to be processed
            self.ib.sleep(0.1)
            
            # Check if order was accepted
            if trade and trade.order:
                order_id = trade.order.orderId
                status = trade.orderStatus.status if trade.orderStatus else "Unknown"
                
                self.log_message(f"Sell order submitted for {symbol}: Order ID {order_id}, Status: {status}", "SUCCESS")
                
                # Additional validation - check if order appears in open orders
                try:
                    open_orders = self.ib.openOrders()
                    order_found = any(o.order.orderId == order_id for o in open_orders)
                    if order_found:
                        self.log_message(f"Order {order_id} confirmed in open orders list", "SUCCESS")
                    else:
                        self.log_message(f"Warning: Order {order_id} not found in open orders list", "WARNING")
                except Exception as e:
                    self.log_message(f"Could not verify order in open orders: {e}", "WARNING")
                
                return True
            else:
                self.log_message(f"Failed to place order for {symbol} - no trade object returned", "ERROR")
                return False
            
        except Exception as e:
            self.log_message(f"Error placing sell order for {symbol}: {str(e)}", "ERROR")
            
            # Try to get more specific error information
            if "Invalid contract" in str(e):
                self.log_message(f"Contract issue for {symbol} - may need manual intervention", "ERROR")
            elif "rate limit" in str(e).lower():
                self.log_message(f"Rate limit hit for {symbol} - will retry with longer delay", "WARNING")
            elif "not connected" in str(e).lower():
                self.log_message(f"Connection lost while placing order for {symbol}", "ERROR")
            
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
