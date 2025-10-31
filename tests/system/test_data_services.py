"""
System tests for data services.

Tests update_runner, quality_runner, and gap_filling_runner.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from backtester.data.cache_manager import write_cache, load_manifest
from backtester.services.update_runner import get_markets_to_update
from backtester.services.quality_runner import get_datasets_updated_today
from backtester.services.gap_filling_runner import run_gap_filling


@pytest.mark.system
class TestDataServices(unittest.TestCase):
    """Test data service runners."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch cache directory
        from backtester.data import cache_manager as cm_module
        self.original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(self.temp_dir)
        cm_module.MANIFEST_FILE = Path(self.temp_dir) / '.cache_manifest.json'
        
        # Create test data
        dates = pd.date_range(start='2020-01-01', periods=100, freq='1h')
        np.random.seed(42)
        
        prices = 50000 + np.random.randn(100).cumsum() * 100
        
        self.test_df = pd.DataFrame({
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        write_cache('BTC/USD', '1h', self.test_df)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
        
        from backtester.data import cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache_dir
        cm_module.MANIFEST_FILE = self.original_cache_dir / '.cache_manifest.json'
    
    def test_get_markets_to_update(self):
        """Test getting markets that need updating."""
        metadata = {
            'exchanges': {
                'coinbase': {
                    'markets': {
                        'BTC/USD': {
                            'timeframes': ['1h'],
                            'liveliness': {'status': 'live', 'verified_date': '2024-01-01'}
                        }
                    }
                }
            }
        }
        
        markets = get_markets_to_update(metadata)
        
        # Should return list of tuples
        self.assertIsInstance(markets, list)
        # Each entry should be (symbol, timeframe) tuple
        for market in markets:
            self.assertIsInstance(market, tuple)
            self.assertEqual(len(market), 2)
    
    def test_get_datasets_updated_today(self):
        """Test getting datasets updated today."""
        # Get datasets updated today (may be empty if none updated)
        datasets = get_datasets_updated_today()
        
        self.assertIsInstance(datasets, list)
        # Each entry should be (symbol, timeframe) tuple
        for dataset in datasets:
            self.assertIsInstance(dataset, tuple)
            self.assertEqual(len(dataset), 2)
    
    @patch('backtester.services.gap_filling_runner.analyze_all_gaps')
    def test_gap_filling_runner_interface(self, mock_analyze):
        """Test gap filling runner interface."""
        # Mock gap analysis to return empty list (no gaps)
        mock_analyze.return_value = []
        
        # Run gap filling
        result = run_gap_filling(priority='largest', max_gaps=None)
        
        # Should return summary dict
        self.assertIsInstance(result, dict)
        # Should have summary fields - check for actual keys in result
        self.assertIn('gaps_found', result)
        self.assertIn('gaps_filled', result)

