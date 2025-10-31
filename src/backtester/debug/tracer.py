"""
Execution tracer for backtest debugging.

Traces execution flow with configurable verbosity levels and sampling.
"""

import time
import random
import queue
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from backtester.config.core.accessor import DebugConfig
from backtester.debug.logging_service import LoggingService
from backtester.debug.exceptions import TracingError

# Import ChangeTracker only when needed to avoid circular dependencies
try:
    from backtester.debug.change_tracker import ChangeTracker
except ImportError:
    ChangeTracker = None


class ExecutionTracer:
    """
    Thread-safe execution tracer with queue-based logging.
    
    Tracks execution flow with configurable verbosity levels:
    - minimal: Only errors
    - standard: Key steps + errors
    - detailed: All steps (with optional sampling)
    """
    
    def __init__(self, config: DebugConfig):
        """
        Initialize execution tracer.
        
        Args:
            config: Debug configuration
        """
        self.config = config
        self.enabled = config.enabled and config.tracing.enabled
        
        if not self.enabled:
            self.logging_service = None
            return
        
        # Create queue and logging service
        self.queue = queue.Queue()
        self.logging_service = LoggingService(config, self.queue)
        self.logging_service.start()
        
        # Initialize change tracker for change attribution
        self.change_tracker = None
        if ChangeTracker is not None:
            try:
                self.change_tracker = ChangeTracker()
            except Exception:
                # If change tracking fails to initialize, continue without it
                self.change_tracker = None
        
        # Context tracking
        self.current_context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """
        Set execution context (symbol, timeframe, window, parameters, etc.).
        
        Args:
            **kwargs: Context key-value pairs to set
        """
        if not self.enabled:
            return
        
        self.current_context.update(kwargs)
    
    def clear_context(self):
        """Clear current execution context."""
        if not self.enabled:
            return
        
        self.current_context.clear()
    
    def trace(self, event_type: str, message: str = "", **kwargs):
        """
        Trace an execution event.
        
        Args:
            event_type: Type of event (e.g., 'function_entry', 'function_exit', 'error')
            message: Optional message
            **kwargs: Additional event data
        """
        if not self.enabled:
            return
        
        if not self._should_log(event_type):
            return
        
        entry = self._build_entry(event_type, message, **kwargs)
        
        try:
            self.queue.put_nowait(entry)  # Non-blocking
        except queue.Full:
            # Queue full - log warning but don't block
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Execution tracer queue full, dropping entry")
    
    def trace_function_entry(self, function_name: str, **kwargs):
        """Convenience method to trace function entry."""
        self.trace('function_entry', f"Entering {function_name}", function=function_name, **kwargs)
    
    def trace_function_exit(self, function_name: str, duration: Optional[float] = None, **kwargs):
        """Convenience method to trace function exit."""
        msg = f"Exiting {function_name}"
        if duration is not None:
            msg += f" (duration: {duration:.3f}s)"
        self.trace('function_exit', msg, function=function_name, duration=duration, **kwargs)
    
    def trace_error(self, error: Exception, **kwargs):
        """Convenience method to trace errors."""
        self.trace('error', str(error), 
                  error_type=type(error).__name__,
                  error_message=str(error),
                  **kwargs)
    
    def _should_log(self, event_type: str) -> bool:
        """
        Check if event should be logged based on level and sampling.
        
        Args:
            event_type: Type of event
            
        Returns:
            True if event should be logged
        """
        level = self.config.tracing.level
        
        # Errors always logged
        if event_type == 'error':
            return True
        
        # Minimal level: Only errors (already handled above)
        if level == 'minimal':
            return False
        
        # Standard level: Key steps
        if level == 'standard':
            key_events = [
                'function_entry', 'function_exit',
                'backtest_start', 'backtest_end',
                'optimization_start', 'optimization_end',
                'window_start', 'window_end'
            ]
            return event_type in key_events
        
        # Detailed level: All steps (with sampling)
        if level == 'detailed':
            sample_rate = self.config.tracing.sample_rate
            if sample_rate >= 1.0:
                return True  # Log all
            return random.random() < sample_rate
        
        return False
    
    def _build_entry(self, event_type: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Build a log entry dictionary.
        
        Args:
            event_type: Type of event
            message: Optional message
            **kwargs: Additional event data
            
        Returns:
            Dictionary representing log entry
        """
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'event_type': event_type,
            'message': message,
            **self.current_context.copy(),  # Include current context
            **kwargs  # Include event-specific data
        }
        
        # Add change metadata to session_start events
        if event_type == 'session_start' and self.change_tracker:
            try:
                entry['change_metadata'] = self.change_tracker.get_change_metadata()
            except Exception:
                # If change tracking fails, continue without it
                pass
        
        return entry
    
    def shutdown(self):
        """Shutdown tracer and logging service."""
        if self.logging_service:
            self.logging_service.stop()

