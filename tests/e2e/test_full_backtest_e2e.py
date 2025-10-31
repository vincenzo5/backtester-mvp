"""
End-to-end tests for complete backtest workflow.

Tests with real cached data: load → prepare → run → verify results.
"""

import unittest
import pytest
import pandas as pd
from pathlib import Path

from backtester.config import ConfigManager
from backtester.backtest.engine import prepare_backtest_data, run_backtest
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.data.cache_manager import read_cache
from backtester.backtest.result import BacktestResult
from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics


@pytest.mark.e2e
@pytest.mark.requires_data
class TestFullBacktestE2E(unittest.TestCase):
    """End-to-end test for complete backtest workflow."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = ConfigManager()
    
    def test_backtest_with_real_data(self):
        """Test complete backtest with real cached data."""
        # Try to load real cached data
        try:
            df = read_cache('BTC/USD', '1h')
        except Exception:
            self.skipTest("No cached data available - skipping E2E test")
        
        if df.empty or len(df) < 500:
            self.skipTest("Insufficient cached data - need at least 500 candles")
        
        # Filter to recent data for faster test
        if len(df) > 1000:
            df = df.tail(1000)
        
        # Prepare data with indicators
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        
        # Verify indicators were added
        # Indicators may not always be added depending on data size
        self.assertGreaterEqual(len(enriched_df.columns), len(df.columns))
        
        # Check for actual configured parameters (or defaults)
        fast_period = strategy_params.get('fast_period', 20)
        slow_period = strategy_params.get('slow_period', 50)
        self.assertIn(f'SMA_{fast_period}', enriched_df.columns)
        self.assertIn(f'SMA_{slow_period}', enriched_df.columns)
        
        # Run backtest
        result = run_backtest(self.config, enriched_df, SMACrossStrategy, verbose=False)
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn('metrics', result)
        self.assertIn('initial_capital', result)
        self.assertIn('execution_time', result)
        
        # Verify metrics contain expected fields
        metrics = result['metrics']
        expected_fields = [
            'net_profit', 'total_return_pct', 'num_trades',
            'sharpe_ratio', 'max_drawdown', 'profit_factor'
        ]
        for field in expected_fields:
            self.assertIn(field, metrics, f"Missing metric field: {field}")
        
        # Verify metrics have reasonable types
        self.assertIsInstance(metrics['num_trades'], int)
        self.assertIsInstance(metrics['total_return_pct'], (int, float))
    
    def test_backtest_with_return_metrics(self):
        """Test backtest with return_metrics=True returns metrics object."""
        try:
            df = read_cache('BTC/USD', '1h')
        except Exception:
            self.skipTest("No cached data available - skipping E2E test")
        
        if df.empty or len(df) < 500:
            self.skipTest("Insufficient cached data")
        
        if len(df) > 1000:
            df = df.tail(1000)
        
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        
        # Run backtest with return_metrics=True
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config, enriched_df, SMACrossStrategy,
            verbose=False, return_metrics=True
        )
        
        # Verify metrics object
        self.assertIsInstance(metrics, BacktestMetrics)
        self.assertIsInstance(metrics.total_return_pct, (int, float))
        self.assertIsInstance(metrics.num_trades, int)
        self.assertGreaterEqual(metrics.num_trades, 0)
    
    def test_backtest_result_creation(self):
        """Test creating BacktestResult from backtest."""
        try:
            df = read_cache('BTC/USD', '1h')
        except Exception:
            self.skipTest("No cached data available")
        
        if df.empty or len(df) < 500:
            self.skipTest("Insufficient cached data")
        
        if len(df) > 1000:
            df = df.tail(1000)
        
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        
        # Run backtest with return_metrics
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config, enriched_df, SMACrossStrategy,
            verbose=False, return_metrics=True
        )
        
        # Create BacktestResult
        from datetime import datetime
        backtest_result = BacktestResult(
            symbol='BTC/USD',
            timeframe='1h',
            timestamp=datetime.now().isoformat(),
            metrics=metrics,
            initial_capital=result_dict['initial_capital'],
            execution_time=result_dict['execution_time'],
            start_date=result_dict.get('start_date'),
            end_date=result_dict.get('end_date')
        )
        
        # Verify BacktestResult
        self.assertIsInstance(backtest_result, BacktestResult)
        self.assertEqual(backtest_result.symbol, 'BTC/USD')
        self.assertIsInstance(backtest_result.metrics, BacktestMetrics)
        
        # Test serialization
        result_dict = backtest_result.to_dict()
        self.assertIn('metrics', result_dict)
        self.assertIsInstance(result_dict['metrics'], dict)

