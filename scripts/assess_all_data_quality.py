#!/usr/bin/env python3
"""
On-demand batch quality assessment script.

This script can be run manually to assess quality for all cached datasets.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtester.services.quality_runner import run_full_assessment
import logging

# Setup logging
LOG_DIR = Path('artifacts/logs')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'quality_assessment.log'),
        logging.StreamHandler()
    ]
)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Assess data quality for all cached datasets')
    parser.add_argument('--full', action='store_true', 
                       help='Run full assessment with liveliness checks (default: incremental)')
    
    args = parser.parse_args()
    
    if args.full:
        print("Running FULL quality assessment (includes liveliness checks)...")
        result = run_full_assessment()
    else:
        print("Running incremental quality assessment (datasets updated today only)...")
        from services.quality_runner import run_incremental_assessment
        result = run_incremental_assessment()
    
    print(f"\n✓ Assessment complete: {result.get('assessed', 0)} datasets assessed")
    
    if result.get('failed', 0) > 0:
        print(f"✗ {result.get('failed', 0)} dataset(s) failed assessment")
        sys.exit(1)
    
    sys.exit(0)

