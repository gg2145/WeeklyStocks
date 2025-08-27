#!/usr/bin/env python3
"""
Timezone Utilities for Weekly ER Strategy

Provides dual timezone display functionality for reports, showing both
NY market time and user's local time (default: Melbourne) for easy coordination.
"""

import datetime as dt
import pytz
from typing import Tuple, Optional
from pathlib import Path
import json

# Standard timezone objects
NY = pytz.timezone("America/New_York")
MELBOURNE = pytz.timezone("Australia/Melbourne")

def load_timezone_config() -> dict:
    """Load timezone configuration from config.json"""
    try:
        base_dir = Path(__file__).resolve().parent
        with open(base_dir / "config.json", 'r') as f:
            cfg = json.load(f)
        return cfg.get("timezone_display", {
            "primary": "America/New_York",
            "secondary": "Australia/Melbourne", 
            "show_dual_time": True,
            "include_market_status": True
        })
    except Exception:
        # Default configuration
        return {
            "primary": "America/New_York",
            "secondary": "Australia/Melbourne", 
            "show_dual_time": True,
            "include_market_status": True
        }

def get_timezone_objects() -> Tuple[pytz.BaseTzInfo, pytz.BaseTzInfo]:
    """Get primary and secondary timezone objects from config"""
    config = load_timezone_config()
    primary_tz = pytz.timezone(config["primary"])
    secondary_tz = pytz.timezone(config["secondary"])
    return primary_tz, secondary_tz

def get_market_status(now_ny: dt.datetime) -> str:
    """Determine current market status"""
    # Market is open Monday-Friday 9:30-16:00 ET
    weekday = now_ny.weekday()  # 0=Monday, 6=Sunday
    hour = now_ny.hour
    minute = now_ny.minute
    
    if weekday >= 5:  # Saturday or Sunday
        return "CLOSED (Weekend)"
    
    # Convert to minutes for easier comparison
    current_time = hour * 60 + minute
    market_open = 9 * 60 + 30  # 9:30 AM
    market_close = 16 * 60     # 4:00 PM
    
    if current_time < market_open:
        return "PRE-MARKET"
    elif current_time >= market_close:
        return "AFTER-HOURS"
    else:
        return "OPEN"

def format_dual_timezone(timestamp: dt.datetime, 
                        include_market_status: bool = True,
                        format_type: str = "full") -> str:
    """
    Format timestamp with dual timezone display
    
    Args:
        timestamp: datetime object (timezone-aware or naive)
        include_market_status: Whether to include market status
        format_type: 'full', 'short', 'time_only', 'date_only'
    
    Returns:
        Formatted string like "2025-08-19 14:30:15 ET (03:30:15+11 AEDT) - Market: OPEN"
    """
    config = load_timezone_config()
    
    if not config["show_dual_time"]:
        # Single timezone mode
        if timestamp.tzinfo is None:
            timestamp = NY.localize(timestamp)
        ny_time = timestamp.astimezone(NY)
        
        if format_type == "time_only":
            return ny_time.strftime("%H:%M:%S ET")
        elif format_type == "date_only":
            return ny_time.strftime("%Y-%m-%d")
        elif format_type == "short":
            return ny_time.strftime("%m/%d %H:%M ET")
        else:
            return ny_time.strftime("%Y-%m-%d %H:%M:%S ET")
    
    # Dual timezone mode
    primary_tz, secondary_tz = get_timezone_objects()
    
    # Ensure timestamp is timezone-aware
    if timestamp.tzinfo is None:
        timestamp = primary_tz.localize(timestamp)
    
    # Convert to both timezones
    primary_time = timestamp.astimezone(primary_tz)
    secondary_time = timestamp.astimezone(secondary_tz)
    
    # Get timezone abbreviations
    primary_abbr = primary_time.strftime("%Z")
    secondary_abbr = secondary_time.strftime("%Z")
    
    # Format based on type
    if format_type == "time_only":
        result = f"{primary_time.strftime('%H:%M:%S')} {primary_abbr} ({secondary_time.strftime('%H:%M:%S')} {secondary_abbr})"
    elif format_type == "date_only":
        result = f"{primary_time.strftime('%Y-%m-%d')} {primary_abbr} ({secondary_time.strftime('%Y-%m-%d')} {secondary_abbr})"
    elif format_type == "short":
        result = f"{primary_time.strftime('%m/%d %H:%M')} {primary_abbr} ({secondary_time.strftime('%m/%d %H:%M')} {secondary_abbr})"
    else:  # full
        result = f"{primary_time.strftime('%Y-%m-%d %H:%M:%S')} {primary_abbr} ({secondary_time.strftime('%Y-%m-%d %H:%M:%S')} {secondary_abbr})"
    
    # Add market status if requested
    if include_market_status and config["include_market_status"]:
        market_status = get_market_status(primary_time)
        result += f" - Market: {market_status}"
    
    return result

