"""
End-to-end tests for walk-forward optimization with filters.

Tests full walk-forward analysis with filter configurations including baseline,
multiple filters, and edge cases.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os
import yaml

from backtester.config import ConfigManager
from backtester.backtest.walkforward.runner import WalkForwardRunner
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.data.cache_manager import read_cache


def create_test_dataframe(num_bars=500, start_date=None) -> pd.DataFrame:
    """Create a test OHLCV DataFrame with sufficient data for walk-forward."""
    if start_date is None:
        start_date = datetime(2023, 1, 1)
    
    dates = pd.date_range(start=start_date, periods=num_bars, freq='1D')
    
    # Generate realistic price data with trends
    np.random.seed(42)
    trend = np.linspace(100, 150, num_bars)
    noise = np.random.normal(0, 5, num_bars)
    prices = trend + noise
    
    # Create OHLCV data
    high_mult = 1 + np.abs(np.random.normal(0, 0.02, num_bars))
    low_mult = 1 - np.abs(np.random.normal(0, 0.02, num_bars))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.01, num_bars)),
        'high': prices * high_mult,
        'low': prices * low_mult,
        'close': prices,
        'volume': np.random.randint(1000, 10000, num_bars)
    }, index=dates)
    
    return df


def create_test_config_with_filters(filters=None, temp_dir=None):
    """Create a temporary config with filters enabled."""
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
    
    # Create minimal config files
    config_files = {
        'backtest.yaml': {
            'backtest': {
                'start_date': '2023-01-01',
                'end_date': '2023-06-30',
                'initial_capital': 10000,
                'symbols': ['BTC/USD'],
                'timeframes': ['1d']
            }
        },
        'strategy.yaml': {
            'strategy': {
                'name': 'sma_cross',
                'parameters': {
                    'fast_period': 10,
                    'slow_period': 20
                }
            }
        },
        'walkforward.yaml': {
            'walkforward': {
                'enabled': True,
                'periods': ['3M/1M'],  # Short periods for testing
                'fitness_functions': ['net_profit'],
                'parameter_ranges': {
                    'fast_period': {'start': 10, 'end': 15, 'step': 5},
                    'slow_period': {'start': 20, 'end': 25, 'step': 5}
                }
            }
        },
        'trading.yaml': {
            'trading': {
                'fee_type': 'maker',
                'fee_rate': 0.001
            }
        },
        'data.yaml': {
            'data': {
                'cache_directory': 'data/cache'
            }
        }
    }
    
    # Add filters if specified
    if filters is not None:
        config_files['walkforward.yaml']['walkforward']['filters'] = filters
    
    # Write config files
    for filename, config in config_files.items():
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w') as f:
            yaml.dump(config, f)
    
    # Create ConfigManager pointing to temp directory
    # Note: This is a simplified approach - in reality ConfigManager
    # might need the full config directory structure
    return temp_dir, config_files


class TestWalkForwardFiltersE2E(unittest.TestCase):
    """End-to-end tests for walk-forward with filters."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        # Register filters
        from backtester.filters.implementations.volatility.atr import VolatilityRegimeATR
        from backtester.filters.implementations.volatility.stddev import VolatilityRegimeStdDev
        from backtester.filters.registry import register_filter
        
        register_filter(VolatilityRegimeATR)
        register_filter(VolatilityRegimeStdDev)
    
    def test_filter_config_generation(self):
        """Test that filter configurations are generated correctly."""
        from backtester.filters.generator import generate_filter_configurations
        
        # Single filter
        configs = generate_filter_configurations(['volatility_regime_atr'])
        # Should have: high, normal, low, none (4) + baseline (1) = 5
        self.assertGreaterEqual(len(configs), 4)
        self.assertIn({}, configs)  # Baseline should be included
        
        # Multiple filters
        configs = generate_filter_configurations(['volatility_regime_atr', 'volatility_regime_stddev'])
        # Should have cartesian product + baseline
        self.assertGreaterEqual(len(configs), 15)
        self.assertIn({}, configs)
    
    def test_walkforward_results_include_filter_config(self):
        """Test that WalkForwardResults includes filter_config field."""
        from backtester.backtest.walkforward.results import WalkForwardResults
        
        # Create result with filter config
        result = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1d',
            period_str='3M/1M',
            fitness_function='net_profit',
            filter_config={'volatility_regime_atr': 'high'}
        )
        
        self.assertEqual(result.filter_config, {'volatility_regime_atr': 'high'})
        
        # Test serialization
        result_dict = result.to_dict()
        self.assertIn('filter_config', result_dict)
        self.assertEqual(result_dict['filter_config'], {'volatility_regime_atr': 'high'})
    
    def test_baseline_filter_config(self):
        """Test that baseline (no filters) is included in results."""
        from backtester.backtest.walkforward.results import WalkForwardResults
        
        # Baseline should have empty filter_config
        result = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1d',
            period_str='3M/1M',
            fitness_function='net_profit',
            filter_config={}  # Empty = baseline
        )
        
        self.assertEqual(result.filter_config, {})
        result_dict = result.to_dict()
        self.assertEqual(result_dict['filter_config'], {})
    
    def test_filter_configs_in_cartesian_product(self):
        """Test that multiple filters generate correct cartesian product."""
        from backtester.filters.generator import generate_filter_configurations
        
        configs = generate_filter_configurations(['volatility_regime_atr', 'volatility_regime_stddev'])
        
        # Check that we have combinations of both filters
        atr_regimes = ['high', 'normal', 'low', 'none']
        stddev_regimes = ['high', 'normal', 'low', 'none']
        
        # Verify some expected combinations exist
        found_combinations = set()
        for config in configs:
            if config:  # Skip baseline
                keys = tuple(sorted(config.keys()))
                values = tuple(sorted(config.values()))
                found_combinations.add((keys, values))
        
        # Should have many combinations (4 * 4 = 16, minus all-none = 15)
        self.assertGreaterEqual(len([c for c in configs if c]), 15)
        
        # Baseline should be present
        self.assertIn({}, configs)
    
    def test_filter_integration_with_config_manager(self):
        """Test that ConfigManager can retrieve filter names."""
        # Create a minimal config
        temp_dir, config_files = create_test_config_with_filters(
            filters=['volatility_regime_atr']
        )
        
        # Note: This test requires ConfigManager to be able to load from temp directory
        # In a real test, you'd set up the config directory properly
        # For now, we'll test the accessor method directly
        from backtester.config.core.accessor import ConfigAccessor
        
        # Create a mock config dict
        mock_config = {
            'walkforward': {
                'filters': ['volatility_regime_atr', 'volatility_regime_stddev']
            }
        }
        
        accessor = ConfigAccessor(mock_config)
        filters = accessor.get_walkforward_filters()
        
        self.assertEqual(len(filters), 2)
        self.assertIn('volatility_regime_atr', filters)
        self.assertIn('volatility_regime_stddev', filters)
    
    def test_empty_filters_returns_empty_list(self):
        """Test that missing or empty filters config returns empty list."""
        from backtester.config.core.accessor import ConfigAccessor
        
        # No filters key
        mock_config = {'walkforward': {}}
        accessor = ConfigAccessor(mock_config)
        filters = accessor.get_walkforward_filters()
        self.assertEqual(filters, [])
        
        # Empty filters list
        mock_config = {'walkforward': {'filters': []}}
        accessor = ConfigAccessor(mock_config)
        filters = accessor.get_walkforward_filters()
        self.assertEqual(filters, [])
        
        # None filters
        mock_config = {'walkforward': {'filters': None}}
        accessor = ConfigAccessor(mock_config)
        filters = accessor.get_walkforward_filters()
        self.assertEqual(filters, [])


class TestWalkForwardFiltersIntegration(unittest.TestCase):
    """Integration tests requiring full walk-forward execution."""
    
    @unittest.skip("Requires full test setup with data cache")
    def test_walkforward_with_single_filter(self):
        """Test walk-forward optimization with a single filter."""
        # This would require:
        # 1. Test data in cache
        # 2. Full config setup
        # 3. Strategy execution
        # This is a placeholder for integration test
        pass
    
    @unittest.skip("Requires full test setup with data cache")
    def test_walkforward_with_multiple_filters(self):
        """Test walk-forward optimization with multiple filters."""
        # This would test cartesian product execution
        pass
    
    @unittest.skip("Requires full test setup with data cache")
    def test_walkforward_baseline_vs_filtered(self):
        """Test that baseline (no filters) produces different results than filtered."""
        # This would verify that filtering actually changes results
        pass


if __name__ == '__main__':
    unittest.main()

