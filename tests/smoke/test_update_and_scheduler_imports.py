"""
Smoke tests for imports of update and scheduler services.
"""

import unittest
import pytest


@pytest.mark.smoke
class TestServiceImports(unittest.TestCase):
    def test_update_runner_import(self):
        from backtester.services import update_runner  # noqa: F401
        self.assertTrue(True)

    def test_scheduler_daemon_import(self):
        from backtester.services import scheduler_daemon  # noqa: F401
        self.assertTrue(True)
