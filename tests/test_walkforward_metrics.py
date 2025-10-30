"""
Validation tests for walk-forward specific metric calculations.

Tests OOS return aggregation, walk-forward efficiency, and other
walk-forward-specific calculations.
"""

import unittest
import pandas as pd
import numpy as np
import math
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtester.backtest.walkforward.results import (
    WalkForwardResults,
    WalkForwardWindowResult
)
from backtester.backtest.walkforward.metrics_calculator import (
    BacktestMetrics,
    update_walkforward_efficiency
)
from tests.test_metrics_calculator import create_minimal_metrics


def create_test_metrics(**overrides) -> BacktestMetrics:
    """Create BacktestMetrics with overrides for testing."""
    base = create_minimal_metrics()
    for key, value in overrides.items():
        if hasattr(base, key):
            setattr(base, key, value)
    return base


class TestOOSReturnAggregation(unittest.TestCase):
    """Test out-of-sample return aggregation (compounding)."""
    
    def test_single_window_oos_return(self):
        """
        Test OOS return aggregation with a single window.
        
        Single window should produce the same result as the window's OOS return.
        """
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='net_profit'
        )
        
        # Single window with 10% OOS return
        window = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01',
            in_sample_end='2020-12-31',
            out_sample_start='2021-01-01',
            out_sample_end='2021-06-30',
            best_parameters={'fast': 10, 'slow': 30},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=1000.0,
                total_return_pct=10.0
            )
        )
        
        results.window_results.append(window)
        results.calculate_aggregates()
        
        # Single window: total OOS return should equal the window's return
        self.assertAlmostEqual(results.total_oos_return_pct, 10.0, places=2)
        self.assertAlmostEqual(results.avg_oos_return_pct, 10.0, places=2)
        self.assertEqual(results.total_windows, 1)
        self.assertEqual(results.successful_windows, 1)
    
    def test_multiple_windows_oos_compounding(self):
        """
        Test OOS return aggregation with multiple windows (compounding).
        
        Scenario:
        - Window 1: +10% return
        - Window 2: +5% return
        - Window 3: -2% return
        
        Expected compounded return:
        (1 + 0.10) * (1 + 0.05) * (1 - 0.02) - 1
        = 1.10 * 1.05 * 0.98 - 1
        = 1.1319 - 1
        = 0.1319 = 13.19%
        """
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='net_profit'
        )
        
        # Window 1: +10%
        window1 = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01',
            in_sample_end='2020-12-31',
            out_sample_start='2021-01-01',
            out_sample_end='2021-06-30',
            best_parameters={'fast': 10, 'slow': 30},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=1000.0,
                total_return_pct=10.0
            )
        )
        
        # Window 2: +5%
        window2 = WalkForwardWindowResult(
            window_index=1,
            in_sample_start='2020-07-01',
            in_sample_end='2021-06-30',
            out_sample_start='2021-07-01',
            out_sample_end='2021-12-31',
            best_parameters={'fast': 12, 'slow': 35},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=500.0,
                total_return_pct=5.0
            )
        )
        
        # Window 3: -2%
        window3 = WalkForwardWindowResult(
            window_index=2,
            in_sample_start='2021-01-01',
            in_sample_end='2021-12-31',
            out_sample_start='2022-01-01',
            out_sample_end='2022-06-30',
            best_parameters={'fast': 15, 'slow': 40},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=-200.0,
                total_return_pct=-2.0
            )
        )
        
        results.window_results = [window1, window2, window3]
        results.calculate_aggregates()
        
        # Calculate expected compounded return
        # Convert percentages to decimals, compound, convert back
        r1 = 10.0 / 100.0
        r2 = 5.0 / 100.0
        r3 = -2.0 / 100.0
        
        expected_compounded = ((1 + r1) * (1 + r2) * (1 + r3) - 1) * 100.0
        # 1.10 * 1.05 * 0.98 - 1 = 1.1319 - 1 = 0.1319 = 13.19%
        expected_compounded = (1.10 * 1.05 * 0.98 - 1) * 100.0
        
        self.assertAlmostEqual(
            results.total_oos_return_pct,
            expected_compounded,
            places=2,
            msg=f"Compounded return: expected {expected_compounded}%, got {results.total_oos_return_pct}%"
        )
        
        # Average should be (10 + 5 - 2) / 3 = 13 / 3 = 4.33%
        self.assertAlmostEqual(results.avg_oos_return_pct, (10.0 + 5.0 - 2.0) / 3.0, places=2)
        self.assertEqual(results.total_windows, 3)
        self.assertEqual(results.successful_windows, 3)
    
    def test_empty_windows(self):
        """Test aggregation with no successful windows."""
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='net_profit'
        )
        
        results.calculate_aggregates()
        
        self.assertEqual(results.total_oos_return_pct, 0.0)
        self.assertEqual(results.avg_oos_return_pct, 0.0)
        self.assertEqual(results.total_oos_net_profit, 0.0)
        self.assertEqual(results.total_windows, 0)
        self.assertEqual(results.successful_windows, 0)
    
    def test_mixed_successful_windows(self):
        """Test aggregation with some successful and some failed windows."""
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='net_profit'
        )
        
        # Window 1: successful
        window1 = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01',
            in_sample_end='2020-12-31',
            out_sample_start='2021-01-01',
            out_sample_end='2021-06-30',
            best_parameters={'fast': 10, 'slow': 30},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=1000.0,
                total_return_pct=10.0
            )
        )
        
        # Window 2: failed (no OOS metrics)
        window2 = WalkForwardWindowResult(
            window_index=1,
            in_sample_start='2020-07-01',
            in_sample_end='2021-06-30',
            out_sample_start='2021-07-01',
            out_sample_end='2021-12-31',
            best_parameters={'fast': 12, 'slow': 35},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=None  # Failed window
        )
        
        # Window 3: successful
        window3 = WalkForwardWindowResult(
            window_index=2,
            in_sample_start='2021-01-01',
            in_sample_end='2021-12-31',
            out_sample_start='2022-01-01',
            out_sample_end='2022-06-30',
            best_parameters={'fast': 15, 'slow': 40},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=500.0,
                total_return_pct=5.0
            )
        )
        
        results.window_results = [window1, window2, window3]
        results.calculate_aggregates()
        
        # Should only compound successful windows (10% and 5%)
        expected_compounded = (1.10 * 1.05 - 1) * 100.0  # = 15.5%
        
        self.assertAlmostEqual(results.total_oos_return_pct, expected_compounded, places=2)
        self.assertAlmostEqual(results.avg_oos_return_pct, (10.0 + 5.0) / 2.0, places=2)
        self.assertEqual(results.total_windows, 3)
        self.assertEqual(results.successful_windows, 2)


