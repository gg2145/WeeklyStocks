#!/usr/bin/env python3
"""
Enhanced Live Trading Runner with Connection Monitoring and Position Safety
Integrates the new robustness features with the existing Weekly ER Trading System
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import existing system components
from ibkr_live_runner import WeeklyERTrader, Journal
from backtest_core import BacktestConfig
from pending_sales import pending_tracker
from options_protection import OptionsProtectionManager

# Import new safety components
from connection_monitor import RobustIBConnection, ConnectionConfig, AlertConfig
from position_safety import PositionSafetyManager, SafetyLimits, run_safety_monitor

LOG = logging.getLogger(__name__)

class EnhancedWeeklyERTrader:
    """Enhanced version of the Weekly ER Trader with robust connection and safety monitoring"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        
        # Initialize core trader
        self.core_trader = WeeklyERTrader(config_file)
        
        # Initialize connection monitoring
        self.connection_config = ConnectionConfig(
            host=self.config.get("ib_host", "127.0.0.1"),
            port=int(self.config.get("ib_port", 7497)),
            client_id=int(self.config.get("ib_client_id", 7)),
            heartbeat_interval=30,
            max_reconnect_attempts=5,
            reconnect_delay=10
        )
        
        # Initialize alert configuration
        self.alert_config = AlertConfig(
            email_enabled=self.config.get("alerts", {}).get("email_enabled", False),
            email_user=self.config.get("alerts", {}).get("email_user", ""),
            email_password=self.config.get("alerts", {}).get("email_password", ""),
            alert_recipients=self.config.get("alerts", {}).get("recipients", [])
        )
        
        # Initialize safety limits
        safety_config = self.config.get("safety_limits", {})
        self.safety_limits = SafetyLimits(
            max_position_value=safety_config.get("max_position_value", 50000),
            max_portfolio_value=safety_config.get("max_portfolio_value", 500000),
            max_daily_loss=safety_config.get("max_daily_loss", 10000),
            max_position_concentration=safety_config.get("max_position_concentration", 0.15),
            emergency_stop_loss=safety_config.get("emergency_stop_loss", 0.10)
        )
        
        # Initialize safety manager
        self.safety_manager = PositionSafetyManager(self.safety_limits)
        
        # Initialize options protection
        self.options_protection = OptionsProtectionManager(self.core_trader.config)
        
        # State tracking
        self.is_running = False
        self.safety_monitoring_task = None
        self.trading_paused = False
        self.last_safety_check = None
        
        # Journal for enhanced logging
        self.journal = Journal()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            LOG.error(f"Failed to load config: {e}")
            return {}
    
    async def run_enhanced_trading_system(self):
        """Run the enhanced trading system with all safety features"""
        LOG.info("Starting Enhanced Weekly ER Trading System")
        
        # Connection callbacks
        async def on_connected(ib):
            LOG.info("Trading system connected - initializing components")
            await self._initialize_trading_components(ib)
            
        async def on_disconnected():
            LOG.warning("Connection lost - pausing trading operations")
            self.trading_paused = True
            await self._pause_trading_operations()
            
        async def on_reconnected(ib):
            LOG.info("Connection restored - resuming trading operations")
            self.trading_paused = False
            await self._resume_trading_operations(ib)
        
        # Use robust connection with monitoring
        try:
            async with RobustIBConnection(self.connection_config, self.alert_config) as ib:
                # Set up connection callbacks
                robust_conn = RobustIBConnection(self.connection_config, self.alert_config)
                robust_conn.monitor.set_callbacks(
                    on_connected=on_connected,
                    on_disconnected=on_disconnected,
                    on_reconnected=on_reconnected
                )
                
                # Start safety monitoring
                self.safety_monitoring_task = asyncio.create_task(
                    run_safety_monitor(ib, check_interval=300)  # Check every 5 minutes
                )
                
                # Run main trading loop
                await self._main_trading_loop(ib)
                
        except Exception as e:
            LOG.error(f"Enhanced trading system error: {e}")
            await self._emergency_shutdown()
        finally:
            if self.safety_monitoring_task:
                self.safety_monitoring_task.cancel()
    
    async def _initialize_trading_components(self, ib):
        """Initialize trading components after connection"""
        try:
            # Initialize core trader with IB connection
            self.core_trader.ib = ib
            
            # Perform initial safety check
            safety_report = await self.safety_manager.perform_safety_check(ib)
            if safety_report.get("violations"):
                LOG.warning(f"Initial safety violations detected: {len(safety_report['violations'])}")
                for violation in safety_report["violations"]:
                    LOG.warning(f"  {violation['severity']}: {violation['message']}")
            
            # Log system status
            self.journal.log_event("system_initialized", {
                "connection_healthy": True,
                "safety_violations": len(safety_report.get("violations", [])),
                "portfolio_value": safety_report.get("portfolio_risk", {}).get("total_value", 0)
            })
            
            LOG.info("Trading components initialized successfully")
            
        except Exception as e:
            LOG.error(f"Failed to initialize trading components: {e}")
            raise
    
    async def _main_trading_loop(self, ib):
        """Main trading loop with enhanced safety monitoring"""
        self.is_running = True
        
        while self.is_running:
            try:
                if not self.trading_paused and ib.isConnected():
                    # Perform safety check before trading operations
                    safety_ok = await self._pre_trading_safety_check(ib)
                    
                    if safety_ok:
                        # Run core trading logic
                        await self._execute_trading_cycle(ib)
                    else:
                        LOG.warning("Trading paused due to safety concerns")
                        await asyncio.sleep(300)  # Wait 5 minutes before retry
                else:
                    LOG.info("Trading paused - waiting for connection/safety clearance")
                    await asyncio.sleep(60)
                
                # Regular interval between trading cycles
                await asyncio.sleep(300)  # 5 minutes between cycles
                
            except KeyboardInterrupt:
                LOG.info("Shutdown requested by user")
                break
            except Exception as e:
                LOG.error(f"Error in main trading loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
        
        LOG.info("Main trading loop stopped")
    
    async def _pre_trading_safety_check(self, ib) -> bool:
        """Perform safety check before trading operations"""
        try:
            safety_report = await self.safety_manager.perform_safety_check(ib)
            
            if "error" in safety_report:
                LOG.error(f"Safety check failed: {safety_report['error']}")
                return False
            
            violations = safety_report.get("violations", [])
            critical_violations = [v for v in violations if v["severity"] == "CRITICAL"]
            
            if critical_violations:
                LOG.critical(f"CRITICAL safety violations - trading halted: {len(critical_violations)}")
                
                # Execute emergency actions
                await self.safety_manager.execute_emergency_actions(ib, critical_violations)
                
                # Log emergency action
                self.journal.log_event("emergency_action", {
                    "violations": critical_violations,
                    "timestamp": datetime.now().isoformat()
                })
                
                return False
            
            # Log safety status
            if violations:
                LOG.warning(f"Non-critical safety violations: {len(violations)}")
                for violation in violations:
                    LOG.warning(f"  {violation['severity']}: {violation['message']}")
            
            self.last_safety_check = datetime.now()
            return True
            
        except Exception as e:
            LOG.error(f"Safety check error: {e}")
            return False
    
    async def _execute_trading_cycle(self, ib):
        """Execute one trading cycle with enhanced monitoring"""
        try:
            # Get current market state
            current_time = datetime.now()
            
            # Check if it's a trading day and time
            if not self._is_trading_time(current_time):
                LOG.debug("Outside trading hours - skipping cycle")
                return
            
            # Monday: Entry logic
            if current_time.weekday() == 0:  # Monday
                await self._monday_entry_logic(ib)
            
            # Tuesday-Thursday: Monitoring
            elif current_time.weekday() in [1, 2, 3]:
                await self._midweek_monitoring(ib)
            
            # Friday: Exit logic
            elif current_time.weekday() == 4:  # Friday
                await self._friday_exit_logic(ib)
            
        except Exception as e:
            LOG.error(f"Error in trading cycle: {e}")
            self.journal.log_event("trading_cycle_error", {
                "error": str(e),
                "timestamp": current_time.isoformat()
            })
    
    async def _monday_entry_logic(self, ib):
        """Enhanced Monday entry logic with safety checks"""
        LOG.info("Executing Monday entry logic")
        
        try:
            # Pre-entry safety check
            safety_report = await self.safety_manager.perform_safety_check(ib)
            portfolio_risk = safety_report.get("portfolio_risk")
            
            if portfolio_risk:
                # Check if we have room for new positions
                current_positions = portfolio_risk.position_count
                max_positions = self.safety_limits.max_positions
                
                if current_positions >= max_positions:
                    LOG.warning(f"Maximum positions reached ({current_positions}/{max_positions}) - skipping entries")
                    return
                
                # Check portfolio value limits
                if portfolio_risk.total_value > self.safety_limits.max_portfolio_value * 0.9:
                    LOG.warning("Portfolio near maximum value - reducing entry size")
            
            # Use core trader's entry logic
            await self.core_trader.monday_entry_logic()
            
            # Post-entry safety check and options protection
            await self._post_entry_actions(ib)
            
        except Exception as e:
            LOG.error(f"Monday entry logic error: {e}")
            self.journal.log_event("monday_entry_error", {"error": str(e)})
    
    async def _post_entry_actions(self, ib):
        """Actions to take after entering new positions"""
        try:
            # Get current positions
            portfolio = ib.portfolio()
            positions = {
                item.contract.symbol: {
                    'current_price': item.marketPrice or item.averageCost,
                    'quantity': int(item.position)
                }
                for item in portfolio if item.position > 0
            }
            
            if positions:
                # Calculate portfolio value for options protection
                portfolio_value = sum(
                    pos['current_price'] * pos['quantity'] 
                    for pos in positions.values()
                )
                
                # Implement options protection for high-risk positions
                if portfolio_value > 100000:  # Only for larger portfolios
                    LOG.info("Implementing options protection for new positions")
                    protection_results = await self.options_protection.implement_comprehensive_protection(
                        ib, positions, portfolio_value
                    )
                    
                    if protection_results:
                        self.journal.log_event("options_protection_implemented", {
                            "protected_positions": protection_results.get("individual_protection", {}),
                            "total_cost": protection_results.get("total_protection_cost", 0)
                        })
            
        except Exception as e:
            LOG.error(f"Post-entry actions error: {e}")
    
    async def _midweek_monitoring(self, ib):
        """Enhanced midweek monitoring with continuous safety checks"""
        LOG.debug("Executing midweek monitoring")
        
        try:
            # Monitor existing positions
            await self.core_trader.monitor_positions()
            
            # Check for options protection adjustments
            if hasattr(self.options_protection, 'monitor_all_protection'):
                monitoring_results = await self.options_protection.monitor_all_protection(ib)
                
                if monitoring_results.get("adjustments_made", 0) > 0:
                    LOG.info(f"Options protection adjustments made: {monitoring_results['adjustments_made']}")
                    self.journal.log_event("options_adjustments", monitoring_results)
            
            # Update pending sales tracking
            await self._update_pending_sales_tracking(ib)
            
        except Exception as e:
            LOG.error(f"Midweek monitoring error: {e}")
    
    async def _friday_exit_logic(self, ib):
        """Enhanced Friday exit logic with safety verification"""
        LOG.info("Executing Friday exit logic")
        
        try:
            current_time = datetime.now()
            
            # Check if it's close to market close (3:55 PM ET)
            if current_time.hour >= 15 and current_time.minute >= 55:
                LOG.info("Market close approaching - executing emergency close")
                
                # Use safety manager's emergency close functionality
                result = await self.safety_manager._emergency_close_all_positions(ib)
                
                if result.get("success"):
                    LOG.info(f"Emergency close completed: {len(result.get('closed_positions', []))} positions closed")
                    self.journal.log_event("friday_emergency_close", result)
                else:
                    LOG.error(f"Emergency close failed: {result.get('error')}")
            else:
                # Use core trader's normal Friday logic
                await self.core_trader.friday_exit_logic()
            
            # Clear pending sales after Friday close
            pending_tracker.clear_all_pending_sales()
            
        except Exception as e:
            LOG.error(f"Friday exit logic error: {e}")
            self.journal.log_event("friday_exit_error", {"error": str(e)})
    
    async def _update_pending_sales_tracking(self, ib):
        """Update pending sales tracking with current orders"""
        try:
            open_orders = ib.openOrders()
            
            for order in open_orders:
                symbol = order.contract.symbol
                action = order.action
                quantity = order.totalQuantity
                
                # Update pending tracker
                if action == "SELL" and not pending_tracker.is_pending_sale(symbol):
                    pending_tracker.mark_as_pending_sale(symbol, quantity, "MARKET", 
                                                       notes=f"Auto-tracked from open orders")
                elif action == "BUY" and not pending_tracker.is_pending_buy(symbol):
                    pending_tracker.mark_as_pending_buy(symbol, quantity, "MARKET",
                                                      notes=f"Auto-tracked from open orders")
            
        except Exception as e:
            LOG.error(f"Error updating pending sales tracking: {e}")
    
    async def _pause_trading_operations(self):
        """Pause trading operations during connection issues"""
        LOG.warning("Pausing trading operations")
        self.trading_paused = True
        
        # Log the pause
        self.journal.log_event("trading_paused", {
            "reason": "connection_lost",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _resume_trading_operations(self, ib):
        """Resume trading operations after connection restoration"""
        LOG.info("Resuming trading operations")
        
        try:
            # Perform safety check before resuming
            safety_report = await self.safety_manager.perform_safety_check(ib)
            
            if not safety_report.get("violations"):
                self.trading_paused = False
                LOG.info("Trading operations resumed successfully")
                
                self.journal.log_event("trading_resumed", {
                    "timestamp": datetime.now().isoformat(),
                    "portfolio_value": safety_report.get("portfolio_risk", {}).get("total_value", 0)
                })
            else:
                LOG.warning("Safety violations detected - keeping trading paused")
                
        except Exception as e:
            LOG.error(f"Error resuming trading operations: {e}")
    
    async def _emergency_shutdown(self):
        """Emergency shutdown procedure"""
        LOG.critical("Executing emergency shutdown")
        
        try:
            self.is_running = False
            
            # Cancel safety monitoring
            if self.safety_monitoring_task:
                self.safety_monitoring_task.cancel()
            
            # Log emergency shutdown
            self.journal.log_event("emergency_shutdown", {
                "timestamp": datetime.now().isoformat(),
                "reason": "system_error"
            })
            
            LOG.critical("Emergency shutdown completed")
            
        except Exception as e:
            LOG.error(f"Error during emergency shutdown: {e}")
    
    def _is_trading_time(self, current_time: datetime) -> bool:
        """Check if current time is within trading hours"""
        # Simplified trading hours check (9:30 AM - 4:00 PM ET)
        hour = current_time.hour
        return 9 <= hour <= 16 and current_time.weekday() < 5
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            status = {
                "timestamp": datetime.now().isoformat(),
                "is_running": self.is_running,
                "trading_paused": self.trading_paused,
                "last_safety_check": self.last_safety_check.isoformat() if self.last_safety_check else None,
                "safety_limits": {
                    "max_position_value": self.safety_limits.max_position_value,
                    "max_daily_loss": self.safety_limits.max_daily_loss,
                    "emergency_stop_loss": self.safety_limits.emergency_stop_loss
                },
                "connection_config": {
                    "host": self.connection_config.host,
                    "port": self.connection_config.port,
                    "heartbeat_interval": self.connection_config.heartbeat_interval
                },
                "alerts_enabled": self.alert_config.email_enabled
            }
            
            return status
            
        except Exception as e:
            LOG.error(f"Error getting system status: {e}")
            return {"error": str(e)}

async def main():
    """Main function to run the enhanced trading system"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/enhanced_trading.log'),
            logging.StreamHandler()
        ]
    )
    
    LOG.info("Starting Enhanced Weekly ER Trading System")
    
    try:
        # Create enhanced trader
        enhanced_trader = EnhancedWeeklyERTrader()
        
        # Run the enhanced system
        await enhanced_trader.run_enhanced_trading_system()
        
    except KeyboardInterrupt:
        LOG.info("System shutdown requested by user")
    except Exception as e:
        LOG.error(f"System error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        LOG.info("Enhanced trading system shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
