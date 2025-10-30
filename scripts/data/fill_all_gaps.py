#!/usr/bin/env python3
"""
On-demand batch gap filling script.

This script can be run manually to fill gaps in cached data.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtester.services.gap_filling_runner import run_gap_filling
import logging

# Setup logging
LOG_DIR = Path('artifacts/logs')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'gap_filling.log'),
        logging.StreamHandler()
    ]
)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Fill gaps in cached data')
    parser.add_argument('--priority', choices=['largest', 'lowest_coverage'], 
                       default='largest', help='Priority order (default: largest)')
    parser.add_argument('--max-gaps', type=int, help='Maximum number of gaps to fill')
    
    args = parser.parse_args()
    
    result = run_gap_filling(priority=args.priority, max_gaps=args.max_gaps)
    
    if result.get('status') != 'no_gaps':
        print(f"\n✓ Gap filling complete: {result.get('gaps_filled', 0)} gaps filled, "
              f"{result.get('total_candles_added', 0):,} candles added")
    
    sys.exit(0 if result.get('status') == 'success' or result.get('status') == 'no_gaps' else 1)

