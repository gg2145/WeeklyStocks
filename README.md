# 📊 Weekly Stocks

A clean, simple Python application for fetching weekly stock data and generating comprehensive reports.

## 🎯 Features

- **Weekly Data Analysis**: Fetches and analyzes weekly stock data (Friday close)
- **Multiple Output Formats**: Generates CSV, HTML, and text summary reports
- **Robust Data Fetching**: Retry logic with exponential backoff for reliable data retrieval
- **Configurable**: Environment-based configuration with sensible defaults
- **Windows-Friendly**: PowerShell scripts for easy setup and execution
- **Professional Reports**: Beautiful HTML reports with performance metrics
- **Error Handling**: Graceful failure handling - continues with other stocks if one fails

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** installed and added to PATH
- **PowerShell** (included with Windows)
- **Internet connection** for fetching stock data

### Installation

1. **Clone or download** this repository
2. **Open PowerShell** in the project directory
3. **Run the setup script**:
   ```powershell
   .\scripts\dev-setup.ps1
   ```

### First Run

```powershell
# Run with default settings
.\scripts\run.ps1

# Run with setup and open report automatically
.\scripts\run.ps1 -Setup -OpenReport

# Run with custom tickers
.\scripts\run.ps1 -Tickers "TSLA,NVDA,AMD,PLTR,ROKU"
```

## 📁 Project Structure

```
WeeklyStocks/
├── .env.example          # Configuration template
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── requirements.txt      # Python dependencies
├── src/
│   ├── config.py        # Configuration management
│   ├── data.py          # Data fetching with retry logic
│   ├── report.py        # Report generation
│   └── main.py          # Main application orchestrator
├── scripts/
│   ├── dev-setup.ps1    # Development environment setup
│   └── run.ps1          # Application runner
├── templates/
│   └── report.html      # HTML report template
├── output/              # Generated reports (by date)
│   └── YYYY-MM-DD/
│       ├── weekly_data.csv
│       ├── summary_stats.csv
│       ├── weekly_stocks_report.html
│       └── summary.txt
└── logs/
    └── app.log          # Application logs
```

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
# Stock tickers to analyze (comma-separated)
TICKERS=AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA,NFLX,CRM,ADBE

# Start date for analysis (leave empty for 3 months ago)
START_DATE=2024-01-01

# Output directory
OUTPUT_DIR=output

# Logging level
LOG_LEVEL=INFO

# API retry settings
MAX_RETRIES=3
RETRY_DELAY=1
```

### Default Tickers

The application comes with a curated list of popular stocks:
- **Tech Giants**: AAPL, MSFT, GOOGL, AMZN, META, NVDA
- **Growth Stocks**: TSLA, NFLX, CRM, ADBE

## 🔧 Usage

### Basic Commands

```powershell
# Show help
.\scripts\run.ps1 -Help

# Run with default settings
.\scripts\run.ps1

# First-time setup and run
.\scripts\run.ps1 -Setup

# Run and open HTML report
.\scripts\run.ps1 -OpenReport

# Custom log level
.\scripts\run.ps1 -LogLevel DEBUG

# Override tickers for one run
.\scripts\run.ps1 -Tickers "AAPL,MSFT,GOOGL"

# Combine options
.\scripts\run.ps1 -Setup -OpenReport -LogLevel INFO
```

### Manual Python Execution

If you prefer to run Python directly:

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run the application
python -m src.main

# Deactivate when done
deactivate
```

## 📊 Output Files

Each run creates a date-stamped directory in `output/` with:

### 1. CSV Files
- **`weekly_data.csv`**: Raw weekly data for all stocks
- **`summary_stats.csv`**: Performance statistics per stock

### 2. HTML Report
- **`weekly_stocks_report.html`**: Interactive report with:
  - Performance summary cards
  - Sortable data tables
  - Color-coded returns (green/red)
  - Links to Yahoo Finance for each stock

### 3. Text Summary
- **`summary.txt`**: Quick text overview with top/bottom performers

## 🔍 Data Analysis

### Weekly Resampling
- Uses **Friday close** prices for weekly data points
- Calculates weekly returns, volatility, and performance metrics
- Handles missing data gracefully

### Performance Metrics
- **Total Return**: Overall performance over the analysis period
- **Average Weekly Return**: Mean weekly performance
- **Weekly Volatility**: Standard deviation of weekly returns
- **Max Weekly Gain/Loss**: Best and worst single-week performance
- **Volume Analysis**: Average trading volume

## 🛠️ Troubleshooting

### Common Issues

#### "Python not found"
- Install Python 3.8+ from [python.org](https://python.org)
- Ensure Python is added to your system PATH
- Restart PowerShell after installation

#### "Virtual environment activation failed"
- Run `.\scripts\dev-setup.ps1 -Force` to recreate the environment
- Check that you have write permissions in the project directory

#### "No data returned for ticker"
- Some tickers may be delisted or have different symbols
- Check ticker symbols on [Yahoo Finance](https://finance.yahoo.com)
- The application will continue with other stocks

#### "Network/API errors"
- Check your internet connection
- Yahoo Finance may have temporary outages
- The retry logic will attempt multiple times automatically

### Debug Mode

Run with debug logging for detailed information:

```powershell
.\scripts\run.ps1 -LogLevel DEBUG
```

### Log Files

Check `logs/app.log` for detailed execution logs, including:
- Data fetching progress
- Error messages and stack traces
- Performance timing information

## 🔄 Automation

### Windows Task Scheduler

To run weekly automatically:

1. Open **Task Scheduler**
2. Create **Basic Task**
3. Set trigger to **Weekly** (e.g., Sunday morning)
4. Set action to **Start a program**:
   - **Program**: `powershell.exe`
   - **Arguments**: `-File "C:\path\to\WeeklyStocks\scripts\run.ps1" -OpenReport`
   - **Start in**: `C:\path\to\WeeklyStocks`

### Batch Processing

Create a batch file for regular execution:

```batch
@echo off
cd /d "C:\path\to\WeeklyStocks"
powershell.exe -ExecutionPolicy Bypass -File "scripts\run.ps1" -OpenReport
pause
```

## 🧪 Development

### Adding New Features

1. **Data Sources**: Extend `src/data.py` for additional data providers
2. **Report Formats**: Modify `templates/report.html` or add new templates
3. **Analysis**: Add new metrics in `StockDataFetcher.get_summary_stats()`
4. **Configuration**: Extend `src/config.py` for new settings

### Dependencies

Core dependencies (see `requirements.txt`):
- **pandas**: Data manipulation and analysis
- **yfinance**: Yahoo Finance data fetching
- **jinja2**: HTML template rendering
- **python-dotenv**: Environment variable management
- **colorlog**: Colored console logging

### Testing

```powershell
# Test with a small set of tickers
.\scripts\run.ps1 -Tickers "AAPL,MSFT" -LogLevel DEBUG

# Test with different date ranges
$env:START_DATE="2024-01-01"
.\scripts\run.ps1
```

## 📈 Data Source

- **Primary**: Yahoo Finance via `yfinance` library
- **Update Frequency**: Real-time during market hours
- **Historical Data**: Available back to stock listing date
- **Coverage**: Global stocks, ETFs, indices, cryptocurrencies

## 📄 License

This project is open source. Feel free to modify and distribute according to your needs.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues or questions:
1. Check the **Troubleshooting** section above
2. Review log files in `logs/app.log`
3. Run with `-LogLevel DEBUG` for detailed information
4. Create an issue with your configuration and error details

---

**Happy analyzing! 📊**
