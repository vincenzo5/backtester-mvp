"""
Unit tests for IndicatorLibrary cache effectiveness tracking.

Tests cache hit/miss tracking, time saved calculation, and cache statistics.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
import time

from backtester.indicators.library import IndicatorLibrary
from backtester.indicators.base import IndicatorSpec


@pytest.mark.unit
class TestIndicatorCacheTracking(unittest.TestCase):
    """Test IndicatorLibrary cache effectiveness tracking."""
    
    def setUp(self):
        """Set up test data."""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='1h')
        np.random.seed(42)
        
        base_price = 50000
        prices = base_price + np.random.randn(100).cumsum() * 100
        
        self.df = pd.DataFrame({
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        self.library = IndicatorLibrary()
    
    def test_cache_stats_initialization(self):
        """Test _cache_stats initialized correctly."""
        lib = IndicatorLibrary()
        
        self.assertTrue(hasattr(lib, '_cache_stats'))
        self.assertIn('hits', lib._cache_stats)
        self.assertIn('misses', lib._cache_stats)
        self.assertIn('computations', lib._cache_stats)
        self.assertIn('time_saved_seconds', lib._cache_stats)
        
        # Initial values should be zero
        self.assertEqual(lib._cache_stats['hits'], 0)
        self.assertEqual(lib._cache_stats['misses'], 0)
        self.assertEqual(lib._cache_stats['computations'], 0)
        self.assertEqual(lib._cache_stats['time_saved_seconds'], 0.0)
    
    def test_compute_indicator_without_tracking(self):
        """Test compute_indicator default behavior (no tracking)."""
        result1 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=False
        )
        
        # Compute same indicator again
        result2 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=False
        )
        
        # Stats should remain at zero
        stats = self.library.get_cache_stats()
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['total_requests'], 0)
    
    def test_compute_indicator_with_tracking_cache_miss(self):
        """Test compute_indicator with tracking - cache miss."""
        # Reset stats
        self.library.reset_cache_stats()
        
        result = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        stats = self.library.get_cache_stats()
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['hits'], 0)
        self.assertGreater(stats['time_saved_seconds'], 0.0)
    
    def test_compute_indicator_with_tracking_cache_hit(self):
        """Test compute_indicator with tracking - cache hit."""
        # Reset stats
        self.library.reset_cache_stats()
        
        # First computation (cache miss)
        result1 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        # Second computation with same parameters (cache hit)
        result2 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        stats = self.library.get_cache_stats()
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['hits'], 1)
        self.assertGreater(stats['time_saved_seconds'], 0.0)
        
        # Results should be equal (cached)
        pd.testing.assert_series_equal(result1, result2)
    
    def test_compute_indicator_different_parameters(self):
        """Test that different parameters create different cache entries."""
        self.library.reset_cache_stats()
        
        # Compute with different timeperiod
        result1 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        result2 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 30}, 'SMA_30',
            track_performance=True
        )
        
        stats = self.library.get_cache_stats()
        # Should be 2 misses (different parameters)
        self.assertEqual(stats['misses'], 2)
        self.assertEqual(stats['hits'], 0)
    
    def test_compute_indicator_different_data(self):
        """Test that different data creates different cache entries."""
        self.library.reset_cache_stats()
        
        # Compute with original data
        result1 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        # Create data with different index range (this changes the fingerprint)
        # The cache key uses first/last index, so different index = different key
        dates = pd.date_range(start='2021-01-01', periods=100, freq='1h')
        df2 = self.df.copy()
        df2.index = dates  # Different date range = different fingerprint
        
        result2 = self.library.compute_indicator(
            df2, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        stats = self.library.get_cache_stats()
        # Should be 2 misses (different data fingerprint due to different index)
        self.assertEqual(stats['misses'], 2)
        self.assertEqual(stats['hits'], 0)
    
    def test_generate_cache_key(self):
        """Test _generate_cache_key creates unique keys."""
        key1 = self.library._generate_cache_key('SMA', {'timeperiod': 20}, 'SMA_20', self.df)
        key2 = self.library._generate_cache_key('SMA', {'timeperiod': 30}, 'SMA_30', self.df)
        key3 = self.library._generate_cache_key('SMA', {'timeperiod': 20}, 'SMA_20', self.df)
        
        # Different parameters should yield different keys
        self.assertNotEqual(key1, key2)
        
        # Same parameters should yield same key
        self.assertEqual(key1, key3)
        
        # Keys should be strings
        self.assertIsInstance(key1, str)
        self.assertIsInstance(key2, str)
    
    def test_generate_cache_key_empty_dataframe(self):
        """Test _generate_cache_key handles empty DataFrame."""
        empty_df = pd.DataFrame()
        key = self.library._generate_cache_key('SMA', {'timeperiod': 20}, 'SMA_20', empty_df)
        
        self.assertIn('empty', key)
        self.assertIsInstance(key, str)
    
    def test_get_cache_stats_structure(self):
        """Test get_cache_stats returns correct structure."""
        self.library.reset_cache_stats()
        
        stats = self.library.get_cache_stats()
        
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('hit_rate', stats)
        self.assertIn('total_requests', stats)
        self.assertIn('time_saved_seconds', stats)
        
        # Initial stats
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['total_requests'], 0)
        self.assertEqual(stats['hit_rate'], 0.0)
        self.assertEqual(stats['time_saved_seconds'], 0.0)
    
    def test_get_cache_stats_hit_rate(self):
        """Test get_cache_stats calculates hit rate correctly."""
        self.library.reset_cache_stats()
        
        # Compute twice (1 miss, 1 hit)
        self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        stats = self.library.get_cache_stats()
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['total_requests'], 2)
        self.assertEqual(stats['hit_rate'], 0.5)
    
    def test_reset_cache_stats(self):
        """Test reset_cache_stats clears statistics."""
        # Generate some stats
        self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        # Verify stats are non-zero
        stats_before = self.library.get_cache_stats()
        self.assertGreater(stats_before['misses'], 0)
        
        # Reset
        self.library.reset_cache_stats()
        
        # Verify stats are zero
        stats_after = self.library.get_cache_stats()
        self.assertEqual(stats_after['hits'], 0)
        self.assertEqual(stats_after['misses'], 0)
        self.assertEqual(stats_after['time_saved_seconds'], 0.0)
        self.assertEqual(stats_after['total_requests'], 0)
    
    def test_compute_all_with_tracking(self):
        """Test compute_all propagates track_performance parameter."""
        self.library.reset_cache_stats()
        
        specs = [
            IndicatorSpec('SMA', {'timeperiod': 10}, 'SMA_10'),
            IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
        ]
        
        # Compute with tracking
        result_df = self.library.compute_all(self.df, specs, track_performance=True)
        
        stats = self.library.get_cache_stats()
        # Should have 2 misses (2 indicators)
        self.assertEqual(stats['misses'], 2)
    
    def test_compute_all_with_tracking_cache_hit(self):
        """Test compute_all cache hits on second computation."""
        self.library.reset_cache_stats()
        
        specs = [
            IndicatorSpec('SMA', {'timeperiod': 10}, 'SMA_10'),
            IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
        ]
        
        # First computation
        result_df1 = self.library.compute_all(self.df, specs, track_performance=True)
        
        # Second computation (should hit cache)
        result_df2 = self.library.compute_all(self.df, specs, track_performance=True)
        
        stats = self.library.get_cache_stats()
        # Should have 2 misses + 2 hits
        self.assertEqual(stats['misses'], 2)
        self.assertEqual(stats['hits'], 2)
    
    def test_compute_all_without_tracking(self):
        """Test compute_all without tracking doesn't update stats."""
        self.library.reset_cache_stats()
        
        specs = [
            IndicatorSpec('SMA', {'timeperiod': 10}, 'SMA_10'),
        ]
        
        result_df = self.library.compute_all(self.df, specs, track_performance=False)
        
        stats = self.library.get_cache_stats()
        # Stats should remain zero
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['hits'], 0)
    
    def test_cache_tracking_time_saved(self):
        """Test that time_saved_seconds reflects actual computation time."""
        self.library.reset_cache_stats()
        
        # First computation (should record time)
        start = time.time()
        result1 = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        first_time = time.time() - start
        
        stats = self.library.get_cache_stats()
        # Time saved should be approximately equal to first computation time
        # (allowing for small overhead)
        self.assertGreater(stats['time_saved_seconds'], 0.0)
        # Time saved should be reasonable (within 10x for safety)
        self.assertLess(stats['time_saved_seconds'], first_time * 10)
    
    def test_cache_empty_dataframe(self):
        """Test cache tracking handles empty DataFrame."""
        empty_df = pd.DataFrame()
        
        with self.assertRaises(ValueError):
            self.library.compute_indicator(
                empty_df, 'SMA', {'timeperiod': 20}, 'SMA_20',
                track_performance=True
            )
        
        # Stats should not be updated on error
        stats = self.library.get_cache_stats()
        self.assertEqual(stats['misses'], 0)


if __name__ == '__main__':
    unittest.main()

