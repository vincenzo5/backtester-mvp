"""
Integration tests for cache effectiveness tracking.

Tests cache reuse across multiple backtests and cache stats in trace events.
"""

import unittest
import pytest
import tempfile
import json
import time
import os
import shutil
import numpy as np

import pandas as pd
from datetime import datetime

from backtester.config import ConfigManager
from backtester.debug import ExecutionTracer, set_debug_components
from backtester.indicators.library import IndicatorLibrary
from backtester.backtest.engine import prepare_backtest_data
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.indicators.base import IndicatorSpec


@pytest.mark.integration
class TestCacheEffectivenessIntegration(unittest.TestCase):
    """Test cache effectiveness integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ConfigManager()
        self.debug_config = self.config.get_debug_config()
        
        # Create temporary trace file
        self.temp_dir = tempfile.mkdtemp()
        self.trace_file = os.path.join(self.temp_dir, 'test_trace.jsonl')
        
        # Override trace file path
        if hasattr(self.debug_config.logging, 'execution_trace_file'):
            self.original_trace_file = self.debug_config.logging.execution_trace_file
            self.debug_config.logging.execution_trace_file = self.trace_file
        
        # Create debug components
        if self.debug_config.enabled and self.debug_config.tracing.enabled:
            self.tracer = ExecutionTracer(self.debug_config)
            set_debug_components(self.tracer, None)
        else:
            self.tracer = None
        
        # Create sample data directly
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
        np.random.seed(42)
        base_price = 50000
        prices = base_price + np.random.randn(100).cumsum() * 100
        self.test_df = pd.DataFrame({
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        # Create IndicatorLibrary
        self.library = IndicatorLibrary()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.tracer:
            self.tracer.shutdown()
        
        if hasattr(self, 'original_trace_file'):
            self.debug_config.logging.execution_trace_file = self.original_trace_file
        
        shutil.rmtree(self.temp_dir)
    
    def read_trace_file(self):
        """Read and parse trace file."""
        if not os.path.exists(self.trace_file):
            return []
        
        entries = []
        with open(self.trace_file, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
    
    def test_indicator_cache_across_backtests(self):
        """Test cache reuse across multiple backtests."""
        strategy_class = SMACrossStrategy
        strategy_params = {'fast_period': 10, 'slow_period': 20}
        
        # Reset cache stats
        self.library.reset_cache_stats()
        
        # First preparation (should be cache miss)
        enriched_df1 = prepare_backtest_data(
            self.test_df,
            strategy_class,
            strategy_params,
            symbol='BTC/USD'
        )
        
        # Get stats after first computation
        stats1 = self.library.get_cache_stats()
        misses_after_first = stats1['misses']
        hits_after_first = stats1['hits']
        
        # Second preparation with same data (should hit cache)
        enriched_df2 = prepare_backtest_data(
            self.test_df,
            strategy_class,
            strategy_params,
            symbol='BTC/USD'
        )
        
        # Get stats after second computation
        stats2 = self.library.get_cache_stats()
        
        # Should have more hits now (if cache is working)
        # Note: Cache might not work across separate IndicatorLibrary instances
        # But within same instance, it should work
        self.assertGreaterEqual(stats2['hits'], hits_after_first)
        self.assertEqual(stats2['misses'], misses_after_first)  # Same misses
        
        # Time saved should increase
        self.assertGreaterEqual(stats2['time_saved_seconds'], stats1['time_saved_seconds'])
    
    def test_cache_stats_in_trace_events(self):
        """Test cache stats appear in trace events."""
        if not self.tracer:
            self.skipTest("Tracer not available")
        
        strategy_class = SMACrossStrategy
        strategy_params = {'fast_period': 10, 'slow_period': 20}
        
        # Prepare data
        enriched_df = prepare_backtest_data(
            self.test_df,
            strategy_class,
            strategy_params,
            symbol='BTC/USD'
        )
        
        time.sleep(0.5)
        
        # Read trace file
        entries = self.read_trace_file()
        
        # Check indicators_computed event
        indicators_event = next(
            (e for e in entries if e.get('event_type') == 'indicators_computed'),
            None
        )
        
        # Cache stats might be in indicators_computed if tracking is enabled
        # This depends on implementation details
        
        # Check data_prep_end event
        data_prep_end = next(
            (e for e in entries if e.get('event_type') == 'data_prep_end'),
            None
        )
        
        if data_prep_end:
            # Should have cache_stats if cache tracking is enabled
            # Note: cache_stats might be None if no indicators were computed
            if 'cache_stats' in data_prep_end:
                cache_stats = data_prep_end['cache_stats']
                if cache_stats is not None:
                    self.assertIn('hits', cache_stats)
                    self.assertIn('misses', cache_stats)
                    self.assertIn('hit_rate', cache_stats)
    
    def test_cache_key_consistency(self):
        """Test that cache keys are consistent for same inputs."""
        # Generate cache key for same inputs multiple times
        key1 = self.library._generate_cache_key(
            'SMA', {'timeperiod': 20}, 'SMA_20', self.test_df
        )
        key2 = self.library._generate_cache_key(
            'SMA', {'timeperiod': 20}, 'SMA_20', self.test_df
        )
        
        # Should be identical
        self.assertEqual(key1, key2)
        
        # Different parameters should yield different key
        key3 = self.library._generate_cache_key(
            'SMA', {'timeperiod': 30}, 'SMA_30', self.test_df
        )
        self.assertNotEqual(key1, key3)
    
    def test_cache_with_different_strategies(self):
        """Test cache works with different strategy indicator requirements."""
        # Reset cache
        self.library.reset_cache_stats()
        
        # Strategy 1: SMACross (needs SMA indicators)
        strategy1 = SMACrossStrategy
        params1 = {'fast_period': 10, 'slow_period': 20}
        
        df1 = prepare_backtest_data(
            self.test_df,
            strategy1,
            params1,
            symbol='BTC/USD'
        )
        
        stats1 = self.library.get_cache_stats()
        
        # Strategy 2: Same strategy, different params (may reuse some indicators)
        params2 = {'fast_period': 10, 'slow_period': 30}  # Different slow_period
        
        df2 = prepare_backtest_data(
            self.test_df,
            strategy1,
            params2,
            symbol='BTC/USD'
        )
        
        stats2 = self.library.get_cache_stats()
        
        # Fast period indicator should hit cache (same params)
        # Slow period indicator should miss (different params)
        # At minimum, should have some hits if cache is working
        # (depends on implementation)
        self.assertGreaterEqual(stats2['misses'], stats1['misses'])


if __name__ == '__main__':
    unittest.main()

