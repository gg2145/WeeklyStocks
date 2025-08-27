#!/usr/bin/env python3
"""
Debug version of monitor to see what's really happening
"""

import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

try:
    from ib_insync import IB, Stock, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

from pending_sales import pending_tracker

class DebugMonitor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DEBUG Position Monitor")
        self.setGeometry(200, 200, 1000, 600)
        
        self.ib = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Connect button
        self.connect_btn = QPushButton("Connect & Test")
        self.connect_btn.clicked.connect(self.test_refresh)
        layout.addWidget(self.connect_btn)
        
        # Simple table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Symbol", "Position", "Pending Status", "Status Display"])
        layout.addWidget(self.table)
        
        # Log
        self.log = QTextEdit()
        self.log.setMaximumHeight(200)
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        
    def log_msg(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        
    def test_refresh(self):
        try:
            # Test pending sales detection
            self.log_msg("=== TESTING PENDING SALES DETECTION ===")
            
            pending_sales = pending_tracker.get_all_pending_sales()
            self.log_msg(f"Found {len(pending_sales)} pending sales")
            
            test_symbols = ['CNC', 'ENPH', 'INTC', 'SIRI', 'VTRS']
            
            # Create fake positions for testing
            fake_positions = {
                'CNC': {'qty': 1028, 'value': 50000, 'pnl': 1000},
                'ENPH': {'qty': 279, 'value': 25000, 'pnl': -500},
                'INTC': {'qty': 422, 'value': 15000, 'pnl': 200},
                'SIRI': {'qty': 874, 'value': 5000, 'pnl': -100},
                'VTRS': {'qty': 1876, 'value': 30000, 'pnl': 800}
            }
            
            self.table.setRowCount(len(test_symbols))
            
            for row, symbol in enumerate(test_symbols):
                self.log_msg(f"Processing {symbol}...")
                
                # Test the exact same logic as monitor
                has_pending_sells = pending_tracker.is_pending_sale(symbol)
                has_pending_buys = pending_tracker.is_pending_buy(symbol)
                
                self.log_msg(f"  {symbol}: pending_sells={has_pending_sells}, pending_buys={has_pending_buys}")
                
                # Set table values
                self.table.setItem(row, 0, QTableWidgetItem(symbol))
                
                pos = fake_positions.get(symbol)
                if pos:
                    self.table.setItem(row, 1, QTableWidgetItem(str(pos['qty'])))
                
                # Show the detected status
                if has_pending_sells:
                    self.table.setItem(row, 2, QTableWidgetItem("DETECTED: PENDING SALE"))
                elif has_pending_buys:
                    self.table.setItem(row, 2, QTableWidgetItem("DETECTED: PENDING BUY"))  
                else:
                    self.table.setItem(row, 2, QTableWidgetItem("DETECTED: NO PENDING"))
                    
                # Try to set the status like the real monitor
                if has_pending_sells:
                    status_item = QTableWidgetItem("PENDING SALE")
                    status_item.setBackground(QColor("#dc3545"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                    self.log_msg(f"  Setting PENDING SALE status for {symbol}")
                elif has_pending_buys:
                    status_item = QTableWidgetItem("PENDING BUY")
                    status_item.setBackground(QColor("#007bff"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                    self.log_msg(f"  Setting PENDING BUY status for {symbol}")
                else:
                    status_item = QTableWidgetItem("Open")
                    status_item.setForeground(QColor("green"))
                    self.log_msg(f"  Setting Open status for {symbol}")
                    
                self.table.setItem(row, 3, status_item)
                
            self.log_msg("=== TESTING COMPLETE ===")
            self.log_msg("Check if Status Display column shows PENDING SALE for your stocks!")
                
        except Exception as e:
            self.log_msg(f"ERROR: {e}")
            import traceback
            self.log_msg(traceback.format_exc())

if __name__ == "__main__":
    app = QApplication([])
    monitor = DebugMonitor()
    monitor.show()
    app.exec()