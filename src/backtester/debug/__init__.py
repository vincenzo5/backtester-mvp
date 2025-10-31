"""
Debug agent module for execution tracing and crash reporting.
"""

from typing import Optional
from backtester.debug.tracer import ExecutionTracer
from backtester.debug.crash_reporter import CrashReporter
from backtester.debug.exceptions import DebugError, TracingError, CrashReportError

__all__ = [
    'ExecutionTracer',
    'CrashReporter',
    'DebugError',
    'TracingError',
    'CrashReportError',
    'get_tracer',
    'get_crash_reporter',
    'set_debug_components',
]

# Module-level debug components (set by main.py)
_tracer: Optional[ExecutionTracer] = None
_crash_reporter: Optional[CrashReporter] = None


def set_debug_components(tracer: Optional[ExecutionTracer] = None,
                         crash_reporter: Optional[CrashReporter] = None):
    """
    Set global debug components (called by main.py).
    
    Args:
        tracer: ExecutionTracer instance
        crash_reporter: CrashReporter instance
    """
    global _tracer, _crash_reporter
    _tracer = tracer
    _crash_reporter = crash_reporter


def get_tracer() -> Optional[ExecutionTracer]:
    """Get current ExecutionTracer instance."""
    return _tracer


def get_crash_reporter() -> Optional[CrashReporter]:
    """Get current CrashReporter instance."""
    return _crash_reporter

