#!/usr/bin/env python3
"""
Check which markets from exchange_metadata.yaml actually exist on Coinbase.

This script will:
1. Load markets from exchange_metadata.yaml
2. Test each market on Coinbase to see if it exists
3. Show a report of available vs unavailable markets
4. Optionally update exchange_metadata.yaml to remove unavailable markets
"""

import sys
import yaml
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.fetcher import create_exchange, MarketNotFoundError


def load_metadata():
    """Load exchange metadata configuration."""
    metadata_path = Path('config/markets.yaml')
    with open(metadata_path, 'r') as f:
        return yaml.safe_load(f)


def test_market_exists(exchange, symbol, timeframe='1d'):
    """
    Test if a market exists on the exchange.
    
    Returns:
        tuple: (exists: bool, error_message: str or None)
    """
    try:
        # Try to fetch just 1 candle to see if market exists
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1)
        if ohlcv and len(ohlcv) > 0:
            return True, None
        else:
            return False, "No data returned"
    except MarketNotFoundError as e:
        return False, str(e)
    except Exception as e:
        # Other errors might be temporary, but likely means market doesn't exist
        error_msg = str(e).lower()
        if 'not have market' in error_msg or 'not found' in error_msg or 'invalid symbol' in error_msg:
            return False, "Market not found"
        return False, f"Error: {str(e)[:50]}"


def check_all_markets(dry_run=True):
    """Check all markets and optionally update metadata."""
    print("=" * 80)
    print("Coinbase Market Availability Checker")
    print("=" * 80)
    print()
    
    # Load metadata
    metadata = load_metadata()
    # Exchange selection is done via exchange.yaml config
    exchange_name = 'coinbase'  # Default for this script
    markets = metadata.get('top_markets', [])
    
    if exchange_name != 'coinbase':
        print(f"⚠️  Warning: Exchange is '{exchange_name}', not 'coinbase'")
        print("   This script is designed for Coinbase. Results may vary.\n")
    
    print(f"Checking {len(markets)} markets on {exchange_name}...")
    print()
    
    # Initialize exchange
    exchange = create_exchange(exchange_name, enable_rate_limit=True)
    
    # Test each market
    available = []
    unavailable = []
    
    for i, market in enumerate(markets, 1):
        print(f"[{i}/{len(markets)}] Testing {market}...", end=' ', flush=True)
        exists, error = test_market_exists(exchange, market)
        
        if exists:
            available.append(market)
            print("✓ Available")
        else:
            unavailable.append((market, error))
            print(f"✗ Unavailable ({error})")
    
    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total markets checked: {len(markets)}")
    print(f"Available: {len(available)} ({len(available)/len(markets)*100:.1f}%)")
    print(f"Unavailable: {len(unavailable)} ({len(unavailable)/len(markets)*100:.1f}%)")
    print()
    
    if available:
        print("✓ Available markets:")
        for market in available:
            print(f"  - {market}")
        print()
    
    if unavailable:
        print("✗ Unavailable markets:")
        for market, error in unavailable:
            print(f"  - {market}: {error}")
        print()
    
    # Optionally update metadata
    if unavailable and not dry_run:
        print("=" * 80)
        print("UPDATING markets.yaml")
        print("=" * 80)
        
        unavailable_markets = [m for m, _ in unavailable]
        metadata['top_markets'] = available
        metadata['last_updated'] = datetime.utcnow().isoformat()
        
        metadata_path = Path('config/markets.yaml')
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
        
        print(f"✓ Removed {len(unavailable_markets)} unavailable markets from metadata")
        print(f"✓ Updated metadata with {len(available)} available markets")
        print()
    elif unavailable and dry_run:
        print("=" * 80)
        print("DRY RUN - No changes made")
        print("=" * 80)
        print("To actually update markets.yaml, run with --apply flag:")
        print(f"  python scripts/check_coinbase_markets.py --apply")
        print()
    
    return available, unavailable


def main():
    """Main entry point."""
    dry_run = True
    
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        dry_run = False
        print("⚠️  This will modify markets.yaml. Proceed? (y/N): ", end='', flush=True)
        response = input().strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
        print()
    
    try:
        available, unavailable = check_all_markets(dry_run=dry_run)
        
        if unavailable:
            sys.exit(1)  # Exit with error code if any markets unavailable
        else:
            print("🎉 All markets are available!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

