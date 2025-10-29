#!/usr/bin/env python3
"""
Gap analysis script.

Identifies all gaps across all cached datasets and generates
a refetch plan with priorities (largest gaps first).
"""

import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.cache_manager import load_manifest, read_cache
from data.validator import detect_gaps


def analyze_all_gaps(output_format: str = 'json') -> List[Dict[str, Any]]:
    """
    Analyze all gaps across all cached datasets.
    
    Args:
        output_format: Output format ('json' or 'csv')
    
    Returns:
        List of gap analysis dictionaries
    """
    manifest = load_manifest()
    
    if not manifest:
        print("No cached datasets found")
        return []
    
    all_gaps = []
    
    print(f"Analyzing gaps for {len(manifest)} datasets...")
    
    for key, entry in manifest.items():
        symbol = entry['symbol']
        timeframe = entry['timeframe']
        source_exchange = entry.get('source_exchange', 'unknown')
        
        # Read cached data
        df = read_cache(symbol, timeframe)
        
        if df.empty:
            continue
        
        # Detect gaps
        gaps = detect_gaps(df, timeframe)
        
        if gaps:
            for gap in gaps:
                gap_analysis = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'source_exchange': source_exchange,
                    'gap_start': gap['start'],
                    'gap_end': gap['end'],
                    'duration_seconds': gap['duration_seconds'],
                    'duration_hours': gap['duration_seconds'] / 3600,
                    'missing_candles': gap['missing_candles'],
                    'expected_candles': gap['expected_candles']
                }
                all_gaps.append(gap_analysis)
    
    # Sort by gap size (largest first)
    all_gaps.sort(key=lambda x: x['duration_seconds'], reverse=True)
    
    return all_gaps


def generate_refetch_plan(gaps: List[Dict[str, Any]], 
                         output_file: Optional[str] = None) -> None:
    """
    Generate refetch plan with priorities.
    
    Args:
        gaps: List of gap analysis dictionaries
        output_file: Output file path (optional, prints to stdout if None)
    """
    if not gaps:
        print("No gaps found")
        return
    
    print("\n" + "=" * 100)
    print("GAP REFETCH PLAN")
    print("=" * 100)
    print(f"\nTotal gaps found: {len(gaps)}")
    print(f"Total missing candles: {sum(g['missing_candles'] for g in gaps):,}")
    
    # Group by priority (large gaps >= 24h, small gaps < 24h)
    large_gaps = [g for g in gaps if g['duration_hours'] >= 24]
    small_gaps = [g for g in gaps if g['duration_hours'] < 24]
    
    print(f"\nLarge gaps (>=24h): {len(large_gaps)}")
    print(f"Small gaps (<24h): {len(small_gaps)}")
    
    print("\n" + "-" * 100)
    print("Top 20 Largest Gaps (Priority Order)")
    print("-" * 100)
    print(f"{'Symbol':<12} {'TF':<6} {'Start Date':<12} {'End Date':<12} {'Duration (h)':<12} "
          f"{'Missing':<10} {'Exchange':<10}")
    print("-" * 100)
    
    for gap in gaps[:20]:
        print(f"{gap['symbol']:<12} {gap['timeframe']:<6} "
              f"{gap['gap_start'][:10]:<12} {gap['gap_end'][:10]:<12} "
              f"{gap['duration_hours']:<12.2f} {gap['missing_candles']:<10,} "
              f"{gap['source_exchange']:<10}")
    
    # Save to file if requested
    if output_file:
        output_path = Path(output_file)
        if output_path.suffix == '.json':
            with open(output_path, 'w') as f:
                json.dump(gaps, f, indent=2)
            print(f"\n✓ Refetch plan saved to: {output_file}")
        elif output_path.suffix == '.csv':
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=gaps[0].keys())
                writer.writeheader()
                writer.writerows(gaps)
            print(f"\n✓ Refetch plan saved to: {output_file}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze gaps in cached data')
    parser.add_argument('--output', '-o', type=str, help='Output file path (JSON or CSV)')
    parser.add_argument('--format', choices=['json', 'csv'], default='json',
                       help='Output format (default: json)')
    
    args = parser.parse_args()
    
    gaps = analyze_all_gaps()
    
    if args.output:
        generate_refetch_plan(gaps, output_file=args.output)
    else:
        generate_refetch_plan(gaps)


if __name__ == '__main__':
    main()

