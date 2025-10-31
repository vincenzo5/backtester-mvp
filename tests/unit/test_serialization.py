"""
Unit tests for serialization functionality.

Tests ConfigManager serialization for parallel execution and result serialization.
"""

import unittest
import pytest
from datetime import datetime

from backtester.config import ConfigManager
from backtester.backtest.result import BacktestResult, SkippedRun
from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics
from backtester.backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult


@pytest.mark.unit
class TestConfigManagerSerialization(unittest.TestCase):
    """Test ConfigManager serialization for parallel execution."""
    
    def setUp(self):
        """Set up test config."""
        self.config = ConfigManager()
    
    def test_to_dict_returns_dict(self):
        """Test that _to_dict() returns a dictionary."""
        config_dict = self.config._to_dict()
        self.assertIsInstance(config_dict, dict)
    
    def test_to_dict_contains_required_keys(self):
        """Test that _to_dict() contains all required keys."""
        config_dict = self.config._to_dict()
        required_keys = ['config', 'metadata', 'profile_name', 'config_dir', 'metadata_path']
        for key in required_keys:
            self.assertIn(key, config_dict)
    
    def test_from_dict_reconstructs_config(self):
        """Test that _from_dict() reconstructs ConfigManager correctly."""
        config_dict = self.config._to_dict()
        reconstructed = ConfigManager._from_dict(config_dict)
        
        self.assertIsInstance(reconstructed, ConfigManager)
        self.assertEqual(reconstructed.config, self.config.config)
        self.assertEqual(reconstructed.metadata, self.config.metadata)
    
    def test_serialization_round_trip(self):
        """Test that serialization and deserialization are reversible."""
        original = ConfigManager()
        config_dict = original._to_dict()
        reconstructed = ConfigManager._from_dict(config_dict)
        
        # Verify accessor methods work after reconstruction
        self.assertEqual(original.get_strategy_name(), reconstructed.get_strategy_name())
        self.assertEqual(original.get_walkforward_start_date(), reconstructed.get_walkforward_start_date())
        self.assertEqual(original.get_walkforward_end_date(), reconstructed.get_walkforward_end_date())


@pytest.mark.unit
class TestBacktestResultSerialization(unittest.TestCase):
    """Test BacktestResult serialization."""
    
    def setUp(self):
        """Set up test metrics."""
        self.metrics = BacktestMetrics(
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
            max_consecutive_wins=5,
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
            percent_time_in_market=50.0,
            walkforward_efficiency=0.0
        )
        
        self.result = BacktestResult(
            symbol='BTC/USD',
            timeframe='1h',
            timestamp=datetime.now().isoformat(),
            metrics=self.metrics,
            initial_capital=10000.0,
            execution_time=0.5,
            start_date='2020-01-01',
            end_date='2021-12-31'
        )
    
    def test_to_dict_returns_dict(self):
        """Test that to_dict() returns a dictionary."""
        result_dict = self.result.to_dict()
        self.assertIsInstance(result_dict, dict)
    
    def test_to_dict_contains_metrics(self):
        """Test that to_dict() contains metrics."""
        result_dict = self.result.to_dict()
        self.assertIn('metrics', result_dict)
        self.assertIsInstance(result_dict['metrics'], dict)
    
    def test_metrics_reconstruction(self):
        """Test that metrics can be reconstructed from dict."""
        result_dict = self.result.to_dict()
        metrics_dict = result_dict['metrics']
        
        # Reconstruct BacktestMetrics from dict
        reconstructed = BacktestMetrics(**metrics_dict)
        
        self.assertEqual(reconstructed.net_profit, self.metrics.net_profit)
        self.assertEqual(reconstructed.total_return_pct, self.metrics.total_return_pct)
        self.assertEqual(reconstructed.num_trades, self.metrics.num_trades)


@pytest.mark.unit
class TestSkippedRunSerialization(unittest.TestCase):
    """Test SkippedRun serialization."""
    
    def test_to_dict_returns_dict(self):
        """Test that to_dict() returns a dictionary."""
        skip = SkippedRun(
            symbol='BTC/USD',
            timeframe='1h',
            reason='Insufficient data'
        )
        skip_dict = skip.to_dict()
        self.assertIsInstance(skip_dict, dict)
    
    def test_to_dict_contains_required_fields(self):
        """Test that to_dict() contains all required fields."""
        skip = SkippedRun(
            symbol='BTC/USD',
            timeframe='1h',
            reason='Insufficient data'
        )
        skip_dict = skip.to_dict()
        
        required_fields = ['symbol', 'timeframe', 'reason', 'timestamp']
        for field in required_fields:
            self.assertIn(field, skip_dict)


@pytest.mark.unit
class TestWalkForwardResultsSerialization(unittest.TestCase):
    """Test WalkForwardResults serialization."""
    
    def setUp(self):
        """Set up test results."""
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
            avg_drawdown=200.0,
            win_rate_pct=70.0,
            percent_trades_profitable=70.0,
            percent_trades_unprofitable=30.0,
            avg_trade=100.0,
            avg_profitable_trade=285.71,
            avg_unprofitable_trade=-333.33,
            largest_winning_trade=500.0,
            largest_losing_trade=-200.0,
            max_consecutive_wins=5,
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
            percent_time_in_market=50.0,
            walkforward_efficiency=0.0
        )
        
        window_result = WalkForwardWindowResult(
            window_index=0,
            in_sample_start='2020-01-01T00:00:00',
            in_sample_end='2020-06-30T23:59:59',
            out_sample_start='2020-07-01T00:00:00',
            out_sample_end='2020-12-31T23:59:59',
            best_parameters={'fast_period': 10, 'slow_period': 20},
            in_sample_metrics=metrics,
            out_sample_metrics=metrics
        )
        
        self.results = WalkForwardResults(
            symbol='BTC/USD',
            timeframe='1h',
            period_str='1Y/6M',
            fitness_function='np_avg_dd',
            filter_config={},
            window_results=[window_result]
        )
    
    def test_to_dict_returns_dict(self):
        """Test that to_dict() returns a dictionary."""
        results_dict = self.results.to_dict()
        self.assertIsInstance(results_dict, dict)
    
    def test_to_dict_contains_window_results(self):
        """Test that to_dict() contains window results."""
        results_dict = self.results.to_dict()
        self.assertIn('window_results', results_dict)
        self.assertIsInstance(results_dict['window_results'], list)
        self.assertGreater(len(results_dict['window_results']), 0)

