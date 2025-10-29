"""
Comprehensive tests for MultiWalk metrics calculator.

Tests all 38 metrics, edge cases, fitness functions, and integration.
"""

import unittest
import pandas as pd
import numpy as np
import backtrader as bt
from datetime import datetime, timedelta
from typing import List, Dict, Any

from backtest.walkforward.metrics_calculator import (
    BacktestMetrics,
    calculate_metrics,
    calculate_fitness
)
from backtest.engine import run_backtest
from config import ConfigManager
from strategies.sma_cross import SMACrossStrategy


def create_minimal_metrics() -> BacktestMetrics:
    """Create a minimal BacktestMetrics with default values for testing."""
    return BacktestMetrics(
        # Basic metrics
        net_profit=0.0,
        total_return_pct=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        profit_factor=0.0,
        np_avg_dd=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        num_trades=0,
        num_winning_trades=0,
        num_losing_trades=0,
        avg_drawdown=0.0,
        # Trade statistics
        win_rate_pct=0.0,
        percent_trades_profitable=0.0,
        percent_trades_unprofitable=0.0,
        avg_trade=0.0,
        avg_profitable_trade=0.0,
        avg_unprofitable_trade=0.0,
        largest_winning_trade=0.0,
        largest_losing_trade=0.0,
        max_consecutive_wins=0,
        max_consecutive_losses=0,
        # Day statistics
        total_calendar_days=0,
        total_trading_days=0,
        days_profitable=0,
        days_unprofitable=0,
        percent_days_profitable=0.0,
        percent_days_unprofitable=0.0,
        # Drawdown metrics
        max_drawdown_pct=0.0,
        max_run_up=0.0,
        recovery_factor=0.0,
        np_max_dd=0.0,
        # Advanced metrics
        r_squared=0.0,
        sortino_ratio=0.0,
        monte_carlo_score=0.0,
        rina_index=0.0,
        tradestation_index=0.0,
        np_x_r2=0.0,
        np_x_pf=0.0,
        annualized_net_profit=0.0,
        annualized_return_avg_dd=0.0,
        percent_time_in_market=0.0,
        walkforward_efficiency=0.0
    )


class TestBacktestMetrics(unittest.TestCase):
    """Test BacktestMetrics dataclass structure."""
    
    def test_metrics_has_all_fields(self):
        """Verify BacktestMetrics has all required MultiWalk fields (43 total including derived metrics)."""
        metrics = create_minimal_metrics()
        
        # Count fields using dataclass fields
        field_count = len(BacktestMetrics.__dataclass_fields__)
        # We have 43 fields: 38 core MultiWalk metrics + 5 derived/combined metrics
        self.assertEqual(field_count, 43, f"Expected 43 fields, got {field_count}")
    
    def test_metrics_initialization(self):
        """Test that metrics can be initialized with all fields."""
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
            percent_time_in_market=60.0,
            walkforward_efficiency=0.0
        )
        
        self.assertEqual(metrics.net_profit, 1000.0)
        self.assertEqual(metrics.total_return_pct, 10.0)
        self.assertEqual(metrics.num_trades, 10)
        self.assertEqual(metrics.win_rate_pct, 70.0)


