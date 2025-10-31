#!/usr/bin/env python3
"""
Simple crypto backtesting engine.
Run: python main.py
Quick test: python main.py --quick
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Configure logging (INFO level - set to DEBUG for troubleshooting)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# Store original excepthook for restoration
_original_excepthook = sys.excepthook

# Add src directory to Python path for imports
src_path = Path(__file__).parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from backtester.cli.parser import parse_arguments
from backtester.cli.output import ConsoleOutput
from backtester.config import ConfigManager
from backtester.backtest.runner import BacktestRunner
from backtester.strategies import get_strategy_class

# Global debug components (set after config load)
_debug_tracer = None
_crash_reporter = None


def debug_excepthook(exc_type, exc_value, exc_traceback):
    """
    Global exception handler that captures uncaught exceptions.
    
    Always captures fatal exceptions synchronously before calling original handler.
    """
    global _crash_reporter
    
    # Always capture uncaught exceptions if crash reporter available
    if _crash_reporter:
        try:
            exception = exc_value if exc_value else exc_type()
            context = {'fatal': True, 'uncaught': True}
            
            # Capture synchronously (fatal errors)
            _crash_reporter.capture(
                'exception',
                exception=exception,
                context=context,
                severity='error',
                sync=True
            )
        except Exception:
            # Ignore errors in exception handler to prevent infinite loop
            pass
    
    # Call original handler
    _original_excepthook(exc_type, exc_value, exc_traceback)


def validate_dependencies():
    """Ensure required dependencies are available."""
    try:
        import psutil
    except ImportError:
        print("\n" + "="*80)
        print("ERROR: Missing required dependency")
        print("="*80)
        print("\npsutil is required for parallel execution.")
        print("\nInstall dependencies:")
        print("  pip install -r requirements.txt")
        print("\n" + "="*80)
        sys.exit(1)


def main():
    """Main entry point for the backtesting engine."""
    # Validate dependencies first
    validate_dependencies()
    
    # Parse CLI arguments
    args = parse_arguments()
    
    # Load configuration
    config_start = time.time()
    config = ConfigManager(profile_name=args.profile)
    config_time = time.time() - config_start
    
    # Initialize debug components if enabled
    global _debug_tracer, _crash_reporter
    debug_config = config.get_debug_config()
    
    if debug_config.enabled:
        from backtester.debug import ExecutionTracer, CrashReporter
        
        # Create tracer
        if debug_config.tracing.enabled:
            _debug_tracer = ExecutionTracer(debug_config)
        
        # Create crash reporter
        if debug_config.crash_reports.enabled:
            _crash_reporter = CrashReporter(debug_config, tracer=_debug_tracer)
            _crash_reporter.start()
        
        # Make debug components globally accessible
        from backtester.debug import set_debug_components
        set_debug_components(_debug_tracer, _crash_reporter)
        
        # Install global exception handler
        sys.excepthook = debug_excepthook
    
    # Setup output handler
    output = ConsoleOutput(verbose=config.get_walkforward_verbose())
    
    # Print banner
    output.print_banner(config, quick_mode=args.quick)
    
    # Print config loading info
    output.print_config_loading(config_time)
    
    # Initialize session tracking
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_start_time = time.time()
    
    # Get hardware profile
    from backtester.backtest.execution.hardware import HardwareProfile
    hardware = HardwareProfile.get_or_create()
    
    # Emit session_start event
    if _debug_tracer:
        _debug_tracer.trace('session_start',
                          "Starting backtesting session",
                          session_id=session_id,
                          hardware_signature=hardware.signature)
    
    # Get strategy class
    strategy_class = get_strategy_class(config.get_strategy_name())
    
    # Always run walk-forward optimization
    runner = BacktestRunner(config, output)
    wf_results = runner.run_walkforward_analysis(strategy_class)
    
    # Print overall summary
    if wf_results:
        print("\n" + "="*100)
        print("OVERALL WALK-FORWARD SUMMARY")
        print("="*100)
        print(f"Total combinations analyzed: {len(wf_results)}")
        print(f"Successful: {len([r for r in wf_results if r.successful_windows > 0])}")
        
        # Aggregate across all results
        if wf_results:
            avg_oos_return = sum(r.avg_oos_return_pct for r in wf_results) / len(wf_results)
            print(f"Average OOS Return: {avg_oos_return:.2f}%")
        
        # Group and display by symbol/timeframe, then period/fitness
        from collections import defaultdict
        grouped = defaultdict(list)
        for result in wf_results:
            key = f"{result.symbol} {result.timeframe}"
            grouped[key].append(result)
        
        print(f"\nBreakdown by Symbol/Timeframe:")
        for key, results in grouped.items():
            print(f"\n{key}:")
            for result in results:
                print(f"  Period: {result.period_str}, Fitness: {result.fitness_function}")
                print(f"    Avg OOS Return: {result.avg_oos_return_pct:.2f}%, Windows: {result.successful_windows}/{result.total_windows}")
        
        print("="*100)
    
    # Calculate session metrics
    session_time = time.time() - session_start_time
    total_workflows = len(wf_results) if wf_results else 0
    
    # Calculate total backtests from workflow results
    total_backtests = 0
    successful_backtests = 0
    failed_backtests = 0
    skipped_backtests = 0
    
    if wf_results:
        for result in wf_results:
            total_backtests += result.total_windows
            successful_backtests += result.successful_windows
            failed_backtests += (result.total_windows - result.successful_windows)
    
    # Emit session_end event
    if _debug_tracer:
        _debug_tracer.trace('session_end',
                          "Session complete",
                          session_id=session_id,
                          performance={
                              'total_wall_time_seconds': session_time,
                              'total_workflows': total_workflows,
                              'total_backtests': total_backtests,
                              'successful_backtests': successful_backtests,
                              'failed_backtests': failed_backtests,
                              'skipped_backtests': skipped_backtests
                          })
    
    # Shutdown debug components
    if _debug_tracer:
        _debug_tracer.shutdown()
    if _crash_reporter:
        _crash_reporter.stop()


if __name__ == '__main__':
    try:
        main()
    finally:
        # Ensure cleanup on exit
        if _crash_reporter:
            _crash_reporter.stop()
        if _debug_tracer:
            _debug_tracer.shutdown()
