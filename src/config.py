"""
Configuration module for Weekly Stocks project.
Loads settings from environment variables with sensible defaults.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class with environment variable support."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        
    @property
    def tickers(self) -> List[str]:
        """Get list of stock tickers from environment or default."""
        tickers_str = os.getenv('TICKERS', 'AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA,NFLX,CRM,ADBE')
        return [ticker.strip().upper() for ticker in tickers_str.split(',') if ticker.strip()]
    
    @property
    def start_date(self) -> str:
        """Get start date for data fetching."""
        env_date = os.getenv('START_DATE', '').strip()
        if env_date:
            return env_date
        
        # Default to 3 months ago
        three_months_ago = datetime.now() - timedelta(days=90)
        return three_months_ago.strftime('%Y-%m-%d')
    
    @property
    def end_date(self) -> str:
        """Get end date for data fetching (today)."""
        return datetime.now().strftime('%Y-%m-%d')
    
    @property
    def output_dir(self) -> Path:
        """Get output directory path."""
        output_dir_str = os.getenv('OUTPUT_DIR', 'output')
        return self.project_root / output_dir_str
    
    @property
    def logs_dir(self) -> Path:
        """Get logs directory path."""
        return self.project_root / 'logs'
    
    @property
    def log_level(self) -> str:
        """Get logging level."""
        return os.getenv('LOG_LEVEL', 'INFO').upper()
    
    @property
    def max_retries(self) -> int:
        """Get maximum number of retries for API calls."""
        try:
            return int(os.getenv('MAX_RETRIES', '3'))
        except ValueError:
            return 3
    
    @property
    def retry_delay(self) -> float:
        """Get delay between retries in seconds."""
        try:
            return float(os.getenv('RETRY_DELAY', '1.0'))
        except ValueError:
            return 1.0
    
    @property
    def today_output_dir(self) -> Path:
        """Get today's output directory."""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.output_dir / today
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.today_output_dir.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        if not self.tickers:
            issues.append("No tickers specified")
        
        try:
            datetime.strptime(self.start_date, '%Y-%m-%d')
        except ValueError:
            issues.append(f"Invalid start_date format: {self.start_date}")
        
        if self.max_retries < 0:
            issues.append("max_retries must be non-negative")
        
        if self.retry_delay < 0:
            issues.append("retry_delay must be non-negative")
        
        return issues

# Global configuration instance
config = Config()
