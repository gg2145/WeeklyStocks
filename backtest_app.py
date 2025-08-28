#!/usr/bin/env python3
"""
Professional Backtest Application
Modern PyQt6-based backtesting interface for Weekly ER Strategy

Inspired by QuantConnect and Backtesting.py best practices
"""

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                            QHBoxLayout, QWidget, QLabel, QPushButton, QLineEdit,
                            QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit,
                            QProgressBar, QComboBox, QGroupBox, QFormLayout,
                            QSlider, QFrame, QSplitter, QDialog, QMessageBox)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor

# Import matplotlib for charts
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import pandas as pd

# Import our clean backtest engine
from backtest_core import BacktestEngine, BacktestConfig, BacktestResults

class ChartWidget(FigureCanvas):
    """Custom chart widget for displaying backtest results"""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.figure)
        self.setParent(parent)
        
        # Set up the plot style
        self.figure.patch.set_facecolor('white')
        
    def plot_equity_curve(self, results: BacktestResults):
        """Plot the equity curve from backtest results"""
        self.figure.clear()
        
        if results.equity_curve.empty:
            # Show empty chart message
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No data to display', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=16, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            self.draw()
            return
        
        # Create subplots
        ax1 = self.figure.add_subplot(211)  # Equity curve
        ax2 = self.figure.add_subplot(212)  # Drawdown
        
        # Convert dates
        equity_df = results.equity_curve.copy()
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        
        # Plot equity curve
        ax1.plot(equity_df['date'], equity_df['equity'], 'b-', linewidth=2, label='Portfolio Value')
        ax1.set_title('Portfolio Performance', fontweight='bold', fontsize=14)
        ax1.set_ylabel('Portfolio Value ($)', fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Format y-axis as currency
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Plot drawdown
        if 'drawdown' in equity_df.columns:
            ax2.fill_between(equity_df['date'], equity_df['drawdown'], 0, 
                           color='red', alpha=0.3, label='Drawdown')
            ax2.plot(equity_df['date'], equity_df['drawdown'], 'r-', linewidth=1)
        else:
            # Calculate drawdown if not present
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
            ax2.fill_between(equity_df['date'], equity_df['drawdown'], 0, 
                           color='red', alpha=0.3, label='Drawdown')
            ax2.plot(equity_df['date'], equity_df['drawdown'], 'r-', linewidth=1)
        
        ax2.set_title('Drawdown', fontweight='bold', fontsize=14)
        ax2.set_xlabel('Date', fontweight='bold')
        ax2.set_ylabel('Drawdown (%)', fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Format dates on x-axis
        for ax in [ax1, ax2]:
            ax.tick_params(axis='x', rotation=45)
            if len(equity_df) > 20:
                ax.xaxis.set_major_locator(mdates.MonthLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            else:
                ax.xaxis.set_major_locator(mdates.WeekdayLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        
        # Adjust layout
        self.figure.tight_layout()
        self.draw()

class BacktestWorker(QThread):
    """Background worker for running backtests"""
    progress_updated = pyqtSignal(str, int)  # message, percentage
    backtest_completed = pyqtSignal(object)  # BacktestResults
    backtest_failed = pyqtSignal(str)  # error message
    
    def __init__(self, config: BacktestConfig):
        super().__init__()
        self.config = config
        
    def run(self):
        """Run backtest in background thread"""
        try:
            print("DEBUG: BacktestWorker starting...")
            print(f"DEBUG: Config - Symbols: {len(self.config.symbols)}, Start: {self.config.start_date}, End: {self.config.end_date}")
            
            engine = BacktestEngine(self.config)
            
            def progress_callback(message, percent):
                self.progress_updated.emit(message, percent)
                
            print("DEBUG: About to call engine.run_backtest()")
            results = engine.run_backtest(progress_callback)
            print("DEBUG: Engine completed, emitting results")
            self.backtest_completed.emit(results)
            
        except Exception as e:
            print(f"DEBUG: BacktestWorker exception: {e}")
            import traceback
            traceback.print_exc()
            self.backtest_failed.emit(str(e))

class BacktestApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Weekly ER Backtest - Professional Edition")
        self.setGeometry(50, 50, 1600, 1000)  # Bigger window
        
        # Create menu bar
        self.create_menu_bar()
        
        # Apply modern styling
        self.apply_professional_style()
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create tab widget for main navigation
        self.tabs = QTabWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.setup_tab = StrategySetupTab()
        self.results_tab = ResultsTab()
        self.live_tab = LiveTradingTab()
        self.settings_tab = SettingsTab()
        
        # Add tabs to main widget
        self.tabs.addTab(self.setup_tab, "Strategy Setup")
        self.tabs.addTab(self.results_tab, "Results & Analysis")
        self.tabs.addTab(self.live_tab, "Live Trading")
        self.tabs.addTab(self.settings_tab, "Settings")
        
        # Status bar with exit button
        status_bar = self.statusBar()
        status_bar.showMessage("Ready to backtest")
        
        # Add exit button to status bar
        self.exit_button = QPushButton("Exit Application")
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                font-size: 12px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.exit_button.clicked.connect(self.safe_close)
        status_bar.addPermanentWidget(self.exit_button)
        
        # Track application state for safe closing
        self.is_backtest_running = False
        self.active_dialogs = []
    
    def safe_close(self):
        """Safe close with confirmation if operations are active"""
        # Check if backtest is running
        if self.is_backtest_running:
            reply = QMessageBox.question(
                self, 'Backtest Running',
                'A backtest is currently running.\n\n'
                'Closing now will stop the backtest.\n'
                'Are you sure you want to exit?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Check for active dialogs (like Position Monitor)
        if self.active_dialogs:
            reply = QMessageBox.question(
                self, 'Active Windows',
                f'{len(self.active_dialogs)} trading window(s) are still open.\n\n'
                'Closing may disconnect IBKR connections.\n'
                'Are you sure you want to exit?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Proceed with close
        self.close()
    
    def closeEvent(self, event):
        """Handle window close event with proper cleanup"""
        try:
            # Check if backtest is running
            if self.is_backtest_running:
                reply = QMessageBox.question(
                    self, 'Confirm Exit',
                    'A backtest is currently running.\n\n'
                    'Closing now will stop the backtest.\n'
                    'Are you sure you want to exit?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
            
            # Stop any running backtest worker
            if hasattr(self.setup_tab, 'worker') and self.setup_tab.worker and self.setup_tab.worker.isRunning():
                self.setup_tab.worker.terminate()
                self.setup_tab.worker.wait(3000)  # Wait up to 3 seconds
            
            # Close any active dialogs
            for dialog in self.active_dialogs[:]:  # Copy list to avoid modification during iteration
                try:
                    if dialog and not dialog.isHidden():
                        dialog.close()
                except:
                    pass
            
            # Update status
            self.statusBar().showMessage("Shutting down...")
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            print(f"Error during close: {e}")
            # Accept anyway to prevent hanging
            event.accept()
    
    def create_menu_bar(self):
        """Create the application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.safe_close)
        
    def apply_professional_style(self):
        """Apply modern, professional styling with larger fonts"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 2px solid #dee2e6;
                background-color: white;
                border-radius: 10px;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                padding: 16px 28px;
                margin-right: 3px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: bold;
                font-size: 16px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #0d6efd;
            }
            QTabBar::tab:hover:!selected {
                background-color: #f8f9fa;
            }
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                padding: 16px 32px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                border: 2px solid #dee2e6;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #495057;
                font-size: 18px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {
                padding: 12px 16px;
                border: 2px solid #ced4da;
                border-radius: 6px;
                font-size: 16px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus {
                border: 2px solid #0d6efd;
                outline: none;
                box-shadow: 0 0 0 2px rgba(13, 110, 253, 0.25);
            }
            QLabel {
                font-size: 15px;
                color: #495057;
            }
            QTextEdit {
                font-size: 14px;
                padding: 10px;
                border: 2px solid #ced4da;
                border-radius: 6px;
            }
            QProgressBar {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                height: 25px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #0d6efd;
                border-radius: 4px;
            }
        """)

class StrategySetupTab(QWidget):
    """Strategy setup and configuration tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        
        # Left panel - Strategy inputs
        left_panel = QWidget()
        left_panel.setMaximumWidth(500)  # Wider left panel
        left_layout = QVBoxLayout(left_panel)
        
        # Universe selection group
        universe_group = QGroupBox("📋 Trading Universe")
        universe_layout = QFormLayout(universe_group)
        
        self.stocks_input = QLineEdit()
        self.stocks_input.setPlaceholderText("Enter up to 10 stocks/ETFs (e.g., AAPL,QQQ,MSFT)")
        universe_layout.addRow("Symbols:", self.stocks_input)
        
        # Quick preset buttons
        preset_layout = QHBoxLayout()
        preset_tech = QPushButton("Tech ETFs")
        preset_market = QPushButton("Market ETFs") 
        preset_leverage = QPushButton("Leveraged")
        preset_layout.addWidget(preset_tech)
        preset_layout.addWidget(preset_market)
        preset_layout.addWidget(preset_leverage)
        universe_layout.addRow("Presets:", preset_layout)
        
        left_layout.addWidget(universe_group)
        
        # Date range group
        dates_group = QGroupBox("📅 Backtest Period")
        dates_layout = QFormLayout(dates_group)
        
        # Calculate 12-month period ending at previous week
        from datetime import datetime, timedelta
        today = datetime.now()
        
        # Get previous Friday (end of last complete week)
        days_since_friday = (today.weekday() + 3) % 7  # Friday is 4, so days since Friday
        if days_since_friday == 0 and today.hour < 16:  # If it's Friday before market close
            days_since_friday = 7
        last_friday = today - timedelta(days=days_since_friday)
        
        # Get Monday of that same week
        last_monday = last_friday - timedelta(days=4)
        
        # Go back 12 months from that Monday
        start_date_12mo = last_monday - timedelta(days=365)
        
        self.start_date = QDateEdit(QDate(start_date_12mo.year, start_date_12mo.month, start_date_12mo.day))
        self.start_date.setCalendarPopup(True) 
        self.end_date = QDateEdit(QDate(last_friday.year, last_friday.month, last_friday.day))
        self.end_date.setCalendarPopup(True)
        
        dates_layout.addRow("Start Date:", self.start_date)
        dates_layout.addRow("End Date:", self.end_date)
        
        # Quick analysis button
        self.prev_week_btn = QPushButton("📈 Analyze Previous Week (Stock Selection)")
        self.prev_week_btn.clicked.connect(self.analyze_previous_week)
        dates_layout.addRow(self.prev_week_btn)
        
        left_layout.addWidget(dates_group)
        
        # Strategy parameters group
        params_group = QGroupBox("⚙️ Strategy Parameters")
        params_layout = QFormLayout(params_group)
        
        self.capital_per_trade = QSpinBox()
        self.capital_per_trade.setRange(1000, 100000)
        self.capital_per_trade.setValue(10000)
        self.capital_per_trade.setSuffix(" USD")
        
        self.stop_loss_pct = QDoubleSpinBox()
        self.stop_loss_pct.setRange(0.5, 10.0)
        self.stop_loss_pct.setValue(2.0)
        self.stop_loss_pct.setSuffix("%")
        self.stop_loss_pct.setDecimals(1)
        
        self.expected_return = QDoubleSpinBox()
        self.expected_return.setRange(0.5, 10.0)
        self.expected_return.setValue(2.0)
        self.expected_return.setSuffix("%")
        self.expected_return.setDecimals(1)
        
        params_layout.addRow("Capital per Trade:", self.capital_per_trade)
        params_layout.addRow("Stop Loss:", self.stop_loss_pct)
        params_layout.addRow("Expected Return:", self.expected_return)
        
        left_layout.addWidget(params_group)
        
        # Run button
        self.run_button = QPushButton("Run Backtest")
        self.run_button.setMinimumHeight(70)  # Even bigger button
        self.run_button.clicked.connect(self.run_backtest)
        left_layout.addWidget(self.run_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        
        left_layout.addStretch()
        
        # Right panel - Preview/validation
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        preview_group = QGroupBox("👁️ Configuration Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)
        
        right_layout.addWidget(preview_group)
        
        # Validation group
        validation_group = QGroupBox("✅ Validation")
        validation_layout = QVBoxLayout(validation_group)
        
        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        validation_layout.addWidget(self.validation_text)
        
        right_layout.addWidget(validation_group)
        
        # Add panels to main layout
        layout.addWidget(left_panel)
        layout.addWidget(right_panel, 1)
        
        # Connect signals for live preview
        self.stocks_input.textChanged.connect(self.update_preview)
        self.start_date.dateChanged.connect(self.update_preview)
        self.end_date.dateChanged.connect(self.update_preview)
        
        # Set preset button actions
        preset_tech.clicked.connect(lambda: self.set_preset("QQQ,XLK,ARKK"))
        preset_market.clicked.connect(lambda: self.set_preset("SPY,QQQ,IWM"))
        preset_leverage.clicked.connect(lambda: self.set_preset("TQQQ,SPXL,SQQQ"))
        
        # Initial preview
        self.update_preview()
        
    def set_preset(self, symbols):
        """Set preset symbol combinations"""
        self.stocks_input.setText(symbols)
        
    def update_preview(self):
        """Update configuration preview"""
        symbols = self.stocks_input.text().strip().upper()
        symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
        
        preview = f"""Configuration Summary:
        
📊 Universe: {len(symbol_list) if symbol_list else 'AUTO (Full Universe)'} symbols
   {', '.join(symbol_list) if symbol_list else 'Will load all 116 stocks from tickers.csv'}

📅 Period: {self.start_date.date().toString('yyyy-MM-dd')} to {self.end_date.date().toString('yyyy-MM-dd')}
   Duration: {self.start_date.date().daysTo(self.end_date.date())} days

💰 Capital: ${self.capital_per_trade.value():,} per trade
🛑 Stop Loss: {self.stop_loss_pct.value()}%
🎯 Target Return: {self.expected_return.value()}%
"""
        self.preview_text.setPlainText(preview)
        
        # Validation  
        validation_messages = []
        if not symbol_list:
            validation_messages.append("💡 Will use full universe (116 stocks from tickers.csv)")
        elif len(symbol_list) > 10:
            validation_messages.append("⚠️ Too many symbols (max 10 for manual selection)")
            
        if self.start_date.date() >= self.end_date.date():
            validation_messages.append("❌ Start date must be before end date")
        
        # Check for future dates    
        today = QDate.currentDate()
        if self.end_date.date() > today.addDays(-2):  # End date should be at least 2 days ago
            validation_messages.append("⚠️ End date very recent - data may be delayed")
        if self.start_date.date() > today:
            validation_messages.append("❌ Start date is in the future - no data available")
            
        if not validation_messages:
            validation_messages.append("✅ Configuration looks good!")
            
        self.validation_text.setPlainText('\n'.join(validation_messages))
        
    def analyze_previous_week(self):
        """Analyze previous week for stock selection"""
        from datetime import datetime, timedelta
        
        # Use last week August 19-23, 2025 (Monday to Friday)
        last_monday = datetime(2025, 8, 18)  # Last Monday
        last_friday = datetime(2025, 8, 22)  # Last Friday
        
        # Set the dates  
        self.start_date.setDate(QDate(last_monday.year, last_monday.month, last_monday.day))
        self.end_date.setDate(QDate(last_friday.year, last_friday.month, last_friday.day))
        
        print(f"Analyzing last week: {last_monday.strftime('%Y-%m-%d')} to {last_friday.strftime('%Y-%m-%d')}")
        
        # Clear stock selection to use full universe
        self.stocks_input.clear()
        
        # Run the backtest
        self.run_backtest()

    def run_backtest(self):
        """Run the backtest"""
        print("DEBUG: run_backtest() called")
        
        # Validate inputs
        symbols_text = self.stocks_input.text().strip().upper()
        symbol_list = [s.strip() for s in symbols_text.split(',') if s.strip()]
        print(f"DEBUG: symbols_text = '{symbols_text}', symbol_list = {symbol_list}")
        
        if not symbol_list:
            # Load full universe from tickers.csv
            print("DEBUG: Loading full universe from tickers.csv")
            try:
                import pandas as pd
                tickers_df = pd.read_csv('tickers.csv')
                symbol_list = tickers_df['Ticker'].tolist()
                print(f"DEBUG: Successfully loaded {len(symbol_list)} symbols from tickers.csv")
            except Exception as e:
                print(f"DEBUG: Failed to load tickers.csv: {e}")
                self.validation_text.setPlainText(f"❌ Failed to load tickers.csv: {e}")
                return
            
        # Only enforce 10-symbol limit for manual input
        if symbols_text and len(symbol_list) > 10:  # symbols_text is empty if using full universe
            self.validation_text.setPlainText("❌ Maximum 10 symbols allowed for manual selection")
            return
        
        # Prepare configuration with date validation
        print("DEBUG: Creating BacktestConfig")
        start_date_str = self.start_date.date().toString('yyyy-MM-dd')
        end_date_str = self.end_date.date().toString('yyyy-MM-dd')
        print(f"DEBUG: GUI shows Start: {start_date_str}, End: {end_date_str}")
        
        # Validate date range (allow any reasonable dates since we're in 2025)
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        
        if start_date >= end_date:
            self.validation_text.setPlainText("❌ Start date must be before end date")
            return
            
        # Allow dates from 2020 onwards (reasonable for stock data)
        if start_date.year < 2020:
            self.validation_text.setPlainText("❌ Start date too early. Please use dates from 2020 onwards.")
            return
        
        config = BacktestConfig(
            symbols=symbol_list,
            start_date=start_date_str,
            end_date=end_date_str,
            capital_per_trade=float(self.capital_per_trade.value()),
            expected_return_pct=self.expected_return.value(),
            stop_loss_pct=self.stop_loss_pct.value()
        )
        print("DEBUG: Config created successfully")
        
        # Start background worker
        print("DEBUG: Creating BacktestWorker")
        self.worker = BacktestWorker(config)
        self.worker.progress_updated.connect(self.on_progress_update)
        self.worker.backtest_completed.connect(self.on_backtest_completed)
        self.worker.backtest_failed.connect(self.on_backtest_failed)
        
        # Update UI and track state
        print("DEBUG: Starting worker thread")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.run_button.setText("Running...")
        
        # Mark backtest as running
        main_window = self.window()
        if hasattr(main_window, 'is_backtest_running'):
            main_window.is_backtest_running = True
        
        # Start the worker thread
        print("DEBUG: About to start worker.start()")
        self.worker.start()
        print("DEBUG: Worker.start() called")
        
    def on_progress_update(self, message: str, percent: int):
        """Handle progress updates"""
        self.progress_bar.setValue(percent)
        # Get the main window to update status bar
        main_window = self.window()
        if hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(message)
        
    def on_backtest_completed(self, results: BacktestResults):
        """Handle successful backtest completion"""
        try:
            print("DEBUG: on_backtest_completed called")
            self.progress_bar.setVisible(False)
            self.run_button.setEnabled(True)
            self.run_button.setText("🚀 Run Backtest")
            
            # Update status bar and mark backtest as complete
            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage("Backtest completed successfully!")
            if hasattr(main_window, 'is_backtest_running'):
                main_window.is_backtest_running = False
                
            print("DEBUG: About to switch to results tab")
        except Exception as e:
            print(f"ERROR: Exception in on_backtest_completed: {e}")
            import traceback
            traceback.print_exc()
        
        # Switch to results tab and display results
        try:
            main_window = self.window()
            if hasattr(main_window, 'tabs'):
                print("DEBUG: Switching to results tab")
                main_window.tabs.setCurrentIndex(1)  # Switch to results tab
                print("DEBUG: Calling display_results")
                main_window.results_tab.display_results(results)
                print("DEBUG: display_results completed")
        except Exception as e:
            print(f"ERROR: Exception in results display: {e}")
            import traceback
            traceback.print_exc()
        
    def on_backtest_failed(self, error_message: str):
        """Handle backtest failure"""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.run_button.setText("🚀 Run Backtest")
        
        # Update status bar and mark backtest as complete
        main_window = self.window()
        if hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage("Backtest failed")
        if hasattr(main_window, 'is_backtest_running'):
            main_window.is_backtest_running = False
            
        self.validation_text.setPlainText(f"❌ Backtest failed: {error_message}")

class ResultsTab(QWidget):
    """Results and analysis tab"""
    
    def __init__(self):
        super().__init__()
        self.results = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Results summary panel - organized in columns
        self.summary_group = QGroupBox("📊 Performance Summary")
        summary_layout = QHBoxLayout(self.summary_group)
        
        # Create labels
        self.total_return_label = QLabel("--")
        self.total_return_dollar_label = QLabel("--")
        self.starting_capital_label = QLabel("--")
        self.ending_value_label = QLabel("--")
        self.annualized_return_label = QLabel("--")
        self.sharpe_ratio_label = QLabel("--")
        self.max_drawdown_label = QLabel("--")
        self.max_drawdown_dollar_label = QLabel("--")
        self.win_rate_label = QLabel("--")
        self.total_trades_label = QLabel("--")
        
        # Column 1 - Capital & Returns
        col1_layout = QFormLayout()
        col1_layout.addRow("Starting Capital:", self.starting_capital_label)
        col1_layout.addRow("Ending Value:", self.ending_value_label)
        col1_layout.addRow("Total Return:", self.total_return_label)
        col1_layout.addRow("Total Return ($):", self.total_return_dollar_label)
        col1_layout.addRow("Annualized Return:", self.annualized_return_label)
        
        # Column 2 - Risk & Trading Metrics  
        col2_layout = QFormLayout()
        col2_layout.addRow("Max Drawdown:", self.max_drawdown_label)
        col2_layout.addRow("Max Drawdown ($):", self.max_drawdown_dollar_label)
        col2_layout.addRow("Sharpe Ratio:", self.sharpe_ratio_label)
        col2_layout.addRow("Win Rate:", self.win_rate_label)
        col2_layout.addRow("Total Trades:", self.total_trades_label)
        
        # Add columns to main layout
        summary_layout.addLayout(col1_layout)
        summary_layout.addLayout(col2_layout)
        
        # Add trades display to the right of performance summary
        trades_column = QVBoxLayout()
        trades_label = QLabel("📊 Weekly Top 5 Picks")
        trades_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        trades_column.addWidget(trades_label)
        
        self.trades_text = QTextEdit()
        self.trades_text.setMinimumHeight(180)  # Smaller - fits exactly 10 trades
        self.trades_text.setMinimumWidth(400)   # Keep width for 2 columns
        self.trades_text.setMaximumHeight(180)  # Fixed height - no growing
        self.trades_text.setReadOnly(True)
        # Add darker border and better styling
        self.trades_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #6c757d;
                border-radius: 8px;
                padding: 8px;
                background-color: #f8f9fa;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        trades_column.addWidget(self.trades_text)
        
        summary_layout.addLayout(trades_column)
        
        layout.addWidget(self.summary_group)
        
        # Charts section with real matplotlib charts
        self.charts_group = QGroupBox("📈 Performance Charts")
        charts_layout = QVBoxLayout(self.charts_group)
        
        # Create the chart widget
        self.chart_widget = ChartWidget(parent=self, width=8, height=6, dpi=100)
        charts_layout.addWidget(self.chart_widget)
        
        layout.addWidget(self.charts_group)
        
        # Initially hide results groups
        self.summary_group.setVisible(False)
        self.charts_group.setVisible(False)
        
        # Show placeholder
        self.placeholder_label = QLabel("🚀 Run a backtest to see results here!")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("font-size: 28px; color: #6c757d; margin: 100px; font-weight: bold;")
        layout.addWidget(self.placeholder_label)
        
    def display_results(self, results: BacktestResults):
        """Display backtest results"""
        self.results = results
        
        # Hide placeholder
        self.placeholder_label.setVisible(False)
        
        # Show results groups
        self.summary_group.setVisible(True)
        self.charts_group.setVisible(True)
        
        # Calculate dollar amounts from equity curve
        if not results.equity_curve.empty:
            starting_value = results.equity_curve.iloc[0]['equity']
            ending_value = results.equity_curve.iloc[-1]['equity']
            total_return_dollars = ending_value - starting_value
            
            # Calculate max drawdown in dollars
            if 'drawdown' in results.equity_curve.columns:
                max_dd_pct = abs(results.equity_curve['drawdown'].min())
                max_drawdown_dollars = starting_value * (max_dd_pct / 100)
            else:
                peak_values = results.equity_curve['equity'].cummax()
                drawdowns = results.equity_curve['equity'] - peak_values
                max_drawdown_dollars = abs(drawdowns.min())
        else:
            starting_value = 100000  # Default
            ending_value = starting_value * (1 + results.total_return_pct / 100)
            total_return_dollars = ending_value - starting_value
            max_drawdown_dollars = starting_value * (results.max_drawdown_pct / 100)
        
        # Update summary metrics
        self.starting_capital_label.setText(f"${starting_value:,.0f}")
        self.ending_value_label.setText(f"${ending_value:,.0f}")
        self.total_return_label.setText(f"{results.total_return_pct:.2f}%")
        self.total_return_dollar_label.setText(f"${total_return_dollars:,.0f}")
        self.annualized_return_label.setText(f"{results.annualized_return_pct:.2f}%")
        self.sharpe_ratio_label.setText(f"{results.sharpe_ratio:.2f}")
        self.max_drawdown_label.setText(f"{results.max_drawdown_pct:.2f}%")
        self.max_drawdown_dollar_label.setText(f"${max_drawdown_dollars:,.0f}")
        self.win_rate_label.setText(f"{results.win_rate_pct:.1f}%")
        self.total_trades_label.setText(f"{results.total_trades}")
        
        # Color code performance (both percentage and dollar amounts)
        color_style = "color: #198754; font-weight: bold;" if results.total_return_pct > 0 else "color: #dc3545; font-weight: bold;"
        self.total_return_label.setStyleSheet(color_style)
        self.total_return_dollar_label.setStyleSheet(color_style)
        self.ending_value_label.setStyleSheet(color_style)
            
        # Plot the actual charts
        self.chart_widget.plot_equity_curve(results)
        
        # Display weekly top 5 selections
        print(f"DEBUG: Results has {len(results.weekly_selections)} weekly selections")
        if results.weekly_selections:
            # Show last 2 weeks of selections
            recent_weeks = results.weekly_selections[-2:]
            
            # Check if this is a single week analysis (stock selection)
            if len(results.weekly_selections) == 1:
                # Show universe info for stock selection - assume full universe for now
                trades_text = f"🎯 TOP 5 STOCKS FOR THIS WEEK:\n(From full universe: ~100+ stocks analyzed)\n\n"
            else:
                trades_text = f"Most Recent Weekly Picks:\n\n"
            
            for week_data in recent_weeks:
                week_date = week_data['date']
                stocks = week_data['stocks']
                
                trades_text += f"Week of {week_date[-5:]}:\n"  # Just MM-DD
                for i, (symbol, momentum) in enumerate(stocks):
                    trades_text += f"  {i+1}. {symbol} ({momentum:+4.1f}%)\n"
                trades_text += "\n"
                
            # Use popup dialog to show stock picks (similar to system status fix)
            try:
                self.trades_text.setPlainText(trades_text)
                print(f"DEBUG: Set trades_text with {len(trades_text)} characters")
                
                # Also show popup for clear visibility
                if len(results.weekly_selections) == 1:  # Single week analysis
                    self.show_stock_picks_popup(trades_text)
                    
            except Exception as e:
                print(f"DEBUG: Error setting trades_text: {e}")
                # Fallback to popup only
                self.show_stock_picks_popup(trades_text)
        else:
            print("DEBUG: No weekly selections found!")
            error_text = "No weekly selections found.\n\nPossible causes:\n• Date range in the future\n• Insufficient data for selected period\n• All symbols filtered out\n\nTry a historical date range\n(e.g., Jan 2023 - Dec 2023)"
            self.trades_text.setPlainText(error_text)
            
    def show_stock_picks_popup(self, content):
        """Show stock picks in popup dialog"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Weekly Stock Selections")
            dialog.setGeometry(200, 200, 500, 400)
            
            layout = QVBoxLayout(dialog)
            
            text_widget = QTextEdit()
            text_widget.setPlainText(content)
            text_widget.setReadOnly(True)
            text_widget.setStyleSheet("""
                QTextEdit {
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                }
            """)
            
            layout.addWidget(text_widget)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            print(f"DEBUG: Error showing stock picks popup: {e}")
            QMessageBox.information(self, "Stock Picks", content)

class LiveTradingTab(QWidget):
    """Live trading control and monitoring tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Live trading controls group
        controls_group = QGroupBox("🚀 Live Trading Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        # Quick action buttons
        button_layout = QHBoxLayout()
        
        self.position_monitor_btn = QPushButton("📊 Position Monitor")
        self.position_monitor_btn.setMinimumHeight(60)
        self.position_monitor_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.position_monitor_btn.clicked.connect(self.launch_position_monitor)
        
        self.setup_live_btn = QPushButton("⚙️ Setup IBKR")
        self.setup_live_btn.setMinimumHeight(60)
        self.setup_live_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.setup_live_btn.clicked.connect(self.launch_setup)
        
        self.system_monitor_btn = QPushButton("🔍 System Status")
        self.system_monitor_btn.setMinimumHeight(60)
        self.system_monitor_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.system_monitor_btn.clicked.connect(self.launch_system_monitor)
        
        button_layout.addWidget(self.position_monitor_btn)
        button_layout.addWidget(self.setup_live_btn)
        button_layout.addWidget(self.system_monitor_btn)
        
        controls_layout.addLayout(button_layout)
        
        # Full live trading button
        self.full_live_btn = QPushButton("🔄 Start Full Live Trading (Monday-Friday Cycle)")
        self.full_live_btn.setMinimumHeight(80)
        self.full_live_btn.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            background-color: #28a745;
            color: white;
        """)
        self.full_live_btn.clicked.connect(self.launch_full_live)
        controls_layout.addWidget(self.full_live_btn)
        
        layout.addWidget(controls_group)
        
        # Status display group
        status_group = QGroupBox("📈 Live Trading Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(400)  # Increased height
        # Enable scrolling
        from PyQt6.QtCore import Qt
        self.status_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.status_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.status_text.setPlainText("""Live Trading Status:

🔄 Ready to start live trading
📊 Use Position Monitor to view current positions
⚙️ Use Setup IBKR to configure connection
🔍 Use System Status to check connections
🚀 Use Full Live Trading for complete automation

Quick Start:
1. Click 'Setup IBKR' to configure connection
2. Click 'Position Monitor' to see current positions  
3. Click 'Start Full Live Trading' for automation

Friday Close: Use Position Monitor option 2 to close all positions
""")
        
        status_layout.addWidget(self.status_text)
        layout.addWidget(status_group)
        
        # IBKR Connection Status group
        ibkr_group = QGroupBox("🔗 IBKR Connection Status")
        ibkr_layout = QVBoxLayout(ibkr_group)
        
        # Connection status display
        self.connection_status = QLabel("🔴 IBKR: Not Connected")
        self.connection_status.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            padding: 10px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
        """)
        
        # Test connection button
        self.test_connection_btn = QPushButton("🔍 Test IBKR Connection")
        self.test_connection_btn.clicked.connect(self.test_ibkr_connection)
        
        ibkr_layout.addWidget(self.connection_status)
        ibkr_layout.addWidget(self.test_connection_btn)
        layout.addWidget(ibkr_group)
        
        # Documentation group
        docs_group = QGroupBox("📚 Documentation & Help")
        docs_layout = QVBoxLayout(docs_group)
        
        self.docs_btn = QPushButton("📖 Open Live Trading Guide")
        self.docs_btn.clicked.connect(self.open_documentation)
        
        self.help_text = QLabel("""
Live Trading Features:
• Position Monitor: Real-time position monitoring and closing
• Setup IBKR: Interactive IBKR connection configuration
• System Status: Real-time system health monitoring  
• Full Live Trading: Complete Monday-Friday automation
• Friday Close: Emergency position closing anytime
        """)
        self.help_text.setWordWrap(True)
        
        docs_layout.addWidget(self.docs_btn)
        docs_layout.addWidget(self.help_text)
        layout.addWidget(docs_group)
        
    def launch_position_monitor(self):
        """Open Professional Position Monitor with real-time updates"""
        self.status_text.append("🚀 Launching Professional Position Monitor...")
        
        try:
            from professional_position_monitor import ProfessionalPositionMonitor
            self.status_text.append("✅ Professional Monitor imported successfully")
            
            # Launch the professional monitor
            dialog = ProfessionalPositionMonitor(self)
            self.status_text.append("✅ Professional Monitor created successfully")
            
            # Track the dialog for safe closing
            main_window = self.window()
            if hasattr(main_window, 'active_dialogs'):
                main_window.active_dialogs.append(dialog)
            
            # Show dialog and wait for it to close
            dialog.exec()
            
            # Remove from tracking when closed
            if hasattr(main_window, 'active_dialogs') and dialog in main_window.active_dialogs:
                main_window.active_dialogs.remove(dialog)
            
            self.status_text.append("✅ Professional Position Monitor closed normally")
            
        except Exception as e:
            self.status_text.append(f"❌ Professional Monitor failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to simple monitor if professional fails
            self.status_text.append("🔄 Falling back to Simple Monitor...")
            try:
                from simple_working_monitor import SimpleWorkingMonitor
                dialog = SimpleWorkingMonitor(self)
                
                # Track the fallback dialog too
                main_window = self.window()
                if hasattr(main_window, 'active_dialogs'):
                    main_window.active_dialogs.append(dialog)
                
                dialog.exec()
                
                # Remove from tracking when closed
                if hasattr(main_window, 'active_dialogs') and dialog in main_window.active_dialogs:
                    main_window.active_dialogs.remove(dialog)
                
                self.status_text.append("✅ Simple Monitor fallback successful")
            except Exception as e2:
                self.status_text.append(f"❌ Fallback also failed: {e2}")
    
    def launch_setup(self):
        """Open integrated IBKR setup dialog"""
        print("DEBUG: launch_setup called")
        
        try:
            from integrated_setup_dialog import IBKRSetupDialog
            dialog = IBKRSetupDialog(self)
            result = dialog.exec()
            
            # Show result in popup
            from PyQt6.QtWidgets import QMessageBox
            if result == QDialog.DialogCode.Accepted:
                QMessageBox.information(self, "IBKR Setup", "✅ IBKR configuration saved successfully!")
            else:
                QMessageBox.information(self, "IBKR Setup", "📝 Setup cancelled by user")
                
        except ImportError as e:
            print(f"DEBUG: Import error in setup: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "IBKR Setup Error", 
                              f"❌ IBKR Setup dialog import failed:\n{e}\n\n💡 Use Position Monitor instead")
        except Exception as e:
            print(f"DEBUG: Exception in setup: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "IBKR Setup Error", 
                               f"❌ Error opening IBKR Setup:\n{e}")
            import traceback
            traceback.print_exc()
    
    def launch_system_monitor(self):
        """Show system status in a popup dialog"""
        try:
            print("DEBUG: Starting system monitor")
            from PyQt6.QtWidgets import QMessageBox
            
            # Build system status text
            status_lines = []
            status_lines.append("🔍 SYSTEM STATUS CHECK")
            status_lines.append("="*30)
            status_lines.append("✅ Modern GUI: Running")
            
            # Check for key files
            import os
            files_to_check = ['backtest_core.py', 'tickers.csv', 'config.json']
            for file in files_to_check:
                if os.path.exists(file):
                    status_lines.append(f"✅ {file}: Found")
                else:
                    status_lines.append(f"❌ {file}: Missing")
            
            # Check data directory
            if os.path.exists('data'):
                status_lines.append("✅ Data directory: Found")
            else:
                status_lines.append("❌ Data directory: Missing")
                
            status_lines.append("✅ Backtest engine: Loaded")
            status_lines.append("")
            status_lines.append("💡 Use Position Monitor for live IBKR status")
            status_lines.append("💡 Use Test Connection to verify IBKR")
            
            # Show in popup dialog
            status_text = "\n".join(status_lines)
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("System Status")
            msg_box.setText(status_text)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.exec()
            
            print("DEBUG: System status dialog shown")
            
        except Exception as e:
            print(f"DEBUG: Exception in launch_system_monitor: {e}")
            import traceback
            traceback.print_exc()
    
    def launch_full_live(self):
        """Launch full live trading system with flexible controls"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(self, 'Start Full Live Trading', 
                                   'This will start the flexible live trading system.\n\n'
                                   'Features:\n'
                                   '• Start trading anytime (not just Monday)\n'
                                   '• Monitor positions in real-time\n'
                                   '• Manual close options available\n'
                                   '• Emergency stop capabilities\n\n'
                                   'Make sure IBKR TWS/Gateway is running.\n\n'
                                   'Continue?',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Launch the full trading system (ibkr_live_runner.py) 
                import subprocess
                import sys
                subprocess.Popen([sys.executable, "ibkr_live_runner.py"])
                self.status_text.append("🚀 Full Live Trading System launched")
                self.status_text.append("✅ System will run Monday-Friday cycle")
                self.status_text.append("💡 Use Position Monitor anytime to:")
                self.status_text.append("  • Monitor positions in real-time")
                self.status_text.append("  • Close positions manually if needed")
                self.status_text.append("  • Override Friday auto-close")
            except Exception as e:
                self.status_text.append(f"❌ Error launching Full Live Trading: {e}")
    
    def test_ibkr_connection(self):
        """Test IBKR connection status"""
        try:
            # Load config to use actual connection settings
            import json
            try:
                with open("config.json", 'r') as f:
                    config = json.load(f)
                host = config.get("ib_host", "127.0.0.1")
                port = int(config.get("ib_port", 7497))
                client_id = int(config.get("ib_client_id", 7))
            except:
                host = "127.0.0.1"
                port = 7497
                client_id = 7
            
            # Try to test IBKR connection
            from ib_insync import IB
            
            ib = IB()
            # Quick connection test using actual config
            try:
                print(f"DEBUG: Testing connection to {host}:{port} with client ID {client_id}")
                ib.connect(host, port, clientId=client_id + 100, timeout=5)  # Use different client ID
                port_name = "Paper Trading" if port == 7497 else "Live Trading" if port == 7496 else f"Port {port}"
                self.connection_status.setText(f"🟢 IBKR: Connected ({port_name})")
                self.connection_status.setStyleSheet("""
                    font-size: 16px; 
                    font-weight: bold; 
                    padding: 10px;
                    background-color: #d4edda;
                    border: 1px solid #c3e6cb;
                    border-radius: 5px;
                """)
                ib.disconnect()
                self.status_text.append(f"✅ IBKR connection successful to {host}:{port}")
            except Exception as e:
                print(f"DEBUG: Connection failed: {e}")
                self.connection_status.setText("🔴 IBKR: Not Connected")
                self.connection_status.setStyleSheet("""
                    font-size: 16px; 
                    font-weight: bold; 
                    padding: 10px;
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 5px;
                """)
                self.status_text.append(f"❌ IBKR connection failed to {host}:{port} - {e}")
                    
        except ImportError:
            self.status_text.append("❌ ib-insync not available for connection test")
        except Exception as e:
            self.connection_status.setText("🔴 IBKR: Connection Error")
            self.status_text.append(f"❌ IBKR connection test failed: {e}")
    
    def open_documentation(self):
        """Open live trading documentation"""
        import subprocess
        import sys
        from pathlib import Path
        
        doc_file = Path("LIVE_TRADING_GUIDE.md")
        if doc_file.exists():
            try:
                if sys.platform == "win32":
                    import os
                    os.startfile(doc_file)
                else:
                    subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", doc_file])
                self.status_text.append("📖 Documentation opened")
            except Exception as e:
                self.status_text.append(f"❌ Error opening documentation: {e}")
        else:
            self.status_text.append("❌ Documentation file not found")

class SettingsTab(QWidget):
    """Settings and preferences tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # IBKR settings group
        ibkr_group = QGroupBox("🔌 IBKR Connection")
        ibkr_layout = QFormLayout(ibkr_group)
        
        self.ib_host = QLineEdit("127.0.0.1")
        self.ib_port = QSpinBox()
        self.ib_port.setRange(1000, 9999)
        self.ib_port.setValue(7497)
        self.ib_client_id = QSpinBox()
        self.ib_client_id.setRange(1, 999)
        self.ib_client_id.setValue(7)
        
        ibkr_layout.addRow("Host:", self.ib_host)
        ibkr_layout.addRow("Port:", self.ib_port)
        ibkr_layout.addRow("Client ID:", self.ib_client_id)
        
        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        
        layout.addWidget(ibkr_group)
        layout.addWidget(save_btn)
        layout.addStretch()
        
        # Load current settings
        self.load_settings()
    
    def load_settings(self):
        """Load settings from config.json"""
        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
                
            self.ib_host.setText(config.get("ib_host", "127.0.0.1"))
            self.ib_port.setValue(int(config.get("ib_port", 7497)))
            self.ib_client_id.setValue(int(config.get("ib_client_id", 7)))
        except Exception as e:
            # Use defaults if config doesn't exist
            pass
    
    def save_settings(self):
        """Save settings to config.json"""
        try:
            # Load existing config
            try:
                with open("config.json", 'r') as f:
                    config = json.load(f)
            except:
                config = {}
            
            # Update IBKR settings
            config["ib_host"] = self.ib_host.text()
            config["ib_port"] = self.ib_port.value()
            config["ib_client_id"] = self.ib_client_id.value()
            
            # Save back to file
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=2)
                
            QMessageBox.information(self, "Settings Saved", 
                                  f"✅ IBKR settings saved successfully!\n\n"
                                  f"Host: {config['ib_host']}\n"
                                  f"Port: {config['ib_port']}\n" 
                                  f"Client ID: {config['ib_client_id']}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"❌ Failed to save settings:\n{e}")

def main():
    """Main application entry point"""
    # Check if QApplication already exists
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Weekly ER Backtest")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Trading Systems")
    
    # Create and show main window
    window = BacktestApp()
    window.show()
    
    # Run application (avoid sys.exit to prevent hanging)
    return app.exec()

if __name__ == "__main__":
    main()
