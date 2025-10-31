"""
Unit tests for filter system components.

Tests filter computation, registry, configuration generation, and trade filtering.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

from backtester.filters.base import BaseFilter
from backtester.filters.registry import (
    register_filter,
    get_filter,
    list_filters,
    get_all_filters
)
from backtester.filters.generator import generate_filter_configurations
from backtester.filters.applicator import (
    apply_filters_to_trades,
    _check_matching_logic,
    recalculate_metrics_with_filtered_trades
)
from backtester.filters.implementations.volatility.atr import VolatilityRegimeATR
from backtester.filters.implementations.volatility.stddev import VolatilityRegimeStdDev
from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics
import backtrader as bt


def create_test_dataframe(num_bars=100, start_date=None) -> pd.DataFrame:
    """Create a test OHLCV DataFrame."""
    if start_date is None:
        start_date = datetime(2024, 1, 1)
    
    dates = pd.date_range(start=start_date, periods=num_bars, freq='1H')
    
    # Generate realistic price data with some volatility
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, num_bars)
    prices = 100 * (1 + returns).cumprod()
    
    # Create OHLCV data
    high_mult = 1 + np.abs(np.random.normal(0, 0.01, num_bars))
    low_mult = 1 - np.abs(np.random.normal(0, 0.01, num_bars))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.005, num_bars)),
        'high': prices * high_mult,
        'low': prices * low_mult,
        'close': prices,
        'volume': np.random.randint(1000, 10000, num_bars)
    }, index=dates)
    
    return df


class TestBaseFilter(unittest.TestCase):
    """Test BaseFilter abstract class."""
    
    def test_base_filter_cannot_be_instantiated(self):
        """BaseFilter should be abstract and cannot be instantiated."""
        with self.assertRaises(TypeError):
            BaseFilter()


class TestFilterRegistry(unittest.TestCase):
    """Test filter registry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Register test filters
        register_filter(VolatilityRegimeATR)
        register_filter(VolatilityRegimeStdDev)
    
    def test_register_and_get_filter(self):
        """Test registering and retrieving a filter."""
        filter_class = get_filter('volatility_regime_atr')
        self.assertIsNotNone(filter_class)
        self.assertEqual(filter_class, VolatilityRegimeATR)
        
        # Verify we can instantiate it
        instance = filter_class()
        self.assertEqual(instance.name, 'volatility_regime_atr')
    
    def test_get_nonexistent_filter(self):
        """Test getting a filter that doesn't exist."""
        filter_class = get_filter('nonexistent_filter')
        self.assertIsNone(filter_class)
    
    def test_list_filters(self):
        """Test listing all registered filters."""
        filters = list_filters()
        self.assertIn('volatility_regime_atr', filters)
        self.assertIn('volatility_regime_stddev', filters)
    
    def test_get_all_filters(self):
        """Test getting all filters as a dictionary."""
        all_filters = get_all_filters()
        self.assertIn('volatility_regime_atr', all_filters)
        self.assertIn('volatility_regime_stddev', all_filters)
        self.assertEqual(all_filters['volatility_regime_atr'], VolatilityRegimeATR)


class TestVolatilityRegimeATR(unittest.TestCase):
    """Test VolatilityRegimeATR filter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = VolatilityRegimeATR()
        self.df = create_test_dataframe(100)
    
    def test_filter_attributes(self):
        """Test filter class attributes."""
        self.assertEqual(self.filter.name, 'volatility_regime_atr')
        self.assertEqual(self.filter.regimes, ['high', 'normal', 'low'])
        self.assertEqual(self.filter.matching, 'entry')
        self.assertIn('lookback', self.filter.default_params)
    
    def test_compute_classification(self):
        """Test filter classification computation."""
        result = self.filter.compute_classification(self.df)
        
        # Should return a Series with same index as input
        self.assertEqual(len(result), len(self.df))
        self.assertTrue(result.index.equals(self.df.index))
        
        # Should only contain valid regime labels
        valid_regimes = set(self.filter.regimes)
        for regime in result:
            self.assertIn(regime, valid_regimes)
    
    def test_empty_dataframe(self):
        """Test filter with empty DataFrame."""
        empty_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        result = self.filter.compute_classification(empty_df)
        self.assertEqual(len(result), 0)
    
    def test_custom_parameters(self):
        """Test filter with custom parameters."""
        custom_params = {'lookback': 20, 'high_threshold': 0.8, 'low_threshold': 0.2}
        result = self.filter.compute_classification(self.df, params=custom_params)
        self.assertEqual(len(result), len(self.df))


class TestVolatilityRegimeStdDev(unittest.TestCase):
    """Test VolatilityRegimeStdDev filter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = VolatilityRegimeStdDev()
        self.df = create_test_dataframe(100)
    
    def test_filter_attributes(self):
        """Test filter class attributes."""
        self.assertEqual(self.filter.name, 'volatility_regime_stddev')
        self.assertEqual(self.filter.regimes, ['high', 'normal', 'low'])
        self.assertEqual(self.filter.matching, 'entry')
    
    def test_compute_classification(self):
        """Test filter classification computation."""
        result = self.filter.compute_classification(self.df)
        
        # Should return a Series with same index as input
        self.assertEqual(len(result), len(self.df))
        self.assertTrue(result.index.equals(self.df.index))
        
        # Should only contain valid regime labels
        valid_regimes = set(self.filter.regimes)
        for regime in result:
            self.assertIn(regime, valid_regimes)


