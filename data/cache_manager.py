"""
Cache manager for data file I/O and manifest tracking.

This module handles reading/writing cache files with simplified naming
and manages the cache manifest for metadata tracking.
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


CACHE_DIR = Path('data/cache')
MANIFEST_FILE = CACHE_DIR / '.cache_manifest.json'


def ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(symbol: str, timeframe: str) -> Path:
    """
    Get cache file path for a symbol/timeframe combination.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        Path object to cache file
    """
    ensure_cache_dir()
    filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"
    return CACHE_DIR / filename


def read_cache(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Read cached data for a symbol/timeframe.
    
    STABLE API: This function signature and return format must remain unchanged
    to maintain compatibility between data collection and backtesting systems.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        DataFrame with datetime index and OHLCV columns (open, high, low, close, volume),
        or empty DataFrame if cache doesn't exist. Index must be DatetimeIndex.
    """
    cache_file = get_cache_path(symbol, timeframe)
    
    if not cache_file.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(cache_file, index_col='datetime', parse_dates=True)
        # Ensure datetime index is timezone-aware if it was written with timezone
        # This maintains compatibility with timezone-aware writes
        if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is None:
            # Try to infer UTC if no timezone (backward compatibility)
            pass  # Keep as-is for now, timezone handling handled elsewhere
        return df
    except Exception as e:
        # If file is corrupted, return empty DataFrame
        return pd.DataFrame()


def write_cache(symbol: str, timeframe: str, df: pd.DataFrame, source_exchange: Optional[str] = None):
    """
    Write data to cache file.
    
    STABLE API: This function signature and CSV format must remain unchanged.
    Cache files use CSV format with: datetime index and columns [open, high, low, close, volume]
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        df: DataFrame with OHLCV data (must have datetime index and OHLCV columns)
        source_exchange: Exchange name from which data was fetched (optional, stored in manifest only)
    
    Raises:
        ValueError: If DataFrame doesn't have DatetimeIndex
    """
    if df.empty:
        return
    
    cache_file = get_cache_path(symbol, timeframe)
    ensure_cache_dir()
    
    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have DatetimeIndex")
    
    # Name the index column for CSV compatibility
    df_with_named_index = df.copy()
    df_with_named_index.index.name = 'datetime'
    
    # Write to CSV
    df_with_named_index.to_csv(cache_file)
    
    # Update manifest
    update_manifest(symbol, timeframe, df, source_exchange=source_exchange)


def update_manifest(symbol: str, timeframe: str, df: pd.DataFrame, source_exchange: Optional[str] = None):
    """
    Update cache manifest with metadata for a symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        df: DataFrame with OHLCV data
        source_exchange: Exchange name from which data was fetched (optional)
    """
    ensure_cache_dir()
    
    # Load existing manifest
    manifest = load_manifest()
    
    # Calculate metadata
    if not df.empty and len(df) > 0:
        first_date = df.index.min().strftime('%Y-%m-%d')
        last_date = df.index.max().strftime('%Y-%m-%d')
        candle_count = len(df)
        last_updated = datetime.utcnow().isoformat() + 'Z'
    else:
        first_date = None
        last_date = None
        candle_count = 0
        last_updated = datetime.utcnow().isoformat() + 'Z'
    
    # Update manifest
    key = f"{symbol}_{timeframe}"
    manifest[key] = {
        'symbol': symbol,
        'timeframe': timeframe,
        'first_date': first_date,
        'last_date': last_date,
        'candle_count': candle_count,
        'last_updated': last_updated
    }
    
    # Add source_exchange if provided
    if source_exchange:
        manifest[key]['source_exchange'] = source_exchange
    
    # Save manifest
    save_manifest(manifest)


def load_manifest() -> Dict[str, Any]:
    """
    Load cache manifest from disk.
    
    Returns:
        Dictionary with cache metadata
    """
    if not MANIFEST_FILE.exists():
        return {}
    
    try:
        with open(MANIFEST_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_manifest(manifest: Dict[str, Any]):
    """Save cache manifest to disk."""
    ensure_cache_dir()
    
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2)


def get_manifest_entry(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Get manifest entry for a specific symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        Manifest entry dictionary or None if not found
    """
    manifest = load_manifest()
    key = f"{symbol}_{timeframe}"
    return manifest.get(key)


def get_last_cached_timestamp(symbol: str, timeframe: str) -> Optional[pd.Timestamp]:
    """
    Get the last cached timestamp for a symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        Last cached timestamp or None if cache doesn't exist
    """
    df = read_cache(symbol, timeframe)
    
    if df.empty or len(df) == 0:
        return None
    
    return df.index.max()


def cache_exists(symbol: str, timeframe: str) -> bool:
    """
    Check if cache file exists for a symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        True if cache file exists
    """
    cache_file = get_cache_path(symbol, timeframe)
    return cache_file.exists()


def delete_cache(symbol: str, timeframe: str):
    """
    Delete cache file and remove from manifest.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    """
    cache_file = get_cache_path(symbol, timeframe)
    
    if cache_file.exists():
        cache_file.unlink()
    
    # Remove from manifest
    manifest = load_manifest()
    key = f"{symbol}_{timeframe}"
    if key in manifest:
        del manifest[key]
        save_manifest(manifest)