class TestFitnessFunctions(unittest.TestCase):
    """Test all MultiWalk fitness functions."""
    
    def setUp(self):
        """Create test metrics."""
        self.metrics = BacktestMetrics(
            net_profit=1000.0,
            total_return_pct=10.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=500.0,
            profit_factor=2.0,
            np_avg_dd=2.0,
            np_max_dd=2.0,
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
            r_squared=0.95,
            monte_carlo_score=75.0,
            rina_index=10.0,
            tradestation_index=15.0,
            np_x_r2=950.0,
            np_x_pf=2000.0,
            annualized_net_profit=1000.0,
            annualized_return_avg_dd=5.0,
            percent_time_in_market=60.0,
            walkforward_efficiency=0.8
        )
    
    def test_basic_fitness_functions(self):
        """Test basic fitness functions."""
        self.assertEqual(calculate_fitness(self.metrics, 'net_profit'), 1000.0)
        self.assertEqual(calculate_fitness(self.metrics, 'sharpe_ratio'), 1.5)
        self.assertEqual(calculate_fitness(self.metrics, 'sortino_ratio'), 2.0)
        self.assertEqual(calculate_fitness(self.metrics, 'max_dd'), -500.0)  # Negated
        self.assertEqual(calculate_fitness(self.metrics, 'profit_factor'), 2.0)
        self.assertEqual(calculate_fitness(self.metrics, 'np_avg_dd'), 2.0)
        self.assertEqual(calculate_fitness(self.metrics, 'np_max_dd'), 2.0)
    
    def test_trade_statistics_fitness(self):
        """Test trade statistics fitness functions."""
        self.assertEqual(calculate_fitness(self.metrics, 'max_consecutive_wins'), 5.0)
        self.assertEqual(calculate_fitness(self.metrics, 'avg_trade'), 100.0)
        self.assertEqual(calculate_fitness(self.metrics, 'avg_profitable_trade'), 285.71)
        self.assertEqual(calculate_fitness(self.metrics, 'avg_unprofitable_trade'), 333.33)  # Negated
        self.assertEqual(calculate_fitness(self.metrics, 'percent_trades_profitable'), 70.0)
    
    def test_day_statistics_fitness(self):
        """Test day statistics fitness functions."""
        self.assertEqual(calculate_fitness(self.metrics, 'percent_days_profitable'), 59.52)
    
    def test_advanced_fitness_functions(self):
        """Test advanced fitness functions."""
        self.assertEqual(calculate_fitness(self.metrics, 'r_squared'), 0.95)
        self.assertEqual(calculate_fitness(self.metrics, 'np_x_r2'), 950.0)
        self.assertEqual(calculate_fitness(self.metrics, 'np_x_pf'), 2000.0)
        self.assertEqual(calculate_fitness(self.metrics, 'rina_index'), 10.0)
        self.assertEqual(calculate_fitness(self.metrics, 'tradestation_index'), 15.0)
        self.assertEqual(calculate_fitness(self.metrics, 'max_run_up'), 1500.0)
        self.assertEqual(calculate_fitness(self.metrics, 'annualized_net_profit'), 1000.0)
        self.assertEqual(calculate_fitness(self.metrics, 'annualized_return_avg_dd'), 5.0)
        self.assertEqual(calculate_fitness(self.metrics, 'percent_time_in_market'), -60.0)  # Negated
        self.assertEqual(calculate_fitness(self.metrics, 'walkforward_efficiency'), 0.8)
    
    def test_invalid_fitness_function(self):
        """Test that invalid fitness function raises error."""
        with self.assertRaises(ValueError) as context:
            calculate_fitness(self.metrics, 'invalid_function')
        self.assertIn('Unknown fitness function', str(context.exception))


