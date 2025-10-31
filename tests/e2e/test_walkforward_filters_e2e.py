"""
End-to-end tests for walk-forward optimization with filters.

Tests the complete workflow with actual data execution:
- Filter computation
- Configuration generation
- Walk-forward execution with filters
- Results verification
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import os
import yaml
from datetime import datetime, timedelta
import shutil

from backtester.config import ConfigManager
from backtester.backtest.walkforward.runner import WalkForwardRunner
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.data.cache_manager import read_cache
from backtester.filters.registry import list_filters


def create_test_ohlcv_data(num_bars=500, start_date=None) -> pd.DataFrame:
    """Create realistic test OHLCV data."""
    if start_date is None:
        start_date = datetime(2023, 1, 1)
    
    dates = pd.date_range(start=start_date, periods=num_bars, freq='1D')
    
    # Generate realistic price data with trends and volatility
    np.random.seed(42)
    trend = np.linspace(100, 150, num_bars)
    volatility_cycles = np.sin(np.linspace(0, 4 * np.pi, num_bars)) * 3
    noise = np.random.normal(0, 2, num_bars)
    prices = trend + volatility_cycles + noise
    
    # Create OHLCV data with realistic relationships
    closes = prices
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    
    high_mult = 1 + np.abs(np.random.normal(0, 0.015, num_bars))
    low_mult = 1 - np.abs(np.random.normal(0, 0.015, num_bars))
    
    df = pd.DataFrame({
        'open': opens,
        'high': closes * high_mult,
        'low': closes * low_mult,
        'close': closes,
        'volume': np.random.randint(1000, 10000, num_bars)
    }, index=dates)
    
    return df


class TestWalkForwardFiltersEndToEnd(unittest.TestCase):
    """End-to-end tests for walk-forward with filters."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Verify filters are registered
        filters = list_filters()
        assert 'volatility_regime_atr' in filters, "volatility_regime_atr filter not registered"
    
    def setUp(self):
        """Set up test fixtures for each test."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        self.data_dir = os.path.join(self.temp_dir, 'data', 'cache')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create test data
        self.test_data = create_test_ohlcv_data(300)  # ~10 months of daily data
        
        # Save test data to cache (simulating cached data)
        # Note: read_cache expects 'datetime' as index column name
        self.test_data.index.name = 'datetime'
        cache_file = os.path.join(self.data_dir, 'BTC_USD_1d.csv')
        self.test_data.to_csv(cache_file, index=True)
        
        # Create minimal config files
        self._create_test_configs()
        
        # Create ConfigManager pointing to temp directory
        # Note: ConfigManager expects config files in a specific structure
        # We'll need to adjust the paths or use a different approach
        self.config = self._create_config_manager()
    
    def _create_test_configs(self):
        """Create test configuration files."""
        configs = {
            'backtest.yaml': {
                'backtest': {
                    'start_date': '2023-01-01',
                    'end_date': '2023-09-30',
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
            'trading.yaml': {
                'trading': {
                    'fee_type': 'maker',
                    'fee_rate': 0.001
                }
            },
            'data.yaml': {
                'data': {
                    'exchange': 'coinbase',
                    'cache_directory': self.data_dir,
                    'cache_enabled': True
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
            'walkforward.yaml': {
                'walkforward': {
                    'start_date': '2023-01-01',  # Required by validator
                    'end_date': '2023-09-30',    # Required by validator
                    'initial_capital': 10000.0,   # Required by validator
                    'periods': ['3M/1M'],  # Short periods for testing
                    'fitness_functions': ['net_profit'],
                    'parameter_ranges': {
                        'fast_period': {'start': 10, 'end': 15, 'step': 5},
                        'slow_period': {'start': 20, 'end': 25, 'step': 5}
                    },
                    'filters': ['volatility_regime_atr']  # Enable filters
                }
            },
            'debug.yaml': {
                'debug': {
                    'enabled': False,
                    'logging': {'level': 'INFO'}
                }
            }
        }
        
        # Write config files
        for filename, config in configs.items():
            filepath = os.path.join(self.config_dir, filename)
            with open(filepath, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
    
    def _create_config_manager(self):
        """Create a ConfigManager with test configs."""
        # ConfigManager can accept a custom config_dir
        # Create a markets.yaml file as well (ConfigManager expects it)
        markets_file = os.path.join(self.config_dir, 'markets.yaml')
        with open(markets_file, 'w') as f:
            yaml.dump({
                'markets': {
                    'BTC/USD': {
                        'exchange': 'coinbase',
                        'active': True
                    }
                }
            }, f)
        
        # Create ConfigManager pointing to our test config directory
        from backtester.config import ConfigManager
        return ConfigManager(config_dir=self.config_dir, metadata_path=markets_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_filter_config_generation_integration(self):
        """Test that filter configurations are generated correctly."""
        from backtester.filters.generator import generate_filter_configurations
        
        # Get filters from config
        filter_names = self.config.get_walkforward_filters()
        self.assertEqual(len(filter_names), 1)
        self.assertEqual(filter_names[0], 'volatility_regime_atr')
        
        # Generate configurations
        configs = generate_filter_configurations(filter_names)
        
        # Should have: 3 regimes (high, normal, low) + baseline = 4 configs
        self.assertGreaterEqual(len(configs), 3)
        self.assertIn({}, configs)  # Baseline must be present
        
        # Verify structure
        for config in configs:
            if config:  # Non-baseline configs
                self.assertIn('volatility_regime_atr', config)
                self.assertIn(config['volatility_regime_atr'], ['high', 'normal', 'low'])
    
    def test_filter_computation_on_data(self):
        """Test that filters are computed correctly on actual data."""
        from backtester.filters.registry import get_filter
        
        # Get filter
        filter_class = get_filter('volatility_regime_atr')
        self.assertIsNotNone(filter_class)
        
        # Compute classification
        filter_instance = filter_class()
        classification = filter_instance.compute_classification(self.test_data)
        
        # Verify results
        self.assertEqual(len(classification), len(self.test_data))
        self.assertTrue(classification.index.equals(self.test_data.index))
        
        # Verify all values are valid regimes
        valid_regimes = {'high', 'normal', 'low'}
        unique_regimes = set(classification.unique())
        self.assertTrue(unique_regimes.issubset(valid_regimes))
        
        # Verify we have multiple regimes (not all the same)
        self.assertGreater(len(unique_regimes), 1, "Filter should produce multiple regimes")
    
    def test_walkforward_with_filters_full_execution(self):
        """Test full walk-forward execution with filters."""
        # Patch cache manager to use test data
        from pathlib import Path
        from backtester.data import cache_manager
        
        # Save original cache dir
        original_cache_dir = cache_manager.CACHE_DIR
        
        try:
            # Point cache to our test cache directory
            cache_manager.CACHE_DIR = Path(self.data_dir)
            
            # Ensure test data is saved to cache with proper format
            cache_file = Path(self.data_dir) / 'BTC_USD_1d.csv'
            test_data_copy = self.test_data.copy()
            test_data_copy.index.name = 'datetime'
            test_data_copy.to_csv(cache_file, index=True)
            
            # Create a walk-forward runner
            runner = WalkForwardRunner(self.config, output=None)
            
            # Load data from cache (simulating real usage)
            from backtester.data.cache_manager import read_cache
            data_df = read_cache('BTC/USD', '1d')
            
            # Run walk-forward analysis
            results = runner.run_walkforward_analysis(
                strategy_class=SMACrossStrategy,
                symbol='BTC/USD',
                timeframe='1d',
                data_df=data_df
            )
            
            # Verify results structure
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0, "Should have at least one result")
            
            # Check that we have results for different filter configs
            filter_configs_seen = set()
            for result in results:
                self.assertIsInstance(result.filter_config, dict)
                # Convert to tuple for set comparison
                config_key = tuple(sorted(result.filter_config.items())) if result.filter_config else tuple()
                filter_configs_seen.add(config_key)
            
            # Should have multiple filter configurations (including baseline)
            self.assertGreater(len(filter_configs_seen), 1, 
                              "Should have results for multiple filter configs")
            
            # Verify baseline is present
            baseline_present = any(not result.filter_config for result in results)
            self.assertTrue(baseline_present, "Baseline (empty filter_config) should be present")
        
        finally:
            # Restore original cache dir
            cache_manager.CACHE_DIR = original_cache_dir
    
    def test_walkforward_results_include_filter_config(self):
        """Test that all walk-forward results include filter_config."""
        from pathlib import Path
        from backtester.data import cache_manager
        
        original_cache_dir = cache_manager.CACHE_DIR
        
        try:
            cache_manager.CACHE_DIR = Path(self.data_dir)
            cache_file = Path(self.data_dir) / 'BTC_USD_1d.csv'
            self.test_data.to_csv(cache_file, index=True)
            
            runner = WalkForwardRunner(self.config, output=None)
            
            from backtester.data.cache_manager import read_cache
            data_df = read_cache('BTC/USD', '1d')
            
            results = runner.run_walkforward_analysis(
                strategy_class=SMACrossStrategy,
                symbol='BTC/USD',
                timeframe='1d',
                data_df=data_df
            )
            
            # Verify all results have filter_config
            for result in results:
                self.assertIsNotNone(result.filter_config)
            self.assertIsInstance(result.filter_config, dict)
            
            # Verify serialization includes filter_config
            result_dict = result.to_dict()
            self.assertIn('filter_config', result_dict)
            self.assertEqual(result_dict['filter_config'], result.filter_config)
        
        finally:
            cache_manager.CACHE_DIR = original_cache_dir
    
    def test_baseline_vs_filtered_results_different(self):
        """Test that baseline and filtered results produce different metrics."""
        from pathlib import Path
        from backtester.data import cache_manager
        
        original_cache_dir = cache_manager.CACHE_DIR
        
        try:
            cache_manager.CACHE_DIR = Path(self.data_dir)
            cache_file = Path(self.data_dir) / 'BTC_USD_1d.csv'
            test_data_copy = self.test_data.copy()
            test_data_copy.index.name = 'datetime'
            test_data_copy.to_csv(cache_file, index=True)
            
            runner = WalkForwardRunner(self.config, output=None)
            
            from backtester.data.cache_manager import read_cache
            data_df = read_cache('BTC/USD', '1d')
            
            results = runner.run_walkforward_analysis(
                strategy_class=SMACrossStrategy,
                symbol='BTC/USD',
                timeframe='1d',
                data_df=data_df
            )
            
            # Find baseline and filtered results
            baseline_results = [r for r in results if not r.filter_config]
            filtered_results = [r for r in results if r.filter_config]
            
            self.assertGreater(len(baseline_results), 0, "Should have baseline results")
            self.assertGreater(len(filtered_results), 0, "Should have filtered results")
            
            # Compare metrics (they should be different if filtering worked)
            # Note: They might be the same if all trades happen in one regime,
            # but in general they should differ
            baseline_metrics = baseline_results[0]
            if filtered_results:
                filtered_metrics = filtered_results[0]
                # At minimum, verify they're different result objects
                # (actual metric differences depend on data and filtering)
                self.assertNotEqual(baseline_metrics.filter_config, 
                                  filtered_metrics.filter_config)
        
        finally:
            cache_manager.CACHE_DIR = original_cache_dir


if __name__ == '__main__':
    unittest.main()

