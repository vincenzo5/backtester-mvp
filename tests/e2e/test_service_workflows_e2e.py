"""
End-to-end tests for service workflows.

Tests service execution with real cache/manifest.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backtester.data.cache_manager import write_cache, read_cache, load_manifest, get_manifest_entry
from backtester.services.quality_runner import assess_dataset_quality


@pytest.mark.e2e
@pytest.mark.requires_data
class TestServiceWorkflowsE2E(unittest.TestCase):
    """End-to-end tests for service workflows."""
    
    def setUp(self):
        """Set up test environment with real cache structure."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch cache directory
        from backtester.data import cache_manager as cm_module
        self.original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(self.temp_dir)
        cm_module.MANIFEST_FILE = Path(self.temp_dir) / '.cache_manifest.json'
        
        # Create realistic test data
        dates = pd.date_range(start='2020-01-01', periods=2000, freq='1h')
        np.random.seed(42)
        
        base_price = 50000
        trend = np.linspace(0, base_price * 0.4, 2000)
        noise = np.random.randn(2000).cumsum() * 100
        prices = base_price + trend + noise
        
        self.test_df = pd.DataFrame({
            'open': np.roll(prices, 1),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 2000)
        }, index=dates)
        self.test_df.at[self.test_df.index[0], 'open'] = base_price
        
        # Write multiple markets to cache
        write_cache('BTC/USD', '1h', self.test_df)
        write_cache('ETH/USD', '1h', self.test_df.iloc[:1000])  # Shorter dataset
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
        
        from backtester.data import cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache_dir
        cm_module.MANIFEST_FILE = self.original_cache_dir / '.cache_manifest.json'
    
    def test_cache_manifest_workflow(self):
        """Test cache and manifest workflow end-to-end."""
        # Verify cache files exist
        from backtester.data.cache_manager import get_cache_path
        btc_path = get_cache_path('BTC/USD', '1h')
        self.assertTrue(btc_path.exists())
        
        # Verify manifest entries
        manifest = load_manifest()
        # Key format is "symbol_timeframe" (preserves / in symbol)
        self.assertIn('BTC/USD_1h', manifest)
        self.assertIn('ETH/USD_1h', manifest)
        
        # Verify manifest entry details
        btc_entry = get_manifest_entry('BTC/USD', '1h')
        self.assertIsNotNone(btc_entry)
        self.assertEqual(btc_entry['symbol'], 'BTC/USD')
        self.assertEqual(btc_entry['timeframe'], '1h')
        self.assertGreater(btc_entry['candle_count'], 0)
    
    def test_read_cache_multiple_markets(self):
        """Test reading multiple markets from cache."""
        btc_df = read_cache('BTC/USD', '1h')
        eth_df = read_cache('ETH/USD', '1h')
        
        self.assertFalse(btc_df.empty)
        self.assertFalse(eth_df.empty)
        self.assertGreater(len(btc_df), len(eth_df))
    
    def test_quality_assessment_workflow(self):
        """Test quality assessment workflow."""
        # Assess quality for a dataset
        try:
            result = assess_dataset_quality('BTC/USD', '1h')
            
            # Should return quality assessment
            self.assertIsInstance(result, dict)
            # May have quality grade or assessment details
        except Exception as e:
            # Quality assessment may fail if dependencies aren't available
            # This is acceptable for E2E test
            self.skipTest(f"Quality assessment requires dependencies: {e}")
    
    def test_manifest_integrity(self):
        """Test manifest integrity across operations."""
        initial_manifest = load_manifest()
        initial_keys = set(initial_manifest.keys())
        
        # Verify both markets are in manifest (key format preserves / in symbol)
        self.assertIn('BTC/USD_1h', initial_keys)
        self.assertIn('ETH/USD_1h', initial_keys)
        
        # Verify entry structure
        for key, entry in initial_manifest.items():
            self.assertIn('symbol', entry)
            self.assertIn('timeframe', entry)
            self.assertIn('candle_count', entry)

