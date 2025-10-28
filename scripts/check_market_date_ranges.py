#!/usr/bin/env python3
"""
Check the actual date ranges available for markets on Coinbase.
Some markets may not have data going back to 2017.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.fetcher import create_exchange, fetch_historical, MarketNotFoundError
import pandas as pd


def check_market_date_range(symbol, timeframe='1d'):
    """Check what date range is actually available for a market."""
    exchange = create_exchange('coinbase', enable_rate_limit=True)
    
    try:
        # First, try to fetch just recent data (last 30 days) to confirm market exists
        end_date = (datetime.utcnow() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        start_date_recent = (datetime.utcnow() - pd.Timedelta(days=30)).strftime('%Y-%m-%d')
        
        df_recent, _ = fetch_historical(exchange, symbol, timeframe, start_date_recent, end_date)
        
        if df_recent.empty:
            return None, "No recent data available"
        
        # Now try to fetch from 2017
        df_2017, _ = fetch_historical(exchange, symbol, timeframe, '2017-01-01', end_date)
        
        if df_2017.empty:
            # Market exists but no data from 2017 - find earliest available date
            # Try incrementally from 2017 forward
            earliest = None
            for year in range(2017, 2026):
                test_start = f"{year}-01-01"
                df_test, _ = fetch_historical(exchange, symbol, timeframe, test_start, end_date)
                if not df_test.empty:
                    earliest = df_test.index.min()
                    break
            
            if earliest:
                latest = df_recent.index.max()
                return (earliest, latest), f"Data starts from {earliest.date()}, not 2017-01-01"
            else:
                latest = df_recent.index.max()
                return (None, latest), "No historical data (only recent data available)"
        else:
            earliest = df_2017.index.min()
            latest = df_2017.index.max()
            return (earliest, latest), "Full range available"
            
    except MarketNotFoundError:
        return None, "Market not found"
    except Exception as e:
        return None, f"Error: {str(e)[:50]}"


def main():
    """Check a few problematic markets."""
    # Markets that showed "No data available" in bulk fetch
    test_markets = ['SOL/USD', 'ADA/USD', 'DOGE/USD', 'AVAX/USD', 'SHIB/USD', 'BNB/USD']
    
    print("=" * 80)
    print("Checking Date Ranges for Markets Showing 'No Data Available'")
    print("=" * 80)
    print()
    
    for symbol in test_markets:
        print(f"Checking {symbol}...", end=' ', flush=True)
        date_range, status = check_market_date_range(symbol, '1d')
        
        if date_range and date_range[0]:
            earliest, latest = date_range
            days = (latest - earliest).days
            print(f"✓ Available from {earliest.date()} to {latest.date()} ({days} days)")
            if earliest.year > 2017:
                print(f"  ⚠️  {status}")
        elif date_range and date_range[1]:
            print(f"✓ {status}")
        else:
            print(f"✗ {status}")
        print()


if __name__ == '__main__':
    main()

