"""
Crash reporter for automatic failure capture.

Generates crash reports with context, stack traces, and system information.
"""

import json
import queue
import shutil
import traceback
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from backtester.config.core.accessor import DebugConfig
from backtester.debug.exceptions import CrashReportError


class CrashReporter:
    """
    Thread-safe crash reporter with async queue-based generation.
    
    Captures crashes with full context, stack traces, and system info.
    Supports multi-factor storage limits and automatic cleanup.
    """
    
    def __init__(self, config: DebugConfig, tracer=None):
        """
        Initialize crash reporter.
        
        Args:
            config: Debug configuration
            tracer: Optional ExecutionTracer instance for capturing trace tail
        """
        self.config = config
        self.enabled = config.enabled and config.crash_reports.enabled
        self.tracer = tracer
        self.crash_report_dir = Path(config.logging.crash_report_dir)
        self.crash_report_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.enabled:
            self.queue = None
            self.background_thread = None
            return
        
        # Create queue and background thread
        self.queue = queue.Queue()
        self.running = False
        self.background_thread = None
        
        # Severity levels for comparison
        self.severity_levels = {'info': 0, 'warning': 1, 'error': 2}
    
    def start(self):
        """Start the background crash report generation thread."""
        if not self.enabled or self.running:
            return
        
        self.running = True
        self.background_thread = threading.Thread(target=self._run, daemon=True)
        self.background_thread.start()
    
    def stop(self, timeout: float = 5.0):
        """
        Stop the background thread.
        
        Args:
            timeout: Maximum time to wait for thread to finish
        """
        if not self.running:
            return
        
        self.running = False
        
        # Put sentinel value to wake up thread
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        
        if self.background_thread:
            self.background_thread.join(timeout=timeout)
    
    def should_capture(self, trigger_type: str, exception: Exception = None, 
                      severity: str = 'error') -> bool:
        """
        Check if trigger should generate crash report.
        
        Args:
            trigger_type: Type of trigger (e.g., 'exception', 'zero_trades')
            exception: Optional exception object
            severity: Severity level ('error', 'warning', 'info')
            
        Returns:
            True if crash report should be generated
        """
        if not self.enabled:
            return False
        
        # Check if trigger is enabled
        triggers = self.config.crash_reports.auto_capture.triggers
        if trigger_type not in triggers:
            return False
        
        # Check severity threshold
        min_severity = self.config.crash_reports.auto_capture.min_severity
        if self.severity_levels.get(severity, 0) < self.severity_levels.get(min_severity, 0):
            return False
        
        # Check if exception is fatal (always capture)
        if exception and self._is_fatal_error(exception):
            return True
        
        # Check storage limits
        if not self._check_storage_limits():
            return False
        
        return True
    
    def capture(self, trigger_type: str, exception: Exception = None,
               context: Dict = None, severity: str = 'error', sync: bool = False):
        """
        Generate crash report.
        
        Args:
            trigger_type: Type of trigger (e.g., 'exception', 'zero_trades')
            exception: Optional exception object
            context: Execution context dictionary
            severity: Severity level ('error', 'warning', 'info')
            sync: If True, generate synchronously (for fatal errors)
        """
        if not self.enabled:
            return
        
        if sync or (exception and self._is_fatal_error(exception)):
            self._generate_report_sync(trigger_type, exception, context, severity)
        else:
            try:
                self.queue.put_nowait((trigger_type, exception, context, severity))
            except queue.Full:
                # Queue full - fallback to sync generation
                self._generate_report_sync(trigger_type, exception, context, severity)
    
    def _is_fatal_error(self, exception: Exception) -> bool:
        """
        Check if exception is fatal (would exit program).
        
        Args:
            exception: Exception to check
            
        Returns:
            True if exception is fatal
        """
        if exception is None:
            return False
        
        fatal_types = (KeyboardInterrupt, SystemExit)
        return isinstance(exception, fatal_types)
    
    def _check_storage_limits(self) -> bool:
        """
        Check if storage limits allow new crash report.
        
        Returns:
            True if limits allow, False otherwise
        """
        # Check disk space
        if HAS_PSUTIL:
            try:
                free_space_mb = shutil.disk_usage(self.crash_report_dir).free / (1024 * 1024)
                if free_space_mb < self.config.crash_reports.min_free_disk_mb:
                    return False
            except Exception:
                pass  # Ignore disk check errors
        
        # Check count limit
        existing_reports = list(self.crash_report_dir.glob('crash_*.json'))
        if len(existing_reports) >= self.config.crash_reports.max_reports:
            # Cleanup oldest reports
            self._cleanup_old_reports(keep_count=self.config.crash_reports.max_reports - 1)
            # Refresh list after cleanup to avoid stale file references
            existing_reports = list(self.crash_report_dir.glob('crash_*.json'))
        
        # Check size limit - use only files that still exist
        # Handle race condition where files may be deleted between glob() and stat()
        total_size_mb = 0
        for f in existing_reports:
            try:
                if f.exists():
                    total_size_mb += f.stat().st_size / (1024 * 1024)
            except (FileNotFoundError, OSError):
                # File was deleted between glob() and stat() - skip it
                continue
        
        if total_size_mb >= self.config.crash_reports.max_total_size_mb:
            # Cleanup until under limit
            self._cleanup_old_reports(target_size_mb=self.config.crash_reports.max_total_size_mb * 0.8)
        
        return True
    
    def _cleanup_old_reports(self, keep_count: int = None, target_size_mb: float = None):
        """
        Cleanup oldest crash reports.
        
        Args:
            keep_count: Number of reports to keep (if specified)
            target_size_mb: Target total size in MB (if specified)
        """
        reports = sorted(self.crash_report_dir.glob('crash_*.json'), 
                        key=lambda p: p.stat().st_mtime)
        
        if keep_count is not None:
            # Remove oldest reports
            to_remove = reports[:-keep_count] if len(reports) > keep_count else []
        elif target_size_mb is not None:
            # Remove reports until under target size
            current_size = sum(f.stat().st_size for f in reports) / (1024 * 1024)
            to_remove = []
            for report in reports:
                if current_size <= target_size_mb:
                    break
                to_remove.append(report)
                current_size -= report.stat().st_size / (1024 * 1024)
        else:
            return
        
        for report in to_remove:
            try:
                report.unlink()
            except Exception:
                pass  # Ignore deletion errors
    
    def _run(self):
        """Background thread main loop."""
        while self.running:
            try:
                item = self.queue.get(timeout=0.5)
                
                # None is sentinel value for shutdown
                if item is None:
                    break
                
                trigger_type, exception, context, severity = item
                self._generate_report(trigger_type, exception, context, severity)
                
            except queue.Empty:
                continue
            except Exception as e:
                # Log error but continue running
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in crash reporter: {e}", exc_info=True)
    
    def _generate_report_sync(self, trigger_type: str, exception: Exception = None,
                             context: Dict = None, severity: str = 'error'):
        """Generate crash report synchronously (for fatal errors)."""
        self._generate_report(trigger_type, exception, context, severity)
    
    def _generate_report(self, trigger_type: str, exception: Exception = None,
                        context: Dict = None, severity: str = 'error'):
        """
        Generate crash report.
        
        Args:
            trigger_type: Type of trigger
            exception: Optional exception object
            context: Execution context
            severity: Severity level
        """
        try:
            now = datetime.now(timezone.utc)
            report = {
                'timestamp': now.isoformat().replace('+00:00', 'Z'),
                'report_id': f"crash_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                'trigger_type': trigger_type,
                'severity': severity,
            }
            
            # Add exception info
            if exception:
                report['exception'] = {
                    'type': type(exception).__name__,
                    'message': str(exception),
                    'stack_trace': traceback.format_exc()
                }
            
            # Add context
            report['context'] = context or {}
            report['context']['fatal'] = exception is not None and self._is_fatal_error(exception)
            
            # Add execution trace tail (last N entries)
            if self.tracer:
                # Get last entries from tracer (would need tracer to expose this)
                # For now, just note that trace is available
                report['execution_trace_available'] = True
            
            # Add system info
            report['system_info'] = self._get_system_info()
            
            # Add config snapshot (relevant sections only)
            report['config_snapshot'] = {
                'debug_enabled': self.config.enabled,
                'tracing_enabled': self.config.tracing.enabled,
                'crash_reports_enabled': self.config.crash_reports.enabled,
            }
            
            # Write report to file
            report_file = self.crash_report_dir / f"{report['report_id']}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            # Log error but don't raise (would cause infinite loop)
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating crash report: {e}", exc_info=True)
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dictionary with system info
        """
        info = {}
        
        if HAS_PSUTIL:
            try:
                info['memory_mb'] = psutil.virtual_memory().total / (1024 * 1024)
                info['memory_used_mb'] = psutil.virtual_memory().used / (1024 * 1024)
                info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
                
                # Disk space
                crash_dir = self.crash_report_dir
                disk_usage = shutil.disk_usage(crash_dir)
                info['free_disk_mb'] = disk_usage.free / (1024 * 1024)
                info['total_disk_mb'] = disk_usage.total / (1024 * 1024)
            except Exception:
                pass
        
        return info

