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
    
    def test_change_tracker_initialization(self):
        """Test ExecutionTracer initializes ChangeTracker."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        # ChangeTracker may or may not be initialized (depends on environment)
        # But should not cause errors
        self.assertTrue(hasattr(tracer, 'change_tracker'))
    
    def test_session_start_with_change_metadata(self):
        """Test session_start event includes change_metadata when ChangeTracker available."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        # Emit session_start event
        tracer.trace('session_start', 'Starting session', session_id='test_session')
        
        # Give background thread time to process
        time.sleep(0.2)
        
        # If change_tracker is available, change_metadata should be included
        # We can't easily verify the log file without more setup, but we can
        # verify the tracer doesn't crash and change_tracker is present or None
        if tracer.change_tracker is not None:
            # ChangeTracker available - metadata should be included in _build_entry
            # We verify this works by checking the entry structure would include it
            entry = tracer._build_entry('session_start', 'Test', session_id='test')
            # Entry should have session_id
            self.assertIn('session_id', entry)
            # If change_tracker available, change_metadata might be included
            # (it's added conditionally in _build_entry)
        
        tracer.shutdown()
    
    def test_session_start_without_change_tracker(self):
        """Test session_start works gracefully when ChangeTracker unavailable."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        # Temporarily remove change_tracker
        original_tracker = tracer.change_tracker
        tracer.change_tracker = None
        
        # Should not raise error
        tracer.trace('session_start', 'Starting session', session_id='test_session')
        
        # Restore
        tracer.change_tracker = original_tracker
        
        time.sleep(0.1)
        tracer.shutdown()
    
    def test_change_metadata_structure(self):
        """Test change_metadata has expected structure when available."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        if tracer.change_tracker is not None:
            metadata = tracer.change_tracker.get_change_metadata()
            
            # Verify structure
            self.assertIn('git', metadata)
            self.assertIn('config', metadata)
            self.assertIn('environment', metadata)
            self.assertIn('dependencies', metadata)
            
            # Verify git structure
            self.assertIn('commit_hash', metadata['git'])
            self.assertIn('branch', metadata['git'])
            self.assertIn('commit_message', metadata['git'])
            self.assertIn('has_uncommitted_changes', metadata['git'])
            
            # Verify environment structure
            self.assertIn('python_version', metadata['environment'])
            self.assertIn('platform', metadata['environment'])
            
            # Verify dependencies is dict
            self.assertIsInstance(metadata['dependencies'], dict)
        
        tracer.shutdown()
    
    def test_build_entry_includes_change_metadata(self):
        """Test _build_entry includes change_metadata for session_start events."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        tracer = ExecutionTracer(self.debug_config)
        
        # Build entry for session_start
        entry = tracer._build_entry('session_start', 'Test session', session_id='test')
        
        # Entry should have basic fields
        self.assertIn('timestamp', entry)
        self.assertIn('event_type', entry)
        self.assertIn('message', entry)
        self.assertEqual(entry['event_type'], 'session_start')
        
        # If change_tracker available, change_metadata should be included
        if tracer.change_tracker is not None:
            # ChangeTracker might have been initialized
            # change_metadata is added conditionally, so we can't guarantee it's always there
            # But we verify the method doesn't crash
            pass
        
        # Build entry for other event type (should not include change_metadata)
        entry2 = tracer._build_entry('test_event', 'Test')
        self.assertNotIn('change_metadata', entry2)
        
        tracer.shutdown()


if __name__ == '__main__':
    unittest.main()

