"""
Background logging service for execution traces.

Writes JSONL entries from queue in a background thread to prevent blocking execution.
"""

import json
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler

from backtester.config.core.accessor import DebugConfig


class LoggingService:
    """
    Background thread service for writing JSONL execution traces.
    
    Consumes entries from a queue and writes them to a rotating log file.
    """
    
    def __init__(self, config: DebugConfig, entry_queue: queue.Queue):
        """
        Initialize logging service.
        
        Args:
            config: Debug configuration
            entry_queue: Queue to consume entries from
        """
        self.config = config
        self.queue = entry_queue
        self.log_file = Path(config.logging.execution_trace_file)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup rotating file handler
        self.handler = RotatingFileHandler(
            str(self.log_file),
            maxBytes=config.logging.rotation.max_bytes,
            backupCount=config.logging.rotation.backup_count,
            encoding='utf-8'
        )
    
    def start(self):
        """Start the background logging thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self, timeout: float = 5.0):
        """
        Stop the background logging thread.
        
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
        
        if self.thread:
            self.thread.join(timeout=timeout)
        
        # Close handler
        if self.handler:
            self.handler.close()
    
    def _run(self):
        """Background thread main loop."""
        buffer = []
        buffer_size = 10  # Batch writes
        last_flush = time.time()
        flush_interval = 1.0  # Flush every second
        
        while self.running:
            try:
                # Wait for entry with timeout
                entry = self.queue.get(timeout=0.5)
                
                # None is sentinel value for shutdown
                if entry is None:
                    break
                
                buffer.append(entry)
                
                # Flush if buffer full or timeout reached
                now = time.time()
                if len(buffer) >= buffer_size or (now - last_flush) >= flush_interval:
                    self._flush_buffer(buffer)
                    buffer.clear()
                    last_flush = now
                
            except queue.Empty:
                # Timeout - flush buffer if needed
                if buffer:
                    now = time.time()
                    if (now - last_flush) >= flush_interval:
                        self._flush_buffer(buffer)
                        buffer.clear()
                        last_flush = now
                continue
            except Exception as e:
                # Log error but continue running
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in logging service: {e}", exc_info=True)
        
        # Flush remaining buffer on shutdown
        if buffer:
            self._flush_buffer(buffer)
    
    def _flush_buffer(self, buffer: list):
        """Write buffered entries to log file."""
        with self.lock:
            for entry in buffer:
                try:
                    # Format as JSON line
                    json_line = json.dumps(entry, ensure_ascii=False)
                    self.handler.stream.write(json_line + '\n')
                except Exception as e:
                    # Log error but continue
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error writing log entry: {e}", exc_info=True)
            
            # Flush to disk
            try:
                self.handler.stream.flush()
            except Exception:
                pass  # Ignore flush errors

