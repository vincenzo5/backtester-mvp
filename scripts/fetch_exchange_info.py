#!/usr/bin/env python3
"""
Fetch and cache exchange metadata from Coinbase via CCXT.

This script retrieves:
- Supported timeframes
- Top 50 trading markets
- Maker and taker fee rates

Usage:
    python scripts/fetch_exchange_info.py
    python scripts/fetch_exchange_info.py --refresh
"""

import ccxt
import yaml
import sys
from datetime import datetime
import os


def fetch_coinbase_metadata(refresh=False):
    """Fetch exchange metadata from Coinbase.
    
    Args:
        refresh (bool): Force refresh even if cache exists
    
    Returns:
        dict: Exchange metadata including timeframes, markets, and fees
    """
    metadata_file = 'config/exchange_metadata.yaml'
    
    # Check if metadata exists and user doesn't want to refresh
    if os.path.exists(metadata_file) and not refresh:
        print(f"Using cached metadata from {metadata_file}")
        with open(metadata_file, 'r') as f:
            return yaml.safe_load(f)
    
    print("Fetching exchange metadata from Coinbase via CCXT...")
    
    # Initialize exchange
    exchange = ccxt.coinbase()
    
    print("Loading markets...")
    exchange.load_markets()
    
    # Get supported timeframes
    timeframes = list(exchange.timeframes.keys())
    print(f"Found {len(timeframes)} supported timeframes")
    
    # Get top markets (filter USD pairs, sort by volume/ticker)
    # Note: Volume data may not be available, so we'll prioritize active markets
    usd_markets = [symbol for symbol in exchange.markets.keys() if '/USD' in symbol]
    active_markets = [m for m in usd_markets if exchange.markets[m]['active']]
    
    # Sort by symbol to get a consistent top 50 (prioritize major coins first)
    priority_pairs = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'USDT/USD', 'ADA/USD', 'AVAX/USD', 
                     'DOT/USD', 'MATIC/USD', 'LINK/USD', 'UNI/USD', 'ATOM/USD', 'XRP/USD',
                     'LTC/USD', 'DOGE/USD', 'SHIB/USD']
    
    # Get top 50, prioritizing known pairs
    top_markets = []
    for pair in priority_pairs:
        if pair in active_markets:
            top_markets.append(pair)
            if len(top_markets) >= 50:
                break
    
    # Add remaining markets up to 50
    for market in active_markets:
        if market not in top_markets and len(top_markets) < 50:
            top_markets.append(market)
    
    print(f"Selected {len(top_markets)} markets")
    
    # Get fee structure from tiers (most accurate)
    try:
        # Get tier-based fees (Tier 0 = highest fees for retail traders)
        tiers = exchange.fees.get('trading', {}).get('tiers', {})
        maker_tier = tiers.get('maker', [[0.0, 0.004]])
        taker_tier = tiers.get('taker', [[0.0, 0.006]])
        
        # Get the first tier (lowest volume/highest fees)
        fees = {
            'maker': maker_tier[0][1],  # Second value in tier [volume, fee]
            'taker': taker_tier[0][1]
        }
        print(f"Maker fee: {fees['maker']*100:.2f}%, Taker fee: {fees['taker']*100:.2f}%")
    except Exception as e:
        print(f"Warning: Could not fetch fee structure: {e}")
        # Use Coinbase Advanced Trade default fees
        fees = {
            'maker': 0.004,  # 0.4%
            'taker': 0.006   # 0.6%
        }
    
    # Build metadata structure
    metadata = {
        'last_updated': datetime.now().isoformat(),
        'exchange': 'coinbase',
        'timeframes': timeframes,
        'top_markets': top_markets,
        'fees': fees
    }
    
    # Save to file
    os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
    with open(metadata_file, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
    
    print(f"Metadata saved to {metadata_file}")
    
    return metadata


def main():
    """Main function."""
    refresh = '--refresh' in sys.argv
    
    try:
        metadata = fetch_coinbase_metadata(refresh=refresh)
        
        print("\n" + "="*60)
        print("EXCHANGE METADATA")
        print("="*60)
        print(f"Exchange: {metadata['exchange']}")
        print(f"Last Updated: {metadata['last_updated']}")
        print(f"\nSupported Timeframes ({len(metadata['timeframes'])}):")
        for tf in metadata['timeframes']:
            print(f"  - {tf}")
        print(f"\nTop {len(metadata['top_markets'])} Markets:")
        for i, market in enumerate(metadata['top_markets'][:10], 1):
            print(f"  {i:2d}. {market}")
        if len(metadata['top_markets']) > 10:
            print(f"  ... and {len(metadata['top_markets']) - 10} more")
        print(f"\nFee Structure:")
        print(f"  Maker: {metadata['fees']['maker']*100:.2f}%")
        print(f"  Taker: {metadata['fees']['taker']*100:.2f}%")
        print("="*60)
        
    except Exception as e:
        print(f"Error fetching metadata: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

