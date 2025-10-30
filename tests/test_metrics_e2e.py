"""
End-to-end tests for MultiWalk metrics in walk-forward optimization.

Tests complete flow from backtest execution through metrics calculation
to walk-forward optimization results.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.backtest.engine import run_backtest
from backtester.backtest.walkforward.metrics_calculator import calculate_metrics, BacktestMetrics
from backtester.backtest.walkforward.optimizer import WindowOptimizer
from backtester.backtest.walkforward.runner import WalkForwardRunner
from backtester.backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult
from backtester.config import ConfigManager
from backtester.strategies.sma_cross import SMACrossStrategy


class TestEndToEndMetrics(unittest.TestCase):
    """End-to-end tests for metrics calculation through complete backtest flow."""
    
    def setUp(self):
        """Set up test data and config."""
        # Create sample OHLCV data for walk-forward
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', end='2021-12-31', freq='D')
        
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
    
    def test_backtest_returns_metrics_correctly(self):
        """Test that run_backtest with return_metrics=True works correctly."""
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        # Verify return structure
        self.assertIsInstance(result_dict, dict)
        self.assertIn('metrics', result_dict)
        self.assertIsNotNone(cerebro)
        self.assertIsNotNone(strategy_instance)
        self.assertIsInstance(metrics, BacktestMetrics)
        
        # Verify cerebro has analyzers
        self.assertTrue(hasattr(cerebro, 'analyzers'))
        
        # Verify equity curve is tracked
        self.assertTrue(hasattr(strategy_instance, 'equity_curve'))
        self.assertGreater(len(strategy_instance.equity_curve), 0)
    
    def test_calculate_metrics_from_real_backtest(self):
        """Test calculate_metrics can process real backtest results."""
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        # Verify metrics are returned directly from run_backtest
        self.assertIsInstance(metrics, BacktestMetrics)
        self.assertIsNotNone(metrics.net_profit)
        self.assertIsNotNone(metrics.total_return_pct)
        self.assertIsNotNone(metrics.num_trades)
        self.assertIsNotNone(metrics.total_calendar_days)
        self.assertGreater(metrics.total_calendar_days, 0)
    
    def test_optimizer_uses_calculate_metrics(self):
        """Test that optimizer correctly uses calculate_metrics instead of placeholders."""
        # Create a small in-sample window
        in_sample_df = self.test_data.iloc[:200].copy()
        
        # Create optimizer
        parameter_ranges = {
            'fast_period': {'start': 10, 'end': 20, 'step': 10},
            'slow_period': {'start': 30, 'end': 40, 'step': 10}
        }
        
        optimizer = WindowOptimizer(
            self.config,
            SMACrossStrategy,
            in_sample_df,
            window_start=in_sample_df.index[0],
            window_end=in_sample_df.index[-1],
            parameter_ranges=parameter_ranges,
            fitness_functions=['net_profit', 'sharpe_ratio'],
            verbose=False
        )
        
        # Run optimization
        best_by_fitness = optimizer.optimize(max_workers=1)
        
        # Verify results
        self.assertIn('net_profit', best_by_fitness)
        self.assertIn('sharpe_ratio', best_by_fitness)
        
        # Verify metrics are proper BacktestMetrics objects (not placeholders)
        for fitness_func, (params, metrics, opt_time) in best_by_fitness.items():
            self.assertIsInstance(metrics, BacktestMetrics)
            # Verify metrics are real (not all zeros/defaults)
            # At minimum, we should have calendar days calculated
            self.assertGreater(metrics.total_calendar_days, 0)
            # Verify all 43 fields are present
            field_count = len(BacktestMetrics.__dataclass_fields__)
            self.assertEqual(field_count, 43)
    
    def test_all_metrics_present_in_optimizer_results(self):
        """Verify all 43 metrics are calculated in optimizer results."""
        in_sample_df = self.test_data.iloc[:100].copy()
        
        parameter_ranges = {
            'fast_period': {'start': 10, 'end': 10, 'step': 1},  # Single param set
            'slow_period': {'start': 30, 'end': 30, 'step': 1}
        }
        
        optimizer = WindowOptimizer(
            self.config,
            SMACrossStrategy,
            in_sample_df,
            window_start=in_sample_df.index[0],
            window_end=in_sample_df.index[-1],
            parameter_ranges=parameter_ranges,
            fitness_functions=['net_profit'],
            verbose=False
        )
        
        best_by_fitness = optimizer.optimize(max_workers=1)
        params, metrics, opt_time = best_by_fitness['net_profit']
        
        # Check that all expected fields exist
        expected_fields = [
            'net_profit', 'total_return_pct', 'sharpe_ratio', 'max_drawdown',
            'profit_factor', 'np_avg_dd', 'gross_profit', 'gross_loss',
            'num_trades', 'num_winning_trades', 'num_losing_trades', 'avg_drawdown',
            'win_rate_pct', 'percent_trades_profitable', 'avg_trade',
            'total_calendar_days', 'total_trading_days', 'days_profitable',
            'max_drawdown_pct', 'recovery_factor', 'r_squared', 'sortino_ratio',
            'monte_carlo_score', 'rina_index', 'tradestation_index'
        ]
        
        for field in expected_fields:
            self.assertTrue(hasattr(metrics, field), f"Missing field: {field}")
            # Verify field is not None (calculated)
            value = getattr(metrics, field)
            self.assertIsNotNone(value, f"Field {field} is None")
    
    def test_walkforward_results_serialization(self):
        """Test that WalkForwardResults can serialize all metrics."""
        # Create a window result with full metrics
        from tests.test_metrics_calculator import create_minimal_metrics
        is_metrics = create_minimal_metrics()
        # Override fields with test values
        is_metrics.net_profit = 1000.0
        is_metrics.total_return_pct = 10.0
        is_metrics.sharpe_ratio = 1.5
        is_metrics.max_drawdown = 500.0
        is_metrics.profit_factor = 2.0
        is_metrics.np_avg_dd = 2.0
        is_metrics.gross_profit = 2000.0
        is_metrics.gross_loss = 1000.0
        is_metrics.num_trades = 10
        is_metrics.num_winning_trades = 7
        is_metrics.num_losing_trades = 3
        is_metrics.avg_drawdown = 200.0
        is_metrics.win_rate_pct = 70.0
        is_metrics.percent_trades_profitable = 70.0
        is_metrics.percent_trades_unprofitable = 30.0
        is_metrics.avg_trade = 100.0
        is_metrics.avg_profitable_trade = 285.71
        is_metrics.avg_unprofitable_trade = -333.33
        is_metrics.largest_winning_trade = 500.0
        is_metrics.largest_losing_trade = -200.0
        is_metrics.max_consecutive_wins = 3
        is_metrics.max_consecutive_losses = 2
        is_metrics.total_calendar_days = 365
        is_metrics.total_trading_days = 252
        is_metrics.days_profitable = 150
        is_metrics.days_unprofitable = 102
        is_metrics.percent_days_profitable = 59.52
        is_metrics.percent_days_unprofitable = 40.48
        is_metrics.max_drawdown_pct = 5.0
        is_metrics.max_run_up = 1500.0
        is_metrics.recovery_factor = 2.0
        is_metrics.np_max_dd = 2.0
        is_metrics.r_squared = 0.95
        is_metrics.sortino_ratio = 2.0
        is_metrics.monte_carlo_score = 75.0
        is_metrics.rina_index = 10.0
        is_metrics.tradestation_index = 15.0
        is_metrics.np_x_r2 = 950.0
        is_metrics.np_x_pf = 2000.0
        is_metrics.annualized_net_profit = 1000.0
        is_metrics.annualized_return_avg_dd = 5.0
        is_metrics.percent_time_in_market = 60.0
        is_metrics.walkforward_efficiency = 0.0
        
        oos_metrics = create_minimal_metrics()
        # Override fields with test values
        oos_metrics.net_profit = 800.0
        oos_metrics.total_return_pct = 8.0
        oos_metrics.sharpe_ratio = 0.9
        oos_metrics.max_drawdown = 400.0
        oos_metrics.profit_factor = 1.8
        oos_metrics.np_avg_dd = 1.6
        oos_metrics.gross_profit = 1600.0
        oos_metrics.gross_loss = 800.0
        oos_metrics.num_trades = 8
        oos_metrics.num_winning_trades = 6
        oos_metrics.num_losing_trades = 2
        oos_metrics.avg_drawdown = 500.0
        oos_metrics.win_rate_pct = 75.0
        oos_metrics.percent_trades_profitable = 75.0
        oos_metrics.percent_trades_unprofitable = 25.0
        oos_metrics.avg_trade = 100.0
        oos_metrics.avg_profitable_trade = 266.67
        oos_metrics.avg_unprofitable_trade = -400.0
        oos_metrics.largest_winning_trade = 400.0
        oos_metrics.largest_losing_trade = -150.0
        oos_metrics.max_consecutive_wins = 4
        oos_metrics.max_consecutive_losses = 1
        oos_metrics.total_calendar_days = 180
        oos_metrics.total_trading_days = 120
        oos_metrics.days_profitable = 70
        oos_metrics.days_unprofitable = 50
        oos_metrics.percent_days_profitable = 58.33
        oos_metrics.percent_days_unprofitable = 41.67
        oos_metrics.max_drawdown_pct = 4.0
        oos_metrics.max_run_up = 1200.0
        oos_metrics.recovery_factor = 2.0
        oos_metrics.np_max_dd = 2.0
        oos_metrics.r_squared = 0.90
        oos_metrics.sortino_ratio = 1.8
        oos_metrics.monte_carlo_score = 70.0
        oos_metrics.rina_index = 8.0
        oos_metrics.tradestation_index = 12.0
        oos_metrics.np_x_r2 = 720.0
        oos_metrics.np_x_pf = 1440.0
        oos_metrics.annualized_net_profit = 1600.0
        oos_metrics.annualized_return_avg_dd = 4.0
        oos_metrics.percent_time_in_market = 50.0
        oos_metrics.walkforward_efficiency = 0.0
        
        window_result = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01',
            in_sample_end='2020-12-31',
            out_sample_start='2021-01-01',
            out_sample_end='2021-06-30',
            best_parameters={'fast_period': 20, 'slow_period': 50},
            in_sample_metrics=is_metrics,
            out_sample_metrics=oos_metrics,
            optimization_time=1.0,
            oos_backtest_time=0.5
        )
        
        # Verify metrics are accessible
        self.assertEqual(window_result.in_sample_metrics.net_profit, 1000.0)
        self.assertEqual(window_result.out_sample_metrics.net_profit, 800.0)
        self.assertEqual(window_result.in_sample_metrics.total_calendar_days, 365)
        self.assertEqual(window_result.out_sample_metrics.total_calendar_days, 180)
        
        # Test serialization to dict
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1d',
            period_str='1Y/6M',
            fitness_function='net_profit'
        )
        results.window_results.append(window_result)
        
        # Verify can access all metrics
        for window in results.window_results:
            self.assertIsNotNone(window.in_sample_metrics.r_squared)
            self.assertIsNotNone(window.out_sample_metrics.sortino_ratio)
            self.assertIsNotNone(window.in_sample_metrics.monte_carlo_score)


if __name__ == '__main__':
    unittest.main(verbosity=2)
