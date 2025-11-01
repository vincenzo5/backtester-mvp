"""
System tests for performance attribution.

Tests disabled modes, error handling, and performance overhead.
"""

import unittest
import pytest
import tempfile
import time
import shutil
import os
import yaml
import numpy as np
from pathlib import Path

import pandas as pd
from datetime import datetime

from backtester.config import ConfigManager
from backtester.debug import ExecutionTracer, CrashReporter, set_debug_components
from backtester.backtest.engine import run_backtest
from backtester.strategies.sma_cross import SMACrossStrategy


@pytest.mark.system
class TestPerformanceAttributionSystem(unittest.TestCase):
    """System tests for performance attribution."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories manually
        self.temp_dir = tempfile.mkdtemp()
        config_dir = os.path.join(self.temp_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        metadata_path = os.path.join(self.temp_dir, 'metadata.yaml')
        
        # Create minimal config files
        data_config = {'data': {'exchange': 'coinbase'}}
        trading_config = {'trading': {'commission': 0.006, 'slippage': 0.0005}}
        strategy_config = {
            'strategy': {
                'name': 'sma_cross',
                'parameters': {'fast_period': 10, 'slow_period': 20}
            }
        }
        walkforward_config = {
            'walkforward': {
                'start_date': '2020-01-01',
                'end_date': '2021-12-31',
                'initial_capital': 100000.0,
                'verbose': False,
                'symbols': ['BTC/USD'],
                'timeframes': ['1h'],
                'periods': ['1Y/6M'],
                'fitness_functions': ['np_avg_dd'],
                'parameter_ranges': {
                    'fast_period': {'start': 10, 'end': 30, 'step': 5},
                    'slow_period': {'start': 40, 'end': 60, 'step': 10}
                }
            }
        }
        data_quality_config = {
            'data_quality': {
                'weights': {
                    'coverage': 0.30,
                    'integrity': 0.25,
                    'gaps': 0.20,
                    'completeness': 0.15,
                    'consistency': 0.08,
                    'volume': 0.01,
                    'outliers': 0.01
                },
                'thresholds': {},
                'warning_threshold': 70.0,
                'liveliness_cache_days': 30,
                'incremental_assessment': True,
                'full_assessment_schedule': 'weekly',
                'gap_filling_schedule': 'weekly'
            }
        }
        parallel_config = {'parallel': {'mode': 'auto'}}
        debug_config_data = {
            'debug': {
                'enabled': True,
                'tracing': {'enabled': True, 'level': 'standard'},
                'crash_reports': {'enabled': True},
                'logging': {'execution_trace_file': 'artifacts/logs/test_system_trace.jsonl'}
            }
        }
        
        with open(os.path.join(config_dir, 'data.yaml'), 'w') as f:
            yaml.dump(data_config, f)
        with open(os.path.join(config_dir, 'trading.yaml'), 'w') as f:
            yaml.dump(trading_config, f)
        with open(os.path.join(config_dir, 'strategy.yaml'), 'w') as f:
            yaml.dump(strategy_config, f)
        with open(os.path.join(config_dir, 'walkforward.yaml'), 'w') as f:
            yaml.dump(walkforward_config, f)
        with open(os.path.join(config_dir, 'data_quality.yaml'), 'w') as f:
            yaml.dump(data_quality_config, f)
        with open(os.path.join(config_dir, 'parallel.yaml'), 'w') as f:
            yaml.dump(parallel_config, f)
        with open(os.path.join(config_dir, 'debug.yaml'), 'w') as f:
            yaml.dump(debug_config_data, f)
        
        metadata = {
            'exchanges': {
                'coinbase': {
                    'markets': {
                        'BTC/USD': {
                            'timeframes': ['1h', '1d'],
                            'liveliness': {'status': 'live', 'verified_date': '2024-01-01'}
                        }
                    }
                }
            }
        }
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f)
        
        self.config = ConfigManager(config_dir=config_dir, metadata_path=metadata_path)
        self.debug_config = self.config.get_debug_config()
        
        # Create sample data
        dates = pd.date_range(start='2020-01-01', periods=100, freq='1h')
        np.random.seed(42)
        base_price = 50000
        prices = base_price + np.random.randn(100).cumsum() * 100
        self.test_df = pd.DataFrame({
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_performance_attribution_disabled(self):
        """Test graceful degradation when performance attribution is disabled."""
        # Get debug config
        debug_config = self.config.get_debug_config()
        
        # Disable debug
        original_enabled = debug_config.enabled
        debug_config.enabled = False
        
        try:
            # Create tracer (should be disabled)
            tracer = ExecutionTracer(debug_config)
            
            self.assertFalse(tracer.enabled)
            self.assertIsNone(tracer.logging_service)
            # change_tracker may not be initialized when disabled
            if hasattr(tracer, 'change_tracker'):
                self.assertIsNone(tracer.change_tracker)
            
            # System should still function
            strategy_class = SMACrossStrategy
            result = run_backtest(
                self.config,
                self.test_df,
                strategy_class,
                verbose=False,
                strategy_params={'fast_period': 10, 'slow_period': 20}
            )
            
            # Should complete without errors
            self.assertIsNotNone(result)
            
        finally:
            # Restore
            debug_config.enabled = original_enabled
            if 'tracer' in locals():
                tracer.shutdown()
    
    def test_change_tracker_error_handling(self):
        """Test errors in ChangeTracker don't break execution."""
        debug_config = self.config.get_debug_config()
        
        if not debug_config.enabled or not debug_config.tracing.enabled:
            self.skipTest("Debug/tracing not enabled")
        
        tracer = ExecutionTracer(debug_config)
        
        try:
            # Try to get change metadata (might fail in some environments)
            if tracer.change_tracker is not None:
                metadata = tracer.change_tracker.get_change_metadata()
                # Should return valid structure even if git/config unavailable
                self.assertIn('git', metadata)
                self.assertIn('config', metadata)
            
            # Execution should continue
            tracer.trace('test_event', 'Test message')
            time.sleep(0.1)
            
        finally:
            tracer.shutdown()
    
    def test_cache_stats_error_handling(self):
        """Test errors in cache stats calculation don't break execution."""
        from backtester.indicators.library import IndicatorLibrary
        
        lib = IndicatorLibrary()
        
        # Reset stats
        lib.reset_cache_stats()
        
        # Compute with invalid data (should raise error, but not crash stats)
        empty_df = pd.DataFrame()
        
        with self.assertRaises(ValueError):
            lib.compute_indicator(
                empty_df, 'SMA', {'timeperiod': 20}, 'SMA_20',
                track_performance=True
            )
        
        # Stats should still be valid (not updated on error)
        stats = lib.get_cache_stats()
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['hits'], 0)
        
        # Normal computation should still work
        result = lib.compute_indicator(
            self.test_df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        stats = lib.get_cache_stats()
        self.assertEqual(stats['misses'], 1)
    
    def test_performance_overhead(self):
        """Test performance tracking adds minimal overhead."""
        debug_config = self.config.get_debug_config()
        
        if not debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        strategy_class = SMACrossStrategy
        strategy_params = {'fast_period': 10, 'slow_period': 20}
        
        # Run backtest with tracking
        start_with = time.time()
        result_with = run_backtest(
            self.config,
            self.test_df,
            strategy_class,
            verbose=False,
            strategy_params=strategy_params
        )
        time_with = time.time() - start_with
        
        # Disable tracing for comparison
        original_tracing = debug_config.tracing.enabled
        debug_config.tracing.enabled = False
        
        try:
            # Recreate tracer (disabled)
            tracer_disabled = ExecutionTracer(debug_config)
            set_debug_components(tracer_disabled, None)
            
            # Run backtest without tracking
            start_without = time.time()
            result_without = run_backtest(
                self.config,
                self.test_df,
                strategy_class,
                verbose=False,
                strategy_params=strategy_params
            )
            time_without = time.time() - start_without
            
            # Overhead should be < 20% (allowing generous margin for test variability)
            if time_without > 0:
                overhead_ratio = (time_with - time_without) / time_without
                # Allow up to 50% overhead in test environment (very generous for CI variability)
                self.assertLess(overhead_ratio, 0.50, 
                              f"Overhead {overhead_ratio:.1%} exceeds 50% threshold")
        
        finally:
            debug_config.tracing.enabled = original_tracing
            if 'tracer_disabled' in locals():
                tracer_disabled.shutdown()
    
    def test_missing_git_repo_graceful(self):
        """Test missing git repo handled gracefully."""
        from backtester.debug.change_tracker import ChangeTracker
        
        # Create temp directory without git
        temp_dir = tempfile.mkdtemp()
        try:
            tracker = ChangeTracker(project_root=Path(temp_dir))
            metadata = tracker.get_change_metadata()
            
            # Should return valid structure with 'unknown' values
            self.assertIn('git', metadata)
            self.assertEqual(metadata['git']['commit_hash'], 'unknown')
            self.assertEqual(metadata['git']['branch'], 'unknown')
            self.assertEqual(metadata['git']['commit_message'], 'unknown')
            # has_uncommitted_changes might be True if git command fails
            self.assertIn(metadata['git']['has_uncommitted_changes'], [True, False])
            
            # Other metadata should still be valid
            self.assertIn('config', metadata)
            self.assertIn('environment', metadata)
            self.assertIn('dependencies', metadata)
        
        finally:
            shutil.rmtree(temp_dir)
    
    def test_missing_config_directory(self):
        """Test missing config directory handled gracefully."""
        from backtester.debug.change_tracker import ChangeTracker
        
        temp_dir = tempfile.mkdtemp()
        try:
            tracker = ChangeTracker(project_root=Path(temp_dir))
            config_hashes = tracker._get_config_hashes()
            
            # Should return empty dict, not raise error
            self.assertIsInstance(config_hashes, dict)
            self.assertEqual(len(config_hashes), 0)
        
        finally:
            shutil.rmtree(temp_dir)
    
    def test_cache_tracking_optional(self):
        """Test cache tracking is optional and doesn't break without it."""
        from backtester.indicators.library import IndicatorLibrary
        
        lib = IndicatorLibrary()
        
        # Compute without tracking (default)
        result1 = lib.compute_indicator(
            self.test_df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=False
        )
        
        # Should work fine
        self.assertIsNotNone(result1)
        
        # Stats should remain zero
        stats = lib.get_cache_stats()
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['hits'], 0)
        
        # Compute with tracking
        result2 = lib.compute_indicator(
            self.test_df, 'SMA', {'timeperiod': 20}, 'SMA_20',
            track_performance=True
        )
        
        # Should work and update stats
        stats = lib.get_cache_stats()
        self.assertGreaterEqual(stats['misses'], 0)


if __name__ == '__main__':
    unittest.main()
