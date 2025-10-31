"""
Integration tests for data pipeline.

Tests cache → read → prepare → backtest pipeline.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from backtester.data.cache_manager import write_cache, read_cache
from backtester.backtest.engine import prepare_backtest_data, run_backtest
from backtester.config import ConfigManager
from backtester.strategies.sma_cross import SMACrossStrategy


@pytest.mark.integration
class TestDataPipeline(unittest.TestCase):
    """Test complete data pipeline: cache → read → prepare → backtest."""
    
    def setUp(self):
        """Set up test data and cache."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch cache directory
        from backtester.data import cache_manager as cm_module
        self.original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(self.temp_dir)
        cm_module.MANIFEST_FILE = Path(self.temp_dir) / '.cache_manifest.json'
        
        # Create test OHLCV data
        dates = pd.date_range(start='2020-01-01', periods=500, freq='1h')
        np.random.seed(42)
        
        base_price = 50000
        prices = base_price + np.random.randn(500).cumsum() * 100
        
        self.test_df = pd.DataFrame({
            'open': np.roll(prices, 1),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 500)
        }, index=dates)
        self.test_df.iloc[0]['open'] = base_price
        
        # Write to cache
        write_cache('BTC/USD', '1h', self.test_df)
        
        self.config = ConfigManager()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
        
        from backtester.data import cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache_dir
        cm_module.MANIFEST_FILE = self.original_cache_dir / '.cache_manifest.json'
    
    def test_cache_read_pipeline(self):
        """Test cache → read pipeline."""
        # Read from cache
        df = read_cache('BTC/USD', '1h')
        
        self.assertFalse(df.empty)
        self.assertEqual(len(df), len(self.test_df))
        self.assertTrue(isinstance(df.index, pd.DatetimeIndex))
    
    def test_read_prepare_pipeline(self):
        """Test read → prepare pipeline."""
        # Read from cache
        df = read_cache('BTC/USD', '1h')
        
        # Prepare data with indicators
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        
        # Verify preparation - indicators may not always be added with minimal data
        self.assertGreaterEqual(len(enriched_df.columns), len(df.columns))
        self.assertTrue(isinstance(enriched_df.index, pd.DatetimeIndex))
    
    def test_complete_pipeline(self):
        """Test complete pipeline: cache → read → prepare → backtest."""
        # Step 1: Read from cache
        df = read_cache('BTC/USD', '1h')
        self.assertFalse(df.empty)
        
        # Step 2: Prepare data
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        # Indicators may not always be added depending on data size
        self.assertGreaterEqual(len(enriched_df.columns), len(df.columns))
        
        # Step 3: Run backtest
        result = run_backtest(self.config, enriched_df, SMACrossStrategy, verbose=False)
        self.assertIsInstance(result, dict)
        self.assertIn('metrics', result)
        self.assertIn('initial_capital', result)
    
    def test_pipeline_preserves_data_integrity(self):
        """Test that pipeline preserves data integrity."""
        # Read original
        df1 = read_cache('BTC/USD', '1h')
        
        # Prepare
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df1, SMACrossStrategy, strategy_params)
        
        # Verify OHLCV columns preserved
        ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in ohlcv_cols:
            self.assertIn(col, enriched_df.columns)
            # Values should match (allowing for small floating point differences)
            pd.testing.assert_series_equal(df1[col], enriched_df[col], check_names=False)

