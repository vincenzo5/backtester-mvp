"""
Custom exceptions for debug module.
"""


class DebugError(Exception):
    """Base exception for debug module errors."""
    pass


class TracingError(DebugError):
    """Exception raised when tracing operations fail."""
    pass


class CrashReportError(DebugError):
    """Exception raised when crash report generation fails."""
    pass

