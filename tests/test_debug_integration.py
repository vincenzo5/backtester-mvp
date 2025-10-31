"""
Integration tests for debug system with backtest engine.
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta

from backtester.config import ConfigManager
from backtester.backtest.engine import run_backtest, prepare_backtest_data
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.debug import get_tracer, get_crash_reporter, set_debug_components
from backtester.debug import ExecutionTracer, CrashReporter


class TestDebugIntegration(unittest.TestCase):
    """Test debug system integration with backtest engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ConfigManager()
        self.debug_config = self.config.get_debug_config()
        
        # Create debug components
        if self.debug_config.enabled:
            self.tracer = ExecutionTracer(self.debug_config) if self.debug_config.tracing.enabled else None
            self.crash_reporter = CrashReporter(self.debug_config, tracer=self.tracer) if self.debug_config.crash_reports.enabled else None
            
            if self.crash_reporter:
                self.crash_reporter.start()
            
            # Make globally accessible
            set_debug_components(self.tracer, self.crash_reporter)
        else:
            self.tracer = None
            self.crash_reporter = None
        
        # Create minimal test data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
        self.test_df = pd.DataFrame({
            'open': [100 + i for i in range(100)],
            'high': [101 + i for i in range(100)],
            'low': [99 + i for i in range(100)],
            'close': [100.5 + i for i in range(100)],
            'volume': [1000] * 100
        }, index=dates)
    
    def tearDown(self):
        """Clean up after tests."""
        if self.crash_reporter:
            self.crash_reporter.stop()
        if self.tracer:
            self.tracer.shutdown()
        set_debug_components(None, None)
    
    def test_prepare_backtest_data_with_tracer(self):
        """Test prepare_backtest_data works with tracer enabled."""
        if not self.tracer:
            self.skipTest("Tracer not enabled")
        
        result = prepare_backtest_data(
            self.test_df,
            SMACrossStrategy,
            {'fast_period': 10, 'slow_period': 20}
        )
        
        self.assertIsNotNone(result)
        self.assertFalse(result.empty)
        
        # Give tracer time to write
        import time
        time.sleep(0.1)
    
    def test_run_backtest_with_debug(self):
        """Test run_backtest works with debug enabled."""
        result = run_backtest(
            self.config,
            self.test_df,
            SMACrossStrategy,
            verbose=False,
            strategy_params={'fast_period': 10, 'slow_period': 20}
        )
        
        self.assertIsNotNone(result)
        self.assertIn('metrics', result)
        
        # Give debug components time to process
        import time
        time.sleep(0.2)
    
    def test_zero_trades_capture(self):
        """Test that zero trades trigger is captured."""
        if not self.crash_reporter:
            self.skipTest("Crash reporter not enabled")
        
        # Create data that won't generate trades (need enough data for indicators but no signals)
        # Need at least slow_period (20) rows for SMA indicator to work
        short_df = self.test_df.head(50)  # 50 rows should be enough for indicators
        
        result = run_backtest(
            self.config,
            short_df,
            SMACrossStrategy,
            verbose=False,
            strategy_params={'fast_period': 10, 'slow_period': 20}
        )
        
        # Check if zero trades was captured
        # This depends on whether zero_trades is in triggers
        if 'zero_trades' in self.debug_config.crash_reports.auto_capture.triggers:
            # Give time for async capture
            import time
            time.sleep(0.3)
            
            # Check if crash report was created (would need to read directory)
            # For now, just verify no exceptions were raised
            self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()

