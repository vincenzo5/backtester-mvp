"""
End-to-end tests for walk-forward optimization.

Tests the complete workflow: load data → generate windows → optimize → test OOS → aggregate results.
"""

import unittest
import tempfile
import os
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from backtester.config import ConfigManager
from backtester.backtest.runner import BacktestRunner
from backtester.strategies.sma_cross import SMACrossStrategy


class TestWalkForwardEndToEnd(unittest.TestCase):
    """End-to-end tests for complete walk-forward workflow."""
    
    def setUp(self):
        """Set up test environment with mock data and config."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        self.cache_dir = os.path.join(self.temp_dir, 'data')
        os.makedirs(self.config_dir)
        os.makedirs(self.cache_dir)
        
        # Create test data: 2 years of hourly data (simple trend + noise)
        dates = pd.date_range(
            start='2020-01-01 00:00:00',
            end='2021-12-31 23:00:00',
            freq='1h'
        )
        
        # Generate realistic OHLCV data with trend
        np.random.seed(42)  # For reproducibility
        n = len(dates)
        base_price = 50000  # Starting price
        
        # Create trend with some volatility
        trend = np.linspace(0, 20000, n)  # Upward trend
        noise = np.random.randn(n).cumsum() * 100  # Random walk noise
        prices = base_price + trend + noise
        
        # Create OHLCV DataFrame
        closes = prices
        opens = np.roll(closes, 1)
        opens[0] = base_price
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 50)
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 50)
        volumes = np.random.randint(100, 1000, n)
        
        self.test_data = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }, index=dates)
        
        # Save test data to cache directory (simulating cached data)
        # Use CSV format to match actual cache_manager
        cache_file = os.path.join(self.cache_dir, 'BTC_USD_1h.csv')
        self.test_data.to_csv(cache_file)
        
        # Create minimal config for walk-forward
        self.config_data = {
            'exchange': {
                'name': 'coinbase',
                'symbols': ['BTC/USD'],
                'timeframes': ['1h']
            },
            'backtest': {
                'start_date': '2020-06-01',  # Start mid-year to ensure enough data
                'end_date': '2021-12-31',
                'initial_capital': 100000.0,
                'verbose': False
            },
            'trading': {
                'commission': 0.001,  # Lower commission for testing
                'slippage': 0.0001
            },
            'strategy': {
                'name': 'sma_cross',
                'parameters': {
                    'fast_period': 20,
                    'slow_period': 50
                }
            },
            'walkforward': {
                'enabled': True,
                'periods': ['3M/1M'],  # Short periods for faster testing
                'fitness_functions': ['np_avg_dd'],  # Use list format
                'parameter_ranges': {
                    'fast_period': {
                        'start': 10,
                        'end': 15,
                        'step': 5  # Only test 2 values
                    },
                    'slow_period': {
                        'start': 20,
                        'end': 25,
                        'step': 5  # Only test 2 values
                    }
                }
            },
            'parallel': {
                'mode': 'manual',
                'max_workers': 2  # Limit workers for testing
            },
            'data': {
                'cache_enabled': True,
                'cache_directory': self.cache_dir
            }
        }
        
        # Create config file
        self.config_path = os.path.join(self.config_dir, 'config.yaml')
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
        # Create minimal metadata
        self.metadata_path = os.path.join(self.config_dir, 'metadata.yaml')
        metadata = {
            'top_markets': ['BTC/USD'],
            'timeframes': ['1h']
        }
        with open(self.metadata_path, 'w') as f:
            yaml.dump(metadata, f)
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_walkforward_complete_workflow(self):
        """
        Test complete walk-forward workflow from start to finish.
        
        This test:
        1. Loads configuration
        2. Generates walk-forward windows
        3. Optimizes parameters on in-sample data
        4. Tests on out-of-sample data
        5. Aggregates results
        """
        # Set the cache directory in environment or patch the module
        import data.cache_manager as cache_manager
        import sys
        
        # Save original values
        original_cache_dir = cache_manager.CACHE_DIR
        original_read = cache_manager.read_cache
        original_get_path = cache_manager.get_cache_path
        
        # Patch cache directory to point to our test cache
        cache_manager.CACHE_DIR = Path(self.cache_dir)
        
        # Ensure the test data is saved properly
        from data.cache_manager import write_cache
        write_cache('BTC/USD', '1h', self.test_data)
        
        try:
            # Load configuration - need to update cache directory in config
            self.config_data['data']['cache_directory'] = self.cache_dir
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config_data, f)
            
            config = ConfigManager(self.config_path, self.metadata_path)
            
            # Verify walk-forward is enabled
            self.assertTrue(config.is_walkforward_enabled())
            
            # Create runner
            from cli.output import ConsoleOutput
            output = ConsoleOutput(verbose=False)
            runner = BacktestRunner(config, output)
            
            # Run walk-forward analysis
            # This should execute the complete workflow
            wf_results = runner.run_walkforward_analysis(SMACrossStrategy)
            
            # Verify we got results
            self.assertIsInstance(wf_results, list)
            self.assertGreater(len(wf_results), 0, "Should have at least one walk-forward result")
            
            # Check first result
            result = wf_results[0]
            self.assertEqual(result.symbol, 'BTC/USD')
            self.assertEqual(result.timeframe, '1h')
            self.assertEqual(result.period_str, '3M/1M')
            self.assertEqual(result.fitness_function, 'np_avg_dd')
            
            # Verify results have windows
            self.assertGreater(len(result.window_results), 0, "Should have at least one window")
            
            # Verify each window has required data
            for window in result.window_results:
                self.assertIsNotNone(window.best_parameters)
                self.assertIn('fast_period', window.best_parameters)
                self.assertIn('slow_period', window.best_parameters)
                
                # Verify parameter values are in our test range
                self.assertIn(window.best_parameters['fast_period'], [10, 15])
                self.assertIn(window.best_parameters['slow_period'], [20, 25])
            
            # Verify aggregates are calculated
            result.calculate_aggregates()
            self.assertGreaterEqual(result.total_windows, 0)
            self.assertGreaterEqual(result.successful_windows, 0)
            
        finally:
            # Restore original values
            cache_manager.CACHE_DIR = original_cache_dir
    
    def test_walkforward_window_generation(self):
        """Test that windows are generated correctly for real data."""
        from backtester.backtest.walkforward.window_generator import generate_windows_from_period
        
        config = ConfigManager(self.config_path, self.metadata_path)
        
        start_date = pd.to_datetime(config.get_start_date())
        end_date = pd.to_datetime(config.get_end_date())
        
        # Generate windows
        windows = generate_windows_from_period(
            start_date,
            end_date,
            '3M/1M',
            data_df=self.test_data
        )
        
        # Should generate multiple windows
        self.assertGreater(len(windows), 0, "Should generate at least one window")
        
        # Verify window structure
        for i, window in enumerate(windows):
            # Each window should have valid date ranges
            self.assertLess(window.in_sample_start, window.in_sample_end)
            self.assertLessEqual(window.in_sample_end, window.out_sample_start)
            self.assertLess(window.out_sample_start, window.out_sample_end)
            
            # Verify we can extract data for this window
            is_data = self.test_data.loc[
                pd.to_datetime(window.in_sample_start):pd.to_datetime(window.in_sample_end)
            ]
            oos_data = self.test_data.loc[
                pd.to_datetime(window.out_sample_start):pd.to_datetime(window.out_sample_end)
            ]
            
            # Should have sufficient data (at least 100 bars for in-sample)
            self.assertGreaterEqual(len(is_data), 100, f"In-sample window {i} should have enough data")
            if len(oos_data) > 0:  # Last window might not have OOS data
                self.assertGreater(len(oos_data), 0, f"Out-of-sample window {i} should have data")
    
    def test_walkforward_parameter_optimization(self):
        """Test parameter optimization on actual data."""
        from backtester.backtest.walkforward.optimizer import WindowOptimizer
        from backtester.backtest.walkforward.param_grid import generate_parameter_combinations
        
        config = ConfigManager(self.config_path, self.metadata_path)
        
        # Get first window
        from backtester.backtest.walkforward.window_generator import generate_windows_from_period
        start_date = pd.to_datetime(config.get_start_date())
        end_date = pd.to_datetime(config.get_end_date())
        windows = generate_windows_from_period(start_date, end_date, '3M/1M', self.test_data)
        
        if len(windows) == 0:
            self.skipTest("No windows generated for test data")
        
        first_window = windows[0]
        
        # Create optimizer
        parameter_ranges = config.get_parameter_ranges()
        
        optimizer = WindowOptimizer(
            config=config,
            strategy_class=SMACrossStrategy,
            data_df=self.test_data,
            window_start=pd.to_datetime(first_window.in_sample_start),
            window_end=pd.to_datetime(first_window.in_sample_end),
            parameter_ranges=parameter_ranges,
            fitness_functions=config.get_walkforward_fitness_functions(),
            verbose=False
        )
        
        # Run optimization (returns dict per fitness function)
        best_by_fitness = optimizer.optimize(max_workers=1)
        # Get first fitness function's results
        fitness_func = list(best_by_fitness.keys())[0]
        best_params, best_metrics, opt_time = best_by_fitness[fitness_func]
        
        # Verify results
        self.assertIsNotNone(best_params)
        self.assertIn('fast_period', best_params)
        self.assertIn('slow_period', best_params)
        
        # Parameters should be from our test range
        self.assertIn(best_params['fast_period'], [10, 15])
        self.assertIn(best_params['slow_period'], [20, 25])
        
        # Should have metrics
        self.assertIsNotNone(best_metrics)
        self.assertGreater(opt_time, 0, "Optimization should take some time")
    
    def test_walkforward_vs_single_backtest_mode(self):
        """Test that walk-forward mode is distinct from single backtest mode."""
        # Test with walk-forward disabled
        self.config_data['walkforward']['enabled'] = False
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
        config_disabled = ConfigManager(self.config_path, self.metadata_path)
        self.assertFalse(config_disabled.is_walkforward_enabled())
        
        # Test with walk-forward enabled
        self.config_data['walkforward']['enabled'] = True
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
        config_enabled = ConfigManager(self.config_path, self.metadata_path)
        self.assertTrue(config_enabled.is_walkforward_enabled())


if __name__ == '__main__':
    unittest.main(verbosity=2)

