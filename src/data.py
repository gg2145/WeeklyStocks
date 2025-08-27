"""
Data fetching module for Weekly Stocks project.
Handles stock data retrieval with retry logic and error handling.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
import pandas as pd
import yfinance as yf
from requests.exceptions import RequestException

from .config import config

logger = logging.getLogger(__name__)

class StockDataFetcher:
    """Handles fetching and processing stock data."""
    
    def __init__(self):
        self.failed_tickers = []
        self.successful_tickers = []
    
    def fetch_ticker_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single ticker with retry logic.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            DataFrame with stock data or None if failed
        """
        for attempt in range(config.max_retries + 1):
            try:
                logger.debug(f"Fetching data for {ticker} (attempt {attempt + 1})")
                
                # Create yfinance ticker object
                stock = yf.Ticker(ticker)
                
                # Fetch historical data
                data = stock.history(
                    start=config.start_date,
                    end=config.end_date,
                    interval='1d',
                    auto_adjust=True,
                    prepost=True
                )
                
                if data.empty:
                    logger.warning(f"No data returned for {ticker}")
                    return None
                
                # Add ticker column
                data['Ticker'] = ticker
                
                # Reset index to make Date a column
                data = data.reset_index()
                
                logger.debug(f"Successfully fetched {len(data)} rows for {ticker}")
                return data
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {ticker}: {str(e)}")
                
                if attempt < config.max_retries:
                    time.sleep(config.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"All attempts failed for {ticker}")
                    return None
        
        return None
    
    def resample_to_weekly(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Resample daily data to weekly (Friday close).
        
        Args:
            data: Daily stock data DataFrame
            
        Returns:
            Weekly resampled DataFrame
        """
        if data.empty:
            return data
        
        # Ensure Date column is datetime
        data['Date'] = pd.to_datetime(data['Date'])
        
        # Set Date as index for resampling
        data_indexed = data.set_index('Date')
        
        # Resample to weekly (Friday close)
        weekly_data = data_indexed.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum',
            'Ticker': 'first'
        }).dropna()
        
        # Reset index to make Date a column again
        weekly_data = weekly_data.reset_index()
        
        # Calculate weekly return
        weekly_data['Weekly_Return'] = weekly_data['Close'].pct_change() * 100
        
        # Calculate price change
        weekly_data['Price_Change'] = weekly_data['Close'] - weekly_data['Open']
        weekly_data['Price_Change_Pct'] = (weekly_data['Price_Change'] / weekly_data['Open']) * 100
        
        return weekly_data
    
    def fetch_all_data(self) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
        """
        Fetch data for all configured tickers.
        
        Returns:
            Tuple of (combined_data_df, status_dict)
        """
        logger.info(f"Starting data fetch for {len(config.tickers)} tickers")
        
        all_data = []
        self.failed_tickers = []
        self.successful_tickers = []
        
        for i, ticker in enumerate(config.tickers, 1):
            logger.info(f"Processing {ticker} ({i}/{len(config.tickers)})")
            
            # Fetch raw data
            raw_data = self.fetch_ticker_data(ticker)
            
            if raw_data is not None:
                # Resample to weekly
                weekly_data = self.resample_to_weekly(raw_data)
                
                if not weekly_data.empty:
                    all_data.append(weekly_data)
                    self.successful_tickers.append(ticker)
                    logger.info(f"✓ {ticker}: {len(weekly_data)} weeks of data")
                else:
                    self.failed_tickers.append(ticker)
                    logger.warning(f"✗ {ticker}: No weekly data after resampling")
            else:
                self.failed_tickers.append(ticker)
                logger.error(f"✗ {ticker}: Failed to fetch data")
        
        # Combine all data
        if all_data:
            combined_data = pd.concat(all_data, ignore_index=True)
            combined_data = combined_data.sort_values(['Date', 'Ticker']).reset_index(drop=True)
        else:
            combined_data = pd.DataFrame()
        
        # Create status summary
        status = {
            'successful': self.successful_tickers,
            'failed': self.failed_tickers,
            'total_requested': len(config.tickers),
            'total_successful': len(self.successful_tickers),
            'total_failed': len(self.failed_tickers)
        }
        
        logger.info(f"Data fetch complete: {status['total_successful']}/{status['total_requested']} successful")
        
        return combined_data, status
    
    def get_summary_stats(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate summary statistics for each ticker.
        
        Args:
            data: Weekly stock data DataFrame
            
        Returns:
            Summary statistics DataFrame
        """
        if data.empty:
            return pd.DataFrame()
        
        summary_stats = []
        
        for ticker in data['Ticker'].unique():
            ticker_data = data[data['Ticker'] == ticker].copy()
            
            if ticker_data.empty:
                continue
            
            # Calculate statistics
            latest_price = ticker_data['Close'].iloc[-1]
            first_price = ticker_data['Close'].iloc[0]
            total_return = ((latest_price - first_price) / first_price) * 100
            
            stats = {
                'Ticker': ticker,
                'Weeks_of_Data': len(ticker_data),
                'First_Date': ticker_data['Date'].min().strftime('%Y-%m-%d'),
                'Last_Date': ticker_data['Date'].max().strftime('%Y-%m-%d'),
                'First_Price': round(first_price, 2),
                'Latest_Price': round(latest_price, 2),
                'Total_Return_Pct': round(total_return, 2),
                'Avg_Weekly_Return_Pct': round(ticker_data['Weekly_Return'].mean(), 2),
                'Weekly_Volatility_Pct': round(ticker_data['Weekly_Return'].std(), 2),
                'Max_Weekly_Gain_Pct': round(ticker_data['Weekly_Return'].max(), 2),
                'Max_Weekly_Loss_Pct': round(ticker_data['Weekly_Return'].min(), 2),
                'Avg_Volume': int(ticker_data['Volume'].mean())
            }
            
            summary_stats.append(stats)
        
        summary_df = pd.DataFrame(summary_stats)
        summary_df = summary_df.sort_values('Total_Return_Pct', ascending=False).reset_index(drop=True)
        
        return summary_df
