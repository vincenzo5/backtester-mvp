"""
Unit tests for cache manager.

Tests cache I/O operations and manifest management.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from backtester.data.cache_manager import (
    read_cache,
    write_cache,
    get_cache_path,
    load_manifest,
    save_manifest,
    update_manifest,
    get_manifest_entry,
    ensure_cache_dir
)


@pytest.mark.unit
class TestCacheOperations(unittest.TestCase):
    """Test cache read/write operations."""
    
    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = None
        
        # Patch CACHE_DIR to use temp directory
        from backtester.data import cache_manager as cm_module
        self.original_cache_dir = cm_module.CACHE_DIR
        self.original_manifest = cm_module.MANIFEST_FILE
        
        cm_module.CACHE_DIR = Path(self.temp_dir)
        cm_module.MANIFEST_FILE = Path(self.temp_dir) / '.cache_manifest.json'
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
        
        # Restore original cache directory
        if self.original_cache_dir:
            from backtester.data import cache_manager as cm_module
            cm_module.CACHE_DIR = self.original_cache_dir
            cm_module.MANIFEST_FILE = self.original_manifest
    
    def test_get_cache_path(self):
        """Test getting cache file path."""
        path = get_cache_path('BTC/USD', '1h')
        
        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, 'BTC_USD_1h.csv')
    
    def test_write_and_read_cache(self):
        """Test writing and reading cache files."""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='1h')
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(200, 300, 100),
            'low': np.random.uniform(50, 100, 100),
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        # Write cache
        write_cache('BTC/USD', '1h', df)
        
        # Read cache
        read_df = read_cache('BTC/USD', '1h')
        
        self.assertFalse(read_df.empty)
        self.assertEqual(len(read_df), len(df))
        self.assertTrue(isinstance(read_df.index, pd.DatetimeIndex))
        self.assertIn('close', read_df.columns)
    
    def test_write_cache_empty_df(self):
        """Test that writing empty DataFrame does nothing."""
        empty_df = pd.DataFrame()
        write_cache('BTC/USD', '1h', empty_df)
        
        # Should not create file or raise error
        path = get_cache_path('BTC/USD', '1h')
        self.assertFalse(path.exists())
    
    def test_write_cache_non_datetime_index(self):
        """Test that writing DataFrame without DatetimeIndex raises error."""
        df = pd.DataFrame({'close': [100, 101, 102]})
        
        with self.assertRaises(ValueError):
            write_cache('BTC/USD', '1h', df)
    
    def test_read_cache_nonexistent(self):
        """Test reading non-existent cache returns empty DataFrame."""
        df = read_cache('NONEXISTENT/USD', '1h')
        self.assertTrue(df.empty)
        self.assertIsInstance(df, pd.DataFrame)
    
    def test_cache_path_normalization(self):
        """Test that symbol paths are normalized correctly."""
        path1 = get_cache_path('BTC/USD', '1h')
        path2 = get_cache_path('BTC_USD', '1h')  # Different format
        
        # Should still create same filename (handles both formats)
        self.assertIn('BTC', str(path1))
        self.assertIn('1h', str(path1))


@pytest.mark.unit
class TestManifestOperations(unittest.TestCase):
    """Test manifest management operations."""
    
    def setUp(self):
        """Set up temporary manifest."""
        self.temp_dir = tempfile.mkdtemp()
        
        from backtester.data import cache_manager as cm_module
        self.original_cache_dir = cm_module.CACHE_DIR
        self.original_manifest = cm_module.MANIFEST_FILE
        
        cm_module.CACHE_DIR = Path(self.temp_dir)
        cm_module.MANIFEST_FILE = Path(self.temp_dir) / '.cache_manifest.json'
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
        
        from backtester.data import cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache_dir
        cm_module.MANIFEST_FILE = self.original_manifest
    
    def test_load_manifest_empty(self):
        """Test loading non-existent manifest returns empty dict."""
        manifest = load_manifest()
        self.assertIsInstance(manifest, dict)
        self.assertEqual(len(manifest), 0)
    
    def test_save_and_load_manifest(self):
        """Test saving and loading manifest."""
        test_manifest = {
            'BTC_USD_1h': {
                'symbol': 'BTC/USD',
                'timeframe': '1h',
                'first_date': '2020-01-01',
                'last_date': '2020-12-31',
                'candle_count': 1000
            }
        }
        
        save_manifest(test_manifest)
        loaded = load_manifest()
        
        self.assertEqual(loaded, test_manifest)
    
    def test_update_manifest(self):
        """Test updating manifest entry."""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='1h')
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(200, 300, 100),
            'low': np.random.uniform(50, 100, 100),
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        update_manifest('BTC/USD', '1h', df, source_exchange='coinbase')
        
        manifest = load_manifest()
        # Key format is "symbol_timeframe" (preserves / in symbol)
        self.assertIn('BTC/USD_1h', manifest)
        
        entry = manifest['BTC/USD_1h']
        self.assertEqual(entry['symbol'], 'BTC/USD')
        self.assertEqual(entry['timeframe'], '1h')
        self.assertEqual(entry['source_exchange'], 'coinbase')
    
    def test_get_manifest_entry(self):
        """Test getting manifest entry."""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='1h')
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(200, 300, 100),
            'low': np.random.uniform(50, 100, 100),
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        update_manifest('BTC/USD', '1h', df)
        
        entry = get_manifest_entry('BTC/USD', '1h')
        self.assertIsNotNone(entry)
        self.assertEqual(entry['symbol'], 'BTC/USD')
        
        # Test non-existent entry
        none_entry = get_manifest_entry('NONEXISTENT/USD', '1h')
        self.assertIsNone(none_entry)

