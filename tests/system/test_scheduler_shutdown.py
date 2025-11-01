"""
System test verifying graceful shutdown behavior of SchedulerDaemon.
"""

import unittest
import pytest

from backtester.services.scheduler_daemon import SchedulerDaemon


class _FakeScheduler:
    def __init__(self):
        self.shutdown_called = False
        self.shutdown_wait = None

    def add_listener(self, *args, **kwargs):
        pass

    def add_job(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def shutdown(self, wait=True):
        self.shutdown_called = True
        self.shutdown_wait = wait


@pytest.mark.system
class TestSchedulerShutdown(unittest.TestCase):
    def test_stop_waits_for_jobs(self):
        daemon = SchedulerDaemon(update_hour=0, update_minute=0)
        fake = _FakeScheduler()
        daemon.scheduler = fake
        daemon.running = True

        daemon.stop()

        self.assertTrue(fake.shutdown_called)
        self.assertTrue(fake.shutdown_wait)
