"""
Background scheduler daemon for automated daily data updates.

This service runs continuously and schedules daily updates using APScheduler.
Designed for Docker container deployment.
"""

import sys
import signal
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from services.update_runner import run_update


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchedulerDaemon:
    """Daemon service for scheduling daily data updates."""
    
    def __init__(self, update_hour: int = 1, update_minute: int = 0):
        """
        Initialize scheduler daemon.
        
        Args:
            update_hour: Hour of day to run updates (0-23)
            update_minute: Minute of hour to run updates (0-59)
        """
        self.scheduler = BlockingScheduler(timezone='UTC')
        self.update_hour = update_hour
        self.update_minute = update_minute
        self.running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def _job_listener(self, event):
        """Listen to job execution events."""
        if event.exception:
            logger.error(f"Job failed: {event.exception}")
        else:
            logger.info(f"Job executed successfully at {datetime.utcnow()}")
    
    def _run_update(self):
        """Wrapper for update job."""
        try:
            logger.info("Starting scheduled daily update...")
            result = run_update()
            
            if result.get('status') == 'success':
                logger.info("Daily update completed successfully")
            else:
                logger.error(f"Daily update failed: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            logger.error(f"Unexpected error in update job: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler daemon."""
        logger.info("=" * 80)
        logger.info("Scheduler Daemon Starting")
        logger.info("=" * 80)
        logger.info(f"Scheduled update time: {self.update_hour:02d}:{self.update_minute:02d} UTC daily")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)
        
        # Add job listener
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # Add daily update job
        self.scheduler.add_job(
            self._run_update,
            'cron',
            hour=self.update_hour,
            minute=self.update_minute,
            id='daily_update',
            name='Daily Data Update',
            replace_existing=True
        )
        
        # Run immediately on startup (optional - comment out if you don't want this)
        # logger.info("Running initial update on startup...")
        # self._run_update()
        
        self.running = True
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler interrupted")
            self.stop()
    
    def stop(self):
        """Stop the scheduler daemon."""
        if self.running:
            logger.info("Stopping scheduler...")
            self.scheduler.shutdown(wait=True)
            self.running = False
            logger.info("Scheduler stopped")


def main():
    """Main entry point for scheduler daemon."""
    import os
    
    # Get update time from environment variables (default: 1:00 AM UTC)
    update_hour = int(os.getenv('UPDATE_HOUR', '1'))
    update_minute = int(os.getenv('UPDATE_MINUTE', '0'))
    
    daemon = SchedulerDaemon(update_hour=update_hour, update_minute=update_minute)
    daemon.start()


if __name__ == '__main__':
    main()