def format_current_time(format_type: str = "full", include_market_status: bool = True) -> str:
    """Format current time with dual timezone display"""
    now = dt.datetime.now(tz=NY)
    return format_dual_timezone(now, include_market_status, format_type)

def get_timestamped_filename(base_name: str, extension: str = "html") -> str:
    """
    Generate filename with timestamp
    
    Args:
        base_name: Base filename (e.g., "monday_plan", "position_monitor")
        extension: File extension without dot
    
    Returns:
        Filename like "monday_plan_20250819_1430ET.html"
    """
    now = dt.datetime.now(tz=NY)
    timestamp = now.strftime("%Y%m%d_%H%M")
    return f"{base_name}_{timestamp}ET.{extension}"

def get_next_market_event() -> Tuple[str, dt.datetime, str]:
    """
    Get information about the next market open/close event
    
    Returns:
        Tuple of (event_type, event_time, dual_timezone_string)
    """
    now_ny = dt.datetime.now(tz=NY)
    weekday = now_ny.weekday()
    
    # Today's market times
    today_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
    today_close = now_ny.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if weekday >= 5:  # Weekend
        # Next Monday open
        days_until_monday = (7 - weekday) % 7
        if days_until_monday == 0:  # Sunday
            days_until_monday = 1
        next_monday = now_ny + dt.timedelta(days=days_until_monday)
        next_open = next_monday.replace(hour=9, minute=30, second=0, microsecond=0)
        return ("Market Open", next_open, format_dual_timezone(next_open, False))
    
    # Weekday
    current_time = now_ny.hour * 60 + now_ny.minute
    market_open_mins = 9 * 60 + 30
    market_close_mins = 16 * 60
    
    if current_time < market_open_mins:
        # Before market open today
        return ("Market Open", today_open, format_dual_timezone(today_open, False))
    elif current_time < market_close_mins:
        # Market is open, next event is close
        return ("Market Close", today_close, format_dual_timezone(today_close, False))
    else:
        # After market close, next event is tomorrow's open (or Monday if Friday)
        if weekday == 4:  # Friday
            next_monday = now_ny + dt.timedelta(days=3)
            next_open = next_monday.replace(hour=9, minute=30, second=0, microsecond=0)
        else:
            tomorrow = now_ny + dt.timedelta(days=1)
            next_open = tomorrow.replace(hour=9, minute=30, second=0, microsecond=0)
        return ("Market Open", next_open, format_dual_timezone(next_open, False))

def time_until_event(event_time: dt.datetime) -> str:
    """
    Calculate human-readable time until event
    
    Returns:
        String like "2h 15m" or "15m" or "3d 2h"
    """
    now = dt.datetime.now(tz=NY)
    if event_time.tzinfo is None:
        event_time = NY.localize(event_time)
    else:
        event_time = event_time.astimezone(NY)
    
    delta = event_time - now
    
    if delta.total_seconds() <= 0:
        return "Now"
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:  # Show minutes if it's the only unit or there are no other units
        parts.append(f"{minutes}m")
    
    return " ".join(parts)

def get_market_countdown() -> str:
    """Get countdown to next market event with dual timezone display"""
    event_type, event_time, event_time_str = get_next_market_event()
    countdown = time_until_event(event_time)
    return f"Next {event_type}: {event_time_str} (in {countdown})"

# Convenience functions for common use cases
def now_dual() -> str:
    """Current time in dual timezone format"""
    return format_current_time("full", True)

def now_short() -> str:
    """Current time in short dual timezone format"""
    return format_current_time("short", True)

def now_time_only() -> str:
    """Current time only (no date) in dual timezone format"""
    return format_current_time("time_only", False)

# For backward compatibility
def ny_datetime(*args, **kwargs):
    """Create a NY timezone datetime - imported from us_trading_calendar"""
    from us_trading_calendar import ny_datetime as orig_ny_datetime
    return orig_ny_datetime(*args, **kwargs)