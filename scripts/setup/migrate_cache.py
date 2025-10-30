"""
Migration script to rename existing cache files to simplified naming.

This script migrates cache files from:
  BTC_USD_1h_2017-01-01_2025-10-27.csv
To:
  BTC_USD_1h.csv

And generates the initial cache manifest.
"""

import os
import re
from pathlib import Path
import pandas as pd
from datetime import datetime

from backtester.data.cache_manager import ensure_cache_dir, get_cache_path, load_manifest, save_manifest, write_cache


def migrate_cache_files():
    """Migrate all cache files to simplified naming."""
    cache_dir = Path(Path(__file__).parent.parent.parent / 'data')
    
    if not cache_dir.exists():
        print("Cache directory doesn't exist. Nothing to migrate.")
        return
    
    # Pattern to match old filename format: SYMBOL_TIMEFRAME_START_END.csv
    pattern = re.compile(r'^(.+?)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv$')
    
    migrated = 0
    skipped = 0
    errors = 0
    
    print("=" * 80)
    print("Cache Migration Script")
    print("=" * 80)
    print()
    
    for file_path in cache_dir.glob('*.csv'):
        # Skip manifest file
        if file_path.name.startswith('.'):
            continue
        
        # Check if already in new format (doesn't match pattern)
        match = pattern.match(file_path.name)
        if not match:
            print(f"Skipping (already new format): {file_path.name}")
            skipped += 1
            continue
        
        # Extract symbol and timeframe from old filename
        # Pattern matches: SYMBOL_TIMEFRAME_START_END.csv
        # Need to figure out where timeframe ends and dates begin
        full_name = match.group(1)  # Everything before dates
        
        # Split by underscore and work backwards
        parts = full_name.split('_')
        # Last part before dates is timeframe (1m, 5m, 1h, 1d, etc.)
        # Everything before that is symbol
        
        # Try to identify timeframe (it's usually a short pattern like 1m, 5m, 1h, 1d, 6h, etc.)
        timeframe_pattern = re.compile(r'^(\d+[mhdwM]|1d|1w|1M)$')
        
        symbol_parts = []
        timeframe = None
        
        # Work backwards to find timeframe
        for i in range(len(parts) - 1, -1, -1):
            if timeframe_pattern.match(parts[i]):
                timeframe = parts[i]
                symbol_parts = parts[:i]
                break
        
        if not timeframe:
            print(f"⚠️  Could not parse timeframe from: {file_path.name}")
            errors += 1
            continue
        
        symbol = '_'.join(symbol_parts).replace('_', '/')
        
        # Check if new format file already exists
        new_path = get_cache_path(symbol, timeframe)
        
        if new_path.exists():
            print(f"⚠️  New format file already exists, skipping: {file_path.name} → {new_path.name}")
            skipped += 1
            continue
        
        # Read old file and write to new location
        try:
            df = pd.read_csv(file_path, index_col='datetime', parse_dates=True)
            
            if df.empty:
                print(f"⚠️  Empty file, skipping: {file_path.name}")
                skipped += 1
                continue
            
            # Write to new location (this also updates manifest)
            from data.cache_manager import write_cache
            write_cache(symbol, timeframe, df)
            
            # Delete old file
            file_path.unlink()
            
            print(f"✓ Migrated: {file_path.name} → {new_path.name} ({len(df):,} candles)")
            migrated += 1
            
        except Exception as e:
            print(f"✗ Error migrating {file_path.name}: {e}")
            errors += 1
    
    print()
    print("=" * 80)
    print("Migration Summary")
    print("=" * 80)
    print(f"Migrated: {migrated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print("=" * 80)
    
    # Regenerate manifest from all files if needed
    print()
    print("Regenerating manifest from all cache files...")
    regenerate_manifest()
    print("✓ Manifest updated")


def regenerate_manifest():
    """Regenerate manifest from all cache files in directory."""
    cache_dir = Path(Path(__file__).parent.parent.parent / 'data')
    manifest = {}
    
    # Pattern for new format: SYMBOL_TIMEFRAME.csv
    # Need to extract symbol and timeframe
    for file_path in cache_dir.glob('*.csv'):
        if file_path.name.startswith('.'):  # Skip manifest
            continue
        
        try:
            # Read file to get metadata
            df = pd.read_csv(file_path, index_col='datetime', parse_dates=True)
            
            if df.empty:
                continue
            
            # Parse symbol and timeframe from filename
            # Format: SYMBOL_TIMEFRAME.csv
            name_parts = file_path.stem.split('_')
            
            # Find timeframe (last part should match timeframe pattern)
            timeframe_pattern = re.compile(r'^(\d+[mhdwM]|1d|1w|1M)$')
            
            symbol_parts = []
            timeframe = None
            
            for i in range(len(name_parts) - 1, -1, -1):
                if timeframe_pattern.match(name_parts[i]):
                    timeframe = name_parts[i]
                    symbol_parts = name_parts[:i]
                    break
            
            if not timeframe:
                continue
            
            symbol = '_'.join(symbol_parts).replace('_', '/')
            
            # Create manifest entry
            key = f"{symbol}_{timeframe}"
            manifest[key] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'first_date': df.index.min().strftime('%Y-%m-%d'),
                'last_date': df.index.max().strftime('%Y-%m-%d'),
                'candle_count': len(df),
                'last_updated': datetime.utcnow().isoformat() + 'Z'
            }
        
        except Exception as e:
            print(f"⚠️  Error processing {file_path.name}: {e}")
    
    # Save manifest
    save_manifest(manifest)


if __name__ == '__main__':
    migrate_cache_files()

