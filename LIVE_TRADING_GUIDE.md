# 🚀 Weekly ER Live Trading System - Quick Start Guide

## ⚡ Quick Setup (5 Minutes)

### 1. **Setup IBKR Connection**
```bash
python setup_live_trading.py
```
- Follow interactive prompts
- Test IBKR connection
- Configure trading parameters

### 2. **Start Live Trading**
```bash
# Option A: Use batch file
start_live_trading.bat

# Option B: Direct Python
python ibkr_live_runner.py
```

### 3. **Monitor System**
```bash
# Option A: Use batch file  
monitor_system.bat

# Option B: Direct Python
python system_monitor.py
```

---

## 🔧 IBKR TWS/Gateway Setup

### Required IBKR Settings:
1. Open **Trader Workstation** or **Gateway**
2. **File** → **Global Configuration** → **API** → **Settings**
3. ✅ Enable "**Enable ActiveX and Socket Clients**"
4. ✅ Set **Socket port**: `7497` (Paper) or `7496` (Live)
5. ✅ Add **Trusted IP**: `127.0.0.1`
6. ❌ Uncheck "**Read-Only API**"
7. Click **OK** and **restart TWS/Gateway**

---

## 📅 Trading Schedule

| Time (NY) | Action | Description |
|-----------|--------|-------------|
| **Monday 11:30 AM** | 📈 Entry | System places long positions |
| **Mon-Fri 9:30-4:00 PM** | 👁️ Monitor | Continuous position monitoring |
| **Friday 3:55 PM** | 📉 Exit | **ALL positions closed automatically** |

---

## 🛠️ System Files

### **Core Files:**
- `ibkr_live_runner.py` - Main live trading engine
- `config.json` - Trading configuration
- `tickers.csv` - Universe of tradable stocks

### **Setup & Monitoring:**
- `setup_live_trading.py` - Interactive setup & connection test
- `system_monitor.py` - Real-time system monitoring
- `start_live_trading.bat` - Easy launch script
- `monitor_system.bat` - Easy monitoring script

### **Logs Directory:**
- `logs/trade_journal.csv` - All executed trades
- `logs/events_log.csv` - System events & alerts
- `logs/live_trading.log` - Detailed system log

---

## ✅ Pre-Flight Checklist

Before starting live trading, verify:

- [ ] **IBKR TWS/Gateway is running**
- [ ] **API settings are configured correctly**
- [ ] **Connection test passes** (`setup_live_trading.py`)
- [ ] **Trading parameters are set** in `config.json`
- [ ] **Sufficient account balance** for position sizes
- [ ] **Market is open** (Monday-Friday 9:30-4:00 PM NY)

---

## 🚨 Emergency Procedures

### **Stop All Trading:**
1. Press **Ctrl+C** in the terminal running `ibkr_live_runner.py`
2. Or close the command window
3. System will attempt graceful shutdown

### **Manual Position Close:**
1. Open IBKR TWS
2. Go to **Portfolio** → **Positions**
3. Right-click position → **Close Position**

### **Check System Status:**
Run `python system_monitor.py` to see:
- Active positions
- Recent trades
- Connection status
- System health

---

## ⚙️ Configuration

### **Key Settings in `config.json`:**

```json
{
  "capital_per_trade": 10000,    // USD per position
  "max_positions": 10,           // Max concurrent positions
  "expected_return_pct": 0.02,   // 2% target return
  "stop_loss_pct": 0.015,        // 1.5% stop loss
  "ib_host": "127.0.0.1",       // IBKR host
  "ib_port": 7497,              // IBKR port (7497=Paper, 7496=Live)
  "ib_client_id": 7             // Unique client ID
}
```

### **Trading Universe:**
Edit `tickers.csv` to change which stocks the system trades.

---

## 📊 Monitoring & Logs

### **Real-Time Status:**
```bash
python system_monitor.py
# Shows: connections, positions, recent trades, system health
```

### **Log Files:**
- **`trade_journal.csv`** - Every buy/sell with timestamps
- **`events_log.csv`** - System events (stops hit, errors, etc.)
- **`live_trading.log`** - Detailed technical log

### **Status Indicators:**
- 🟢 **HEALTHY** - System running, connected, trading
- 🟡 **MONITORING** - System running but no recent trades
- 🔴 **OFFLINE** - System not running or disconnected

---

## 🔧 Troubleshooting

### **Common Issues:**

#### "Connection refused" Error:
- Verify TWS/Gateway is running
- Check API settings are enabled
- Try different client ID (8, 9, 10...)

#### "No trades executed":
- Check market is open (Mon-Fri 9:30-4:00 PM NY)
- Verify sufficient account balance
- Check stock filters in config.json

#### "Friday close didn't execute":
- System must run continuously through Friday
- Check system was running at 3:55 PM NY time
- Review `events_log.csv` for errors

### **Get Help:**
1. Check `logs/live_trading.log` for detailed errors
2. Run `python system_monitor.py` for system status
3. Test connection with `python setup_live_trading.py`

---

## 📈 Expected Behavior

### **Monday Morning:**
1. System analyzes stock universe
2. Selects top momentum stocks
3. Places buy orders around 11:30 AM NY
4. Sets stop-loss orders for each position

### **During the Week:**
1. Monitors positions continuously
2. Adjusts stops based on price movement
3. Takes profits at target returns
4. Logs all activity

### **Friday Afternoon:**
1. **Exactly at 3:55 PM NY time**
2. **Cancels all stop orders**
3. **Places market sell orders for ALL positions**
4. **Logs all closing trades**
5. **System ready for next Monday**

---

## 💡 Tips for Success

1. **Start with Paper Trading** (port 7497) to verify system works
2. **Monitor closely** the first few weeks
3. **Keep TWS/Gateway running** during market hours
4. **Review logs daily** to understand system behavior
5. **Have manual override plan** ready if needed

---

## ⚠️ Risk Disclaimers

- **This system trades real money** when connected to live account
- **Always test thoroughly** with paper trading first
- **Monitor positions actively** - automation is not perfect
- **Have stop-loss mechanisms** in place
- **Be prepared for losses** - this is not guaranteed profit
- **Past performance does not guarantee future results**

---

*🤖 System created for educational purposes. Trade at your own risk.*