class TestWalkForwardEfficiency(unittest.TestCase):
    """Test walk-forward efficiency calculation."""
    
    def test_efficiency_calculation_positive_returns(self):
        """
        Test efficiency calculation with positive returns.
        
        Scenario:
        - IS return: 10%
        - OOS return: 8%
        - Expected efficiency: 8% / 10% = 0.8 (80%)
        """
        is_metrics = create_test_metrics(total_return_pct=10.0)
        oos_metrics = create_test_metrics(total_return_pct=8.0)
        
        efficiency = oos_metrics.total_return_pct / is_metrics.total_return_pct
        updated_metrics = update_walkforward_efficiency(oos_metrics, efficiency)
        
        self.assertAlmostEqual(updated_metrics.walkforward_efficiency, 0.8, places=2)
    
    def test_efficiency_calculation_zero_is_return(self):
        """
        Test efficiency when IS return is zero.
        
        Scenario:
        - IS return: 0%
        - OOS return: 5%
        - Expected efficiency: 0.0 (handled in runner)
        """
        is_metrics = create_test_metrics(total_return_pct=0.0)
        oos_metrics = create_test_metrics(total_return_pct=5.0)
        
        # Efficiency should be 0.0 when IS return is 0 or negative
        efficiency = 0.0
        updated_metrics = update_walkforward_efficiency(oos_metrics, efficiency)
        
        self.assertEqual(updated_metrics.walkforward_efficiency, 0.0)
    
    def test_efficiency_calculation_negative_returns(self):
        """
        Test efficiency calculation with negative returns.
        
        Scenario:
        - IS return: -5% (loss)
        - OOS return: -2% (smaller loss, better!)
        - Efficiency: -2% / -5% = 0.4 (40%, meaning OOS did better)
        """
        is_metrics = create_test_metrics(total_return_pct=-5.0)
        oos_metrics = create_test_metrics(total_return_pct=-2.0)
        
        # When both are negative, efficiency still calculated: -2 / -5 = 0.4
        efficiency = oos_metrics.total_return_pct / is_metrics.total_return_pct
        updated_metrics = update_walkforward_efficiency(oos_metrics, efficiency)
        
        self.assertAlmostEqual(updated_metrics.walkforward_efficiency, 0.4, places=2)
    
    def test_efficiency_preserves_other_metrics(self):
        """Test that update_walkforward_efficiency preserves all other metric values."""
        original_metrics = create_test_metrics(
            net_profit=1000.0,
            total_return_pct=8.0,
            sharpe_ratio=1.5,
            max_drawdown=500.0,
            num_trades=10
        )
        
        efficiency = 0.8
        updated_metrics = update_walkforward_efficiency(original_metrics, efficiency)
        
        # All other fields should be unchanged
        self.assertEqual(updated_metrics.net_profit, original_metrics.net_profit)
        self.assertEqual(updated_metrics.total_return_pct, original_metrics.total_return_pct)
        self.assertEqual(updated_metrics.sharpe_ratio, original_metrics.sharpe_ratio)
        self.assertEqual(updated_metrics.max_drawdown, original_metrics.max_drawdown)
        self.assertEqual(updated_metrics.num_trades, original_metrics.num_trades)
        
        # Only efficiency should be updated
        self.assertEqual(updated_metrics.walkforward_efficiency, efficiency)


class TestWalkForwardNetProfitAggregation(unittest.TestCase):
    """Test net profit aggregation (summing, not compounding)."""
    
    def test_net_profit_summation(self):
        """
        Test that net profits are summed (not compounded).
        
        Net profit is in dollars, not percentages, so it's additive.
        """
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='net_profit'
        )
        
        window1 = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01',
            in_sample_end='2020-12-31',
            out_sample_start='2021-01-01',
            out_sample_end='2021-06-30',
            best_parameters={'fast': 10, 'slow': 30},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=1000.0,
                total_return_pct=10.0
            )
        )
        
        window2 = WalkForwardWindowResult(
            window_index=1,
            in_sample_start='2020-07-01',
            in_sample_end='2021-06-30',
            out_sample_start='2021-07-01',
            out_sample_end='2021-12-31',
            best_parameters={'fast': 12, 'slow': 35},
            in_sample_metrics=create_minimal_metrics(),
            out_sample_metrics=create_test_metrics(
                net_profit=500.0,
                total_return_pct=5.0
            )
        )
        
        results.window_results = [window1, window2]
        results.calculate_aggregates()
        
        # Net profit should be summed: 1000 + 500 = 1500
        self.assertAlmostEqual(results.total_oos_net_profit, 1500.0, places=2)


if __name__ == '__main__':
    unittest.main()

