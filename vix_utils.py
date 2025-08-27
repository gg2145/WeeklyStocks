#!/usr/bin/env python3
"""
VIX Data Utilities

Provides robust VIX data retrieval with multiple fallback sources:
1. Yahoo Finance (primary, most reliable)
2. IBKR VIX Index (fallback)
3. Yahoo Finance daily data (last resort)

Used across multiple reports for consistent VIX data access.
"""

import asyncio
import logging
from typing import Optional
import yfinance as yf
from ib_insync import IB, Index, Stock

LOG = logging.getLogger(__name__)

async def get_vix_data(ib: Optional[IB] = None) -> Optional[float]:
    """
    Get current VIX level using multiple data sources with fallback logic
    
    Args:
        ib: Optional IBKR connection for fallback data source
        
    Returns:
        VIX level as float, or None if all sources fail
    """
    vix_level = None
    
    # Method 1: Yahoo Finance intraday (most reliable)
    try:
        LOG.debug("Fetching VIX data from Yahoo Finance (intraday)...")
        vix_ticker = yf.Ticker('^VIX')
        vix_info = vix_ticker.history(period='1d', interval='1m')
        
        if not vix_info.empty:
            vix_level = float(vix_info['Close'].iloc[-1])
            LOG.info(f"VIX from Yahoo Finance (intraday): {vix_level:.2f}")
            return vix_level
        else:
            LOG.warning("No VIX intraday data returned from Yahoo Finance")
            
    except Exception as e:
        LOG.warning(f"Yahoo Finance VIX intraday fetch failed: {e}")
    
    # Method 2: Yahoo Finance daily data (reliable fallback)
    try:
        LOG.debug("Fetching VIX daily data from Yahoo Finance...")
        vix_ticker = yf.Ticker('^VIX')
        vix_daily = vix_ticker.history(period='2d')
        
        if not vix_daily.empty:
            vix_level = float(vix_daily['Close'].iloc[-1])
            LOG.info(f"VIX from Yahoo Finance (daily): {vix_level:.2f}")
            return vix_level
        else:
            LOG.warning("No VIX daily data returned from Yahoo Finance")
            
    except Exception as e:
        LOG.warning(f"Yahoo Finance daily VIX fetch failed: {e}")
    
    # Method 3: IBKR VIX Index (requires connection)
    if ib and ib.isConnected():
        try:
            LOG.debug("Fetching VIX data from IBKR...")
            vix_contract = Index('VIX', 'CBOE', 'USD')
            ib.qualifyContracts(vix_contract)
            
            vix_ticker = ib.reqMktData(vix_contract, '', False, False)
            await asyncio.sleep(0.5)  # Give time for data
            
            # Try multiple price sources
            if hasattr(vix_ticker, 'last') and vix_ticker.last and vix_ticker.last > 0:
                vix_level = float(vix_ticker.last)
            elif hasattr(vix_ticker, 'close') and vix_ticker.close and vix_ticker.close > 0:
                vix_level = float(vix_ticker.close)
            elif hasattr(vix_ticker, 'marketPrice') and vix_ticker.marketPrice() and vix_ticker.marketPrice() > 0:
                vix_level = float(vix_ticker.marketPrice())
            
            # Cancel market data
            ib.cancelMktData(vix_contract)
            
            if vix_level:
                LOG.info(f"VIX from IBKR: {vix_level:.2f}")
                return vix_level
            else:
                LOG.warning("No valid VIX price from IBKR")
                
        except Exception as e:
            LOG.warning(f"IBKR VIX fetch failed: {e}")
    
    # Method 4: IBKR VIX as Stock (legacy fallback)
    if ib and ib.isConnected():
        try:
            LOG.debug("Fetching VIX as stock from IBKR (legacy)...")
            from .data_utils import hist_daily_closes  # Import here to avoid circular imports
            
            vix = Stock("VIX", "SMART", "USD")
            vix_bars = await hist_daily_closes(ib, vix, days=3)
            
            if vix_bars:
                vix_level = float(vix_bars[-1].close)
                LOG.info(f"VIX from IBKR (stock): {vix_level:.2f}")
                return vix_level
            else:
                LOG.warning("No VIX historical data from IBKR")
                
        except Exception as e:
            LOG.warning(f"IBKR VIX stock fetch failed: {e}")
    
    LOG.error("All VIX data sources failed")
    return None

def check_vix_regime(vix_level: Optional[float], max_vix: Optional[float] = None) -> dict:
    """
    Check if VIX indicates favorable regime conditions
    
    Args:
        vix_level: Current VIX level
        max_vix: Maximum acceptable VIX level
        
    Returns:
        Dict with regime analysis
    """
    if not max_vix:
        return {
            "vix_ok": True, 
            "vix_level": vix_level, 
            "reason": "No VIX filter configured"
        }
    
    if vix_level is None:
        return {
            "vix_ok": True, 
            "vix_level": None, 
            "reason": "VIX data unavailable, assuming OK"
        }
    
    vix_ok = vix_level <= max_vix
    return {
        "vix_ok": vix_ok,
        "vix_level": vix_level,
        "reason": f"VIX {vix_level:.2f} {'<=' if vix_ok else '>'} max {max_vix:.2f}"
    }

async def get_vix_regime_async(ib: Optional[IB] = None, max_vix: Optional[float] = None) -> dict:
    """
    Async convenience function to get VIX data and check regime in one call
    
    Args:
        ib: Optional IBKR connection
        max_vix: Maximum acceptable VIX level
        
    Returns:
        Dict with regime analysis including VIX level
    """
    vix_level = await get_vix_data(ib)
    return check_vix_regime(vix_level, max_vix)