"""
Command-line argument parsing module.

This module handles parsing and validation of CLI arguments.
"""

import argparse
from typing import Optional


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for the backtesting engine.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Crypto backtesting engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run full backtest from config
  python main.py --quick            # Run quick test mode
        """
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick test: BTC/USD 1h with verbose output'
    )
    
    args = parser.parse_args()
    
    # Determine profile name based on flags
    args.profile = 'quick' if args.quick else None
    
    return args