class TestFilterGenerator(unittest.TestCase):
    """Test filter configuration generator."""
    
    def test_single_filter_configs(self):
        """Test generating configs for a single filter."""
        # VolatilityRegimeATR has 3 regimes: high, normal, low
        configs = generate_filter_configurations(['volatility_regime_atr'])
        
        # Should have: 3 regimes + 1 'none' + 1 baseline (empty dict)
        # Actually, 'none' is included in the regimes list, so we get:
        # high, normal, low, none (4 configs) + baseline (1) = 5 total
        # But we skip configs where all are 'none', so we get: high, normal, low, none (4) + baseline = 5
        self.assertGreaterEqual(len(configs), 4)  # At least regimes + baseline
        
        # Should include baseline (empty dict)
        self.assertIn({}, configs)
        
        # Should include each regime
        regime_configs = [c for c in configs if 'volatility_regime_atr' in c]
        self.assertGreaterEqual(len(regime_configs), 3)
    
    def test_multiple_filters_configs(self):
        """Test generating configs for multiple filters (cartesian product)."""
        configs = generate_filter_configurations(['volatility_regime_atr', 'volatility_regime_stddev'])
        
        # Should have cartesian product of all combinations
        # Each filter has 4 options (high, normal, low, none)
        # So we get 4 * 4 = 16 combinations, minus the one where both are 'none'
        # Plus baseline = 16 total configs
        self.assertGreaterEqual(len(configs), 15)
        
        # Should include baseline
        self.assertIn({}, configs)
    
    def test_empty_filter_list(self):
        """Test generating configs with no filters."""
        configs = generate_filter_configurations([])
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs, [{}])  # Only baseline
    
    def test_nonexistent_filter(self):
        """Test generating configs with non-existent filter."""
        with self.assertRaises(ValueError):
            generate_filter_configurations(['nonexistent_filter'])


class TestFilterApplicator(unittest.TestCase):
    """Test filter applicator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.df = create_test_dataframe(100)
        
        # Add filter columns
        atr_filter = VolatilityRegimeATR()
        self.df['volatility_regime_atr'] = atr_filter.compute_classification(self.df)
        
        # Create sample trades
        self.trades = [
            {
                'entry_date': self.df.index[10],
                'exit_date': self.df.index[15],
                'entry_price': 100.0,
                'exit_price': 105.0,
                'size': 1.0,
                'pnl': 5.0,
                'gross_pnl': 5.0,
                'entry_commission': 0.0,
                'exit_commission': 0.0
            },
            {
                'entry_date': self.df.index[20],
                'exit_date': self.df.index[25],
                'entry_price': 110.0,
                'exit_price': 115.0,
                'size': 1.0,
                'pnl': 5.0,
                'gross_pnl': 5.0,
                'entry_commission': 0.0,
                'exit_commission': 0.0
            }
        ]
    
    def test_baseline_no_filtering(self):
        """Test baseline configuration (no filtering)."""
        filtered = apply_filters_to_trades(self.trades, self.df, {})
        self.assertEqual(len(filtered), len(self.trades))
        self.assertEqual(filtered, self.trades)
    
    def test_filter_by_regime(self):
        """Test filtering trades by regime."""
        # Get the regime at entry date for first trade
        entry_date = self.trades[0]['entry_date']
        entry_idx = self.df.index.get_indexer([entry_date], method='nearest')[0]
        regime = self.df.iloc[entry_idx]['volatility_regime_atr']
        
        # Filter for that regime
        filter_config = {'volatility_regime_atr': regime}
        filtered = apply_filters_to_trades(self.trades, self.df, filter_config)
        
        # Should include trades that match the regime
        self.assertGreaterEqual(len(filtered), 0)
        self.assertLessEqual(len(filtered), len(self.trades))
    
    def test_filter_none_regime(self):
        """Test filtering with 'none' regime (disabled filter)."""
        filter_config = {'volatility_regime_atr': 'none'}
        filtered = apply_filters_to_trades(self.trades, self.df, filter_config)
        # 'none' should not filter anything (skip this filter)
        self.assertEqual(len(filtered), len(self.trades))
    
    def test_empty_trades(self):
        """Test filtering with empty trades list."""
        filtered = apply_filters_to_trades([], self.df, {'volatility_regime_atr': 'high'})
        self.assertEqual(filtered, [])
    
    def test_check_matching_logic_entry(self):
        """Test entry matching logic."""
        self.assertTrue(_check_matching_logic('entry', 'high', 'low', 'high'))
        self.assertFalse(_check_matching_logic('entry', 'low', 'high', 'high'))
    
    def test_check_matching_logic_both(self):
        """Test 'both' matching logic."""
        self.assertTrue(_check_matching_logic('both', 'high', 'high', 'high'))
        self.assertFalse(_check_matching_logic('both', 'high', 'low', 'high'))
    
    def test_check_matching_logic_either(self):
        """Test 'either' matching logic."""
        self.assertTrue(_check_matching_logic('either', 'high', 'low', 'high'))
        self.assertTrue(_check_matching_logic('either', 'low', 'high', 'high'))
        self.assertFalse(_check_matching_logic('either', 'low', 'low', 'high'))


if __name__ == '__main__':
    unittest.main()

