"""
Period parser for walk-forward optimization.

Parses calendar-based period notation (e.g., "1Y/6M") into days.
"""

import re
from typing import Tuple
from datetime import timedelta


class PeriodParseError(Exception):
    """Raised when period notation cannot be parsed."""
    pass


# Average days per period unit
DAYS_PER_YEAR = 365.25
DAYS_PER_MONTH = 30.4375  # 365.25 / 12
DAYS_PER_WEEK = 7
DAYS_PER_DAY = 1


def parse_period(period_str: str) -> Tuple[int, int]:
    """
    Parse period notation into in-sample and out-of-sample days.
    
    Args:
        period_str: Period notation like "1Y/6M", "252/126", etc.
                   Format: <in_sample>/<out_sample>
                   Units: Y (years), M (months), W (weeks), D (days)
    
    Returns:
        Tuple of (in_sample_days, out_sample_days)
    
    Raises:
        PeriodParseError: If period format is invalid
    
    Examples:
        >>> parse_period("1Y/6M")
        (365, 182)
        >>> parse_period("2Y/3M")
        (730, 91)
        >>> parse_period("252/126")
        (252, 126)
        >>> parse_period("12M/3M")
        (365, 91)
    """
    # Split by slash
    parts = period_str.split('/')
    if len(parts) != 2:
        raise PeriodParseError(f"Invalid period format: {period_str}. Expected format: <in_sample>/<out_sample>")
    
    in_sample_str = parts[0].strip()
    out_sample_str = parts[1].strip()
    
    # Parse in-sample period
    in_sample_days = _parse_period_unit(in_sample_str)
    
    # Parse out-of-sample period
    out_sample_days = _parse_period_unit(out_sample_str)
    
    return int(in_sample_days), int(out_sample_days)


def _parse_period_unit(period_unit: str) -> float:
    """
    Parse a single period unit (e.g., "1Y", "6M", "252") into days.
    
    Args:
        period_unit: Period unit string (e.g., "1Y", "6M", "12W", "30D", "252")
    
    Returns:
        Number of days as float
    
    Raises:
        PeriodParseError: If period unit format is invalid
    """
    # Try to match pattern: number followed by optional unit
    pattern = r'^(\d+(?:\.\d+)?)\s*([YMWD]?)$'
    match = re.match(pattern, period_unit, re.IGNORECASE)
    
    if not match:
        raise PeriodParseError(f"Invalid period unit format: {period_unit}")
    
    value = float(match.group(1))
    unit = match.group(2).upper() if match.group(2) else None
    
    # If no unit specified, assume it's already in days
    if not unit:
        return value
    
    # Convert based on unit
    if unit == 'Y':
        return value * DAYS_PER_YEAR
    elif unit == 'M':
        return value * DAYS_PER_MONTH
    elif unit == 'W':
        return value * DAYS_PER_WEEK
    elif unit == 'D':
        return value * DAYS_PER_DAY
    else:
        raise PeriodParseError(f"Unknown period unit: {unit}. Supported: Y, M, W, D")
    
    
def validate_period(period_str: str) -> bool:
    """
    Validate that a period string is in correct format.
    
    Args:
        period_str: Period notation to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        parse_period(period_str)
        return True
    except PeriodParseError:
        return False


