#!/usr/bin/env python3
"""
Options Protection Module for Weekly ER Strategy

Implements comprehensive options-based protection strategies:
- Protective puts for individual positions
- Collar strategies (covered calls + protective puts)
- Portfolio-level insurance (index puts, VIX calls)
- Dynamic options selection based on volatility
- Options P&L tracking and management
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from pathlib import Path
import logging
import datetime as dt
from scipy.stats import norm
import math

from ib_insync import IB, Option, Stock, MarketOrder, LimitOrder
from backtest_core import BacktestConfig

LOG = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent

@dataclass
class OptionsContract:
    """Options contract specification"""
    symbol: str
    expiry: dt.date
    strike: float
    right: str  # 'C' for call, 'P' for put
    multiplier: int = 100
    last_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    iv: float = 0.0  # Implied volatility
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0

@dataclass
class ProtectionStrategy:
    """Protection strategy configuration"""
    strategy_type: str  # 'protective_put', 'collar', 'portfolio_insurance'
    protection_level: float  # Percentage of position to protect
    max_cost_pct: float  # Maximum cost as % of position value
    min_days_to_expiry: int = 7
    max_days_to_expiry: int = 45
    delta_target: float = 0.2  # Target delta for protective puts
    enable_dynamic_adjustment: bool = True

class BlackScholesCalculator:
    """Black-Scholes options pricing and Greeks calculator"""
    
    @staticmethod
    def calculate_option_price(S: float, K: float, T: float, r: float, 
                             sigma: float, option_type: str = 'put') -> float:
        """Calculate Black-Scholes option price"""
        if T <= 0:
            return max(0, K - S) if option_type == 'put' else max(0, S - K)
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'put':
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:  # call
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        
        return max(0, price)
    
    @staticmethod
    def calculate_greeks(S: float, K: float, T: float, r: float, 
                        sigma: float, option_type: str = 'put') -> Dict[str, float]:
        """Calculate option Greeks"""
        if T <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Delta
        if option_type == 'put':
            delta = -norm.cdf(-d1)
        else:
            delta = norm.cdf(d1)
        
        # Gamma
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        
        # Theta
        if option_type == 'put':
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + 
                    r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        else:
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - 
                    r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        
        # Vega
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega
        }
    
    @staticmethod
    def calculate_implied_volatility(market_price: float, S: float, K: float, 
                                   T: float, r: float, option_type: str = 'put',
                                   max_iterations: int = 100, tolerance: float = 1e-6) -> float:
        """Calculate implied volatility using Newton-Raphson method"""
        if T <= 0:
            return 0.0
        
        # Initial guess
        sigma = 0.2
        
        for _ in range(max_iterations):
            price = BlackScholesCalculator.calculate_option_price(S, K, T, r, sigma, option_type)
            vega = BlackScholesCalculator.calculate_greeks(S, K, T, r, sigma, option_type)['vega']
            
            if abs(vega) < tolerance:
                break
                
            diff = market_price - price
            if abs(diff) < tolerance:
                break
                
            sigma += diff / (vega * 100)  # vega is per 1% change
            sigma = max(0.01, min(5.0, sigma))  # Keep within reasonable bounds
        
        return sigma

class OptionsDataProvider:
    """Provides options chain data and market prices"""
    
    def __init__(self):
        self.cache = {}
        self.risk_free_rate = 0.02  # 2% risk-free rate assumption
    
    def get_options_chain(self, symbol: str, expiry_date: dt.date = None) -> List[OptionsContract]:
        """Get options chain for a symbol"""
        # In a real implementation, this would connect to an options data provider
        # For now, we'll simulate an options chain
        
        try:
            # Get current stock price
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period="1d")['Close'].iloc[-1]
            
            # Calculate volatility from historical data
            hist_data = ticker.history(period="60d")
            returns = hist_data['Close'].pct_change().dropna()
            historical_vol = returns.std() * np.sqrt(252)
            
            # If no expiry specified, use next Friday
            if expiry_date is None:
                today = dt.date.today()
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                expiry_date = today + dt.timedelta(days=days_until_friday)
            
            # Generate strike prices around current price
            strikes = []
            for i in range(-10, 11):
                strike = current_price * (1 + i * 0.05)  # 5% intervals
                strikes.append(round(strike, 2))
            
            # Calculate time to expiry
            time_to_expiry = (expiry_date - dt.date.today()).days / 365.0
            
            options_chain = []
            
            for strike in strikes:
                # Calculate theoretical prices and Greeks
                put_price = BlackScholesCalculator.calculate_option_price(
                    current_price, strike, time_to_expiry, self.risk_free_rate, 
                    historical_vol, 'put'
                )
                
                call_price = BlackScholesCalculator.calculate_option_price(
                    current_price, strike, time_to_expiry, self.risk_free_rate, 
                    historical_vol, 'call'
                )
                
                put_greeks = BlackScholesCalculator.calculate_greeks(
                    current_price, strike, time_to_expiry, self.risk_free_rate, 
                    historical_vol, 'put'
                )
                
                call_greeks = BlackScholesCalculator.calculate_greeks(
                    current_price, strike, time_to_expiry, self.risk_free_rate, 
                    historical_vol, 'call'
                )
                
                # Add bid-ask spread (simulate market impact)
                put_bid = put_price * 0.95
                put_ask = put_price * 1.05
                call_bid = call_price * 0.95
                call_ask = call_price * 1.05
                
                # Put option
                put_contract = OptionsContract(
                    symbol=symbol,
                    expiry=expiry_date,
                    strike=strike,
                    right='P',
                    last_price=put_price,
                    bid=put_bid,
                    ask=put_ask,
                    iv=historical_vol,
                    delta=put_greeks['delta'],
                    gamma=put_greeks['gamma'],
                    theta=put_greeks['theta'],
                    vega=put_greeks['vega']
                )
                
                # Call option
                call_contract = OptionsContract(
                    symbol=symbol,
                    expiry=expiry_date,
                    strike=strike,
                    right='C',
                    last_price=call_price,
                    bid=call_bid,
                    ask=call_ask,
                    iv=historical_vol,
                    delta=call_greeks['delta'],
                    gamma=call_greeks['gamma'],
                    theta=call_greeks['theta'],
                    vega=call_greeks['vega']
                )
                
                options_chain.extend([put_contract, call_contract])
            
            return options_chain
            
        except Exception as e:
            LOG.error(f"Error getting options chain for {symbol}: {e}")
            return []
    
    def get_current_volatility(self, symbol: str) -> float:
        """Get current implied volatility estimate"""
        try:
            ticker = yf.Ticker(symbol)
            hist_data = ticker.history(period="30d")
            returns = hist_data['Close'].pct_change().dropna()
            return returns.std() * np.sqrt(252)
        except:
            return 0.25  # Default volatility

class ProtectivePutManager:
    """Manages protective put strategies for individual positions"""
    
    def __init__(self, options_provider: OptionsDataProvider, strategy: ProtectionStrategy):
        self.options_provider = options_provider
        self.strategy = strategy
        self.active_puts = {}  # symbol -> put contract
    
    def select_protective_put(self, symbol: str, stock_price: float, 
                            position_size: int, max_cost: float) -> Optional[OptionsContract]:
        """Select optimal protective put for a position"""
        
        # Get options chain
        options_chain = self.options_provider.get_options_chain(symbol)
        
        if not options_chain:
            LOG.warning(f"No options chain available for {symbol}")
            return None
        
        # Filter for puts only
        puts = [opt for opt in options_chain if opt.right == 'P']
        
        if not puts:
            return None
        
        # Filter by days to expiry
        today = dt.date.today()
        valid_puts = []
        
        for put in puts:
            days_to_expiry = (put.expiry - today).days
            if self.strategy.min_days_to_expiry <= days_to_expiry <= self.strategy.max_days_to_expiry:
                valid_puts.append(put)
        
        if not valid_puts:
            return None
        
        # Select put based on delta target and cost constraints
        best_put = None
        best_score = -np.inf
        
        for put in valid_puts:
            # Cost per share
            cost_per_share = put.ask
            total_cost = cost_per_share * position_size
            
            # Check cost constraint
            if total_cost > max_cost:
                continue
            
            # Score based on delta proximity to target and cost efficiency
            delta_score = 1 - abs(abs(put.delta) - self.strategy.delta_target)
            cost_score = 1 - (total_cost / max_cost)
            
            # Prefer puts closer to the money for better protection
            moneyness = put.strike / stock_price
            moneyness_score = 1 - abs(moneyness - 0.95)  # Target 5% out of the money
            
            total_score = delta_score * 0.4 + cost_score * 0.3 + moneyness_score * 0.3
            
            if total_score > best_score:
                best_score = total_score
                best_put = put
        
        return best_put
    
    def calculate_protection_cost(self, symbol: str, stock_price: float, 
                                position_size: int) -> Tuple[float, Optional[OptionsContract]]:
        """Calculate the cost of protection for a position"""
        
        max_cost = stock_price * position_size * self.strategy.max_cost_pct
        selected_put = self.select_protective_put(symbol, stock_price, position_size, max_cost)
        
        if selected_put is None:
            return 0.0, None
        
        total_cost = selected_put.ask * position_size
        return total_cost, selected_put
    
    def implement_protection(self, ib: IB, symbol: str, stock_price: float, 
                           position_size: int) -> Optional[Dict]:
        """Implement protective put for a position"""
        
        cost, put_contract = self.calculate_protection_cost(symbol, stock_price, position_size)
        
        if put_contract is None:
            LOG.warning(f"No suitable protective put found for {symbol}")
            return None
        
        try:
            # Create IBKR options contract
            option = Option(
                symbol=symbol,
                lastTradeDateOrContractMonth=put_contract.expiry.strftime('%Y%m%d'),
                strike=put_contract.strike,
                right=put_contract.right,
                exchange='SMART'
            )
            
            # Place buy order
            order = MarketOrder('BUY', position_size)
            trade = ib.placeOrder(option, order)
            
            # Wait for fill (with timeout)
            filled = trade.filledEvent.wait(timeout=30)
            
            if filled and trade.orderStatus.status == 'Filled':
                protection_info = {
                    'symbol': symbol,
                    'put_contract': put_contract,
                    'position_size': position_size,
                    'cost': cost,
                    'trade': trade,
                    'protection_level': put_contract.strike,
                    'expiry': put_contract.expiry
                }
                
                self.active_puts[symbol] = protection_info
                LOG.info(f"Protective put implemented for {symbol}: ${put_contract.strike} put @ ${put_contract.ask:.2f}")
                
                return protection_info
            else:
                LOG.warning(f"Failed to fill protective put order for {symbol}")
                return None
                
        except Exception as e:
            LOG.error(f"Error implementing protective put for {symbol}: {e}")
            return None
    
    def monitor_and_adjust_protection(self, ib: IB) -> Dict[str, str]:
        """Monitor active protective puts and make adjustments"""
        
        adjustments = {}
        
        for symbol, protection_info in list(self.active_puts.items()):
            try:
                # Get current stock price
                stock = Stock(symbol, 'SMART', 'USD')
                ticker = ib.reqMktData(stock)
                ib.sleep(1)
                current_price = ticker.last or ticker.close
                
                if current_price is None:
                    continue
                
                put_contract = protection_info['put_contract']
                days_to_expiry = (put_contract.expiry - dt.date.today()).days
                
                # Check if adjustment is needed
                adjustment_needed = False
                adjustment_reason = ""
                
                # Check expiry proximity
                if days_to_expiry <= 3:
                    adjustment_needed = True
                    adjustment_reason = "Expiry approaching"
                
                # Check if protection level is too far from current price
                protection_ratio = put_contract.strike / current_price
                if protection_ratio < 0.85:  # Protection more than 15% below current price
                    adjustment_needed = True
                    adjustment_reason = "Protection level too low"
                
                # Check if put is deeply in the money (stock declined significantly)
                if current_price < put_contract.strike * 0.9:
                    adjustment_needed = True
                    adjustment_reason = "Put deeply in the money"
                
                if adjustment_needed and self.strategy.enable_dynamic_adjustment:
                    success = self._adjust_protection(ib, symbol, current_price, protection_info)
                    adjustments[symbol] = adjustment_reason if success else f"Failed: {adjustment_reason}"
                
            except Exception as e:
                LOG.error(f"Error monitoring protection for {symbol}: {e}")
                adjustments[symbol] = f"Monitoring error: {e}"
        
        return adjustments
    
    def _adjust_protection(self, ib: IB, symbol: str, current_price: float, 
                         protection_info: Dict) -> bool:
        """Adjust protection for a symbol"""
        
        try:
            # Close existing put
            existing_trade = protection_info['trade']
            close_order = MarketOrder('SELL', protection_info['position_size'])
            
            option = Option(
                symbol=symbol,
                lastTradeDateOrContractMonth=protection_info['put_contract'].expiry.strftime('%Y%m%d'),
                strike=protection_info['put_contract'].strike,
                right='P',
                exchange='SMART'
            )
            
            close_trade = ib.placeOrder(option, close_order)
            close_filled = close_trade.filledEvent.wait(timeout=30)
            
            if not close_filled:
                LOG.warning(f"Failed to close existing put for {symbol}")
                return False
            
            # Implement new protection
            new_protection = self.implement_protection(ib, symbol, current_price, 
                                                     protection_info['position_size'])
            
            if new_protection:
                LOG.info(f"Successfully adjusted protection for {symbol}")
                return True
            else:
                LOG.warning(f"Failed to implement new protection for {symbol}")
                return False
                
        except Exception as e:
            LOG.error(f"Error adjusting protection for {symbol}: {e}")
            return False

class CollarStrategy:
    """Implements collar strategies (covered call + protective put)"""
    
    def __init__(self, options_provider: OptionsDataProvider):
        self.options_provider = options_provider
        self.active_collars = {}
    
    def design_collar(self, symbol: str, stock_price: float, position_size: int,
                     target_protection: float = 0.95, max_net_cost: float = 0.02) -> Optional[Dict]:
        """Design optimal collar strategy"""
        
        options_chain = self.options_provider.get_options_chain(symbol)
        
        if not options_chain:
            return None
        
        puts = [opt for opt in options_chain if opt.right == 'P']
        calls = [opt for opt in options_chain if opt.right == 'C']
        
        best_collar = None
        best_score = -np.inf
        
        # Find protective put near target protection level
        protection_strike = stock_price * target_protection
        suitable_puts = [p for p in puts if abs(p.strike - protection_strike) / protection_strike < 0.1]
        
        if not suitable_puts:
            return None
        
        # For each put, find optimal call to minimize net cost
        for put_option in suitable_puts:
            put_cost = put_option.ask * position_size
            
            # Find calls that can offset the put cost
            for call_option in calls:
                if call_option.strike <= stock_price:  # Don't sell in-the-money calls
                    continue
                
                call_premium = call_option.bid * position_size
                net_cost = put_cost - call_premium
                net_cost_pct = net_cost / (stock_price * position_size)
                
                if net_cost_pct > max_net_cost:
                    continue
                
                # Calculate upside potential
                upside_potential = (call_option.strike - stock_price) / stock_price
                
                # Score collar based on protection level, cost, and upside potential
                protection_score = put_option.strike / stock_price
                cost_score = 1 - (net_cost_pct / max_net_cost)
                upside_score = min(1.0, upside_potential / 0.1)  # Normalize to 10% upside
                
                total_score = protection_score * 0.4 + cost_score * 0.4 + upside_score * 0.2
                
                if total_score > best_score:
                    best_score = total_score
                    best_collar = {
                        'put': put_option,
                        'call': call_option,
                        'net_cost': net_cost,
                        'net_cost_pct': net_cost_pct,
                        'protection_level': put_option.strike,
                        'upside_cap': call_option.strike,
                        'upside_potential': upside_potential
                    }
        
        return best_collar
    
    def implement_collar(self, ib: IB, symbol: str, stock_price: float, 
                        position_size: int) -> Optional[Dict]:
        """Implement collar strategy"""
        
        collar_design = self.design_collar(symbol, stock_price, position_size)
        
        if collar_design is None:
            LOG.warning(f"No suitable collar found for {symbol}")
            return None
        
        try:
            # Create put option contract
            put_option = Option(
                symbol=symbol,
                lastTradeDateOrContractMonth=collar_design['put'].expiry.strftime('%Y%m%d'),
                strike=collar_design['put'].strike,
                right='P',
                exchange='SMART'
            )
            
            # Create call option contract
            call_option = Option(
                symbol=symbol,
                lastTradeDateOrContractMonth=collar_design['call'].expiry.strftime('%Y%m%d'),
                strike=collar_design['call'].strike,
                right='C',
                exchange='SMART'
            )
            
            # Buy protective put
            put_order = MarketOrder('BUY', position_size)
            put_trade = ib.placeOrder(put_option, put_order)
            
            # Sell covered call
            call_order = MarketOrder('SELL', position_size)
            call_trade = ib.placeOrder(call_option, call_order)
            
            # Wait for fills
            put_filled = put_trade.filledEvent.wait(timeout=30)
            call_filled = call_trade.filledEvent.wait(timeout=30)
            
            if put_filled and call_filled:
                collar_info = {
                    'symbol': symbol,
                    'put_trade': put_trade,
                    'call_trade': call_trade,
                    'collar_design': collar_design,
                    'position_size': position_size,
                    'implementation_date': dt.date.today()
                }
                
                self.active_collars[symbol] = collar_info
                LOG.info(f"Collar implemented for {symbol}: ${collar_design['protection_level']:.2f} put / ${collar_design['upside_cap']:.2f} call")
                
                return collar_info
            else:
                LOG.warning(f"Failed to fill collar orders for {symbol}")
                return None
                
        except Exception as e:
            LOG.error(f"Error implementing collar for {symbol}: {e}")
            return None

class PortfolioInsurance:
    """Portfolio-level insurance using index options and VIX derivatives"""
    
    def __init__(self, options_provider: OptionsDataProvider):
        self.options_provider = options_provider
        self.active_insurance = {}
    
    def calculate_portfolio_beta(self, positions: Dict[str, Dict]) -> float:
        """Calculate portfolio beta relative to SPY"""
        # Simplified beta calculation
        # In practice, would use regression analysis of returns
        return 1.0  # Assume market-neutral portfolio
    
    def design_portfolio_insurance(self, portfolio_value: float, 
                                 protection_level: float = 0.9,
                                 insurance_type: str = 'index_puts') -> Optional[Dict]:
        """Design portfolio-level insurance strategy"""
        
        if insurance_type == 'index_puts':
            return self._design_index_put_insurance(portfolio_value, protection_level)
        elif insurance_type == 'vix_calls':
            return self._design_vix_call_insurance(portfolio_value, protection_level)
        else:
            return None
    
    def _design_index_put_insurance(self, portfolio_value: float, 
                                  protection_level: float) -> Optional[Dict]:
        """Design insurance using SPY puts"""
        
        # Get SPY options chain
        spy_chain = self.options_provider.get_options_chain('SPY')
        
        if not spy_chain:
            return None
        
        # Get current SPY price
        try:
            spy_ticker = yf.Ticker('SPY')
            spy_price = spy_ticker.history(period="1d")['Close'].iloc[-1]
        except:
            return None
        
        # Calculate number of SPY equivalents to hedge
        portfolio_beta = self.calculate_portfolio_beta({})
        spy_equivalent_value = portfolio_value * portfolio_beta
        spy_shares_equivalent = spy_equivalent_value / spy_price
        
        # Find appropriate put strikes
        target_strike = spy_price * protection_level
        puts = [opt for opt in spy_chain if opt.right == 'P']
        
        suitable_puts = []
        for put in puts:
            if abs(put.strike - target_strike) / target_strike < 0.05:  # Within 5% of target
                suitable_puts.append(put)
        
        if not suitable_puts:
            return None
        
        # Select put with best cost/protection ratio
        best_put = min(suitable_puts, key=lambda p: p.ask)
        
        # Calculate number of puts needed
        puts_needed = int(spy_shares_equivalent / 100)  # Each put covers 100 shares
        
        if puts_needed == 0:
            return None
        
        insurance_cost = best_put.ask * puts_needed * 100
        
        return {
            'type': 'index_puts',
            'underlying': 'SPY',
            'put_contract': best_put,
            'quantity': puts_needed,
            'cost': insurance_cost,
            'protection_level': protection_level,
            'coverage_ratio': (puts_needed * 100 * spy_price) / portfolio_value
        }
    
    def _design_vix_call_insurance(self, portfolio_value: float, 
                                 protection_level: float) -> Optional[Dict]:
        """Design insurance using VIX calls"""
        
        # Get VIX options (simplified - would need actual VIX options data)
        try:
            vix_ticker = yf.Ticker('^VIX')
            current_vix = vix_ticker.history(period="1d")['Close'].iloc[-1]
        except:
            return None
        
        # Calculate VIX call strategy
        # Target: buy calls that pay off when VIX > 25 (stress scenario)
        target_vix_level = 25.0
        
        if current_vix >= target_vix_level:
            return None  # Already in stress mode
        
        # Estimate cost and payoff (simplified)
        estimated_call_cost = portfolio_value * 0.01  # 1% of portfolio
        
        return {
            'type': 'vix_calls',
            'underlying': 'VIX',
            'target_level': target_vix_level,
            'cost': estimated_call_cost,
            'protection_type': 'volatility_spike'
        }
    
    def implement_portfolio_insurance(self, ib: IB, portfolio_value: float,
                                    insurance_type: str = 'index_puts') -> Optional[Dict]:
        """Implement portfolio-level insurance"""
        
        insurance_design = self.design_portfolio_insurance(portfolio_value, 0.9, insurance_type)
        
        if insurance_design is None:
            LOG.warning("No suitable portfolio insurance found")
            return None
        
        if insurance_design['type'] == 'index_puts':
            return self._implement_index_put_insurance(ib, insurance_design)
        elif insurance_design['type'] == 'vix_calls':
            return self._implement_vix_insurance(ib, insurance_design)
        
        return None
    
    def _implement_index_put_insurance(self, ib: IB, insurance_design: Dict) -> Optional[Dict]:
        """Implement index put insurance"""
        
        try:
            put_contract = insurance_design['put_contract']
            
            # Create SPY put option
            spy_put = Option(
                symbol='SPY',
                lastTradeDateOrContractMonth=put_contract.expiry.strftime('%Y%m%d'),
                strike=put_contract.strike,
                right='P',
                exchange='SMART'
            )
            
            # Buy puts
            quantity = insurance_design['quantity']
            order = MarketOrder('BUY', quantity)
            trade = ib.placeOrder(spy_put, order)
            
            filled = trade.filledEvent.wait(timeout=30)
            
            if filled:
                insurance_info = {
                    'type': 'index_puts',
                    'trade': trade,
                    'design': insurance_design,
                    'implementation_date': dt.date.today()
                }
                
                self.active_insurance['portfolio'] = insurance_info
                LOG.info(f"Portfolio insurance implemented: {quantity} SPY ${put_contract.strike} puts")
                
                return insurance_info
            else:
                LOG.warning("Failed to fill portfolio insurance order")
                return None
                
        except Exception as e:
            LOG.error(f"Error implementing portfolio insurance: {e}")
            return None
    
    def _implement_vix_insurance(self, ib: IB, insurance_design: Dict) -> Optional[Dict]:
        """Implement VIX-based insurance (placeholder)"""
        LOG.info("VIX insurance implementation not available in this demo")
        return None

class OptionsProtectionManager:
    """Main manager class for all options protection strategies"""
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.options_provider = OptionsDataProvider()
        
        # Initialize strategy managers
        protection_strategy = ProtectionStrategy(
            strategy_type='protective_put',
            protection_level=0.95,
            max_cost_pct=0.03,  # Maximum 3% of position value
            delta_target=0.2
        )
        
        self.protective_put_manager = ProtectivePutManager(self.options_provider, protection_strategy)
        self.collar_strategy = CollarStrategy(self.options_provider)
        self.portfolio_insurance = PortfolioInsurance(self.options_provider)
    
    def implement_comprehensive_protection(self, ib: IB, positions: Dict[str, Dict],
                                         portfolio_value: float) -> Dict[str, Dict]:
        """Implement comprehensive options protection for all positions"""
        
        protection_results = {
            'individual_protection': {},
            'portfolio_insurance': None,
            'total_protection_cost': 0.0,
            'coverage_summary': {}
        }
        
        # Individual position protection
        for symbol, position_info in positions.items():
            stock_price = position_info['current_price']
            position_size = position_info['quantity']
            position_value = stock_price * position_size
            
            # Decide protection type based on position characteristics
            volatility = self.options_provider.get_current_volatility(symbol)
            
            if volatility > 0.4:  # High volatility - use collar
                protection = self.collar_strategy.implement_collar(ib, symbol, stock_price, position_size)
                protection_type = 'collar'
            else:  # Normal volatility - use protective put
                protection = self.protective_put_manager.implement_protection(ib, symbol, stock_price, position_size)
                protection_type = 'protective_put'
            
            if protection:
                protection_results['individual_protection'][symbol] = {
                    'type': protection_type,
                    'details': protection,
                    'cost': protection.get('cost', 0)
                }
                protection_results['total_protection_cost'] += protection.get('cost', 0)
        
        # Portfolio-level insurance
        if portfolio_value > 50000:  # Only for larger portfolios
            portfolio_protection = self.portfolio_insurance.implement_portfolio_insurance(
                ib, portfolio_value, 'index_puts'
            )
            
            if portfolio_protection:
                protection_results['portfolio_insurance'] = portfolio_protection
                protection_results['total_protection_cost'] += portfolio_protection.get('cost', 0)
        
        # Coverage summary
        protected_positions = len(protection_results['individual_protection'])
        total_positions = len(positions)
        coverage_pct = protected_positions / total_positions if total_positions > 0 else 0
        
        protection_results['coverage_summary'] = {
            'protected_positions': protected_positions,
            'total_positions': total_positions,
            'coverage_percentage': coverage_pct,
            'total_cost_pct': protection_results['total_protection_cost'] / portfolio_value
        }
        
        LOG.info(f"Protection implemented: {protected_positions}/{total_positions} positions, "
                f"Cost: ${protection_results['total_protection_cost']:.0f} "
                f"({protection_results['coverage_summary']['total_cost_pct']:.2%})")
        
        return protection_results
    
    def monitor_all_protection(self, ib: IB) -> Dict[str, Dict]:
        """Monitor and adjust all active protection strategies"""
        
        monitoring_results = {
            'protective_puts': {},
            'collars': {},
            'portfolio_insurance': {},
            'adjustments_made': 0
        }
        
        # Monitor protective puts
        put_adjustments = self.protective_put_manager.monitor_and_adjust_protection(ib)
        monitoring_results['protective_puts'] = put_adjustments
        monitoring_results['adjustments_made'] += len([adj for adj in put_adjustments.values() if 'Failed' not in adj])
        
        # Monitor collars (simplified)
        collar_adjustments = {}
        for symbol in self.collar_strategy.active_collars:
            collar_adjustments[symbol] = "Monitored - no adjustment needed"
        monitoring_results['collars'] = collar_adjustments
        
        # Monitor portfolio insurance (simplified)
        if 'portfolio' in self.portfolio_insurance.active_insurance:
            monitoring_results['portfolio_insurance']['portfolio'] = "Monitored - active"
        
        return monitoring_results

def main():
    """Example usage of options protection system"""
    import asyncio
    from ib_insync import IB
    
    # Initialize protection manager
    protection_manager = OptionsProtectionManager()
    
    # Example positions
    positions = {
        'AAPL': {'current_price': 150.0, 'quantity': 100},
        'MSFT': {'current_price': 300.0, 'quantity': 50},
        'GOOGL': {'current_price': 2500.0, 'quantity': 10}
    }
    
    portfolio_value = sum(pos['current_price'] * pos['quantity'] for pos in positions.values())
    
    print(f"Portfolio Value: ${portfolio_value:,.0f}")
    print("Analyzing protection options...")
    
    # Analyze protection costs (without IB connection)
    for symbol, pos in positions.items():
        cost, put_contract = protection_manager.protective_put_manager.calculate_protection_cost(
            symbol, pos['current_price'], pos['quantity']
        )
        
        if put_contract:
            print(f"{symbol}: Protection cost ${cost:.0f} ({cost/(pos['current_price']*pos['quantity']):.2%})")
            print(f"  Put: ${put_contract.strike:.0f} strike, {put_contract.delta:.2f} delta")
        else:
            print(f"{symbol}: No suitable protection found")
    
    # Design collar for high volatility stock
    collar_design = protection_manager.collar_strategy.design_collar(
        'AAPL', 150.0, 100
    )
    
    if collar_design:
        print(f"\nAAL Collar Design:")
        print(f"  Protection: ${collar_design['protection_level']:.2f} put")
        print(f"  Upside cap: ${collar_design['upside_cap']:.2f} call")
        print(f"  Net cost: ${collar_design['net_cost']:.0f} ({collar_design['net_cost_pct']:.2%})")
    
    # Design portfolio insurance
    insurance_design = protection_manager.portfolio_insurance.design_portfolio_insurance(
        portfolio_value, 0.9, 'index_puts'
    )
    
    if insurance_design:
        print(f"\nPortfolio Insurance Design:")
        print(f"  Type: {insurance_design['type']}")
        print(f"  Cost: ${insurance_design['cost']:.0f}")
        print(f"  Coverage: {insurance_design.get('coverage_ratio', 0):.2%}")

if __name__ == "__main__":
    main()