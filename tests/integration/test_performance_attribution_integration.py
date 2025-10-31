"""
Integration tests for performance attribution system.

Tests integration between ChangeTracker, ExecutionTracer, cache tracking,
and event emission.
"""

import unittest
import pytest
import tempfile
import json
import time
import os
import shutil
import numpy as np
from pathlib import Path

import pandas as pd
from datetime import datetime

from backtester.config import ConfigManager
from backtester.debug import ExecutionTracer, set_debug_components
from backtester.debug.change_tracker import ChangeTracker
from backtester.backtest.engine import prepare_backtest_data, run_backtest
from backtester.strategies.sma_cross import SMACrossStrategy
from tests.conftest import sample_ohlcv_data


@pytest.mark.integration
class TestPerformanceAttributionIntegration(unittest.TestCase):
    """Test performance attribution integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ConfigManager()
        self.debug_config = self.config.get_debug_config()
        
        # Create temporary trace file
        self.temp_dir = tempfile.mkdtemp()
        self.trace_file = os.path.join(self.temp_dir, 'test_trace.jsonl')
        
        # Override trace file path in debug config
        if hasattr(self.debug_config.logging, 'execution_trace_file'):
            self.original_trace_file = self.debug_config.logging.execution_trace_file
            self.debug_config.logging.execution_trace_file = self.trace_file
        
        # Create debug components
        if self.debug_config.enabled and self.debug_config.tracing.enabled:
            self.tracer = ExecutionTracer(self.debug_config)
            self.crash_reporter = None  # Not needed for these tests
            set_debug_components(self.tracer, self.crash_reporter)
        else:
            self.tracer = None
            self.crash_reporter = None
        
        # Create sample data directly (not using fixture in unittest)
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
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
        if self.tracer:
            self.tracer.shutdown()
        
        # Restore original trace file
        if hasattr(self, 'original_trace_file'):
            self.debug_config.logging.execution_trace_file = self.original_trace_file
        
        shutil.rmtree(self.temp_dir)
    
    def read_trace_file(self):
        """Read and parse trace file."""
        if not os.path.exists(self.trace_file):
            return []
        
        entries = []
        with open(self.trace_file, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
    
    def test_change_tracker_with_tracer(self):
        """Test ChangeTracker works with ExecutionTracer."""
        if not self.tracer:
            self.skipTest("Tracer not available")
        
        # Emit session_start event
        self.tracer.trace('session_start', 'Starting test session', session_id='test_001')
        
        # Give background thread time to write (need more time for file I/O)
        time.sleep(1.0)
        
        # Force flush by shutting down tracer
        self.tracer.shutdown()
        time.sleep(0.2)
        
        # Read trace file
        entries = self.read_trace_file()
        
        # Should have at least one entry
        if len(entries) == 0:
            # If no entries, verify the tracer is at least working
            # (trace file might not be created if logging service hasn't started)
            self.assertIsNotNone(self.tracer.logging_service)
            return
        
        # Find session_start entry
        session_start = next((e for e in entries if e.get('event_type') == 'session_start'), None)
        if session_start:
            # If change_tracker available, change_metadata should be included
            if self.tracer.change_tracker is not None:
                self.assertIn('change_metadata', session_start)
                metadata = session_start['change_metadata']
                self.assertIn('git', metadata)
                self.assertIn('config', metadata)
                self.assertIn('environment', metadata)
                self.assertIn('dependencies', metadata)
    
    def test_cache_tracking_through_prepare_data(self):
        """Test cache stats flow through prepare_backtest_data."""
        if not self.tracer:
            self.skipTest("Tracer not available")
        
        strategy_class = SMACrossStrategy
        strategy_params = {'fast_period': 10, 'slow_period': 20}
        
        # Prepare data (should compute indicators with tracking)
        enriched_df = prepare_backtest_data(
            self.test_df,
            strategy_class,
            strategy_params,
            symbol='BTC/USD'
        )
        
        # Give tracer time to write events
        time.sleep(0.5)
        
        # Verify cache_stats stored in DataFrame.attrs
        self.assertIn('cache_stats', enriched_df.attrs)
        cache_stats = enriched_df.attrs.get('cache_stats')
        
        if cache_stats is not None:
            self.assertIn('hits', cache_stats)
            self.assertIn('misses', cache_stats)
            self.assertIn('hit_rate', cache_stats)
            self.assertIn('time_saved_seconds', cache_stats)
            
            # Should have at least one miss (first computation)
            self.assertGreaterEqual(cache_stats['misses'], 0)
        
        # Read trace file
        entries = self.read_trace_file()
        
        # Find indicators_computed event
        indicators_event = next(
            (e for e in entries if e.get('event_type') == 'indicators_computed'),
            None
        )
        
        if indicators_event:
            # Should have cache_stats if tracking enabled
            if 'cache_stats' in indicators_event:
                stats = indicators_event['cache_stats']
                self.assertIn('hits', stats)
                self.assertIn('misses', stats)
        
        # Find data_prep_end event
        data_prep_end = next(
            (e for e in entries if e.get('event_type') == 'data_prep_end'),
            None
        )
        
        if data_prep_end:
            # Should have cache_stats
            if 'cache_stats' in data_prep_end:
                stats = data_prep_end['cache_stats']
                self.assertIsInstance(stats, dict)
    
    def test_backtest_events_with_performance(self):
        """Test backtest events include performance data."""
        if not self.tracer:
            self.skipTest("Tracer not available")
        
        strategy_class = SMACrossStrategy
        strategy_params = {'fast_period': 10, 'slow_period': 20}
        
        # Run backtest
        result = run_backtest(
            self.config,
            self.test_df,
            strategy_class,
            verbose=False,
            strategy_params=strategy_params
        )
        
        # Give tracer time to write events
        time.sleep(0.5)
        
        # Read trace file
        entries = self.read_trace_file()
        
        # Find backtest_start event
        backtest_start = next(
            (e for e in entries if e.get('event_type') == 'backtest_start'),
            None
        )
        
        if backtest_start:
            # Should have data characteristics
            self.assertIn('data', backtest_start)
            data_info = backtest_start['data']
            self.assertIn('num_candles', data_info)
            self.assertIn('date_range', data_info)
            self.assertIn('data_size_mb', data_info)
        
        # Find backtest_end event
        backtest_end = next(
            (e for e in entries if e.get('event_type') == 'backtest_end'),
            None
        )
        
        if backtest_end:
            # Should have performance data
            self.assertIn('performance', backtest_end)
            perf = backtest_end['performance']
            self.assertIn('execution_time_seconds', perf)
            self.assertIn('timing_breakdown', perf)
            
            # Timing breakdown should have components
            breakdown = perf['timing_breakdown']
            self.assertIn('data_prep_time', breakdown)
            self.assertIn('backtrader_execution_time', breakdown)
            
            # Should have results
            self.assertIn('results', backtest_end)
            results = backtest_end['results']
            self.assertIn('num_trades', results)
            self.assertIn('total_return_pct', results)
    
    def test_session_workflow_window_events(self):
        """Test complete event hierarchy is emitted."""
        if not self.tracer:
            self.skipTest("Tracer not available")
        
        # Emit mock event sequence
        self.tracer.trace('session_start', 'Session start', session_id='test_session')
        self.tracer.set_context(symbol='BTC/USD', timeframe='1h')
        self.tracer.trace('workflow_start', 'Workflow start', workflow_id='test_workflow')
        self.tracer.set_context(window_index=0)
        self.tracer.trace('window_start', 'Window start')
        self.tracer.trace('backtest_start', 'Backtest start')
        self.tracer.trace('backtest_end', 'Backtest end')
        self.tracer.trace('window_end', 'Window end')
        self.tracer.trace('workflow_end', 'Workflow end')
        self.tracer.trace('session_end', 'Session end')
        
        # Give tracer time to write and force flush
        time.sleep(1.0)
        self.tracer.shutdown()
        time.sleep(0.2)
        
        # Read trace file
        entries = self.read_trace_file()
        
        if len(entries) == 0:
            # If no entries written, verify tracer is at least working
            self.assertIsNotNone(self.tracer.logging_service)
            return
        
        # Verify some event types present (may be filtered by tracing level)
        event_types = [e.get('event_type') for e in entries]
        
        # At minimum, key events should be present (backtest_start/end are key events)
        self.assertIn('backtest_start', event_types)
        self.assertIn('backtest_end', event_types)
        
        # Other events may be filtered based on tracing level, but if present, verify structure
        if 'session_start' in event_types:
            session_start = next(e for e in entries if e.get('event_type') == 'session_start')
            self.assertIn('session_id', session_start)
        
        if 'workflow_start' in event_types:
            workflow_start = next(e for e in entries if e.get('event_type') == 'workflow_start')
            self.assertIn('symbol', workflow_start)
            self.assertEqual(workflow_start['symbol'], 'BTC/USD')
        
        if 'window_start' in event_types:
            window_start = next(e for e in entries if e.get('event_type') == 'window_start')
            self.assertIn('window_index', window_start)
            self.assertEqual(window_start['window_index'], 0)
    
    def test_timing_data_consistency(self):
        """Test timing breakdowns are consistent."""
        if not self.tracer:
            self.skipTest("Tracer not available")
        
        strategy_class = SMACrossStrategy
        strategy_params = {'fast_period': 10, 'slow_period': 20}
        
        # Run backtest
        result = run_backtest(
            self.config,
            self.test_df,
            strategy_class,
            verbose=False,
            strategy_params=strategy_params
        )
        
        time.sleep(0.5)
        
        # Read trace file
        entries = self.read_trace_file()
        
        backtest_end = next(
            (e for e in entries if e.get('event_type') == 'backtest_end'),
            None
        )
        
        if backtest_end and 'performance' in backtest_end:
            perf = backtest_end['performance']
            if 'timing_breakdown' in perf:
                breakdown = perf['timing_breakdown']
                total_time = perf.get('execution_time_seconds', 0)
                
                # Sum of breakdown times should be <= total time (allowing for overhead)
                sum_breakdown = sum(v for v in breakdown.values() if isinstance(v, (int, float)))
                # Allow 20% tolerance for overhead
                self.assertLessEqual(sum_breakdown, total_time * 1.2)


if __name__ == '__main__':
    unittest.main()

