"""
Main orchestrator for Weekly Stocks project.
Coordinates data fetching, processing, and report generation.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
import colorlog

from .config import config
from .data import StockDataFetcher
from .report import ReportGenerator

def setup_logging():
    """Set up logging configuration with colors and file output."""
    
    # Ensure logs directory exists
    config.ensure_directories()
    
    # Create formatters
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))
    
    # Console handler
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    log_file = config.logs_dir / 'app.log'
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from external libraries
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def print_banner():
    """Print application banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                     📊 Weekly Stocks                         ║
    ║                  Stock Data Analysis Tool                    ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def validate_configuration():
    """Validate configuration and exit if issues found."""
    logger = logging.getLogger(__name__)
    
    issues = config.validate()
    if issues:
        logger.error("Configuration validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        sys.exit(1)
    
    logger.info("Configuration validation passed")

def print_configuration_summary():
    """Print summary of current configuration."""
    logger = logging.getLogger(__name__)
    
    logger.info("Configuration Summary:")
    logger.info(f"  Tickers: {', '.join(config.tickers[:5])}{'...' if len(config.tickers) > 5 else ''} ({len(config.tickers)} total)")
    logger.info(f"  Date Range: {config.start_date} to {config.end_date}")
    logger.info(f"  Output Directory: {config.today_output_dir}")
    logger.info(f"  Log Level: {config.log_level}")
    logger.info(f"  Max Retries: {config.max_retries}")

def main():
    """Main application entry point."""
    
    # Print banner
    print_banner()
    
    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting Weekly Stocks analysis...")
        start_time = datetime.now()
        
        # Validate configuration
        validate_configuration()
        
        # Print configuration summary
        print_configuration_summary()
        
        # Ensure output directories exist
        config.ensure_directories()
        
        # Initialize components
        logger.info("Initializing data fetcher and report generator...")
        data_fetcher = StockDataFetcher()
        report_generator = ReportGenerator()
        
        # Fetch stock data
        logger.info("=" * 60)
        logger.info("PHASE 1: Fetching stock data")
        logger.info("=" * 60)
        
        weekly_data, status = data_fetcher.fetch_all_data()
        
        if weekly_data.empty:
            logger.error("No data was successfully fetched. Exiting.")
            sys.exit(1)
        
        # Calculate summary statistics
        logger.info("=" * 60)
        logger.info("PHASE 2: Calculating summary statistics")
        logger.info("=" * 60)
        
        summary_stats = data_fetcher.get_summary_stats(weekly_data)
        
        if not summary_stats.empty:
            logger.info(f"Calculated statistics for {len(summary_stats)} stocks")
            
            # Log top performers
            top_3 = summary_stats.head(3)
            logger.info("Top 3 performers:")
            for i, row in top_3.iterrows():
                logger.info(f"  {i+1}. {row['Ticker']}: {row['Total_Return_Pct']:.2f}%")
        
        # Generate reports
        logger.info("=" * 60)
        logger.info("PHASE 3: Generating reports")
        logger.info("=" * 60)
        
        report_files = report_generator.generate_all_reports(weekly_data, summary_stats, status)
        
        # Print summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("=" * 60)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Duration: {duration.total_seconds():.1f} seconds")
        logger.info(f"Stocks processed: {status['total_successful']}/{status['total_requested']}")
        logger.info(f"Output directory: {config.today_output_dir}")
        logger.info("Generated files:")
        
        for file_type, file_path in report_files.items():
            logger.info(f"  - {file_type}: {file_path.name}")
        
        # Print text summary to console
        if not summary_stats.empty:
            print("\n" + "=" * 60)
            print("QUICK SUMMARY")
            print("=" * 60)
            summary_text = report_generator.create_summary_text(summary_stats, status)
            print(summary_text)
        
        logger.info("Weekly Stocks analysis completed successfully!")
        
    except KeyboardInterrupt:
        logger.warning("Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
