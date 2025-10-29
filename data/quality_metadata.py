"""
Quality metadata manager for storing detailed quality scores.

This module handles reading/writing detailed quality scores to a separate
metadata file, keeping the manifest lean while providing full quality details.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


QUALITY_METADATA_FILE = Path('data/quality_metadata.json')


def ensure_data_dir():
    """Ensure data directory exists."""
    QUALITY_METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_quality_metadata() -> Dict[str, Any]:
    """
    Load quality metadata from disk.
    
    Returns:
        Dictionary with quality metadata for all datasets
    """
    if not QUALITY_METADATA_FILE.exists():
        return {}
    
    try:
        with open(QUALITY_METADATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_quality_metadata(metadata: Dict[str, Any]):
    """Save quality metadata to disk."""
    ensure_data_dir()
    
    with open(QUALITY_METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def get_quality_key(symbol: str, timeframe: str) -> str:
    """
    Get metadata key for a symbol/timeframe combination.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        Key string (e.g., 'BTC/USD_1h')
    """
    return f"{symbol}_{timeframe}"


def save_quality_metadata_entry(symbol: str, timeframe: str, scores: Dict[str, Any],
                               market_status: Optional[Dict[str, Any]] = None,
                               assessment_details: Optional[Dict[str, Any]] = None):
    """
    Save quality metadata entry for a symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        scores: Component scores dictionary (should include composite and grade)
        market_status: Market liveliness status dictionary (optional)
        assessment_details: Detailed assessment results (gaps, outliers, etc.) (optional)
    """
    metadata = load_quality_metadata()
    key = get_quality_key(symbol, timeframe)
    
    entry = {
        'symbol': symbol,
        'timeframe': timeframe,
        'quality_scores': scores,
        'quality_assessment_date': datetime.utcnow().isoformat() + 'Z'
    }
    
    if market_status:
        entry['market_status'] = market_status
    
    if assessment_details:
        entry['assessment_details'] = assessment_details
    
    metadata[key] = entry
    save_quality_metadata(metadata)


def load_quality_metadata_entry(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Load quality metadata entry for a symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        Quality metadata dictionary or None if not found
    """
    metadata = load_quality_metadata()
    key = get_quality_key(symbol, timeframe)
    return metadata.get(key)


def load_all_quality_metadata() -> Dict[str, Any]:
    """
    Load all quality metadata.
    
    Returns:
        Dictionary with all quality metadata entries
    """
    return load_quality_metadata()


def delete_quality_metadata_entry(symbol: str, timeframe: str):
    """
    Delete quality metadata entry for a symbol/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    """
    metadata = load_quality_metadata()
    key = get_quality_key(symbol, timeframe)
    
    if key in metadata:
        del metadata[key]
        save_quality_metadata(metadata)

