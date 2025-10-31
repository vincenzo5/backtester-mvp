"""
Integration tests for metrics calculation in full backtest context.

Tests that metrics are calculated correctly in complete backtest scenarios.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.backtest.engine import prepare_backtest_data, run_backtest
from backtester.config import ConfigManager
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics
from backtester.backtest.result import BacktestResult


@pytest.mark.integration
class TestMetricsIntegration(unittest.TestCase):
    """Test metrics calculation in full backtest context."""
    
    def setUp(self):
        """Set up test data."""
        self.config = ConfigManager()
        
        # Create sample OHLCV data
        dates = pd.date_range(start='2020-01-01', periods=500, freq='1h')
        np.random.seed(42)
        
        base_price = 50000
        prices = base_price + np.random.randn(500).cumsum() * 100
        
        self.df = pd.DataFrame({
            'open': np.roll(prices, 1),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 500)
        }, index=dates)
        self.df.iloc[0]['open'] = base_price
        
        # Prepare data
        strategy_params = self.config.get_strategy_config().parameters
        self.enriched_df = prepare_backtest_data(self.df, SMACrossStrategy, strategy_params)
    
    def test_metrics_in_result_dict(self):
        """Test that metrics are included in result dict."""
        result = run_backtest(self.config, self.enriched_df, SMACrossStrategy, verbose=False)
        
        self.assertIn('metrics', result)
        metrics = result['metrics']
        
        # Verify all expected metric fields
        expected_fields = [
            'net_profit', 'total_return_pct', 'num_trades',
            'sharpe_ratio', 'max_drawdown', 'profit_factor'
        ]
        for field in expected_fields:
            self.assertIn(field, metrics)
    
    def test_metrics_with_return_metrics_true(self):
        """Test metrics object when return_metrics=True."""
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config, self.enriched_df, SMACrossStrategy,
            verbose=False, return_metrics=True
        )
        
        # Verify metrics object
        self.assertIsInstance(metrics, BacktestMetrics)
        self.assertIsInstance(metrics.total_return_pct, (int, float))
        self.assertIsInstance(metrics.num_trades, int)
        self.assertGreaterEqual(metrics.num_trades, 0)
    
    def test_metrics_serialization_roundtrip(self):
        """Test that metrics can be serialized and reconstructed."""
        result = run_backtest(self.config, self.enriched_df, SMACrossStrategy, verbose=False)
        
        # Extract metrics dict
        metrics_dict = result['metrics']
        
        # Reconstruct BacktestMetrics
        reconstructed = BacktestMetrics(**metrics_dict)
        
        # Verify reconstruction
        self.assertIsInstance(reconstructed, BacktestMetrics)
        self.assertEqual(reconstructed.net_profit, metrics_dict['net_profit'])
        self.assertEqual(reconstructed.total_return_pct, metrics_dict['total_return_pct'])
    
    def test_backtest_result_creation(self):
        """Test creating BacktestResult with metrics."""
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config, self.enriched_df, SMACrossStrategy,
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
        
        # Verify result
        self.assertIsInstance(backtest_result, BacktestResult)
        self.assertIsInstance(backtest_result.metrics, BacktestMetrics)
        
        # Test serialization
        result_dict_serialized = backtest_result.to_dict()
        self.assertIn('metrics', result_dict_serialized)

