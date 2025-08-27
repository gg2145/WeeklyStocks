#!/usr/bin/env python3
"""
Position Safety Manager for Weekly ER Trading System
Implements comprehensive position safety checks and emergency controls
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, Contract
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

LOG = logging.getLogger(__name__)

@dataclass
class SafetyLimits:
    """Configuration for position safety limits"""
    max_position_value: float = 50000  # Maximum value per position
    max_portfolio_value: float = 500000  # Maximum total portfolio value
    max_daily_loss: float = 10000  # Maximum daily loss
    max_position_concentration: float = 0.15  # Max 15% in any single position
    max_sector_concentration: float = 0.30  # Max 30% in any sector
    max_correlation_exposure: float = 0.50  # Max 50% in highly correlated positions
    emergency_stop_loss: float = 0.10  # Emergency stop at 10% portfolio loss
    max_positions: int = 20  # Maximum number of positions
    min_cash_reserve: float = 10000  # Minimum cash to maintain
    
@dataclass
class PositionRisk:
    """Risk metrics for a single position"""
    symbol: str
    quantity: int
    current_price: float
    market_value: float
    unrealized_pnl: float
    daily_pnl: float
    position_concentration: float
    sector: str = "Unknown"
    beta: float = 1.0
    volatility: float = 0.25
    risk_score: float = 0.0
    
@dataclass
class PortfolioRisk:
    """Risk metrics for entire portfolio"""
    total_value: float
    total_pnl: float
    daily_pnl: float
    cash_balance: float
    position_count: int
    max_position_concentration: float
    sector_concentrations: Dict[str, float]
    correlation_risk: float
    var_95: float  # Value at Risk 95%
    risk_score: float = 0.0

class SectorClassifier:
    """Classifies stocks into sectors for concentration risk analysis"""
    
    def __init__(self):
        # Simplified sector mapping - in production, use proper sector data
        self.sector_map = {
            # Technology
            'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 
            'AMZN': 'Technology', 'META': 'Technology', 'NVDA': 'Technology',
            'TSLA': 'Technology', 'NFLX': 'Technology', 'ADBE': 'Technology',
            
            # Healthcare
            'JNJ': 'Healthcare', 'PFE': 'Healthcare', 'UNH': 'Healthcare',
            'ABBV': 'Healthcare', 'TMO': 'Healthcare', 'DHR': 'Healthcare',
            
            # Financial
            'JPM': 'Financial', 'BAC': 'Financial', 'WFC': 'Financial',
            'GS': 'Financial', 'MS': 'Financial', 'C': 'Financial',
            
            # Consumer
            'WMT': 'Consumer', 'PG': 'Consumer', 'KO': 'Consumer',
            'PEP': 'Consumer', 'MCD': 'Consumer', 'NKE': 'Consumer',
            
            # Industrial
            'BA': 'Industrial', 'CAT': 'Industrial', 'GE': 'Industrial',
            'MMM': 'Industrial', 'HON': 'Industrial', 'UPS': 'Industrial',
            
            # Energy
            'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy',
            'EOG': 'Energy', 'SLB': 'Energy', 'PSX': 'Energy',
            
            # ETFs
            'SPY': 'ETF-Broad', 'QQQ': 'ETF-Tech', 'IWM': 'ETF-Small',
            'VTI': 'ETF-Broad', 'TQQQ': 'ETF-Leveraged', 'SQQQ': 'ETF-Leveraged'
        }
    
    def get_sector(self, symbol: str) -> str:
        """Get sector for a symbol"""
        return self.sector_map.get(symbol.upper(), 'Other')
    
    def load_sector_data(self, file_path: str = "sector_data.json"):
        """Load sector data from file if available"""
        try:
            if Path(file_path).exists():
                with open(file_path, 'r') as f:
                    additional_sectors = json.load(f)
                    self.sector_map.update(additional_sectors)
        except Exception as e:
            LOG.warning(f"Could not load sector data: {e}")

class PositionSafetyManager:
    """Main class for position safety management"""
    
    def __init__(self, safety_limits: SafetyLimits = None):
        self.limits = safety_limits or SafetyLimits()
        self.sector_classifier = SectorClassifier()
        self.orphaned_positions = []
        self.emergency_stops_triggered = []
        self.daily_start_value = None
        self.last_safety_check = None
        
        # Load configuration
        self._load_config()
        
    def _load_config(self):
        """Load safety configuration from config.json"""
        try:
            config_path = Path("config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                if "safety_limits" in config:
                    limits_cfg = config["safety_limits"]
                    self.limits.max_position_value = limits_cfg.get("max_position_value", self.limits.max_position_value)
                    self.limits.max_portfolio_value = limits_cfg.get("max_portfolio_value", self.limits.max_portfolio_value)
                    self.limits.max_daily_loss = limits_cfg.get("max_daily_loss", self.limits.max_daily_loss)
                    self.limits.max_position_concentration = limits_cfg.get("max_position_concentration", self.limits.max_position_concentration)
                    self.limits.emergency_stop_loss = limits_cfg.get("emergency_stop_loss", self.limits.emergency_stop_loss)
                    
        except Exception as e:
            LOG.warning(f"Could not load safety config: {e}")
    
    async def perform_safety_check(self, ib: IB) -> Dict[str, Any]:
        """Perform comprehensive safety check on all positions"""
        if not ib or not ib.isConnected():
            return {"error": "No IBKR connection available"}
        
        try:
            # Get current portfolio
            portfolio = ib.portfolio()
            account_summary = ib.accountSummary()
            
            # Calculate position risks
            position_risks = []
            total_value = 0
            
            for item in portfolio:
                if item.position != 0:
                    position_risk = await self._calculate_position_risk(ib, item)
                    position_risks.append(position_risk)
                    total_value += position_risk.market_value
            
            # Calculate portfolio risk
            portfolio_risk = self._calculate_portfolio_risk(position_risks, account_summary)
            
            # Check for violations
            violations = self._check_safety_violations(position_risks, portfolio_risk)
            
            # Check for orphaned positions
            orphaned = await self._check_orphaned_positions(ib, position_risks)
            
            # Update daily tracking
            if self.daily_start_value is None:
                self.daily_start_value = total_value
            
            self.last_safety_check = datetime.now()
            
            return {
                "timestamp": self.last_safety_check,
                "portfolio_risk": portfolio_risk,
                "position_risks": position_risks,
                "violations": violations,
                "orphaned_positions": orphaned,
                "emergency_actions_needed": len(violations) > 0,
                "overall_risk_score": portfolio_risk.risk_score
            }
            
        except Exception as e:
            LOG.error(f"Error in safety check: {e}")
            return {"error": str(e)}
    
    async def _calculate_position_risk(self, ib: IB, portfolio_item) -> PositionRisk:
        """Calculate risk metrics for a single position"""
        symbol = portfolio_item.contract.symbol
        quantity = int(portfolio_item.position)
        current_price = portfolio_item.marketPrice or portfolio_item.averageCost
        market_value = portfolio_item.marketValue
        unrealized_pnl = portfolio_item.unrealizedPNL or 0
        
        # Get sector
        sector = self.sector_classifier.get_sector(symbol)
        
        # Estimate volatility (simplified - in production, use proper volatility data)
        volatility = await self._estimate_volatility(symbol)
        
        # Calculate position concentration (will be updated with portfolio total)
        position_concentration = 0  # Will be calculated in portfolio risk
        
        # Calculate risk score (0-100, higher = riskier)
        risk_score = self._calculate_position_risk_score(
            market_value, volatility, unrealized_pnl, sector
        )
        
        return PositionRisk(
            symbol=symbol,
            quantity=quantity,
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            daily_pnl=unrealized_pnl,  # Simplified
            position_concentration=position_concentration,
            sector=sector,
            volatility=volatility,
            risk_score=risk_score
        )
    
    def _calculate_portfolio_risk(self, position_risks: List[PositionRisk], 
                                account_summary) -> PortfolioRisk:
        """Calculate portfolio-level risk metrics"""
        total_value = sum(pos.market_value for pos in position_risks)
        total_pnl = sum(pos.unrealized_pnl for pos in position_risks)
        daily_pnl = total_pnl  # Simplified
        
        # Get cash balance
        cash_balance = 0
        for item in account_summary:
            if item.tag == 'TotalCashValue':
                cash_balance = float(item.value)
                break
        
        # Calculate position concentrations
        for pos in position_risks:
            pos.position_concentration = pos.market_value / total_value if total_value > 0 else 0
        
        max_position_concentration = max(
            (pos.position_concentration for pos in position_risks), default=0
        )
        
        # Calculate sector concentrations
        sector_values = {}
        for pos in position_risks:
            sector_values[pos.sector] = sector_values.get(pos.sector, 0) + pos.market_value
        
        sector_concentrations = {
            sector: value / total_value for sector, value in sector_values.items()
        } if total_value > 0 else {}
        
        # Estimate VaR (simplified)
        var_95 = self._estimate_var_95(position_risks)
        
        # Calculate overall risk score
        risk_score = self._calculate_portfolio_risk_score(
            total_value, max_position_concentration, sector_concentrations, var_95
        )
        
        return PortfolioRisk(
            total_value=total_value,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            cash_balance=cash_balance,
            position_count=len(position_risks),
            max_position_concentration=max_position_concentration,
            sector_concentrations=sector_concentrations,
            correlation_risk=0.0,  # Simplified
            var_95=var_95,
            risk_score=risk_score
        )
    
    def _check_safety_violations(self, position_risks: List[PositionRisk], 
                               portfolio_risk: PortfolioRisk) -> List[Dict[str, Any]]:
        """Check for safety limit violations"""
        violations = []
        
        # Check portfolio value limit
        if portfolio_risk.total_value > self.limits.max_portfolio_value:
            violations.append({
                "type": "portfolio_value_exceeded",
                "severity": "HIGH",
                "message": f"Portfolio value ${portfolio_risk.total_value:,.0f} exceeds limit ${self.limits.max_portfolio_value:,.0f}",
                "action": "Reduce position sizes"
            })
        
        # Check daily loss limit
        if self.daily_start_value and portfolio_risk.daily_pnl < -self.limits.max_daily_loss:
            violations.append({
                "type": "daily_loss_exceeded",
                "severity": "CRITICAL",
                "message": f"Daily loss ${abs(portfolio_risk.daily_pnl):,.0f} exceeds limit ${self.limits.max_daily_loss:,.0f}",
                "action": "Emergency position closure required"
            })
        
        # Check emergency stop loss
        if self.daily_start_value:
            portfolio_loss_pct = (portfolio_risk.total_value - self.daily_start_value) / self.daily_start_value
            if portfolio_loss_pct < -self.limits.emergency_stop_loss:
                violations.append({
                    "type": "emergency_stop_triggered",
                    "severity": "CRITICAL",
                    "message": f"Portfolio down {abs(portfolio_loss_pct):.1%}, emergency stop at {self.limits.emergency_stop_loss:.1%}",
                    "action": "EMERGENCY: Close all positions immediately"
                })
        
        # Check position concentration
        if portfolio_risk.max_position_concentration > self.limits.max_position_concentration:
            violations.append({
                "type": "position_concentration_exceeded",
                "severity": "MEDIUM",
                "message": f"Max position concentration {portfolio_risk.max_position_concentration:.1%} exceeds limit {self.limits.max_position_concentration:.1%}",
                "action": "Reduce largest positions"
            })
        
        # Check sector concentration
        for sector, concentration in portfolio_risk.sector_concentrations.items():
            if concentration > self.limits.max_sector_concentration:
                violations.append({
                    "type": "sector_concentration_exceeded",
                    "severity": "MEDIUM",
                    "message": f"{sector} concentration {concentration:.1%} exceeds limit {self.limits.max_sector_concentration:.1%}",
                    "action": f"Reduce {sector} exposure"
                })
        
        # Check individual position limits
        for pos in position_risks:
            if pos.market_value > self.limits.max_position_value:
                violations.append({
                    "type": "position_value_exceeded",
                    "severity": "MEDIUM",
                    "symbol": pos.symbol,
                    "message": f"{pos.symbol} value ${pos.market_value:,.0f} exceeds limit ${self.limits.max_position_value:,.0f}",
                    "action": f"Reduce {pos.symbol} position size"
                })
        
        # Check cash reserve
        if portfolio_risk.cash_balance < self.limits.min_cash_reserve:
            violations.append({
                "type": "insufficient_cash_reserve",
                "severity": "LOW",
                "message": f"Cash balance ${portfolio_risk.cash_balance:,.0f} below minimum ${self.limits.min_cash_reserve:,.0f}",
                "action": "Consider reducing positions to increase cash"
            })
        
        return violations
    
    async def _check_orphaned_positions(self, ib: IB, position_risks: List[PositionRisk]) -> List[str]:
        """Check for orphaned positions (positions without corresponding orders or tracking)"""
        orphaned = []
        
        try:
            # Load pending sales to check if positions are tracked
            from pending_sales import pending_tracker
            pending_orders = pending_tracker.get_all_pending_orders()
            
            # Get open orders
            open_orders = ib.openOrders()
            symbols_with_orders = {order.contract.symbol for order in open_orders}
            
            for pos in position_risks:
                symbol = pos.symbol
                
                # Check if position has pending sale order or open order
                has_pending_order = symbol in pending_orders
                has_open_order = symbol in symbols_with_orders
                
                # If position exists but no tracking/orders, it might be orphaned
                if not has_pending_order and not has_open_order and pos.quantity > 0:
                    # Additional check: is this a recent position?
                    # (In production, check against trade logs)
                    orphaned.append(symbol)
            
        except Exception as e:
            LOG.error(f"Error checking orphaned positions: {e}")
        
        return orphaned
    
    async def execute_emergency_actions(self, ib: IB, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute emergency actions based on violations"""
        actions_taken = []
        
        for violation in violations:
            if violation["severity"] == "CRITICAL":
                if violation["type"] == "emergency_stop_triggered":
                    # Emergency close all positions
                    result = await self._emergency_close_all_positions(ib)
                    actions_taken.append({
                        "action": "emergency_close_all",
                        "result": result
                    })
                elif violation["type"] == "daily_loss_exceeded":
                    # Close losing positions first
                    result = await self._close_losing_positions(ib)
                    actions_taken.append({
                        "action": "close_losing_positions",
                        "result": result
                    })
        
        return {
            "timestamp": datetime.now(),
            "actions_taken": actions_taken,
            "emergency_stops_triggered": self.emergency_stops_triggered
        }
    
    async def _emergency_close_all_positions(self, ib: IB) -> Dict[str, Any]:
        """Emergency close all positions"""
        try:
            portfolio = ib.portfolio()
            positions_to_close = [item for item in portfolio if item.position > 0]
            
            closed_positions = []
            failed_positions = []
            
            for item in positions_to_close:
                try:
                    symbol = item.contract.symbol
                    quantity = int(item.position)
                    
                    # Create stock contract
                    contract = Stock(symbol, 'SMART', 'USD')
                    
                    # Place market sell order
                    order = MarketOrder('SELL', quantity)
                    trade = ib.placeOrder(contract, order)
                    
                    # Wait briefly for fill
                    await asyncio.sleep(1)
                    
                    closed_positions.append({
                        "symbol": symbol,
                        "quantity": quantity,
                        "order_id": trade.order.orderId
                    })
                    
                    LOG.critical(f"EMERGENCY CLOSE: {symbol} {quantity} shares")
                    
                except Exception as e:
                    failed_positions.append({
                        "symbol": item.contract.symbol,
                        "error": str(e)
                    })
                    LOG.error(f"Failed to emergency close {item.contract.symbol}: {e}")
            
            # Record emergency stop
            self.emergency_stops_triggered.append({
                "timestamp": datetime.now(),
                "reason": "Emergency stop loss triggered",
                "positions_closed": len(closed_positions),
                "positions_failed": len(failed_positions)
            })
            
            return {
                "success": True,
                "closed_positions": closed_positions,
                "failed_positions": failed_positions
            }
            
        except Exception as e:
            LOG.error(f"Emergency close all failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _close_losing_positions(self, ib: IB) -> Dict[str, Any]:
        """Close positions with significant losses"""
        try:
            portfolio = ib.portfolio()
            losing_positions = [
                item for item in portfolio 
                if item.position > 0 and (item.unrealizedPNL or 0) < -1000  # Losing more than $1000
            ]
            
            # Sort by loss amount (worst first)
            losing_positions.sort(key=lambda x: x.unrealizedPNL or 0)
            
            closed_positions = []
            
            for item in losing_positions:
                try:
                    symbol = item.contract.symbol
                    quantity = int(item.position)
                    loss = item.unrealizedPNL or 0
                    
                    contract = Stock(symbol, 'SMART', 'USD')
                    order = MarketOrder('SELL', quantity)
                    trade = ib.placeOrder(contract, order)
                    
                    closed_positions.append({
                        "symbol": symbol,
                        "quantity": quantity,
                        "loss": loss,
                        "order_id": trade.order.orderId
                    })
                    
                    LOG.warning(f"LOSS CONTROL: Closed {symbol} with ${loss:.0f} loss")
                    
                except Exception as e:
                    LOG.error(f"Failed to close losing position {item.contract.symbol}: {e}")
            
            return {
                "success": True,
                "closed_positions": closed_positions
            }
            
        except Exception as e:
            LOG.error(f"Close losing positions failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _estimate_volatility(self, symbol: str) -> float:
        """Estimate volatility for a symbol (simplified)"""
        # In production, use proper volatility calculation
        volatility_map = {
            'SPY': 0.15, 'QQQ': 0.20, 'IWM': 0.25,
            'AAPL': 0.25, 'MSFT': 0.25, 'GOOGL': 0.30,
            'TSLA': 0.50, 'NVDA': 0.40, 'AMZN': 0.30,
            'TQQQ': 0.60, 'SQQQ': 0.60  # Leveraged ETFs
        }
        return volatility_map.get(symbol.upper(), 0.30)  # Default 30%
    
    def _calculate_position_risk_score(self, market_value: float, volatility: float, 
                                     unrealized_pnl: float, sector: str) -> float:
        """Calculate risk score for a position (0-100)"""
        score = 0
        
        # Size risk (larger positions = higher risk)
        if market_value > 30000:
            score += 20
        elif market_value > 20000:
            score += 10
        
        # Volatility risk
        if volatility > 0.40:
            score += 30
        elif volatility > 0.25:
            score += 15
        
        # Loss risk
        loss_pct = unrealized_pnl / market_value if market_value > 0 else 0
        if loss_pct < -0.10:  # More than 10% loss
            score += 25
        elif loss_pct < -0.05:  # More than 5% loss
            score += 10
        
        # Sector risk
        if sector in ['Technology', 'ETF-Leveraged']:
            score += 10
        
        return min(score, 100)
    
    def _calculate_portfolio_risk_score(self, total_value: float, 
                                      max_concentration: float,
                                      sector_concentrations: Dict[str, float],
                                      var_95: float) -> float:
        """Calculate portfolio risk score (0-100)"""
        score = 0
        
        # Concentration risk
        if max_concentration > 0.20:
            score += 25
        elif max_concentration > 0.15:
            score += 15
        
        # Sector concentration risk
        max_sector_concentration = max(sector_concentrations.values()) if sector_concentrations else 0
        if max_sector_concentration > 0.40:
            score += 20
        elif max_sector_concentration > 0.30:
            score += 10
        
        # VaR risk
        var_pct = var_95 / total_value if total_value > 0 else 0
        if var_pct > 0.15:
            score += 25
        elif var_pct > 0.10:
            score += 15
        
        # Size risk
        if total_value > 400000:
            score += 15
        elif total_value > 200000:
            score += 10
        
        return min(score, 100)
    
    def _estimate_var_95(self, position_risks: List[PositionRisk]) -> float:
        """Estimate 95% Value at Risk (simplified)"""
        # Simplified VaR calculation
        total_var = 0
        for pos in position_risks:
            # Assume normal distribution, 95% VaR ≈ 1.65 * volatility * value
            position_var = 1.65 * pos.volatility * pos.market_value
            total_var += position_var ** 2  # Assuming some diversification
        
        return (total_var ** 0.5) * 0.8  # Apply diversification factor

# Integration with existing system
async def run_safety_monitor(ib: IB, check_interval: int = 300):
    """Run continuous safety monitoring"""
    safety_manager = PositionSafetyManager()
    
    LOG.info(f"Starting position safety monitoring (check every {check_interval}s)")
    
    while True:
        try:
            # Perform safety check
            safety_report = await safety_manager.perform_safety_check(ib)
            
            if "error" in safety_report:
                LOG.error(f"Safety check failed: {safety_report['error']}")
            else:
                violations = safety_report.get("violations", [])
                
                if violations:
                    LOG.warning(f"Safety violations detected: {len(violations)}")
                    for violation in violations:
                        LOG.warning(f"  {violation['severity']}: {violation['message']}")
                    
                    # Execute emergency actions if needed
                    critical_violations = [v for v in violations if v["severity"] == "CRITICAL"]
                    if critical_violations:
                        LOG.critical("CRITICAL violations detected - executing emergency actions")
                        await safety_manager.execute_emergency_actions(ib, critical_violations)
                
                # Log summary
                portfolio_risk = safety_report.get("portfolio_risk")
                if portfolio_risk:
                    LOG.info(f"Portfolio: ${portfolio_risk.total_value:,.0f}, "
                           f"P&L: ${portfolio_risk.total_pnl:,.0f}, "
                           f"Risk Score: {portfolio_risk.risk_score:.0f}/100")
            
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            LOG.error(f"Error in safety monitoring: {e}")
            await asyncio.sleep(60)  # Wait before retrying

def main():
    """Test the position safety manager"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if not IB_AVAILABLE:
        print("ib-insync not available - install with: pip install ib-insync")
        return
    
    print("Position Safety Manager Test")
    print("This would normally run with a live IBKR connection")
    
    # Test safety limits
    limits = SafetyLimits(
        max_position_value=25000,
        max_daily_loss=5000,
        emergency_stop_loss=0.05  # 5% emergency stop
    )
    
    safety_manager = PositionSafetyManager(limits)
    print(f"Safety limits configured:")
    print(f"  Max position value: ${limits.max_position_value:,}")
    print(f"  Max daily loss: ${limits.max_daily_loss:,}")
    print(f"  Emergency stop: {limits.emergency_stop_loss:.1%}")

if __name__ == "__main__":
    main()
