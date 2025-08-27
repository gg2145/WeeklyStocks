#!/usr/bin/env python3
"""
Integrated IBKR Setup Dialog for Backtest App
"""

import json
import asyncio
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QLineEdit, QSpinBox, QPushButton, QLabel, QTextEdit,
                            QMessageBox, QGroupBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

try:
    from ib_insync import IB, Stock
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

class ConnectionTester(QThread):
    """Background thread for testing IBKR connection"""
    test_completed = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, host, port, client_id):
        super().__init__()
        self.host = host
        self.port = port
        self.client_id = client_id
    
    def run(self):
        if not IB_AVAILABLE:
            self.test_completed.emit(False, "ib-insync not available")
            return
            
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        
        try:
            result = loop.run_until_complete(self.test_connection())
            self.test_completed.emit(result[0], result[1])
        except Exception as e:
            self.test_completed.emit(False, f"Test failed: {e}")
        finally:
            loop.close()
    
    async def test_connection(self):
        ib = IB()
        try:
            await ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=10)
            
            if ib.isConnected():
                # Test basic functionality
                spy = Stock("SPY", "ARCA", "USD")
                ib.qualifyContracts(spy)
                
                # Get account info
                account_summary = ib.accountSummary()
                account_info = f"Account access confirmed ({len(account_summary)} items)"
                
                ib.disconnect()
                return True, f"Connection successful! {account_info}"
            else:
                return False, "Failed to establish connection"
                
        except Exception as e:
            try:
                ib.disconnect()
            except:
                pass
            return False, f"Connection error: {e}"

class IBKRSetupDialog(QDialog):
    """Integrated IBKR Setup Dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IBKR Connection Setup")
        self.setGeometry(150, 150, 600, 500)
        self.config = self.load_config()
        
        self.init_ui()
        
    def load_config(self):
        """Load current configuration"""
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except:
            return {
                "ib_host": "127.0.0.1",
                "ib_port": 7497,
                "ib_client_id": 7,
                "capital_per_trade": 10000,
                "max_positions": 10
            }
    
    def save_config(self):
        """Save configuration"""
        try:
            with open("config.json", 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save config: {e}")
            return False
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("IBKR Connection Setup & Testing")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Connection settings group
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QFormLayout(conn_group)
        
        self.host_input = QLineEdit(self.config.get("ib_host", "127.0.0.1"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1000, 9999)
        self.port_input.setValue(int(self.config.get("ib_port", 7497)))
        
        self.client_id_input = QSpinBox()
        self.client_id_input.setRange(1, 999)
        self.client_id_input.setValue(int(self.config.get("ib_client_id", 7)))
        
        conn_layout.addRow("Host:", self.host_input)
        conn_layout.addRow("Port (7497=Paper, 7496=Live):", self.port_input)
        conn_layout.addRow("Client ID:", self.client_id_input)
        
        layout.addWidget(conn_group)
        
        # Trading settings group
        trading_group = QGroupBox("Trading Settings")
        trading_layout = QFormLayout(trading_group)
        
        self.capital_input = QSpinBox()
        self.capital_input.setRange(1000, 100000)
        self.capital_input.setSuffix(" USD")
        self.capital_input.setValue(int(self.config.get("capital_per_trade", 10000)))
        
        self.max_pos_input = QSpinBox()
        self.max_pos_input.setRange(1, 50)
        self.max_pos_input.setValue(int(self.config.get("max_positions", 10)))
        
        trading_layout.addRow("Capital per Trade:", self.capital_input)
        trading_layout.addRow("Max Positions:", self.max_pos_input)
        
        layout.addWidget(trading_group)
        
        # Test connection section
        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout(test_group)
        
        test_btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 10px;")
        self.test_btn.clicked.connect(self.test_connection)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        test_btn_layout.addWidget(self.test_btn)
        test_btn_layout.addStretch()
        
        test_layout.addLayout(test_btn_layout)
        test_layout.addWidget(self.progress_bar)
        
        layout.addWidget(test_group)
        
        # Results area
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(150)
        self.results_text.setReadOnly(True)
        self.results_text.setPlainText("""IBKR Setup Instructions:

1. Open IBKR Trader Workstation (TWS) or Gateway
2. Go to File → Global Configuration → API → Settings
3. Enable "Enable ActiveX and Socket Clients"
4. Set Socket port to: 7497 (Paper) or 7496 (Live)
5. Add IP address: 127.0.0.1
6. Uncheck "Read-Only API"
7. Click OK and restart TWS/Gateway
8. Click "Test Connection" above""")
        
        layout.addWidget(self.results_text)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Configuration")
        save_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.save_configuration)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def test_connection(self):
        """Test IBKR connection"""
        if not IB_AVAILABLE:
            QMessageBox.warning(self, "Missing Dependency", 
                              "ib-insync not available.\nRun: pip install ib-insync")
            return
        
        host = self.host_input.text().strip()
        port = self.port_input.value()
        client_id = self.client_id_input.value()
        
        if not host:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid host")
            return
        
        self.test_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.results_text.append(f"\nTesting connection to {host}:{port} (Client ID: {client_id})...")
        
        self.tester = ConnectionTester(host, port, client_id)
        self.tester.test_completed.connect(self.on_test_completed)
        self.tester.start()
    
    def on_test_completed(self, success: bool, message: str):
        """Handle connection test completion"""
        self.test_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.results_text.append(f"✅ {message}")
            self.results_text.setStyleSheet("background-color: #d4edda;")
            QMessageBox.information(self, "Connection Successful", message)
        else:
            self.results_text.append(f"❌ {message}")
            self.results_text.setStyleSheet("background-color: #f8d7da;")
            
            # Show troubleshooting tips
            self.results_text.append("\nTroubleshooting:")
            self.results_text.append("• Make sure TWS/Gateway is running")
            self.results_text.append("• Check API settings are enabled")
            self.results_text.append("• Verify port number (7497 for paper, 7496 for live)")
            self.results_text.append("• Try different client ID if connection refused")
    
    def save_configuration(self):
        """Save current configuration"""
        # Update config with current values
        self.config.update({
            "ib_host": self.host_input.text().strip(),
            "ib_port": self.port_input.value(),
            "ib_client_id": self.client_id_input.value(),
            "capital_per_trade": self.capital_input.value(),
            "max_positions": self.max_pos_input.value()
        })
        
        if self.save_config():
            QMessageBox.information(self, "Configuration Saved", 
                                  "Configuration saved successfully!")
            self.accept()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    dialog = IBKRSetupDialog()
    dialog.show()
    sys.exit(app.exec())