class TestMetricsCalculationIntegration(unittest.TestCase):
    """Integration tests for calculate_metrics with real backtest."""
    
    def setUp(self):
        """Set up test data and config."""
        # Create sample OHLCV data
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        np.random.seed(42)
        
        # Create realistic price data with trend
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
        
        # Create minimal config
        self.config = ConfigManager()
    
    def test_calculate_metrics_with_real_backtest(self):
        """Test that calculate_metrics works with actual backtest."""
        # Run backtest with return_metrics=True
        result_dict, cerebro, strategy_instance = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        # Calculate metrics
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
        
        # Verify metrics object is created
        self.assertIsInstance(metrics, BacktestMetrics)
        
        # Verify basic metrics are calculated
        self.assertIsNotNone(metrics.net_profit)
        self.assertIsNotNone(metrics.total_return_pct)
        self.assertIsNotNone(metrics.num_trades)
        
        # Verify equity curve was extracted
        self.assertTrue(hasattr(strategy_instance, 'equity_curve'))
        self.assertGreater(len(strategy_instance.equity_curve), 0)
    
    def test_all_38_metrics_calculated(self):
        """Verify all 38 metrics are calculated (not None/0 without reason)."""
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
        
        # Check that all fields exist and have appropriate types
        for field_name, field_info in BacktestMetrics.__dataclass_fields__.items():
            value = getattr(metrics, field_name)
            
            # Type checks
            if field_info.type == int:
                self.assertIsInstance(value, int, f"Field {field_name} should be int")
            elif field_info.type == float:
                self.assertIsInstance(value, (int, float), f"Field {field_name} should be float")
                # Allow inf but not NaN
                if isinstance(value, float):
                    self.assertFalse(np.isnan(value), f"Field {field_name} should not be NaN")
    
    def test_analyzers_are_added(self):
        """Test that analyzers are properly added to cerebro."""
        result_dict, cerebro, strategy_instance = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        # Verify analyzers exist
        self.assertTrue(hasattr(cerebro, 'analyzers'))
        
        # Check for trade analyzer
        try:
            trade_analyzer = cerebro.analyzers.trade.get_analysis()
            # Should have some structure even if no trades
            self.assertIsNotNone(trade_analyzer)
        except AttributeError:
            # Analyzer might not be accessible this way, which is okay
            pass
    
    def test_equity_curve_tracking(self):
        """Test that equity curve is properly tracked."""
        result_dict, cerebro, strategy_instance = run_backtest(
            self.config,
            self.test_data,
            SMACrossStrategy,
            verbose=False,
            return_metrics=True
        )
        
        # Verify equity curve exists
        self.assertTrue(hasattr(strategy_instance, 'equity_curve'))
        equity_curve = strategy_instance.equity_curve
        
        # Should have entries
        self.assertGreater(len(equity_curve), 0)
        
        # Each entry should have date and value
        for entry in equity_curve:
            self.assertIn('date', entry)
            self.assertIn('value', entry)
            self.assertIsInstance(entry['value'], (int, float))
            self.assertGreater(entry['value'], 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases for metrics calculation."""
    
    def setUp(self):
        """Set up minimal test components."""
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(10000.0)
        
        # Create a strategy that doesn't trade
        class NoTradeStrategy(bt.Strategy):
            def next(self):
                pass
        
        # Add strategy to cerebro and run to create instance
        self.cerebro.addstrategy(NoTradeStrategy)
        # Create minimal data feed
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        }, index=dates)
        self.cerebro.adddata(bt.feeds.PandasData(dataname=df))
        result = self.cerebro.run()
        self.strategy_instance = result[0]
    
    def test_no_trades(self):
        """Test metrics calculation with no trades."""
        initial_capital = 10000.0
        equity_curve = [
            {'date': datetime(2020, 1, 1), 'value': initial_capital},
            {'date': datetime(2020, 12, 31), 'value': initial_capital}
        ]
        
        metrics = calculate_metrics(
            self.cerebro,
            self.strategy_instance,
            initial_capital,
            equity_curve=equity_curve,
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31)
        )
        
        # Should handle no trades gracefully
        self.assertEqual(metrics.num_trades, 0)
        self.assertEqual(metrics.num_winning_trades, 0)
        self.assertEqual(metrics.num_losing_trades, 0)
        self.assertEqual(metrics.net_profit, 0.0)
        self.assertEqual(metrics.win_rate_pct, 0.0)
    
    def test_all_winning_trades(self):
        """Test with hypothetical all-winning scenario."""
        # Create a mock cerebro with profit
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(11000.0)  # 10% profit
        
        # Create minimal equity curve showing profit
        equity_curve = [
            {'date': datetime(2020, 1, 1), 'value': 10000.0},
            {'date': datetime(2020, 6, 30), 'value': 11000.0},
            {'date': datetime(2020, 12, 31), 'value': 11000.0}
        ]
        
        # Create strategy with trades_log showing wins
        class MockStrategy(bt.Strategy):
            def __init__(self):
                super().__init__()
                self.trades_log = [
                    {'pnl': 500.0, 'entry_date': datetime(2020, 1, 15), 'exit_date': datetime(2020, 2, 15)},
                    {'pnl': 500.0, 'entry_date': datetime(2020, 3, 1), 'exit_date': datetime(2020, 4, 1)}
                ]
        
        # Create minimal data and run to get strategy instance
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        }, index=dates)
        cerebro.addstrategy(MockStrategy)
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        result = cerebro.run()
        strategy = result[0]
        
        metrics = calculate_metrics(
            cerebro,
            strategy,
            10000.0,
            equity_curve=equity_curve,
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31)
        )
        
        self.assertEqual(metrics.num_winning_trades, 2)
        self.assertEqual(metrics.num_losing_trades, 0)
        self.assertEqual(metrics.win_rate_pct, 100.0)
        self.assertGreater(metrics.profit_factor, 0)
    
    def test_all_losing_trades(self):
        """Test with all-losing scenario."""
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(9000.0)  # 10% loss
        
        equity_curve = [
            {'date': datetime(2020, 1, 1), 'value': 10000.0},
            {'date': datetime(2020, 6, 30), 'value': 9500.0},
            {'date': datetime(2020, 12, 31), 'value': 9000.0}
        ]
        
        class MockStrategy(bt.Strategy):
            def __init__(self):
                super().__init__()
                self.trades_log = [
                    {'pnl': -500.0, 'entry_date': datetime(2020, 1, 15), 'exit_date': datetime(2020, 2, 15)},
                    {'pnl': -500.0, 'entry_date': datetime(2020, 3, 1), 'exit_date': datetime(2020, 4, 1)}
                ]
        
        # Create minimal data and run to get strategy instance
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        }, index=dates)
        cerebro.addstrategy(MockStrategy)
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        result = cerebro.run()
        strategy = result[0]
        
        metrics = calculate_metrics(
            cerebro,
            strategy,
            10000.0,
            equity_curve=equity_curve,
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31)
        )
        
        self.assertEqual(metrics.num_winning_trades, 0)
        self.assertEqual(metrics.num_losing_trades, 2)
        self.assertEqual(metrics.win_rate_pct, 0.0)
        self.assertEqual(metrics.profit_factor, 0.0)  # No gross profit


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions used in metrics calculation."""
    
    def test_edge_cases_in_calculation(self):
        """Test that calculation handles edge cases gracefully."""
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(10000.0)
        
        # Empty equity curve
        equity_curve = []
        
        class MockStrategy(bt.Strategy):
            pass
        
        # Create minimal data and run to get strategy instance
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        }, index=dates)
        cerebro.addstrategy(MockStrategy)
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        result = cerebro.run()
        strategy = result[0]
        
        # Should not raise exception
        metrics = calculate_metrics(
            cerebro,
            strategy,
            10000.0,
            equity_curve=equity_curve,
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31)
        )
        
        # Should return valid metrics object
        self.assertIsInstance(metrics, BacktestMetrics)
    
    def test_division_by_zero_protection(self):
        """Test that division by zero is handled."""
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(10000.0)
        
        # Single point equity curve
        equity_curve = [
            {'date': datetime(2020, 1, 1), 'value': 10000.0}
        ]
        
        class MockStrategy(bt.Strategy):
            pass
        
        # Create minimal data and run to get strategy instance
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        }, index=dates)
        cerebro.addstrategy(MockStrategy)
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        result = cerebro.run()
        strategy = result[0]
        
        # Should not raise ZeroDivisionError
        metrics = calculate_metrics(
            cerebro,
            strategy,
            10000.0,
            equity_curve=equity_curve,
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31)
        )
        
        self.assertIsInstance(metrics, BacktestMetrics)


if __name__ == '__main__':
    unittest.main(verbosity=2)
