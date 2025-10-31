"""
Tests for execution tracer.
"""

import unittest
import tempfile
from pathlib import Path
import time
import json

from backtester.config import ConfigManager
from backtester.debug import ExecutionTracer


class TestExecutionTracer(unittest.TestCase):
    """Test execution tracer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ConfigManager()
        self.debug_config = self.config.get_debug_config()
    
    def test_tracer_initialization(self):
        """Test tracer initializes correctly."""
        tracer = ExecutionTracer(self.debug_config)
        
        self.assertIsNotNone(tracer)
        self.assertEqual(tracer.enabled, self.debug_config.enabled and self.debug_config.tracing.enabled)
    
    def test_tracer_disabled_when_config_disabled(self):
        """Test tracer is disabled when config disabled."""
        self.debug_config.enabled = False
        tracer = ExecutionTracer(self.debug_config)
        
        self.assertFalse(tracer.enabled)
        self.assertIsNone(tracer.logging_service)
    
    def test_tracer_context(self):
        """Test context tracking."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        tracer.set_context(symbol='BTC/USD', timeframe='1h')
        
        self.assertEqual(tracer.current_context.get('symbol'), 'BTC/USD')
        self.assertEqual(tracer.current_context.get('timeframe'), '1h')
        
        tracer.clear_context()
        self.assertEqual(len(tracer.current_context), 0)
    
    def test_tracer_trace_methods(self):
        """Test tracer trace methods don't crash."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        # Should not raise exceptions
        tracer.trace('test_event', 'Test message')
        tracer.trace_function_entry('test_function')
        tracer.trace_function_exit('test_function', duration=1.0)
        tracer.trace_error(Exception('Test error'))
        
        # Give background thread time to process
        time.sleep(0.1)
        
        tracer.shutdown()
    
    def test_tracer_shutdown(self):
        """Test tracer shuts down cleanly."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        # Should not raise
        tracer.shutdown()
        
        # Second shutdown should also work
        tracer.shutdown()


if __name__ == '__main__':
    unittest.main()

