#!/usr/bin/env python3
"""
Clean Backtest Engine
Simple, fast, reliable backtesting without hanging issues

Inspired by Backtesting.py's clean API approach
"""

import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json
import warnings
warnings.filterwarnings('ignore')

@dataclass
class BacktestConfig:
    """Clean configuration for backtesting"""
    symbols: List[str]
    start_date: str
    end_date: str
    capital_per_trade: float = 10000.0
    expected_return_pct: float = 2.0
    stop_loss_pct: float = 2.0
    commission_per_trade: float = 1.0

@dataclass 
class BacktestResults:
    """Results from backtesting"""
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    profit_factor: float
    trades_df: pd.DataFrame
    equity_curve: pd.DataFrame
    weekly_selections: list
    
class BacktestEngine:
    """Clean, fast backtesting engine"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.data = {}
        self.trades = []
        self.equity_curve = []
        self.weekly_selections = []  # Track top 5 each week
        
    def download_data(self, progress_callback=None) -> bool:
        """Download price data for all symbols"""
        try:
            total_symbols = len(self.config.symbols)
            
            for i, symbol in enumerate(self.config.symbols):
                if progress_callback:
                    progress_callback(f"Downloading {symbol}...", int((i / total_symbols) * 50))
                
                # Download data with timeout
                ticker = yf.Ticker(symbol)
                data = ticker.history(
                    start=self.config.start_date,
                    end=self.config.end_date,
                    interval="1d",
                    timeout=10
                )
                
                if data.empty:
                    print(f"Warning: No data for {symbol}")
                    continue
                    
                # Clean data
                data = data.dropna()
                if len(data) < 1:  # Need at least 1 day of data
                    print(f"Warning: No data for {symbol} ({len(data)} days)")
                    continue
                # Show which days we actually got for first few symbols
                if symbol in ['AAL', 'ACHC', 'ADC']:
                    print(f"DEBUG: Loaded {len(data)} days for {symbol}")
                    print(f"DEBUG: {symbol} dates: {data.index.strftime('%Y-%m-%d').tolist()}")
                    print(f"DEBUG: Expected: 2025-08-18 to 2025-08-22")
                    
                self.data[symbol] = data
                
            if progress_callback:
                progress_callback("Data download complete", 50)
                
            successful_symbols = list(self.data.keys())
            print(f"DEBUG: Successfully loaded data for {len(self.data)} symbols out of {len(self.config.symbols)} total")
            if successful_symbols:
                print(f"DEBUG: Loaded symbols: {successful_symbols[:10]}{'...' if len(successful_symbols) > 10 else ''}")
            
            return len(self.data) > 0
            
        except Exception as e:
            print(f"Error downloading data: {e}")
            return False
    
    def calculate_momentum(self, prices: pd.Series, days: int = 5) -> float:
        """Calculate simple momentum"""
        # Use available data, minimum 2 days
        available_days = min(days, len(prices) - 1)
        if available_days < 1:
            return 0
        
        current_price = prices.iloc[-1]
        past_price = prices.iloc[-(available_days+1)]
        momentum = ((current_price - past_price) / past_price) * 100
        
        return momentum
    
    def get_trading_weeks(self) -> List[Tuple[str, str]]:
        """Get Monday-Friday trading weeks"""
        start = pd.to_datetime(self.config.start_date)
        end = pd.to_datetime(self.config.end_date)
        
        # For single week or simple date ranges, just use the provided dates
        if (end - start).days <= 7:
            # Simple case: just use start and end dates as one week
            return [(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))]
        
        # Complex logic for multi-week backtests
        weeks = []
        current = start
        
        while current <= end:
            # Find next Monday from current position
            days_ahead = 0 - current.weekday()  # Monday is 0
            if days_ahead <= 0:  # If current day is Monday or later in week
                days_ahead += 7  # Go to next Monday
            monday = current + dt.timedelta(days=days_ahead)
            
            if monday > end:  # Monday is past end date
                break
                
            friday = monday + dt.timedelta(days=4)
            if friday <= end:  # Only include complete weeks
                weeks.append((monday.strftime('%Y-%m-%d'), friday.strftime('%Y-%m-%d')))
            
            current = monday + dt.timedelta(days=1)  # Move to Tuesday to find next Monday
            
        return weeks
    
    def run_backtest(self, progress_callback=None) -> BacktestResults:
        """Run the complete backtest"""
        
        print(f"DEBUG: Starting backtest with {len(self.config.symbols)} symbols")
        print(f"DEBUG: Date range: {self.config.start_date} to {self.config.end_date}")
        
        # Download data
        if not self.download_data(progress_callback):
            print("DEBUG: Data download failed!")
            raise Exception("Failed to download data")
        
        print(f"DEBUG: Downloaded data for {len(self.data)} symbols")
        
        # Get trading weeks
        weeks = self.get_trading_weeks()
        total_weeks = len(weeks)
        print(f"DEBUG: Found {total_weeks} trading weeks")
        print(f"DEBUG: Trading weeks: {weeks}")
        
        if progress_callback:
            progress_callback(f"Running backtest for {total_weeks} weeks...", 60)
        
        # Calculate starting portfolio - use reasonable total regardless of universe size
        if len(self.config.symbols) <= 10:
            # Manual selection: use capital per trade × symbols
            portfolio_value = self.config.capital_per_trade * len(self.config.symbols)
        else:
            # Full universe: use fixed total portfolio (5 positions × capital per trade)
            portfolio_value = self.config.capital_per_trade * 5
        equity_values = [{'date': self.config.start_date, 'equity': portfolio_value}]
        
        for week_idx, (monday, friday) in enumerate(weeks):
            if progress_callback:
                progress = 60 + int((week_idx / total_weeks) * 35)
                progress_callback(f"Week {week_idx + 1}/{total_weeks}: {monday}", progress)
            
            # Get momentum rankings for the full week
            rankings = []
            for symbol, data in self.data.items():
                # Get data for the full week (Monday to Friday)
                week_data = data[(data.index >= monday) & (data.index <= friday)]
                if len(week_data) < 2:  # Need at least 2 days to calculate momentum
                    continue
                    
                momentum = self.calculate_momentum(week_data['Close'])
                rankings.append((symbol, momentum))
                
                # Debug first few symbols that actually make it through
                if len(rankings) <= 3:
                    print(f"DEBUG: {symbol} week_data length: {len(week_data)}, momentum: {momentum}")
                    print(f"DEBUG: {symbol} close prices: {week_data['Close'].tolist()}")
                    print(f"DEBUG: {symbol} date range: {week_data.index[0]} to {week_data.index[-1]}")
            
            if week_idx < 3:  # Debug first few weeks
                print(f"DEBUG: Week {week_idx + 1} ({monday}): {len(rankings)} stocks with valid data")
            
            if not rankings:
                if week_idx < 3:
                    print(f"DEBUG: No rankings for week {week_idx + 1} - all stocks filtered out")
                continue
                
            # Sort by momentum and take top stocks
            rankings.sort(key=lambda x: x[1], reverse=True)
            selected_stocks = rankings[:min(5, len(rankings))]  # Top 5 or fewer
            
            # Track weekly selection for display
            week_selection = {
                'week': f"{monday} to {friday}",
                'date': monday,
                'stocks': [(symbol, momentum) for symbol, momentum in selected_stocks]
            }
            self.weekly_selections.append(week_selection)
            
            if week_idx < 3:  # Debug first few weeks
                symbols_list = [f"{symbol}({momentum:.1f}%)" for symbol, momentum in selected_stocks]
                print(f"DEBUG: Week {week_idx + 1} selected: {', '.join(symbols_list)}")
            
            # Simulate trades for the week
            for symbol, momentum in selected_stocks:
                trade_result = self.simulate_trade(symbol, monday, friday)
                if trade_result:
                    self.trades.append(trade_result)
                    
            # Update portfolio value with dollar P&L from this week's trades
            week_pnl_dollars = sum(trade.get('profit_loss', 0) for trade in self.trades[-len(selected_stocks):])
            portfolio_value += week_pnl_dollars
            equity_values.append({'date': friday, 'equity': portfolio_value})
        
        if progress_callback:
            progress_callback("Calculating results...", 95)
        
        print(f"DEBUG: Backtest completed with {len(self.trades)} total trades")
        
        # Calculate final results
        results = self.calculate_results(equity_values)
        
        if progress_callback:
            progress_callback("Backtest complete!", 100)
            
        return results
    
    def simulate_trade(self, symbol: str, entry_date: str, exit_date: str) -> Optional[Dict]:
        """Simulate a single trade"""
        try:
            data = self.data[symbol]
            
            # Get entry price (Monday open or close)
            entry_data = data[data.index >= entry_date]
            if entry_data.empty:
                return None
            entry_price = entry_data.iloc[0]['Open']
            
            # Get exit price (Friday close)
            exit_data = data[data.index <= exit_date]
            if exit_data.empty:
                return None
            exit_price = exit_data.iloc[-1]['Close']
            
            # Calculate return
            return_pct = ((exit_price - entry_price) / entry_price) * 100
            
            # Apply expected return logic (if return >= target, exit at target)
            if return_pct >= self.config.expected_return_pct:
                return_pct = self.config.expected_return_pct
                
            # Apply stop loss
            if return_pct <= -self.config.stop_loss_pct:
                return_pct = -self.config.stop_loss_pct
            
            return {
                'symbol': symbol,
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'return_pct': return_pct,
                'profit_loss': (return_pct / 100) * self.config.capital_per_trade - self.config.commission_per_trade
            }
            
        except Exception as e:
            print(f"Error simulating trade for {symbol}: {e}")
            return None
    
    def calculate_results(self, equity_values: List[Dict]) -> BacktestResults:
        """Calculate final performance metrics"""
        
        # Convert to DataFrame
        equity_df = pd.DataFrame(equity_values)
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        
        trades_df = pd.DataFrame(self.trades)
        
        if equity_df.empty or len(equity_df) < 2:
            return BacktestResults(0, 0, 0, 0, 0, 0, 0, trades_df, equity_df, [])
        
        # Calculate metrics
        start_value = equity_df.iloc[0]['equity']
        end_value = equity_df.iloc[-1]['equity']
        total_return_pct = ((end_value - start_value) / start_value) * 100
        
        # Annualized return
        days = (equity_df.iloc[-1]['date'] - equity_df.iloc[0]['date']).days
        years = max(days / 365, 0.1)  # Avoid division by zero
        annualized_return = ((end_value / start_value) ** (1/years) - 1) * 100
        
        # Sharpe ratio (simplified)
        if not trades_df.empty and 'return_pct' in trades_df.columns:
            returns = trades_df['return_pct'] / 100
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Max drawdown
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = abs(equity_df['drawdown'].min()) if not equity_df.empty else 0
        
        # Win rate
        if not trades_df.empty and 'return_pct' in trades_df.columns:
            winning_trades = len(trades_df[trades_df['return_pct'] > 0])
            win_rate = (winning_trades / len(trades_df)) * 100
        else:
            win_rate = 0
        
        # Profit factor
        if not trades_df.empty and 'return_pct' in trades_df.columns:
            gross_profit = trades_df[trades_df['return_pct'] > 0]['return_pct'].sum()
            gross_loss = abs(trades_df[trades_df['return_pct'] < 0]['return_pct'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        else:
            profit_factor = 0
        
        return BacktestResults(
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_drawdown,
            win_rate_pct=win_rate,
            total_trades=len(trades_df),
            profit_factor=profit_factor,
            trades_df=trades_df,
            equity_curve=equity_df,
            weekly_selections=self.weekly_selections
        )

# Simple test function
def quick_test():
    """Quick test of the backtest engine"""
    config = BacktestConfig(
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        start_date='2024-06-01',
        end_date='2024-12-31',
        capital_per_trade=10000,
        expected_return_pct=2.0,
        stop_loss_pct=2.0
    )
    
    engine = BacktestEngine(config)
    
    def progress_print(message, percent):
        print(f"[{percent:3d}%] {message}")
    
    try:
        results = engine.run_backtest(progress_print)
        
        print(f"\n{'='*50}")
        print("BACKTEST RESULTS")
        print(f"{'='*50}")
        print(f"Total Return: {results.total_return_pct:.2f}%")
        print(f"Annualized Return: {results.annualized_return_pct:.2f}%")
        print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {results.max_drawdown_pct:.2f}%")
        print(f"Win Rate: {results.win_rate_pct:.1f}%")
        print(f"Total Trades: {results.total_trades}")
        print(f"Profit Factor: {results.profit_factor:.2f}")
        print(f"{'='*50}")
        
    except Exception as e:
        print(f"Backtest failed: {e}")

if __name__ == "__main__":
    quick_test()