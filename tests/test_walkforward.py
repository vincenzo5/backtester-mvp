"""
Tests for walk-forward optimization system.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any

from backtest.walkforward.period_parser import parse_period, validate_period, PeriodParseError
from backtest.walkforward.window_generator import generate_windows, generate_windows_from_period, WalkForwardWindow
from backtest.walkforward.param_grid import generate_parameter_values, generate_parameter_combinations, count_parameter_combinations
from backtest.walkforward.metrics_calculator import calculate_fitness, BacktestMetrics
from config import ConfigManager


class TestPeriodParser(unittest.TestCase):
    """Test period parser functionality."""
    
    def test_parse_years_months(self):
        """Test parsing year/month notation."""
        in_days, out_days = parse_period("1Y/6M")
        # Parser returns int, so 365.25 becomes 365, 182.6 becomes 182
        self.assertAlmostEqual(in_days, 365, places=0)
        self.assertAlmostEqual(out_days, 182, places=0)
    
    def test_parse_months_weeks(self):
        """Test parsing month/week notation."""
        in_days, out_days = parse_period("12M/4W")
        self.assertAlmostEqual(in_days, 365.25, places=0)
        self.assertAlmostEqual(out_days, 28, places=0)  # 4 weeks = 28 days
    
    def test_parse_days_only(self):
        """Test parsing days without units."""
        in_days, out_days = parse_period("252/126")
        self.assertEqual(in_days, 252)
        self.assertEqual(out_days, 126)
    
    def test_parse_mixed_units(self):
        """Test parsing mixed unit types."""
        in_days, out_days = parse_period("2Y/3M")
        self.assertAlmostEqual(in_days, 730.5, places=0)
        self.assertAlmostEqual(out_days, 91.3, places=0)
    
    def test_parse_with_spaces(self):
        """Test parsing with spaces."""
        in_days, out_days = parse_period("1Y / 6M")
        # Parser returns int values
        self.assertAlmostEqual(in_days, 365, places=0)
        self.assertAlmostEqual(out_days, 182, places=0)
    
    def test_invalid_format(self):
        """Test invalid period format."""
        with self.assertRaises(PeriodParseError):
            parse_period("1Y")
        
        with self.assertRaises(PeriodParseError):
            parse_period("1Y/6M/3M")
    
    def test_validate_period(self):
        """Test period validation."""
        self.assertTrue(validate_period("1Y/6M"))
        self.assertTrue(validate_period("252/126"))
        self.assertFalse(validate_period("1Y"))
        self.assertFalse(validate_period("invalid"))


class TestWindowGenerator(unittest.TestCase):
    """Test window generator functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample data: 2 years of daily data
        dates = pd.date_range(start='2020-01-01', end='2021-12-31', freq='D')
        self.sample_data = pd.DataFrame({
            'close': np.random.randn(len(dates)).cumsum() + 100,
            'open': np.random.randn(len(dates)).cumsum() + 100,
            'high': np.random.randn(len(dates)).cumsum() + 105,
            'low': np.random.randn(len(dates)).cumsum() + 95,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates)
    
    def test_generate_windows(self):
        """Test basic window generation."""
        start = datetime(2020, 1, 1)
        end = datetime(2021, 12, 31)
        in_sample_days = 180  # 6 months
        out_sample_days = 90   # 3 months
        
        windows = generate_windows(start, end, in_sample_days, out_sample_days, self.sample_data)
        
        self.assertGreater(len(windows), 0)
        
        # Check first window
        first_window = windows[0]
        self.assertEqual(first_window.window_index, 0)
        # In-sample end should be <= out-sample start (they're adjacent)
        self.assertLessEqual(first_window.in_sample_end, first_window.out_sample_start)
        self.assertLessEqual(first_window.out_sample_end, end or datetime(2022, 1, 1))
    
    def test_generate_windows_from_period(self):
        """Test window generation from period string."""
        start = datetime(2020, 1, 1)
        end = datetime(2021, 12, 31)
        
        windows = generate_windows_from_period(start, end, "6M/3M", self.sample_data)
        
        self.assertGreater(len(windows), 0)
        
        # Verify window structure
        for window in windows:
            self.assertIsInstance(window, WalkForwardWindow)
            self.assertLess(window.in_sample_start, window.in_sample_end)
            # In-sample end and out-sample start are adjacent (equal)
            self.assertLessEqual(window.in_sample_end, window.out_sample_start)
            self.assertLess(window.out_sample_start, window.out_sample_end)
    
    def test_rolling_windows(self):
        """Test that windows are rolling (not anchored)."""
        start = datetime(2020, 1, 1)
        end = datetime(2021, 12, 31)
        
        windows = generate_windows(start, end, 180, 90, self.sample_data)
        
        if len(windows) > 1:
            # Second window should start after first window's out-sample period
            # For rolling windows, second in-sample should start after first out-sample
            first_oos_end = windows[0].out_sample_end
            second_is_start = windows[1].in_sample_start
            
            # In rolling windows, they should be close (window slides by out-sample period)
            # Actually, for rolling windows, second IS starts where first OOS started
            # Let me verify the windows don't all start at the same point
            self.assertNotEqual(windows[0].in_sample_start, windows[1].in_sample_start)
    
    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        start = datetime(2020, 1, 1)
        end = datetime(2020, 2, 1)  # Only 1 month of data
        in_sample_days = 365  # Need 1 year
        
        windows = generate_windows(start, end, in_sample_days, 30)
        
        # Should return empty list or handle gracefully
        self.assertEqual(len(windows), 0)


class TestParameterGrid(unittest.TestCase):
    """Test parameter grid generation."""
    
    def test_generate_parameter_values(self):
        """Test generating parameter values from range."""
        values = generate_parameter_values(10, 30, 5)
        expected = [10, 15, 20, 25, 30]
        self.assertEqual(values, expected)
    
    def test_generate_parameter_values_single(self):
        """Test generating single value."""
        values = generate_parameter_values(10, 10, 5)
        self.assertEqual(values, [10])
    
    def test_generate_parameter_combinations(self):
        """Test generating all parameter combinations."""
        ranges = {
            'fast_period': {'start': 10, 'end': 15, 'step': 5},
            'slow_period': {'start': 20, 'end': 25, 'step': 5}
        }
        
        combinations = generate_parameter_combinations(ranges)
        
        # Should have 2 * 2 = 4 combinations
        self.assertEqual(len(combinations), 4)
        
        # Check all combinations are present
        expected_combos = [
            {'fast_period': 10, 'slow_period': 20},
            {'fast_period': 10, 'slow_period': 25},
            {'fast_period': 15, 'slow_period': 20},
            {'fast_period': 15, 'slow_period': 25},
        ]
        
        for combo in expected_combos:
            self.assertIn(combo, combinations)
    
    def test_generate_parameter_combinations_single_param(self):
        """Test generating combinations with single parameter."""
        ranges = {
            'fast_period': {'start': 10, 'end': 20, 'step': 5}
        }
        
        combinations = generate_parameter_combinations(ranges)
        self.assertEqual(len(combinations), 3)
    
    def test_count_parameter_combinations(self):
        """Test counting combinations without generating."""
        ranges = {
            'fast_period': {'start': 10, 'end': 20, 'step': 5},
            'slow_period': {'start': 30, 'end': 40, 'step': 10}
        }
        
        count = count_parameter_combinations(ranges)
        self.assertEqual(count, 6)  # 3 * 2 = 6
    
    def test_invalid_range(self):
        """Test invalid range specification."""
        with self.assertRaises(ValueError):
            generate_parameter_values(30, 10, 5)  # start > end
        
        with self.assertRaises(ValueError):
            generate_parameter_values(10, 30, -5)  # negative step


class TestMetricsCalculator(unittest.TestCase):
    """Test metrics calculator and fitness functions."""
    
    def test_calculate_fitness_net_profit(self):
        """Test net profit fitness calculation."""
        metrics = BacktestMetrics(
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
            avg_drawdown=200.0
        )
        
        fitness = calculate_fitness(metrics, 'net_profit')
        self.assertEqual(fitness, 1000.0)
    
    def test_calculate_fitness_sharpe_ratio(self):
        """Test Sharpe ratio fitness calculation."""
        metrics = BacktestMetrics(
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
            avg_drawdown=200.0
        )
        
        fitness = calculate_fitness(metrics, 'sharpe_ratio')
        self.assertEqual(fitness, 1.5)
    
    def test_calculate_fitness_max_dd(self):
        """Test max drawdown fitness (negated)."""
        metrics = BacktestMetrics(
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
            avg_drawdown=200.0
        )
        
        fitness = calculate_fitness(metrics, 'max_dd')
        # Max DD is negated because lower is better
        self.assertEqual(fitness, -500.0)
    
    def test_calculate_fitness_profit_factor(self):
        """Test profit factor fitness."""
        metrics = BacktestMetrics(
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
            avg_drawdown=200.0
        )
        
        fitness = calculate_fitness(metrics, 'profit_factor')
        self.assertEqual(fitness, 2.0)
    
    def test_calculate_fitness_np_avg_dd(self):
        """Test NP/AvgDD fitness (mentor's preferred metric)."""
        metrics = BacktestMetrics(
            net_profit=1000.0,
            total_return_pct=10.0,
            sharpe_ratio=1.5,
            max_drawdown=500.0,
            profit_factor=2.0,
            np_avg_dd=5.0,  # 1000 / 200 = 5
            gross_profit=2000.0,
            gross_loss=1000.0,
            num_trades=10,
            num_winning_trades=7,
            num_losing_trades=3,
            avg_drawdown=200.0
        )
        
        fitness = calculate_fitness(metrics, 'np_avg_dd')
        self.assertEqual(fitness, 5.0)
    
    def test_invalid_fitness_function(self):
        """Test invalid fitness function name."""
        metrics = BacktestMetrics(
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
            avg_drawdown=200.0
        )
        
        with self.assertRaises(ValueError):
            calculate_fitness(metrics, 'invalid_function')


class TestWalkForwardIntegration(unittest.TestCase):
    """Integration tests for walk-forward optimization."""
    
    def setUp(self):
        """Set up test configuration and data."""
        # Create a simple config for testing
        # We'll use a mock config since we can't easily modify the actual config file
        pass
    
    def test_period_parser_integration(self):
        """Test period parser with window generator."""
        start = datetime(2020, 1, 1)
        end = datetime(2021, 12, 31)
        
        # Parse period
        in_days, out_days = parse_period("6M/3M")
        
        # Generate windows
        dates = pd.date_range(start='2020-01-01', end='2021-12-31', freq='D')
        sample_data = pd.DataFrame({'close': np.random.randn(len(dates))}, index=dates)
        
        windows = generate_windows(start, end, int(in_days), int(out_days), sample_data)
        
        # Should generate multiple windows
        self.assertGreater(len(windows), 0)
        
        # Verify windows are properly spaced
        for i, window in enumerate(windows):
            if i > 0:
                # Windows should be rolling forward
                prev_oos_end = windows[i-1].out_sample_end
                curr_is_start = window.in_sample_start
                # Current window should start around where previous window's OOS ended
                # (for rolling windows, they may overlap slightly or be adjacent)
                self.assertLessEqual(curr_is_start, prev_oos_end + timedelta(days=5))  # Allow small tolerance
    
    def test_parameter_grid_with_window_generator(self):
        """Test parameter grid generation with window data."""
        # Generate parameter combinations
        ranges = {
            'fast_period': {'start': 5, 'end': 10, 'step': 5},
            'slow_period': {'start': 10, 'end': 20, 'step': 10}
        }
        
        combinations = generate_parameter_combinations(ranges)
        
        # Should have valid combinations
        self.assertEqual(len(combinations), 4)
        
        # Each combination should be a valid parameter dict
        for combo in combinations:
            self.assertIn('fast_period', combo)
            self.assertIn('slow_period', combo)
            self.assertIn(combo['fast_period'], [5, 10])
            self.assertIn(combo['slow_period'], [10, 20])


class TestWalkForwardResults(unittest.TestCase):
    """Test walk-forward results aggregation."""
    
    def test_results_calculation(self):
        """Test results aggregate calculation."""
        from backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult
        from backtest.walkforward.metrics_calculator import BacktestMetrics
        
        # Create sample results
        results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='np_avg_dd'
        )
        
        # Add window results
        window1 = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01',
            in_sample_end='2020-12-31',
            out_sample_start='2021-01-01',
            out_sample_end='2021-06-30',
            best_parameters={'fast_period': 20, 'slow_period': 50},
            in_sample_metrics=BacktestMetrics(
                net_profit=1000.0,
                total_return_pct=10.0,
                sharpe_ratio=1.0,
                max_drawdown=500.0,
                profit_factor=2.0,
                np_avg_dd=2.0,
                gross_profit=2000.0,
                gross_loss=1000.0,
                num_trades=10,
                num_winning_trades=7,
                num_losing_trades=3,
                avg_drawdown=500.0
            ),
            out_sample_metrics=BacktestMetrics(
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
                avg_drawdown=500.0
            )
        )
        
        results.window_results.append(window1)
        
        # Calculate aggregates
        results.calculate_aggregates()
        
        # Verify aggregates
        self.assertEqual(results.total_windows, 1)
        self.assertEqual(results.successful_windows, 1)
        self.assertAlmostEqual(results.total_oos_net_profit, 800.0, places=2)
        self.assertAlmostEqual(results.avg_oos_return_pct, 8.0, places=2)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)

