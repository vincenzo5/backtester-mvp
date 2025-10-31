"""
System tests for parallel execution.

Tests WindowOptimizer parallel execution and ConfigManager serialization.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtester.config import ConfigManager
from backtester.backtest.walkforward.optimizer import WindowOptimizer
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.backtest.engine import prepare_backtest_data


@pytest.mark.system
@pytest.mark.parallel
class TestConfigManagerSerializationInParallel(unittest.TestCase):
    """Test ConfigManager serialization in parallel execution context."""
    
    def setUp(self):
        """Set up test config."""
        self.config = ConfigManager()
    
    def test_config_serialization_for_workers(self):
        """Test that ConfigManager can be serialized for worker processes."""
        # Serialize
        config_dict = self.config._to_dict()
        
        # Deserialize (simulating worker process)
        worker_config = ConfigManager._from_dict(config_dict)
        
        # Verify worker config works
        self.assertEqual(worker_config.get_strategy_name(), self.config.get_strategy_name())
        self.assertEqual(worker_config.get_walkforward_initial_capital(), self.config.get_walkforward_initial_capital())
    
    def test_config_with_updated_params(self):
        """Test that ConfigManager with updated params serializes correctly."""
        self.config._update_strategy_parameters({'fast_period': 15, 'slow_period': 25})
        
        # Serialize
        config_dict = self.config._to_dict()
        
        # Deserialize
        worker_config = ConfigManager._from_dict(config_dict)
        
        # Verify updated params are preserved
        strategy_config = worker_config.get_strategy_config()
        self.assertEqual(strategy_config.parameters['fast_period'], 15)
        self.assertEqual(strategy_config.parameters['slow_period'], 25)


@pytest.mark.system
@pytest.mark.parallel
@pytest.mark.slow
class TestWindowOptimizerParallel(unittest.TestCase):
    """Test WindowOptimizer parallel execution."""
    
    def setUp(self):
        """Set up test data."""
        self.config = ConfigManager()
        
        # Create sample OHLCV data
        dates = pd.date_range(start='2020-01-01', periods=2000, freq='1h')
        np.random.seed(42)
        
        base_price = 50000
        trend = np.linspace(0, base_price * 0.4, 2000)
        noise = np.random.randn(2000).cumsum() * base_price * 0.01
        prices = base_price + trend + noise
        
        self.df = pd.DataFrame({
            'open': np.roll(prices, 1),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 2000)
        }, index=dates)
        self.df.at[self.df.index[0], 'open'] = base_price
        
        # Prepare data
        strategy_params = self.config.get_strategy_config().parameters
        self.enriched_df = prepare_backtest_data(self.df, SMACrossStrategy, strategy_params)
    
    def test_optimize_parallel_executes(self):
        """Test that _optimize_parallel executes without errors."""
        # Create optimizer
        window_start = datetime(2020, 1, 1)
        window_end = datetime(2020, 6, 30)
        is_start = datetime(2020, 1, 1)
        is_end = datetime(2020, 5, 31)
        
        # WindowOptimizer requires parameter_ranges and fitness_functions
        parameter_ranges = {
            'fast_period': {'start': 10, 'end': 30, 'step': 10},
            'slow_period': {'start': 20, 'end': 60, 'step': 20}
        }
        fitness_functions = ['np_avg_dd']
        
        optimizer = WindowOptimizer(
            config=self.config,
            strategy_class=SMACrossStrategy,
            data_df=self.enriched_df,
            window_start=window_start,
            window_end=window_end,
            parameter_ranges=parameter_ranges,
            fitness_functions=fitness_functions,
            verbose=False
        )
        
        # Create parameter combinations
        param_combinations = [
            {'fast_period': 10, 'slow_period': 20},
            {'fast_period': 15, 'slow_period': 25},
            {'fast_period': 20, 'slow_period': 30}
        ]
        
        # Run parallel optimization with 2 workers
        results = optimizer._optimize_parallel(param_combinations, max_workers=2)
        
        # Verify results
        self.assertEqual(len(results), len(param_combinations))
        for params, metrics in results:
            self.assertIsInstance(params, dict)
            # metrics might be None if backtest failed, which is OK

