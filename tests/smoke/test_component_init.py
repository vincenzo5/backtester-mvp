"""
Smoke tests for component initialization.

Validates that components can be instantiated and basic operations work.
"""

import pytest
import unittest
import pandas as pd
import tempfile
import os
import shutil
import json
from pathlib import Path


@pytest.mark.smoke
class TestComponentInitialization(unittest.TestCase):
    """Test component initialization and basic operations."""
    
    def setUp(self):
        """Set up temporary cache directory for cache tests."""
        self.temp_cache_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary cache directory."""
        if hasattr(self, 'temp_cache_dir') and os.path.exists(self.temp_cache_dir):
            shutil.rmtree(self.temp_cache_dir)
    
    def test_strategy_class_loading(self):
        """Test strategy classes can be loaded."""
        from backtester.strategies import get_strategy_class
        
        # Test valid strategy names
        sma_cross_class = get_strategy_class('sma_cross')
        self.assertIsNotNone(sma_cross_class)
        self.assertTrue(hasattr(sma_cross_class, 'get_required_indicators'))
        
        rsi_sma_class = get_strategy_class('rsi_sma')
        self.assertIsNotNone(rsi_sma_class)
        self.assertTrue(hasattr(rsi_sma_class, 'get_required_indicators'))
    
    def test_invalid_strategy_name(self):
        """Test invalid strategy name raises helpful error."""
        from backtester.strategies import get_strategy_class
        
        with self.assertRaises(ValueError) as context:
            get_strategy_class('nonexistent_strategy')
        
        error_message = str(context.exception)
        self.assertIn('nonexistent_strategy', error_message)
        self.assertIn('Available strategies', error_message)
    
    def test_cache_manager_write_read(self):
        """Test cache manager can write and read cache files."""
        from backtester.data.cache_manager import write_cache, read_cache
        
        cache_dir = self.temp_cache_dir
        
        # Create sample OHLCV data
        dates = pd.date_range('2024-01-01', periods=10, freq='1h')
        df = pd.DataFrame({
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'volume': [1000000] * 10
        }, index=dates)
        
        # Patch cache directory for this test
        from backtester.data import cache_manager as cm_module
        original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(cache_dir)
        cm_module.MANIFEST_FILE = Path(cache_dir) / '.cache_manifest.json'
        
        try:
            # Write cache
            write_cache('TEST/USD', '1h', df)
            
            # Read cache back
            read_df = read_cache('TEST/USD', '1h')
            self.assertFalse(read_df.empty)
            self.assertEqual(len(read_df), 10)
            self.assertIn('close', read_df.columns)
        finally:
            # Restore original cache directory
            cm_module.CACHE_DIR = original_cache_dir
            cm_module.MANIFEST_FILE = original_cache_dir / '.cache_manifest.json'
    
    def test_cache_manager_nonexistent_cache(self):
        """Test cache manager returns empty DataFrame for non-existent cache."""
        from backtester.data.cache_manager import read_cache
        
        cache_dir = self.temp_cache_dir
        
        # Patch cache directory
        from backtester.data import cache_manager as cm_module
        original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(cache_dir)
        cm_module.MANIFEST_FILE = Path(cache_dir) / '.cache_manifest.json'
        
        try:
            # Try to read non-existent cache
            df = read_cache('NONEXISTENT/USD', '1h')
            self.assertIsInstance(df, pd.DataFrame)
            self.assertTrue(df.empty)
        finally:
            # Restore original cache directory
            cm_module.CACHE_DIR = original_cache_dir
            cm_module.MANIFEST_FILE = original_cache_dir / '.cache_manifest.json'
    
    def test_cli_parser(self):
        """Test CLI parser can parse arguments."""
        from backtester.cli.parser import parse_arguments
        import sys
        from unittest.mock import patch
        
        # Test default parsing (no args)
        with patch.object(sys, 'argv', ['test_script']):
            args = parse_arguments()
            self.assertIsNotNone(args)
            self.assertFalse(args.quick)
            self.assertIsNone(args.profile)
        
        # Test --quick flag
        with patch.object(sys, 'argv', ['test_script', '--quick']):
            args = parse_arguments()
            self.assertIsNotNone(args)
            self.assertTrue(args.quick)
            self.assertEqual(args.profile, 'quick')

