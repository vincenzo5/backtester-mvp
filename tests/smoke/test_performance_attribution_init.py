"""
Smoke tests for performance attribution initialization.

Tests that components can be imported and initialized without errors.
"""

import unittest
import pytest
import tempfile
import shutil
from pathlib import Path

from backtester.debug.change_tracker import ChangeTracker
from backtester.indicators.library import IndicatorLibrary
from backtester.config import ConfigManager
from backtester.debug import ExecutionTracer


@pytest.mark.smoke
class TestPerformanceAttributionInit(unittest.TestCase):
    """Test performance attribution components can be initialized."""
    
    def test_change_tracker_import(self):
        """Test ChangeTracker can be imported."""
        from backtester.debug.change_tracker import ChangeTracker
        self.assertIsNotNone(ChangeTracker)
    
    def test_change_tracker_initialization(self):
        """Test ChangeTracker initializes without errors."""
        tracker = ChangeTracker()
        self.assertIsNotNone(tracker)
        self.assertIsNotNone(tracker.project_root)
    
    def test_change_tracker_initialization_with_root(self):
        """Test ChangeTracker initializes with custom project root."""
        temp_dir = tempfile.mkdtemp()
        try:
            tracker = ChangeTracker(project_root=Path(temp_dir))
            self.assertEqual(tracker.project_root, Path(temp_dir))
        finally:
            shutil.rmtree(temp_dir)
    
    def test_change_tracker_handles_missing_git(self):
        """Test ChangeTracker handles missing git repo gracefully."""
        temp_dir = tempfile.mkdtemp()
        try:
            tracker = ChangeTracker(project_root=Path(temp_dir))
            metadata = tracker.get_change_metadata()
            # Should return 'unknown' for git info when no git repo
            self.assertIn('git', metadata)
            self.assertIn('commit_hash', metadata['git'])
            # Should not raise exception
        finally:
            shutil.rmtree(temp_dir)
    
    def test_indicator_library_cache_stats_init(self):
        """Test IndicatorLibrary initializes cache stats."""
        lib = IndicatorLibrary()
        self.assertTrue(hasattr(lib, '_cache_stats'))
        self.assertIn('hits', lib._cache_stats)
        self.assertIn('misses', lib._cache_stats)
        self.assertIn('computations', lib._cache_stats)
        self.assertIn('time_saved_seconds', lib._cache_stats)
        
        # Verify initial values are zero
        self.assertEqual(lib._cache_stats['hits'], 0)
        self.assertEqual(lib._cache_stats['misses'], 0)
    
    def test_indicator_library_get_cache_stats(self):
        """Test IndicatorLibrary.get_cache_stats returns valid structure."""
        lib = IndicatorLibrary()
        stats = lib.get_cache_stats()
        
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('hit_rate', stats)
        self.assertIn('total_requests', stats)
        self.assertIn('time_saved_seconds', stats)
        
        # Initial stats should be zero
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['total_requests'], 0)
        self.assertEqual(stats['hit_rate'], 0.0)
    
    def test_execution_tracer_with_change_tracker(self):
        """Test ExecutionTracer initializes with ChangeTracker."""
        config = ConfigManager()
        debug_config = config.get_debug_config()
        
        if debug_config.enabled and debug_config.tracing.enabled:
            tracer = ExecutionTracer(debug_config)
            self.assertIsNotNone(tracer)
            # ChangeTracker may or may not be initialized depending on environment
            # Just verify tracer doesn't crash
            self.assertTrue(hasattr(tracer, 'change_tracker') or tracer.change_tracker is None)
        else:
            # If debug disabled, skip test
            self.skipTest("Debug/tracing not enabled")


if __name__ == '__main__':
    unittest.main()

