#!/usr/bin/env python3
"""
Integrated Position Monitor Dialog for Backtest App
Embeds position monitoring directly in the GUI
"""

import asyncio
import json
import datetime as dt
from typing import Dict
from pathlib import Path
import pytz

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                            QTableWidgetItem, QPushButton, QLabel, QTextEdit,
                            QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

NY = pytz.timezone('America/New_York')

class IBKRWorker(QThread):
    """Background worker for IBKR operations"""
    positions_updated = pyqtSignal(dict)  # positions data
    connection_status = pyqtSignal(bool, str)  # connected, message
    position_closed = pyqtSignal(str, str)  # symbol, message
    refresh_requested = pyqtSignal()  # manual refresh request
    
    def __init__(self):
        super().__init__()
        self.ib = None
        self.running = False
        self.config = self.load_config()
        self.force_refresh = False  # Flag for immediate refresh
        
    def load_config(self):
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {"ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 7}
    
    def run(self):
        """Main worker thread"""
        print("DEBUG: IBKRWorker.run() started")
        if not IB_AVAILABLE:
            print("DEBUG: ib-insync not available")
            self.connection_status.emit(False, "ib-insync not available")
            return
            
        print("DEBUG: Setting up async loop")
        self.running = True
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        
        try:
            print("DEBUG: Starting async_main")
            loop.run_until_complete(self.async_main())
        except Exception as e:
            print(f"DEBUG: Exception in run(): {e}")
            self.connection_status.emit(False, f"Error: {e}")
        finally:
            print("DEBUG: Closing event loop")
            loop.close()
    
    async def async_main(self):
        """Async main function"""
        self.ib = IB()
        
        try:
            # Connect to IBKR
            host = self.config.get("ib_host", "127.0.0.1")
            port = int(self.config.get("ib_port", 7497))
            client_id = int(self.config.get("ib_client_id", 7))
            print(f"DEBUG: Connecting to IBKR: {host}:{port} with client ID {client_id}")
            
            await self.ib.connectAsync(
                host, port, clientId=client_id, timeout=10
            )
            
            if self.ib.isConnected():
                self.connection_status.emit(True, "Connected to IBKR")
                
                # Monitor positions
                while self.running and self.ib.isConnected():
                    try:
                        positions = await self.get_positions()
                        self.positions_updated.emit(positions)
                        
                        # Check for manual refresh request
                        if self.force_refresh:
                            print("DEBUG: Force refresh triggered")
                            self.force_refresh = False
                            # Skip sleep to refresh immediately
                            continue
                        
                        # Always sleep to prevent tight loop
                        await asyncio.sleep(10)  # Update every 10 seconds (slower)
                        
                    except Exception as e:
                        print(f"DEBUG: Error in monitoring loop: {e}")
                        await asyncio.sleep(5)  # Sleep on error to prevent rapid retries
            else:
                self.connection_status.emit(False, "Failed to connect")
                
        except Exception as e:
            self.connection_status.emit(False, f"Connection error: {e}")
        finally:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
    
    async def get_positions(self):
        """Get current positions and open orders"""
        print("DEBUG: get_positions() called")
        positions = {}
        try:
            if self.ib and self.ib.isConnected():
                print("DEBUG: IBKR is connected, getting data...")
                # Get portfolio positions
                portfolio_items = self.ib.portfolio()
                for item in portfolio_items:
                    if item.position != 0:
                        symbol = item.contract.symbol
                        positions[symbol] = {
                            'contract': item.contract,
                            'quantity': int(item.position),
                            'avg_cost': float(item.averageCost),
                            'market_price': float(item.marketPrice),
                            'market_value': float(item.marketValue),
                            'unrealized_pnl': float(item.unrealizedPNL),
                            'pending_sell': 0  # Will be updated below
                        }
                
                # Check for pending sell orders
                try:
                    open_orders = self.ib.openOrders()
                    print(f"DEBUG: Found {len(open_orders)} open orders")
                    
                    # Also try getting all orders (not just this client)
                    try:
                        print("DEBUG: Requesting all open orders...")
                        all_orders = self.ib.reqAllOpenOrders()
                        print(f"DEBUG: Found {len(all_orders)} total orders (all clients)")
                        all_order_list = list(open_orders) + list(all_orders)
                    except Exception as e:
                        print(f"DEBUG: Error getting all orders: {e}")
                        all_order_list = list(open_orders)
                    
                    # Remove duplicates
                    unique_orders = {order.order.orderId: order for order in all_order_list}.values()
                    print(f"DEBUG: Processing {len(unique_orders)} unique orders")
                    
                    for order in unique_orders:
                        print(f"DEBUG: Order: {order.contract.symbol} {order.action} {order.totalQuantity} status: {order.orderStatus.status} clientId: {order.order.clientId}")
                        if order.action == 'SELL':
                            symbol = order.contract.symbol
                            if symbol in positions:
                                print(f"DEBUG: Setting pending_sell for {symbol}: {order.totalQuantity}")
                                positions[symbol]['pending_sell'] = int(order.totalQuantity)
                            else:
                                print(f"DEBUG: Order symbol {symbol} not found in positions")
                                
                except Exception as e:
                    print(f"DEBUG: Error checking orders: {e}")
                            
        except Exception as e:
            print(f"Error getting positions: {e}")
        
        return positions
    
    def close_position_sync(self, symbol):
        """Close position using synchronous approach"""
        print(f"DEBUG: close_position_sync called for {symbol}")
        try:
            if not self.ib or not self.ib.isConnected():
                print(f"DEBUG: Not connected - ib={self.ib}, connected={self.ib.isConnected() if self.ib else False}")
                self.position_closed.emit(symbol, "Not connected to IBKR")
                return
            
            print(f"DEBUG: Connected to IBKR, getting portfolio...")
            # Find the position
            portfolio_items = self.ib.portfolio()
            print(f"DEBUG: Found {len(portfolio_items)} portfolio items")
            
            for item in portfolio_items:
                print(f"DEBUG: Portfolio item: {item.contract.symbol}, position: {item.position}")
                if item.contract.symbol == symbol and item.position != 0:
                    # Fix the contract exchange field
                    try:
                        print(f"DEBUG: Using existing portfolio contract for {symbol}")
                        print(f"DEBUG: Contract details: {item.contract}")
                        
                        # Create a copy of the contract and fix the exchange field
                        fixed_contract = Stock(
                            symbol=item.contract.symbol,
                            exchange=item.contract.primaryExchange,  # Use primaryExchange as exchange
                            currency=item.contract.currency
                        )
                        
                        print(f"DEBUG: Fixed contract: {fixed_contract}")
                        print(f"DEBUG: Placing sell order for {abs(int(item.position))} shares")
                        print(f"DEBUG: Using client ID: {self.ib.client.clientId}")
                        
                        # Place market sell order with fixed contract
                        trade = self.ib.placeOrder(fixed_contract, MarketOrder("SELL", abs(int(item.position))))
                        print(f"DEBUG: Trade object created: {trade}")
                        print(f"DEBUG: Order ID: {trade.order.orderId}, Client ID: {trade.order.clientId}")
                        self.position_closed.emit(symbol, f"Order submitted: {abs(int(item.position))} shares")
                        
                        # Don't wait - let it process asynchronously
                        return
                        
                    except Exception as e:
                        print(f"DEBUG: Exception placing order: {e}")
                        self.position_closed.emit(symbol, f"Error placing order: {e}")
                    return
                    
            print(f"DEBUG: Position {symbol} not found in portfolio")
            self.position_closed.emit(symbol, "Position not found")
            
        except Exception as e:
            print(f"DEBUG: Exception in close_position_sync: {e}")
            self.position_closed.emit(symbol, f"Error: {e}")
    
    def close_all_positions_sync(self):
        """Close all positions using synchronous approach"""
        try:
            if not self.ib or not self.ib.isConnected():
                self.position_closed.emit("ALL", "Not connected to IBKR")
                return
            
            portfolio_items = self.ib.portfolio()
            positions_closed = 0
            
            for item in portfolio_items:
                if item.position != 0:
                    symbol = item.contract.symbol
                    try:
                        # Fix the contract exchange field
                        fixed_contract = Stock(
                            symbol=item.contract.symbol,
                            exchange=item.contract.primaryExchange,  # Use primaryExchange as exchange
                            currency=item.contract.currency
                        )
                        
                        trade = self.ib.placeOrder(fixed_contract, MarketOrder("SELL", abs(int(item.position))))
                        positions_closed += 1
                        self.position_closed.emit(symbol, f"Order submitted for {abs(int(item.position))} shares")
                        
                    except Exception as e:
                        self.position_closed.emit(symbol, f"Error closing {symbol}: {e}")
                        
            self.position_closed.emit("ALL", f"Submitted close orders for {positions_closed} positions")
            
        except Exception as e:
            self.position_closed.emit("ALL", f"Error closing all: {e}")
    
    async def close_position(self, symbol, contract, quantity):
        """Close a specific position"""
        try:
            if self.ib and self.ib.isConnected():
                # Cancel existing orders for this symbol
                orders = self.ib.openOrders()
                for order in orders:
                    if order.contract.symbol == symbol:
                        self.ib.cancelOrder(order)
                        await asyncio.sleep(0.1)
                
                # Place market sell order
                trade = self.ib.placeOrder(contract, MarketOrder("SELL", abs(quantity)))
                await trade.filledEvent
                
                fill_price = float(trade.orderStatus.avgFillPrice or 0.0)
                self.position_closed.emit(symbol, f"Closed {quantity} shares @ ${fill_price:.2f}")
                
        except Exception as e:
            self.position_closed.emit(symbol, f"Error closing: {e}")
    
    def stop(self):
        """Stop the worker"""
        self.running = False
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()

class PositionMonitorDialog(QDialog):
    """Integrated Position Monitor Dialog"""
    
    def __init__(self, parent=None):
        print("DEBUG: PositionMonitorDialog.__init__ called")
        super().__init__(parent)
        self.setWindowTitle("Position Monitor & Control")
        self.setGeometry(100, 100, 800, 600)
        self.positions = {}
        self.worker = None
        
        print("DEBUG: About to call init_ui")
        self.init_ui()
        print("DEBUG: About to call start_monitoring")
        self.start_monitoring()
        print("DEBUG: PositionMonitorDialog initialization complete")
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        self.status_label = QLabel("Connecting to IBKR...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_positions)
        
        self.close_all_btn = QPushButton("Close All Positions")
        self.close_all_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.close_all_btn.clicked.connect(self.close_all_positions)
        
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        header_layout.addWidget(self.close_all_btn)
        
        layout.addLayout(header_layout)
        
        # Positions table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Quantity", "Pending Sell", "Avg Cost", "Market Price", 
            "Market Value", "Unrealized P&L", "Action"
        ])
        
        # Make table more readable
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Summary
        self.summary_label = QLabel("Portfolio Summary: No positions")
        self.summary_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 10px;")
        layout.addWidget(self.summary_label)
        
        # Log output
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Close button
        close_btn = QPushButton("Close Monitor")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
    def start_monitoring(self):
        """Start IBKR monitoring"""
        print("DEBUG: start_monitoring called")
        if not IB_AVAILABLE:
            self.status_label.setText("❌ ib-insync not available")
            self.log_text.append("Error: ib-insync not installed")
            return
            
        print("DEBUG: Creating IBKRWorker")
        self.worker = IBKRWorker()
        self.worker.connection_status.connect(self.on_connection_status)
        self.worker.positions_updated.connect(self.update_positions)
        self.worker.position_closed.connect(self.on_position_closed)
        print("DEBUG: Starting worker thread")
        self.worker.start()
        print("DEBUG: Worker started")
        
    def on_connection_status(self, connected: bool, message: str):
        """Handle connection status updates"""
        if connected:
            self.status_label.setText("✅ Connected to IBKR")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText(f"❌ {message}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        self.log_text.append(f"{dt.datetime.now().strftime('%H:%M:%S')} - {message}")
    
    def update_positions(self, positions: Dict):
        """Update positions table"""
        self.positions = positions
        
        # Clear and repopulate table
        self.table.setRowCount(len(positions))
        
        total_value = 0
        total_pnl = 0
        
        for row, (symbol, pos) in enumerate(positions.items()):
            # Symbol
            self.table.setItem(row, 0, QTableWidgetItem(symbol))
            
            # Quantity
            qty_item = QTableWidgetItem(str(pos['quantity']))
            self.table.setItem(row, 1, qty_item)
            
            # Pending Sell
            pending_sell = pos.get('pending_sell', 0)
            if pending_sell > 0:
                pending_item = QTableWidgetItem(f"{pending_sell} (PENDING)")
                pending_item.setForeground(Qt.GlobalColor.red)
                pending_item.setStyleSheet("font-weight: bold;")
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
            
            # Action button - disable if already has pending sell
            if pending_sell > 0:
                close_btn = QPushButton("SELLING...")
                close_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
                close_btn.setEnabled(False)
            else:
                close_btn = QPushButton("Close")
                close_btn.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold;")
                close_btn.clicked.connect(lambda checked, s=symbol: self.close_single_position(s))
            self.table.setCellWidget(row, 7, close_btn)
        
        # Update summary
        if positions:
            pnl_pct = (total_pnl / (total_value - total_pnl)) * 100 if (total_value - total_pnl) > 0 else 0
            self.summary_label.setText(
                f"Portfolio: {len(positions)} positions | "
                f"Value: ${total_value:.2f} | "
                f"P&L: ${total_pnl:.2f} ({pnl_pct:+.1f}%)"
            )
        else:
            self.summary_label.setText("Portfolio: No active positions")
    
    def close_single_position(self, symbol: str):
        """Close a single position"""
        if symbol not in self.positions:
            return
            
        pos = self.positions[symbol]
        reply = QMessageBox.question(
            self, 'Close Position',
            f'Close {symbol} position?\n'
            f'Quantity: {pos["quantity"]}\n'
            f'Current Value: ${pos["market_value"]:.2f}\n'
            f'Unrealized P&L: ${pos["unrealized_pnl"]:.2f}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_text.append(f"Closing {symbol} position...")
            if self.worker and self.worker.isRunning():
                # Use QTimer to make call non-blocking
                QTimer.singleShot(100, lambda: self.worker.close_position_sync(symbol))
            else:
                self.log_text.append(f"❌ Worker not running - cannot close {symbol}")
    
    def close_all_positions(self):
        """Close all positions"""
        if not self.positions:
            QMessageBox.information(self, "No Positions", "No positions to close")
            return
            
        reply = QMessageBox.question(
            self, 'Close All Positions',
            f'Close ALL {len(self.positions)} positions?\n'
            f'This action cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_text.append("Closing all positions...")
            if self.worker and self.worker.isRunning():
                # Use QTimer to make call non-blocking
                QTimer.singleShot(100, lambda: self.worker.close_all_positions_sync())
            else:
                self.log_text.append("❌ Worker not running - cannot close positions")
    
    def refresh_positions(self):
        """Refresh positions manually"""
        self.log_text.append("Refreshing positions...")
        print("DEBUG: Manual refresh requested")
        # Force immediate update if worker is running
        if self.worker and self.worker.isRunning():
            print("DEBUG: Worker is running, setting force_refresh flag")
            self.worker.force_refresh = True
        else:
            print("DEBUG: Worker not running")
    
    def on_position_closed(self, symbol: str, message: str):
        """Handle position closed event"""
        self.log_text.append(f"{symbol}: {message}")
    
    def closeEvent(self, event):
        """Handle dialog close"""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        event.accept()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    dialog = PositionMonitorDialog()
    dialog.show()
    sys.exit(app.exec())