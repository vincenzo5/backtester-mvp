"""
Unit tests for indicator library.

Tests IndicatorLibrary, custom indicator registration, and indicator computation.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.indicators.library import IndicatorLibrary
from backtester.indicators.base import (
    IndicatorSpec,
    register_custom_indicator,
    get_custom_indicator,
    list_custom_indicators
)


@pytest.mark.unit
class TestIndicatorLibrary(unittest.TestCase):
    """Test IndicatorLibrary class."""
    
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
    
    def test_compute_indicator_sma(self):
        """Test computing SMA indicator."""
        result = self.library.compute_indicator(
            self.df, 'SMA', {'timeperiod': 20}, 'SMA_20'
        )
        
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(self.df))
        # SMA should have NaN for first few values
        self.assertTrue(pd.isna(result.iloc[0]) or isinstance(result.iloc[0], (int, float)))
    
    def test_compute_indicator_rsi(self):
        """Test computing RSI indicator."""
        result = self.library.compute_indicator(
            self.df, 'RSI', {'timeperiod': 14}, 'RSI_14'
        )
        
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(self.df))
        # RSI should be between 0 and 100 (if computed)
        valid_values = result.dropna()
        if len(valid_values) > 0:
            self.assertTrue(all(0 <= v <= 100 for v in valid_values))
    
    def test_compute_indicator_empty_df(self):
        """Test that computing indicator on empty DataFrame raises error."""
        empty_df = pd.DataFrame()
        with self.assertRaises(ValueError):
            self.library.compute_indicator(empty_df, 'SMA', {'timeperiod': 20}, 'SMA_20')
    
    def test_compute_indicator_invalid_type(self):
        """Test that invalid indicator type raises error."""
        with self.assertRaises(ValueError):
            self.library.compute_indicator(
                self.df, 'INVALID_INDICATOR', {}, 'invalid'
            )
    
    def test_compute_all(self):
        """Test computing multiple indicators."""
        specs = [
            IndicatorSpec('SMA', {'timeperiod': 10}, 'SMA_10'),
            IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
            IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
        ]
        
        result_df = self.library.compute_all(self.df, specs)
        
        # Should have original columns plus indicator columns
        self.assertGreater(len(result_df.columns), len(self.df.columns))
        self.assertIn('SMA_10', result_df.columns)
        self.assertIn('SMA_20', result_df.columns)
        self.assertIn('RSI_14', result_df.columns)
    
    def test_compute_all_empty_specs(self):
        """Test computing with empty specs returns original DataFrame."""
        result_df = self.library.compute_all(self.df, [])
        self.assertEqual(len(result_df.columns), len(self.df.columns))
    
    def test_compute_all_preserves_original(self):
        """Test that compute_all doesn't modify original DataFrame."""
        original_columns = set(self.df.columns)
        specs = [IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20')]
        
        result_df = self.library.compute_all(self.df, specs)
        
        # Original should be unchanged
        self.assertEqual(set(self.df.columns), original_columns)
        # Result should have more columns
        self.assertGreater(len(result_df.columns), len(self.df.columns))


@pytest.mark.unit
class TestCustomIndicators(unittest.TestCase):
    """Test custom indicator registration and usage."""
    
    def setUp(self):
        """Set up test data."""
        dates = pd.date_range(start='2020-01-01', periods=50, freq='1h')
        np.random.seed(42)
        
        self.df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 50),
            'high': np.random.uniform(200, 300, 50),
            'low': np.random.uniform(50, 100, 50),
            'close': np.random.uniform(100, 200, 50),
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)
        
        self.library = IndicatorLibrary()
    
    def test_register_custom_indicator(self):
        """Test registering a custom indicator."""
        def my_custom_avg(df, params):
            """Custom indicator: average of close prices."""
            return df['close'].rolling(window=params['period']).mean()
        
        register_custom_indicator('MY_AVG', my_custom_avg)
        
        # Should be able to retrieve it (returns CustomIndicator wrapper)
        retrieved = get_custom_indicator('MY_AVG')
        self.assertIsNotNone(retrieved)
        # Check that the compute_func is the same function
        self.assertEqual(retrieved.compute_func, my_custom_avg)
    
    def test_compute_custom_indicator(self):
        """Test computing a registered custom indicator."""
        def volume_ma(df, params):
            """Custom indicator: moving average of volume."""
            return df['volume'].rolling(window=params['window']).mean()
        
        register_custom_indicator('VOLUME_MA', volume_ma)
        
        result = self.library.compute_indicator(
            self.df, 'VOLUME_MA', {'window': 10}, 'vol_ma_10'
        )
        
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(self.df))
    
    def test_list_custom_indicators(self):
        """Test listing registered custom indicators."""
        def indicator1(df, params):
            return df['close'].mean()
        
        def indicator2(df, params):
            return df['volume'].mean()
        
        register_custom_indicator('CUSTOM_1', indicator1)
        register_custom_indicator('CUSTOM_2', indicator2)
        
        custom_list = list_custom_indicators()
        self.assertIn('CUSTOM_1', custom_list)
        self.assertIn('CUSTOM_2', custom_list)


@pytest.mark.unit
class TestIndicatorSpec(unittest.TestCase):
    """Test IndicatorSpec dataclass."""
    
    def test_indicator_spec_creation(self):
        """Test creating IndicatorSpec."""
        spec = IndicatorSpec(
            indicator_type='SMA',
            params={'timeperiod': 20},
            column_name='SMA_20'
        )
        
        self.assertEqual(spec.indicator_type, 'SMA')
        self.assertEqual(spec.params, {'timeperiod': 20})
        self.assertEqual(spec.column_name, 'SMA_20')
    
    def test_indicator_spec_with_empty_params(self):
        """Test IndicatorSpec with empty params."""
        spec = IndicatorSpec('RSI', {}, 'RSI_14')
        
        self.assertEqual(spec.indicator_type, 'RSI')
        self.assertEqual(spec.params, {})
        self.assertEqual(spec.column_name, 'RSI_14')

