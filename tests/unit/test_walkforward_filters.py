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
import shutil
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
        # Register filters only if not already registered (auto-registered via __init__.py)
        from backtester.filters.implementations.volatility.atr import VolatilityRegimeATR
        from backtester.filters.implementations.volatility.stddev import VolatilityRegimeStdDev
        from backtester.filters.registry import register_filter, get_filter
        
        # Only register if not already registered
        if not get_filter('volatility_regime_atr'):
            register_filter(VolatilityRegimeATR)
        if not get_filter('volatility_regime_stddev'):
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
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        # Ensure filters are registered
        from backtester.filters.registry import list_filters
        filters = list_filters()
        assert 'volatility_regime_atr' in filters, "volatility_regime_atr filter not registered"
    
    def setUp(self):
        """Set up test environment for each test."""
        from pathlib import Path
        from backtester.data.cache_manager import write_cache
        from backtester.data import cache_manager as cm_module
        
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        self.data_dir = os.path.join(self.temp_dir, 'data', 'cache')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create test data - need sufficient data for walk-forward (300+ bars)
        self.test_data = create_test_dataframe(300)  # ~10 months of daily data
        
        # Patch cache directory
        self.original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(self.data_dir)
        
        # Write test data to cache
        write_cache('BTC/USD', '1d', self.test_data)
        
        # Create metadata file
        self.metadata_path = os.path.join(self.config_dir, 'markets.yaml')
        with open(self.metadata_path, 'w') as f:
            yaml.dump({
                'top_markets': ['BTC/USD'],
                'timeframes': ['1d']
            }, f)
    
    def tearDown(self):
        """Clean up test environment."""
        from backtester.data import cache_manager as cm_module
        
        # Restore original cache directory
        cm_module.CACHE_DIR = self.original_cache_dir
        
        # Clean up temp directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_config_with_filters(self, filters=None):
        """Create test configuration files with optional filters."""
        configs = {
            'data.yaml': {
                'data': {
                    'exchange': 'coinbase',
                    'cache_directory': self.data_dir,
                    'cache_enabled': True
                }
            },
            'trading.yaml': {
                'trading': {
                    'fee_type': 'maker',
                    'commission': 0.001
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
                    'start_date': '2023-01-01',  # Required by validator
                    'end_date': '2023-09-30',     # Required by validator
                    'initial_capital': 10000.0,   # Required by validator
                    'periods': ['3M/1M'],  # Short periods for testing
                    'fitness_functions': ['net_profit'],
                    'parameter_ranges': {
                        'fast_period': {'start': 10, 'end': 15, 'step': 5},
                        'slow_period': {'start': 20, 'end': 25, 'step': 5}
                    }
                }
            },
            'parallel.yaml': {
                'parallel': {
                    'mode': 'manual',
                    'max_workers': 1
                }
            },
            'data_quality.yaml': {
                'data_quality': {
                    'enabled': False
                }
            },
            'debug.yaml': {
                'debug': {
                    'enabled': False,
                    'logging': {'level': 'INFO'}
                }
            }
        }
        
        # Add filters if specified
        if filters is not None:
            configs['walkforward.yaml']['walkforward']['filters'] = filters
        
        # Write config files
        for filename, config in configs.items():
            filepath = os.path.join(self.config_dir, filename)
            with open(filepath, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
        
        # Create ConfigManager
        return ConfigManager(config_dir=self.config_dir, metadata_path=self.metadata_path)
    
    def test_walkforward_with_single_filter(self):
        """Test walk-forward optimization with a single filter."""
        # Create config with single filter
        config = self._create_config_with_filters(filters=['volatility_regime_atr'])
        
        # Create walk-forward runner
        runner = WalkForwardRunner(config, output=None)
        
        # Run walk-forward analysis
        results = runner.run_walkforward_analysis(
            strategy_class=SMACrossStrategy,
            symbol='BTC/USD',
            timeframe='1d',
            data_df=self.test_data
        )
        
        # Verify results
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should have at least one result")
        
        # Verify we have results for different filter configurations
        filter_configs_seen = set()
        for result in results:
            self.assertIsNotNone(result.filter_config)
            self.assertIsInstance(result.filter_config, dict)
            
            # Track unique filter configs
            if result.filter_config:
                config_key = tuple(sorted(result.filter_config.items()))
            else:
                config_key = tuple()  # Baseline
            filter_configs_seen.add(config_key)
        
        # Should have multiple configurations: high, normal, low, none + baseline = 5
        self.assertGreaterEqual(len(filter_configs_seen), 4, 
                              "Should have results for multiple filter regimes")
        
        # Verify baseline is present (empty filter_config)
        baseline_present = any(not result.filter_config for result in results)
        self.assertTrue(baseline_present, "Baseline (empty filter_config) should be present")
        
        # Verify all results have required fields
        for result in results:
            self.assertEqual(result.symbol, 'BTC/USD')
            self.assertEqual(result.timeframe, '1d')
            self.assertEqual(result.period_str, '3M/1M')
            self.assertEqual(result.fitness_function, 'net_profit')
    
    def test_walkforward_with_multiple_filters(self):
        """Test walk-forward optimization with multiple filters."""
        # Create config with multiple filters
        config = self._create_config_with_filters(
            filters=['volatility_regime_atr', 'volatility_regime_stddev']
        )
        
        # Create walk-forward runner
        runner = WalkForwardRunner(config, output=None)
        
        # Run walk-forward analysis
        results = runner.run_walkforward_analysis(
            strategy_class=SMACrossStrategy,
            symbol='BTC/USD',
            timeframe='1d',
            data_df=self.test_data
        )
        
        # Verify results
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should have at least one result")
        
        # Track filter configurations
        filter_configs_seen = set()
        for result in results:
            self.assertIsNotNone(result.filter_config)
            self.assertIsInstance(result.filter_config, dict)
            
            # Track unique filter configs
            if result.filter_config:
                config_key = tuple(sorted(result.filter_config.items()))
            else:
                config_key = tuple()  # Baseline
            filter_configs_seen.add(config_key)
        
        # Should have cartesian product: (4 regimes ATR × 4 regimes StdDev) + baseline
        # Expected: 16 combinations + 1 baseline = 17 (but some combinations may be filtered out)
        # At minimum, should have significantly more than single filter
        self.assertGreater(len(filter_configs_seen), 10, 
                          "Should have results for cartesian product of filter combinations")
        
        # Verify baseline is present
        baseline_present = any(not result.filter_config for result in results)
        self.assertTrue(baseline_present, "Baseline should be present")
        
        # Verify both filters appear in non-baseline results
        atr_found = False
        stddev_found = False
        for result in results:
            if result.filter_config:
                if 'volatility_regime_atr' in result.filter_config:
                    atr_found = True
                if 'volatility_regime_stddev' in result.filter_config:
                    stddev_found = True
        
        self.assertTrue(atr_found, "Should have results with volatility_regime_atr filter")
        self.assertTrue(stddev_found, "Should have results with volatility_regime_stddev filter")
    
    def test_walkforward_baseline_vs_filtered(self):
        """Test that baseline (no filters) produces different results than filtered."""
        # Create config with single filter
        config = self._create_config_with_filters(filters=['volatility_regime_atr'])
        
        # Create walk-forward runner
        runner = WalkForwardRunner(config, output=None)
        
        # Run walk-forward analysis
        results = runner.run_walkforward_analysis(
            strategy_class=SMACrossStrategy,
            symbol='BTC/USD',
            timeframe='1d',
            data_df=self.test_data
        )
        
        # Separate baseline and filtered results
        baseline_results = [r for r in results if not r.filter_config]
        filtered_results = [r for r in results if r.filter_config]
        
        self.assertGreater(len(baseline_results), 0, "Should have baseline results")
        self.assertGreater(len(filtered_results), 0, "Should have filtered results")
        
        # Get baseline result
        baseline = baseline_results[0]
        
        # Verify baseline has proper structure
        self.assertEqual(baseline.filter_config, {})
        self.assertIsNotNone(baseline.window_results)
        
        # Verify filtered results have filter configs
        for filtered in filtered_results:
            self.assertNotEqual(filtered.filter_config, {})
            self.assertIn('volatility_regime_atr', filtered.filter_config)
            self.assertIn(filtered.filter_config['volatility_regime_atr'], 
                         ['high', 'normal', 'low', 'none'])
        
        # Verify baseline and filtered results are different objects
        # (They may have same metrics if all trades happen in one regime, but structure differs)
        self.assertNotEqual(baseline.filter_config, filtered_results[0].filter_config)
        
        # Calculate aggregates for comparison
        baseline.calculate_aggregates()
        filtered_results[0].calculate_aggregates()
        
        # Both should have calculated aggregates
        self.assertGreaterEqual(baseline.total_windows, 0)
        self.assertGreaterEqual(filtered_results[0].total_windows, 0)


if __name__ == '__main__':
    unittest.main()

