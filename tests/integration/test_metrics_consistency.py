"""
Tests to verify single backtest and walk-forward produce identical metrics for same data.

This module ensures that when the same data and parameters are used in both:
1. A single backtest
2. A walk-forward window (where IS period equals the full data range)

The calculated metrics should be identical (or very close due to rounding).
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtester.backtest.engine import run_backtest
from backtester.backtest.walkforward.optimizer import WindowOptimizer
from backtester.backtest.walkforward.runner import WalkForwardRunner
from backtester.backtest.walkforward.metrics_calculator import calculate_metrics, BacktestMetrics
from backtester.config import ConfigManager
from backtester.strategies.sma_cross import SMACrossStrategy


class TestMetricsConsistency(unittest.TestCase):
    """Test that single backtest and walk-forward produce identical metrics."""
    
    def setUp(self):
        """Set up test data and configuration."""
        # Create reproducible test data
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        
        # Create price data with some trend
        base_price = 10000
        returns = np.random.randn(len(dates)) * 0.02
        prices = base_price * (1 + returns).cumprod()
        
        self.test_data = pd.DataFrame({
            'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
            'high': prices * (1 + abs(np.random.randn(len(dates)) * 0.001)),
            'low': prices * (1 - abs(np.random.randn(len(dates)) * 0.001)),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)
        
        self.config = ConfigManager()
    
    def test_single_vs_walkforward_identical_period(self):
        """
        Test that single backtest and walk-forward with identical period produce same metrics.
        
        Scenario:
        - Single backtest on full data
        - Walk-forward with IS period = full data (no OOS period)
        - Metrics should be identical
        """
        # Parameters to test
        test_params = {
            'fast_period': 10,
            'slow_period': 30
        }
        
        # Run single backtest
        result_dict, cerebro, strategy_instance, single_metrics = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            strategy_params=test_params,
            return_metrics=True
        )
        
        # Run walk-forward with IS period = full data
        # We'll use WindowOptimizer with IS period covering all data
        optimizer = WindowOptimizer(
            self.config,
            SMACrossStrategy,
            self.test_data,  # Use full data as IS
            window_start=self.test_data.index[0],
            window_end=self.test_data.index[-1],
            parameter_ranges={
                'fast_period': {'start': 10, 'end': 10, 'step': 1},
                'slow_period': {'start': 30, 'end': 30, 'step': 1}
            },
            fitness_functions=['net_profit'],
            verbose=False
        )
        
        best_by_fitness = optimizer.optimize(max_workers=1)
        params, wf_metrics, opt_time = best_by_fitness['net_profit']
        
        # Compare key metrics
        # Using assertAlmostEqual for floating point comparison
        self.assertAlmostEqual(
            single_metrics.net_profit,
            wf_metrics.net_profit,
            places=2,
            msg="Net profit should match between single and walk-forward"
        )
        
        self.assertAlmostEqual(
            single_metrics.total_return_pct,
            wf_metrics.total_return_pct,
            places=2,
            msg="Total return % should match between single and walk-forward"
        )
        
        self.assertAlmostEqual(
            single_metrics.max_drawdown,
            wf_metrics.max_drawdown,
            places=2,
            msg="Max drawdown should match between single and walk-forward"
        )
        
        self.assertEqual(
            single_metrics.num_trades,
            wf_metrics.num_trades,
            msg="Number of trades should match between single and walk-forward"
        )
        
        # Compare all numeric metrics
        for field_name, field_info in BacktestMetrics.__dataclass_fields__.items():
            single_value = getattr(single_metrics, field_name)
            wf_value = getattr(wf_metrics, field_name)
            
            # Skip walkforward_efficiency (only calculated in walk-forward)
            if field_name == 'walkforward_efficiency':
                continue
            
            # Compare based on type
            if isinstance(single_value, (int, float)) and isinstance(wf_value, (int, float)):
                # Skip infinity and NaN comparisons
                if np.isinf(single_value) or np.isinf(wf_value):
                    continue
                if np.isnan(single_value) or np.isnan(wf_value):
                    continue
                
                # Use appropriate tolerance
                if isinstance(single_value, float) and isinstance(wf_value, float):
                    self.assertAlmostEqual(
                        single_value,
                        wf_value,
                        places=4,
                        msg=f"Field {field_name} should match: single={single_value}, wf={wf_value}"
                    )
                else:
                    self.assertEqual(
                        single_value,
                        wf_value,
                        msg=f"Field {field_name} should match: single={single_value}, wf={wf_value}"
                    )
    
    def test_multiple_runs_consistency(self):
        """
        Test that running the same backtest multiple times produces identical results.
        
        This ensures deterministic behavior and no state leakage.
        """
        test_params = {
            'fast_period': 10,
            'slow_period': 30
        }
        
        # Run backtest twice
        result1_dict, _, _, metrics1 = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            strategy_params=test_params,
            return_metrics=True
        )
        
        result2_dict, _, _, metrics2 = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            strategy_params=test_params,
            return_metrics=True
        )
        
        # Results should be identical
        for field_name in BacktestMetrics.__dataclass_fields__:
            value1 = getattr(metrics1, field_name)
            value2 = getattr(metrics2, field_name)
            
            if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
                if np.isinf(value1) or np.isinf(value2):
                    self.assertTrue(np.isinf(value1) and np.isinf(value2))
                    continue
                if np.isnan(value1) or np.isnan(value2):
                    self.assertTrue(np.isnan(value1) and np.isnan(value2))
                    continue
                
                if isinstance(value1, float):
                    self.assertAlmostEqual(value1, value2, places=6)
                else:
                    self.assertEqual(value1, value2)


if __name__ == '__main__':
    unittest.main()

