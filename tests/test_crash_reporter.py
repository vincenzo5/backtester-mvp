"""
Tests for crash reporter.
"""

import unittest
import tempfile
from pathlib import Path
import json

from backtester.config import ConfigManager
from backtester.debug import CrashReporter


class TestCrashReporter(unittest.TestCase):
    """Test crash reporter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ConfigManager()
        self.debug_config = self.config.get_debug_config()
    
    def test_reporter_initialization(self):
        """Test reporter initializes correctly."""
        reporter = CrashReporter(self.debug_config)
        
        self.assertIsNotNone(reporter)
        self.assertEqual(reporter.enabled, 
                        self.debug_config.enabled and self.debug_config.crash_reports.enabled)
    
    def test_reporter_disabled_when_config_disabled(self):
        """Test reporter is disabled when config disabled."""
        self.debug_config.enabled = False
        reporter = CrashReporter(self.debug_config)
        
        self.assertFalse(reporter.enabled)
        self.assertIsNone(reporter.queue)
    
    def test_should_capture_checks(self):
        """Test should_capture logic."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        reporter = CrashReporter(self.debug_config)
        reporter.start()
        
        # Check trigger not in list
        result = reporter.should_capture('unknown_trigger', severity='error')
        self.assertFalse(result)
        
        # Check valid trigger (if exception is in triggers)
        if 'exception' in self.debug_config.crash_reports.auto_capture.triggers:
            result = reporter.should_capture('exception', Exception('Test'), severity='error')
            self.assertTrue(result)
        
        reporter.stop()
    
    def test_capture_methods(self):
        """Test capture methods don't crash."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        reporter = CrashReporter(self.debug_config)
        reporter.start()
        
        # Should not raise exceptions
        reporter.capture('exception', Exception('Test'), context={'test': True}, severity='error')
        
        # Give background thread time to process
        import time
        time.sleep(0.2)
        
        reporter.stop()
    
    def test_fatal_error_detection(self):
        """Test fatal error detection."""
        if not self.debug_config.enabled:
            self.skipTest("Debug not enabled")
        
        reporter = CrashReporter(self.debug_config)
        
        # KeyboardInterrupt should be detected as fatal
        self.assertTrue(reporter._is_fatal_error(KeyboardInterrupt()))
        
        # SystemExit should be detected as fatal
        self.assertTrue(reporter._is_fatal_error(SystemExit()))
        
        # Regular exception should not be fatal
        self.assertFalse(reporter._is_fatal_error(ValueError('Test')))
        
        # None should not be fatal
        self.assertFalse(reporter._is_fatal_error(None))


if __name__ == '__main__':
    unittest.main()

