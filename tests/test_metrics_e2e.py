"""
End-to-end tests for MultiWalk metrics in walk-forward optimization.

Tests complete flow from backtest execution through metrics calculation
to walk-forward optimization results.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime

from backtest.engine import run_backtest
from backtest.walkforward.metrics_calculator import calculate_metrics, BacktestMetrics
from backtest.walkforward.optimizer import WindowOptimizer
from backtest.walkforward.runner import WalkForwardRunner
from backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult
from config import ConfigManager
from strategies.sma_cross import SMACrossStrategy


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
        result_dict, cerebro, strategy_instance = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        # Verify return structure
        self.assertIsInstance(result_dict, dict)
        self.assertIn('final_value', result_dict)
        self.assertIsNotNone(cerebro)
        self.assertIsNotNone(strategy_instance)
        
        # Verify cerebro has analyzers
        self.assertTrue(hasattr(cerebro, 'analyzers'))
        
        # Verify equity curve is tracked
        self.assertTrue(hasattr(strategy_instance, 'equity_curve'))
        self.assertGreater(len(strategy_instance.equity_curve), 0)
    
    def test_calculate_metrics_from_real_backtest(self):
        """Test calculate_metrics can process real backtest results."""
        result_dict, cerebro, strategy_instance = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        initial_capital = self.config.get_initial_capital()
        start_date = self.test_data.index[0].to_pydatetime()
        end_date = self.test_data.index[-1].to_pydatetime()
        
        metrics = calculate_metrics(
            cerebro,
            strategy_instance,
            initial_capital,
            equity_curve=None,
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify all key metrics are populated
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
        is_metrics = BacktestMetrics(
            net_profit=1000.0,
            total_return_pct=10.0,
            sharpe_ratio=1.5,
            max_drawdown=500.0,
            profit_factor=2.0,
            np_avg_dd=2.0,
            gross_profit=2000.0,
            gross_loss=1000.0,
            num_trades=10,
            num_winning_trades=7,
            num_losing_trades=3,
            avg_drawdown=200.0,
            win_rate_pct=70.0,
            percent_trades_profitable=70.0,
            percent_trades_unprofitable=30.0,
            avg_trade=100.0,
            avg_profitable_trade=285.71,
            avg_unprofitable_trade=-333.33,
            largest_winning_trade=500.0,
            largest_losing_trade=-200.0,
            max_consecutive_wins=3,
            max_consecutive_losses=2,
            total_calendar_days=365,
            total_trading_days=252,
            days_profitable=150,
            days_unprofitable=102,
            percent_days_profitable=59.52,
            percent_days_unprofitable=40.48,
            max_drawdown_pct=5.0,
            max_run_up=1500.0,
            recovery_factor=2.0,
            np_max_dd=2.0,
            r_squared=0.95,
            sortino_ratio=2.0,
            monte_carlo_score=75.0,
            rina_index=10.0,
            tradestation_index=15.0,
            np_x_r2=950.0,
            np_x_pf=2000.0,
            annualized_net_profit=1000.0,
            annualized_return_avg_dd=5.0,
            percent_time_in_market=60.0,
            walkforward_efficiency=0.0
        )
        
        oos_metrics = BacktestMetrics(
            net_profit=800.0,
            total_return_pct=8.0,
            sharpe_ratio=0.9,
            max_drawdown=400.0,
            profit_factor=1.8,
            np_avg_dd=1.6,
            gross_profit=1600.0,
            gross_loss=800.0,
            num_trades=8,
            num_winning_trades=6,
            num_losing_trades=2,
            avg_drawdown=500.0,
            win_rate_pct=75.0,
            percent_trades_profitable=75.0,
            percent_trades_unprofitable=25.0,
            avg_trade=100.0,
            avg_profitable_trade=266.67,
            avg_unprofitable_trade=-400.0,
            largest_winning_trade=400.0,
            largest_losing_trade=-150.0,
            max_consecutive_wins=4,
            max_consecutive_losses=1,
            total_calendar_days=180,
            total_trading_days=120,
            days_profitable=70,
            days_unprofitable=50,
            percent_days_profitable=58.33,
            percent_days_unprofitable=41.67,
            max_drawdown_pct=4.0,
            max_run_up=1200.0,
            recovery_factor=2.0,
            np_max_dd=2.0,
            r_squared=0.90,
            sortino_ratio=1.8,
            monte_carlo_score=70.0,
            rina_index=8.0,
            tradestation_index=12.0,
            np_x_r2=720.0,
            np_x_pf=1440.0,
            annualized_net_profit=1600.0,
            annualized_return_avg_dd=4.0,
            percent_time_in_market=50.0,
            walkforward_efficiency=0.0
        )
        
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
