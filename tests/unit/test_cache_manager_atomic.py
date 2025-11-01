"""
Unit tests for atomic writes in cache manager.

Verifies that cache CSV and manifest writes are atomic and result in
consistent, readable files.
"""

import os
import json
import pytest
from pathlib import Path

from backtester.data import cache_manager as cm


@pytest.mark.unit
def test_write_cache_atomic(temp_cache_dir, sample_ohlcv_data):
    """Write cache and verify file exists, readable, and no temp files remain."""
    # Redirect cache directory to temporary location
    original_cache_dir = cm.CACHE_DIR
    try:
        cm.CACHE_DIR = Path(temp_cache_dir)

        # Prepare small dataset
        df = sample_ohlcv_data(num_candles=10, frequency='1h')

        # Write cache
        cm.write_cache('TEST/USD', '1h', df)

        # Verify cache file exists and is readable
        cache_path = cm.get_cache_path('TEST/USD', '1h')
        assert cache_path.exists()

        read_df = cm.read_cache('TEST/USD', '1h')
        assert not read_df.empty
        assert len(read_df) == len(df)

        # Ensure no leftover temp files in directory
        tmp_files = list(Path(temp_cache_dir).glob('*.tmp'))
        assert len(tmp_files) == 0
    finally:
        cm.CACHE_DIR = original_cache_dir


@pytest.mark.unit
def test_save_manifest_atomic(temp_cache_dir):
    """Multiple manifest writes produce valid JSON with expected keys."""
    original_cache_dir = cm.CACHE_DIR
    try:
        cm.CACHE_DIR = Path(temp_cache_dir)
        manifest_path = cm.MANIFEST_FILE

        # First write
        cm.save_manifest({'foo': {'a': 1}})
        with open(manifest_path, 'r') as f:
            data1 = json.load(f)
        assert 'foo' in data1

        # Second write with different content
        cm.save_manifest({'bar': {'b': 2}})
        with open(manifest_path, 'r') as f:
            data2 = json.load(f)
        assert 'bar' in data2 and 'foo' not in data2

        # Ensure no temporary file is left behind
        assert not any(p.suffix == '.tmp' for p in Path(temp_cache_dir).iterdir())
    finally:
        cm.CACHE_DIR = original_cache_dir


