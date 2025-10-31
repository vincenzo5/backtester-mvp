"""
System tests for complete backtest workflow.

Tests complete workflow: config → data → run → results.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from backtester.config import ConfigManager
from backtester.data.cache_manager import write_cache, read_cache
from backtester.backtest.engine import prepare_backtest_data, run_backtest
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.backtest.result import BacktestResult


@pytest.mark.system
class TestBacktestWorkflow(unittest.TestCase):
    """Test complete backtest workflow end-to-end."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch cache directory
        from backtester.data import cache_manager as cm_module
        self.original_cache_dir = cm_module.CACHE_DIR
        cm_module.CACHE_DIR = Path(self.temp_dir)
        cm_module.MANIFEST_FILE = Path(self.temp_dir) / '.cache_manifest.json'
        
        # Create test data
        dates = pd.date_range(start='2020-01-01', periods=1000, freq='1h')
        np.random.seed(42)
        
        base_price = 50000
        trend = np.linspace(0, base_price * 0.2, 1000)
        noise = np.random.randn(1000).cumsum() * 100
        prices = base_price + trend + noise
        
        self.test_df = pd.DataFrame({
            'open': np.roll(prices, 1),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 1000)
        }, index=dates)
        self.test_df.iloc[0]['open'] = base_price
        
        # Write to cache
        write_cache('BTC/USD', '1h', self.test_df)
        
        self.config = ConfigManager()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
        
        from backtester.data import cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache_dir
        cm_module.MANIFEST_FILE = self.original_cache_dir / '.cache_manifest.json'
    
    def test_complete_backtest_workflow(self):
        """Test complete workflow: config → load data → prepare → run → results."""
        # Step 1: Load config
        config = ConfigManager()
        strategy_name = config.get_strategy_name()
        self.assertEqual(strategy_name, 'sma_cross')
        
        # Step 2: Load data from cache
        df = read_cache('BTC/USD', '1h')
        self.assertFalse(df.empty)
        
        # Step 3: Prepare data with indicators
        strategy_params = config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        # Indicators may or may not be added depending on data size and params
        # For smoke test, we just verify the function completes without error
        self.assertGreaterEqual(len(enriched_df.columns), len(df.columns))
        
        # Step 4: Run backtest
        result = run_backtest(config, enriched_df, SMACrossStrategy, verbose=False)
        self.assertIsInstance(result, dict)
        self.assertIn('metrics', result)
        
        # Step 5: Verify results
        metrics = result['metrics']
        self.assertIn('total_return_pct', metrics)
        self.assertIn('num_trades', metrics)
        self.assertIsInstance(metrics['num_trades'], int)
    
    def test_workflow_with_return_metrics(self):
        """Test workflow with return_metrics=True."""
        df = read_cache('BTC/USD', '1h')
        strategy_params = self.config.get_strategy_config().parameters
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
        
        # Run with return_metrics
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            self.config, enriched_df, SMACrossStrategy,
            verbose=False, return_metrics=True
        )
        
        # Verify all components
        self.assertIsInstance(result_dict, dict)
        self.assertIsNotNone(cerebro)
        self.assertIsNotNone(strategy_instance)
        self.assertIsNotNone(metrics)
        
        # Create BacktestResult
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
        
        # Verify result can be serialized
        result_dict_serialized = backtest_result.to_dict()
        self.assertIn('metrics', result_dict_serialized)

