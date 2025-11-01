"""
Integration tests for update lock behavior in update_runner.
"""

import os
import json
import unittest
import pytest
from pathlib import Path

from backtester.services import update_runner


@pytest.mark.integration
class TestUpdateLockIntegration(unittest.TestCase):
    """Test update lock presence and cleanup."""

    def setUp(self):
        self.lock_dir = Path('artifacts/locks')
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.lock_dir / 'update.lock'
        # Ensure clean state
        if self.lock_file.exists():
            self.lock_file.unlink()

    def tearDown(self):
        # Cleanup
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception:
            pass

    def test_run_update_returns_busy_when_lock_exists(self):
        """If lock exists before start, run_update should return busy and not create/modify files."""
        self.lock_file.write_text('locked')
        result = update_runner.run_update(target_end_date=None)
        self.assertEqual(result.get('status'), 'busy')
        # Lock should remain unchanged by busy path
        self.assertTrue(self.lock_file.exists())

    def test_run_update_removes_lock_on_error(self):
        """When an error occurs after acquiring lock, lock is removed in finally."""
        # Ensure no pre-existing lock so run_update acquires it
        if self.lock_file.exists():
            self.lock_file.unlink()

        # Monkeypatch load_exchange_metadata to raise
        original_loader = update_runner.load_exchange_metadata
        try:
            def raise_loader():  # noqa: D401
                raise RuntimeError('boom')
            update_runner.load_exchange_metadata = raise_loader

            result = update_runner.run_update(target_end_date=None)
            self.assertEqual(result.get('status'), 'error')
            # Lock should be removed even on error
            self.assertFalse(self.lock_file.exists())
        finally:
            update_runner.load_exchange_metadata = original_loader
