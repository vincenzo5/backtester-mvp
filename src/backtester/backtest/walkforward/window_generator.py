"""
Window generator for rolling walk-forward analysis.

Generates rolling in-sample/out-of-sample windows from date ranges.
"""

from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta
import pandas as pd

from backtester.backtest.walkforward.period_parser import parse_period, PeriodParseError


@dataclass
class WalkForwardWindow:
    """Represents a single walk-forward window."""
    
    window_index: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_sample_start: datetime
    out_sample_end: datetime
    
    def __str__(self):
        return (f"Window {self.window_index}: "
                f"IS {self.in_sample_start.date()} to {self.in_sample_end.date()}, "
                f"OOS {self.out_sample_start.date()} to {self.out_sample_end.date()}")


def generate_windows(
    start_date: datetime,
    end_date: datetime,
    in_sample_days: int,
    out_sample_days: int,
    data_df: pd.DataFrame = None
) -> List[WalkForwardWindow]:
    """
    Generate rolling walk-forward windows.
    
    Args:
        start_date: Overall analysis start date
        end_date: Overall analysis end date
        in_sample_days: Number of days for in-sample period
        out_sample_days: Number of days for out-of-sample period
        data_df: Optional DataFrame to ensure windows align with actual data
    
    Returns:
        List of WalkForwardWindow objects
    """
    windows = []
    window_index = 0
    
    # Current position - starts at start_date
    current_start = start_date
    
    # Adjust dates based on actual data if DataFrame provided
    if data_df is not None and not data_df.empty:
        # Get actual data dates
        data_dates = pd.to_datetime(data_df.index)
        data_start = data_dates.min()
        data_end = data_dates.max()
        
        # Normalize timezones - if data has timezone, convert start/end to match
        if data_start.tzinfo is not None:
            # Data is timezone-aware, make start/end match
            if start_date.tzinfo is None:
                from datetime import timezone
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                from datetime import timezone
                end_date = end_date.replace(tzinfo=timezone.utc)
            if current_start.tzinfo is None:
                from datetime import timezone
                current_start = current_start.replace(tzinfo=timezone.utc)
        
        # Use data bounds if they're narrower than specified
        if data_start > start_date:
            # Convert to same type (datetime or Timestamp)
            if isinstance(data_start, pd.Timestamp):
                current_start = data_start.to_pydatetime()
            else:
                current_start = data_start
        if data_end < end_date:
            if isinstance(data_end, pd.Timestamp):
                end_date = data_end.to_pydatetime()
            else:
                end_date = data_end
    
    while True:
        # Calculate in-sample period
        in_sample_start = current_start
        in_sample_end = in_sample_start + timedelta(days=in_sample_days)
        
        # Normalize timezone for in_sample_end to match in_sample_start
        if in_sample_start.tzinfo is not None and in_sample_end.tzinfo is None:
            in_sample_end = in_sample_end.replace(tzinfo=in_sample_start.tzinfo)
        elif in_sample_start.tzinfo is None and in_sample_end.tzinfo is not None:
            in_sample_end = in_sample_end.replace(tzinfo=None)
        
        # Check if we have enough data for in-sample
        if in_sample_end > end_date:
            break
        
        # Calculate out-of-sample period
        out_sample_start = in_sample_end
        out_sample_end = out_sample_start + timedelta(days=out_sample_days)
        
        # Normalize timezone for out_sample_end to match out_sample_start
        if out_sample_start.tzinfo is not None and out_sample_end.tzinfo is None:
            out_sample_end = out_sample_end.replace(tzinfo=out_sample_start.tzinfo)
        elif out_sample_start.tzinfo is None and out_sample_end.tzinfo is not None:
            out_sample_end = out_sample_end.replace(tzinfo=None)
        
        # Check if we have enough data for out-of-sample
        if out_sample_end > end_date:
            # Try to use remaining data if there's at least some amount
            remaining_days = (end_date - out_sample_start).days
            if remaining_days < out_sample_days * 0.5:  # Need at least 50% of out-sample period
                break
            out_sample_end = end_date
        
        # Create window
        window = WalkForwardWindow(
            window_index=window_index,
            in_sample_start=in_sample_start,
            in_sample_end=in_sample_end,
            out_sample_start=out_sample_start,
            out_sample_end=out_sample_end
        )
        windows.append(window)
        
        # Move to next window: slide forward by out_sample_days
        current_start = out_sample_start
        window_index += 1
    
    return windows


def generate_windows_from_period(
    start_date: datetime,
    end_date: datetime,
    period_str: str,
    data_df: pd.DataFrame = None
) -> List[WalkForwardWindow]:
    """
    Generate windows from period notation string.
    
    Args:
        start_date: Overall analysis start date
        end_date: Overall analysis end date
        period_str: Period notation (e.g., "1Y/6M")
        data_df: Optional DataFrame to align windows with actual data
    
    Returns:
        List of WalkForwardWindow objects
    
    Raises:
        PeriodParseError: If period format is invalid
    """
    in_sample_days, out_sample_days = parse_period(period_str)
    return generate_windows(start_date, end_date, in_sample_days, out_sample_days, data_df)

